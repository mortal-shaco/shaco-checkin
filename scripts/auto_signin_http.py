#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: SakuraFRP每日签到
# cron: 7 9 * * *
from __future__ import annotations
#
# 来源：claaudy/sakurafrp-auto-sign auto_signin_http.py + geetest_crack.py（MIT）
# https://github.com/claaudy/sakurafrp-auto-sign
# 提交：b27240b156718ee4b958e9bc72133349c4831953
# GeeTest v3 协议逆向参考：ladeng07/sakura-signin；九宫格 Prompt 参考 Yumu2497/SakuraFrpQiandao（MIT）
#
# MIT License
#
# Copyright (c) 2026 Leon
# Copyright (c) claaudy / sakurafrp-auto-sign contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""SakuraFRP（natfrp.com）每日签到 - 青龙维护版。

功能清点（相对上游 auto_signin_http.py）：
- OpenID（openid.13a.com）账号密码登录，经 GeeTest v3 验证后桥接到 natfrp 会话
- 查询用户公开身份（name / id）与签到状态；未签到时破解签到 GeeTest 并提交每日签到
- 使用 OpenAI 兼容多模态接口识别点选/九宫格验证码（正式执行需要）
- 移除 .env 强制加载、原始响应大段打印、本地 mousepath.json / 私有 geetest_crack 模块路径依赖
- 将 GeeTest 协议实现内联；公开依赖仅 httpx 与 cryptography（延迟导入，断网预演不加载）
- 增加逐行多账号、SAKURAFRP_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

SAKURAFRP_ACCOUNTS（规范）：每个非空行一个账号，格式 用户名或邮箱|密码；
  仅在第一个 | 处分割，后续原文保留为密码。不要用 & 或 @ 分隔账号。
username / password：可选兼容单账号输入（二者同时非空时视为一个账号）。
SAKURAFRP_CAPTCHA_API_KEY（规范）：多模态验证码识别 API Key；CAPTCHA_API_KEY 为兼容别名。
SAKURAFRP_CAPTCHA_API_BASE / CAPTCHA_API_BASE：可选，默认 https://api.openai.com/v1。
SAKURAFRP_CAPTCHA_MODEL / CAPTCHA_MODEL：可选，默认 gpt-4o。
SAKURAFRP_MAX_RETRIES / MAX_RETRIES：验证码最大重试，默认 10，范围 1..20。
SAKURAFRP_TIMEOUT：单次 HTTPS 超时秒数，默认 30，范围 5..120。
SAKURAFRP_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 9 * * *（对齐上游 Docker 示例）。不打印密码、Cookie、Token、validate 或原始响应。
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
        _ql_notify_identities = ('997de6e58b1ddd7a', 'scripts/auto_signin_http.py', 'auto_signin_http.py', 'auto_signin_http')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

TITLE = "SakuraFRP每日签到"
CATALOG_ID = "997de6e58b1ddd7a"
DEFAULT_TIMEOUT = 30
DEFAULT_CAPTCHA_BASE = "https://api.openai.com/v1"
DEFAULT_CAPTCHA_MODEL = "gpt-4o"
DEFAULT_MAX_RETRIES = 10
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

COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-ch-ua": '"Chromium";v="145", "Not:A_Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
}
OPENID_AJAX_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "x-requested-with": "XMLHttpRequest",
}
DEFAULT_MOUSE_PATH = [
    ["move", 385, 313, 1724572150164, "pointermove"],
    ["move", 385, 315, 1724572150166, "pointermove"],
    ["move", 386, 315, 1724572150174, "pointermove"],
    ["move", 387, 315, 1724572150182, "pointermove"],
    ["move", 387, 316, 1724572150188, "pointermove"],
    ["move", 388, 316, 1724572150204, "pointermove"],
    ["move", 388, 317, 1724572150218, "pointermove"],
    ["down", 388, 317, 1724572150586, "pointerdown"],
    ["focus", 1724572150587],
    ["up", 388, 317, 1724572150632, "pointerup"],
]

_httpx = None
_crypto = None


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def ensure_live_deps() -> None:
    global _httpx, _crypto
    if _httpx is not None and _crypto is not None:
        return
    try:
        import httpx as httpx_mod
    except ImportError as exc:
        raise SafeError("缺少公开依赖 httpx，请安装 httpx[http2]") from exc
    try:
        from cryptography.hazmat.primitives import padding, serialization
        from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:
        raise SafeError("缺少公开依赖 cryptography，请从公共包仓库安装") from exc
    _httpx = httpx_mod
    _crypto = {
        "Cipher": Cipher,
        "algorithms": algorithms,
        "modes": modes,
        "padding": padding,
        "serialization": serialization,
        "PKCS1v15": PKCS1v15,
    }


def resolve_timeout() -> float:
    raw = env("SAKURAFRP_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("SAKURAFRP_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("SAKURAFRP_TIMEOUT 须在 5 到 120 秒之间")
    return value


def resolve_retries() -> int:
    raw = env("SAKURAFRP_MAX_RETRIES") or env("MAX_RETRIES")
    if not raw:
        return DEFAULT_MAX_RETRIES
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("SAKURAFRP_MAX_RETRIES 须为正整数") from exc
    if value < 1 or value > 20:
        raise SafeError("SAKURAFRP_MAX_RETRIES 须在 1 到 20 之间")
    return value


def resolve_captcha_config() -> Dict[str, str]:
    api_key = env("SAKURAFRP_CAPTCHA_API_KEY") or env("CAPTCHA_API_KEY")
    base = env("SAKURAFRP_CAPTCHA_API_BASE") or env("CAPTCHA_API_BASE") or DEFAULT_CAPTCHA_BASE
    model = env("SAKURAFRP_CAPTCHA_MODEL") or env("CAPTCHA_MODEL") or DEFAULT_CAPTCHA_MODEL
    base = base.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SafeError("验证码 API 地址须为 https:// 开头的完整 URL")
    if not model:
        raise SafeError("验证码模型名称无效")
    return {"api_key": api_key, "base": base, "model": model}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            raise SafeError("账号行缺少分隔符；格式为 用户名或邮箱|密码")
        username, password = text.split("|", 1)
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise SafeError("用户名/邮箱或密码为空")
        if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
            raise SafeError("账号行含控制字符")
        accounts.append({"username": username, "password": password})
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("SAKURAFRP_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("SAKURAFRP_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("username") or env("SAKURAFRP_USERNAME")
    password = env("password") or env("SAKURAFRP_PASSWORD")
    if username and password:
        if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
            raise SafeError("兼容账号变量含控制字符")
        return [{"username": username, "password": password}]
    raise SafeError(
        "未配置 SAKURAFRP_ACCOUNTS；请按每个非空行 用户名或邮箱|密码 填写"
        "（或同时设置兼容变量 username 与 password）"
    )


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("name", "nickname", "username", "display_name", "displayName", "id"):
        value = payload.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            text = compact(value, 64)
            if text:
                return text
    return ""


def sign_status_text(user_info: Dict[str, Any]) -> Tuple[bool, str]:
    sign_info = user_info.get("sign") if isinstance(user_info.get("sign"), dict) else {}
    signed = bool(sign_info.get("signed"))
    days = sign_info.get("days", "?")
    if signed:
        return True, "今日已签到（连续 {} 天）".format(days)
    return False, "今日尚未签到"


def classify_sign_result(payload: Any) -> Tuple[str, str]:
    if isinstance(payload, str):
        text = compact(payload, 120)
        if text:
            return "success", "签到成功（{}）".format(text)
        return "success", "签到成功（接口返回文本回执）"
    if not isinstance(payload, dict):
        return "failure", "签到响应无法解析"
    if payload.get("status") == "success" or payload.get("code") == 0:
        message = ""
        for key in ("message", "msg", "data"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                message = compact(value, 120)
                break
        return "success", "签到成功" + ("（{}）".format(message) if message else "")
    return "failure", "签到业务失败"


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def display(self) -> str:
        return self.identity or "账号{}".format(self.number)

    def stage(self, number: int, name: str, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.display(), number, name))
        state, detail = "failure", "操作未完成"
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
                    self.display(),
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def finish(self) -> None:
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.display(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


# ── GeeTest v3（内联自上游 geetest_crack.py，MIT）──────────────────────────
class GeeTestCrack:
    def __init__(self, gt: str, challenge: str, timeout: float = 30.0, referer: str = "https://openid.13a.com/"):
        ensure_live_deps()
        serialization = _crypto["serialization"]
        PKCS1v15 = _crypto["PKCS1v15"]
        self.pic_path = None
        self.s = None
        self.c = None
        self.referer = referer
        self.debug = False
        self.last_get_type = None
        self.last_get_c_s = None
        self.last_ajax = None
        self.last_pic = None
        self.last_validate = None
        self.fullpage_host = "https://api.geevisit.com"
        self.type_api_host = "https://api.geetest.com"
        self.static_host = "https://static.geetest.com"
        self.get_php_host = "https://api.geetest.com"
        self.ajax_host = "https://api.geevisit.com"
        self.session = _httpx.Client(http2=True, timeout=timeout)
        self.session.headers = {
            "User-Agent": COMMON_HEADERS["user-agent"],
            "Referer": self.referer,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Sec-CH-UA": '"Chromium";v="145", "Not:A-Brand";v="99"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
        }
        self.gt = gt
        self.challenge = challenge

        # 生成随机 AES 密钥
        self.aeskey = "".join(
            f"{int((1 + random.random()) * 65536):04x}"[1:] for _ in range(4)
        )

        # GeeTest RSA 公钥 (固定)
        public_key_pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDB45NNFhRGWzMFPn9I7k7IexS5\n"
            "XviJR3E9Je7L/350x5d9AtwdlFH3ndXRwQwprLaptNb7fQoCebZxnhdyVl8Jr2J3\n"
            "FZGSIa75GJnK4IwNaG10iyCjYDviMYymvCtZcGWSqSGdC/Bcn2UCOiHSMwgHJSrg\n"
            "Bm1Zzu+l8nSOqAurgQIDAQAB\n"
            "-----END PUBLIC KEY-----"
        )
        self.public_key = serialization.load_pem_public_key(public_key_pem.encode())
        self.enc_key = self.public_key.encrypt(self.aeskey.encode(), PKCS1v15()).hex()
        self.mouse_path = list(DEFAULT_MOUSE_PATH)

    # ── 编码工具 ──────────────────────────────────────────────

    @staticmethod
    def encode(input_bytes: list) -> str:
        """GeeTest 自定义 base64 编码"""
        def get_char_from_index(index):
            char_table = (
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()"
            )
            return char_table[index] if 0 <= index < len(char_table) else "."

        def transform_value(value, bit_mask):
            result = 0
            for r in range(23, -1, -1):
                if (bit_mask >> r) & 1:
                    result = (result << 1) + ((value >> r) & 1)
            return result

        encoded_string = ""
        pad = ""
        input_length = len(input_bytes)
        for i in range(0, input_length, 3):
            chunk_length = min(3, input_length - i)
            chunk = input_bytes[i : i + chunk_length]
            if chunk_length == 3:
                value = (chunk[0] << 16) + (chunk[1] << 8) + chunk[2]
                encoded_string += (
                    get_char_from_index(transform_value(value, 7274496))
                    + get_char_from_index(transform_value(value, 9483264))
                    + get_char_from_index(transform_value(value, 19220))
                    + get_char_from_index(transform_value(value, 235))
                )
            elif chunk_length == 2:
                value = (chunk[0] << 16) + (chunk[1] << 8)
                encoded_string += (
                    get_char_from_index(transform_value(value, 7274496))
                    + get_char_from_index(transform_value(value, 9483264))
                    + get_char_from_index(transform_value(value, 19220))
                )
                pad = "."
            elif chunk_length == 1:
                value = chunk[0] << 16
                encoded_string += (
                    get_char_from_index(transform_value(value, 7274496))
                    + get_char_from_index(transform_value(value, 9483264))
                )
                pad = ".."
        return encoded_string + pad

    @staticmethod
    def md5(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    @staticmethod
    def encode_mouse_path(path: list, c: list, s: str) -> str:
        """编码鼠标轨迹为 GeeTest 格式"""

        def preprocess(path: list):
            def BFIQ(e):
                t = 32767
                if not isinstance(e, int):
                    return e
                if t < e:
                    e = t
                elif e < -t:
                    e = -t
                return round(e)

            def BGAB(e):
                t = ""
                n = 0
                while n < len(e) and not t:
                    if e[n]:
                        t = e[n][4]
                    n += 1
                if not t:
                    return e
                r = ""
                i = ["mouse", "touch", "pointer", "MSPointer"]
                for s in range(len(i)):
                    if t.startswith(i[s]):
                        r = i[s]
                _ = list(e)
                for a in range(len(_) - 1, -1, -1):
                    item = _[a]
                    etype = item[0]
                    if etype in ["move", "down", "up"]:
                        value = item[4] or ""
                        if not value.startswith(r):
                            _.pop(a)
                return _

            t = 0
            n = 0
            r = []
            s_val = 0
            if len(path) <= 0:
                return []
            o = None
            _ = None
            a = BGAB(path)
            c_len = len(a)
            for l in range(0 if c_len < 300 else c_len - 300, c_len):
                u = a[l]
                h = u[0]
                if h in ["down", "move", "up", "scroll"]:
                    if not o:
                        o = u
                    _ = u
                    r.append([h, [u[1] - t, u[2] - n], BFIQ(u[3] - s_val if s_val else s_val)])
                    t = u[1]
                    n = u[2]
                    s_val = u[3]
                elif h in ["blur", "focus", "unload"]:
                    r.append([h, BFIQ(u[1] - s_val if s_val else s_val)])
                    s_val = u[1]
            return r

        def process(prepared_path: list):
            h = {
                "move": 0, "down": 1, "up": 2, "scroll": 3,
                "focus": 4, "blur": 5, "unload": 6, "unknown": 7,
            }

            def p(e, t):
                n = bin(e)[2:]
                r = ""
                i = len(n) + 1
                while i <= t:
                    i += 1
                    r += "0"
                return r + n

            def d(e):
                t = []
                n = len(e)
                r = 0
                while r < n:
                    i = e[r]
                    s = 0
                    while True:
                        if s >= 16:
                            break
                        o = r + s + 1
                        if o >= n:
                            break
                        if e[o] != i:
                            break
                        s += 1
                    r += 1 + s
                    _ = h[i]
                    if s != 0:
                        t.append(_ | 8)
                        t.append(s - 1)
                    else:
                        t.append(_)
                a = p(n | 32768, 16)
                c = ""
                for l in range(len(t)):
                    c += p(t[l], 4)
                return a + c

            def g(e, tt):
                def temp1(e1):
                    n = len(e1)
                    r = 0
                    i = []
                    while r < n:
                        s = 1
                        o = e1[r]
                        _ = abs(o)
                        while True:
                            if n <= r + s:
                                break
                            if e1[r + s] != o:
                                break
                            if (_ >= 127) or (s >= 127):
                                break
                            s += 1
                        if s > 1:
                            i.append((49152 if o < 0 else 32768) | s << 7 | _)
                        else:
                            i.append(o)
                        r += s
                    return i

                e = temp1(e)
                r = []
                i = []

                def n(e, t):
                    return 0 if e == 0 else math.log(e) / math.log(t)

                for temp in e:
                    t = math.ceil(n(abs(temp) + 1, 16))
                    if t == 0:
                        t = 1
                    r.append(p(t - 1, 2))
                    i.append(p(abs(temp), t * 4))

                s = "".join(r)
                o = "".join(i)

                def temp2(t):
                    return t != 0 and t >> 15 != 1

                def temp3(e1):
                    n = []
                    for r in range(len(e1)):
                        if temp2(e1[r]):
                            n.append("1" if e1[r] < 0 else "0")
                    return "".join(n)

                if tt:
                    n_str = temp3(e)
                else:
                    n_str = ""
                return p(len(e) | 32768, 16) + s + o + n_str

            def u(e):
                t = ""
                n = len(e) // 6
                charset = "()*,-./0123456789:?@ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~"
                for r in range(n):
                    t += charset[int(e[6 * r : 6 * (r + 1)], 2)]
                return t

            t = []
            n = []
            r = []
            i = []
            for a in range(len(prepared_path)):
                _ = prepared_path[a]
                a_len = len(_)
                t.append(_[0])
                n.append(_[1] if a_len == 2 else _[2])
                if a_len == 3:
                    r.append(_[1][0])
                    i.append(_[1][1])
            c = d(t) + g(n, False) + g(r, True) + g(i, True)
            l = len(c)
            if l % 6 != 0:
                c += p(0, 6 - l % 6)
            return u(c)

        def postprocess(e, t, n):
            i = 0
            s = e
            o = t[0]
            _ = t[2]
            a = t[4]
            while True:
                r = n[i : i + 2]
                if not r:
                    break
                i += 2
                c = int(r, 16)
                l = chr(c)
                u = (o * c * c + _ * c + a) % len(e)
                s = s[:u] + l + s[u:]
            return s

        return postprocess(process(preprocess(path)), c, s)

    def aes_encrypt(self, content: str) -> bytes:
        Cipher = _crypto["Cipher"]
        algorithms = _crypto["algorithms"]
        modes = _crypto["modes"]
        padding = _crypto["padding"]
        cipher = Cipher(
            algorithms.AES(self.aeskey.encode()), modes.CBC(b"0000000000000000")
        )
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(content.encode()) + padder.finalize()
        return encryptor.update(padded_data) + encryptor.finalize()

    # ── GeeTest 协议流程 ─────────────────────────────────────

    def get_type(self) -> dict:
        params = {
            "gt": self.gt,
            "callback": "geetest_" + str(int(round(time.time() * 1000))),
        }
        url = self._build_url("https://api.geetest.com/gettype.php", params)
        self._debug_request("get_type", url)
        resp = self.session.get(url)
        parsed = self._parse_jsonp(resp.text)
        self._debug_response("get_type", parsed)
        self.last_get_type = parsed
        return parsed["data"]

    def get_c_s(self):
        """获取验证码配置和加密参数 c, s"""
        o = {
            "gt": self.gt,
            "challenge": self.challenge,
            "offline": False,
            "new_captcha": True,
            "product": "float",
            "width": "100%",
            "https": True,
            "protocol": "https://",
        }
        o.update(self.get_type())
        o.update(
            {
                "cc": 16,
                "ww": True,
                "i": "-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1!!-1",
            }
        )
        o = json.dumps(o, separators=(",", ":"))
        ct = self.aes_encrypt(o)
        s = list(ct)
        i = self.encode(s)
        r = self.enc_key
        w = i + r
        params = {
            "gt": self.gt,
            "challenge": self.challenge,
            "lang": "zh-cn",
            "pt": 0,
            "client_type": "web",
            "callback": "geetest_" + str(int(round(time.time() * 1000))),
            "w": w,
        }
        url = self._build_url("https://api.geetest.com/get.php", params)
        self._debug_request("get_c_s", url)
        resp = self.session.get(url).text
        parsed = self._parse_jsonp(resp)
        self._debug_response("get_c_s", parsed)
        if "data" not in parsed:
            raise SafeError("GeeTest 配置获取失败")
        data = parsed["data"]
        self.last_get_c_s = data
        self._apply_geetest_hosts(data)
        self.c = data["c"]
        self.s = data["s"]
        return data["c"], data["s"]

    def _apply_geetest_hosts(self, data) -> None:
        if not isinstance(data, dict):
            return
        api_server = data.get("api_server")
        if isinstance(api_server, str) and api_server:
            api_server = api_server.strip().rstrip("/")
            if not api_server.startswith("http"):
                api_server = f"https://{api_server}"
            self.fullpage_host = api_server
            self.ajax_host = api_server
            self.get_php_host = api_server.replace("api.geevisit.com", "api.geetest.com")

        static_servers = data.get("static_servers")
        if isinstance(static_servers, list) and static_servers:
            server = static_servers[0]
            if isinstance(server, str) and server:
                server = server.rstrip("/")
                if not server.startswith("http"):
                    server = f"https://{server}"
                self.static_host = server

    def ajax(self):
        """第一轮交互: 模拟点击验证按钮"""
        def transform(e, t, n):
            if not t or not n:
                return e
            o = 0
            i = list(e)
            s = t[0]
            a = t[2]
            b = t[4]
            while o < len(n):
                r = n[o : o + 2]
                o += 2
                c = int(r, 16)
                l = chr(c)
                u = (s * c * c + a * c + b) % len(i)
                i.insert(u, l)
            return "".join(i)

        tt = transform(
            self.encode_mouse_path(self.mouse_path, self.c, self.s), self.c, self.s
        )
        rp = self.md5(self.gt + self.challenge + self.s)
        now = int(time.time() * 1000)
        temp1 = (
            """"lang":"zh-cn","type":"fullpage","tt":"%s","light":"DIV_0","s":"c7c3e21112fe4f741921cb3e4ff9f7cb","h":"321f9af1e098233dbd03f250fd2b5e21","hh":"39bd9cad9e425c3a8f51610fd506e3b3","hi":"09eb21b3ae9542a9bc1e8b63b3d9a467","vip_order":-1,"ct":-1,"ep":{"v":"9.1.9-dbjg5z","te":false,"me":true,"ven":"Google Inc. (Intel)","ren":"ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x0000A7A0) Direct3D11 vs_5_0 ps_5_0, D3D11)","fp":["scroll",0,1602,%d,null],"lp":["up",386,217,%d,"pointerup"],"em":{"ph":0,"cp":0,"ek":"11","wd":1,"nt":0,"si":0,"sc":0},"tm":{"a":%d,"b":%d,"c":%d,"d":0,"e":0,"f":%d,"g":%d,"h":%d,"i":%d,"j":%d,"k":%d,"l":%d,"m":%d,"n":%d,"o":%d,"p":%d,"q":%d,"r":%d,"s":%d,"t":%d,"u":%d},"dnf":"dnf","by":0},"passtime":1600,"rp":"%s","""
            % (tt, now - 5000, now - 3000, now - 8000, now - 7970, now - 7960, now - 8000, now - 8000, now - 8000, now - 7990, now - 7880, now - 7990, now - 7880, now - 7970, now - 7968, now - 7950, now - 7400, now - 7400, now - 5000, now - 4000, now - 4000, now - 4000, rp)
        )
        r = "{" + temp1 + '"captcha_token":"1198034057","du6o":"eyjf7nne"}'
        ct = self.aes_encrypt(r)
        s = [byte for byte in ct]
        w = self.encode(s)
        params = {
            "gt": self.gt,
            "challenge": self.challenge,
            "lang": "zh-cn",
            "pt": 0,
            "client_type": "web",
            "callback": "geetest_" + str(int(round(time.time() * 1000))),
            "w": w,
        }
        url = self._build_url(f"{self.ajax_host}/ajax.php", params)
        self._debug_request("ajax", url)
        resp = self.session.get(url).text
        parsed = self._parse_jsonp(resp)
        self._debug_response("ajax", parsed)
        if "data" not in parsed:
            raise SafeError("GeeTest 交互失败")
        self.last_ajax = parsed["data"]
        self.last_validate = parsed["data"].get("validate")
        return parsed["data"]

    def _build_url(self, base_url: str, params: dict) -> str:
        normalized = {}
        for key, value in params.items():
            if isinstance(value, bool):
                normalized[key] = "true" if value else "false"
            else:
                normalized[key] = value
        return f"{base_url}?{urlencode(normalized)}"

    def _debug_request(self, label: str, url: str) -> None:
        if not self.debug:
            return
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        redacted = {}
        for key, value in query.items():
            if key == "w":
                redacted[key] = f"{value[:32]}...({len(value)})"
            else:
                redacted[key] = value
        print(f"[GeeTest:{label}] request {parsed.scheme}://{parsed.netloc}{parsed.path}")
        print(f"[GeeTest:{label}] params {json.dumps(redacted, ensure_ascii=False)}")

    def _debug_response(self, label: str, parsed: dict) -> None:
        if not self.debug:
            return
        if isinstance(parsed, dict):
            keys = sorted(parsed.keys())
            print(f"[GeeTest:{label}] response keys {keys}")
            if "status" in parsed:
                print(f"[GeeTest:{label}] status {parsed.get('status')}")
            if "error_code" in parsed or "error" in parsed:
                print(f"[GeeTest:{label}] error {json.dumps({k: parsed.get(k) for k in ['error', 'error_code', 'user_error'] if k in parsed}, ensure_ascii=False)}")
            if "data" in parsed and isinstance(parsed['data'], dict):
                print(f"[GeeTest:{label}] data keys {sorted(parsed['data'].keys())}")

    @staticmethod
    def _parse_jsonp(text: str) -> dict:
        """解析 JSONP 响应，提取 JSON 对象"""
        # JSONP 格式: callback({...})
        left = text.find("(")
        right = text.rfind(")")
        if left != -1 and right != -1:
            return json.loads(text[left + 1 : right])
        return json.loads(text)

    def get_pic(self, retry: int = 0):
        """获取验证码图片，返回 (类型, 图片URL)"""
        params = {
            "type": "click",
            "gt": self.gt,
            "challenge": self.challenge,
            "lang": "zh-cn",
            "callback": "geetest_" + str(int(round(time.time() * 1000))),
        }
        if retry == 0:
            url = f"{self.get_php_host}/get.php"
            params.update(
                {
                    "is_next": "true",
                    "https": True,
                    "protocol": "https://",
                    "offline": False,
                    "product": "float",
                    "api_server": self.ajax_host.removeprefix("https://"),
                    "isPC": True,
                    "autoReset": True,
                    "width": "100%",
                }
            )
        else:
            url = "https://api.geetest.com/refresh.php"
        request_url = self._build_url(url, params)
        self._debug_request(f"get_pic[{retry}]", request_url)
        resp = self.session.get(request_url).text
        parsed = self._parse_jsonp(resp)
        self._debug_response(f"get_pic[{retry}]", parsed)
        self.last_pic = parsed
        if "data" not in parsed:
            if "pic" in parsed:
                data = parsed
            else:
                raise SafeError("GeeTest 图片获取失败")
        else:
            data = parsed["data"]
        self._apply_geetest_hosts(data)
        self.pic_path = data["pic"]
        pic_url = "https://" + data["image_servers"][0][:-1] + data["pic"]
        return data["pic_type"], pic_url

    def verify(self, points: list) -> dict:
        """
        提交验证码点击结果
        points: 格式为 ["1_1", "2_3"] 的列表 (col_row)
        返回验证结果 dict
        """
        u = self.enc_key
        now = int(time.time() * 1000)
        o = {
            "lang": "zh-cn",
            "passtime": 1600,
            "a": ",".join(points),
            "pic": self.pic_path,
            "tt": self.encode_mouse_path(self.mouse_path, self.c, self.s),
            "ep": {
                "ca": [
                    {"x": 524, "y": 209, "t": 0, "dt": 1819},
                    {"x": 558, "y": 299, "t": 0, "dt": 428},
                    {"x": 563, "y": 95, "t": 0, "dt": 952},
                    {"x": 670, "y": 407, "t": 3, "dt": 892},
                ],
                "v": "3.1.2",
                "$_FG": False,
                "me": True,
                "tm": {
                    "a": now - 5000,
                    "b": 0, "c": 0, "d": 0, "e": 0,
                    "f": now - 4994, "g": now - 4994, "h": now - 4994,
                    "i": now - 4994, "j": now - 4992,
                    "k": 0,
                    "l": now - 4990, "m": now - 4959, "n": now - 4958,
                    "o": now - 4952, "p": now - 4905, "q": now - 2598,
                    "r": now - 2598, "s": now - 1509, "t": now - 1509, "u": now - 1509,
                },
            },
            "h9s9": "1816378497",
        }
        o["rp"] = self.md5(self.gt + self.challenge + str(o["passtime"]))
        o = json.dumps(o, separators=(",", ":"))
        ct = self.aes_encrypt(o)
        s = [byte for byte in ct]
        p = self.encode(s)
        w = p + u
        params = {
            "gt": self.gt,
            "challenge": self.challenge,
            "lang": "zh-cn",
            "pt": 0,
            "client_type": "web",
            "w": w,
        }
        resp = self.session.get(self._build_url(f"{self.ajax_host}/ajax.php", params)).text
        return self._parse_jsonp(resp)

    def close(self):
        self.session.close()



# ── 业务 HTTP / 验证码识别 ──────────────────────────────────────────────────


def create_client(timeout: float, follow_redirects: bool = False):
    ensure_live_deps()
    return _httpx.Client(
        follow_redirects=follow_redirects,
        timeout=timeout,
        headers=COMMON_HEADERS,
    )


def prime_openid_session(client, max_steps: int = 10) -> None:
    resp = client.get("https://www.natfrp.com/cgi/user/login")
    step = 0
    while resp.is_redirect and step < max_steps:
        location = resp.headers.get("location")
        if not location:
            break
        next_url = urljoin(str(resp.url), location)
        referer = str(resp.url)
        resp = client.get(next_url, headers={"referer": referer})
        step += 1


def follow_openid_redirect(client, max_steps: int = 10) -> None:
    resp = client.get(
        "https://openid.13a.com/redirect",
        headers={"referer": "https://openid.13a.com/login"},
    )
    redirect_steps = 0
    while resp.is_redirect and redirect_steps < max_steps:
        location = resp.headers.get("location")
        if not location:
            break
        next_url = urljoin(str(resp.url), location)
        referer = str(resp.url)
        resp = client.get(next_url, headers={"referer": referer})
        redirect_steps += 1


def strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        return text[7:-3].strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    return text


def extract_message_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part).strip()
    return ""


def call_captcha_ai(image_url: str, pic_type: str, captcha: Dict[str, str], timeout: float) -> list:
    ensure_live_deps()
    if pic_type == "nine":
        prompt = (
            "这是一个九宫格验证码。请按从左到右、从上到下的顺序识别每个格子里的物品名称，"
            "最后识别左下角的参考图。输出格式为JSON："
            '{"1":"名称", "2":"名称", ..., "10":"参考图名称"}。'
            "名称要简洁，参考图名称必须是九宫格里已有的名称。若有类似物品（如气球与热气球），请统一名称。"
            "只输出JSON，不要其他文字。"
        )
    else:
        prompt = (
            "这是一个点选验证码。请识别图中需要点击的目标文字或图标，"
            "并返回每个目标的大致坐标位置。输出格式为JSON列表："
            '[{"x": 100, "y": 200}, ...]。坐标原点在左上角。'
            "只输出JSON，不要其他文字。"
        )
    body = {
        "model": captcha["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "stream": False,
    }
    url = "{}/chat/completions".format(captcha["base"])
    headers = {
        "Authorization": "Bearer {}".format(captcha["api_key"]),
        "Content-Type": "application/json",
        "User-Agent": COMMON_HEADERS["user-agent"],
    }
    try:
        with _httpx.Client(timeout=timeout) as ai_client:
            resp = ai_client.post(url, headers=headers, json=body)
    except Exception as exc:
        raise SafeError("验证码识别接口网络失败") from exc
    if resp.status_code >= 400:
        raise SafeError("验证码识别接口 HTTP {}".format(resp.status_code))
    try:
        payload = resp.json()
    except Exception as exc:
        raise SafeError("验证码识别响应不是 JSON") from exc
    result_text = strip_json_fence(extract_message_content(payload))
    if not result_text:
        return []
    try:
        recognition = json.loads(result_text)
    except json.JSONDecodeError:
        return []
    if pic_type == "nine":
        if not isinstance(recognition, dict):
            return []
        target_name = compact(recognition.get("10", ""), 64)
        if not target_name:
            return []
        points = []
        for i in range(9):
            position = str(i + 1)
            item_name = compact(recognition.get(position, ""), 64)
            if item_name == target_name:
                row = i // 3 + 1
                col = i % 3 + 1
                points.append("{}_{}".format(col, row))
        return points
    coords = recognition
    if isinstance(coords, dict):
        coords = coords.get("coordinates", coords.get("points", []))
    if not isinstance(coords, list):
        return []
    points = []
    for item in coords:
        if isinstance(item, dict):
            if "x" in item and "y" in item:
                points.append("{}_{}".format(item["x"], item["y"]))
            elif "point_2d" in item and isinstance(item["point_2d"], (list, tuple)):
                pt = item["point_2d"]
                points.append("{}_{}".format(pt[0], pt[1]))
    return points


def solve_click_captcha(
    crack: GeeTestCrack,
    captcha: Dict[str, str],
    timeout: float,
    max_retries: int,
) -> str:
    for attempt in range(1, max_retries + 1):
        log("验证码尝试 {}/{}".format(attempt, max_retries))
        pic_type, pic_url = crack.get_pic(0 if attempt == 1 else attempt)
        points = call_captcha_ai(pic_url, pic_type, captcha, timeout)
        if not points:
            time.sleep(2)
            continue
        result = crack.verify(points)
        data = result.get("data") if isinstance(result, dict) else None
        if (
            isinstance(result, dict)
            and result.get("status") == "success"
            and isinstance(data, dict)
            and data.get("result") == "success"
            and data.get("validate")
        ):
            return str(data["validate"])
        time.sleep(2)
    raise SafeError("验证码重试均失败")


def login_account(
    username: str,
    password: str,
    captcha: Dict[str, str],
    timeout: float,
    max_retries: int,
):
    client = create_client(timeout, follow_redirects=False)
    crack = None
    try:
        prime_openid_session(client)
        resp = client.get(
            "https://openid.13a.com/cgi/captcha?login",
            headers={"referer": "https://openid.13a.com/login", **OPENID_AJAX_HEADERS},
        )
        try:
            captcha_data = resp.json()
        except Exception as exc:
            raise SafeError("登录验证码配置响应无效") from exc
        if not captcha_data.get("success"):
            raise SafeError("获取登录验证码配置失败")
        message = captcha_data.get("message") or {}
        gt = message.get("gt")
        challenge = message.get("challenge")
        if not gt or not challenge:
            raise SafeError("登录验证码参数缺失")
        crack = GeeTestCrack(gt, challenge, timeout, referer="https://openid.13a.com/")
        crack.get_type()
        crack.get_c_s()
        ajax_result = crack.ajax()
        validate = ajax_result.get("validate")
        if ajax_result.get("result") == "click":
            validate = solve_click_captcha(crack, captcha, timeout, max_retries)
        elif not validate:
            raise SafeError("登录验证码未返回校验令牌")
        login_data = {
            "username": username,
            "password": password,
            "geetest_id": challenge,
            "geetest_challenge": challenge,
            "geetest_validate": validate,
            "geetest_seccode": "{}|jordan".format(validate),
        }
        resp = client.post(
            "https://openid.13a.com/cgi/password/login",
            data=login_data,
            headers={
                "referer": "https://openid.13a.com/login",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                **OPENID_AJAX_HEADERS,
            },
        )
        if resp.status_code not in (200, 302):
            raise SafeError("登录请求失败（HTTP {}）".format(resp.status_code))
        follow_openid_redirect(client)
        resp = client.get("https://www.natfrp.com/cgi/v4/user/info")
        try:
            user_info = resp.json()
        except Exception as exc:
            raise SafeError("登录后用户信息响应无效") from exc
        if not isinstance(user_info, dict) or ("name" not in user_info and "id" not in user_info):
            raise SafeError("登录验证失败（未返回公开身份）")
        return client, user_info
    except SafeError:
        client.close()
        raise
    except Exception as exc:
        client.close()
        raise SafeError("登录流程失败") from exc
    finally:
        if crack is not None:
            crack.close()


def fetch_user_info(client) -> Dict[str, Any]:
    resp = client.get("https://www.natfrp.com/cgi/v4/user/info")
    try:
        data = resp.json()
    except Exception as exc:
        raise SafeError("用户信息响应无效") from exc
    if not isinstance(data, dict):
        raise SafeError("用户信息不是对象")
    return data


def perform_sign(
    client,
    captcha: Dict[str, str],
    timeout: float,
    max_retries: int,
) -> Tuple[str, str]:
    user_info = fetch_user_info(client)
    already, detail = sign_status_text(user_info)
    if already:
        return "alreadyComplete", detail
    resp = client.get("https://www.natfrp.com/cgi/v4/user/sign?gt")
    try:
        geetest_data = resp.json()
    except Exception:
        match = re.search(r"\((.+)\)", resp.text, re.DOTALL)
        if not match:
            raise SafeError("签到验证码配置无法解析")
        try:
            geetest_data = json.loads(match.group(1))
        except Exception as exc:
            raise SafeError("签到验证码配置不是 JSON") from exc
    if not isinstance(geetest_data, dict) or "gt" not in geetest_data or "challenge" not in geetest_data:
        raise SafeError("签到验证码参数缺失")
    gt = geetest_data["gt"]
    challenge = geetest_data["challenge"]
    crack = GeeTestCrack(gt, challenge, timeout, referer="https://openid.13a.com/")
    try:
        crack.get_type()
        crack.get_c_s()
        crack.ajax()
        validate = solve_click_captcha(crack, captcha, timeout, max_retries)
    finally:
        crack.close()
    sign_data = {
        "geetest_challenge": challenge,
        "geetest_validate": validate,
        "geetest_seccode": "{}|jordan".format(validate),
    }
    sign_headers = dict(COMMON_HEADERS)
    sign_headers["content-type"] = "application/x-www-form-urlencoded"
    sign_headers["referer"] = "https://www.natfrp.com/user/"
    resp = client.post(
        "https://www.natfrp.com/cgi/v4/user/sign",
        data=sign_data,
        headers=sign_headers,
    )
    try:
        sign_result = resp.json()
    except Exception as exc:
        raise SafeError("签到响应不是 JSON") from exc
    return classify_sign_result(sign_result)


def run_account(
    runner: AccountRunner,
    username: str,
    password: str,
    captcha: Dict[str, str],
    timeout: float,
    max_retries: int,
    dry_run: bool,
) -> None:
    if dry_run:
        def dry_config():
            return (
                "success",
                "配置已校验（用户名已提供，密码已提供，验证码 Key 已提供），未联网",
                None,
            )

        runner.stage(1, "参数预检", dry_config)

        def skip_login():
            return "skipped", "断网预演：不请求登录接口", None

        def skip_sign():
            return "skipped", "断网预演：不请求签到接口", None

        def skip_verify():
            return "skipped", "断网预演：不复核签到状态", None

        runner.stage(2, "登录", skip_login)
        runner.stage(3, "签到", skip_sign)
        runner.stage(4, "结果复核", skip_verify)
        runner.status = "dry-run"
        log("账号 {}：DRY_RUN_OK，仅验证配置，未联网".format(runner.display()))
        return

    ensure_live_deps()
    client = None

    def do_login():
        nonlocal client
        client, user_info = login_account(username, password, captcha, timeout, max_retries)
        identity = extract_identity(user_info)
        if identity:
            runner.identity = identity
            log("账号公开身份：{}".format(identity))
        return "success", "登录成功（身份已核对）", user_info

    runner.stage(1, "登录", do_login)

    def do_sign():
        state, detail = perform_sign(client, captcha, timeout, max_retries)
        return state, detail, state

    sign_state = runner.stage(2, "签到", do_sign)

    def do_verify():
        info = fetch_user_info(client)
        identity = extract_identity(info)
        if identity:
            runner.identity = identity
            log("账号公开身份：{}".format(identity))
        already, detail = sign_status_text(info)
        if sign_state == "alreadyComplete":
            if already:
                return "alreadyComplete", detail, info
            return "failure", "已签到状态复核失败", info
        if already:
            return "success", "签到后状态已复核为已签到", info
        if sign_state == "success":
            return "success", "签到业务成功（状态字段可能延迟）", info
        return "failure", "签到后状态未确认", info

    verify_state = runner.stage(3, "结果复核", do_verify)
    if client is not None:
        client.close()
    if sign_state == "alreadyComplete" or verify_state == "alreadyComplete":
        runner.status = "alreadyComplete"
    elif sign_state == "success" and verify_state == "success":
        runner.status = "success"
    else:
        runner.status = "failure"
        raise SafeError("签到未通过业务成功校验")


PY_NOTIFY_RUNNER = """
import importlib.util
import json
import sys
from pathlib import Path
payload = json.load(sys.stdin)
sys.path.insert(0, payload['directory'])
spec = importlib.util.find_spec('notify')
if spec is None and payload.get('path'):
    path = Path(payload['path'])
    spec = importlib.util.spec_from_file_location('notify', path)
if spec is None or spec.loader is None:
    raise SystemExit(1)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
send = getattr(module, 'send', None) or getattr(module, 'notify', None)
if send is None:
    raise SystemExit(1)
send(payload['title'], payload['body'])
"""

JS_NOTIFY_RUNNER = """
const fs = require('fs');
let raw = '';
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(raw);
  Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
    .then(result => process.exit(result === false ? 1 : 0))
    .catch(() => process.exit(1));
});
"""


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "sakurafrp_auto_signin.py",
        "candidate.py",
        "auto_signin_http.py",
        "scripts/sakurafrp_auto_signin.py",
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
    directory = env("QINGLONG_NOTIFY_DIR")
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
    dry_setting = env("SAKURAFRP_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    max_retries = DEFAULT_MAX_RETRIES
    captcha = {"api_key": "", "base": DEFAULT_CAPTCHA_BASE, "model": DEFAULT_CAPTCHA_MODEL}
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("SAKURAFRP_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        max_retries = resolve_retries()
        captcha = resolve_captcha_config()
        accounts_data = load_accounts()
        if not captcha["api_key"]:
            raise SafeError(
                "未配置 SAKURAFRP_CAPTCHA_API_KEY（或兼容别名 CAPTCHA_API_KEY）"
            )
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；验证码重试：{}；模型：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                max_retries,
                captcha["model"],
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["username"],
                    item["password"],
                    captcha,
                    timeout,
                    max_retries,
                    dry_run,
                )
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        state: sum(a.status == state for a in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
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
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
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

