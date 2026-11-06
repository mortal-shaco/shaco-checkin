#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 今日校园辅导员签到
# cron: 0 21 * * *
#
# 来源：just-test-2021/CpdailyAutoSign-for-NAU index.py（MIT）
# https://github.com/just-test-2021/CpdailyAutoSign-for-NAU
# 提交：dbb8050d362192466d4815baea64f64b2a50e9fb
# 上游说明亦致谢 ZimoLoveShuang/auto-submit；本维护版移除其默认第三方登录/邮件服务。
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2021 just-test-2021
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
#
"""今日校园辅导员签到（校园圈 / campusphere）青龙维护版。

功能清点（相对上游 index.py + config_nau.yml）：
- 按学校全称查询 guest/tenant，解析 ids 登录地址与校园圈 host
- 使用学号/密码对学校统一身份认证做本机 HTTP 登录（已移除默认 zimo.wiki 模拟登录 API）
- 也可直接提供校园圈会话 Cookie，跳过密码登录
- 拉取当日未签到任务、详情，按配置填写定位/附加项/可选照片后提交签到
- 可选处理请假签到任务列表（CPDAILY_TASK_KIND=leave）
- 移除 Cookie/原始响应打印、无超时请求、第三方邮件与 Server酱直连
- 增加逐行多账号、CPDAILY_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

CPDAILY_ACCOUNTS：每个非空行一个账号。推荐 JSON：
{"school":"南京审计大学","username":"学号","password":"密码",
 "lon":"118.619966","lat":"32.070899","address":"中国江苏省南京市浦口区…",
 "abnormalReason":"36.5","photo":""}
会话模式 JSON 使用 cookie（可含 host）：
{"school":"南京审计大学","cookie":"MOD_AUTH_CAS=…","host":"nau.campusphere.net",
 "lon":"…","lat":"…","address":"…","abnormalReason":"…"}
兼容管道格式（密码不得含 |）：
学校|学号|密码|经度|纬度|地址|异常原因
会话管道：session|学校|Cookie|经度|纬度|地址|异常原因 ，仅按前六个 | 拆分。
CPDAILY_EXTRA_DEFAULTS：附加题默认答案 JSON 数组，如
[{"title":"请填报体温","value":"其它"}]；题目需照片时在账号 photo 填本地可读路径。
CPDAILY_TASK_KIND：unsigned（默认）或 leave。
CPDAILY_DRY_RUN=1：完全断网预演。建议 Cron：0 21 * * *。
不打印密码、Cookie、Token、设备标识或原始响应。本脚本不发布帖子/评论/分享文字。
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
        _ql_notify_identities = ('c04cea4deb8400a4', 'scripts/task_c04cea4d.py', 'task_c04cea4d.py', 'task_c04cea4d')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import hashlib
import http.cookiejar
import json
import os
import random
import re
import shutil
import ssl
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "今日校园辅导员签到"
CATALOG_ID = "c04cea4deb8400a4"
TENANT_LIST = "https://mobile.campushoy.com/v6/config/guest/tenant/list"
TENANT_INFO = "https://mobile.campushoy.com/v6/config/guest/tenant/info"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
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
UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/83.0.4103.97 Safari/537.36"
)
UA_APP = (
    "Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 "
    "Safari/537.36 okhttp/3.12.4"
)
AES_CHARSET = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
DES_KEY = b"b3L26XNL"
DES_IV = b"\x01\x02\x03\x04\x05\x06\x07\x08"


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


def resolve_timeout() -> float:
    raw = env("CPDAILY_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("CPDAILY_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("CPDAILY_TIMEOUT 须在 5 到 120 秒之间")
    return value


def task_kind() -> str:
    kind = env("CPDAILY_TASK_KIND", "unsigned").lower() or "unsigned"
    if kind not in {"unsigned", "leave"}:
        raise SafeError("CPDAILY_TASK_KIND 仅允许 unsigned 或 leave")
    return kind


def load_extra_defaults() -> List[Dict[str, str]]:
    raw = env("CPDAILY_EXTRA_DEFAULTS")
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise SafeError("CPDAILY_EXTRA_DEFAULTS 须为 JSON 数组") from exc
    if not isinstance(payload, list):
        raise SafeError("CPDAILY_EXTRA_DEFAULTS 须为 JSON 数组")
    result: List[Dict[str, str]] = []
    for index, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            raise SafeError("附加题默认第 {} 项须为对象".format(index))
        title = str(item.get("title") or "").strip()
        value = str(item.get("value") or "").strip()
        if not title or not value:
            raise SafeError("附加题默认第 {} 项缺少 title 或 value".format(index))
        result.append({"title": title, "value": value})
    return result


# --- minimal DES CBC PKCS5 (Cpdaily-Extension) ---
def _des_permute(block: int, table: Tuple[int, ...], in_bits: int) -> int:
    out = 0
    for bit in table:
        out = (out << 1) | ((block >> (in_bits - bit)) & 1)
    return out


_IP = (
    58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
)
_FP = (
    40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
    38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
    36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25,
)
_E = (
    32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13,
    12, 13, 14, 15, 16, 17, 16, 17, 18, 19, 20, 21, 20, 21, 22, 23,
    24, 25, 24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1,
)
_P = (
    16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
    2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25,
)
_PC1 = (
    57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18, 10, 2,
    59, 51, 43, 35, 27, 19, 11, 3, 60, 52, 44, 36, 63, 55, 47, 39,
    31, 23, 15, 7, 62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37,
    29, 21, 13, 5, 28, 20, 12, 4,
)
_PC2 = (
    14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4,
    26, 8, 16, 7, 27, 20, 13, 2, 41, 52, 31, 37, 47, 55, 30, 40,
    51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32,
)
_SHIFTS = (1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1)
_SBOX = (
    (
        14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7,
        0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8,
        4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0,
        15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13,
    ),
    (
        15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10,
        3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5,
        0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15,
        13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9,
    ),
    (
        10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8,
        13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1,
        13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7,
        1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12,
    ),
    (
        7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15,
        13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9,
        10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4,
        3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14,
    ),
    (
        2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9,
        14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6,
        4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14,
        11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3,
    ),
    (
        12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11,
        10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8,
        9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6,
        4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13,
    ),
    (
        4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1,
        13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6,
        1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2,
        6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12,
    ),
    (
        13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7,
        1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2,
        7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8,
        2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11,
    ),
)


def _des_key_schedule(key: bytes) -> List[int]:
    key_int = int.from_bytes(key[:8], "big")
    key56 = _des_permute(key_int, _PC1, 64)
    c = (key56 >> 28) & 0xFFFFFFF
    d = key56 & 0xFFFFFFF
    subkeys: List[int] = []
    for shift in _SHIFTS:
        c = ((c << shift) | (c >> (28 - shift))) & 0xFFFFFFF
        d = ((d << shift) | (d >> (28 - shift))) & 0xFFFFFFF
        cd = (c << 28) | d
        subkeys.append(_des_permute(cd, _PC2, 56))
    return subkeys


def _des_f(right: int, subkey: int) -> int:
    expanded = _des_permute(right, _E, 32)
    xored = expanded ^ subkey
    s_out = 0
    for i in range(8):
        chunk = (xored >> (42 - 6 * i)) & 0x3F
        row = ((chunk & 0x20) >> 4) | (chunk & 0x01)
        col = (chunk >> 1) & 0x0F
        s_out = (s_out << 4) | _SBOX[i][row * 16 + col]
    return _des_permute(s_out, _P, 32)


def _des_block(block: bytes, subkeys: List[int]) -> bytes:
    value = _des_permute(int.from_bytes(block, "big"), _IP, 64)
    left = (value >> 32) & 0xFFFFFFFF
    right = value & 0xFFFFFFFF
    for subkey in subkeys:
        left, right = right, left ^ _des_f(right, subkey)
    pre = ((right & 0xFFFFFFFF) << 32) | (left & 0xFFFFFFFF)
    return _des_permute(pre, _FP, 64).to_bytes(8, "big")


def des_encrypt_cpdaily(plain: str) -> str:
    data = plain.encode("utf-8")
    pad_len = 8 - (len(data) % 8)
    data = data + bytes([pad_len] * pad_len)
    subkeys = _des_key_schedule(DES_KEY)
    prev = DES_IV
    out = bytearray()
    for offset in range(0, len(data), 8):
        block = bytes(a ^ b for a, b in zip(data[offset : offset + 8], prev))
        enc = _des_block(block, subkeys)
        out.extend(enc)
        prev = enc
    return base64.b64encode(out).decode("ascii")


def random_aes_string(length: int) -> str:
    return "".join(random.choice(AES_CHARSET) for _ in range(length))


def encrypt_cas_password(password: str, salt: str) -> str:
    if not salt or len(salt) != 16:
        raise SafeError("登录页密码盐值无效")
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        # 无 pycryptodome 时仅允许明文登录页（无 salt 场景）；有 salt 则要求依赖
        raise SafeError("学校登录启用了加密口令，请安装公开依赖 pycryptodome")
    plain = (random_aes_string(64) + password).encode("utf-8")
    cipher = AES.new(salt.encode("utf-8"), AES.MODE_CBC, random_aes_string(16).encode("utf-8"))
    return base64.b64encode(cipher.encrypt(pad(plain, AES.block_size, style="pkcs7"))).decode(
        "utf-8"
    )


class HttpSession:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )

    def set_cookie_header(self, cookie_header: str, host: str) -> None:
        text = cookie_header.strip()
        if text.lower().startswith("cookie:"):
            text = text.split(":", 1)[1].strip()
        for part in text.split(";"):
            item = part.strip()
            if not item or "=" not in item:
                continue
            name, value = item.split("=", 1)
            name, value = name.strip(), value.strip()
            if not name:
                continue
            cookie = http.cookiejar.Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=host,
                domain_specified=True,
                domain_initial_dot=host.startswith("."),
                path="/",
                path_specified=True,
                secure=True,
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            self.cookie_jar.set_cookie(cookie)

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
    ) -> Tuple[int, Dict[str, str], bytes, str]:
        current = url
        payload = data
        verb = method.upper()
        for _ in range(max_redirects + 1):
            req_headers = {
                "User-Agent": UA_WEB,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            if headers:
                req_headers.update(headers)
            request = urllib.request.Request(
                current, data=payload, headers=req_headers, method=verb
            )
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    status = getattr(response, "status", 200)
                    resp_headers = {k.lower(): v for k, v in response.headers.items()}
                    raw = response.read(MAX_BYTES + 1)
                    final_url = response.geturl()
            except urllib.error.HTTPError as error:
                status = error.code
                resp_headers = {k.lower(): v for k, v in (error.headers or {}).items()}
                try:
                    raw = error.read(MAX_BYTES + 1)
                except Exception:
                    raw = b""
                finally:
                    error.close()
                final_url = error.geturl() if hasattr(error, "geturl") else current
                if allow_redirects and status in {301, 302, 303, 307, 308}:
                    location = resp_headers.get("location")
                    if not location:
                        raise SafeError("登录重定向缺少 Location")
                    current = urllib.parse.urljoin(current, location)
                    if status in {301, 302, 303}:
                        verb = "GET"
                        payload = None
                    continue
            except Exception as exc:
                raise SafeError("网络、超时或连接失败") from exc
            if len(raw) > MAX_BYTES:
                raise SafeError("响应超过大小限制")
            if allow_redirects and status in {301, 302, 303, 307, 308}:
                location = resp_headers.get("location")
                if not location:
                    raise SafeError("重定向缺少 Location")
                current = urllib.parse.urljoin(final_url or current, location)
                if status in {301, 302, 303}:
                    verb = "GET"
                    payload = None
                continue
            return status, resp_headers, raw, final_url
        raise SafeError("重定向次数过多")


def parse_json_object(raw: bytes, label: str) -> Dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="replace")
        payload = json.loads(text)
    except Exception as exc:
        raise SafeError("{} 不是合法 JSON".format(label)) from exc
    if not isinstance(payload, dict):
        raise SafeError("{} JSON 不是对象".format(label))
    return payload


def html_input_value(html: str, name: str) -> str:
    patterns = [
        r'name=["\']' + re.escape(name) + r'["\'][^>]*value=["\']([^"\']*)["\']',
        r'value=["\']([^"\']*)["\'][^>]*name=["\']' + re.escape(name) + r'["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return match.group(1)
    return ""


def validate_account(account: Dict[str, Any]) -> Dict[str, Any]:
    school = str(account.get("school") or "").strip()
    if not school:
        raise SafeError("缺少学校全称 school")
    lon = str(account.get("lon") or account.get("longitude") or "").strip()
    lat = str(account.get("lat") or account.get("latitude") or "").strip()
    address = str(account.get("address") or "").strip()
    if not lon or not lat or not address:
        raise SafeError("缺少 lon/lat/address 定位字段")
    try:
        lon_f = float(lon)
        lat_f = float(lat)
    except ValueError as exc:
        raise SafeError("经纬度须为数字") from exc
    if not (-180.0 <= lon_f <= 180.0 and -90.0 <= lat_f <= 90.0):
        raise SafeError("经纬度超出有效范围")
    abnormal = str(account.get("abnormalReason") or account.get("abnormal") or "").strip()
    photo = str(account.get("photo") or "").strip()
    cookie = str(account.get("cookie") or account.get("session") or "").strip()
    host = str(account.get("host") or "").strip()
    username = str(account.get("username") or account.get("user") or "").strip()
    password = str(account.get("password") or account.get("passwd") or "").strip()
    if cookie:
        if len(cookie) < 8:
            raise SafeError("Cookie 过短，疑似无效")
        if any(ord(ch) < 32 for ch in cookie):
            raise SafeError("Cookie 含控制字符")
        mode = "cookie"
    else:
        if not username or not password:
            raise SafeError("缺少 username/password，或改用 cookie 会话模式")
        mode = "password"
    if photo and not Path(photo).is_file():
        raise SafeError("photo 路径不存在或不可读")
    return {
        "school": school,
        "username": username,
        "password": password,
        "cookie": cookie,
        "host": host,
        "lon": str(lon_f),
        "lat": str(lat_f),
        "address": address,
        "abnormalReason": abnormal,
        "photo": photo,
        "mode": mode,
    }


def parse_account_line(line: str, index: int) -> Dict[str, Any]:
    text = line.strip()
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise SafeError("账号 {} JSON 无法解析".format(index)) from exc
        if not isinstance(payload, dict):
            raise SafeError("账号 {} JSON 须为对象".format(index))
        return validate_account(payload)
    lowered = text.lower()
    if lowered.startswith("session|"):
        parts = text.split("|", 6)
        if len(parts) < 7:
            raise SafeError(
                "账号 {} 会话格式错误；应为 session|学校|Cookie|经度|纬度|地址|异常原因".format(
                    index
                )
            )
        return validate_account(
            {
                "school": parts[1],
                "cookie": parts[2],
                "lon": parts[3],
                "lat": parts[4],
                "address": parts[5],
                "abnormalReason": parts[6],
            }
        )
    parts = text.split("|", 6)
    if len(parts) < 7:
        raise SafeError(
            "账号 {} 格式错误；应为 学校|学号|密码|经度|纬度|地址|异常原因 或 JSON".format(
                index
            )
        )
    return validate_account(
        {
            "school": parts[0],
            "username": parts[1],
            "password": parts[2],
            "lon": parts[3],
            "lat": parts[4],
            "address": parts[5],
            "abnormalReason": parts[6],
        }
    )


def load_accounts() -> List[Dict[str, Any]]:
    raw = env("CPDAILY_ACCOUNTS")
    if not raw:
        # 兼容单账号拆分变量
        school = env("CPDAILY_SCHOOL")
        username = env("CPDAILY_USERNAME")
        password = env("CPDAILY_PASSWORD")
        cookie = env("CPDAILY_COOKIE")
        lon = env("CPDAILY_LON")
        lat = env("CPDAILY_LAT")
        address = env("CPDAILY_ADDRESS")
        abnormal = env("CPDAILY_ABNORMAL_REASON")
        photo = env("CPDAILY_PHOTO")
        host = env("CPDAILY_HOST")
        if cookie or username or password or school:
            return [
                validate_account(
                    {
                        "school": school,
                        "username": username,
                        "password": password,
                        "cookie": cookie,
                        "host": host,
                        "lon": lon,
                        "lat": lat,
                        "address": address,
                        "abnormalReason": abnormal,
                        "photo": photo,
                    }
                )
            ]
        raise SafeError(
            "未配置 CPDAILY_ACCOUNTS；请按每行一个账号填写 JSON 或管道格式；"
            "亦可使用单账号别名 CPDAILY_USERNAME/CPDAILY_PASSWORD 等"
        )
    accounts: List[Dict[str, Any]] = []
    for index, line in enumerate(raw.replace("\r\n", "\n").split("\n"), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text, index))
    if not accounts:
        raise SafeError("CPDAILY_ACCOUNTS 没有有效账号行")
    return accounts


def resolve_apis(session: HttpSession, school: str) -> Dict[str, str]:
    status, _, raw, _ = session.request(TENANT_LIST, headers={"Accept": "application/json"})
    if status != 200:
        raise SafeError("学校列表请求失败（HTTP {}）".format(status))
    payload = parse_json_object(raw, "学校列表")
    data = payload.get("data")
    if not isinstance(data, list):
        raise SafeError("学校列表缺少 data")
    matched = None
    for item in data:
        if isinstance(item, dict) and str(item.get("name") or "") == school:
            matched = item
            break
    if matched is None:
        raise SafeError("未找到学校全称，请核对今日校园租户名称")
    if str(matched.get("joinType") or "") == "NONE":
        raise SafeError("学校未接入今日校园或全称错误")
    school_id = matched.get("id")
    if school_id is None:
        raise SafeError("学校租户缺少 id")
    info_url = TENANT_INFO + "?" + urllib.parse.urlencode({"ids": school_id})
    status, _, raw, _ = session.request(info_url, headers={"Accept": "application/json"})
    if status != 200:
        raise SafeError("学校详情请求失败（HTTP {}）".format(status))
    info = parse_json_object(raw, "学校详情")
    rows = info.get("data")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise SafeError("学校详情缺少 data")
    row = rows[0]
    ids_url = str(row.get("idsUrl") or "").rstrip("/")
    amp_url = str(row.get("ampUrl") or "")
    amp_url2 = str(row.get("ampUrl2") or "")
    host = ""
    for candidate in (amp_url2, amp_url):
        lowered = candidate.lower()
        if "campusphere" in lowered or "cpdaily" in lowered:
            host = urllib.parse.urlparse(candidate).netloc
            scheme = urllib.parse.urlparse(candidate).scheme or "https"
            break
    if not ids_url or not host:
        raise SafeError("未能解析学校登录地址或校园圈 host")
    login_url = (
        ids_url
        + "/login?service="
        + urllib.parse.quote(scheme + "://" + host + "/portal/login", safe="")
    )
    return {"login-url": login_url, "host": host, "ids-url": ids_url}


def cas_login(session: HttpSession, login_url: str, username: str, password: str) -> None:
    status, _, raw, final_url = session.request(login_url, headers={"Accept": "text/html"})
    if status != 200:
        raise SafeError("打开登录页失败（HTTP {}）".format(status))
    html = raw.decode("utf-8", errors="replace")
    if "captcha" in html.lower() and re.search(r'id=["\']captcha', html, re.I):
        raise SafeError("学校登录需要验证码，请改用 cookie 会话模式")
    salt = html_input_value(html, "pwdEncryptSalt") or html_input_value(html, "pwdDefaultEncryptSalt")
    execution = html_input_value(html, "execution")
    lt = html_input_value(html, "lt")
    event_id = html_input_value(html, "_eventId") or "submit"
    form: Dict[str, str] = {
        "username": username,
        "_eventId": event_id,
    }
    if execution:
        form["execution"] = execution
    if lt:
        form["lt"] = lt
    if salt:
        form["password"] = encrypt_cas_password(password, salt)
    else:
        form["password"] = password
    # 常见附加字段
    for name in ("dllt", "cllt", "rmShown"):
        value = html_input_value(html, name)
        if value:
            form[name] = value
    body = urllib.parse.urlencode(form).encode("utf-8")
    post_url = final_url or login_url
    status, _, raw2, _ = session.request(
        post_url,
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": urllib.parse.urlparse(post_url).scheme
            + "://"
            + urllib.parse.urlparse(post_url).netloc,
            "Referer": post_url,
            "Accept": "text/html,application/xhtml+xml",
        },
        allow_redirects=True,
    )
    html2 = raw2.decode("utf-8", errors="replace")
    lowered = html2.lower()
    if status >= 400:
        raise SafeError("登录提交失败（HTTP {}）".format(status))
    if any(
        hint in html2
        for hint in ("用户名或密码错误", "密码错误", "账号或密码", "authentication failed")
    ) or ("name=\"password\"" in lowered and "login" in lowered and "portal" not in lowered):
        # 仍停在登录页通常表示失败
        if "execution" in lowered and "password" in lowered:
            raise SafeError("登录失败：账号或密码无效，或学校改用了不支持的登录流程")


def post_json(
    session: HttpSession,
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": UA_WEB,
    }
    if headers:
        req_headers.update(headers)
    status, _, raw, _ = session.request(url, method="POST", data=body, headers=req_headers)
    if status in (401, 403):
        raise SafeError("会话无效或已过期（HTTP {}）".format(status))
    if status != 200:
        raise SafeError("业务请求失败（HTTP {}）".format(status))
    return parse_json_object(raw, "业务响应")


def get_sign_task(
    session: HttpSession, host: str, kind: str
) -> Tuple[str, Dict[str, str]]:
    url = "https://{}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay".format(host)
    # 与上游一致：连续请求两次以建立 MOD_AUTH_CAS 相关会话
    post_json(session, url, {})
    payload = post_json(session, url, {})
    datas = payload.get("datas")
    if not isinstance(datas, dict):
        raise SafeError("签到任务响应缺少 datas")
    key = "leaveTasks" if kind == "leave" else "unSignedTasks"
    tasks = datas.get(key)
    signed = datas.get("signedTasks")
    if not isinstance(tasks, list):
        raise SafeError("签到任务列表格式无效")
    if not tasks:
        if isinstance(signed, list) and signed:
            return "alreadyComplete", {}
        return "skipped", {}
    latest = tasks[0]
    if not isinstance(latest, dict):
        raise SafeError("签到任务项无效")
    sign_instance = str(latest.get("signInstanceWid") or "").strip()
    sign_wid = str(latest.get("signWid") or "").strip()
    if not sign_instance:
        raise SafeError("任务缺少 signInstanceWid")
    return "pending", {"signInstanceWid": sign_instance, "signWid": sign_wid}


def get_detail(
    session: HttpSession, host: str, params: Dict[str, str]
) -> Dict[str, Any]:
    url = "https://{}/wec-counselor-sign-apps/stu/sign/detailSignInstance".format(host)
    payload = post_json(session, url, params)
    datas = payload.get("datas")
    if not isinstance(datas, dict):
        raise SafeError("任务详情缺少 datas")
    return datas


def upload_picture(session: HttpSession, host: str, image_path: str) -> str:
    sts_url = "https://{}/wec-counselor-sign-apps/stu/sign/getStsAccess".format(host)
    payload = post_json(session, sts_url, {})
    datas = payload.get("datas")
    if not isinstance(datas, dict):
        raise SafeError("获取上传凭证失败")
    file_name = str(datas.get("fileName") or "").strip()
    access_key = str(datas.get("accessKeyId") or "").strip()
    access_secret = str(datas.get("accessKeySecret") or "").strip()
    security_token = str(datas.get("securityToken") or "").strip()
    end_point = str(datas.get("endPoint") or "").strip()
    bucket = str(datas.get("bucket") or "").strip()
    if not all([file_name, access_key, access_secret, security_token, end_point, bucket]):
        raise SafeError("上传凭证字段不完整")
    try:
        with open(image_path, "rb") as handle:
            content = handle.read()
    except Exception as exc:
        raise SafeError("读取签到照片失败") from exc
    if not content:
        raise SafeError("签到照片为空")
    # 使用 STS 临时密钥构造的签名 PUT（简化：走校园 preview 前的直传接口约定）
    # 多数校园圈实现依赖 oss2；此处改为对 endPoint 的 HTTPS PUT，并附带 security-token。
    put_host = end_point
    if put_host.startswith("http://"):
        put_host = "https://" + put_host[len("http://") :]
    if not put_host.startswith("https://"):
        put_host = "https://" + put_host
    # bucket.endpoint/key
    parsed = urllib.parse.urlparse(put_host)
    upload_url = "{}://{}.{}/{}".format(
        parsed.scheme, bucket, parsed.netloc, urllib.parse.quote(file_name, safe="")
    )
    date_hdr = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    content_md5 = base64.b64encode(hashlib.md5(content).digest()).decode("ascii")
    content_type = "image/jpeg"
    canonical = "PUT\n{}\n{}\n{}\nx-oss-security-token:{}\n/{}/{}".format(
        content_md5, content_type, date_hdr, security_token, bucket, file_name
    )
    import hmac

    signature = base64.b64encode(
        hmac.new(access_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    status, _, _, _ = session.request(
        upload_url,
        method="PUT",
        data=content,
        headers={
            "Date": date_hdr,
            "Content-MD5": content_md5,
            "Content-Type": content_type,
            "x-oss-security-token": security_token,
            "Authorization": "OSS {}:{}".format(access_key, signature),
        },
        allow_redirects=False,
    )
    if status not in (200, 204):
        raise SafeError("照片上传失败（HTTP {}）".format(status))
    preview_url = "https://{}/wec-counselor-sign-apps/stu/sign/previewAttachment".format(host)
    preview = post_json(session, preview_url, {"ossKey": file_name})
    photo_url = preview.get("datas")
    if not isinstance(photo_url, str) or not photo_url.strip():
        raise SafeError("照片地址预览失败")
    return photo_url.strip()


def fill_form(
    task: Dict[str, Any],
    account: Dict[str, Any],
    extras: List[Dict[str, str]],
    session: HttpSession,
    host: str,
) -> Dict[str, Any]:
    form: Dict[str, Any] = {
        "signInstanceWid": task.get("signInstanceWid"),
        "longitude": account["lon"],
        "latitude": account["lat"],
        "isMalposition": task.get("isMalposition"),
        "abnormalReason": account["abnormalReason"],
        "position": account["address"],
        "uaIsCpadaily": True,
        "signPhotoUrl": "",
    }
    if int(task.get("isPhoto") or 0) == 1:
        if not account["photo"]:
            raise SafeError("该任务需要照片，请在账号配置中提供 photo 本地路径")
        form["signPhotoUrl"] = upload_picture(session, host, account["photo"])
    if int(task.get("isNeedExtra") or 0) == 1:
        extra_fields = task.get("extraField")
        if not isinstance(extra_fields, list) or not extra_fields:
            raise SafeError("任务要求附加题但未返回题目")
        if len(extras) < len(extra_fields):
            raise SafeError(
                "附加题默认不足：任务 {} 题，CPDAILY_EXTRA_DEFAULTS 仅 {} 项".format(
                    len(extra_fields), len(extras)
                )
            )
        values = []
        for index, extra_field in enumerate(extra_fields):
            if not isinstance(extra_field, dict):
                raise SafeError("附加题第 {} 项无效".format(index + 1))
            default = extras[index]
            title = str(extra_field.get("title") or "")
            if default["title"] != title:
                raise SafeError(
                    "附加题第 {} 项标题不匹配：配置「{}」实际「{}」".format(
                        index + 1, default["title"], title
                    )
                )
            items = extra_field.get("extraFieldItems")
            if not isinstance(items, list):
                raise SafeError("附加题第 {} 项缺少选项".format(index + 1))
            matched = None
            for item in items:
                if isinstance(item, dict) and str(item.get("content") or "") == default["value"]:
                    matched = item
                    break
            if matched is None:
                raise SafeError(
                    "附加题第 {} 项找不到选项「{}」".format(index + 1, default["value"])
                )
            values.append(
                {
                    "extraFieldItemValue": default["value"],
                    "extraFieldItemWid": matched.get("wid"),
                }
            )
        form["extraFieldItems"] = values
    return form


def submit_sign(
    session: HttpSession,
    host: str,
    account: Dict[str, Any],
    form: Dict[str, Any],
) -> Tuple[str, str]:
    extension = {
        "lon": account["lon"],
        "model": "OPPO R11 Plus",
        "appVersion": "8.1.14",
        "systemVersion": "4.4.4",
        "userId": account["username"] or "cookie-user",
        "systemName": "android",
        "lat": account["lat"],
        "deviceId": str(uuid.uuid1()),
    }
    headers = {
        "User-Agent": UA_APP,
        "CpdailyStandAlone": "0",
        "extension": "1",
        "Cpdaily-Extension": des_encrypt_cpdaily(json.dumps(extension, ensure_ascii=False)),
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }
    url = "https://{}/wec-counselor-sign-apps/stu/sign/submitSign".format(host)
    payload = post_json(session, url, form, headers=headers)
    message = str(payload.get("message") or "").strip()
    if message == "SUCCESS":
        return "success", "自动签到成功"
    if any(hint in message for hint in ("已经签", "已签到", "重复签", "无需重复")):
        return "alreadyComplete", message or "今日已签到"
    raise SafeError("签到失败：{}".format(compact(message, 80) or "业务未返回 SUCCESS"))


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = "账号{}".format(number)

    def display(self) -> str:
        return self.identity

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

    def skip(self, number: int, name: str, reason: str) -> None:
        self.stage(number, name, lambda: ("skipped", reason, None))

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


def run_account(
    runner: AccountRunner,
    account: Dict[str, Any],
    timeout: float,
    dry_run: bool,
    extras: List[Dict[str, str]],
    kind: str,
) -> None:
    def parameter_check():
        label = account["school"]
        if account["username"]:
            runner.identity = "{}:{}".format(label, account["username"])
        else:
            runner.identity = "{}#{}".format(label, runner.number)
        return "success", "账号本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "解析学校接口", "断网预演：不请求租户列表")
        runner.skip(3, "登录或载入会话", "断网预演：不发起登录")
        runner.skip(4, "查询签到任务", "断网预演：不请求任务接口")
        runner.skip(5, "填写并提交签到", "断网预演：不提交签到")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    session = HttpSession(timeout)
    host_box: Dict[str, str] = {"host": account.get("host") or ""}

    def resolve_stage():
        apis = resolve_apis(session, account["school"])
        host_box["host"] = apis["host"]
        host_box["login-url"] = apis["login-url"]
        return "success", "已解析学校 host", apis

    runner.stage(2, "解析学校接口", resolve_stage)

    def login_stage():
        host = host_box["host"]
        if account["mode"] == "cookie":
            session.set_cookie_header(account["cookie"], host)
            return "success", "已载入会话 Cookie", None
        cas_login(session, host_box["login-url"], account["username"], account["password"])
        return "success", "统一身份认证登录完成", None

    runner.stage(3, "登录或载入会话", login_stage)

    task_state_box: Dict[str, str] = {"state": "failure"}
    params_box: Dict[str, Dict[str, str]] = {}

    def task_stage():
        state, params = get_sign_task(session, host_box["host"], kind)
        task_state_box["state"] = state
        if state == "alreadyComplete":
            return "alreadyComplete", "今日已签到（无未签任务）", None
        if state == "skipped":
            return "skipped", "今日没有可处理的签到任务", None
        params_box["params"] = params
        return "success", "已获取未签到任务", params

    result = runner.stage(4, "查询签到任务", task_stage)
    if task_state_box["state"] in {"alreadyComplete", "skipped"}:
        runner.status = task_state_box["state"]
        return

    def submit_stage():
        detail = get_detail(session, host_box["host"], params_box["params"])
        form = fill_form(detail, account, extras, session, host_box["host"])
        state, detail_msg = submit_sign(session, host_box["host"], account, form)
        task_state_box["state"] = state
        return state, detail_msg, None

    runner.stage(5, "填写并提交签到", submit_stage)
    if runner.stats["failure"] or task_state_box["state"] == "failure":
        runner.status = "failure"
    elif task_state_box["state"] == "alreadyComplete":
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"


PY_NOTIFY_RUNNER = r'''
import importlib.util
import json
import os
import socket
import sys
specification = json.load(sys.stdin)
if specification.get("dry_run"):
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    socket.socket = denied  # type: ignore
    socket.create_connection = denied  # type: ignore
    for name in ("system", "popen", "execv", "execve", "spawnv", "spawnve"):
        if hasattr(os, name):
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
'''

JS_NOTIFY_RUNNER = r'''
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
'''


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
        "cpdaily_counselor_sign.py",
        "candidate.py",
        "scripts/cpdaily_counselor_sign.py",
        TITLE,
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
    if dry_run:
        log("通知：⏭️ 断网预演仅生成脱敏摘要，不投递外部通知")
        log("通知摘要：" + body)
        return "dry-run-skipped"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": False,
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
                log("通知：✅ 脱敏总结已交给青龙适配器")
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用或投递失败；保留业务退出码")
    return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("CPDAILY_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, Any]] = []
    timeout = float(DEFAULT_TIMEOUT)
    extras: List[Dict[str, str]] = []
    kind = "unsigned"
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("CPDAILY_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        kind = task_kind()
        extras = load_extra_defaults()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；任务类型：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                kind,
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, timeout, dry_run, extras, kind)
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
        for state in ("success", "alreadyComplete", "failure", "dry-run", "skipped")
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
        final_label = "配置错误"
    elif failed and (succeeded or counts["dry-run"] or counts["skipped"]):
        status = "partial-failure"
        final_label = "部分失败"
    elif failed:
        status = "failure"
        final_label = "失败"
    elif dry_run:
        status = "dry-run"
        final_label = "预演完成"
    elif counts["skipped"] and not succeeded:
        status = "failure"
        final_label = "失败"
        exit_code = 1
    else:
        status = "success"
        final_label = "成功"
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
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}，跳过 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
            counts["skipped"],
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
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
        log("无网络预演通过")
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
                "skipped": counts["skipped"],
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
