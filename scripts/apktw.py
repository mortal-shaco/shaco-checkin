#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: apk.tw每日签到
# cron: 19 9 * * *
#
# 来源：ychsieh95/auto-check-in apktw/apktw.py（MIT）
# https://github.com/ychsieh95/auto-check-in
# 提交：48f49aefc706f91f4b884cf95b21f90d5d5626b8
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2026 ychsieh95
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
"""apk.tw（Discuz!）每日签到 — 青龙维护版。

功能清点（相对上游 apktw/apktw.py + README 入口流程）：
- 用户名密码登录（登录页 formhash；图像验证码或 Cloudflare Turnstile 经 2captcha）
- Cookie 会话复用（环境变量提供 Cookie，不再默认 pickle 落盘）
- 校验登录态（home.php?mod=spacecp）
- 每日 dsu_amupper 签到，解析累计/连续天数与今日是否已签
- 读取用户组与积分摘要（鑽石/碎鑽/經驗/金豆等，只读展示）
- 移除对私有 i18n / BeautifulSoup 依赖、默认 .session_cookies.pkl、原始响应片段打印
- 多账号换行、APKTW_DRY_RUN 断网预演、超时、业务核验、时间轴日志、青龙通知、TASK_SUMMARY

APKTW_ACCOUNT（必填）：每个非空行一个账号。
  1) 用户名|密码
  2) 用户名|密码|2captcha密钥（仅按最后一个疑似密钥拆分）
  3) 备注|用户名|密码[|2captcha密钥]
  4) 完整 Cookie（须含 auth= 或 saltkey=）；可选 备注|Cookie
全局可选 APKTW_2CAPTCHA_KEY；仅当账号行未带密钥时用于密码登录。
APKTW_COOKIE：兼容别名，仅当 APKTW_ACCOUNT 为空时读取（Cookie 行格式同上）。
APKTW_DRY_RUN=1：完全断网预演。
建议 Cron：0 8 * * *。不打印密码、Cookie、Token、验证码密钥或原始响应。
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
        _ql_notify_identities = ('22d5d26fa295b1ea', 'scripts/apktw.py', 'apktw.py', 'apktw')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_NAME = "apk.tw每日签到"
CATALOG_ID = "22d5d26fa295b1ea"
SCRIPT_FILENAME = "candidate.py"
BASE_URL = "https://apk.tw"
LOGIN_URL = f"{BASE_URL}/member.php?mod=logging&action=login"
LOGIN_POST_URL = (
    f"{BASE_URL}/member.php?mod=logging&action=login&loginsubmit=yes"
)
SECCODE_MODID = "member::logging"
TWOCAPTCHA_SUBMIT_URL = "https://2captcha.com/in.php"
TWOCAPTCHA_RESULT_URL = "https://2captcha.com/res.php"
TWOCAPTCHA_POLL_INTERVAL = 5
TWOCAPTCHA_POLL_TIMEOUT = 120
MAX_LOGIN_ATTEMPTS = 3
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DRY_RUN_ENV = "APKTW_DRY_RUN"
ACCOUNT_ENV = "APKTW_ACCOUNT"
COOKIE_ALIAS_ENV = "APKTW_COOKIE"
CAPTCHA_ENV = "APKTW_2CAPTCHA_KEY"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
CREDIT_FIELDS = {
    "1": "鑽石",
    "2": "碎鑽",
    "3": "經驗",
    "4": "幫助",
    "5": "技術",
    "6": "貢獻",
    "7": "宣傳",
    "8": "金豆",
}


class SafeError(Exception):
    """脱敏业务/配置错误。"""


@dataclass
class Account:
    index: int
    label: str
    username: str = ""
    password: str = ""
    captcha_key: str = ""
    cookie: str = ""

    @property
    def mode(self) -> str:
        return "cookie" if self.cookie else "password"

    def secrets(self) -> List[str]:
        values = [self.password, self.captcha_key, self.cookie]
        return [v for v in values if v]


def now() -> datetime:
    return datetime.now()


def ts(dt: Optional[datetime] = None) -> str:
    return (dt or now()).strftime("%H:%M:%S")


def iso(dt: Optional[datetime] = None) -> str:
    return (dt or now()).strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{ts()}] {message}", flush=True)


def log_stage(index: int, title: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    log(f"阶段{index} {title}{suffix}")


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def env_truthy(name: str, default: bool = False) -> bool:
    raw = env(name)
    if not raw:
        return default
    low = raw.lower()
    if low in TRUE_VALUES:
        return True
    if low in FALSE_VALUES:
        return False
    raise SafeError(f"{name} 须为开关值（1/0、true/false）")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def redact(text: str, secrets: List[str]) -> str:
    out = clean_text(text)
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 4:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(
        r"(?i)(cookie|token|authorization|session|password|auth|key)=([^;\s&]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable())[:240]


def looks_like_cookie(text: str) -> bool:
    low = text.lower()
    if "=" not in text:
        return False
    return (
        "auth=" in low
        or "saltkey=" in low
        or ";" in text
        or re.search(r"(?i)\b[a-z0-9_]*auth\b\s*=", text) is not None
    )


def looks_like_captcha_key(text: str) -> bool:
    value = text.strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{32}", value))


def parse_account_line(line_no: int, text: str, global_captcha: str) -> Account:
    label = ""
    payload = text
    if "|" in text:
        head, rest = text.split("|", 1)
        head = head.strip()
        rest = rest.strip()
        if head and looks_like_cookie(rest) and not looks_like_cookie(head):
            label = head
            payload = rest
        elif head and not looks_like_cookie(text) and text.count("|") >= 2:
            # 备注|用户名|密码[...]
            parts = [p.strip() for p in text.split("|")]
            captcha = ""
            if looks_like_captcha_key(parts[-1]):
                captcha = parts[-1]
                parts = parts[:-1]
            if len(parts) < 3:
                raise SafeError(f"第 {line_no} 行账号格式无效")
            label = parts[0]
            username = parts[1]
            password = "|".join(parts[2:])
            if not username or not password:
                raise SafeError(f"第 {line_no} 行用户名或密码为空")
            return Account(
                index=0,
                label=label or username,
                username=username,
                password=password,
                captcha_key=captcha or global_captcha,
            )

    if looks_like_cookie(payload):
        if any(ord(ch) < 32 for ch in payload):
            raise SafeError(f"第 {line_no} 行 Cookie 含控制字符")
        return Account(
            index=0,
            label=label or f"账号Cookie",
            cookie=payload,
        )

    if "|" not in payload:
        raise SafeError(
            f"第 {line_no} 行格式无效：密码登录须为 用户名|密码，"
            "Cookie 行须含 auth= 或 saltkey="
        )
    left, right = payload.split("|", 1)
    username = left.strip()
    password = right.strip()
    captcha = ""
    if "|" in password:
        maybe_user_pass, maybe_key = password.rsplit("|", 1)
        if looks_like_captcha_key(maybe_key):
            password = maybe_user_pass.strip()
            captcha = maybe_key.strip()
    if not username or not password:
        raise SafeError(f"第 {line_no} 行用户名或密码为空")
    if any(ord(ch) < 32 for ch in password):
        raise SafeError(f"第 {line_no} 行密码含控制字符")
    return Account(
        index=0,
        label=label or username,
        username=username,
        password=password,
        captcha_key=captcha or global_captcha,
    )


def load_accounts() -> List[Account]:
    raw = env(ACCOUNT_ENV)
    source = ACCOUNT_ENV
    if not raw:
        raw = env(COOKIE_ALIAS_ENV)
        source = COOKIE_ALIAS_ENV
    if not raw:
        raise SafeError(
            f"请设置必填环境变量 {ACCOUNT_ENV}（或兼容别名 {COOKIE_ALIAS_ENV}）"
        )
    global_captcha = env(CAPTCHA_ENV)
    accounts: List[Account] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        account = parse_account_line(line_no, text, global_captcha)
        account.index = len(accounts) + 1
        if account.label == "账号Cookie":
            account.label = f"账号{account.index}"
        accounts.append(account)
    if not accounts:
        raise SafeError(f"{source} 未解析到任何有效账号")
    return accounts


def http_timeout() -> float:
    raw = env("APKTW_TIMEOUT")
    if not raw:
        return float(HTTP_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("APKTW_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("APKTW_TIMEOUT 须在 5 到 60 秒之间")
    return value


class HttpClient:
    def __init__(self, timeout: float, cookie_header: str = "") -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.cookie_header = cookie_header.strip()

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": BASE_URL + "/",
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        url: str,
        *,
        data: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: Optional[str] = None,
        allow_hosts: Optional[Tuple[str, ...]] = None,
    ) -> Tuple[str, str]:
        parts = urllib.parse.urlsplit(url)
        allowed = allow_hosts or ("apk.tw", "www.apk.tw")
        if parts.scheme != "https" or parts.netloc.lower() not in allowed:
            raise SafeError("拒绝非本站或非 HTTPS 请求")
        body = None
        req_headers = self._headers(headers)
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault(
                "Content-Type", "application/x-www-form-urlencoded"
            )
        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method or ("POST" if body is not None else "GET"),
        )
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise SafeError("业务响应超过大小限制")
                charset = resp.headers.get_content_charset() or "utf-8"
                final_url = resp.geturl()
                return raw.decode(charset, errors="replace"), final_url
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raise SafeError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络错误或超时") from exc
        except TimeoutError as exc:
            raise SafeError("请求超时") from exc


def extract_form_hash(html: str) -> str:
    match = re.search(
        r'name=["\']formhash["\']\s+value=["\']([a-f0-9]+)["\']',
        html,
        flags=re.I,
    )
    if match:
        return match.group(1)
    match = re.search(r'formhash["\s]+value="([a-f0-9]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r"formhash=([a-f0-9]+)", html)
    if match:
        return match.group(1)
    raise SafeError("未能解析登录表单令牌")


def extract_seccode_idhash(html: str) -> Optional[str]:
    match = re.search(r"updateseccode\('([^']+)'", html)
    return match.group(1) if match else None


def extract_turnstile_sitekey(html: str) -> Optional[str]:
    text = re.sub(r"\\+(['\"])", r"\1", html)
    if "turnstile" not in text.lower():
        return None
    match = re.search(r'data-sitekey=["\']([^"\']+)["\']', text, flags=re.I)
    if match:
        return match.group(1)
    match = re.search(r"\bsitekey\s*:\s*['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1)
    raise SafeError("检测到 Turnstile 但缺少 sitekey")


def extract_nickname(html: str) -> Optional[str]:
    patterns = [
        r'title=["\']訪問我的空間["\']>([^<]+)</a>',
        r'title=["\']访问我的空间["\']>([^<]+)</a>',
        r'id=["\']um["\'][\s\S]{0,400}?>([^<]{1,64})</strong>',
        r'class=["\'][^"\']*vwmy[^"\']*["\'][^>]*>([^<]+)<',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if match:
            name = clean_text(re.sub(r"<[^>]+>", "", match.group(1)))
            if name and len(name) <= 64 and "http" not in name.lower():
                return name
    return None


def external_json_request(
    url: str,
    *,
    timeout: float,
    data: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() not in {
        "2captcha.com",
        "www.2captcha.com",
    }:
        raise SafeError("拒绝非 2captcha HTTPS 请求")
    req = urllib.request.Request(
        url, data=body, headers=headers, method="POST" if body else "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536)
            return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise SafeError("2captcha 请求失败或超时") from exc


def solve_2captcha(captcha_key: str, task: Dict[str, str], timeout: float) -> str:
    if not captcha_key:
        raise SafeError("登录需要验证码，但未配置 APKTW_2CAPTCHA_KEY")
    payload = {"key": captcha_key, "json": "1"}
    payload.update(task)
    data = external_json_request(
        TWOCAPTCHA_SUBMIT_URL, timeout=timeout, data=payload
    )
    if data.get("status") != 1:
        raise SafeError("2captcha 提交失败")
    task_id = str(data.get("request") or "")
    if not task_id:
        raise SafeError("2captcha 未返回任务编号")
    deadline = time.monotonic() + TWOCAPTCHA_POLL_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(TWOCAPTCHA_POLL_INTERVAL)
        result = external_json_request(
            TWOCAPTCHA_RESULT_URL,
            timeout=timeout,
            params={
                "key": captcha_key,
                "action": "get",
                "id": task_id,
                "json": "1",
            },
        )
        if result.get("status") == 1:
            token = str(result.get("request") or "").strip()
            if not token:
                raise SafeError("2captcha 返回空结果")
            return token
        if result.get("request") != "CAPCHA_NOT_READY":
            raise SafeError("2captcha 识别失败")
    raise SafeError("2captcha 识别超时")


def validate_captcha_image(image_bytes: bytes) -> None:
    if not image_bytes or not image_bytes.startswith(
        (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")
    ):
        raise SafeError("验证码图片无效")


def fetch_seccode_challenge(client: HttpClient, idhash: str) -> str:
    url = (
        f"{BASE_URL}/misc.php?"
        + urllib.parse.urlencode(
            {
                "mod": "seccode",
                "action": "update",
                "idhash": idhash,
                "modid": SECCODE_MODID,
                "inajax": "1",
                "ajaxtarget": f"seccode_{idhash}",
            }
        )
    )
    text, _ = client.request(url)
    return re.sub(r"\\+(['\"])", r"\1", text)


def fetch_captcha_image(
    client: HttpClient, idhash: str, challenge_html: str, timeout: float
) -> bytes:
    if extract_turnstile_sitekey(challenge_html):
        raise SafeError("站点使用 Turnstile，无图像验证码")
    img_url = (
        f"{BASE_URL}/misc.php?mod=seccode&update={int(time.time() * 1000)}"
        f"&idhash={idhash}"
    )
    for src in re.findall(
        r'''<img\b[^>]*\bsrc=["']([^"']+)["']''', challenge_html, flags=re.I
    ):
        if "mod=seccode" in unescape(src):
            img_url = urllib.parse.urljoin(BASE_URL + "/", unescape(src))
            break
    parts = urllib.parse.urlsplit(img_url)
    if parts.scheme != "https" or parts.netloc.lower() not in {"apk.tw", "www.apk.tw"}:
        raise SafeError("验证码图片地址非法")
    req = urllib.request.Request(img_url, headers=client._headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(512 * 1024)
    except Exception as exc:
        raise SafeError("下载验证码失败") from exc
    validate_captcha_image(raw)
    return raw


def login_with_password(account: Account, client: HttpClient, timeout: float) -> None:
    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        html, _ = client.request(LOGIN_URL)
        formhash = extract_form_hash(html)
        payload = {
            "formhash": formhash,
            "referer": BASE_URL,
            "loginfield": "username",
            "username": account.username,
            "password": account.password,
            "questionid": "0",
            "answer": "",
            "cookietime": "2592000",
        }
        idhash = extract_seccode_idhash(html)
        challenge = ""
        sitekey = None
        if idhash:
            payload.update(
                {
                    "seccodehash": idhash,
                    "seccodemodid": SECCODE_MODID,
                    "seccodeverify": "",
                }
            )
            challenge = fetch_seccode_challenge(client, idhash)
            sitekey = extract_turnstile_sitekey(challenge)
        else:
            sitekey = extract_turnstile_sitekey(html)

        if sitekey:
            token = solve_2captcha(
                account.captcha_key,
                {
                    "method": "turnstile",
                    "sitekey": sitekey,
                    "pageurl": LOGIN_URL,
                },
                timeout,
            )
            payload["cf-turnstile-response"] = token
        elif idhash:
            image_bytes = fetch_captcha_image(client, idhash, challenge, timeout)
            captcha_text = solve_2captcha(
                account.captcha_key,
                {
                    "method": "base64",
                    "body": base64.b64encode(image_bytes).decode("ascii"),
                    "regsense": "1",
                    "min_len": "4",
                    "max_len": "4",
                },
                timeout,
            )
            payload["seccodeverify"] = captcha_text

        log(f"  提交登录（第 {attempt}/{MAX_LOGIN_ATTEMPTS} 次，不输出凭据）")
        resp_text, resp_url = client.request(LOGIN_POST_URL, data=payload)
        if resp_url and "mod=logging" not in resp_url:
            return
        if any(
            key in resp_text
            for key in ("欢迎您回来", "歡迎您回來", "succeedhandle_login", "main_succeed")
        ):
            return
        if idhash and ("驗證碼" in resp_text or "验证码" in resp_text):
            log(f"  {ICONS['warning']} 验证码未通过，重试")
            continue
        if any(
            key in resp_text
            for key in ("密碼錯誤次數過多", "请稍后再尝试登录", "請稍後再嘗試登錄")
        ):
            raise SafeError("登录失败：账号被临时锁定")
        if any(
            key in resp_text
            for key in ("密码错误", "密碼錯誤", "login_invalid", "errorhandle_")
        ):
            raise SafeError("登录失败：用户名或密码错误")
        if any(
            cookie.name == "auth" and cookie.value
            for cookie in client.jar
        ):
            return
        raise SafeError("登录结果不明确，请检查凭据或验证码配置")
    raise SafeError(f"登录失败：已尝试 {MAX_LOGIN_ATTEMPTS} 次")


def verify_login(client: HttpClient) -> Tuple[bool, Optional[str]]:
    html, url = client.request(f"{BASE_URL}/home.php?mod=spacecp")
    if "login" in url or "您需要先登錄" in html or "您需要先登录" in html:
        return False, None
    if "action=logout" not in html:
        return False, None
    nick = extract_nickname(html)
    if not nick and html:
        # 回退：部分皮肤把用户名放在顶部导航
        match = re.search(r"歡迎您回來[，,]\s*([^，,<\s]+)", html)
        if not match:
            match = re.search(r"欢迎您回来[，,]\s*([^，,<\s]+)", html)
        if match:
            nick = clean_text(match.group(1))
    return True, nick


def perform_checkin(client: HttpClient) -> Dict[str, Any]:
    html, _ = client.request(f"{BASE_URL}/forum.php")
    pending = re.search(r'id="my_amupper"[^>]*formhash=([a-f0-9]+)', html)
    triggered = False
    if pending:
        checkin_url = (
            f"{BASE_URL}/plugin.php?id=dsu_amupper:pper&ajax=1"
            f"&formhash={pending.group(1)}&zjtesttimes={int(time.time() * 1000)}"
        )
        client.request(
            checkin_url,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        triggered = True
        html, _ = client.request(f"{BASE_URL}/forum.php")

    result: Dict[str, Any] = {
        "triggered": triggered,
        "total": None,
        "consecutive": None,
        "last_checkin": None,
        "checked_in_today": False,
        "message": None,
    }
    total_m = re.search(r"累計簽到[：:](?:</strong>)?\s*(\d+)\s*次", html)
    if total_m:
        result["total"] = int(total_m.group(1))
    consec_m = re.search(r"連續簽到[：:](?:</strong>)?\s*(\d+)\s*次", html)
    if consec_m:
        result["consecutive"] = int(consec_m.group(1))
    last_m = re.search(
        r"您上次簽到時間為</strong>:?\s*([\d\-]+\s+[\d:]+)", html
    )
    if last_m:
        result["last_checkin"] = last_m.group(1)
    msg_m = re.search(r'<font color="red">(.*?)</font>', html)
    if msg_m:
        result["message"] = clean_text(msg_m.group(1))
    footer_m = re.search(r"GMT\+8,\s*(\d+)-(\d+)-(\d+)", html)
    if footer_m and last_m:
        today = tuple(int(p) for p in footer_m.groups())
        last_date = tuple(int(p) for p in last_m.group(1).split()[0].split("-"))
        result["checked_in_today"] = today == last_date
    # 已签到图标（chavyleung 同源判定）也可辅助确认
    if not result["checked_in_today"] and re.search(
        r"/source/plugin/dsu_amupper/images/wb\.gif", html
    ):
        result["checked_in_today"] = True
    if result["total"] is None and result["last_checkin"] is None and not result["checked_in_today"]:
        raise SafeError("未找到签到结果区域，请确认登录态")
    if not result["checked_in_today"]:
        raise SafeError("签到后未能确认今日已签到")
    return result


def fetch_user_info(client: HttpClient) -> Dict[str, Any]:
    info: Dict[str, Any] = {"usergroup": None, "credits": {}}
    html, _ = client.request(f"{BASE_URL}/home.php?mod=space&do=profile")
    match = re.search(
        r"用戶組.*?<a[^>]*ac=usergroup[^>]*>(.*?)</a>", html, flags=re.S
    )
    if not match:
        match = re.search(
            r"用户组.*?<a[^>]*ac=usergroup[^>]*>(.*?)</a>", html, flags=re.S
        )
    if match:
        info["usergroup"] = clean_text(re.sub(r"<[^>]+>", "", match.group(1)))
    credit_html, _ = client.request(
        f"{BASE_URL}/home.php?mod=spacecp&ac=credit&showcredit=1"
        "&inajax=1&ajaxtarget=extcreditmenu_menu"
    )
    for cid, name in CREDIT_FIELDS.items():
        cm = re.search(rf'id="hcredit_{cid}">([^<]*)</span>', credit_html)
        if cm:
            info["credits"][name] = clean_text(cm.group(1))
    return info


def empty_stats() -> Dict[str, int]:
    return {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }


def run_account_dry(account: Account, total: int) -> Dict[str, Any]:
    started = time.monotonic()
    stats = empty_stats()
    identity = account.label or account.username or f"账号{account.index}"
    log(f"—— 账号{account.index}/{total}（{identity}）开始 ——")
    log_stage(1, "校验账号格式")
    stats["total"] += 1
    if account.mode == "cookie":
        if not account.cookie or "=" not in account.cookie:
            stats["failed"] += 1
            log(f"  {ICONS['failure']} Cookie 无效")
            ok = False
            message = "Cookie 无效"
        else:
            stats["success"] += 1
            log(f"  {ICONS['success']} Cookie 格式有效（不输出内容）")
            ok = True
            message = "Cookie 预演就绪"
    else:
        if not account.username or not account.password:
            stats["failed"] += 1
            log(f"  {ICONS['failure']} 用户名或密码缺失")
            ok = False
            message = "凭据不完整"
        else:
            stats["success"] += 1
            has_key = "已配置" if account.captcha_key else "未配置（若遇验证码将失败）"
            log(f"  {ICONS['success']} 密码登录参数就绪；2captcha {has_key}")
            ok = True
            message = "密码登录预演就绪"

    log_stage(2, "预演登录校验", "跳过真实网络请求")
    stats["total"] += 1
    stats["skipped"] += 1
    log(f"  {ICONS['skipped']} 断网预演：将校验 spacecp 登录态")

    log_stage(3, "预演每日签到", "跳过真实网络请求")
    stats["total"] += 1
    stats["skipped"] += 1
    log(f"  {ICONS['skipped']} 断网预演：将触发 dsu_amupper 签到并核验今日状态")

    log_stage(4, "预演积分摘要", "跳过真实网络请求")
    stats["total"] += 1
    stats["skipped"] += 1
    log(f"  {ICONS['skipped']} 断网预演：将读取用户组与积分")

    elapsed = time.monotonic() - started
    log(
        f"{identity} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed:.2f}秒"
    )
    return {
        "ok": ok and stats["failed"] == 0,
        "identity": identity,
        "status": "success" if ok else "failure",
        "message": message,
        "stats": stats,
        "elapsed": elapsed,
    }


def run_account_live(
    account: Account, total: int, timeout: float
) -> Dict[str, Any]:
    started = time.monotonic()
    stats = empty_stats()
    identity = account.label or account.username or f"账号{account.index}"
    secrets = account.secrets()
    result: Dict[str, Any] = {
        "ok": False,
        "identity": identity,
        "status": "failure",
        "message": "",
        "stats": stats,
        "elapsed": 0.0,
    }
    log(f"—— 账号{account.index}/{total}（{identity}）开始 ——")
    try:
        log_stage(1, "建立会话")
        stats["total"] += 1
        client = HttpClient(
            timeout, cookie_header=account.cookie if account.mode == "cookie" else ""
        )
        if account.mode == "password":
            login_with_password(account, client, timeout)
            log(f"  {ICONS['success']} 密码登录完成")
        else:
            log(f"  {ICONS['success']} 已载入 Cookie 会话")
        stats["success"] += 1

        log_stage(2, "校验登录态")
        stats["total"] += 1
        ok_login, nick = verify_login(client)
        if not ok_login:
            raise SafeError("登录态无效，请更新 Cookie 或检查账号密码")
        if nick:
            identity = nick
            result["identity"] = nick
            log(f"  {ICONS['success']} 官方身份：{nick}")
        elif account.username:
            identity = account.username
            result["identity"] = identity
            log(f"  {ICONS['success']} 登录成功，用户名：{account.username}")
        else:
            log(f"  {ICONS['success']} 登录态有效")
        stats["success"] += 1

        log_stage(3, "每日签到")
        stats["total"] += 1
        checkin = perform_checkin(client)
        streak = checkin.get("consecutive")
        total_days = checkin.get("total")
        if checkin.get("triggered"):
            stats["success"] += 1
            message = (
                f"签到成功：累计{total_days}次，连续{streak}次"
                if total_days is not None
                else "签到成功"
            )
            log(f"  {ICONS['success']} {message}")
        else:
            stats["alreadyComplete"] += 1
            message = (
                f"今日已签到：累计{total_days}次，连续{streak}次"
                if total_days is not None
                else "今日已签到"
            )
            log(f"  {ICONS['alreadyComplete']} {message}")
        if checkin.get("message"):
            log(f"  站点提示：{redact(str(checkin['message']), secrets)}")
        result["message"] = message

        log_stage(4, "读取积分摘要")
        stats["total"] += 1
        info = fetch_user_info(client)
        parts = []
        if info.get("usergroup"):
            parts.append(f"用户组={info['usergroup']}")
        for key in ("鑽石", "碎鑽", "經驗", "金豆"):
            if key in info.get("credits", {}):
                parts.append(f"{key}={info['credits'][key]}")
        if parts:
            stats["success"] += 1
            summary = "，".join(parts)
            log(f"  {ICONS['success']} {summary}")
            result["message"] = f"{result['message']}；{summary}"
        else:
            stats["skipped"] += 1
            log(f"  {ICONS['skipped']} 未解析到积分摘要（不影响签到成功）")

        result["ok"] = True
        result["status"] = "success"
    except Exception as exc:
        stats["failed"] += 1
        message = (
            str(exc) if isinstance(exc, SafeError) else "执行失败（已脱敏）"
        )
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = redact(message, secrets)
        log(f"  {ICONS['failure']} {result['message']}")

    elapsed = time.monotonic() - started
    result["elapsed"] = elapsed
    result["stats"] = stats
    log(
        f"{result['identity']} 统计: 总任务={stats['total']} "
        f"成功={stats['success']} 已完成={stats['alreadyComplete']} "
        f"跳过={stats['skipped']} 失败={stats['failed']} 耗时={elapsed:.2f}秒"
    )
    return result


def notify_should_send() -> bool:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selectors_raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selectors_raw is None:
        return True
    if selectors_raw.strip() == "":
        return False
    selectors = [s for s in re.split(r"[,;\s]+", selectors_raw.strip()) if s]
    identities = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        f"scripts/{SCRIPT_FILENAME}",
        "scripts/apktw_checkin.py",
        "apktw_checkin.py",
        "apktw.py",
        SCRIPT_NAME,
    }
    for selector in selectors:
        if selector == "*":
            return True
        for identity in identities:
            if _ql_notify_fnmatch.fnmatch(identity.lower(), selector.lower()):
                return True
    return False


def send_notification(title: str, body: str) -> str:
    if not notify_should_send():
        return "skipped"
    try:
        from notify import send as notify_send  # type: ignore

        notify_send(title, body)
        return "sent"
    except Exception:
        pass
    search_dirs = []
    custom = env("QINGLONG_NOTIFY_DIR")
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                send(title, body)
                return "sent"
        except Exception:
            continue
    return "unavailable"


def main() -> int:
    task_start = now()
    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)
    dry = False
    try:
        dry = env_truthy(DRY_RUN_ENV, False)
    except SafeError as exc:
        log(f"{ICONS['failure']} 配置错误：{exc}")
        print(
            "TASK_SUMMARY="
            + json.dumps(
                {
                    "script": SCRIPT_NAME,
                    "catalogId": CATALOG_ID,
                    "mode": "live",
                    "status": "configuration-error",
                    "accountsTotal": 0,
                    "accountsSuccess": 0,
                    "accountsFailed": 0,
                    "elapsedMs": 0,
                    "notify": "skipped",
                    "dryRun": False,
                    "exitCode": 2,
                },
                ensure_ascii=False,
            )
        )
        return 2

    mode = "dry-run" if dry else "live"
    log(f"开始时间: {iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    exit_code = 0
    config_error = False
    account_results: List[Dict[str, Any]] = []
    summary_status = "success"
    accounts: List[Account] = []

    try:
        timeout = http_timeout()
        accounts = load_accounts()
        log(f"账号数量: {len(accounts)}")
        for account in accounts:
            if dry:
                account_results.append(run_account_dry(account, len(accounts)))
            else:
                account_results.append(
                    run_account_live(account, len(accounts), timeout)
                )
        failed = [a for a in account_results if not a.get("ok")]
        succeeded = [a for a in account_results if a.get("ok")]
        if failed and succeeded:
            summary_status = "partial-failure"
            exit_code = 1
        elif failed:
            summary_status = "failure"
            exit_code = 1
        else:
            summary_status = "dry-run" if dry else "success"
            exit_code = 0
    except SafeError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICONS['failure']} 配置错误: {exc}")
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICONS['failure']} 未处理异常: {type(exc).__name__}")

    task_end = now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(int((a.get("stats") or {}).get("success") or 0) for a in account_results)
    sub_fail = sum(int((a.get("stats") or {}).get("failed") or 0) for a in account_results)
    sub_skip = sum(int((a.get("stats") or {}).get("skipped") or 0) for a in account_results)
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0) for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {iso(task_end)}")

    if dry and not config_error:
        event = "dry-run"
    elif config_error:
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        f"任务: {SCRIPT_NAME}",
        f"模式: {mode}",
        f"事件: {event}",
        f"账号总数: {total_accounts if not config_error else 0}",
        f"成功: {ok_count}",
        f"失败: {fail_count}",
        f"状态: {summary_status}",
    ]
    for item in account_results:
        lines.append(
            f"- {item.get('identity')}: {item.get('status')} / "
            f"{str(item.get('message') or '')[:120]}"
        )
    body = "\n".join(lines)
    notify_status = "skipped"
    try:
        if dry and not config_error:
            log(f"{ICONS['skipped']} 断网预演：跳过真实通知发送")
            notify_status = "simulated"
        else:
            notify_status = send_notification(SCRIPT_NAME, body)
    except Exception:
        notify_status = "failed"
    log(f"通知状态: {notify_status}")

    final_label = {
        "success": "成功",
        "dry-run": "预演完成",
        "partial-failure": "部分失败",
        "failure": "失败",
        "configuration-error": "配置错误",
    }.get(summary_status, summary_status)
    log(f"最终状态：{final_label}")
    if dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        print("无网络预演通过", flush=True)

    task_summary = {
        "script": SCRIPT_NAME,
        "catalogId": CATALOG_ID,
        "mode": mode,
        "status": summary_status,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSuccess": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notify": notify_status,
        "dryRun": dry,
        "exitCode": exit_code,
    }
    print(f"TASK_SUMMARY={json.dumps(task_summary, ensure_ascii=False)}", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
