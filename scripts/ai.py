#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AiCheckin 每日签到
# cron: 54 10 * * *
# SPDX-License-Identifier: MIT
# 来源 LiSeafood/AiCheckin/checkin.py，MIT。Trae 设备算法参考 trae-mate，
# Qoder 活动过滤参考 sun-olympic/qoder-checkin。保留上游协议归属。
"""AiCheckin 青龙独立维护版，Python 3.10+，仅使用标准库。

AI_CHECKIN_ACCOUNTS 每个非空行为一个 JSON 对象，service 为 workbuddy、trae 或 qoder，
同一账号的凭据放在同一对象。token 必填。Trae 还需 user_id，可设 region（默认 CN）。
Qoder 还需 machine_id 和 device 对象，其 machineToken、machineCode、machineType
从本人已登录客户端请求头 Cosy-* 获取，不能用随机值替代。
WorkBuddy 在本人客户端 DevTools 的 billing 请求中复制 Authorization 的 Bearer 值。
Trae 在本人客户端 DevTools 的 checkin_credits 请求中复制 Cloud-IDE-JWT 和用户 ID。
Qoder 在本人客户端 DevTools 的 campaigns 请求中复制 Bearer 和上述 Cosy-* 头。
不会运行客户端、读取登录文件或导出凭据。服务凭据不能互换。
兼容 WORKBUDDY_ACCESS_TOKEN / WORKBUDDY_UID，TRAE_TOKEN / TRAE_USER_ID /
TRAE_REGION。每个 token 变量同样按非空行分账号，配套 UID 按行对应。
设置 AI_CHECKIN_DRY_RUN=1 完全离线预演。--no-trae / --no-qoder 保留跳过选项。
上游无 cron 注释，建议每天北京时间 10:15，Qoder 每日 10:00 刷新。
可选 refresh_token 与 expires_at（ISO UTC），Trae 默认临期 24h、Qoder 72h 续期。
续期必须显式设置 CHECKIN_REFRESH_STATE 为专用状态文件，安全保存轮换凭据，
同一状态文件由文件锁保护。请保密备份，不要放入订阅目录或提交到仓库。
未启用状态文件时使用环境凭据签到，过期后在客户端重新取得凭据。
QINGLONG_NOTIFY 控制通知，auto 按 QINGLONG_NOTIFY_SCRIPTS 选择器决定。
"""
from __future__ import annotations
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('89bf4d992b4beaa3', 'scripts/ai.py', 'ai.py', 'ai')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import contextlib
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import random
import re
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TRAE_BASE = "https://api.trae.cn"
TRAE_STATUS_URL = TRAE_BASE + "/trae/api/v2/ug/checkin_credits/status"
TRAE_CLAIM_URL = TRAE_BASE + "/trae/api/v2/ug/checkin_credits/claim"
TRAE_CREDITS_URL = TRAE_BASE + "/trae/api/v2/pay/ide_user_ent_usage"
TRAE_EXCHANGE_URL = "https://api.trae.com.cn/cloudide/api/v3/trae/oauth/ExchangeToken"
TRAE_CLIENT_ID = "en1oxy7wnw8j9n"
QODER_BASE = "https://openapi.qoder.com.cn"
TITLE = "AiCheckin 每日签到"
CATALOG_ID = "89bf4d992b4beaa3"

class TaskError(Exception):
    pass

def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

def number(name, default, low, high):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        raise TaskError(f"{name} 必须为整数") from None
    if not low <= value <= high:
        raise TaskError(f"{name} 超出允许范围")
    return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝接口重定向，保护凭据")

class Client:
    def __init__(self, dry):
        self.dry = dry
        self.timeout = number("CHECKIN_HTTP_TIMEOUT", 30, 1, 120)
        self.attempts = number("CHECKIN_MAX_RETRY", 14, 1, 20)
        self.minimum = number("CHECKIN_RETRY_WAIT_MIN", 15, 0, 300)
        self.maximum = number("CHECKIN_RETRY_WAIT_MAX", 30, self.minimum, 300)
        self.trae_attempts = number("CHECKIN_TRAE_MAX_RETRY", 4, 1, 20)
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, url, headers, body=None, attempts=1):
        if self.dry:
            raise TaskError("离线预演禁止 HTTP")
        data = None if body is None else json.dumps(body).encode()
        headers = dict(headers)
        headers["Accept-Encoding"] = "identity"
        if body is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(1, attempts + 1):
            status, payload = -1, None
            try:
                request = urllib.request.Request(url, data=data, headers=headers,
                                                 method="GET" if body is None else "POST")
                with self.opener.open(request, timeout=self.timeout) as response:
                    status = response.status
                    raw = response.read(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        raise TaskError("响应超过大小限制")
                    payload = json.loads(raw)
            except urllib.error.HTTPError as error:
                status = error.code
            except (OSError, ValueError):
                pass
            retry = status in (-1, 429) or status >= 500
            retry = retry or (isinstance(payload, dict) and str(payload.get("code")) in {"9074", "9004"})
            if not retry or attempt == attempts:
                if status != 200 or not isinstance(payload, dict):
                    raise TaskError(f"接口未返回有效成功响应（HTTP {status}）")
                show_identity(payload)
                return payload
            wait = random.randint(self.minimum, self.maximum)
            if isinstance(payload, dict) and str(payload.get("code")) in {"9074", "9004"}:
                wait = random.randint(60, 90) if attempt > 4 else random.randint(25, 45)
            log(f"请求暂时失败，第 {attempt}/{attempts} 次，等待 {wait} 秒")
            time.sleep(wait)

def show_identity(payload):
    # 只输出官方明确标记的非凭据身份字段，禁止回显服务端自由错误文本。
    nodes = [payload]
    for key in ("data", "user", "account"):
        node = payload.get(key)
        if isinstance(node, dict):
            nodes.append(node)
            if isinstance(node.get("user"), dict):
                nodes.append(node["user"])
    for node in nodes:
        for key in ("nickname", "username", "displayName", "display_name", "uid", "name"):
            value = node.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                if key != "uid" and re.fullmatch(r"\+?\d{11,15}", value):
                    continue
                log(f"官方账号 {key} {json.dumps(value, ensure_ascii=False)}")

def api_ok(body):
    return (not isinstance(body.get("code"), bool) and body.get("code") in (0, 200, "0", "200")
            or body.get("success") is True or body.get("status") == "success")

def jwt_payload(token):
    try:
        part = token.split(".")[1]
        value = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return value if isinstance(value, dict) else {}
    except (ValueError, IndexError, UnicodeError):
        return {}

def parse_expiry(value):
    from datetime import datetime
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("缺少时区")
    return parsed.timestamp()


def expiry(account):
    value = account.get("expires_at")
    if value:
        from datetime import datetime
        try:
            return parse_expiry(value)
        except (ValueError, TypeError):
            raise TaskError("expires_at 必须为带时区的 ISO 时间") from None
    value = jwt_payload(account["token"]).get("exp")
    return value if isinstance(value, (int, float)) else None

def _seeded_stream(seed: str, salt: str, nbytes: int) -> bytes:
    """确定性字节流: SHA256(f"{salt}:{seed}" || counter_be32) 连续拼接。"""
    data = f"{salt}:{seed}".encode("utf-8")
    out = b""
    i = 0
    while len(out) < nbytes:
        out += hashlib.sha256(data + struct.pack(">I", i)).digest()
        i += 1
    return out[:nbytes]


def _trae_device_digits(n: int, seed: str) -> str:
    return "".join(str(b % 10) for b in _seeded_stream(seed, "devid", n + 1)[:n])


def _trae_device_hex(n: int, seed: str) -> str:
    return _seeded_stream(seed, "sess", (n + 1) // 2).hex()[:n]


def _trae_market_uuid(seed: str) -> str:
    bs = bytearray(_seeded_stream(seed, "market", 16))
    bs[6] = (bs[6] & 0x0F) | 0x40   # UUID v4 版本位
    bs[8] = (bs[8] & 0x3F) | 0x80   # RFC 4122 variant 位
    h = bs.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def trae_device_identity(user_id: str) -> dict:
    """按 user_id 确定性派生一套稳定的伪设备身份(trae-mate gen 2 算法)。

    同一 user_id 永远得到同一套标识,服务端按设备维度记账也保持稳定。
    测试向量(user_id="1234567890123456"): device_id=413174708280782,
    session_id=fbabf7aa1e173b90385c623e1ec49157860cc07a4b01f53f7ca141b17d876eae,
    market_user_id=746608f9-7f37-4960-b4c7-8553cec6d366。
    """
    return {
        "device_id": _trae_device_digits(15, user_id),
        "market_user_id": _trae_market_uuid(user_id),
        "session_id": _trae_device_hex(64, user_id),
    }


def build_trae_headers(token: str, user_id: str) -> dict:
    """Trae 签到接口的完整请求头(逆向自 trae-mate checkin.rs)。

    旧版只带 x-device-id 等零星头,领取接口常返回 9074 限流;
    完整的客户端伪装头 + 稳定伪设备身份是稳定领取的关键。
    x-request-id / x-tt-trace-id 每次请求刷新。
    """
    dev = trae_device_identity(user_id or "")
    return {
        "authorization": f"Cloud-IDE-JWT {token}",
        "accept": "*/*",
        "accept-encoding": "identity",
        "accept-language": "zh-CN",
        "content-type": "application/json",
        "user-agent": "VSCode 1.107.1 (TRAE SOLO CN)",
        "x-market-client-id": "VSCode 1.107.1",
        "x-market-user-id": dev["market_user_id"],
        "x-user-region": "CN",
        "x-device-id": dev["device_id"],
        "x-lgw-req-sdk-type": "3",
        "package-type": "stable_cn",
        "x-lscbd-aid": "787976",
        "x-lscbd-platform": "windows",
        "app-version": "0.1.45",
        "x-tt-trace-id": "00-" + uuid.uuid4().hex[:16] + "-01",
        "vscode-sessionid": dev["session_id"],
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "none",
        "x-request-id": str(uuid.uuid4()),
    }



def lines(name):
    return [line.strip() for line in os.environ.get(name, "").splitlines() if line.strip()]


def read_accounts(args):
    accounts = []
    for line in lines("AI_CHECKIN_ACCOUNTS"):
        try:
            account = json.loads(line)
        except ValueError:
            account = {"_invalid": True}
        accounts.append(account if isinstance(account, dict) else {"_invalid": True})
    if not accounts:
        for service, token_var, uid_var in (
            ("workbuddy", "WORKBUDDY_ACCESS_TOKEN", "WORKBUDDY_UID"),
            ("trae", "TRAE_TOKEN", "TRAE_USER_ID"),
        ):
            tokens, uids = lines(token_var), lines(uid_var)
            for index, token in enumerate(tokens):
                uid = uids[index] if index < len(uids) else ""
                if service == "trae" and not uid:
                    uid = str((jwt_payload(token).get("data") or {}).get("id") or "")
                accounts.append({"service": service, "token": token, "user_id": uid,
                                 "region": os.environ.get("TRAE_REGION", "CN")})
    if not accounts:
        raise TaskError("请配置 AI_CHECKIN_ACCOUNTS 或兼容凭据变量")
    return accounts


def validate(account):
    service = account.get("service")
    if service not in {"workbuddy", "trae", "qoder"}:
        raise TaskError("账号 service 必须为 workbuddy、trae 或 qoder")
    for key in ("token",):
        if not isinstance(account.get(key), str) or not account[key].strip():
            raise TaskError(f"账号缺少 {key}")
    if service == "trae":
        if not isinstance(account.get("user_id"), str) or not account["user_id"]:
            raise TaskError("Trae 账号缺少 user_id")
        if account.get("region", "CN") != "CN":
            raise TaskError("该接口仅支持 Trae CN")
    if service == "qoder":
        if not isinstance(account.get("machine_id"), str) or not account["machine_id"]:
            raise TaskError("Qoder 账号缺少 machine_id")
        device = account.get("device")
        if not isinstance(device, dict) or any(
            not isinstance(device.get(key), str) or not device[key]
            for key in ("machineToken", "machineCode", "machineType")
        ):
            raise TaskError("Qoder 缺少本人客户端的完整 Cosy 设备凭据")
    expiry(account)


class RefreshState:
    """显式启用的私有凭据状态，原子写入并禁止并发轮换。"""
    def __init__(self):
        value = os.environ.get("CHECKIN_REFRESH_STATE", "").strip()
        self.path = Path(value).expanduser() if value else None
        self.state = {}
        self.lock = None

    def __enter__(self):
        if not self.path:
            return self
        self.lock = str(self.path) + ".lock"
        try:
            descriptor = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except OSError:
            self.lock = None
            raise TaskError("续期状态文件锁不可用，请检查路径或其他运行实例") from None
        try:
            if self.path.exists():
                if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
                    raise TaskError("续期状态文件必须为普通私有文件，权限应为 600")
                self.state = json.loads(self.path.read_text())
                if not isinstance(self.state, dict):
                    raise TaskError("续期状态文件格式错误")
        except Exception:
            self.__exit__(None, None, None)
            raise TaskError("无法安全读取续期状态文件") from None
        return self

    def __exit__(self, *args):
        if self.lock:
            os.unlink(self.lock)
            self.lock = None

    def key(self, account):
        original = account.get("refresh_token") or account["token"]
        return hashlib.sha256((account["service"] + ":" + original).encode()).hexdigest()

    def save(self, key, account):
        self.state[key] = {name: account[name] for name in
                           ("token", "refresh_token", "expires_at") if name in account}
        descriptor, temporary = tempfile.mkstemp(prefix=".checkin-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(self.state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def qoder_headers(account):
    headers = {"Authorization": "Bearer " + account["token"], "Accept": "application/json",
               "User-Agent": "Qoder/claim", "Cosy-ClientType": "10",
               "Cosy-MachineOS": "x86_64_windows", "Cosy-MachineHostname": "pc",
               "Cosy-MachineId": account["machine_id"]}
    for key, value in account["device"].items():
        if key in ("machineToken", "machineCode", "machineType"):
            headers["Cosy-" + key[0].upper() + key[1:]] = value
    return headers


def refresh(client, account, state, force=False):
    service = account["service"]
    if service == "workbuddy":
        return False
    exp = expiry(account)
    remaining = exp - time.time() if exp else None
    threshold = 86400 if service == "trae" else 3 * 86400
    if not force and remaining is not None and remaining > threshold:
        return False
    if not state.path or not account.get("refresh_token"):
        return False
    key = account.get("_state_key") or state.key(account)
    if service == "trae":
        body = client.request(TRAE_EXCHANGE_URL, {}, {
            "ClientID": TRAE_CLIENT_ID, "RefreshToken": account["refresh_token"],
            "ClientSecret": "-", "UserID": ""})
        result = body.get("Result") or {}
        data = body.get("data") or {}
        token = result.get("Token") or data.get("access_token") or data.get("token")
        rt = result.get("RefreshToken") or data.get("refresh_token")
    else:
        headers = qoder_headers(account)
        headers.pop("Authorization")
        body = client.request(QODER_BASE + "/api/v1/deviceToken/refresh", headers,
                              {"refresh_token": account["refresh_token"]})
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        token = (data.get("device_token") or data.get("token") or data.get("accessToken")
                 or data.get("access_token"))
        rt = data.get("refresh_token") or data.get("refreshToken")
    if not isinstance(token, str) or not token:
        raise TaskError("续期响应缺少有效令牌")
    account["token"] = token
    account["refresh_token"] = rt or account["refresh_token"]
    account.pop("expires_at", None)
    for field in ("expires_at", "expiresAt"):
        if isinstance(data.get(field), str):
            account["expires_at"] = data[field]
    state.save(key, account)
    log("令牌续期成功，已安全保存轮换状态")
    return True


def workbuddy(client, account, stage):
    domain = os.environ.get("WORKBUDDY_DOMAIN", "www.codebuddy.cn")
    if domain not in {"www.codebuddy.cn", "www.codebuddy.com"}:
        raise TaskError("WORKBUDDY_DOMAIN 必须为官方 CodeBuddy 域名")
    base = "https://" + domain + "/v2/billing/meter/"
    headers = {"Authorization": "Bearer " + account["token"], "Accept": "application/json"}
    body = stage("查询签到状态", lambda: client.request(base + "checkin-status", headers, {}, client.attempts))
    if not isinstance(body.get("data"), dict) or body.get("code") not in (0, "0"):
        raise TaskError("WorkBuddy 状态业务校验失败")
    if body["data"].get("today_checked_in") is True:
        return "already-complete"
    body = stage("领取签到积分", lambda: client.request(base + "daily-checkin", headers, {}, client.attempts))
    if body.get("code") in (0, "0"):
        log("签到成功，积分领取已确认")
        return "success"
    if body.get("code") in (10001, "10001") or "已签到" in str(body.get("msg", "")):
        return "already-complete"
    raise TaskError("WorkBuddy 领取业务校验失败")


def trae_credits(client, token):
    try:
        body = client.request(TRAE_CREDITS_URL, {"authorization": "Cloud-IDE-JWT " + token},
                              {"require_usage": True, "req_source": 2})
        packs = body.get("user_entitlement_pack_list")
        if not isinstance(packs, list):
            raise TaskError("积分响应字段无效")
        total, earliest = 0.0, None
        for pack in packs:
            limit = ((pack.get("entitlement_base_info") or {}).get("quota") or {}).get("credits_limit")
            if limit is not None:
                used = (pack.get("usage") or {}).get("credits_amount") or 0
                total += max(0, float(limit) - float(used))
            exp = pack.get("expire_time")
            if isinstance(exp, (int, float)) and exp > time.time():
                earliest = min(earliest, exp) if earliest else exp
        text = time.strftime("%Y-%m-%d", time.localtime(earliest)) if earliest else "未知"
        log(f"当前剩余积分 {total:g}，最早过期日期 {text}")
    except (TaskError, ValueError, TypeError, AttributeError):
        log("⚠️ 积分查询不可用，签到结果保持")


def trae(client, account, stage):
    headers = build_trae_headers(account["token"], account["user_id"])
    body = stage("查询签到状态", lambda: client.request(TRAE_STATUS_URL, headers, {}, 3))
    if body.get("checked_in") is True:
        result = "already-complete"
    elif body.get("enable") is False:
        log("官方状态确认活动未开启")
        return "skipped"
    else:
        body = stage("领取签到积分", lambda: client.request(TRAE_CLAIM_URL, headers, {}, client.trae_attempts))
        if api_ok(body):
            result = "success"
        elif "已签到" in str(body.get("message") or body.get("msg") or ""):
            result = "already-complete"
        else:
            raise TaskError("Trae 领取业务校验失败")
    stage("查询剩余积分与过期日期", lambda: trae_credits(client, account["token"]))
    return result


def qoder(client, account, stage, state):
    headers = qoder_headers(account)
    url = QODER_BASE + "/sash/api/v1/me/campaigns"
    try:
        body = stage("查询积分活动", lambda: client.request(url, headers, attempts=3))
    except TaskError as error:
        if "HTTP 401" not in str(error) or not refresh(client, account, state, force=True):
            raise
        headers = qoder_headers(account)
        body = stage("重新查询积分活动", lambda: client.request(url, headers))
    campaigns = body.get("campaigns")
    if not isinstance(campaigns, list):
        raise TaskError("Qoder 活动响应字段无效")
    benefits = [item for item in campaigns if isinstance(item, dict)
                and item.get("actionType") == "CLAIM_BENEFIT"
                and isinstance(item.get("benefit"), dict) and item["benefit"].get("kind") == "CREDITS"]
    claimable = [item for item in benefits if item.get("claimStatus") == "CLAIMABLE"]
    if not claimable:
        if any(item.get("claimStatus") == "CLAIMED" for item in benefits):
            return "already-complete"
        raise TaskError("Qoder 未下发可领取或已领取的积分签到活动")
    failed = 0
    for index, item in enumerate(claimable, 1):
        try:
            cid = item.get("campaignId")
            if not isinstance(cid, (str, int)) or not str(cid):
                raise TaskError("活动缺少编号")
            body = stage(f"领取积分活动 {index}", lambda: client.request(
                url + "/" + urllib.parse.quote(str(cid), safe="") + "/claim", headers, {}))
            data = body.get("data") if isinstance(body.get("data"), dict) else body
            if data.get("status") != "CLAIMED" and data.get("replayed") is not True:
                raise TaskError("Qoder 活动领取业务校验失败")
        except TaskError as error:
            failed += 1
            log(str(error))
    if failed:
        raise TaskError(f"积分活动部分失败，成功 {len(claimable)-failed}，失败 {failed}")
    return "success"


def notify_summary(body, dry):
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in {"0", "false", "no", "off"}:
        return "已关闭"
    selected = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    names = {CATALOG_ID, Path(__file__).name, "checkin.py", "candidate.py"}
    for root in ("/ql/data/scripts/", "/ql/scripts/"):
        path = str(Path(__file__).absolute())
        if path.startswith(root):
            names.add(path[len(root):])
    matches = any(fnmatch.fnmatch(name, pattern)
                  for pattern in re.split(r"[,;\s]+", selected) if pattern for name in names)
    if switch not in {"1", "true", "yes", "on"} and not matches:
        return "未列入通知选择器"
    if dry:
        log("离线预演通知摘要 " + body)
        return "离线预演已生成通知摘要"
    # 通知组件在独立进程中运行，限制耗时并隔离其输出及退出行为。
    worker = """
import importlib, importlib.util, os, sys
from pathlib import Path
try:
    module = importlib.import_module('notify')
except ImportError:
    module = None
if module is not None and callable(getattr(module, 'send', None)):
    module.send(sys.argv[1], sys.argv[2])
    sys.exit(0)
for directory in filter(None, [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']):
    file = Path(directory) / 'notify.py'
    if file.is_file():
        sys.path.insert(0, str(file.parent))
        spec = importlib.util.spec_from_file_location('qinglong_notify', file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.send(sys.argv[1], sys.argv[2])
        sys.exit(0)
sys.exit(3)
"""
    try:
        result = subprocess.run([sys.executable, "-c", worker, TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode == 0:
            return "已调用 notify.py"
        if result.returncode != 3:
            return "通知失败，保留业务退出码"
        directories = [os.environ.get("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
        for directory in filter(None, directories):
            file = Path(directory) / "sendNotify.js"
            if file.is_file():
                script = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(()=>process.exit(1))"
                result = subprocess.run(["node", "-e", script, str(file.absolute()), TITLE, body],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                return "已调用 sendNotify.js" if result.returncode == 0 else "通知失败，保留业务退出码"
    except Exception:
        return "通知失败，保留业务退出码"
    return "通知组件不可用，保留业务退出码"



def main():
    started = time.monotonic()
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    dry = os.environ.get("AI_CHECKIN_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}
    log("=" * 55)
    log(TITLE)
    log(f"开始时间 {start_time}，运行模式 {'离线预演' if dry else '正式执行'}")
    records = []
    count = 0
    configuration_error = False
    try:
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("--no-trae", action="store_true", help="跳过 Trae CN")
        parser.add_argument("--no-qoder", action="store_true", help="跳过 Qoder")
        args, unknown = parser.parse_known_args()
        if unknown:
            raise TaskError("存在不支持的选项；凭据导出和本机账号库修改命令已移除")
        accounts = read_accounts(args)
        count = len(accounts)
        log(f"账号数量 {count}")
        client = Client(dry)
        state_context = contextlib.nullcontext(None) if dry else RefreshState()
        with state_context as state:
            for index, original in enumerate(accounts, 1):
                account_started = time.monotonic()
                stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
                service = original.get("service", "未知")
                label = service if service in {"workbuddy", "trae", "qoder"} else "未知"
                log(f"账号 {index}/{count}，服务 {label}")

                def stage(name, action):
                    stats["total"] += 1
                    step_started = time.monotonic()
                    log(f"阶段 {stats['total']} {name} 开始")
                    try:
                        value = action()
                    except Exception:
                        stats["failure"] += 1
                        log(f"❌ 阶段 {stats['total']} {name} 失败，耗时 {time.monotonic()-step_started:.2f} 秒")
                        raise
                    stats["success"] += 1
                    log(f"✅ 阶段 {stats['total']} {name} 完成，耗时 {time.monotonic()-step_started:.2f} 秒")
                    return value

                try:
                    stage("检查账号参数", lambda: validate(original))
                    account = dict(original)
                    skip = (args.no_trae and service == "trae") or (args.no_qoder and service == "qoder")
                    if account.get("excluded") is True or skip:
                        result = "skipped"
                    elif dry:
                        stage("离线检查签到请求计划", lambda: None)
                        log("DRY_RUN_OK 参数检查通过，HTTP、凭据轮换和通知投递均为离线预演")
                        result = "dry-run"
                    else:
                        key = state.key(account)
                        account["_state_key"] = key
                        account.update(state.state.get(key, {}))
                        stage("检查令牌有效期与可选续期", lambda: refresh(client, account, state))
                        exp = expiry(account)
                        if exp:
                            log(f"令牌剩余有效期 {(exp-time.time())/86400:.1f} 天")
                            if exp <= time.time():
                                raise TaskError("令牌已过期，请更新本人客户端凭据或启用安全续期")
                        if service == "workbuddy":
                            result = workbuddy(client, account, stage)
                        elif service == "trae":
                            result = trae(client, account, stage)
                        else:
                            result = qoder(client, account, stage, state)
                    if result == "already-complete":
                        stats["alreadyComplete"] += 1
                    if result == "skipped":
                        stats["skipped"] += 1
                except TaskError as error:
                    log("❌ " + str(error))
                    result = "failure"
                    if not stats["failure"]:
                        stats["failure"] += 1
                except Exception:
                    log("❌ 账号执行异常，已隐藏异常内容以保护凭据")
                    result = "failure"
                    if not stats["failure"]:
                        stats["failure"] += 1
                elapsed = round(time.monotonic() - account_started, 2)
                records.append({"account": index, "service": label, "status": result,
                                "steps": stats, "elapsedSeconds": elapsed})
                log(f"账号 {index} 结果 {result}，总阶段 {stats['total']}，成功 {stats['success']}，"
                    f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failure']}，耗时 {elapsed} 秒")
    except TaskError as error:
        configuration_error = True
        log("❌ 配置错误 " + str(error))
    except Exception:
        configuration_error = True
        log("❌ 初始化失败，已隐藏异常内容以保护凭据")
    failed = sum(record["status"] == "failure" for record in records)
    if configuration_error:
        failed += max(0, count - len(records))
    successful = sum(record["status"] in {"success", "already-complete", "dry-run"} for record in records)
    skipped = sum(record["status"] == "skipped" for record in records)
    code = int(configuration_error or failed > 0)
    status = "configuration-error" if configuration_error else (
        "partial-failure" if failed and successful else "failure" if failed else "dry-run" if dry else "success")
    text = f"账号总数 {count}，成功 {successful}，失败 {failed}，跳过 {skipped}，最终状态 {status}"
    notification = notify_summary(text, dry)
    log("-" * 55)
    log(text)
    totals = {key: sum(record["steps"][key] for record in records)
              for key in ("total", "success", "alreadyComplete", "skipped", "failure")}
    log("子任务统计 " + json.dumps(totals, ensure_ascii=False))
    finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
    log(f"总耗时 {time.monotonic()-started:.2f} 秒，完成时间 {finish_time}，通知状态 {notification}")
    log(f"最终状态 {status}，退出码 {code}")
    print("TASK_SUMMARY=" + json.dumps({"applicationKey": "ai", "status": status,
          "accounts": count, "success": successful, "failure": failed, "skipped": skipped,
          "configurationError": configuration_error, "results": records, "steps": totals,
          "startTime": start_time, "finishTime": finish_time, "notification": notification,
          "elapsedSeconds": round(time.monotonic()-started, 2), "exitCode": code},
          ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
