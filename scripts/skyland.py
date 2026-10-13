#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 森空岛签到
# cron: 0 8 * * *
# new Env("森空岛签到")
# 上游：CN-Grace/QinglongScripts / skyland.py（MIT）
# 原始来源提交：a40a2b080e0160bd8e0b0b807081115537b87153
# 保留上游数美设备协议、请求签名和两款游戏签到能力。
# SKYLAND_TOKEN：鹰角网络账号 Token，每个非空行一个账号；不使用逗号分隔。
# 登录官方账号页面 https://user.hypergryph.com/ 后，在自己的浏览器中
# 打开 https://web-api.hypergryph.com/account/info/hg ，将响应中的 content
# 作为 Token；若登录流程变化，请从本人已登录客户端的授权请求获取 token。
# 不要把 Token、Cookie 或响应发给他人。
# SKYLAND_DRY_RUN=1：断网预演，不登录、不签到、不调用远程通知。
# QINGLONG_NOTIFY=0：关闭通知；默认开启，可设置 QINGLONG_NOTIFY_DIR。
#
# MIT License
# Original attribution: CN-Grace/QinglongScripts contributors.
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

import base64
import gzip
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib import parse

APP_CODE = "4ca99fa6b56cc2ba"
_TIME_OFFSET = 0.0
_DID_CACHE = None
DRY_RUN = os.getenv("SKYLAND_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}

class TaskError(Exception):
    """只携带本地生成的脱敏错误说明。"""


def log_info(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

log_success = log_info


def real_time():
    return time.time() + _TIME_OFFSET


def real_localtime():
    return time.localtime(real_time())


class HTTP:
    """本脚本实现的 HTTP 层：禁止预演联网、不跟随重定向、限制响应。"""
    @staticmethod
    def request(method, url, **kwargs):
        if DRY_RUN:
            raise TaskError("预演禁止网络请求")
        import requests as client
        try:
            response = client.request(method, url, timeout=(8, 20),
                                      allow_redirects=False, stream=True, **kwargs)
            with response:
                if not 200 <= response.status_code < 300:
                    raise TaskError(f"HTTP 状态异常（{response.status_code}）")
                if method == "HEAD":
                    return dict(response.headers)
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > 1048576:
                        raise TaskError("响应超过大小限制")
                    chunks.append(chunk)
                value = json.loads(b"".join(chunks))
                if not isinstance(value, dict):
                    raise TaskError("接口响应格式异常")
                return value
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络、依赖或接口解析失败；请检查网络与运行环境") from None

    @staticmethod
    def post(url, **kwargs):
        return HTTP.request("POST", url, **kwargs)

    @staticmethod
    def get(url, **kwargs):
        return HTTP.request("GET", url, **kwargs)


# 兼容上游设备协议的调用形态，实际 HTTP 由本脚本实现。
class Reply:
    def __init__(self, data):
        self.data = data
    def json(self):
        return self.data

class DeviceHTTP:
    @staticmethod
    def post(url, **kwargs):
        return Reply(HTTP.post(url, **kwargs))

requests = DeviceHTTP


def sync_time():
    global _TIME_OFFSET
    import email.utils
    try:
        headers = HTTP.request("HEAD", "https://zonai.skland.com/")
        stamp = headers.get("Date") or headers.get("date")
        _TIME_OFFSET = email.utils.parsedate_to_datetime(stamp).timestamp() - time.time()
        log_info("服务器时间校准完成")
    except Exception:
        _TIME_OFFSET = 0.0
        log_info("⚠️ 时间校准不可用，使用本地时间")

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

def _des_encrypt(obj: dict) -> dict:
    result = {}
    for key, value in obj.items():
        rule = DES_RULE.get(key)
        if not rule:
            result[key] = value
            continue
        if rule["is_encrypt"] == 1:
            key = rule["key"].encode("utf-8")
            cipher = Cipher(TripleDES(key * 3), ECB())
            data = str(value).encode("utf-8")
            data += b"\x00" * (8 - len(data) % 8)
            encrypted = cipher.encryptor().update(data)
            result[rule["obfuscated_name"]] = base64.b64encode(encrypted).decode("utf-8")
        else:
            result[rule["obfuscated_name"]] = value
    return result


def _aes_encrypt(data: bytes, key: bytes) -> str:
    iv = b"0102030405060708"
    cipher = Cipher(AES(key), CBC(iv))
    encryptor = cipher.encryptor()
    pad_len = 16 - (len(data) % 16)
    data += b"\x00" * pad_len
    encrypted = encryptor.update(data) + encryptor.finalize()
    return encrypted.hex()


def _gzip_compress(obj: dict) -> bytes:
    json_str = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(gzip.compress(json_str.encode("utf-8"), compresslevel=2, mtime=0))


def _get_tn(obj: dict) -> str:
    sorted_keys = sorted(obj.keys())
    parts = []
    for k in sorted_keys:
        v = obj[k]
        if isinstance(v, (int, float)):
            parts.append(str(int(v * 10000)))
        elif isinstance(v, dict):
            parts.append(_get_tn(v))
        else:
            parts.append(str(v))
    return "".join(parts)


def _get_smid() -> str:
    t = real_localtime()
    time_str = f"{t.tm_year}{t.tm_mon:02d}{t.tm_mday:02d}{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}"
    uid = str(uuid.uuid4())
    md5_uid = hashlib.md5(uid.encode()).hexdigest()
    base = time_str + md5_uid + "00"
    smsk = hashlib.md5(("smsk_web_" + base).encode()).hexdigest()[:14]
    return base + smsk + "0"


def get_device_id() -> str:
    global _DID_CACHE
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    global Cipher, AES, TripleDES, CBC, ECB
    from cryptography.hazmat.primitives.ciphers import Cipher
    from cryptography.hazmat.primitives.ciphers.algorithms import AES
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    from cryptography.hazmat.primitives.ciphers.modes import CBC, ECB
    _PUBLIC_KEY = serialization.load_der_public_key(base64.b64decode(SM_CONFIG["publicKey"]))
    if _DID_CACHE:
        log_info("使用缓存的设备凭据")
        return _DID_CACHE

    log_info("开始生成设备 ID...")
    uid = str(uuid.uuid4()).encode("utf-8")
    pri_id = hashlib.md5(uid).hexdigest()[:16]
    ep = _PUBLIC_KEY.encrypt(uid, padding.PKCS1v15())
    ep_b64 = base64.b64encode(ep).decode("utf-8")

    browser = BROWSER_ENV.copy()
    current_time = int(time.time() * 1000)
    browser.update({"vpw": str(uuid.uuid4()), "svm": current_time, "trees": str(uuid.uuid4()), "pmf": current_time})

    des_target = {
        **browser,
        "protocol": 102, "organization": SM_CONFIG["organization"], "appId": SM_CONFIG["appId"],
        "os": "web", "version": "3.0.0", "sdkver": "3.0.0",
        "box": "", "rtype": "all", "smid": _get_smid(), "subVersion": "1.0.0", "time": 0,
    }
    des_target["tn"] = hashlib.md5(_get_tn(des_target).encode()).hexdigest()

    des_encrypted = _des_encrypt(des_target)
    compressed = _gzip_compress(des_encrypted)
    aes_encrypted = _aes_encrypt(compressed, pri_id.encode("utf-8"))

    url = f"https://{SM_CONFIG['apiHost']}/deviceprofile/v4"
    payload = {"appId": "default", "compress": 2, "data": aes_encrypted, "encode": 5, "ep": ep_b64, "organization": SM_CONFIG["organization"], "os": "web"}
    log_info("向数美服务请求设备 ID...")
    resp = requests.post(url, json=payload).json()
    if resp.get("code") != 1100:
        raise TaskError("设备服务业务失败")
    detail = resp.get("detail")
    if not isinstance(detail, dict) or not isinstance(detail.get("deviceId"), str) or not detail["deviceId"]:
        raise TaskError("设备服务响应缺少设备凭据")
    _DID_CACHE = "B" + detail["deviceId"]
    log_success("设备凭据生成成功")
    return _DID_CACHE



def generate_signature(path: str, body_or_query: str, token: str, d_id: str) -> tuple:
    timestamp = str(int(real_time()) - 2)
    header_ca = {"platform": "3", "timestamp": timestamp, "dId": d_id, "vName": "1.0.0"}
    header_str = json.dumps(header_ca, separators=(",", ":"))
    raw_string = path + body_or_query + timestamp + header_str
    hmac_sha256 = hmac.new(token.encode(), raw_string.encode(), hashlib.sha256).hexdigest()
    sign = hashlib.md5(hmac_sha256.encode()).hexdigest()
    return sign, header_ca


def get_sign_headers(url: str, method: str, body, token: str, d_id: str, cred: str) -> dict:
    parsed = parse.urlparse(url)
    if method.lower() == "get":
        sign, header_ca = generate_signature(parsed.path, parsed.query, token, d_id)
    else:
        body_str = json.dumps(body) if body else ""
        sign, header_ca = generate_signature(parsed.path, body_str, token, d_id)
    return {
        "cred": cred,
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1",
        "Accept-Encoding": "gzip", "Connection": "close",
        "X-Requested-With": "com.hypergryph.skland",
        "sign": sign, **header_ca,
    }




def business(data, field, label):
    # 缺失业务码、字符串码和布尔值均不能视为成功。
    value = data.get(field)
    if type(value) is not int or value != 0:
        code = str(value) if type(value) is int else "缺失或格式异常"
        raise TaskError(f"{label}业务失败（业务码：{code}）")
    payload = data.get("data")
    if not isinstance(payload, dict):
        raise TaskError(f"{label}响应缺少有效数据")
    return payload


def required_text(data, key, label):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TaskError(f"{label}响应缺少必要字段")
    return value


SECRETS = []


def display(value):
    # 官方昵称、公开 UID 原样显示；只移除日志控制字符和已知凭据。
    if not isinstance(value, (str, int, float)):
        return "[字段格式异常]"
    text = str(value).replace("\n", " ").replace("\r", " ")
    for secret in SECRETS:
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    return "".join(c for c in text if c.isprintable())


class Account:
    def __init__(self, index):
        self.index = index
        self.stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        self.stage = 0
        self.details = []
        self.started = time.monotonic()

    def step(self, name, action):
        self.stage += 1
        self.stats["total"] += 1
        start = time.monotonic()
        log_info(f"账号 {self.index} 阶段 {self.stage}：{name}")
        try:
            result = action()
            self.stats["success"] += 1
            if isinstance(result, str):
                self.details.append(f"✅ {display(name)}：{display(result)}")
            log_info(f"✅ 账号 {self.index} 阶段 {self.stage}：{name}成功，耗时 {time.monotonic()-start:.2f} 秒")
            return result
        except Exception as exc:
            self.stats["failed"] += 1
            reason = str(exc) if isinstance(exc, TaskError) else "运行异常，请检查依赖和接口契约"
            self.details.append(f"❌ {display(name)}：{display(reason)}")
            log_info(f"❌ 账号 {self.index} 阶段 {self.stage}：{name}失败；{display(reason)}；耗时 {time.monotonic()-start:.2f} 秒")
            raise TaskError(reason) from None

    def finish(self):
        s = self.stats
        log_info(f"账号 {self.index} 统计：总任务 {s['total']}，成功 {s['success']}，已完成 {s['alreadyComplete']}，跳过 {s['skipped']}，失败 {s['failed']}，耗时 {time.monotonic()-self.started:.2f} 秒")
        return {"account": self.index, **s, "details": self.details, "elapsedSeconds": round(time.monotonic()-self.started, 2),
                "status": "failure" if s["failed"] else "success"}


def auth_headers(did):
    return {"User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1", "Accept-Encoding": "gzip",
            "Connection": "close", "dId": did,
            "X-Requested-With": "com.hypergryph.skland"}


def grant(user_token, did):
    response = HTTP.post("https://as.hypergryph.com/user/oauth2/v2/grant",
                         headers=auth_headers(did),
                         json={"appCode": APP_CODE, "token": user_token, "type": 0})
    code = required_text(business(response, "status", "授权"), "code", "授权")
    SECRETS.append(code)
    return code


def credentials(code, did):
    response = HTTP.post("https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code",
                         headers=auth_headers(did), json={"code": code, "kind": 1})
    data = business(response, "code", "登录")
    cred = required_text(data, "cred", "登录")
    token = required_text(data, "token", "登录")
    SECRETS.extend([cred, token])
    for key in ("nickName", "nickname", "username", "displayName", "uid"):
        if data.get(key) is not None:
            log_info(f"账号身份：{display(data[key])}")
    return cred, token


def bindings(cred, token, did):
    url = "https://zonai.skland.com/api/v1/game/player/binding"
    response = HTTP.get(url, headers=get_sign_headers(url, "get", None, token, did, cred))
    games = business(response, "code", "角色查询").get("list")
    if not isinstance(games, list):
        raise TaskError("角色列表格式异常")
    tasks = []
    for game in games:
        if not isinstance(game, dict):
            raise TaskError("游戏列表格式异常")
        app = game.get("appCode")
        if app not in ("arknights", "endfield"):
            continue
        characters = game.get("bindingList")
        if not isinstance(characters, list):
            raise TaskError("绑定角色格式异常")
        for char in characters:
            if not isinstance(char, dict):
                raise TaskError("角色数据格式异常")
            if app == "arknights":
                tasks.append((app, char))
            else:
                roles = char.get("roles")
                if not isinstance(roles, list):
                    raise TaskError("终末地角色列表格式异常")
                for role in roles:
                    if not isinstance(role, dict):
                        raise TaskError("终末地角色数据格式异常")
                    tasks.append((app, role))
    if not tasks:
        raise TaskError("未找到可签到的绑定角色，未验证业务成功")
    log_info(f"角色查询成功，可签到角色 {len(tasks)} 个")
    return tasks


def attendance(app, role, cred, token, did):
    if app == "arknights":
        if not role.get("gameId") or not role.get("uid"):
            raise TaskError("明日方舟角色缺少游戏或角色标识")
        url = "https://zonai.skland.com/api/v1/game/attendance"
        body = {"gameId": role["gameId"], "uid": role["uid"]}
        headers = get_sign_headers(url, "post", body, token, did, cred)
        # 签名所用字符串与实际发送的正文完全一致。
        headers["Content-Type"] = "application/json"
        response = HTTP.post(url, headers=headers, data=json.dumps(body).encode("utf-8"))
        data = business(response, "code", "明日方舟签到")
        awards = data.get("awards")
        if not isinstance(awards, list):
            raise TaskError("签到响应缺少奖励列表")
        rewards = []
        for award in awards:
            if not isinstance(award, dict) or not isinstance(award.get("resource"), dict):
                raise TaskError("签到奖励格式异常")
            rewards.append(f"{display(required_text(award['resource'], 'name', '奖励'))}x{display(award.get('count', 1))}")
    else:
        if not role.get("roleId") or not role.get("serverId"):
            raise TaskError("终末地角色缺少角色或服务器标识")
        url = "https://zonai.skland.com/web/v1/game/endfield/attendance"
        headers = get_sign_headers(url, "post", None, token, did, cred)
        headers.update({"Content-Type": "application/json",
                        "sk-game-role": f"3_{role['roleId']}_{role['serverId']}",
                        "referer": "https://game.skland.com/", "origin": "https://game.skland.com/"})
        response = HTTP.post(url, headers=headers)
        data = business(response, "code", "终末地签到")
        info, ids = data.get("resourceInfoMap"), data.get("awardIds")
        if not isinstance(info, dict) or not isinstance(ids, list):
            raise TaskError("终末地签到奖励格式异常")
        rewards = []
        for award in ids:
            if not isinstance(award, dict) or "id" not in award:
                raise TaskError("终末地奖励标识缺失")
            item = info.get(str(award["id"]))
            if not isinstance(item, dict) or "count" not in item:
                raise TaskError("终末地奖励详情缺失")
            rewards.append(f"{display(required_text(item, 'name', '奖励'))}x{display(item['count'])}")
    message = f"签到成功，获得 {','.join(rewards) if rewards else '无额外奖励'}"
    log_info(message)
    return message



def validate_device_config():
    if not SM_CONFIG["apiHost"] or not SM_CONFIG["publicKey"]:
        raise TaskError("设备协议配置缺失")
    base64.b64decode(SM_CONFIG["publicKey"], validate=True)
    return "设备协议配置有效；未生成远程设备凭据"


def validate_dry_signature(url, body):
    headers = get_sign_headers(url, "post", body, "dry-signing-key", "dry-device", "dry-cred")
    if len(headers["sign"]) != 32 or headers["platform"] != "3":
        raise TaskError("离线请求签名格式异常")
    return "请求签名构造通过；未发送签到请求"


def process(index, token):
    account = Account(index)
    try:
        if DRY_RUN:
            account.step("设备协议预演", lambda: validate_device_config())
            account.step("登录流程预演", lambda: business({"status": 0, "data": {}}, "status", "模拟授权"))
            account.step("角色查询预演", lambda: business({"code": 0, "data": {"list": []}}, "code", "模拟角色查询"))
            for game, url, body in (
                ("明日方舟", "https://zonai.skland.com/api/v1/game/attendance", {"gameId": "dry-game", "uid": "dry-role"}),
                ("终末地", "https://zonai.skland.com/web/v1/game/endfield/attendance", None),
            ):
                account.step(f"{game}签到签名预演", lambda: validate_dry_signature(url, body))
            log_info("DRY_RUN_OK：仅验证配置与执行流程，未发送任何业务请求")
        else:
            did = account.step("生成设备凭据", get_device_id)
            SECRETS.append(did)
            code = account.step("取得授权", lambda: grant(token, did))
            cred, key = account.step("登录森空岛", lambda: credentials(code, did))
            tasks = account.step("查询绑定角色", lambda: bindings(cred, key, did))
            for app, role in tasks:
                nickname = role.get("nickName") or role.get("nickname") or role.get("uid") or role.get("roleId")
                game = "明日方舟" if app == "arknights" else "终末地"
                label = f"{game}角色 {display(nickname)} 签到"
                try:
                    account.step(label, lambda: attendance(app, role, cred, key, did))
                except TaskError:
                    continue
    except TaskError:
        pass
    finally:
        result = account.finish()
    return result


NOTIFY_WORKER = r'''
import importlib, importlib.util, json, os, socket, sys
payload = json.load(sys.stdin)
if payload['dryRun']:
    def offline(*args, **kwargs):
        raise RuntimeError('dry-run 禁止网络通知')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    socket.getaddrinfo = offline
paths = []
if os.environ.get('QINGLONG_NOTIFY_DIR'):
    paths.append(os.path.join(os.environ['QINGLONG_NOTIFY_DIR'], 'notify.py'))
paths.extend(['/ql/data/scripts/notify.py', '/ql/scripts/notify.py'])
module = None
for path in paths:
    if os.path.isfile(path):
        spec = importlib.util.spec_from_file_location('qinglong_notify', path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.dirname(path))
        spec.loader.exec_module(module)
        break
if module is None:
    module = importlib.import_module('notify')
module.send(payload['title'], payload['body'])
'''


def notify(summary):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in {"0", "false", "no", "off"}:
        log_info("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    body = (f"模式：{summary['mode']}；状态：{summary['status']}\n"
            f"账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}\n"
            f"子任务：{json.dumps(summary['tasks'], ensure_ascii=False)}")
    for account in summary["accountResults"]:
        body += f"\n账号 {account['account']}：{account['status']}"
        for detail in account["details"]:
            body += "\n  " + detail
    env = dict(os.environ)
    env.pop("SKYLAND_TOKEN", None)
    try:
        result = subprocess.run([sys.executable, "-c", NOTIFY_WORKER],
                                input=json.dumps({"title": "森空岛签到", "body": body, "dryRun": DRY_RUN}),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=20, env=env)
        if result.returncode:
            raise TaskError("通知不可用")
        log_info("✅ 脱敏通知已交给青龙通知模块")
        return "sent"
    except Exception:
        log_info("⚠️ 通知模块不可用或发送失败，保留业务退出码" + ("；预演禁止网络通知" if DRY_RUN else ""))
        return "unavailable"


def main():
    started = time.monotonic()
    now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    tokens = [line.strip() for line in os.getenv("SKYLAND_TOKEN", "").splitlines() if line.strip()]
    SECRETS.extend(tokens)
    log_info("========== 森空岛签到 ==========")
    log_info(f"开始时间：{now()}；模式：{'断网预演' if DRY_RUN else '正式运行'}；账号数：{len(tokens)}")
    records = []
    config_error = not tokens or any(',' in token or any(c.isspace() for c in token) for token in tokens)
    if config_error:
        log_info("❌ 配置错误：SKYLAND_TOKEN 必须每个非空行一个完整 Token，不使用逗号或空白分隔")
    else:
        if not DRY_RUN:
            sync_time()
        for index, token in enumerate(tokens, 1):
            records.append(process(index, token))
    failed = sum(r["status"] == "failure" for r in records)
    success = len(records) - failed
    status = ("configuration-error" if config_error else
              "partial-failure" if failed and success else
              "failure" if failed else "dry-run" if DRY_RUN else "success")
    exit_code = 1 if config_error or failed else 0
    tasks = {key: sum(r[key] for r in records) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    summary = {"task": "森空岛签到", "mode": "dry-run" if DRY_RUN else "live", "status": status,
               "accounts": len(tokens), "success": success, "failed": len(tokens) if config_error else failed,
               "tasks": tasks, "accountResults": records, "exitCode": exit_code}
    log_info("----------------------------------------")
    log_info(f"任务统计：账号 {summary['accounts']}，成功 {success}，失败 {summary['failed']}；子任务 {json.dumps(tasks, ensure_ascii=False)}")
    summary["notification"] = notify(summary)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 2)
    summary["finishedAt"] = now()
    log_info(f"完成时间：{summary['finishedAt']}；总耗时：{summary['elapsedSeconds']} 秒；最终状态：{status}；通知：{summary['notification']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
