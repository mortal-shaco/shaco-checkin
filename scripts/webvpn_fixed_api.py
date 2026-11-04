#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: CC98 WebVPN 每日签到
# cron: 12 8 * * *
from __future__ import annotations
#
# 来源：Anchorite-no/cc98-autosign-fast
# python-reference/webvpn-fixed-api.py（MIT）
# https://github.com/Anchorite-no/cc98-autosign-fast
# 提交：3430b23dc1b08a1ac1ca1862a27c864014e541ee
# 相关参考：python-reference/run-webvpn-fixed-api.sh（仅虚拟环境安装引导，不作为独立任务）
#
# MIT License
#
# Copyright (c) Anchorite-no / cc98-autosign-fast contributors
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
"""CC98 通过浙大 WebVPN 固定路由每日签到 - 青龙维护版。

功能清点（相对上游 webvpn-fixed-api.py）：
- 使用浙大 WebVPN 账号登录，经固定 WebVPN 路径获取 CC98 OAuth Token 并提交每日签到
- 读取签到结果（财富值奖励、连续签到天数）；区分签到成功与今日已签到
- 多 CC98 账号共用同一 WebVPN 会话；移除本地 Cookie 落盘与 .env 文件依赖
- 相关 shell 仅为 venv/pip 引导，不合并为独立账号任务

CC98_WEBVPN：浙大 WebVPN 账号，格式 用户名|密码；仅在第一个竖线处分割。
兼容可选别名：WEBVPN_USER + WEBVPN_PASS（二者齐全且 CC98_WEBVPN 为空时生效）。
CC98_ACCOUNTS：每个非空行一个 CC98 账号，格式 用户名|密码；仅在第一个竖线处分割。
兼容可选别名：CC98_ACCOUNT_COUNT + CC98_USER_N / CC98_PASS_N（CC98_ACCOUNTS 为空时）。
CC98_TOKEN_PATH / CC98_SIGN_PATH：可选覆盖固定 WebVPN API 路径。
CC98_CONNECT_TIMEOUT_SEC / CC98_REQUEST_TIMEOUT_SEC：连接与读超时，默认 5 / 15。
CC98_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 08:10。不打印密码、Cookie、Token 或原始响应。
依赖：pycryptodome（WebVPN 登录页 AES-CFB 加密口令，运行时按需导入）。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "862ebb51276428df",
            "scripts/cc98_webvpn_signin.py",
            "cc98_webvpn_signin.py",
            "candidate.py",
            "cc98_webvpn_signin",
            "webvpn-fixed-api.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "CC98 WebVPN 每日签到"
CATALOG_ID = "862ebb51276428df"

LOGIN_URL = "https://webvpn.zju.edu.cn/login"
DO_LOGIN_URL = "https://webvpn.zju.edu.cn/do-login"
DO_CONFIRM_LOGIN_URL = "https://webvpn.zju.edu.cn/do-confirm-login"
WEBVPN_BASE = "https://webvpn.zju.edu.cn"
DEFAULT_ROUTE_VALUE = "8768cab8c7e7ee1c6799ad807f94da0a"
DEFAULT_CONNECT_TIMEOUT_SEC = 5.0
DEFAULT_REQUEST_TIMEOUT_SEC = 15.0
MAX_BYTES = 65536

# www.cc98.org 前端公开的 OAuth 客户端标识（非用户凭据）
CC98_CLIENT_ID = "9a1fd200-8687-44b1-4c20-08d50a96e5cd"
CC98_CLIENT_SECRET = "8b53f727-08e2-4509-8857-e34bf92b27f2"

DEFAULT_TOKEN_PATH = (
    "/https/77726476706e69737468656265737421ffe744922e3426537d51d1e2974724/"
    "connect/token?vpn-12-o2-www.cc98.org"
)
DEFAULT_SIGN_PATH = (
    "/https/77726476706e69737468656265737421f1e748d22433310830079bab/"
    "me/signin?vpn-12-o2-www.cc98.org"
)

CSRF_PATTERN = re.compile(r'name="_csrf"\s+value="([^"]+)"')
CAPTCHA_PATTERN = re.compile(r'name="captcha_id"\s+value="([^"]+)"')
KEY_IV_PATTERN = re.compile(r'encrypt\s*\([^,]+,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)')

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

BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


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


def parse_credential_pair(raw: str, label: str) -> Tuple[str, str]:
    text = raw.strip()
    if not text:
        raise SafeError("{} 为空".format(label))
    if "|" not in text:
        raise SafeError("{} 缺少分隔符；格式为 用户名|密码".format(label))
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("{} 的用户名或密码为空".format(label))
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
        raise SafeError("{} 含控制字符".format(label))
    return username, password


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        username, password = parse_credential_pair(text, "CC98 账号行")
        accounts.append({"username": username, "password": password})
    return accounts


def load_legacy_indexed_accounts() -> List[Dict[str, str]]:
    raw_count = env("CC98_ACCOUNT_COUNT")
    if not raw_count:
        return []
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise SafeError("CC98_ACCOUNT_COUNT 须为正整数") from exc
    if count < 1:
        raise SafeError("CC98_ACCOUNT_COUNT 须至少为 1")
    accounts: List[Dict[str, str]] = []
    for index in range(1, count + 1):
        username = env("CC98_USER_{}".format(index))
        password = env("CC98_PASS_{}".format(index))
        if not username or not password:
            raise SafeError(
                "兼容模式缺少 CC98_USER_{0} 或 CC98_PASS_{0}".format(index)
            )
        if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
            raise SafeError("兼容模式账号 {} 含控制字符".format(index))
        accounts.append({"username": username, "password": password})
    return accounts


def load_webvpn_credentials() -> Tuple[str, str]:
    combined = env("CC98_WEBVPN")
    if combined:
        return parse_credential_pair(combined, "CC98_WEBVPN")
    user = env("WEBVPN_USER")
    password = env("WEBVPN_PASS")
    if user and password:
        if any(ord(ch) < 32 for ch in user) or any(ord(ch) < 32 for ch in password):
            raise SafeError("WEBVPN_USER/WEBVPN_PASS 含控制字符")
        return user, password
    raise SafeError(
        "未配置 CC98_WEBVPN；请填写 用户名|密码，或同时提供 WEBVPN_USER 与 WEBVPN_PASS"
    )


def load_cc98_accounts() -> List[Dict[str, str]]:
    raw = env("CC98_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("CC98_ACCOUNTS 没有有效账号行")
        return accounts
    legacy = load_legacy_indexed_accounts()
    if legacy:
        return legacy
    raise SafeError(
        "未配置 CC98_ACCOUNTS；请按每个非空行 用户名|密码 填写，"
        "或使用兼容别名 CC98_ACCOUNT_COUNT + CC98_USER_N/CC98_PASS_N"
    )


def resolve_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = env(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(name)) from exc
    if value < minimum or value > maximum:
        raise SafeError("{} 须在 {} 到 {} 秒之间".format(name, minimum, maximum))
    return value


def encrypt_password(password: str, key: str, iv: str) -> str:
    try:
        from Crypto.Cipher import AES  # type: ignore
    except ModuleNotFoundError as exc:
        raise SafeError(
            "缺少依赖 pycryptodome；请先安装后再执行真实签到"
        ) from exc
    cipher = AES.new(
        key.encode("utf-8"),
        AES.MODE_CFB,
        iv.encode("utf-8"),
        segment_size=128,
    )
    encrypted = cipher.encrypt(password.encode("utf-8"))
    return iv.encode("utf-8").hex() + encrypted.hex()


def extract_login_fields(html: str) -> Tuple[str, str, str, str]:
    csrf_match = CSRF_PATTERN.search(html)
    captcha_match = CAPTCHA_PATTERN.search(html)
    key_iv_match = KEY_IV_PATTERN.search(html)
    if not csrf_match or not captcha_match or not key_iv_match:
        raise SafeError("WebVPN 登录页字段提取失败")
    return (
        csrf_match.group(1),
        captcha_match.group(1),
        key_iv_match.group(1),
        key_iv_match.group(2),
    )


class WebVpnClient:
    def __init__(self, connect_timeout: float, request_timeout: float) -> None:
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.ProxyHandler({}),
        )
        self._ensure_route_cookie()

    def _ensure_route_cookie(self) -> None:
        for cookie in self.cookies:
            if cookie.name == "route":
                return
        route = http.cookiejar.Cookie(
            version=0,
            name="route",
            value=DEFAULT_ROUTE_VALUE,
            port=None,
            port_specified=False,
            domain="webvpn.zju.edu.cn",
            domain_specified=True,
            domain_initial_dot=False,
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
        self.cookies.set_cookie(route)

    def _has_core_ticket(self) -> bool:
        for cookie in self.cookies:
            if cookie.name == "wengine_vpn_ticketwebvpn_zju_edu_cn":
                return True
        return False

    def clear_session(self) -> None:
        self.cookies.clear()
        self._ensure_route_cookie()

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        accept_non_json: bool = False,
    ) -> Tuple[int, str, bytes]:
        request_headers = dict(BROWSER_HEADERS)
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            # urllib 仅支持单一超时；取连接与读超时中的较大值，避免过短截断
            timeout = max(self.connect_timeout, self.request_timeout)
            with self.opener.open(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("content-type", "")
                raw = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            content_type = error.headers.get("content-type", "") if error.headers else ""
            try:
                raw = error.read(MAX_BYTES + 1)
            except Exception:
                raw = b""
            finally:
                error.close()
        except Exception as exc:
            raise SafeError("网络、超时或连接失败") from exc
        if len(raw) > MAX_BYTES:
            raise SafeError("响应超过大小限制")
        if not accept_non_json and raw and "text/html" in content_type.lower():
            # WebVPN 常在会话失效时返回登录 HTML；交给上层判定
            pass
        return status, content_type, raw

    def request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        form: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        body = None
        request_headers = dict(headers or {})
        if form is not None:
            body = urllib.parse.urlencode(form).encode("utf-8")
            request_headers.setdefault(
                "Content-Type", "application/x-www-form-urlencoded"
            )
        status, _content_type, raw = self.request(
            url, method=method, headers=request_headers, data=body, accept_non_json=True
        )
        return status, raw.decode("utf-8", errors="replace")

    def request_json(
        self,
        url: str,
        *,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        form: Optional[Dict[str, str]] = None,
        empty_body: bool = False,
    ) -> Tuple[int, Any, str]:
        body = None
        request_headers = dict(headers or {})
        if form is not None:
            body = urllib.parse.urlencode(form).encode("utf-8")
            request_headers.setdefault(
                "Content-Type", "application/x-www-form-urlencoded"
            )
        elif empty_body:
            body = b""
            request_headers.setdefault("Content-Type", "application/json")
        status, content_type, raw = self.request(
            url, method=method, headers=request_headers, data=body, accept_non_json=True
        )
        text = raw.decode("utf-8", errors="replace")
        payload: Any = None
        if raw:
            stripped = raw.lstrip()
            if "application/json" in content_type.lower() or stripped.startswith(
                (b"{", b"[")
            ):
                try:
                    payload = json.loads(text)
                except ValueError:
                    payload = None
        return status, payload, text

    def login(self, username: str, password: str) -> None:
        status, html = self.request_text(LOGIN_URL, method="GET")
        if status != 200 or not html:
            raise SafeError("打开 WebVPN 登录页失败")
        csrf, captcha_id, key, iv = extract_login_fields(html)
        form = {
            "_csrf": csrf,
            "auth_type": "local",
            "username": username,
            "sms_code": "",
            "password": encrypt_password(password, key, iv),
            "captcha": "",
            "needCaptcha": "false",
            "captcha_id": captcha_id,
        }
        status, payload, text = self.request_json(
            DO_LOGIN_URL, method="POST", form=form
        )
        if status >= 400:
            raise SafeError("WebVPN 登录请求失败")
        error = ""
        message = ""
        if isinstance(payload, dict):
            error = str(payload.get("error") or "")
            message = compact(payload.get("message") or error, 80)
        if error == "NEED_CONFIRM":
            confirm_status, _ = self.request_text(
                DO_CONFIRM_LOGIN_URL, method="POST", form=form
            )
            if confirm_status >= 400:
                raise SafeError("WebVPN 二次确认失败")
        elif error:
            raise SafeError("WebVPN 登录业务失败")
        if not self._has_core_ticket():
            # 部分成功响应不回 JSON，只要拿到核心 ticket 即视为成功
            markers = ('name="_csrf"', "captcha_id", "WebVPN")
            if any(marker in text for marker in markers) and not self._has_core_ticket():
                raise SafeError("WebVPN 登录后未获得有效会话")
            if not self._has_core_ticket():
                raise SafeError("WebVPN 登录后未获得有效会话")


def looks_like_webvpn_login_html(text: str) -> bool:
    markers = ('name="_csrf"', "captcha_id", "wengine_vpn_ticket", "WebVPN")
    return any(marker in text for marker in markers)


def summarize_sign(body: str, payload: Any, sign_info: Any) -> Tuple[str, str]:
    text = (body or "").strip()
    reward = None
    streak = None
    status = "failure"

    if text == "has_signed_in_today":
        status = "alreadyComplete"
    elif text.isdigit():
        status = "success"
        reward = int(text)
    elif isinstance(payload, dict):
        if payload.get("hasSignedInToday") is True:
            status = "alreadyComplete"
        reward_value = payload.get("reward") or payload.get("lastReward")
        streak_value = payload.get("signInCount") or payload.get("lastSignInCount")
        if reward_value is not None:
            try:
                reward = int(reward_value)
            except (TypeError, ValueError):
                pass
        if streak_value is not None:
            try:
                streak = int(streak_value)
            except (TypeError, ValueError):
                pass

    if isinstance(sign_info, dict):
        if reward is None and sign_info.get("lastReward") is not None:
            try:
                reward = int(sign_info["lastReward"])
            except (TypeError, ValueError):
                pass
        if streak is None and sign_info.get("lastSignInCount") is not None:
            try:
                streak = int(sign_info["lastSignInCount"])
            except (TypeError, ValueError):
                pass
        if sign_info.get("hasSignedInToday") is True and status == "failure":
            status = "alreadyComplete"

    if status == "failure":
        return "failure", "签到业务失败或响应无法核实"

    parts = []
    if status == "alreadyComplete":
        parts.append("今日已签到")
    else:
        parts.append("签到成功")
    if reward is not None:
        parts.append("财富值 {}".format(reward))
    if streak is not None:
        parts.append("连续 {} 天".format(streak))
    return status, "；".join(parts)


class AccountRunner:
    def __init__(self, number: int, username: str) -> None:
        self.number = number
        self.identity = username
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"

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


def obtain_token(
    client: WebVpnClient, token_path: str, username: str, password: str
) -> Tuple[str, str]:
    status, payload, text = client.request_json(
        WEBVPN_BASE + token_path,
        method="POST",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.cc98.org",
            "Referer": "https://www.cc98.org/",
        },
        form={
            "client_id": CC98_CLIENT_ID,
            "client_secret": CC98_CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password,
        },
    )
    if looks_like_webvpn_login_html(text):
        raise SafeError("WebVPN 会话失效，需重新登录网关")
    if status in (401, 403):
        raise SafeError("CC98 凭据无效或没有访问权限")
    if not isinstance(payload, dict):
        raise SafeError("CC98 Token 响应无法解析")
    access_token = str(payload.get("access_token") or "").strip()
    if status >= 400 or not access_token:
        # 不回传错误正文，避免泄漏
        raise SafeError("获取 CC98 Token 失败")
    return access_token, username


def do_sign(
    client: WebVpnClient, sign_path: str, access_token: str
) -> Tuple[str, str]:
    status, payload, text = client.request_json(
        WEBVPN_BASE + sign_path,
        method="POST",
        headers={
            "Accept": "*/*",
            "Authorization": "Bearer {}".format(access_token),
            "Origin": "https://www.cc98.org",
            "Referer": "https://www.cc98.org/",
        },
        empty_body=True,
    )
    if looks_like_webvpn_login_html(text):
        raise SafeError("WebVPN 会话失效，需重新登录网关")
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")

    sign_info: Any = None
    body = text.strip()
    provisional_ok = status < 400 or body == "has_signed_in_today" or body.isdigit()
    if provisional_ok:
        try:
            info_status, info_payload, info_text = client.request_json(
                WEBVPN_BASE + sign_path,
                method="GET",
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Authorization": "Bearer {}".format(access_token),
                    "Origin": "https://www.cc98.org",
                    "Referer": "https://www.cc98.org/",
                },
            )
            if (
                info_status < 400
                and isinstance(info_payload, dict)
                and not looks_like_webvpn_login_html(info_text)
            ):
                sign_info = info_payload
        except SafeError:
            sign_info = None

    state, detail = summarize_sign(body, payload, sign_info)
    if state == "failure":
        raise SafeError(detail)
    return state, detail


def ensure_webvpn_session(
    client: WebVpnClient,
    webvpn_user: str,
    webvpn_pass: str,
    force: bool = False,
) -> None:
    if force or not client._has_core_ticket():
        client.clear_session()
        client.login(webvpn_user, webvpn_pass)


def run_account(
    runner: AccountRunner,
    client: WebVpnClient,
    webvpn_user: str,
    webvpn_pass: str,
    account: Dict[str, str],
    token_path: str,
    sign_path: str,
    dry_run: bool,
    shared_webvpn_ready: List[bool],
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "WebVPN 网关登录", "断网预演：不请求 WebVPN")
        runner.skip(3, "获取 CC98 Token", "断网预演：不请求 Token")
        runner.skip(4, "公开身份", "断网预演：使用配置中的用户名作为展示名")
        runner.skip(5, "提交每日签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    def webvpn_stage():
        if not shared_webvpn_ready or not shared_webvpn_ready[0]:
            ensure_webvpn_session(client, webvpn_user, webvpn_pass, force=True)
            if shared_webvpn_ready is not None:
                shared_webvpn_ready[:] = [True]
            return "success", "WebVPN 网关登录成功（会话仅存内存）", None
        return "success", "复用本进程内 WebVPN 会话", None

    runner.stage(2, "WebVPN 网关登录", webvpn_stage)

    token_box: Dict[str, str] = {}

    def token_stage():
        try:
            access_token, identity = obtain_token(
                client, token_path, account["username"], account["password"]
            )
        except SafeError as error:
            if "会话失效" not in str(error):
                raise
            ensure_webvpn_session(client, webvpn_user, webvpn_pass, force=True)
            if shared_webvpn_ready is not None:
                shared_webvpn_ready[:] = [True]
            access_token, identity = obtain_token(
                client, token_path, account["username"], account["password"]
            )
        token_box["access_token"] = access_token
        runner.identity = identity
        return "success", "已获取 CC98 访问令牌（不输出）", access_token

    runner.stage(3, "获取 CC98 Token", token_stage)

    def identity_stage():
        return "success", "公开账号身份：{}".format(runner.display()), None

    runner.stage(4, "公开身份", identity_stage)

    def sign_stage():
        state, detail = do_sign(client, sign_path, token_box["access_token"])
        return state, detail, None

    runner.stage(5, "提交每日签到", sign_stage)
    runner.status = (
        "alreadyComplete" if runner.stats["alreadyComplete"] else "success"
    )


PY_NOTIFY_RUNNER = r'''
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
        "cc98_webvpn_signin.py",
        "candidate.py",
        "scripts/cc98_webvpn_signin.py",
        "webvpn-fixed-api.py",
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
    dry_setting = env("CC98_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    webvpn_user = ""
    webvpn_pass = ""
    token_path = DEFAULT_TOKEN_PATH
    sign_path = DEFAULT_SIGN_PATH
    connect_timeout = DEFAULT_CONNECT_TIMEOUT_SEC
    request_timeout = DEFAULT_REQUEST_TIMEOUT_SEC
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("CC98_DRY_RUN 配置无效，停止执行")
        connect_timeout = resolve_float(
            "CC98_CONNECT_TIMEOUT_SEC", DEFAULT_CONNECT_TIMEOUT_SEC, 2.0, 60.0
        )
        request_timeout = resolve_float(
            "CC98_REQUEST_TIMEOUT_SEC", DEFAULT_REQUEST_TIMEOUT_SEC, 5.0, 120.0
        )
        webvpn_user, webvpn_pass = load_webvpn_credentials()
        accounts_data = load_cc98_accounts()
        token_path = env("CC98_TOKEN_PATH") or DEFAULT_TOKEN_PATH
        sign_path = env("CC98_SIGN_PATH") or DEFAULT_SIGN_PATH
        if not token_path.startswith("/"):
            raise SafeError("CC98_TOKEN_PATH 须为以 / 开头的 WebVPN 路径")
        if not sign_path.startswith("/"):
            raise SafeError("CC98_SIGN_PATH 须为以 / 开头的 WebVPN 路径")
        log(
            "运行模式：{}；账号数：{}；连接超时：{}秒；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(connect_timeout) if connect_timeout.is_integer() else connect_timeout,
                int(request_timeout) if request_timeout.is_integer() else request_timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    shared_webvpn_ready = [False]
    client: Optional[WebVpnClient] = None
    if config_error is None and not dry_run:
        client = WebVpnClient(connect_timeout, request_timeout)

    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number, item["username"])
            accounts.append(runner)
            try:
                if dry_run:
                    run_account(
                        runner,
                        client,  # type: ignore[arg-type]
                        webvpn_user,
                        webvpn_pass,
                        item,
                        token_path,
                        sign_path,
                        True,
                        shared_webvpn_ready,
                    )
                else:
                    assert client is not None
                    run_account(
                        runner,
                        client,
                        webvpn_user,
                        webvpn_pass,
                        item,
                        token_path,
                        sign_path,
                        False,
                        shared_webvpn_ready,
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
