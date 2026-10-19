#!/usr/bin/env python3
# name: CodeArts 每日福利领取
# cron: 52 1 * * *
# 上游作者及来源：L0NE-6/CodeArts-Daily，codearts_daily.py
# 许可证：MIT（保留上游署名；所提供源文件无其他版权声明）
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
CodeArts 每日福利领取：每日登录积分与新人一次性注册礼。
CODEARTS_CREDENTIALS：每个非空行一个账号，单行 JSON 或 AK|SK|STS。
从官方 CodeArts 客户端已登录会话取得 access_key_id、secret_access_key、
security_token；不可使用其他应用的永久 AK/SK 替代临时登录凭据。
可在自己设备上查看官方客户端登录态或自己的 HTTPS 登录响应，不分享凭据。
JSON 可含 expiration、domain_id、user_name；续期需 refresh_token 与同次登录的
 oauth_context.pkce_pair.code_verifier、oauth_context.dpop_key_pair.private_key_jwk。
保留 camelCase/ak/sk/sts 别名。STS 文本中的 | 不再拆分；不以 &/@ 分隔账号。
续期可选依赖 cryptography（公共 PyPI），不自动安装。
--preview 仅查询，不续期或写台账；--only N 选择原始行序号；--force 显式绕过
本地每日六次、十分钟间隔限制；--no-notify 或 QINGLONG_NOTIFY=0 关闭通知。
CODEARTS_DRY_RUN=1 完全断网，不读写台账，不发送通知（输出模拟通知摘要）。
正常模式保留领取/确认/回读；学生认证、邀请好友不自动领取。
状态保存在脚本目录，原子写入、权限 0600；请勿将凭据状态文件公开上传。
上游未指定 cron，本维护版建议北京时间每日 08:15，面板时区需为亚洲/上海。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('b896028c3fdcd52d', 'scripts/codearts_daily.py', 'codearts_daily.py', 'codearts_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import urllib.request
import urllib.error
import urllib.parse
import importlib.util
import tempfile
import argparse

DRY_RUN = os.environ.get("CODEARTS_DRY_RUN", "").lower() in ("1", "true", "yes", "on")
STATS = None

class TaskError(RuntimeError):
    pass

class Response:
    def __init__(self, status, content):
        self.status_code = status
        self.content = content
    def json(self):
        return json.loads(self.content)


try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

BASE = "https://snap-access.cn-north-4.myhuaweicloud.com"
DELIVERY_PATH = "/v1/ops/delivery?channel=IDE"
CLAIM_PATH = "/v1/ops/claim"
CONFIRM_PATH = "/v1/ops/confirm"
TOKEN_URL = "https://sts.cn-north-4.myhuaweicloud.com/v1/oauth2/tokens"
CLIENT_ID = "vscode-codebot"
REFRESH_LEAD_SECONDS = 15 * 60
SIGN_ALGORITHM = "SDK-HMAC-SHA256"
EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
STORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codearts_credentials.json")
LEDGER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codearts_welfare_ledger.json")
LEDGER_VERSION = 2
MAX_ATTEMPTS_PER_DAY = 6
MIN_ATTEMPT_GAP_SECONDS = 10 * 60
BEIJING_OFFSET_SECONDS = 8 * 60 * 60

ONLY = None
PREVIEW_ONLY = False
NO_NOTIFY = False
FORCE = False


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


def split_accounts(raw):
    return [line.strip() for line in (raw or "").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]

def request(method, url, headers=None, body=None, data=None, timeout=20, retries=3):
    if DRY_RUN:
        raise TaskError("断网预演禁止网络请求")
    if not url.startswith("https://"):
        raise TaskError("仅允许 HTTPS 请求")
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    elif isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode("utf-8")
    elif isinstance(data, str):
        data = data.encode("utf-8")
    # No redirect forwarding of credentials; POST is never automatically retried.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    attempts = retries if method.upper() == "GET" else 1
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
            try:
                response = opener.open(req, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                content = response.read(2 * 1024 * 1024 + 1)
                if len(content) > 2 * 1024 * 1024:
                    raise TaskError("响应过大，已拒绝")
                return Response(response.code, content)
        except TaskError:
            raise
        except Exception:
            if attempt + 1 >= attempts:
                raise TaskError("网络或 TLS 请求失败，请检查服务与网络") from None
            time.sleep(attempt + 1)

def json_of(response):
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except Exception:
        raise TaskError("接口响应不是有效 JSON 对象") from None

def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


TITLE_BY_TYPE = {
    "DAILY_CLAIM": "每日签到",
    "USER_LOGIN": "用户登录送积分",
    "NEW_USER_REGISTER": "新用户注册礼",
    "STUDENT_CERTIFIED": "学生认证",
    "INVITE_USER": "邀请好友",
}


def display_title(campaign):
    """活动标题按活动类映射中文；认不出的类回退上游原文（再空才回退 type）。"""
    mapped = TITLE_BY_TYPE.get(campaign.get("type") or "")
    if mapped:
        return mapped
    return (campaign.get("title") or campaign.get("type") or "活动").strip()


# ---------- 华为云 SDK-HMAC-SHA256 签名 ----------

def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def hmac_sha256_hex(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def encode_component(raw):
    safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()"
    out = []
    for byte in raw:
        if byte in safe:
            out.append(chr(byte))
        else:
            out.append("%%%02X" % byte)
    return "".join(out)




def unescape(raw, plus_as_space):
    # Go 按字节处理：非 ASCII 字符先展开成 UTF-8 字节再逐个处理
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    out = bytearray()
    index = 0
    while index < len(data):
        byte = data[index]
        if byte == 0x25:                       # '%'
            if index + 2 >= len(data):
                return None
            try:
                out.append(int(data[index + 1:index + 3].decode("ascii"), 16))
            except ValueError:
                return None
            index += 3
        elif byte == 0x2B and plus_as_space:   # '+'
            out.append(0x20)
            index += 1
        else:
            out.append(byte)
            index += 1
    return bytes(out)


def canonical_uri(path_bytes):
    if not path_bytes:
        return "/"
    segments = [encode_component(segment) for segment in path_bytes.split(b"/")]
    escaped = "/".join(segments)
    if not escaped.endswith("/"):
        escaped += "/"
    return escaped


def query_pairs(raw_query):
    pairs = []
    for part in raw_query.split("&"):
        if not part or ";" in part:
            continue
        key, _, value = part.partition("=")
        key_bytes = unescape(key, True)
        value_bytes = unescape(value, True)
        if key_bytes is None or value_bytes is None:
            continue
        pairs.append((key_bytes, value_bytes))
    return pairs


def canonical_query_string(raw_query):
    pairs = query_pairs(raw_query)
    if not pairs:
        return ""
    pairs.sort(key=lambda item: (encode_component(item[0]), item[1]))
    return "&".join("%s=%s" % (encode_component(key), encode_component(value)) for key, value in pairs)


def sdk_date_now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def sign_request(method, url, headers, body_bytes, credential, include_host=False):
    """返回应发出去的头集合（含 Authorization），按上游 SDK-HMAC-SHA256 规范签名。"""
    if not credential.get("access_key_id") or not credential.get("secret_access_key"):
        raise RuntimeError("凭据不完整：缺少 access key 或 secret key")

    items = []          # [(name, value)]，同名大小写无关覆盖、位置不变

    def put(name, value):
        lower = name.lower()
        for index, (existing, _) in enumerate(items):
            if existing.lower() == lower:
                items[index] = (existing, value)
                return
        items.append((name, value))

    for name, value in (headers or {}).items():
        put(name, value)
    if credential.get("security_token"):
        put("X-Security-Token", credential["security_token"])
    if credential.get("domain_id"):
        put("X-Domain-Id", credential["domain_id"])
    if not any(name.lower() == "x-sdk-date" for name, _ in items):
        put("X-Sdk-Date", sdk_date_now())

    parsed = urlsplit(url)
    authority = parsed.netloc
    if include_host:
        put("Host", authority)

    date = next(value for name, value in items if name.lower() == "x-sdk-date")
    canonical = sorted(((name.lower(), value.strip()) for name, value in items), key=lambda item: item[0])
    canonical_headers = "".join("%s:%s\n" % (name, value) for name, value in canonical)
    signed_headers = ";".join(name for name, _ in canonical)

    payload_hash = sha256_hex(body_bytes)
    override = next((value for name, value in canonical if name == "x-sdk-content-sha256" and value), None)
    if override:
        payload_hash = override
    elif method.upper() not in ("PUT", "PATCH", "POST"):
        payload_hash = EMPTY_BODY_SHA256

    path_bytes = unescape(parsed.path, False)
    if path_bytes is None:
        raise RuntimeError("URL 路径转义非法")
    canonical_request = "\n".join([
        method.upper(), canonical_uri(path_bytes), canonical_query_string(parsed.query),
        canonical_headers, signed_headers, payload_hash,
    ])
    string_to_sign = "\n".join([SIGN_ALGORITHM, date, sha256_hex(canonical_request.encode("utf-8"))])
    signature = hmac_sha256_hex(credential["secret_access_key"].encode("utf-8"), string_to_sign)
    put("Authorization", "%s Access=%s, SignedHeaders=%s, Signature=%s"
        % (SIGN_ALGORITHM, credential["access_key_id"], signed_headers, signature))

    return {name: value for name, value in items}


# ---------- 凭据解析 / 存储 / 续期 ----------

def normalize_credential(raw):
    oauth = raw.get("oauth_context") if isinstance(raw.get("oauth_context"), dict) else {}
    pkce = oauth.get("pkce_pair") if isinstance(oauth.get("pkce_pair"), dict) else {}
    dpop = oauth.get("dpop_key_pair") if isinstance(oauth.get("dpop_key_pair"), dict) else {}
    jwk = dpop.get("private_key_jwk") if isinstance(dpop.get("private_key_jwk"), dict) else {}
    return {
        "access_key_id": first_text(raw.get("access_key_id"), raw.get("accessKeyId"), raw.get("ak")),
        "secret_access_key": first_text(raw.get("secret_access_key"), raw.get("secretAccessKey"), raw.get("sk")),
        "security_token": first_text(raw.get("security_token"), raw.get("securityToken"), raw.get("sts")),
        "expiration": first_text(raw.get("expiration"), raw.get("expires_at"), raw.get("expiresAt")),
        "refresh_token": first_text(raw.get("refresh_token"), raw.get("refreshToken")),
        "domain_id": first_text(raw.get("domain_id"), raw.get("domainId")),
        "user_name": first_text(raw.get("user_name"), raw.get("userName")),
        "code_verifier": first_text(pkce.get("code_verifier"), raw.get("code_verifier")),
        "dpop_jwk": jwk,
        "note": first_text(raw.get("note")),
    }


def parse_accounts(raw):
    accounts = []
    for index, line in enumerate(split_accounts(raw), 1):
        try:
            if line.startswith("{"):
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError()
                credential = normalize_credential(value)
            else:
                ak, rest = line.split("|", 1)
                sk, sts = rest.split("|", 1)
                credential = normalize_credential({"ak": ak.strip(), "sk": sk.strip(), "sts": sts.strip()})
            if not all(credential[k] for k in ("access_key_id", "secret_access_key", "security_token")):
                raise ValueError()
            credential["_store_key"] = identity_of(credential)
            accounts.append(credential)
        except Exception:
            accounts.append({"_invalid": True})
    return accounts

def identity_of(credential):
    if credential.get("_store_key"):
        return credential["_store_key"]
    identity = ((credential.get("domain_id", "") + ":" + credential["user_name"])
                if credential.get("user_name") else credential.get("access_key_id"))
    return hashlib.sha256(str(identity).encode("utf-8")).hexdigest()

def load_store():
    return read_state(STORE_FILE)

def save_store(store):
    atomic_state(STORE_FILE, store)

def apply_store(credential):
    saved = load_store().get(identity_of(credential))
    if not isinstance(saved, dict):
        return False
    for key in ("access_key_id", "secret_access_key", "security_token", "expiration",
                "refresh_token", "domain_id", "user_name", "code_verifier"):
        if saved.get(key):
            credential[key] = saved[key]
    if isinstance(saved.get("dpop_jwk"), dict) and saved["dpop_jwk"]:
        credential["dpop_jwk"] = saved["dpop_jwk"]
    return True


def persist(credential):
    store = load_store()
    store[identity_of(credential)] = {key: credential.get(key) for key in (
        "access_key_id", "secret_access_key", "security_token", "expiration",
        "refresh_token", "domain_id", "user_name", "code_verifier")}
    store[identity_of(credential)]["dpop_jwk"] = credential.get("dpop_jwk") or {}
    store[identity_of(credential)]["at"] = int(time.time())
    save_store(store)


def expires_within(credential, seconds):
    text = credential.get("expiration", "")
    if not text:
        return True
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z"):
        try:
            moment = datetime.strptime(text.replace("+00:00", "Z"), fmt)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return moment.timestamp() - time.time() < seconds
        except ValueError:
            continue
    return True


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text):
    text += "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text)


def dpop_proof(jwk, method, url):
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    except Exception:
        raise RuntimeError("缺少 cryptography 库，无法生成 DPoP proof（pip install cryptography）")
    scalar = int.from_bytes(b64url_decode(jwk.get("d", "")), "big")
    key = ec.derive_private_key(scalar, ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    header = {"alg": "ES256", "typ": "dpop+jwt",
              "jwk": {"kty": "EC", "crv": "P-256", "x": b64url(x), "y": b64url(y)}}
    payload = {"htm": method.upper(), "htu": url, "iat": int(time.time()),
               "jti": os.urandom(32).hex()}
    signing_input = "%s.%s" % (
        b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
        b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
    )
    der = key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return "%s.%s" % (signing_input, b64url(raw))


def refresh_credential(credential):
    if not credential.get("refresh_token") or not credential.get("code_verifier"):
        raise RuntimeError("凭据缺少 refresh_token 或 code_verifier，无法续期")
    jwk = credential.get("dpop_jwk") or {}
    if not jwk.get("d"):
        raise RuntimeError("凭据缺少 DPoP 私钥（oauth_context.dpop_key_pair.private_key_jwk）")
    proof = dpop_proof(jwk, "POST", TOKEN_URL)
    form = {
        "client_id": CLIENT_ID,
        "code_verifier": credential["code_verifier"],
        "grant_type": "refresh_token",
        "refresh_token": credential["refresh_token"],
    }
    response = request("POST", TOKEN_URL,
                       headers={"Content-Type": "application/x-www-form-urlencoded",
                                "Accept": "application/json", "DPoP": proof},
                       data=form, timeout=30)
    payload = json_of(response)
    if response.status_code < 200 or response.status_code >= 300:
        raise TaskError("令牌续期被拒：HTTP %s" % response.status_code)
    data = payload.get("credentials") if isinstance(payload.get("credentials"), dict) else payload

    def read(name):
        value = data.get(name)
        if isinstance(value, str):
            return value.strip()
        value = payload.get(name)
        return value.strip() if isinstance(value, str) else ""

    fresh = {
        "access_key_id": read("access_key_id"),
        "secret_access_key": read("secret_access_key"),
        "security_token": read("security_token"),
        "expiration": first_text(read("expiration"), read("expires_at")),
        "refresh_token": read("refresh_token") or credential["refresh_token"],
    }
    if not fresh["access_key_id"] or not fresh["secret_access_key"] or not fresh["security_token"]:
        raise RuntimeError("令牌响应缺少 AK/SK/STS")
    for key in ("domain_id", "user_name", "code_verifier", "dpop_jwk", "note", "_store_key"):
        fresh[key] = credential.get(key, "" if key != "dpop_jwk" else {})
    persist(fresh)
    log("   🔄 凭据已续期并保存")
    return fresh


def ensure_fresh(credential):
    if not expires_within(credential, REFRESH_LEAD_SECONDS):
        return credential
    if credential.get("refresh_token") and credential.get("code_verifier") and (credential.get("dpop_jwk") or {}).get("d"):
        try:
            return refresh_credential(credential)
        except Exception as error:
            raise TaskError("自动续期失败，请重新获取登录凭据") from None
    log("   ⚠️ 凭据已临近到期且未配置完整续期材料，直接尝试（失败请重新登录获取新凭据）")
    return credential


# ---------- 本地台账（幂等键 + 写请求限流） ----------

def beijing_day(now_ms=None):
    """北京时间意义上的「今天」：上游活动周期是 UTC+8 零点。"""
    moment = (now_ms if now_ms is not None else int(time.time() * 1000)) / 1000.0 + BEIJING_OFFSET_SECONDS
    return time.strftime("%Y-%m-%d", time.gmtime(moment))


def load_ledger_store():
    return read_state(LEDGER_FILE)

def save_ledger_store(store):
    atomic_state(LEDGER_FILE, store)
    return True

def fresh_ledger():
    return {"version": LEDGER_VERSION, "day": beijing_day(), "attempts": 0, "lastAttemptMs": 0,
            "accepted": False, "campaigns": {}, "newbieSettled": False}


def ledger_of(store, identity):
    """读台账并归一到北京时间「今天」。

    读不懂的台账一律拒绝（版本不对 / 日期越界 / attempts 越界）：当成空台账重来
    会把上一轮的幂等键丢掉，崩溃后重试会被上游当成另一笔领取。
    """
    ledger = fresh_ledger()
    entry = (store.get("accounts") or {}).get(identity)
    if not isinstance(entry, dict):
        return ledger
    ledger["newbieSettled"] = entry.get("newbieSettled") is True
    stored = entry.get("ledger")
    if stored is None:
        return ledger
    day = stored.get("day") if isinstance(stored, dict) else None
    attempts = stored.get("attempts") if isinstance(stored, dict) else None
    if (not isinstance(stored, dict) or stored.get("version") != LEDGER_VERSION
            or not isinstance(day, str) or not isinstance(attempts, int)
            or attempts < 0):
        raise RuntimeError("本地领取台账无效，未发送领取请求；请备份并核查记录，勿直接删除幂等记录")
    today = beijing_day()
    if day > today:
        raise RuntimeError("系统日期（%s）早于领取记录（%s），先纠正时钟再领取" % (today, day))
    if day < today:
        return ledger
    ledger["day"] = day
    ledger["attempts"] = attempts
    ledger["lastAttemptMs"] = stored.get("lastAttemptMs") if isinstance(stored.get("lastAttemptMs"), int) else 0
    ledger["accepted"] = stored.get("accepted") is True
    campaigns = stored.get("campaigns")
    if not isinstance(campaigns, dict) or any(not isinstance(value, dict) for value in campaigns.values()):
        raise TaskError("本地活动幂等记录无效，已停止写操作")
    ledger["campaigns"] = campaigns
    return ledger


def persist_ledger(store, identity, ledger):
    accounts = store.setdefault("accounts", {})
    entry = accounts.get(identity)
    if not isinstance(entry, dict):
        entry = {}
    entry["ledger"] = {key: ledger.get(key) for key in (
        "version", "day", "attempts", "lastAttemptMs", "accepted", "campaigns")}
    entry["newbieSettled"] = ledger.get("newbieSettled") is True
    entry["at"] = int(time.time())
    accounts[identity] = entry
    if not save_ledger_store(store):
        raise RuntimeError("领取台账写入失败，为避免重复领取已中止（检查脚本目录写权限）")


def gap_remaining_seconds(ledger):
    last = ledger.get("lastAttemptMs") or 0
    if not isinstance(last, int) or last <= 0:
        return 0
    elapsed = max(0, int(time.time() * 1000) - last)
    return max(0, MIN_ATTEMPT_GAP_SECONDS - elapsed // 1000)


# ---------- ops 请求与领取流程 ----------

def welfare_request(credential, method, path, body=None):
    label = {DELIVERY_PATH: "读取福利活动", CLAIM_PATH: "领取福利", CONFIRM_PATH: "确认福利"}[path]
    started = time.monotonic()
    if STATS is not None:
        STATS["total"] += 1
        number = STATS["total"]
    else:
        number = 1
    log("阶段 %d：%s 开始" % (number, label))
    try:
        url = BASE + path
        headers = {"Content-Type": "application/json", "Agent-Type": "PromptCenter", "X-Language": "en-us"}
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if body is not None else b""
        signed = sign_request(method, url, headers, payload, credential, include_host=False)
        response = request(method, url, headers=signed, data=payload if body is not None else None, timeout=20)
        if response.status_code != 200:
            raise TaskError("福利接口 HTTP %s，未确认成功" % response.status_code)
        parsed = json_of(response)
        if type(parsed.get("code")) is not int or parsed["code"] != 0:
            hint = benefit_hint(json.dumps(parsed, ensure_ascii=False))
            raise TaskError("福利接口业务状态未确认成功" + hint)
        data = parsed.get("data")
        if isinstance(data, dict):
            for field in ("nickname", "user_name", "userName", "displayName", "username", "uid"):
                if isinstance(data.get(field), (str, int)) and not isinstance(data.get(field), bool):
                    identity = str(data[field]).replace("\n", " ").replace("\r", " ")
                    # Do not print a returned identity if it equals credential material or a phone number.
                    secrets = [str(credential.get(k, "")) for k in ("access_key_id", "secret_access_key", "security_token", "refresh_token", "code_verifier")]
                    if not any(s and s in identity for s in secrets) and not (identity.isdigit() and len(identity) == 11):
                        log("官方账号身份：%s" % identity)
        if STATS is not None:
            STATS["success"] += 1
        log("阶段 %d：%s ✅ code=0；耗时 %.2f 秒" % (number, label, time.monotonic()-started))
        return data
    except Exception:
        if STATS is not None:
            STATS["failed"] += 1
        log("阶段 %d：%s ❌；耗时 %.2f 秒" % (number, label, time.monotonic()-started))
        raise

def benefit_hint(text):
    """「无福利档案」类报错给一句人话：官方建档后重试即可。"""
    lowered = (text or "").lower()
    for token in ("4004", "benefit not found", "档案", "不存在"):
        if token in lowered:
            return "（该账号尚未开通福利档案；官方客户端登录/首次使用时会自动建档，稍后重试即可）"
    return ""


def fetch_deliveries(credential):
    data = welfare_request(credential, "GET", DELIVERY_PATH)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("福利接口没有返回 items 字段")
    campaigns = []
    for item in items:
        if not isinstance(item, dict):
            continue
        campaigns.append({
            "id": item.get("campaignId"),
            "key": str(item.get("campaignId")) if item.get("campaignId") is not None else "",
            "type": item.get("type") or "",
            "title": item.get("title") or "",
            "claimable": item.get("claimable") is True,
            "status": item.get("status") or "",
            "amount": item.get("benefitAmount") or 0,
            "unit": item.get("benefitUnit") or "",
        })
    return campaigns


def is_daily_login(campaign):
    return campaign["type"] == "USER_LOGIN" and campaign["unit"] == "CREDIT" and bool(campaign["key"])


def is_confirmed(campaign):
    return (not campaign["claimable"]) and campaign["status"] in ("CONFIRMED", "CONSUMED")


def is_newbie_gift(campaign):
    """新人注册礼：一次性奖励，与每日福利共用领取执行体；学生认证 / 邀请好友不自动领。"""
    return campaign["type"] == "NEW_USER_REGISTER" and bool(campaign["key"])


def has_work(campaign):
    """这一条还有活要干吗（能领，或领了没确认）。"""
    return campaign["claimable"] or campaign["status"] == "CLAIMED"


def claim_one(credential, campaign, idempotent_key):
    """领一笔（campaignId 原样带回，不改类型）；响应 id 对不上就不进入 confirm 阶段。"""
    data = welfare_request(credential, "POST", CLAIM_PATH,
                           {"campaignId": campaign["id"], "idempotentKey": idempotent_key, "channel": "IDE"})
    returned = str(data.get("campaignId")) if isinstance(data, dict) else ""
    if returned != campaign["key"]:
        raise RuntimeError("领取响应活动 ID 不匹配（要 %s，回 %s），未进入确认阶段" % (campaign["key"], returned))


def do_checkin(credential):
    credential = credential if PREVIEW_ONLY else ensure_fresh(credential)
    identity = identity_of(credential)
    store = {} if PREVIEW_ONLY else load_ledger_store()
    ledger = fresh_ledger() if PREVIEW_ONLY else ledger_of(store, identity)

    campaigns = fetch_deliveries(credential)
    daily = [item for item in campaigns if is_daily_login(item)]
    newbie = [item for item in campaigns if is_newbie_gift(item)]

    if PREVIEW_ONLY:
        rows = []
        for item in daily:
            rows.append("%s:%s(%s)" % (display_title(item), item["status"] or "可领取", item["amount"]))
        for item in newbie:
            state = "已确认" if is_confirmed(item) else (item["status"] or "可领取")
            rows.append("%s:%s(%s)" % (display_title(item), state, item["amount"]))
        return True, "仅预览（--preview）: " + ("; ".join(rows) if rows else "当前没有福利活动"), credential

    # 新人礼是一次性奖励：结清记本机后不再重查（与每日链共用同一份台账与限流）
    daily_work = [item for item in daily if has_work(item)]
    newbie_work = [] if ledger.get("newbieSettled") else [item for item in newbie if has_work(item)]
    todo = daily_work + newbie_work

    if not todo:
        if daily and all(is_confirmed(item) for item in daily):
            extra = "；新人注册礼已确认" if newbie and all(is_confirmed(item) for item in newbie) else ""
            return True, "今日福利已确认到账" + extra, credential
        if newbie and all(is_confirmed(item) for item in newbie) and not daily:
            return True, "新人注册礼已确认到账", credential
        return False, "当前没有可领取的福利活动，无法验证到账", credential

    now_ms = int(time.time() * 1000)
    if not FORCE:
        if ledger["attempts"] >= MAX_ATTEMPTS_PER_DAY:
            return False, "本地限流：今日已提交 %d 次，跳过本轮（--force 可强制重试）" % ledger["attempts"], credential
        wait = gap_remaining_seconds(ledger)
        if wait > 0:
            return False, "本地限流：距上次提交不足 10 分钟（约 %d 秒后重试，--force 可跳过）" % wait, credential

    ledger["attempts"] += 1
    ledger["lastAttemptMs"] = now_ms
    ledger["accepted"] = False
    persist_ledger(store, identity, ledger)   # 幂等键先落盘再发写请求

    submitted = []
    for item in todo:
        key = item["key"]
        progress = ledger["campaigns"].get(key) or {}
        if item["status"] == "CLAIMED":
            progress["claimed"] = True
        if not progress.get("claimed") and item["claimable"]:
            if not progress.get("idempotentKey"):
                progress["idempotentKey"] = "claim_%s_%d" % (key, now_ms)
            ledger["campaigns"][key] = progress
            persist_ledger(store, identity, ledger)
            claim_one(credential, item, progress["idempotentKey"])
            progress["claimed"] = True
            ledger["campaigns"][key] = progress
            persist_ledger(store, identity, ledger)
        if progress.get("claimed"):
            # 已领但未确认：只补 confirm，不重复发 claim
            welfare_request(credential, "POST", CONFIRM_PATH, {"campaignId": item["id"]})
        submitted.append(item)
        time.sleep(1.0)

    # 回读二次确认：claim / confirm 都只回 code:0，那是「受理」不是「到账」
    verified = fetch_deliveries(credential)
    missing = []
    for item in submitted:
        matched = any(seen["key"] == item["key"] and seen["type"] == item["type"] and is_confirmed(seen)
                      for seen in verified)
        if matched:
            progress = ledger["campaigns"].get(item["key"]) or {}
            progress["confirmed"] = True
            ledger["campaigns"][item["key"]] = progress
        else:
            missing.append(display_title(item))
    if missing:
        persist_ledger(store, identity, ledger)
        return False, "请求已提交，但官方活动列表尚未确认到账：%s（稍后重跑会补确认）" % "、".join(missing), credential

    ledger["accepted"] = True
    verified_newbie = [item for item in verified if is_newbie_gift(item)]
    if verified_newbie and all(is_confirmed(item) for item in verified_newbie):
        ledger["newbieSettled"] = True   # 一次性福利结清后记本机，下次不再重查
    persist_ledger(store, identity, ledger)

    parts = []
    done_daily = [item for item in verified if is_daily_login(item) and is_confirmed(item)]
    if done_daily:
        parts.append("每日福利 %s" % sum(float(item["amount"] or 0) for item in done_daily))
    done_newbie = [item for item in verified_newbie if is_confirmed(item)]
    if done_newbie:
        parts.append("新人注册礼 %s" % sum(float(item["amount"] or 0) for item in done_newbie))
    return True, "福利已确认到账：%s（本次提交 %d 笔）" % ("；".join(parts) or "已确认", len(submitted)), credential



def read_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except FileNotFoundError:
        return {}
    except Exception:
        raise TaskError("本地状态文件损坏或无法读取，已停止写操作") from None


def atomic_state(path, data):
    if DRY_RUN:
        raise TaskError("断网预演禁止状态写入")
    temp = None
    try:
        fd, temp = tempfile.mkstemp(prefix=".codearts-", dir=os.path.dirname(path))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        raise TaskError("本地状态保存失败，已停止写操作") from None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def post_json(url, payload, timeout=20):
    return request("POST", url, body=payload, headers={"Content-Type": "application/json"}, timeout=timeout)


def _env(name):
    return os.environ.get(name, "").strip()


def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json("https://www.pushplus.plus/send",
                           {"token": token, "title": title, "content": text, "template": "txt"})
        return str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint or not endpoint.startswith("https://"):
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "CodeArts"})
        return json_of(answer).get("code") == 200
    except Exception:
        return False


def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("https://") and not hook.startswith("http://"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": ("%s\n%s" % (title, content))[:2000]}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(secret.encode(), ("%s\n%s" % (stamp, secret)).encode(),
                              hashlib.sha256).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp, urllib.parse.quote(base64.b64encode(digest)))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False



def notify_summary(content):
    if NO_NOTIFY or os.environ.get("QINGLONG_NOTIFY", "1").lower() in ("0", "false", "no", "off"):
        return "已关闭"
    if DRY_RUN:
        log("通知预演（未发送）：" + content)
        return "断网预演"
    candidates = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "")
    if directory:
        candidates.append(os.path.join(directory, "notify.py"))
    candidates.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    try:
        from notify import send
        send("CodeArts 每日福利领取", content)
        return "已发送"
    except Exception:
        pass
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("codearts_ql_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send("CodeArts 每日福利领取", content)
            return "已发送"
        except Exception:
            continue
    delivered = [handler("CodeArts 每日福利领取", content) for handler in
                 (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk)]
    if any(delivered):
        log("⚠️ 青龙通知不可用；备用渠道已发送，保留业务退出码")
        return "备用渠道已发送"
    log("⚠️ 青龙通知不可用或发送失败，保留业务退出码")
    return "不可用或失败"


def main():
    global PREVIEW_ONLY, NO_NOTIFY, FORCE, STATS
    started = time.monotonic()
    log("========== CodeArts 每日福利领取 ==========")
    log("开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    results = []
    config_error = False
    accounts = parse_accounts(os.environ.get("CODEARTS_CREDENTIALS", ""))
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise TaskError("命令参数无效")
    parser = SafeParser(description="CodeArts 每日福利领取", exit_on_error=False)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--only", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    try:
        args = parser.parse_args()
        PREVIEW_ONLY, NO_NOTIFY, FORCE = args.preview, args.no_notify, args.force
        if not accounts or (args.only is not None and not 1 <= args.only <= len(accounts)):
            raise ValueError()
    except (Exception, SystemExit):
        config_error = True
        log("❌ 配置错误：检查参数及 CODEARTS_CREDENTIALS，每行需完整 AK/SK/STS")
        args = None
    log("模式：%s；账号数：%d" % ("断网预演" if DRY_RUN else ("只读预览" if PREVIEW_ONLY else "福利领取"), len(accounts)))
    if not config_error:
        for index, credential in enumerate(accounts, 1):
            if args.only is not None and index != args.only:
                continue
            moment = time.monotonic()
            STATS = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
            log("账号 %d 开始" % index)
            success = False
            try:
                if credential.get("_invalid"):
                    raise TaskError("账号配置无效：需单行 JSON 或 AK|SK|STS")
                if DRY_RUN:
                    STATS.update(total=3, success=3)
                    for number, label in enumerate(("凭据格式与本地签名", "领取/确认/回读流程", "通知摘要"), 1):
                        if number == 1:
                            signed = sign_request("GET", BASE+DELIVERY_PATH, {"Content-Type":"application/json"}, b"", credential)
                            assert signed.get("Authorization")
                        log("阶段 %d：%s ✅ 预演通过；耗时 0.00 秒；未发请求或写入" % (number, label))
                    success, message = True, "DRY_RUN_OK：配置及流程预演通过，未验证真实业务"
                else:
                    apply_store(credential)
                    success, message, _ = do_checkin(credential)
                    if "已确认到账" in message and "本次提交" not in message:
                        STATS["alreadyComplete"] += 1
                    if not success:
                        STATS["failed"] += 1
                        STATS["total"] += 1
                log(("✅ " if success else "❌ ") + message)
            except Exception as error:
                if STATS["failed"] == 0:
                    STATS["failed"] += 1
                    STATS["total"] += 1
                # Only locally defined safe errors are displayed; never print arbitrary exceptions.
                message = str(error) if isinstance(error, TaskError) else "执行失败：检查凭据、接口契约或本地状态"
                log("❌ " + message)
            elapsed = round(time.monotonic()-moment, 3)
            results.append(dict(account=index, success=success, tasks=dict(STATS), durationSeconds=elapsed))
            log("账号 %d 统计：总任务 %d；成功 %d；已完成 %d；跳过 %d；失败 %d；耗时 %.2f 秒" %
                (index, STATS["total"], STATS["success"], STATS["alreadyComplete"], STATS["skipped"], STATS["failed"], elapsed))
    good = sum(r["success"] for r in results)
    bad = len(results)-good
    code = 1 if config_error or bad or not results else 0
    status = "configuration-error" if config_error else ("dry-run" if DRY_RUN and code==0 else ("success" if code==0 else ("partial-failure" if good else "failure")))
    body = "账号总数 %d，执行 %d，成功 %d，失败 %d；状态 %s" % (len(accounts), len(results), good, bad, status)
    notification = notify_summary(body)
    log("----------------------------------------")
    log("任务统计：" + body)
    totals = {key: sum(r["tasks"][key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("子任务统计：总数 %(total)d；成功 %(success)d；已完成 %(alreadyComplete)d；跳过 %(skipped)d；失败 %(failed)d" % totals)
    finish = time.strftime("%Y-%m-%d %H:%M:%S")
    log("完成时间：%s；总耗时 %.2f 秒；通知：%s；最终状态：%s" % (finish, time.monotonic()-started, notification, status))
    print("TASK_SUMMARY=" + json.dumps(dict(application="codearts", mode="dry-run" if DRY_RUN else "live", status=status, accountCount=len(accounts), processed=len(results), succeeded=good, failed=bad, configurationError=config_error, accounts=results, tasks=totals, notification=notification, finishTime=finish, durationSeconds=round(time.monotonic()-started,3), exitCode=code), ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
