#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 电子科大晚安成电打卡
# cron: 25 21 * * *
# SPDX-License-Identifier: MIT
"""电子科技大学「晚安成电」每日打卡（jzsz.uestc.edu.cn）独立维护版。

来源：kznLeaf/faq-daily-checkin（MIT），合并 checkin / login / encrypt 同应用能力。
本维护版改为青龙可调度独立脚本：环境变量多账号、断网预演、超时与业务成功判定、
脱敏通知与时间轴日志；不依赖私有仓库、本地 config.yaml 或长驻循环调度。
青龙请用 cron 在晚间窗口触发；上游 --loop 随机等待不纳入本脚本。

FAQ_CHECKIN_ACCOUNTS：每个非空行一个账号（推荐 JSON）。
登录模式 JSON 必填 student_id、password、browser_fingerprint、latitude、longitude、address；
会话模式 JSON 必填 session、latitude、longitude、address（跳过 CAS 登录）。
也支持「学号|密码|指纹|纬度|经度|地址」；仅按前五个竖线拆分，地址可含竖线。
会话管道格式：「session|SESSION值|纬度|经度|地址」，仅按前四个竖线拆分。
浏览器指纹：登录 idas.uestc.edu.cn 后从 Cookie 复制 MULTIFACTOR_BROWSER_FINGERPRINT。
经纬度与逆地理地址须为本人真实打卡位置，勿使用他人坐标。
FAQ_CHECKIN_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
FAQ_CHECKIN_TIMEOUT：单次请求超时秒数，默认 15，范围 5..120。
FAQ_CHECKIN_MMWEBID：可选微信 MMWEBID 数字；未设置则随机生成。
依赖公共包：requests、pycryptodome。不打印密码、SESSION、指纹或原始响应。

MIT License

Copyright (c) 2026 kznLeaf

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
        _ql_notify_identities = ('d8ce25fb54ffde83', 'scripts/faq_daily_checkin.py', 'faq_daily_checkin.py', 'faq_daily_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import datetime
import fnmatch
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

TITLE = "电子科大晚安成电打卡"
CATALOG_ID = "d8ce25fb54ffde83"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
DEFAULT_BASE_URL = "https://jzsz.uestc.edu.cn"
API_PATH = "/daily-checkin/api/student-checkin-record/checkin"
IDAS_HOST = "https://idas.uestc.edu.cn"
JZSZ_HOST = "https://jzsz.uestc.edu.cn"
LOGIN_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) "
    "Gecko/20100101 Firefox/153.0"
)
AES_CHARSET = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
ALREADY_HINTS = ("已打卡", "已经打卡", "重复打卡", "今日已", "无需重复", "已完成打卡")


class SafeError(Exception):
    """仅允许脱敏说明进入日志。"""


def clock() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def redact_text(value: Any, secrets: List[str]) -> str:
    text = str(value)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def env_flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    raise SafeError("{} 必须为布尔开关值".format(name))


def parse_timeout() -> int:
    raw = os.environ.get("FAQ_CHECKIN_TIMEOUT", "15").strip() or "15"
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("FAQ_CHECKIN_TIMEOUT 必须是整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError("FAQ_CHECKIN_TIMEOUT 允许范围 5..120")
    return value


def parse_float_field(raw: Any, label: str) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise SafeError("{} 必须是数字".format(label)) from exc
    if not (-90.0 <= value <= 90.0) and label.startswith("纬度"):
        raise SafeError("纬度超出有效范围")
    if label.startswith("经度") and not (-180.0 <= value <= 180.0):
        raise SafeError("经度超出有效范围")
    return value


def normalize_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return DEFAULT_BASE_URL
    if not value.startswith("https://"):
        raise SafeError("业务站点地址必须是 HTTPS")
    if any(c.isspace() for c in value):
        raise SafeError("业务站点地址格式错误")
    return value


def get_random_string(length: int) -> str:
    return "".join(random.choice(AES_CHARSET) for _ in range(length))


def encrypt_password(password: str, salt: str) -> str:
    """金智 CAS encrypt.js 等价实现（AES-CBC + PKCS7）。"""
    if not salt or len(salt) != 16:
        raise SafeError("登录页盐值无效")
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError as exc:
        raise SafeError("缺少公开依赖 pycryptodome，请在青龙依赖管理中安装") from exc

    plain_text = (get_random_string(64) + password).encode("utf-8")
    key = salt.encode("utf-8")
    iv = get_random_string(16).encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plain_text, AES.block_size, style="pkcs7"))
    return base64.b64encode(ciphertext).decode("utf-8")


def mmwebid_value() -> int:
    raw = os.environ.get("FAQ_CHECKIN_MMWEBID", "").strip()
    if not raw:
        return random.randint(100, 9999)
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("FAQ_CHECKIN_MMWEBID 必须是整数") from exc
    if value <= 0:
        raise SafeError("FAQ_CHECKIN_MMWEBID 必须为正整数")
    return value


def generate_wechat_miniprogram_ua(appid: str = "wxaa78bf2905f01cee") -> str:
    net_type = "WIFI"
    mm_web_id = mmwebid_value()
    wechat_version = "8.0.79.3200(0x28004F32)"
    xweb_version = "1500145"
    sdk_date = "20260902"
    chrome_version = "150.0.7871.189"
    return (
        "Mozilla/5.0 (Linux; Android 14; ELI-AN00 Build/HONORELI-AN00; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{chrome} "
        "Mobile Safari/537.36 XWEB/{xweb} MMWEBSDK/{sdk} "
        "MMWEBID/{mm} MicroMessenger/{wechat} "
        "WeChat/arm64 Weixin NetType/{net} Language/zh_CN ABI/arm64 "
        "miniProgram/{appid}"
    ).format(
        chrome=chrome_version,
        xweb=xweb_version,
        sdk=sdk_date,
        mm=mm_web_id,
        wechat=wechat_version,
        net=net_type,
        appid=appid,
    )


def add_realistic_drift(value: float, max_limit: float = 0.000003) -> float:
    sigma = max_limit / 3.0
    drift = random.gauss(0, sigma)
    drift = max(-max_limit, min(drift, max_limit))
    return round(value + drift, 6)


def shanghai_now() -> datetime.datetime:
    if ZoneInfo is not None:
        return datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    return datetime.datetime.now().astimezone()


def message_already_complete(message: str) -> bool:
    text = (message or "").strip()
    return any(hint in text for hint in ALREADY_HINTS)


def account_secrets(account: Dict[str, Any]) -> List[str]:
    values = [
        account.get("password") or "",
        account.get("browser_fingerprint") or "",
        account.get("session") or "",
        account.get("student_id") or "",
    ]
    return [item for item in values if item]


def parse_account_payload(data: Dict[str, Any], index: int) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise SafeError("账号 {} JSON 必须是对象".format(index))
    latitude = parse_float_field(data.get("latitude"), "纬度")
    longitude = parse_float_field(data.get("longitude"), "经度")
    address = str(data.get("address") or "").strip()
    if not address:
        raise SafeError("账号 {} 缺少逆地理地址 address".format(index))
    session = str(data.get("session") or data.get("SESSION") or "").strip()
    student_id = str(data.get("student_id") or data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    fingerprint = str(
        data.get("browser_fingerprint")
        or data.get("fingerprint")
        or data.get("MULTIFACTOR_BROWSER_FINGERPRINT")
        or ""
    ).strip()
    if session:
        return {
            "mode": "session",
            "session": session,
            "student_id": student_id,
            "password": "",
            "browser_fingerprint": "",
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
        }
    if not student_id or not password or not fingerprint:
        raise SafeError(
            "账号 {} 登录模式须提供 student_id、password、browser_fingerprint".format(index)
        )
    return {
        "mode": "login",
        "session": "",
        "student_id": student_id,
        "password": password,
        "browser_fingerprint": fingerprint,
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
    }


def parse_account_line(line: str, index: int) -> Dict[str, Any]:
    text = line.strip()
    if not text:
        raise SafeError("账号 {} 为空行".format(index))
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise SafeError("账号 {} JSON 无法解析".format(index)) from exc
        return parse_account_payload(payload, index)

    lowered = text.lower()
    if lowered.startswith("session|"):
        parts = text.split("|", 4)
        if len(parts) < 5:
            raise SafeError(
                "账号 {} 会话格式错误；应为 session|SESSION|纬度|经度|地址".format(index)
            )
        return parse_account_payload(
            {
                "session": parts[1],
                "latitude": parts[2],
                "longitude": parts[3],
                "address": parts[4],
            },
            index,
        )

    parts = text.split("|", 5)
    if len(parts) < 6:
        raise SafeError(
            "账号 {} 格式错误；请使用 JSON 或「学号|密码|指纹|纬度|经度|地址」".format(index)
        )
    return parse_account_payload(
        {
            "student_id": parts[0],
            "password": parts[1],
            "browser_fingerprint": parts[2],
            "latitude": parts[3],
            "longitude": parts[4],
            "address": parts[5],
        },
        index,
    )


def load_accounts() -> List[Dict[str, Any]]:
    raw = os.environ.get("FAQ_CHECKIN_ACCOUNTS", "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if lines:
        return [parse_account_line(line, index) for index, line in enumerate(lines, 1)]

    # 兼容单账号拆分变量（可选）
    student_id = os.environ.get("FAQ_STUDENT_ID", "").strip()
    password = os.environ.get("FAQ_PASSWORD", "").strip()
    fingerprint = os.environ.get("FAQ_BROWSER_FINGERPRINT", "").strip()
    session = os.environ.get("FAQ_SESSION", "").strip()
    latitude = os.environ.get("FAQ_LATITUDE", "").strip()
    longitude = os.environ.get("FAQ_LONGITUDE", "").strip()
    address = os.environ.get("FAQ_ADDRESS", "").strip()
    if session or student_id or password or fingerprint:
        payload: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
        }
        if session:
            payload["session"] = session
        else:
            payload.update(
                {
                    "student_id": student_id,
                    "password": password,
                    "browser_fingerprint": fingerprint,
                }
            )
        return [parse_account_payload(payload, 1)]

    raise SafeError("缺少必填环境变量 FAQ_CHECKIN_ACCOUNTS")


def require_requests():
    try:
        import requests
    except ImportError as exc:
        raise SafeError("缺少公开依赖 requests，请在青龙依赖管理中安装") from exc
    return requests


class AccountRunner:
    def __init__(self, number: int):
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def stage(self, number: int, name: str, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        state, detail = "failure", "操作未完成"
        result = None
        try:
            state, detail, result = operation()
            return result
        except SafeError as error:
            detail = str(error)
            raise
        except Exception:
            detail = "内部处理失败，已抑制异常详情"
            raise SafeError(detail) from None
        finally:
            self.stats[state] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number: int, name: str, reason: str) -> None:
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self) -> None:
        label = self.identity or "账号{}".format(self.number)
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


def cas_login(account: Dict[str, Any], timeout: int, secrets: List[str]) -> str:
    requests = require_requests()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": LOGIN_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,en-US;q=0.9,en;q=0.8",
        }
    )
    login_url = "{}/authserver/login?service={}/".format(IDAS_HOST, JZSZ_HOST)
    try:
        resp = session.get(login_url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise SafeError("获取登录页失败：网络或超时") from exc

    exec_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
    salt_match = re.search(r'id="pwdEncryptSalt"\s+value="([^"]+)"', resp.text)
    if not exec_match or not salt_match:
        raise SafeError("无法从登录页提取必要参数")
    execution = exec_match.group(1)
    salt = salt_match.group(1)
    secrets.append(salt)
    secrets.append(execution)

    session.cookies.set(
        name="MULTIFACTOR_BROWSER_FINGERPRINT",
        value=account["browser_fingerprint"],
        domain="idas.uestc.edu.cn",
        path="/",
    )
    encrypted_pwd = encrypt_password(account["password"], salt)
    secrets.append(encrypted_pwd)
    login_data = {
        "username": account["student_id"],
        "password": encrypted_pwd,
        "captcha": "",
        "_eventId": "submit",
        "cllt": "userNameLogin",
        "dllt": "generalLogin",
        "lt": "",
        "execution": execution,
    }
    session.headers["Content-Type"] = "application/x-www-form-urlencoded"
    session.headers["Origin"] = IDAS_HOST
    session.headers["Referer"] = login_url
    try:
        resp_submit = session.post(
            login_url, data=login_data, allow_redirects=False, timeout=timeout
        )
    except requests.exceptions.RequestException as exc:
        raise SafeError("提交登录失败：网络或超时") from exc

    if resp_submit.status_code != 302:
        raise SafeError("CAS 登录失败（凭据无效或需额外验证）")

    location = resp_submit.headers.get("Location", "")
    if not location:
        raise SafeError("登录重定向目标缺失")
    session.headers["Referer"] = "{}/".format(IDAS_HOST)
    try:
        session.get(location, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise SafeError("跟随登录重定向失败：网络或超时") from exc

    session_cookie = session.cookies.get("SESSION", domain="jzsz.uestc.edu.cn")
    if not session_cookie:
        # 部分环境下 domain 匹配不稳定，回退扫描
        for cookie in session.cookies:
            if cookie.name == "SESSION" and cookie.value:
                session_cookie = cookie.value
                break
    if not session_cookie:
        raise SafeError("未获取到业务 SESSION")
    secrets.append(session_cookie)

    warmup_url = "{}/api/isLoginFailure?_t={}".format(
        JZSZ_HOST, int(time.time() * 1000)
    )
    session.headers["Accept"] = "application/json, text/plain, */*"
    session.headers["Content-Type"] = "application/json;charset=UTF-8"
    session.headers["Origin"] = JZSZ_HOST
    session.headers["Referer"] = "{}/".format(JZSZ_HOST)
    session.headers["Sec-Fetch-Site"] = "same-origin"
    session.headers["Sec-Fetch-Mode"] = "cors"
    try:
        resp_warmup = session.get(warmup_url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise SafeError("激活 SESSION 失败：网络或超时") from exc
    if resp_warmup.status_code != 200:
        raise SafeError("激活 SESSION 失败（HTTP {}）".format(resp_warmup.status_code))
    return session_cookie


def send_checkin(
    session_cookie: str,
    account: Dict[str, Any],
    base_url: str,
    timeout: int,
    secrets: List[str],
) -> Tuple[str, str]:
    requests = require_requests()
    user_agent = generate_wechat_miniprogram_ua()
    session_id = str(uuid.uuid4())
    client_time = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "platform": "h5",
        "Origin": base_url,
        "X-Requested-With": "com.tencent.mm",
        "User-Agent": user_agent,
        "Referer": "{}/daily-checkin-h5/index.html?sessionId={}".format(
            base_url, session_id
        ),
        "sec-ch-ua-platform": '"Android"',
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Android WebView";v="150"',
        "sec-ch-ua-mobile": "?1",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    payload = {
        "latitude": add_realistic_drift(account["latitude"]),
        "longitude": add_realistic_drift(account["longitude"]),
        "reverseGeocode": account["address"],
        "clientTime": client_time,
        "userAgent": user_agent,
        "coordinateSystemCode": "gcj02",
        "accuracy": 30,
        "locationDurationMs": random.randint(300, 1000),
        "networkTypeCode": "wifi",
        "locationEnabled": False,
        "locationAuthorized": "",
        "locationAccuracy": "",
        "errorMessage": "",
    }
    try:
        response = requests.post(
            url="{}{}".format(base_url, API_PATH),
            headers=headers,
            cookies={"SESSION": session_cookie},
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        raise SafeError("打卡请求失败：网络或超时") from exc

    if response.status_code >= 400:
        raise SafeError("打卡 HTTP 失败（状态码 {}）".format(response.status_code))
    try:
        res_json = response.json()
    except ValueError as exc:
        raise SafeError("打卡响应不是有效 JSON") from exc
    if not isinstance(res_json, dict):
        raise SafeError("打卡响应结构无效")

    message = str(res_json.get("msg") or "").strip()
    safe_message = redact_text(message, secrets)[:120] if message else ""
    if res_json.get("code") == 0 and res_json.get("ok"):
        if message_already_complete(message):
            return "alreadyComplete", safe_message or "今日已打卡"
        return "success", safe_message or "打卡成功"
    if message_already_complete(message):
        return "alreadyComplete", safe_message or "今日已打卡"
    raise SafeError(safe_message or "未完成打卡")


def run_account(
    runner: AccountRunner,
    account: Dict[str, Any],
    base_url: str,
    timeout: int,
    dry_run: bool,
) -> None:
    secrets = account_secrets(account)

    def parameter_check():
        if account["mode"] == "session":
            if not account["session"]:
                raise SafeError("SESSION 为空")
        else:
            if not account["student_id"] or not account["password"]:
                raise SafeError("学号或密码为空")
            if not account["browser_fingerprint"]:
                raise SafeError("浏览器指纹为空")
        if not account["address"]:
            raise SafeError("逆地理地址为空")
        parse_float_field(account["latitude"], "纬度")
        parse_float_field(account["longitude"], "经度")
        return "success", "本地参数检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    identity = ""
    if account.get("student_id"):
        # 学号属于账号标识，截断展示避免完整输出
        sid = account["student_id"]
        identity = "学号尾号{}".format(sid[-4:]) if len(sid) >= 4 else "学号已配置"
        runner.identity = identity

    if dry_run:
        for number, name in (
            (2, "CAS登录或会话复用"),
            (3, "提交每日打卡"),
        ):
            runner.skip(number, name, "断网预演：不请求登录或打卡接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实身份、凭据或业务结果".format(runner.number)
        )
        return

    def obtain_session():
        if account["mode"] == "session":
            return "success", "使用提供的 SESSION，跳过 CAS 登录", account["session"]
        cookie = cas_login(account, timeout, secrets)
        return "success", "CAS 登录成功并已激活 SESSION", cookie

    session_cookie = runner.stage(2, "CAS登录或会话复用", obtain_session)
    secrets.append(session_cookie)

    def do_checkin():
        state, detail = send_checkin(
            session_cookie, account, base_url, timeout, secrets
        )
        return state, detail, None

    runner.stage(3, "提交每日打卡", do_checkin)
    if runner.stats["alreadyComplete"]:
        runner.status = "alreadyComplete"
    elif runner.stats["failure"]:
        runner.status = "failure"
    else:
        runner.status = "success"


PY_NOTIFY_RUNNER = r"""
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
            setattr(os, name, denied)
sys.path.insert(0, specification["directory"])
module = None
if specification["path"] is None:
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as error:
        sys.exit(3 if error.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", specification["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
sender = getattr(module, "send", None)
if not callable(sender):
    sys.exit(3)
result = sender(specification["title"], specification["body"])
sys.exit(1 if result is False else 0)
"""

JS_NOTIFY_RUNNER = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (input.dry_run) {
  const denied = () => { throw new Error('dry-run forbids network and external processes'); };
  require('net').Socket.prototype.connect = denied;
  require('dgram').createSocket = denied;
  for (const name of ['http', 'https']) {
    require(name).request = denied;
    require(name).get = denied;
  }
  require('tls').connect = denied;
  require('http2').connect = denied;
  const dns = require('dns');
  for (const key of Object.keys(dns)) if (typeof dns[key] === 'function') dns[key] = denied;
  for (const key of Object.keys(dns.promises)) if (typeof dns.promises[key] === 'function') dns.promises[key] = denied;
  const cp = require('child_process');
  for (const key of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) cp[key] = denied;
  require('worker_threads').Worker = denied;
  globalThis.fetch = denied;
}
Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
  .then(result => process.exit(result === false ? 1 : 0))
  .catch(() => process.exit(1));
"""


def notification_enabled() -> Tuple[bool, str]:
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "faq_daily_checkin.py",
        "candidate.py",
        "scripts/faq_daily_checkin.py",
        "faq-daily-checkin",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(
        ("python", directory / "notify.py")
        for directory in paths
        if (directory / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", directory / "sendNotify.js")
            for directory in paths
            if (directory / "sendNotify.js").is_file()
        )
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = (
            [sys.executable, "-c", PY_NOTIFY_RUNNER]
            if kind == "python"
            else [node, "-e", JS_NOTIFY_RUNNER]
        )
        try:
            result = subprocess.run(
                command,
                input=json.dumps(specification, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                log(
                    "通知：✅ 脱敏总结已交给青龙适配器"
                    + ("（断网保护启用）" if dry_run else "")
                )
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = os.environ.get("FAQ_CHECKIN_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts: List[AccountRunner] = []
    parsed: List[Dict[str, Any]] = []
    config_error = None
    base_url = DEFAULT_BASE_URL
    timeout = 15

    log("========== {} ==========".format(TITLE))
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise SafeError("FAQ_CHECKIN_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout()
        base_url = normalize_base_url(
            os.environ.get("FAQ_CHECKIN_BASE_URL", DEFAULT_BASE_URL)
        )
        parsed = load_accounts()
    except SafeError as error:
        config_error = str(error)
        log(
            "开始时间：{}；运行模式：{}；账号数：0".format(
                started_at, "断网预演" if dry_run else "真实执行"
            )
        )
        log("阶段 0 参数配置：❌ " + config_error)
    else:
        log(
            "开始时间：{}；运行模式：{}；账号数：{}".format(
                started_at, "断网预演" if dry_run else "真实执行", len(parsed)
            )
        )
        for number, account in enumerate(parsed, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, base_url, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(parsed):
                time.sleep(1)

    counts = {
        state: sum(item.status == state for item in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    account_total = len(parsed) if not config_error else 0
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    if config_error and not parsed:
        failed = max(failed, 1)
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and (succeeded or counts["dry-run"])
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status,
        account_total if not config_error else 0,
        succeeded,
        failed,
        counts["dry-run"],
        "是" if config_error else "否",
    )
    log("阶段 99 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log(
        "阶段 99 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started)
    )
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total if not config_error else 0,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total if not config_error else 0,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
