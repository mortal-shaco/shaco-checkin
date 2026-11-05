#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: linux.sb 每日签到
# cron: 10 8 * * *
"""linux.sb（烧饼社区）每日签到独立维护版。

来源：Eitan-S-23/NodeSeek-DeepFlood-LinuxSB-Checkin（MIT），原路径 linuxsb_daily.py。
上游协议（对照 qd-today/templates Linux_SB.har 与源码）：
  - GET  https://linux.sb/daily_checkin 携带 Cookie，解析 CSRF 与「今日已签到」
  - POST https://linux.sb/daily_checkin 提交表单 _csrf，响应 ok=1 为成功；
    ok=0 且文案含已签到/已打卡/重复签到时按当日已完成处理

本维护版：仅标准库 HTTP，青龙可调度；LINUXSB_COOKIE 换行多账号；
LINUXSB_DRY_RUN 完全断网预演；超时、业务成功判定、脱敏时间轴日志、TASK_SUMMARY
与青龙通知策略。不依赖私有仓库、本机 Chrome / undetected-chromedriver / xvfb。
上游浏览器过盾与账号密码登录兜底依赖预装浏览器可执行文件，青龙环境不可用；
遇 Cloudflare 挑战或 Cookie 失效时明确失败并提示更新 Cookie。
不与 NodeSeek / DeepFlood 合并（不同应用与凭据）。

参数：
LINUXSB_COOKIE：必填。每个非空行一个账号的完整 Cookie（含 bbs_auth 等登录态）。
  浏览器登录 https://linux.sb 后，在开发者工具网络面板任选同域请求，复制请求头
  Cookie 完整值；不要复制响应 Set-Cookie。过期后重新获取。
LINUXSB_TIMEOUT：单次请求超时秒数，默认 30，范围 5..120。
LINUXSB_SITE_GAP_MIN / LINUXSB_SITE_GAP_MAX：正式执行前随机延迟秒数，默认 0；
  需要拉开执行间隔时自行设置（兼容上游 SITE_GAP_MIN / SITE_GAP_MAX）。
LINUXSB_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：见契约。
本脚本不发布帖子、评论或分享文本。

MIT License

Copyright (c) 2024-2026 Eitan-S-23 / Hosea and contributors
（NodeSeek-DeepFlood-LinuxSB-Checkin）

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
from __future__ import annotations

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
        _ql_notify_identities = ('b60e5edc4107a20d', 'scripts/linuxsb_daily.py', 'linuxsb_daily.py', 'linuxsb_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import Message
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import HTTPCookieProcessor, Request, build_opener

TITLE = "linux.sb 每日签到"
CATALOG_ID = "b60e5edc4107a20d"
BASE_URL = "https://linux.sb"
CHECKIN_URL = BASE_URL + "/daily_checkin"
CSRF_RE = re.compile(r'name="_csrf"\s+value="([^"]+)"')
CHECKED_IN_TEXT = "今日已签到"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
CF_CHALLENGE_MARKERS = (
    "just a moment",
    "challenges.cloudflare.com",
    "cf-browser-verification",
)
_CHECKIN_BONUS_FIELDS = ("bonus", "points", "gain", "reward", "score", "earned")
_BONUS_TEXT_RE = re.compile(
    r"(?:获得|获得积分|奖励|积分[＋+]\s*|本次签到获得)\s*[＋+]?\s*(\d+)\s*积分"
)
USERNAME_PATTERNS = (
    re.compile(r'class="user-name"[^>]*>([^<]{1,32})</a>'),
    re.compile(
        r'href="[^"]*/(?:user|member|profile|u)/\d+[^"]*"[^>]*>([^<]{1,32})</a>',
        re.IGNORECASE,
    ),
)
COOKIE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$")
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
MAX_RESPONSE_BYTES = 1024 * 1024
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SECRETS: List[str] = []


class TaskError(Exception):
    """脚本生成的安全错误文案。"""


class CloudflareChallenged(TaskError):
    """HTTP 通道被 Cloudflare 挑战拦截。"""


class CookieExpired(TaskError):
    """登录态无效或 Cookie 已过期。"""


class CheckinRejected(TaskError):
    """服务端明确拒绝签到。"""


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(name: str) -> bool:
    return env(name).lower() in TRUE_VALUES


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if value and value not in SECRETS:
        SECRETS.append(value)
    for part in re.split(r"[;\s]+", value):
        if "=" in part:
            _, raw = part.split("=", 1)
            raw = raw.strip()
            if raw and raw not in SECRETS:
                SECRETS.append(raw)


def safe_text(value: Any, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(
        r"(?i)(cookie|token|session|authorization|bbs_auth|bbs_csrf|"
        r"signature|device[_-]?id)\s*[:=]\s*[^\s,;]+",
        "[敏感字段已隐藏]",
        text,
    )
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit] if text else "未提供业务消息"


def parse_timeout() -> float:
    raw = env("LINUXSB_TIMEOUT", "30") or "30"
    try:
        value = float(raw)
    except ValueError as exc:
        raise TaskError("LINUXSB_TIMEOUT 必须是数字秒数") from exc
    if value < 5 or value > 120:
        raise TaskError("LINUXSB_TIMEOUT 必须在 5 到 120 秒之间")
    return value


def parse_site_gap() -> Tuple[int, int]:
    def read(name: str, alias: str, default: int) -> int:
        raw = env(name) or env(alias)
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise TaskError("{} 必须是整数秒".format(name)) from exc

    low = read("LINUXSB_SITE_GAP_MIN", "SITE_GAP_MIN", 0)
    high = read("LINUXSB_SITE_GAP_MAX", "SITE_GAP_MAX", 0)
    if low < 0 or high < 0:
        raise TaskError("站间延迟不能为负数")
    if low > high:
        low, high = high, low
    if high > 600:
        raise TaskError("站间延迟上限不得超过 600 秒")
    return low, high


def load_accounts() -> List[str]:
    raw = os.environ.get("LINUXSB_COOKIE", "")
    if raw is None:
        raw = ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise TaskError(
            "未配置 LINUXSB_COOKIE：请登录 https://linux.sb 后复制请求头 Cookie，"
            "每个非空行一个账号"
        )
    accounts: List[str] = []
    for line in lines:
        # 旧上游用 & 分隔多账号；HTTP Cookie 头本身用分号。若整行被 & 切成多段合法
        # name=value，视为遗留多账号写法并要求改用换行。
        amp_parts = [p.strip() for p in line.split("&") if p.strip()]
        if len(amp_parts) >= 2 and all(
            "=" in part and COOKIE_NAME_PATTERN.match(part.split("=", 1)[0].strip())
            for part in amp_parts
        ):
            raise TaskError(
                "LINUXSB_COOKIE 多账号请改用换行分隔，不再使用 & 分隔账号"
            )
        remember_secret(line)
        accounts.append(line)
    return accounts


def parse_cookies(raw_cookie: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    current: Optional[str] = None
    for chunk in re.split(r"[;]+", raw_cookie or ""):
        segment = chunk.strip()
        if not segment:
            continue
        if "=" in segment:
            key, value = segment.split("=", 1)
            key = key.strip()
            if key and COOKIE_NAME_PATTERN.match(key):
                cookies[key] = value.strip()
                current = key
                continue
        if current is not None:
            cookies[current] += ";" + segment
    return cookies


def cookie_header(cookies: Dict[str, str]) -> str:
    return "; ".join("{}={}".format(k, v) for k, v in cookies.items())


def header_value(headers: Any, name: str, default: str = "") -> str:
    if headers is None:
        return default
    target = name.lower()
    if hasattr(headers, "items"):
        for key, value in headers.items():
            if str(key).lower() == target:
                return str(value).strip()
    return default


def is_cf_challenge(status: int, headers: Any, body: str) -> bool:
    if header_value(headers, "cf-mitigated").lower() == "challenge":
        return True
    head = (body or "")[:3000].lower()
    return any(marker in head for marker in CF_CHALLENGE_MARKERS)


def extract_username(html: str) -> Optional[str]:
    for pattern in USERNAME_PATTERNS:
        match = pattern.search(html or "")
        if match:
            name = match.group(1).strip()
            if name:
                return name
    return None


def extract_checkin_meta(html: str) -> List[Tuple[str, str]]:
    text = re.sub(r"<!--[\s\S]*?-->", " ", html or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    found: List[Tuple[str, str]] = []

    def try_find(label: str, pattern: str, suffix: str = "") -> bool:
        match = re.search(pattern, text)
        if match:
            found.append((label, match.group(1) + suffix))
            return True
        return False

    if not try_find("当前积分", r"当前积分[:：]?\s*([\d,]+)"):
        try_find("积分", r"积分\s*[:：]?\s*([\d,]+)")
    try_find("连续签到", r"连续签到\s*[:：]?\s*(\d+)\s*天", " 天")
    return found


def checkin_bonus(result: Any) -> Optional[int]:
    if not isinstance(result, dict):
        return None
    for key in _CHECKIN_BONUS_FIELDS:
        value = result.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            match = re.search(r"[+]?\s*(\d+)", value)
            if match:
                return int(match.group(1))
    return None


def checkin_bonus_from_text(html: str) -> Optional[str]:
    match = _BONUS_TEXT_RE.search(html or "")
    return match.group(1) if match else None


def _decode_body(raw: bytes, content_type: str) -> str:
    charset = "utf-8"
    if content_type:
        msg = Message()
        msg["content-type"] = content_type
        charset = msg.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def http_request(
    method: str,
    url: str,
    *,
    cookie: str,
    timeout: float,
    data: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, str], str, str, str]:
    """返回 (status, headers, body, merged_cookie, final_url)。"""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": USER_AGENT,
        "Cookie": cookie_header(parse_cookies(cookie)),
        "Referer": CHECKIN_URL,
    }
    body_bytes: Optional[bytes] = None
    if data is not None:
        body_bytes = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Accept"] = "application/json, text/plain, */*"

    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    request = Request(url, data=body_bytes, headers=headers, method=method.upper())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise TaskError("响应体过大，已中止读取")
            status = int(getattr(response, "status", None) or response.getcode())
            resp_headers = {k: v for k, v in response.headers.items()}
            final_url = response.geturl()
            text = _decode_body(raw, response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1) if exc.fp else b""
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TaskError("错误响应体过大，已中止读取") from exc
        status = int(exc.code)
        resp_headers = {k: v for k, v in (exc.headers.items() if exc.headers else [])}
        final_url = str(getattr(exc, "url", None) or url)
        text = _decode_body(raw, resp_headers.get("Content-Type", ""))
        if is_cf_challenge(status, resp_headers, text):
            mitigated = header_value(resp_headers, "cf-mitigated", "-")
            ray = header_value(resp_headers, "cf-ray", "-")
            raise CloudflareChallenged(
                "Cloudflare 挑战拦截 HTTP 通道（HTTP {}，cf-mitigated={}，cf-ray={}）；"
                "维护版不启动本机浏览器，请稍后重试或更新 Cookie".format(
                    status, mitigated, ray
                )
            ) from exc
        raise TaskError("HTTP {}".format(status)) from exc
    except urllib.error.URLError as exc:
        raise TaskError("网络错误：{}".format(safe_text(exc.reason))) from exc

    if is_cf_challenge(status, resp_headers, text):
        mitigated = header_value(resp_headers, "cf-mitigated", "-")
        ray = header_value(resp_headers, "cf-ray", "-")
        raise CloudflareChallenged(
            "Cloudflare 挑战拦截 HTTP 通道（HTTP {}，cf-mitigated={}，cf-ray={}）；"
            "维护版不启动本机浏览器，请稍后重试或更新 Cookie".format(
                status, mitigated, ray
            )
        )

    merged = parse_cookies(cookie)
    for item in jar:
        if item.value is not None:
            merged[item.name] = item.value
    return status, resp_headers, text, cookie_header(merged) if merged else cookie, final_url


def fetch_checkin_state(cookie: str, timeout: float) -> Tuple[Optional[str], bool, bool, str]:
    """返回 (csrf, checked_in, is_login_page, html)。"""
    status, _headers, html, _cookie, final_url = http_request(
        "GET", CHECKIN_URL, cookie=cookie, timeout=timeout
    )
    if status != 200:
        raise TaskError("获取签到页面失败，HTTP {}".format(status))

    has_password_field = 'name="password"' in html
    log(
        "阶段1 探测签到页：HTTP {}，URL 主机已校验，长度 {}，csrf={}，password框={}，已签到={}".format(
            status,
            len(html),
            "有" if CSRF_RE.search(html) else "无",
            has_password_field,
            CHECKED_IN_TEXT in html,
        )
    )
    if (
        "/login" in final_url
        or "user_review_login_email" in final_url
        or has_password_field
    ):
        return None, CHECKED_IN_TEXT in html, True, html

    match = CSRF_RE.search(html)
    csrf = match.group(1) if match else None
    checked_in = CHECKED_IN_TEXT in html
    if csrf is None and not checked_in:
        return None, False, True, html
    return csrf, checked_in, False, html


def build_overview_lines(cookie: str, timeout: float, base_lines: List[str]) -> Tuple[List[str], Optional[str]]:
    lines = list(base_lines)
    try:
        status, _h, html, _c, final_url = http_request(
            "GET", CHECKIN_URL, cookie=cookie, timeout=timeout
        )
    except TaskError as exc:
        log("{} 概览页获取失败：{}".format(ICONS["warning"], safe_text(exc)))
        if len(lines) == 1:
            lines.append("概览信息: 未从页面取到（请求失败）")
        return lines, None

    username = None
    if status == 200 and html:
        title_match = re.search(r"<title>([^<]*)</title>", html)
        title = title_match.group(1).strip() if title_match else "?"
        log(
            "概览页：HTTP {}，标题「{}」，长度 {}".format(
                status, safe_text(title, 40), len(html)
            )
        )
        username = extract_username(html)
        meta = extract_checkin_meta(html)
        for label, value in meta:
            lines.append("{}: {}".format(label, value))
        toast_bonus = checkin_bonus_from_text(html)
        if toast_bonus is not None and not any("本次签到获得" in x for x in lines):
            lines.append("本次签到获得: {} 积分".format(toast_bonus))
    else:
        log("概览页未取到：HTTP {}".format(status))
    if len(lines) == 1:
        lines.append("概览信息: 未从页面取到（模板差异或 Cookie 权限不足）")
    return lines, username


def sign_in_account(cookie: str, timeout: float) -> Tuple[str, str, Optional[str], List[str]]:
    """
    返回 (status, message, username, detail_lines)
    status: success | alreadyComplete | failure
    """
    csrf, checked_in, is_login_page, html = fetch_checkin_state(cookie, timeout)

    if csrf is None:
        if not is_login_page:
            page_csrf = parse_cookies(cookie).get("bbs_csrf")
            if page_csrf:
                log("签到页未渲染 _csrf 字段，改用 cookie 中的 bbs_csrf")
                csrf = page_csrf
        if csrf is None:
            if checked_in and not is_login_page:
                lines, username = build_overview_lines(
                    cookie, timeout, ["签到结果: 今日已签到，无需重复签到"]
                )
                return "alreadyComplete", lines[0], username or extract_username(html), lines
            raise CookieExpired(
                "Cookie 已失效或页面结构变化：未找到 CSRF token，请重新登录 linux.sb 并更新 LINUXSB_COOKIE"
            )

    if is_login_page:
        raise CookieExpired(
            "未取得登录态（可能被重定向到登录/邮箱确认页）。"
            "维护版仅支持 HTTP Cookie 签到；请确认 Cookie 含 bbs_auth 且出口未被 Cloudflare 挑战，"
            "或稍后重试"
        )

    if checked_in:
        lines, username = build_overview_lines(
            cookie, timeout, ["签到结果: 今日已签到，无需重复签到"]
        )
        return "alreadyComplete", lines[0], username or extract_username(html), lines

    log("阶段2 提交签到 POST")
    status, _h, body, merged_cookie, _url = http_request(
        "POST",
        CHECKIN_URL,
        cookie=cookie,
        timeout=timeout,
        data={"_csrf": csrf},
    )
    if status != 200:
        raise TaskError("签到请求失败，HTTP {}".format(status))
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TaskError("签到响应不是合法 JSON") from exc

    if result.get("ok") in (1, True, "1", "true"):
        message = result.get("message", "") or ""
        lines = ["签到结果: 签到成功{}".format("（{}）".format(message) if message else "")]
        bonus = checkin_bonus(result)
        if bonus is not None:
            lines.append("本次签到获得: {} 积分".format(bonus))
        extras = [
            "{}: {}".format(key, value)
            for key, value in result.items()
            if key not in ("ok", "message", "redirect")
            and key not in _CHECKIN_BONUS_FIELDS
        ]
        lines.extend(extras)
        overview, username = build_overview_lines(merged_cookie, timeout, lines)
        return "success", overview[0], username, overview

    message = str(result.get("message", "") or "")
    if any(word in message for word in ("已签到", "已打卡", "重复签到")):
        lines = ["签到结果: 今日已签到，无需重复签到（服务端：{}）".format(safe_text(message))]
        overview, username = build_overview_lines(merged_cookie, timeout, lines)
        return "alreadyComplete", overview[0], username, overview

    hint = (
        "（Cookie 可能已失效，请重新登录 linux.sb 并更新 LINUXSB_COOKIE）"
        if "过期" in message
        else ""
    )
    raise CheckinRejected("签到失败：{}{}".format(safe_text(message), hint))


def run_account_dry(index: int, cookie: str) -> Dict[str, Any]:
    started = time.monotonic()
    log("---------- 账号 {} ----------".format(index))
    log("[1/2] 校验 Cookie 形态")
    cookies = parse_cookies(cookie)
    if not cookies:
        elapsed = time.monotonic() - started
        log("{} Cookie 无法解析为 name=value".format(ICONS["failure"]))
        return {
            "index": index,
            "identity": "账号{}".format(index),
            "ok": False,
            "status": "failure",
            "message": "Cookie 格式无效",
            "stats": {
                "total": 1,
                "success": 0,
                "already": 0,
                "skipped": 0,
                "failed": 1,
            },
            "elapsed": elapsed,
        }
    has_auth = any(k.lower() == "bbs_auth" for k in cookies)
    log(
        "[2/2] 预检通过：cookie 项 {} 个，bbs_auth={}".format(
            len(cookies), "有" if has_auth else "无"
        )
    )
    if not has_auth:
        log("{} 警告：未见 bbs_auth，正式执行时登录态可能不完整".format(ICONS["warning"]))
    elapsed = time.monotonic() - started
    identity = "账号{}".format(index)
    log(
        "{} 断网预演通过；身份={}；耗时={:.2f}秒".format(
            ICONS["skipped"], identity, elapsed
        )
    )
    return {
        "index": index,
        "identity": identity,
        "ok": True,
        "status": "dry-run",
        "message": "断网预演通过",
        "stats": {
            "total": 1,
            "success": 0,
            "already": 0,
            "skipped": 1,
            "failed": 0,
        },
        "elapsed": elapsed,
    }


def run_account(index: int, cookie: str, timeout: float) -> Dict[str, Any]:
    started = time.monotonic()
    log("---------- 账号 {} ----------".format(index))
    stats = {"total": 1, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    try:
        status, message, username, details = sign_in_account(cookie, timeout)
        identity = username or "账号{}".format(index)
        if username:
            log("官方返回用户名：{}".format(username))
        if status == "success":
            stats["success"] = 1
            icon = ICONS["success"]
        else:
            stats["already"] = 1
            icon = ICONS["alreadyComplete"]
        for line in details:
            log("  · {}".format(safe_text(line, 160)))
        elapsed = time.monotonic() - started
        log(
            "{} 账号{} 身份={}；结果={}；总任务=1，成功={}，已完成={}，跳过=0，失败=0，耗时={:.2f}秒".format(
                icon,
                index,
                identity,
                message,
                stats["success"],
                stats["already"],
                elapsed,
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": True,
            "status": status,
            "message": message,
            "stats": stats,
            "elapsed": elapsed,
        }
    except Exception as exc:
        stats["failed"] = 1
        elapsed = time.monotonic() - started
        identity = "账号{}".format(index)
        msg = safe_text(exc)
        log("{} 账号{} 失败：{}".format(ICONS["failure"], index, msg))
        log(
            "[账号{}] 身份={}；结果=失败；总任务=1，成功=0，已完成=0，跳过=0，失败=1，耗时={:.2f}秒".format(
                index, identity, elapsed
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": False,
            "status": "failure",
            "message": msg,
            "stats": stats,
            "elapsed": elapsed,
        }


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {
        CATALOG_ID,
        Path(__file__).name,
        "candidate.py",
        "linuxsb_daily.py",
        "scripts/linuxsb_daily.py",
        "linuxsb-daily",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    if value != "auto":
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = env("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = env("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    return paths


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    paths = [None] + [path for path in python_notifier_paths() if path.is_file()]
    for path in paths:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    python_runner,
                    str(path) if path else "",
                    str(Path(__file__).resolve().parent),
                ],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                log(
                    "通知状态：{} 已调用".format(
                        "notify.py" if path else "notify.send"
                    )
                )
                return "sent"
        except Exception:
            continue

    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in js_notifier_paths():
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue

    log(
        "{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(
            ICONS["warning"]
        )
    )
    return "unavailable"


def emit_summary(
    *,
    status: str,
    final_label: str,
    dry_run: bool,
    results: List[Dict[str, Any]],
    account_success: int,
    account_failed: int,
    notify_state: str,
    started_at: str,
    overall_started: float,
) -> None:
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    print("\n" + "-" * 56)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), account_success, account_failed
        )
    )
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(
            **task_stats
        )
    )
    print("总耗时：{:.2f}秒".format(elapsed))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：{}".format(final_label))
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "status": status,
                "mode": "dry-run" if dry_run else "live",
                "accounts": {
                    "total": len(results),
                    "success": account_success,
                    "failed": account_failed,
                },
                "tasks": {
                    "total": task_stats["total"],
                    "success": task_stats["success"],
                    "alreadyComplete": task_stats["already"],
                    "skipped": task_stats["skipped"],
                    "failed": task_stats["failed"],
                },
                "notification": notify_state,
                "elapsedSeconds": round(elapsed, 3),
                "startedAt": started_at,
                "finishedAt": finished_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_setting = env("LINUXSB_DRY_RUN", "0").lower() or "0"
    dry_run = dry_setting in TRUE_VALUES
    print("=" * 56)
    print("{} | 独立维护版".format(TITLE))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("目录编号：{}".format(CATALOG_ID))
    print("=" * 56, flush=True)

    try:
        if dry_setting and dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise TaskError("LINUXSB_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout()
        gap_min, gap_max = parse_site_gap()
        accounts = load_accounts()
    except TaskError as exc:
        log("账号数量：0")
        log("[0/0] {} 配置错误：{}".format(ICONS["failure"], safe_text(exc)))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误；详情：{}".format(
            safe_text(exc)
        )
        notify_state = send_notification(TITLE, body, dry_run)
        emit_summary(
            status="configuration-error",
            final_label="CONFIG_ERROR",
            dry_run=dry_run,
            results=[],
            account_success=0,
            account_failed=1,
            notify_state=notify_state,
            started_at=started_at,
            overall_started=overall_started,
        )
        return 2

    log("账号数量：{}".format(len(accounts)))
    log("超时：{}秒；站间延迟：{}-{}秒".format(int(timeout), gap_min, gap_max))

    if not dry_run and gap_max > 0:
        gap = random.randint(gap_min, gap_max)
        log("正式执行前等待 {} 秒".format(gap))
        time.sleep(gap)

    if dry_run:
        results = [run_account_dry(i, cookie) for i, cookie in enumerate(accounts, 1)]
    else:
        results = [
            run_account(i, cookie, timeout) for i, cookie in enumerate(accounts, 1)
        ]

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success

    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
        final_label = "DRY_RUN"
        log("断网预演通过")
    elif account_failed == 0:
        status = "success"
        exit_code = 0
        final_label = "SUCCESS"
    elif account_success:
        status = "partial-failure"
        exit_code = 1
        final_label = "PARTIAL_FAILURE"
    else:
        status = "failure"
        exit_code = 1
        final_label = "FAILURE"

    detail_bits = [
        "账号{}({})：{}".format(item["index"], item["identity"], item["message"])
        for item in results
    ]
    body = "账号总数：{}；成功：{}；失败：{}；状态：{}。{}".format(
        len(results),
        account_success,
        account_failed,
        status,
        "；".join(detail_bits),
    )
    notify_state = send_notification(TITLE, body, dry_run)
    emit_summary(
        status=status,
        final_label=final_label,
        dry_run=dry_run,
        results=results,
        account_success=account_success,
        account_failed=account_failed,
        notify_state=notify_state,
        started_at=started_at,
        overall_started=overall_started,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
