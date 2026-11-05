#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 一亩三分地每日签到答题
# cron: 51 8 * * *
#
# 来源：harryhare/1point3acres src/raw_requests.py（编排参考 src/service.py）
# https://github.com/harryhare/1point3acres
# 提交：514c193f8ba2d7034486971f98487672a9f567b6
# 许可：GPL-3.0
# 题目数据来源声明（上游 README）：https://github.com/eagleoflqj/p1a3_script
#
# Copyright (C) harryhare and contributors
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""一亩三分地（1point3acres）每日签到 + 每日答题 — 青龙维护版。

功能清点（相对上游 raw_requests.py / service.py）：
- Cookie 会话登录（推荐；应对强制微信扫码）
- 可选用户名密码登录（auth.1point3acres.com + reCAPTCHA，需 2captcha）
- 每日签到：检测「今日已签到」；否则 POST api/users/checkin（Turnstile）
- 签到附带 todaysay：优先一言 HTTPS 文案，失败回退本地；dry-run 不请求一言
- 每日答题：GET/POST api/daily_questions，内置题库匹配选项
- 移除 tmp.html 落盘、无超时请求与原始响应打印
- 多账号：YM3D_COOKIE 每行一个 Cookie；任账号失败整体非零退出
- YM3D_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY

建议 Cron：15 8 * * *。不打印 Cookie、Token、验证码密钥或原始响应。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "7658724a6095b13b",
            "scripts/ym3d_daily.py",
            "ym3d_daily.py",
            "ym3d_daily",
            "candidate.py",
            "一亩三分地每日签到答题",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import http.cookiejar
import http.cookies
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_NAME = "一亩三分地每日签到答题"
CATALOG_ID = "7658724a6095b13b"
SCRIPT_FILENAME = "candidate.py"

REFERER = "https://www.1point3acres.com/"
CHECKIN_PAGE = "https://www.1point3acres.com/next/daily-checkin"
POST_CHECKIN_URL = "https://api.1point3acres.com/api/users/checkin"
QUESTION_PAGE = "https://www.1point3acres.com/next/daily-question"
DAILY_QUESTION_URL = "https://api.1point3acres.com/api/daily_questions"
AUTH_LOGIN_PAGE = "https://auth.1point3acres.com/"
AUTH_LOGIN_URL = "https://auth.1point3acres.com/login"
BBS_HOME = "https://www.1point3acres.com/bbs/"

CF_TURNSTILE_SITEKEY = "0x4AAAAAAAA6iSaNNPWafmlz"
LOGIN_RECAPTCHA_SITEKEY = "6LewCc8ZAAAAAOu08V7c-IYrzICepKEQFFX401py"

HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_TIMEOUT = 8
HITOKOTO_MAX_BYTES = 16384

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) "
    "Gecko/20100101 Firefox/72.0"
)
HTTP_TIMEOUT = 20
CAPTCHA_POLL_TIMEOUT = 120
CAPTCHA_POLL_INTERVAL = 5

DRY_RUN_ENV = "YM3D_DRY_RUN"
COOKIE_ENV = "YM3D_COOKIE"
ACCOUNT_ENV = "YM3D_ACCOUNT"
CAPTCHA_ENV = "YM3D_CAPTCHA_KEY"
ENABLE_CHECKIN_ENV = "YM3D_ENABLE_CHECKIN"
ENABLE_QUESTION_ENV = "YM3D_ENABLE_QUESTION"
LOCAL_TEXT_ENV = "YM3D_LOCAL_TEXT"
TIMEOUT_ENV = "YM3D_TIMEOUT"

EMOJI_LIST = ["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]
LOCAL_FALLBACK_TEXTS = [
    "今天也要好好加油。",
    "保持好奇，继续前进。",
    "小步迭代，日有寸进。",
]

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _now() -> datetime:
    return datetime.now()


def _ts(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%H:%M:%S")


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def log_stage(index: int, title: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    log(f"阶段{index} {title}{suffix}")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_truthy(name: str, default: str = "0") -> bool:
    return _env(name, default).strip().lower() in TRUE_VALUES


def _env_flag(name: str, default: bool = True) -> bool:
    raw = _env(name, "").strip().lower()
    if not raw:
        return default
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    return default


def _is_dry_run() -> bool:
    return _env_truthy(DRY_RUN_ENV)


def _http_timeout() -> int:
    raw = _env(TIMEOUT_ENV, "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError:
        return HTTP_TIMEOUT
    return max(5, min(120, value))


def _user_agent() -> str:
    return _env("YM3D_UA", DEFAULT_UA).strip() or DEFAULT_UA


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------


def parse_cookie_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text and " " not in text and ";" not in text:
            # still accept opaque cookie tokens, but warn-like validate length
            if len(text) < 8:
                raise ValueError(f"第 {line_no} 行 Cookie 过短，疑似无效")
        accounts.append({"mode": "cookie", "cookie": text})
    return accounts


def parse_password_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "&" not in text:
            raise ValueError(
                f"第 {line_no} 行账号格式无效：缺少用户名与密码分隔符 &"
            )
        username, password = text.split("&", 1)
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise ValueError(f"第 {line_no} 行账号格式无效：用户名或密码为空")
        accounts.append(
            {"mode": "password", "username": username, "password": password}
        )
    return accounts


def load_accounts() -> Tuple[List[Dict[str, str]], str]:
    cookie_raw = _env(COOKIE_ENV)
    if cookie_raw is not None and cookie_raw.strip() != "":
        return parse_cookie_accounts(cookie_raw), COOKIE_ENV
    account_raw = _env(ACCOUNT_ENV)
    if account_raw is not None and account_raw.strip() != "":
        return parse_password_accounts(account_raw), ACCOUNT_ENV
    return [], ""


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def _notify_global_mode() -> str:
    raw = _env("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in TRUE_VALUES:
        return "enabled"
    if raw in FALSE_VALUES:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if raw is None:
        return None
    if raw.strip() == "":
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _selector_match(selector: str) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if sel == "*":
        return True
    candidates = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        f"scripts/{SCRIPT_FILENAME}",
        "scripts/ym3d_daily.py",
        "ym3d_daily.py",
        SCRIPT_NAME,
    }
    sel_l = sel.lower()
    if sel in candidates or sel_l in {c.lower() for c in candidates}:
        return True
    if sel.endswith("*") and (
        SCRIPT_FILENAME.startswith(sel[:-1])
        or "ym3d_daily.py".startswith(sel[:-1])
    ):
        return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    if mode == "enabled":
        return True
    selectors = _script_selectors()
    if selectors is None:
        return True
    if not selectors:
        return False
    return any(_selector_match(s) for s in selectors)


def _load_notify_send():
    try:
        from notify import send as notify_send  # type: ignore

        return notify_send
    except Exception:
        pass
    import importlib.util

    search_dirs = []
    custom = _env("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, body: str) -> str:
    if not _should_notify():
        log("通知: 已跳过（全局开关或脚本选择未启用）")
        return "skipped"
    sender = _load_notify_send()
    if sender is None:
        log(f"{ICON_WARN} 通知: 未找到 notify.py，已跳过发送")
        return "unavailable"
    try:
        sender(title, body)
        log(f"{ICON_OK} 通知: 已发送")
        return "sent"
    except Exception as exc:
        log(f"{ICON_WARN} 通知发送失败: {type(exc).__name__}")
        return "failed"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class HttpClient:
    def __init__(self, timeout: int, ua: str) -> None:
        self.timeout = timeout
        self.ua = ua
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def set_cookie_header(self, cookie: str) -> None:
        # Parse into jar via SimpleCookie for robustness
        simple = http.cookies.SimpleCookie()
        try:
            simple.load(cookie)
        except Exception:
            # fallback: treat as raw Cookie header via dummy request helper
            simple = http.cookies.SimpleCookie()
            for part in cookie.split(";"):
                part = part.strip()
                if not part or "=" not in part:
                    continue
                k, v = part.split("=", 1)
                try:
                    simple[k.strip()] = v.strip()
                except Exception:
                    continue
        for morsel in simple.values():
            ck = http.cookiejar.Cookie(
                version=0,
                name=morsel.key,
                value=morsel.value,
                port=None,
                port_specified=False,
                domain="1point3acres.com",
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
            self.jar.set_cookie(ck)
            ck2 = http.cookiejar.Cookie(
                version=0,
                name=morsel.key,
                value=morsel.value,
                port=None,
                port_specified=False,
                domain=".1point3acres.com",
                domain_specified=True,
                domain_initial_dot=True,
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
            self.jar.set_cookie(ck2)

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        max_bytes: int = 2_000_000,
        allow_redirects: bool = True,
    ) -> Tuple[int, str]:
        hdrs = {
            "User-Agent": self.ua,
            "Referer": REFERER,
            "Connection": "close",
        }
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", None) or resp.getcode()
                raw = resp.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise RuntimeError("响应过大")
                charset = resp.headers.get_content_charset() or "utf-8"
                return int(status), raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read(max_bytes) if hasattr(exc, "read") else b""
            charset = "utf-8"
            try:
                if exc.headers:
                    charset = exc.headers.get_content_charset() or "utf-8"
            except Exception:
                pass
            text = raw.decode(charset, errors="replace") if raw else ""
            return int(exc.code), text
        except urllib.error.URLError as exc:
            raise RuntimeError(f"网络错误: {type(exc.reason).__name__}") from exc


def json_loads_safe(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except Exception as exc:
        raise RuntimeError("响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("响应 JSON 不是对象")
    return data


# ---------------------------------------------------------------------------
# 2captcha
# ---------------------------------------------------------------------------


def _captcha_post(api_key: str, fields: Dict[str, str], timeout: int) -> Dict[str, Any]:
    payload = dict(fields)
    payload["key"] = api_key
    payload["json"] = "1"
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://2captcha.com/in.php",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Connection": "close"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(65536).decode("utf-8", errors="replace")
    data = json.loads(raw)
    if str(data.get("status")) != "1":
        raise RuntimeError(f"2captcha 提交失败: {data.get('request')}")
    return data


def _captcha_poll(api_key: str, captcha_id: str, timeout: int) -> str:
    deadline = time.time() + CAPTCHA_POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(CAPTCHA_POLL_INTERVAL)
        query = urllib.parse.urlencode(
            {
                "key": api_key,
                "action": "get",
                "id": captcha_id,
                "json": "1",
            }
        )
        req = urllib.request.Request(
            f"https://2captcha.com/res.php?{query}",
            headers={"Connection": "close"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
        data = json.loads(raw)
        if str(data.get("status")) == "1":
            code = data.get("request")
            if not code:
                raise RuntimeError("2captcha 返回空结果")
            return str(code)
        if data.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"2captcha 取结果失败: {data.get('request')}")
    raise RuntimeError("2captcha 等待超时")


def solve_turnstile(api_key: str, pageurl: str, timeout: int, ua: str) -> str:
    submitted = _captcha_post(
        api_key,
        {
            "method": "turnstile",
            "sitekey": CF_TURNSTILE_SITEKEY,
            "pageurl": pageurl,
            "userAgent": ua,
        },
        timeout=timeout,
    )
    return _captcha_poll(api_key, str(submitted["request"]), timeout=timeout)


def solve_recaptcha(api_key: str, pageurl: str, sitekey: str, timeout: int) -> str:
    submitted = _captcha_post(
        api_key,
        {
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": pageurl,
        },
        timeout=timeout,
    )
    return _captcha_poll(api_key, str(submitted["request"]), timeout=timeout)


# ---------------------------------------------------------------------------
# public text (一言) for todaysay
# ---------------------------------------------------------------------------


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def format_hitokoto(data: Dict[str, Any]) -> str:
    text = normalize_public_text(data.get("hitokoto"))
    author = normalize_public_text(data.get("from_who"))
    source = normalize_public_text(data.get("from"))
    if not text:
        raise ValueError("一言响应缺少正文")
    if author and source:
        result = f"{text} —— {author}《{source}》"
    elif source:
        result = f"{text} ——《{source}》"
    elif author:
        result = f"{text} —— {author}"
    else:
        result = text
    result = normalize_public_text(result)
    if len(result) > 280:
        raise ValueError("一言格式化内容超过 280 字")
    return result


def local_fallback_text() -> str:
    override = normalize_public_text(_env(LOCAL_TEXT_ENV, ""))
    if override:
        return override[:280]
    return random.choice(LOCAL_FALLBACK_TEXTS)


def fetch_todaysay(*, dry_run: bool, timeout: int) -> Tuple[str, str]:
    fallback = local_fallback_text()
    if dry_run:
        return fallback, "本地预演（未访问一言）"
    try:
        req = urllib.request.Request(
            HITOKOTO_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": _user_agent(),
                "Connection": "close",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=min(timeout, HITOKOTO_TIMEOUT)) as resp:
            raw = resp.read(HITOKOTO_MAX_BYTES + 1)
            if len(raw) > HITOKOTO_MAX_BYTES:
                raise RuntimeError("oversized-response")
            data = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            raise RuntimeError("invalid-json")
        return format_hitokoto(data), "一言"
    except Exception as exc:  # noqa: BLE001 — policy fallback
        return fallback, f"本地回退（{type(exc).__name__}）"


# ---------------------------------------------------------------------------
# business helpers
# ---------------------------------------------------------------------------


def extract_identity(html: str) -> str:
    patterns = (
        r'"username"\s*:\s*"([^"]+)"',
        r'"name"\s*:\s*"([^"]+)"',
        r"欢迎您[，,]\s*([^<>\s]+)",
        r'title="访问我的空间">([^<]+)</a>',
        r"用户名[：:]\s*([^<\s]+)",
    )
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            name = normalize_public_text(m.group(1))
            if name and name.lower() not in {"null", "undefined"}:
                return name
    return ""


def login_with_cookie(client: HttpClient, cookie: str) -> str:
    client.set_cookie_header(cookie)
    status, html = client.request(CHECKIN_PAGE)
    if status == 503:
        raise RuntimeError("被 Cloudflare 拦截（HTTP 503）")
    if status != 200:
        raise RuntimeError(f"打开签到页失败: HTTP {status}")
    if "请登录后进行签到" in html:
        raise RuntimeError("Cookie 无效或已过期")
    identity = extract_identity(html)
    return identity


def login_with_password(
    client: HttpClient,
    username: str,
    password: str,
    api_key: str,
    timeout: int,
) -> str:
    status, home = client.request(BBS_HOME)
    if status == 503:
        raise RuntimeError("被 Cloudflare 拦截（HTTP 503）")
    if status != 200:
        raise RuntimeError(f"访问论坛失败: HTTP {status}")
    status, auth_html = client.request(AUTH_LOGIN_PAGE)
    if status != 200:
        raise RuntimeError(f"打开登录页失败: HTTP {status}")
    m = re.search(
        r'input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)"',
        auth_html,
    )
    if not m:
        raise RuntimeError("未找到 csrf_token")
    csrf_token = m.group(1)
    captcha = solve_recaptcha(
        api_key,
        pageurl=AUTH_LOGIN_PAGE,
        sitekey=LOGIN_RECAPTCHA_SITEKEY,
        timeout=timeout,
    )
    body = urllib.parse.urlencode(
        {
            "redirect_url": BBS_HOME,
            "csrf_token": csrf_token,
            "username": username,
            "password": password,
            "question_id": "0",
            "answer": "",
            "g-recaptcha-response": captcha,
            "submit": "登录",
        }
    ).encode("utf-8")
    status, text = client.request(
        AUTH_LOGIN_URL,
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://auth.1point3acres.com",
            "Referer": "https://auth.1point3acres.com/login",
        },
    )
    if status not in (200, 302):
        raise RuntimeError(f"登录失败: HTTP {status}")
    if "验证码填写错误" in text:
        raise RuntimeError("登录验证码错误")
    if "您的账号存在被盗风险" in text:
        raise RuntimeError("账号被要求强制微信登录，请改用 Cookie")
    if "用户名或密码错误" in text:
        raise RuntimeError("用户名或密码错误")
    return username


def check_need_checkin(client: HttpClient) -> Tuple[bool, str, str]:
    status, html = client.request(CHECKIN_PAGE)
    if status != 200:
        raise RuntimeError(f"读取签到状态失败: HTTP {status}")
    if "请登录后进行签到" in html:
        raise RuntimeError("会话无效：请登录后进行签到")
    identity = extract_identity(html)
    if "今日已签到" in html:
        return False, identity, "今日已签到"
    return True, identity, "待签到"


def do_checkin(
    client: HttpClient,
    api_key: str,
    todaysay: str,
    timeout: int,
) -> Tuple[str, bool]:
    captcha = solve_turnstile(
        api_key, pageurl=CHECKIN_PAGE, timeout=timeout, ua=client.ua
    )
    payload = {
        "qdxq": random.choice(EMOJI_LIST),
        "todaysay": todaysay,
        "captcha_response": captcha,
        "hashkey": "",
        "version": 2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    status, text = client.request(
        POST_CHECKIN_URL,
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": REFERER,
        },
    )
    if status != 200:
        raise RuntimeError(f"签到请求失败: HTTP {status}")
    if "人机验证出错，请重试" in text:
        raise RuntimeError("签到人机验证失败")
    data = json_loads_safe(text)
    msg = str(data.get("msg") or "")
    errno = data.get("errno")
    if errno == 0:
        return msg or "签到成功", False
    if msg == "您今天已经签到过了":
        return msg, True
    raise RuntimeError(msg or "签到业务失败")


def match_answer(question: str, answers: Dict[int, str]) -> Optional[int]:
    q = question.strip()
    if q not in QUESTIONS:
        return None
    expected = QUESTIONS[q]
    if isinstance(expected, list):
        for k, text in answers.items():
            if text in expected:
                return k
    else:
        for k, text in answers.items():
            if text == expected:
                return k
    return None


def do_daily_question(
    client: HttpClient, api_key: str, timeout: int
) -> Tuple[str, bool]:
    status, text = client.request(
        DAILY_QUESTION_URL,
        headers={"Referer": REFERER},
    )
    if status != 200:
        raise RuntimeError(f"获取每日一题失败: HTTP {status}")
    data = json_loads_safe(text)
    if data.get("errno") != 0 or data.get("msg") != "OK":
        msg = str(data.get("msg") or "获取题目失败")
        if "已答" in msg:
            return msg, True
        raise RuntimeError(msg)
    question_obj = data.get("question") or {}
    if not isinstance(question_obj, dict):
        raise RuntimeError("题目结构无效")
    qid = question_obj.get("id")
    qc = str(question_obj.get("qc") or "").strip()
    answers = {
        1: str(question_obj.get("a1") or ""),
        2: str(question_obj.get("a2") or ""),
        3: str(question_obj.get("a3") or ""),
        4: str(question_obj.get("a4") or ""),
    }
    answer_id = match_answer(qc, answers)
    if not qid or not answer_id:
        raise RuntimeError("题库未覆盖该题或选项未匹配，已跳过提交以免误答")
    captcha = solve_turnstile(
        api_key, pageurl=QUESTION_PAGE, timeout=timeout, ua=client.ua
    )
    payload = {
        "qid": qid,
        "answer": answer_id,
        "captcha_response": captcha,
        "hashkey": "",
        "version": 2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    status, text = client.request(
        DAILY_QUESTION_URL,
        method="POST",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": REFERER,
        },
    )
    if status != 200:
        raise RuntimeError(f"提交答案失败: HTTP {status}")
    if "人机验证出错，请重试" in text:
        raise RuntimeError("答题人机验证失败")
    result = json_loads_safe(text)
    msg = str(result.get("msg") or "")
    errno = result.get("errno")
    if errno == 0:
        return msg or "答题成功", False
    if msg == "您今天已经答过题了":
        return msg, True
    raise RuntimeError(msg or "答题业务失败")


# ---------------------------------------------------------------------------
# per-account runners
# ---------------------------------------------------------------------------


def run_account_dry(
    index: int,
    total: int,
    account: Dict[str, str],
    *,
    do_checkin_flag: bool,
    do_question_flag: bool,
    has_captcha: bool,
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始（预演）——")
    stages = 1 + int(do_checkin_flag) + int(do_question_flag)
    stats = {
        "total": stages,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": label,
        "ok": True,
        "status": "success",
        "message": "预演通过",
        "elapsedMs": 0,
        "stats": stats,
    }

    stage = 1
    log_stage(stage, "校验凭据与验证码配置")
    if account.get("mode") == "cookie":
        if not account.get("cookie"):
            stats["failed"] += 1
            result["ok"] = False
            result["status"] = "failure"
            result["message"] = "Cookie 为空"
            log(f"  {ICON_FAIL} Cookie 为空")
            result["elapsedMs"] = int((_now() - started).total_seconds() * 1000)
            return result
        log(f"  {ICON_OK} Cookie 格式已接受（不输出内容）")
    else:
        log(f"  {ICON_OK} 用户名密码格式已接受（不输出内容）")
    if not has_captcha:
        log(f"  {ICON_WARN} 未配置 {CAPTCHA_ENV}：真实执行签到/答题需要 2captcha")
    else:
        log(f"  {ICON_OK} 已检测到验证码密钥（不输出）")
    stats["success"] += 1

    if do_checkin_flag:
        stage += 1
        log_stage(stage, "预演签到", "跳过真实网络与 Turnstile")
        todaysay, source = fetch_todaysay(dry_run=True, timeout=_http_timeout())
        log(f"  {ICON_SKIP} 断网预演：将请求签到接口；todaysay 来源={source}，长度={len(todaysay)}")
        stats["skipped"] += 1

    if do_question_flag:
        stage += 1
        log_stage(stage, "预演每日答题", "跳过真实网络与 Turnstile")
        log(f"  {ICON_SKIP} 断网预演：将拉取题目并用内置题库匹配后提交")
        stats["skipped"] += 1

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(
    index: int,
    total: int,
    account: Dict[str, str],
    *,
    api_key: str,
    do_checkin_flag: bool,
    do_question_flag: bool,
    timeout: int,
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始 ——")
    stages = 1 + int(do_checkin_flag) + int(do_question_flag)
    stats = {
        "total": stages,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": label,
        "ok": False,
        "status": "failure",
        "message": "",
        "elapsedMs": 0,
        "stats": stats,
    }
    messages: List[str] = []
    client = HttpClient(timeout=timeout, ua=_user_agent())
    try:
        stage = 1
        t0 = _now()
        log_stage(stage, "登录会话")
        if not api_key and (do_checkin_flag or do_question_flag):
            raise RuntimeError(f"缺少 {CAPTCHA_ENV}，无法完成人机验证")
        if account.get("mode") == "cookie":
            identity = login_with_cookie(client, account["cookie"])
        else:
            identity = login_with_password(
                client,
                account["username"],
                account["password"],
                api_key=api_key,
                timeout=timeout,
            )
        if identity:
            result["identity"] = identity
            log(
                f"  {ICON_OK} 登录成功，身份: {identity}"
                f"（耗时 {int((_now() - t0).total_seconds() * 1000)}ms）"
            )
        else:
            log(
                f"  {ICON_OK} 登录成功（未返回公开身份，使用 {label}；"
                f"耗时 {int((_now() - t0).total_seconds() * 1000)}ms）"
            )
        stats["success"] += 1

        if do_checkin_flag:
            stage += 1
            t1 = _now()
            log_stage(stage, "每日签到")
            need, page_identity, status_msg = check_need_checkin(client)
            if page_identity and not identity:
                identity = page_identity
                result["identity"] = identity
            if not need:
                stats["alreadyComplete"] += 1
                messages.append(status_msg)
                log(
                    f"  {ICON_DONE} {status_msg}"
                    f"（耗时 {int((_now() - t1).total_seconds() * 1000)}ms）"
                )
            else:
                todaysay, source = fetch_todaysay(dry_run=False, timeout=timeout)
                log(f"  todaysay 来源={source}，长度={len(todaysay)}（不输出正文）")
                msg, already = do_checkin(client, api_key, todaysay, timeout)
                if already:
                    stats["alreadyComplete"] += 1
                    log(f"  {ICON_DONE} {msg}")
                else:
                    stats["success"] += 1
                    log(f"  {ICON_OK} {msg}")
                messages.append(msg)

        if do_question_flag:
            stage += 1
            t2 = _now()
            log_stage(stage, "每日答题")
            msg, already = do_daily_question(client, api_key, timeout)
            if already:
                stats["alreadyComplete"] += 1
                log(
                    f"  {ICON_DONE} {msg}"
                    f"（耗时 {int((_now() - t2).total_seconds() * 1000)}ms）"
                )
            else:
                stats["success"] += 1
                log(
                    f"  {ICON_OK} {msg}"
                    f"（耗时 {int((_now() - t2).total_seconds() * 1000)}ms）"
                )
            messages.append(msg)

        result["ok"] = True
        result["status"] = "success"
        result["message"] = "；".join(messages) if messages else "全部完成"
    except Exception as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = str(exc)[:200]
        log(f"  {ICON_FAIL} {result['message']}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{result['identity']} 统计: 总任务={stats['total']} "
        f"成功={stats['success']} 已完成={stats['alreadyComplete']} "
        f"跳过={stats['skipped']} 失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def main() -> int:
    task_start = _now()
    dry = _is_dry_run()
    mode = "dry-run" if dry else "live"
    timeout = _http_timeout()
    do_checkin_flag = _env_flag(ENABLE_CHECKIN_ENV, True)
    do_question_flag = _env_flag(ENABLE_QUESTION_ENV, True)
    api_key = _env(CAPTCHA_ENV, "").strip()

    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(
        f"子任务: 签到={'开' if do_checkin_flag else '关'} "
        f"答题={'开' if do_question_flag else '关'}"
    )

    notify_status = "skipped"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    success_accounts = 0
    failed_accounts = 0
    final_status = "failure"

    try:
        if not do_checkin_flag and not do_question_flag:
            raise RuntimeError(
                f"未启用任何子任务：请至少开启 {ENABLE_CHECKIN_ENV} 或 {ENABLE_QUESTION_ENV}"
            )
        accounts, source_env = load_accounts()
        if not accounts:
            raise RuntimeError(
                f"缺少账号凭据：请配置 {COOKIE_ENV}（推荐，每行一个 Cookie），"
                f"或可选 {ACCOUNT_ENV}（每行 用户名&密码）"
            )
        log(f"账号数量: {len(accounts)}（来源 {source_env}）")
        if not dry and not api_key:
            raise RuntimeError(
                f"真实执行需要 {CAPTCHA_ENV}（2captcha API Key），"
                "用于 Turnstile/reCAPTCHA 人机验证"
            )

        for idx, account in enumerate(accounts, start=1):
            if dry:
                account_results.append(
                    run_account_dry(
                        idx,
                        len(accounts),
                        account,
                        do_checkin_flag=do_checkin_flag,
                        do_question_flag=do_question_flag,
                        has_captcha=bool(api_key),
                    )
                )
            else:
                account_results.append(
                    run_account_live(
                        idx,
                        len(accounts),
                        account,
                        api_key=api_key,
                        do_checkin_flag=do_checkin_flag,
                        do_question_flag=do_question_flag,
                        timeout=timeout,
                    )
                )

        success_accounts = sum(1 for r in account_results if r.get("ok"))
        failed_accounts = len(account_results) - success_accounts
        if failed_accounts:
            exit_code = 1

        print("-" * 56)
        log("任务统计")
        log(f"  账号: 总数={len(account_results)} 成功={success_accounts} 失败={failed_accounts}")
        sub_success = sum(int((r.get("stats") or {}).get("success") or 0) for r in account_results)
        sub_done = sum(
            int((r.get("stats") or {}).get("alreadyComplete") or 0) for r in account_results
        )
        sub_skip = sum(int((r.get("stats") or {}).get("skipped") or 0) for r in account_results)
        sub_fail = sum(int((r.get("stats") or {}).get("failed") or 0) for r in account_results)
        log(
            f"  子任务: 成功={sub_success} 已完成={sub_done} "
            f"跳过={sub_skip} 失败={sub_fail}"
        )

        if dry:
            final_status = "dry-run"
            summary_line = (
                f"预演完成：账号总数 {len(account_results)}，"
                f"成功 {success_accounts}，失败 {failed_accounts}"
            )
            for r in account_results:
                if r.get("ok"):
                    r["message"] = "预演通过"
                    log(f"  {ICON_OK} 账号{r['index']}: 预演通过")
        elif failed_accounts == 0:
            final_status = "success"
            summary_line = (
                f"全部成功：账号总数 {len(account_results)}，"
                f"成功 {success_accounts}，失败 0"
            )
        elif success_accounts == 0:
            final_status = "failure"
            summary_line = (
                f"全部失败：账号总数 {len(account_results)}，"
                f"成功 0，失败 {failed_accounts}"
            )
        else:
            final_status = "partial-failure"
            summary_line = (
                f"部分失败：账号总数 {len(account_results)}，"
                f"成功 {success_accounts}，失败 {failed_accounts}"
            )

        detail_lines = []
        for r in account_results:
            ident = r.get("identity") or ("账号" + str(r.get("index")))
            state = "成功" if r.get("ok") else "失败"
            detail_lines.append(
                f"- {ident}：{state}（{r.get('message') or ''}）"
            )
        body = "\n".join([summary_line, *detail_lines])
        notify_status = send_notification(SCRIPT_NAME, body)

    except Exception as exc:
        exit_code = 1
        final_status = "configuration-error" if not account_results else "failure"
        summary_line = f"配置或执行错误: {str(exc)[:200]}"
        log(f"{ICON_FAIL} {summary_line}")
        notify_status = send_notification(SCRIPT_NAME, summary_line)
        success_accounts = sum(1 for r in account_results if r.get("ok"))
        failed_accounts = (
            len(account_results) - success_accounts
            if account_results
            else 1
        )

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    log(f"结束时间: {_iso(task_end)}")
    log(f"总耗时: {elapsed_ms}ms")
    log(f"通知状态: {notify_status}")
    log(f"最终状态: {final_status}")

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "name": SCRIPT_NAME,
        "status": final_status,
        "mode": mode,
        "accounts": len(account_results),
        "success": success_accounts if account_results else 0,
        "failed": failed_accounts if account_results else (0 if exit_code == 0 else 1),
        "notify": notify_status,
        "elapsedMs": elapsed_ms,
        "exitCode": exit_code,
    }
    print(f"TASK_SUMMARY={json.dumps(task_summary, ensure_ascii=False)}")
    return exit_code


# Embedded question bank from upstream src/questions.py (GPL-3.0)

QUESTIONS = {'Apollo 11是哪一年登月的？': '1969', 'Miami University在哪个城市': 'Oxford, Ohio', 'Miami University在哪个城市?': 'Oxford, Ohio', 'Negotiate 工资的时候，哪种做法有利于得到更大的包裹？': '精读地里谈工资宝典，知己知彼，百战不殆', 'Speak for yourself 是什么意思': '请你不要代表其他人讲话，“那是你自己的看法，我可不这样想”', 'Which company is the largest single-site employer in the US?': 'Disney World', 'which state is University of Miami located?': 'Florida', '地里发帖可以隐藏内容。假如要设置200积分以上才可以看到，下面哪个语法正确？': '[hide=200]想要隐藏的内容[/hide]', '地里面经数目最多的是哪家公司？': 'Amazon', '地里数据科学类职位面经放在在什么版最合理？': '数科面经版', '给论坛ios或者安卓手机应用留评价如何获取50大米？': '以上步骤都需要', '公司之间级别对应，如下哪个是错误的？': 'Facebook L6 = Facebook E6', '关于旧金山市中心描述，下面哪个不正确？': '旧金山创业公司很多，被称为“硅谷”', '关于帖子内容审核，哪种说法是正确的': '这些都正确。', '回答别人的私信提问还需要消耗我5大米怎么办？': '直接在版面回答，这样大家都能看见', '加州大学有多个分校，下面哪个成立时间最短？': 'UC Merced', '论坛鼓励如何发面经？': '以上都正确', '美国哪个州具有地中海气候？': '加利福尼亚', '美国哪个州没有夏令时？': '亚利桑那州', '哪些行为会被禁言和封号？': '这些都会被禁言封号', '哪种选校策略最合理？': '根据自己下一步职业和学业目标，参考地里数据和成功率，认真斟酌', '求内推如何作死？': '这些都会作死', '如何建设性的讨论有争议的话题？': '这些办法轮流来', '下面关于论坛使用的说法，哪种是错误的？': '在手工加分的帖子里，多次回复试图得到重复加分，不会被系统检测到。', '下面几个州，哪个离美国首都最远？': 'North Carolina', '下面加州哪个地点离墨西哥最近？': '圣迭戈', '下面哪部作品是喜剧？': '仲夏夜之梦', '下面哪个Ivy League，离东海岸最远？': 'Cornell', '下面哪个machine learning的模型不是supervised learning？': 'Clustering', '下面哪个城市不是典型的温带海洋性气候？': '波士顿', '下面哪个城市没有SUNY（纽约州立大学）校区？': 'Fulton', '下面哪个大学不在Virginia/DC附近': 'Washington and Jefferson College', '下面哪个大学实际上不存在？': 'University of Michigan, Twin City', '下面哪个大学在华盛顿州？': 'University of Washington', '下面哪个公司的streaming service不是会员subscription付费模式运营的？': 'Tubi', '下面哪个公司的主要收入不是来自广告？': 'Apple', '下面哪个公司总部不在湾区？': 'snapchat', '下面哪个公司总部在圣地亚哥？': 'Qualcomm', '下面哪个情况，不会消耗你的积分？': '看到干货帖子和精华回复，给作者加分！', '下面哪个说法错误？': ['芝加哥是美国著名的雨城', '中国驻纽约领事馆位于法拉盛中国城，周围全是好吃的！'], '下面哪个童话故事不是安徒生写的？': '尼尔斯骑鹅旅行记', '下面哪个学术会议不是机器学习领域的？': 'ICSE', '下面哪个州，对公司友好，所以吸引了美国很多公司注册？': '特拉华', '下面哪个州，没有income tax?': 'Nevada', '下面哪个州，没有state income tax?': ['Alaska', 'Florida', 'New Hampshire'], '下面哪个州，有state income tax': ['Mississippi', 'North Dakota'], '下面哪个州，有state income tax on wages': ['Mississippi', 'North Dakota'], '下面哪个州不属于西海岸三州？': '内华达', '下面哪个州冬天最暖和？': 'Oklahoma', '下面哪个州里有Disney World？': 'Florida', '下面哪个州在美国西海岸': 'Washington', '下面哪个专业，不是STEM，OPT没法延期？': '教育学', '下面哪个作家是英国人？': 'Charles Dickens', '下面哪家公司的总部不在西雅图': '波音', '下面哪家公司的总部不在西雅图?': '波音', '下面哪类版块，可以拉群，而且不会被警告扣分？': '学友工友、找室友或者版聚本地', '下面哪类版块可以拉群，而且不会被警告扣分？': '学友工友、找室友或者版聚本地', '下面哪所大学所在城市不是波士顿？': ['Boston College', 'MIT'], '下面哪所纽约高校的主校区坐落于中央公园附近？': 'Columbia University', '下列哪一项首府与州的对应关系是正确的？': '俄克拉何马州 - 俄克拉何马城', '下面哪种方法，可以妥妥拿到积分？': '这些全都可以', '下面哪种画像，最符合论坛大多数用户群体？': '论坛用户是多元的，任何单一画像都无法代表大多数用户', '下面哪种情况，管理员会按照你的要求，进行删帖？': '这些情况全都不删帖！', '下面哪种行为，在地里会被扣光积分，甚至封号？': '这些全都会', '想找室友或者当房东，帖子发在哪里？': '租房广告|找室友版', '休斯敦在美国以什么工业出名?': '宇航', '一亩三分地发帖可以用hide语法隐藏内容。下面哪个写法正确？': '柯南的名字是[hide=200]工藤新一[/hide]', '一亩三分地鼓励如何发面经？': '以上都正确', '一亩三分地是哪年创立的？': '2009', '一亩三分地是谁创立的？': 'Warald', '以下哪个不是Linux操作系统？': 'Vue', '以下哪个美国城市不靠海？': '亚特兰大', '以下哪个神经网络不能处理语音数据？': '以上都可以', '以下哪个说法正确？': '一篇一作指的是有一篇第一作者的文章', '以下哪所学校不位于南部？': '凯斯西储大学', '以下哪所学校是美国第一所研究型大学？': '约翰霍普金斯大学', '以下哪一位名人不是英国人？': 'Louis Pasteur(他发现了巴斯德高温消毒法)', '以下哪种不是Modes of dataflow?': 'tcp/ip', '以下哪种内容，一亩三分地没有？': 'Military 军版', '以下有哪一个包是pytorch下的？（就是torch.xx）': 'cuda', '音乐家贝多芬出生于哪国？': '德国', '有的帖子只有某非主流群体才能回答，因此我回帖：“你不该在一亩三分地发这种帖子，没用的！”。为什么这样做没有建设性？': '这些，和其他更多理由', '遇到跟自己不同的意见怎么办？': '保持开放包容的心态，看看对方内容是否有可取之处。实在不喜欢就叉掉页面看点别的。', '在Linkedin上求内推如何作死': '这些都会作死', '在论坛发slack群，qq群，微信群，任何站外讨论方式，会如何？': '以上都正确', '在一亩三分地发帖，需要遵守哪些规则？': '以上都需要遵守。', '在一亩三分地论坛参与社区讨论需要遵守哪些规则？': '这些全都要遵守', '参与讨论时需要遵守哪些规则？': '这些全都要遵守', '普通用户参与维护社区文明秩序的方法有哪些': '以上都是', '在一亩三分地发帖，不需要遵守哪些规则？': '世界唯一正确的道德评判标准', '普通用户如何参与维护社区文明秩序？': '点楼层内”举报“', '下面哪种发帖方式不适合一亩三分地，应该杜绝？': '遇到有权限设置的帖子，我积分不够也不想攒积分，发些“看不到啊”、“积分不够啊”之类的回复，水掉论坛', '如何文明礼貌的表达不同意见？': '这些都可以', '以下哪种内容，一亩三分地不允许？': ['小广告、导流软广', '色情图片和录像'], '论坛大米有什么用？': '这些都可以', '为什么有时候一亩三分地的数据跟我感觉的平均情况相差很大？': '这些都包括', '下面哪种行为，在地里会被扣光积分甚至封号？': '这些全都会', '使用论坛遇到问题，如何寻求帮助？': '这些都可以', '以下哪些说法正确？': '全都是错的', '关于积分的说法，哪个正确？': '以上都对', '为什么我们不鼓励用谐音或者各种拐弯抹角的说法来指代公司或者学校名称？比如：“湾区某元音开头和结尾公司”': '写成这样子，别人看不懂，也搜不到。如果别人也这样写，你也看不懂、搜不到。信息没法分享和交流。', '使用一亩三分地遇到奇怪的问题，比如网站和app里内容不一致等，如何处理？': '这些都可以', '有的人征友条件也太苛刻了怎么办？': '这些都包括，不然我们上哪里看可爱的小哥哥小姐姐呢？', '如何说服论坛里意见不同的用户改变 TA 的意见？': '从因特网存在开始，就不存在能被别人说服的用户。改变只能来源于自身。', '关于地里的违规警告，哪种说法是错误的？': '这些都是错误的', '一亩三分地发帖可以选择内容用hide进行隐藏。正确隐藏语法是：': '两人第一次华山论剑，争的是荣名与[hide=188]《九阴真经》[/hide]；', '关于论坛小米的说法，哪些正确？': '小米通过参与社区讨论获得，可以计入总积分，会提升阅读权限。', '新人积分不够。下面哪些做法正确？': '分享干货、签到答题、参加活动等，争取早日攒够积分。', '下面哪些方式，可以获得积分奖励？': '这些行为都被提倡和鼓励，也可获得积分奖励', '把一亩三分地介绍给朋友的正确姿势不包括什么？': '直接把我的账号密码给朋友用', '关于论坛账号分享的说法，哪些正确?': '这些都不对', '如果我把论坛积分隐藏内容公开发出来会怎么样？': '会被扣分，情节严重者会封号', '以下关于帖子审核，哪些说法正确？': '这些都不正确', '在论坛发slack群、qq群、微信群等任何站外讨论方式，会如何？': '以上都正确', '关于 网络 Troll 的定义，下面哪些说法正确？': '以上都对', '哪些行为有可能被禁言和封号？': '购买了VIP通行证，作为付费用户，违反网站规则。', '一亩三分地鼓励和提倡哪些发帖方式？': '读一下各个版块的置顶信息，了解网站规则。按规则发帖，与其他论坛用户高效交流', '在Linkedin上求内推如何作死?': '这些都会作死', '哪些人群在一亩三分地上不可能存在？': '这些都可能存在，并且尊重其他人文明发言的空间', '希望帖子被更多人看到、注意到，如何操作？': '这些都可以', '一亩三分地里可以购买VIP通行证，位于网站上方导航栏 -> VIP。关于VIP，下面哪些说法正确？': '以上都正确', '如果不希望大家继续讨论我发表的帖子，应该如何操作？': '帖子首楼右下角->”道具“中选择”关贴卡“，使用在自己发的主贴上。', '想找室友或者作为房东想找租客，帖子发在哪里？': '租房广告|找室友版', '在国内可以访问一亩三分地吗？': '可以', '为什么有人要讨论某个我觉得没用的问题？': '这些都包括，单个用户不能代表论坛全部用户', '违反论坛规则，被封号了怎么办？': '重新注册账号，这次认真遵守论坛规则，文明参与社区讨论', '是否可以在论坛发slack群、qq群、微信群等站外讨论方式？': '以上都正确', '以下关于 Troll 的说法，哪些正确？': '看见 troll 可以点击“thumb down" 表示反对，也可以点击“举报”', '在论坛发现 bug的时候，怎么做最有效？': '发工单或者在公民公社版开帖子，仔细描述遇到的情况，这样才能尽快 fix这个bug', '遇到不文明言论，如何合理应对？': ['这些违反论坛规则，被封号了怎么办？都是', '这些都是'], '在论坛上看见不符合我认知的帖子，怎么办？': '这些都包括。', '哪些方法可以保护你的账号？': '这些方法都会有帮助。', '下面哪种方式，可以获得积分奖励，且不会被扣分和警告？': '分享干货，无论是录取信息、面经题目、工资数据，还是各种生活经验。', '如何给论坛提建议？': '可以在论坛的"联系我们”页面，给论坛提出建议。', 'Disagree agreeably 是什么意思？': '这些都包括。', '下面论坛规则，下面哪种说法是正确的？': '有的版块发帖消耗积分。如果试图跨区发帖躲开限制，在帖子被挪到正确的版块后，仍可能会被扣分。', '谈判工资时，哪种做法有利于得到更大的包裹？': '精读工资谈判宝典：https://www.1point3acres.com/bbs/thread-286214-1-1.html 知己知彼，百战不殆', '一亩三分地里有哪些方面的干货信息？': '这些都有', '哪些行为可能被禁言和封号？': '这些都可能禁言封号', '下面哪些言论，在一亩三分地里算违规？': '这些以偏概全的说法都不推荐', '为什么讨论时不建议使用”凡尔赛“，”学渣“， ”一线土著“之类的标签？': '这些都包括', '如果希望匿名发帖，以下哪些说法正确？': '这些都正确', '在什么地方发帖可以不受任何限制？': '这些地方都有各自的社区规则、发帖都有限制。', '一亩三分地发面经的规则有哪些？': '以上都正确', '关于地里积分类型“萝卜”的说法，哪些正确？': '这些都对', '关于论坛账号的说法，哪些正确？': '这些都不对', '回答别人的私信提问还需要消耗我1鳄梨怎么办？': '除非涉及隐私并且无法”脱敏“处理，否则应该直接在版面回答，这样大家都能看见。', '哪种快速解锁全部论坛权限的姿势是错误的？': '借用/共享朋友的账号（你和朋友都将失去这个账号）', '为什么一亩三分地除了租房广告、找室友学友飞友工友、本地版聚等少数版块外，其他数板块都不允许拉群？': '以上全都理解并接受', '一亩三分地里可以购买VIP通行证，位于网站上方导航栏 -> VIP。关于VIP，下面哪些说法错误？': 'VIP是“免责金牌”，在地里不受规则约束，可以为所欲为', '一亩三分地社区文明，应该由谁来维护？': '维护社区文明，人人有责。社区用户可以平心静气讨论，不引战，不恋战，举报不文明行为。', '对于有争议性的话题，如何有建设性的讨论？': '这些办法轮流来', '关于关闭帖子的说法，哪些正确？': '这些都正确', '我觉得自己最可以代表哪种群体？': '我只代表自己', '下面关于论坛积分（大米）的说法，哪种是错误的？': '抖包袱版看帖，不会消耗积分', '留学申请选校时，哪种策略最合理？': '根据自己的职业目标，参考地里Offer多多的录取数据，找出自身特点和优势。', '如何对贴主表达支持？': '这些都可以', '我想对论坛提出反馈，哪些说法不正确？': '在哪个版块想到，就发在哪个版块，反正版务组会阅读每个帖子的。', '下面哪些行为会被扣分？': '这些都会被扣分', '希望你能问一个具体的问题 https://www.1point3acres.com/bbs/forum.php?mod=viewthread&tid=130271 这篇置顶帖子讲了什么？': '如果希望最高效的解决自己遇到的问题，建议仔细阅读原贴，公开提问，细化问题->得到答案->付出行动。这样对自己和对别人都是最优解。', '以下哪些对自己感受的表述，可以代表整个人群？': '每个人的感受，仅能代表自己', '在下面哪些板块里留微信号等各种联系方式，事后可以要求版主删除？': '绝大多数板块禁止留微信、拉群，如果你非要发出来，那就永远不删。如果需要私聊，建议发站内信。', '一亩三分地有多个微信公众号，除了主号“一亩三分地Warald”之外，以下哪些也是？': '这些都是', '论坛为什么屏蔽某些关键字？': '挡住垃圾广告、减少戾气攻击、杜绝不符合国家法律法规和社区文明准则的内容。', '关于编辑帖子的说法，哪些正确？': '这些都正确', '如果非常希望发表不符合一亩三分地论坛规则或国家法规的言论怎么办?': '这些都可以', '如何重设论坛密码？': '这些都可以', '在网上互怼5 个来回，仍然说服不了对方，怎么办？': '承认彼此意见不同。离开这个帖子，不再继续参与。', '关于加分的说法，哪些正确？': '不同版有不同的规则。干货内容上限会更高', '如果被引战，钓鱼，人身攻击，该怎么办？': '举报', '如果网暴他人，贴出别人隐私信息，以下哪些说法是正确的？': '会被删帖，扣分，情节严重的会被禁言、封号', '如果希望发布实习群，应该发在哪个版？': '入职圈', '如果希望使用论坛道具，关于兑换鳄梨，以下说法哪个最正确？': '以上都正确', '如果希望找飞友，应该发在哪个版': '学友飞友', '有的帖子感觉只适用于某些非主流群体，为什么我不能回帖说：“你不该在一亩三分地发这种帖子，没用的！”？': '以上这些都有道理。', '抖包袱版存在的目的是？': '让工资信息透明化，帮助有需求的人们更好的 negotiate 到最大的包', '什么样的内容会得到其他用户的大量加分？': '这些都包括。', '急着求职了，想看帖子，如何可以快速获得积分？': '这些都可以', '关于论坛通行证的说法，哪个最正确？': '以上都正确', '如果希望发帖讨论和室友/邻居的关系，应该发在哪个版？': '人际', '有的帖子一看就不是论坛常见人群发的，应该如何回帖？': '默默关掉，不回帖', '抖包袱版存在的目的是': '让工资信息透明化，帮助有需求的人们更好的 negotiate 到最大的包', '给自己发的帖子添加到相关的热门话题，哪些说法是错误的？': '可能会被扣分，视情况，最多扣 10 分', '遇到特别奇葩的帖子，以下哪些做法是错误的？': '回帖：肯定是气氛组在冲业绩', '如果焦虑，抑郁，不想干活，觉得无趣，想吐槽，可以在哪个版发帖？': '心理健康', '按地区发帖和浏览有哪些好处？': '可以更好的获取周围地区的分类信息', '为什么有时候被警告会造成禁言，有时候又不会？': '累计警告超过一定数量后，会自动被禁言 N 天', '求购或者出手某专业复习资料': '跳蚤市场', '如果希望找人一起打球，应该发在哪个版': '玩友募集', '跨区发帖后，会有什么结果？': '这些都正确', '如果希望招人加入family plan，或者加入别人的 plan，应该发在哪个版': '跳蚤市场', '在论坛下载的附件有密码怎么办？': '关注一亩三分地公众号，获取解压密码', '给自己发的帖子添加到无关的热门话题，哪些说法是正确的？': '可能被扣分，视情况，最多扣 10 分', '关闭帖子': '这些都正确'}



if __name__ == "__main__":
    sys.exit(main())
