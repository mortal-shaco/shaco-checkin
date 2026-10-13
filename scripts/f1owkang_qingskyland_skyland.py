#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 森空岛自动签到
# cron: 15 8 * * *
# filename: qingskyland_attendance.py
# 修复 release-path-collision：发布器必须使用下述路径，不能按上游文件名 skyland.py 推导。
# publish-path: scripts/qingskyland_attendance.py
# 交付文件 output/candidate.py 导入后必须以该产品专属文件名发布。
# 发布路径：scripts/qingskyland_attendance.py；禁止使用其他产品占用的 scripts/skyland.py。
# SPDX-License-Identifier: MIT
# 来源：f1owkang/QingSkyland，skyland.py，commit 563c86c9d5965b5fc622e1cb33963346b661f26c
# 原文件说明：森空岛自动签到 - 青龙 / Hermes 双模式
# dId 计算来源：原项目 src/SecuritySm.py；保留原数美协议与配置。
# 原文件未附版权声明；本维护版本沿用任务指定的 MIT 许可。
# MIT License
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
"""森空岛明日方舟、终末地每日签到。
SKYLAND_TOKENS：每行一个鹰角登录 token，或官方返回的 {"data":{"content":"..."}} JSON。
获取：本人登录 https://www.skland.com/ 后，在同一浏览器打开
https://web-api.skland.com/account/info/hg ，取 data.content；不要公开登录响应。
SKYLAND_TOKEN_FILE：可选自有凭据文件，每行一个账号，允许 # 注释；与环境输入合并去重。
不再将逗号当账号分隔符，以免破坏完整 JSON。无账号、无角色或任一失败均非零退出。
SKYLAND_DRY_RUN=1：仅验证配置及本地签名，不联网、不签到、不调用通知模块。
USE_PROXY=on：显式允许 requests 使用系统代理；默认忽略系统代理。
SKYLAND_MODE=auto/qinglong/hermes；SKYLAND_SILENT_OK=on 仅抑制 Hermes 成功投递文本。
QINGLONG_NOTIFY=0 可关闭通知；QINGLONG_NOTIFY_DIR 指向面板 notify.py 所在目录。
EXIT_WHEN_FAIL 保留为兼容输入，但不再允许失败返回零。上游未指定 cron，本版每日 08:15。
依赖：requests>=2.31、cryptography>=43；通过公共包仓库安装，无自动安装行为。
"""
import base64
import gzip
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime
from urllib import parse

# 导入器须使用产品专属路径；交付文件名不代表订阅发布文件名。
PUBLISH_FILENAME = "qingskyland_attendance.py"
PUBLISH_PATH = "scripts/" + PUBLISH_FILENAME

APP_CODE = "4ca99fa6b56cc2ba"
GRANT_CODE_URL = "https://as.hypergryph.com/user/oauth2/v2/grant"
CRED_CODE_URL = "https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code"
BINDING_URL = "https://zonai.skland.com/api/v1/game/player/binding"
SIGN_URL_MAPPING = {
    "arknights": "https://zonai.skland.com/api/v1/game/attendance",
    "endfield": "https://zonai.skland.com/web/v1/game/endfield/attendance",
}
UA = "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1"
DISABLED = {"0", "false", "no", "off"}
SECRETS = []
LOG_STREAM = sys.stdout

class TaskError(Exception):
    pass

def clean(value):
    # 只用于已知身份/奖励等非凭据字段；禁止传入完整响应或异常正文。
    value = " ".join(str(value).split())
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[凭据已隐藏]")
    return value

def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {clean(message)}", file=LOG_STREAM, flush=True)

def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in DISABLED | {""}

class Client:
    def __init__(self):
        try:
            import requests
        except ImportError:
            raise TaskError("缺少公共依赖 requests，请安装契约列出的依赖") from None
        self.session = requests.Session()
        self.session.trust_env = os.getenv("USE_PROXY", "off").lower() == "on"

    def request(self, method, url, body=None, headers=None):
        # 不重试写操作；签名字符串与实际发送的 JSON 字节完全一致。
        if enabled("SKYLAND_DRY_RUN"):
            raise TaskError("预演禁止网络请求")
        payload = json.dumps(body) if body is not None else None
        request_headers = dict(headers or {})
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        try:
            with self.session.request(method, url, data=payload, headers=request_headers,
                                      timeout=(8, 20), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise TaskError(f"HTTP 状态异常（{response.status_code}）")
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > 1048576:
                        raise TaskError("接口响应超出大小限制")
                    chunks.append(chunk)
                data = json.loads(b"".join(chunks))
                if not isinstance(data, dict):
                    raise TaskError("接口响应结构异常")
                return data
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络超时、连接失败或接口 JSON 无效") from None

    def close(self):
        self.session.close()

# 查询dId请求头
devices_info_url = "https://fp-it.portal101.cn/deviceprofile/v4"

# 数美配置
SM_CONFIG = {
    "organization": "UWXspnCCJN4sfYlNfqps",
    "appId": "default",
    "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCmxMNr7n8ZeT0tE1R9j/mPixoinPkeM+k4VGIn/s0k7N5rJAfnZ0eMER+QhwFvshzo0LNmeUkpR8uIlU/GEVr8mN28sKmwd2gpygqj0ePnBmOW4v0ZVwbSYK+izkhVFk2V/doLoMbWy6b+UnA8mkjvg0iYWRByfRsK2gdl7llqCwIDAQAB",
    "protocol": "https",
    "apiHost": "fp-it.portal101.cn",
}



DES_RULE = {
    "appId": {"cipher": "DES", "is_encrypt": 1, "key": "uy7mzc4h", "obfuscated_name": "xx"},
    "box": {"is_encrypt": 0, "obfuscated_name": "jf"},
    "canvas": {"cipher": "DES", "is_encrypt": 1, "key": "snrn887t", "obfuscated_name": "yk"},
    "clientSize": {"cipher": "DES", "is_encrypt": 1, "key": "cpmjjgsu", "obfuscated_name": "zx"},
    "organization": {"cipher": "DES", "is_encrypt": 1, "key": "78moqjfc", "obfuscated_name": "dp"},
    "os": {"cipher": "DES", "is_encrypt": 1, "key": "je6vk6t4", "obfuscated_name": "pj"},
    "platform": {"cipher": "DES", "is_encrypt": 1, "key": "pakxhcd2", "obfuscated_name": "gm"},
    "plugins": {"cipher": "DES", "is_encrypt": 1, "key": "v51m3pzl", "obfuscated_name": "kq"},
    "pmf": {"cipher": "DES", "is_encrypt": 1, "key": "2mdeslu3", "obfuscated_name": "vw"},
    "protocol": {"is_encrypt": 0, "obfuscated_name": "protocol"},
    "referer": {"cipher": "DES", "is_encrypt": 1, "key": "y7bmrjlc", "obfuscated_name": "ab"},
    "res": {"cipher": "DES", "is_encrypt": 1, "key": "whxqm2a7", "obfuscated_name": "hf"},
    "rtype": {"cipher": "DES", "is_encrypt": 1, "key": "x8o2h2bl", "obfuscated_name": "lo"},
    "sdkver": {"cipher": "DES", "is_encrypt": 1, "key": "9q3dcxp2", "obfuscated_name": "sc"},
    "status": {"cipher": "DES", "is_encrypt": 1, "key": "2jbrxxw4", "obfuscated_name": "an"},
    "subVersion": {"cipher": "DES", "is_encrypt": 1, "key": "eo3i2puh", "obfuscated_name": "ns"},
    "svm": {"cipher": "DES", "is_encrypt": 1, "key": "fzj3kaeh", "obfuscated_name": "qr"},
    "time": {"cipher": "DES", "is_encrypt": 1, "key": "q2t3odsk", "obfuscated_name": "nb"},
    "timezone": {"cipher": "DES", "is_encrypt": 1, "key": "1uv05lj5", "obfuscated_name": "as"},
    "tn": {"cipher": "DES", "is_encrypt": 1, "key": "x9nzj1bp", "obfuscated_name": "py"},
    "trees": {"cipher": "DES", "is_encrypt": 1, "key": "acfs0xo4", "obfuscated_name": "pi"},
    "ua": {"cipher": "DES", "is_encrypt": 1, "key": "k92crp1t", "obfuscated_name": "bj"},
    "url": {"cipher": "DES", "is_encrypt": 1, "key": "y95hjkoo", "obfuscated_name": "cf"},
    "version": {"is_encrypt": 0, "obfuscated_name": "version"},
    "vpw": {"cipher": "DES", "is_encrypt": 1, "key": "r9924ab5", "obfuscated_name": "ca"},
}

BROWSER_ENV = {
    "plugins": "MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,MicrosoftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1",
    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "canvas": "259ffe69",
    "timezone": -480,
    "platform": "Win32",
    "url": "https://www.skland.com/",
    "referer": "",
    "res": "1920_1080_24_1.25",
    "clientSize": "0_0_1080_1920_1920_1080_1920_1080",
    "status": "0011",
}


def _DES(o: dict):
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    from cryptography.hazmat.primitives.ciphers import Cipher, modes
    result = {}
    for i in o.keys():
        if i in DES_RULE.keys():
            rule = DES_RULE[i]
            res = o[i]
            if rule["is_encrypt"] == 1:
                c = Cipher(TripleDES(rule["key"].encode("utf-8")), modes.ECB())
                data = str(res).encode("utf-8")
                data += b"\x00" * (8 - len(data) % 8)
                encryptor = c.encryptor()
                res = base64.b64encode(encryptor.update(data) + encryptor.finalize()).decode("utf-8")
            result[rule["obfuscated_name"]] = res
        else:
            result[i] = o[i]
    return result


def _AES(v: bytes, k: bytes):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    iv = "0102030405060708"
    key = algorithms.AES(k)
    c = Cipher(key, modes.CBC(iv.encode("utf-8")))
    v += b"\x00"
    while len(v) % 16 != 0:
        v += b"\x00"
    encryptor = c.encryptor()
    return (encryptor.update(v) + encryptor.finalize()).hex()


def GZIP(o: dict):
    json_str = json.dumps(o, ensure_ascii=False)
    stream = gzip.compress(json_str.encode("utf-8"), 2, mtime=0)
    return base64.b64encode(stream)


def get_tn(o: dict):
    sorted_keys = sorted(o.keys())
    result_list = []
    for i in sorted_keys:
        v = o[i]
        if isinstance(v, (int, float)):
            v = str(v * 10000)
        elif isinstance(v, dict):
            v = get_tn(v)
        result_list.append(v)
    return "".join(result_list)


def get_smid():
    t = time.localtime()
    _time = "{}{:0>2d}{:0>2d}{:0>2d}{:0>2d}{:0>2d}".format(
        t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec
    )
    uid = str(uuid.uuid4())
    v = _time + hashlib.md5(uid.encode("utf-8")).hexdigest() + "00"
    smsk_web = hashlib.md5(("smsk_web_" + v).encode("utf-8")).hexdigest()[0:14]
    return v + smsk_web + "0"


def get_d_id(client):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    PK = serialization.load_der_public_key(base64.b64decode(SM_CONFIG["publicKey"]))
    uid = str(uuid.uuid4()).encode("utf-8")
    priId = hashlib.md5(uid).hexdigest()[0:16]
    ep = PK.encrypt(uid, padding.PKCS1v15())
    ep = base64.b64encode(ep).decode("utf-8")

    browser = BROWSER_ENV.copy()
    current_time = int(time.time() * 1000)
    browser.update({"vpw": str(uuid.uuid4()), "svm": current_time, "trees": str(uuid.uuid4()), "pmf": current_time})

    des_target = {
        **browser,
        "protocol": 102,
        "organization": SM_CONFIG["organization"],
        "appId": SM_CONFIG["appId"],
        "os": "web",
        "version": "3.0.0",
        "sdkver": "3.0.0",
        "box": "",
        "rtype": "all",
        "smid": get_smid(),
        "subVersion": "1.0.0",
        "time": 0,
    }
    des_target["tn"] = hashlib.md5(get_tn(des_target).encode()).hexdigest()

    des_result = _AES(GZIP(_DES(des_target)), priId.encode("utf-8"))

    resp = client.request(
        "POST", devices_info_url,
        body={
            "appId": "default",
            "compress": 2,
            "data": des_result,
            "encode": 5,
            "ep": ep,
            "organization": SM_CONFIG["organization"],
            "os": "web",
        },
    )

    if resp.get("code") != 1100:
        raise TaskError("设备认证业务失败")
    device = resp.get("detail", {}).get("deviceId")
    if not isinstance(device, str) or not device:
        raise TaskError("设备认证缺少必要字段")
    SECRETS.extend((device, "B" + device))
    return "B" + device



def require_text(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise TaskError("接口缺少必要认证字段")
    SECRETS.append(value)
    return value


def signature(path, body_or_query, token, did, timestamp=None):
    stamp = str(int(time.time())) if timestamp is None else str(timestamp)
    signed = {"platform": "3", "timestamp": stamp, "dId": did, "vName": "1.0.0"}
    material = path + body_or_query + stamp + json.dumps(signed, separators=(",", ":"))
    digest = hmac.new(token.encode(), material.encode(), hashlib.sha256).hexdigest()
    return hashlib.md5(digest.encode()).hexdigest(), signed


def sign_headers(url, method, body, cred, token, did):
    parts = parse.urlparse(url)
    payload = parts.query if method == "GET" else (json.dumps(body) if body is not None else "")
    sign, signed = signature(parts.path, payload, token, did)
    return {"cred": cred, "User-Agent": UA, "Accept-Encoding": "gzip", "Connection": "close",
            "X-Requested-With": "com.hypergryph.skland", "sign": sign, **signed}


def read_tokens():
    lines = os.getenv("SKYLAND_TOKENS", "").splitlines()
    filename = os.getenv("SKYLAND_TOKEN_FILE", "").strip()
    if filename:
        try:
            lines.extend(Path(filename).expanduser().read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            raise TaskError("凭据文件无法读取，请检查 SKYLAND_TOKEN_FILE") from None
    result = []
    seen = set()
    # 先登记所有账号原始输入，防止后续日志意外包含尚未处理的凭据。
    SECRETS.extend(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        SECRETS.append(line)
        try:
            token = parse_token(line)
            if token not in seen:
                seen.add(token)
                result.append((token, None))
        except TaskError as error:
            # 单行凭据错误只影响本账号，其他有效账号仍独立执行。
            result.append((None, str(error)))
    if not result:
        raise TaskError("未配置账号，请设置 SKYLAND_TOKENS 或兼容凭据文件")
    return result


def parse_token(line):
    if line.startswith("{"):
        try:
            token = json.loads(line)["data"]["content"]
        except (ValueError, KeyError, TypeError):
            raise TaskError("账号 JSON 需包含 data.content；每行仅一个账号") from None
        if not isinstance(token, str) or not token.strip():
            raise TaskError("账号 JSON 的 data.content 必须是非空字符串")
        token = token.strip()
    else:
        token = line
    SECRETS.append(token)
    if any(ch.isspace() for ch in token) or "," in token:
        raise TaskError("凭据格式无效；请每行放一个完整 token，不使用逗号分隔账号")
    return token


def notify_files():
    roots = [Path(__file__).resolve().parent]
    configured = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if configured:
        roots.append(Path(configured).expanduser())
    roots += [Path("/ql/data/scripts"), Path("/ql/scripts")]
    files = [root / "notify.py" for root in roots]
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            files.append(Path(spec.origin))
    except (ImportError, ValueError):
        pass
    # 按发现顺序去重，首个通知模块不可用时继续尝试其他面板目录。
    found = []
    for file in files:
        if file.is_file() and file.resolve() not in found:
            found.append(file.resolve())
    return found


def send_summary(body, dry_run, hermes, success):
    title = clean(os.getenv("NOTIFY_TITLE", "森空岛自动签到")) or "森空岛自动签到"
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if hermes and not (success and os.getenv("SKYLAND_SILENT_OK", "off").lower() == "on"):
        print(f"{title}\n{body}", flush=True)
    if dry_run:
        log("⏭️ 通知离线预演：已生成脱敏总结，未调用通知模块")
        return "离线预演"
    files = notify_files()
    if not files:
        log("⚠️ 青龙 notify.py 不可用，保留业务退出码")
        return "通知模块不可用"
    # 隔离通知库的输出及异常，避免第三方通知插件意外输出账号配置。
    code = (
        "import importlib.util,json,sys;"
        "p=sys.argv[1];sys.path.insert(0,str(__import__('pathlib').Path(p).parent));"
        "s=importlib.util.spec_from_file_location('notify',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    for file in files:
        try:
            done = subprocess.run([sys.executable, "-c", code, str(file)],
                                  input=json.dumps({"title": title, "body": body}), text=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                                  check=False)
            if done.returncode != 0:
                raise TaskError("通知模块执行失败")
            log("✅ 青龙通知模块调用完成")
            return "已调用"
        except Exception:
            log("⚠️ 通知模块失败或超时，尝试下一发现位置；保留业务退出码")
    return "通知失败"


class Account:
    def __init__(self, index):
        self.index = index
        self.stage = 0
        self.started = time.monotonic()
        self.stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        self.details = []

    def step(self, name, action):
        self.stage += 1
        self.stats["total"] += 1
        started = time.monotonic()
        log(f"账号 {self.index} 阶段 {self.stage}：{name}")
        try:
            value, detail = action()
            self.stats["success"] += 1
            self.details.append(clean(f"账号 {self.index}：{name}；{detail}"))
            log(f"✅ 账号 {self.index} 阶段 {self.stage}：{detail}；耗时 {time.monotonic()-started:.2f} 秒")
            return value
        except Exception as error:
            self.stats["failed"] += 1
            message = str(error) if isinstance(error, TaskError) else "依赖缺失或接口字段结构异常，请核对契约及账号绑定"
            self.details.append(clean(f"账号 {self.index}：{name}失败；{message}"))
            log(f"❌ 账号 {self.index} 阶段 {self.stage}：{message}；耗时 {time.monotonic()-started:.2f} 秒")
            raise TaskError("账号阶段失败") from None

    def finish(self):
        stats = self.stats
        log(f"账号 {self.index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，"
            f"耗时 {time.monotonic()-self.started:.2f} 秒")
        return {"account": self.index, "status": "failure" if stats["failed"] else "success",
                **stats, "details": self.details}


def authenticate(client, token):
    did = get_d_id(client)
    SECRETS.append(did)
    headers = {"User-Agent": UA, "Accept-Encoding": "gzip", "Connection": "close",
               "dId": did, "X-Requested-With": "com.hypergryph.skland"}
    grant = client.request("POST", GRANT_CODE_URL,
                           {"appCode": APP_CODE, "token": token, "type": 0}, headers)
    if grant.get("status") != 0:
        raise TaskError("鹰角授权业务失败，请检查登录 token 是否有效")
    code = require_text(grant.get("data"), "code")
    response = client.request("POST", CRED_CODE_URL, {"code": code, "kind": 1}, headers)
    if response.get("code") != 0:
        raise TaskError("森空岛凭据换取业务失败")
    data = response.get("data")
    return (require_text(data, "cred"), require_text(data, "token"), did), "设备认证、鹰角授权及森空岛凭据换取成功"


def bindings(client, credentials):
    response = client.request("GET", BINDING_URL,
                              headers=sign_headers(BINDING_URL, "GET", None, *credentials))
    if response.get("code") != 0:
        raise TaskError("绑定角色查询业务失败")
    games = response.get("data", {}).get("list")
    if not isinstance(games, list):
        raise TaskError("绑定角色列表字段无效")
    result = []
    for game in games:
        if not isinstance(game, dict):
            raise TaskError("绑定游戏字段无效")
        app = game.get("appCode")
        if app not in SIGN_URL_MAPPING:
            continue
        players = game.get("bindingList")
        if not isinstance(players, list):
            raise TaskError("绑定账号列表字段无效")
        for player in players:
            if not isinstance(player, dict):
                raise TaskError("绑定角色字段无效")
            result.append({**player, "appCode": app})
    if not result:
        raise TaskError("未找到明日方舟或终末地绑定角色，未验证任何签到")
    return result, f"绑定角色查询成功，共 {len(result)} 个绑定账号"


def required_id(data, key):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (str, int)) or str(value) == "":
        raise TaskError("角色缺少签到必要标识")
    return value


def attendance(client, credentials, player, role=None):
    app = player["appCode"]
    url = SIGN_URL_MAPPING[app]
    if app == "arknights":
        body = {"gameId": required_id(player, "gameId"), "uid": required_id(player, "uid")}
        headers = sign_headers(url, "POST", body, *credentials)
    else:
        body = None
        headers = sign_headers(url, "POST", None, *credentials)
        headers.update({"Content-Type": "application/json",
                        "sk-game-role": f"3_{required_id(role, 'roleId')}_{required_id(role, 'serverId')}",
                        "referer": "https://game.skland.com/", "origin": "https://game.skland.com/"})
    response = client.request("POST", url, body, headers)
    # 上游仅提供 code=0 成功依据；不猜测非零业务码为“今日已签到”。
    if response.get("code") != 0:
        code = response.get("code")
        diagnostic = str(code) if type(code) is int else "缺失或字段无效"
        raise TaskError(f"签到业务失败（业务码：{diagnostic}）；未将其视为已完成")
    data = response.get("data")
    if not isinstance(data, dict):
        raise TaskError("签到成功响应缺少奖励数据")
    rewards = []
    if app == "arknights":
        awards = data.get("awards")
        if not isinstance(awards, list):
            raise TaskError("明日方舟奖励字段结构异常")
        for award in awards:
            rewards.append(f"{award['resource']['name']}×{award.get('count') or 1}")
    else:
        award_ids, resources = data.get("awardIds"), data.get("resourceInfoMap")
        if not isinstance(award_ids, list) or not isinstance(resources, dict):
            raise TaskError("终末地奖励字段结构异常")
        for award in award_ids:
            resource = resources[str(award["id"])]
            rewards.append(f"{resource['name']}×{resource['count']}")
    return True, "签到成功，奖励：" + ("，".join(clean(reward) for reward in rewards) or "无奖励条目")


def role_label(player, role=None):
    game = "明日方舟" if player["appCode"] == "arknights" else "终末地"
    subject = role if role is not None else player
    nickname = subject.get("nickname") or subject.get("nickName")
    public_uid = subject.get("uid")
    identity = str(nickname) if nickname else (f"公开 UID {public_uid}" if public_uid is not None else "绑定角色")
    # 返回的公开身份直接展示；从不展示 roleId/serverId/dId 等设备或会话字段。
    return f"{game} {clean(identity)}（{clean(player.get('channelName') or '未知渠道')}）"


def run_account(index, token, dry_run, parse_error=None):
    account = Account(index)
    client = None
    try:
        if parse_error:
            def invalid_credential():
                raise TaskError(parse_error)
            account.step("凭据格式检查", invalid_credential)
        if dry_run:
            account.step("离线凭据解析", lambda: (True, "凭据格式验证通过；未验证真实登录"))
            def dry_signature():
                expected = signature("/api/v1/game/attendance", '{"gameId": 1, "uid": "dry"}',
                                     "offline-key", "offline-device", 1700000000)
                if expected[0] != "620f826eb7541563c11b71058ab0f70d" or expected[1]["timestamp"] != "1700000000":
                    raise TaskError("本地签名契约验证失败")
                # 同时覆盖两种签到请求的路径、载荷和请求头；绝不构造网络客户端。
                credentials = ("offline-cred", "offline-key", "offline-device")
                body = {"gameId": 1, "uid": "dry"}
                for app, request_body in (("arknights", body), ("endfield", None)):
                    url = SIGN_URL_MAPPING[app]
                    headers = sign_headers(url, "POST", request_body, *credentials)
                    payload = json.dumps(request_body) if request_body is not None else ""
                    expected_sign, signed = signature(parse.urlparse(url).path, payload,
                                                      credentials[1], credentials[2], headers["timestamp"])
                    if headers["sign"] != expected_sign or any(headers[k] != v for k, v in signed.items()):
                        raise TaskError("签到请求签名与载荷不一致")
                if parse_token('{"data":{"content":"offline-json-token"}}') != "offline-json-token":
                    raise TaskError("官方 JSON 凭据解析失败")
                return True, "本地签名、双游戏请求及 JSON 凭据契约通过；签到仅预演，未发出请求"
            account.step("离线签到计划", dry_signature)
            log(f"✅ 账号 {index} DRY_RUN_OK（离线预演通过）")
        else:
            def login():
                nonlocal client
                client = Client()
                return authenticate(client, token)
            credentials = account.step("设备认证与登录", login)
            players = account.step("查询绑定角色", lambda: bindings(client, credentials))
            for player in players:
                if player["appCode"] == "arknights":
                    try:
                        account.step(role_label(player) + "签到", lambda p=player: attendance(client, credentials, p))
                    except TaskError:
                        pass
                else:
                    roles = player.get("roles")
                    if not isinstance(roles, list) or not roles:
                        def invalid_roles():
                            raise TaskError("终末地未返回有效角色列表")
                        try:
                            account.step("终末地角色检查", invalid_roles)
                        except TaskError:
                            pass
                        continue
                    for role in roles:
                        try:
                            if not isinstance(role, dict):
                                def invalid_role():
                                    raise TaskError("终末地角色字段结构异常")
                                account.step("终末地角色检查", invalid_role)
                            else:
                                account.step(role_label(player, role) + "签到",
                                             lambda r=role, p=player: attendance(client, credentials, p, r))
                        except TaskError:
                            pass
    except TaskError:
        pass
    finally:
        if client:
            try:
                client.close()
            except Exception:
                log(f"⚠️ 账号 {index}：连接清理失败；保留已记录的业务结果")
    return account.finish()


def main():
    global LOG_STREAM
    started = time.monotonic()
    dry_run = enabled("SKYLAND_DRY_RUN")
    mode = os.getenv("SKYLAND_MODE", "auto").strip().lower()
    hermes = mode == "hermes" or (mode == "auto" and not notify_files())
    LOG_STREAM = sys.stderr if hermes else sys.stdout
    log("========== 森空岛自动签到（青龙 / Hermes 双模式） ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'离线预演' if dry_run else '实际签到'} / {mode}")
    accounts, configuration_error = [], False
    try:
        if mode not in {"auto", "qinglong", "hermes"}:
            raise TaskError("SKYLAND_MODE 仅支持 auto、qinglong、hermes")
        tokens = read_tokens()
        log(f"账号总数：{len(tokens)}")
        for index, (token, parse_error) in enumerate(tokens, 1):
            accounts.append(run_account(index, token, dry_run, parse_error))
    except TaskError as error:
        configuration_error = True
        log("账号总数：0")
        log(f"❌ 阶段 1：配置检查失败；{error}")
    successful = sum(account["status"] == "success" for account in accounts)
    failed = len(accounts) - successful
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and successful else "failure" if failed else
              "dry-run" if dry_run else "success")
    exit_code = 1 if configuration_error or failed else 0
    totals = {key: sum(account[key] for account in accounts)
              for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("--------------------------------------------------")
    body = (f"模式：{'离线预演（未验证业务）' if dry_run else '实际签到'}；状态：{status}\n"
            f"账号总数 {len(accounts)}，成功 {successful}，失败 {failed}，配置错误 {int(configuration_error)}\n"
            f"子任务 {totals['total']}，成功 {totals['success']}，已完成 {totals['alreadyComplete']}，"
            f"跳过 {totals['skipped']}，失败 {totals['failed']}")
    details = [detail for account in accounts for detail in account["details"]]
    if details:
        body += "\n" + "\n".join(details)
    log(body)
    notification = send_summary(body, dry_run, hermes, not exit_code)
    elapsed = round(time.monotonic() - started, 3)
    finished = datetime.now().isoformat(timespec="seconds")
    log(f"完成时间：{finished}；总耗时 {elapsed:.3f} 秒；通知状态：{notification}；最终状态：{status}")
    summary = {"task": "森空岛自动签到", "mode": "dry-run" if dry_run else "live", "status": status,
               "accounts": len(accounts), "success": successful, "failed": failed,
               "configurationErrors": int(configuration_error), "statistics": totals,
               "accountResults": accounts, "notification": notification,
               "elapsedSeconds": elapsed, "finishedAt": finished, "exitCode": exit_code,
               "publishFilename": PUBLISH_FILENAME, "publishPath": PUBLISH_PATH}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
