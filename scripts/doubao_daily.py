#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 豆包天天领额度签到
# cron: 23 9 * * *
#
# 来源：meliissy/doubao-daily-checkin（MIT）
# https://github.com/meliissy/doubao-daily-checkin
# 提交：cb28058d325e2bf355860bf09d984f83862bb4e4
# 原路径：main.py，并合并同仓 src/__init__.py、src/client.py、
# src/config.py、src/http.py 的可维护逻辑为青龙独立脚本。
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) meliissy / doubao-daily-checkin contributors
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
"""豆包「天天领额度」每日签到（青龙独立维护版）。

功能：
  1. 按用户抓包得到的签到接口，使用 Cookie 发起「天天领额度」签到
  2. 支持成功 / 已签到 / 鉴权失败 / 风控关键词判定与可选 JSON 路径成功规则
  3. 多账号换行配置；任一账号失败整体非零退出
  4. DOUBAO_DRY_RUN 完全断网预演、时间轴日志、TASK_SUMMARY、青龙通知

环境变量：
  DOUBAO_COOKIE            必填。每行一个账号 Cookie；禁止用 &、@ 分账号。
  COOKIE                   可选兼容别名，仅当 DOUBAO_COOKIE 为空时生效。
  DOUBAO_CHECKIN_URL       必填。抓包得到的完整签到接口 URL。
  CHECKIN_URL              可选兼容别名。
  DOUBAO_CHECKIN_METHOD    可选。GET/POST/PUT，默认 POST。
  DOUBAO_CHECKIN_BODY      可选。合法 JSON 请求体字符串。
  DOUBAO_EXTRA_HEADERS     可选。额外请求头 JSON 对象。
  DOUBAO_USER_AGENT        可选。自定义 User-Agent。
  DOUBAO_TIMEOUT           可选。超时秒数，默认 20。
  DOUBAO_RETRY             可选。重试次数，默认 3。
  DOUBAO_RETRY_BACKOFF     可选。重试退避基数秒，默认 3。
  DOUBAO_SUCCESS_KEYWORDS  可选。逗号分隔成功关键词。
  DOUBAO_ALREADY_KEYWORDS  可选。逗号分隔已签到关键词。
  DOUBAO_AUTH_KEYWORDS     可选。逗号分隔鉴权失败关键词。
  DOUBAO_RISK_KEYWORDS     可选。逗号分隔风控关键词。
  DOUBAO_SUCCESS_JSON_PATH 可选。逗号分隔 path=value 成功规则。
  DOUBAO_DRY_RUN           1/true/yes/on 完全断网预演。
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略
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
        _ql_notify_identities = ('4ac225148a2befcd', 'scripts/doubao_daily.py', 'doubao_daily.py', 'doubao_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import gzip
import importlib.util
import io
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "4ac225148a2befcd"
TASK_NAME = "豆包天天领额度签到"
SCRIPT_FILENAME = "doubao_daily_checkin.py"
DRY_RUN_ENV = "DOUBAO_DRY_RUN"
CN_TZ = timezone(timedelta(hours=8))

SUCCESS = "SUCCESS"
ALREADY = "ALREADY"
AUTH_FAILED = "AUTH_FAILED"
RISK = "RISK"
FAILED = "FAILED"

DEFAULT_SUCCESS_KEYWORDS = ["签到成功", "领取成功", "签到完成", "success"]
DEFAULT_ALREADY_KEYWORDS = ["已签到", "已经签到", "今日已领", "重复签到", "already"]
DEFAULT_AUTH_KEYWORDS = ["未登录", "登录已过期", "not login", "unauthorized", "401", "403"]
DEFAULT_RISK_KEYWORDS = ["风控", "验证", "captcha", "risk", "verify", "频繁"]

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
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

_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
_IDENTITY_KEYS = (
    "nickname",
    "nick_name",
    "nickName",
    "username",
    "user_name",
    "userName",
    "display_name",
    "displayName",
    "name",
    "uid",
    "user_id",
    "userId",
    "open_id",
    "openId",
)


@dataclass
class HttpResponse:
    status: int
    text: str
    headers: dict = field(default_factory=dict)


@dataclass
class CheckinResult:
    status: str
    message: str
    http_status: int = 0
    amount: str = ""
    identity: str = ""
    elapsed: float = 0.0
    attempts: int = 1
    ok: bool = False


class ConfigError(Exception):
    """配置缺失或格式错误。"""


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def ts() -> str:
    return now_cn().strftime("%H:%M:%S")


def iso_now() -> str:
    return now_cn().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{ts()}] {message}", flush=True)


def env_get(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ConfigError(f"{name} 只能是 1/true/yes/on 或 0/false/no/off")


def split_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]


def parse_json_object(raw: str, name: str) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{name} 不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{name} 必须是 JSON 对象")
    return value


def redact(text: str, secrets: List[str]) -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for secret in secrets:
        if not secret:
            continue
        cleaned = cleaned.replace(secret, "[REDACTED]")
        for part in secret.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, val = part.partition("=")
                if val:
                    cleaned = cleaned.replace(val, f"[{key or 'COOKIE'}_REDACTED]")
    cleaned = re.sub(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", "[手机号已隐藏]", cleaned)
    return cleaned[:240]


def normalize_unicode(text: str) -> str:
    if "\\u" not in text:
        return text
    return _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), text)


def dig(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def check_json_path(body: Any, rules: List[str]) -> Optional[bool]:
    if not rules:
        return None
    for rule in rules:
        if "=" not in rule:
            continue
        path, _, expected = rule.partition("=")
        actual = dig(body, path.strip())
        if actual is None:
            continue
        if str(actual).strip().lower() == expected.strip().lower():
            return True
    return False


def extract_amount(text: str) -> str:
    patterns = [
        r"[+＋]\s*(\d+)\s*(?:活动)?额度",
        r"(?:获得|领取|赠送)[^\d]{0,6}(\d+)\s*(?:活动)?额度",
        r'"(?:amount|credit|quota|reward)"\s*:\s*(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def extract_identity(text: str) -> str:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return ""
    stack: List[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key in _IDENTITY_KEYS:
                value = current.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    candidate = str(value).strip()
                    if len(candidate) <= 64 and not any(
                        token in candidate.lower()
                        for token in ("cookie", "token", "bearer", "session")
                    ):
                        return candidate
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return ""


def decode_body(raw: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower()
    try:
        if encoding == "gzip":
            return gzip.decompress(raw)
        if encoding == "deflate":
            return zlib.decompress(raw)
    except Exception:
        pass
    return raw


def http_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    body: Optional[str] = None,
    timeout: float = 20.0,
) -> HttpResponse:
    payload = body.encode("utf-8") if isinstance(body, str) else None
    merged = {"Accept-Encoding": "identity"}
    merged.update(headers or {})
    req = urllib.request.Request(
        url=url, data=payload, headers=merged, method=method.upper()
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            raw = decode_body(resp.read(), resp.headers.get("Content-Encoding", ""))
            return HttpResponse(
                status=resp.status,
                text=raw.decode("utf-8", "replace"),
                headers=dict(resp.headers),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        encoding = ""
        if exc.headers:
            encoding = exc.headers.get("Content-Encoding", "")
        raw = decode_body(raw, encoding)
        return HttpResponse(
            status=exc.code,
            text=raw.decode("utf-8", "replace"),
            headers=dict(exc.headers) if exc.headers else {},
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ConnectionError(f"{exc.__class__.__name__}: {reason}") from exc


@dataclass
class SharedConfig:
    url: str
    method: str
    body: str
    extra_headers: dict
    user_agent: str
    timeout: float
    retries: int
    retry_backoff: float
    success_keywords: List[str]
    already_keywords: List[str]
    auth_keywords: List[str]
    risk_keywords: List[str]
    success_json_path: List[str]


def load_shared_config() -> SharedConfig:
    url = env_get("DOUBAO_CHECKIN_URL", "CHECKIN_URL")
    if not url:
        raise ConfigError(
            "缺少 DOUBAO_CHECKIN_URL：请把抓包拿到的豆包「天天领额度」签到接口完整 URL "
            "填入环境变量（兼容别名 CHECKIN_URL）。"
        )
    if not url.startswith(("http://", "https://")):
        raise ConfigError("DOUBAO_CHECKIN_URL 必须是完整的 http(s) 地址")

    method = env_get("DOUBAO_CHECKIN_METHOD", default="POST").upper()
    if method not in {"GET", "POST", "PUT"}:
        raise ConfigError("DOUBAO_CHECKIN_METHOD 只支持 GET / POST / PUT")

    body = env_get("DOUBAO_CHECKIN_BODY")
    if body:
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"DOUBAO_CHECKIN_BODY 不是合法 JSON：{exc}") from exc

    retries_raw = env_get("DOUBAO_RETRY", default="3")
    try:
        retries = max(1, int(retries_raw))
    except ValueError as exc:
        raise ConfigError("DOUBAO_RETRY 必须是整数") from exc

    timeout_raw = env_get("DOUBAO_TIMEOUT", default="20")
    backoff_raw = env_get("DOUBAO_RETRY_BACKOFF", default="3")
    try:
        timeout = float(timeout_raw)
        retry_backoff = float(backoff_raw)
    except ValueError as exc:
        raise ConfigError("DOUBAO_TIMEOUT / DOUBAO_RETRY_BACKOFF 必须是数字") from exc
    if not 3 <= timeout <= 120:
        raise ConfigError("DOUBAO_TIMEOUT 须在 3~120 秒之间")
    if not 0 <= retry_backoff <= 60:
        raise ConfigError("DOUBAO_RETRY_BACKOFF 须在 0~60 秒之间")

    return SharedConfig(
        url=url,
        method=method,
        body=body,
        extra_headers=parse_json_object(
            env_get("DOUBAO_EXTRA_HEADERS"), "DOUBAO_EXTRA_HEADERS"
        ),
        user_agent=env_get("DOUBAO_USER_AGENT", default=DEFAULT_UA),
        timeout=timeout,
        retries=retries,
        retry_backoff=retry_backoff,
        success_keywords=split_list(env_get("DOUBAO_SUCCESS_KEYWORDS"))
        or list(DEFAULT_SUCCESS_KEYWORDS),
        already_keywords=split_list(env_get("DOUBAO_ALREADY_KEYWORDS"))
        or list(DEFAULT_ALREADY_KEYWORDS),
        auth_keywords=split_list(env_get("DOUBAO_AUTH_KEYWORDS"))
        or list(DEFAULT_AUTH_KEYWORDS),
        risk_keywords=split_list(env_get("DOUBAO_RISK_KEYWORDS"))
        or list(DEFAULT_RISK_KEYWORDS),
        success_json_path=split_list(env_get("DOUBAO_SUCCESS_JSON_PATH")),
    )


def load_accounts() -> List[str]:
    raw = env_get("DOUBAO_COOKIE", "COOKIE")
    if not raw:
        raise ConfigError(
            "缺少 DOUBAO_COOKIE：请在浏览器登录豆包后复制完整 Cookie，"
            "每行一个账号写入环境变量（兼容别名 COOKIE）。"
        )
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise ConfigError("DOUBAO_COOKIE 为空：请至少配置一个非空账号行")
    for index, cookie in enumerate(accounts, 1):
        validate_cookie(cookie, index)
    return accounts


def validate_cookie(cookie: str, number: int) -> None:
    if "=" not in cookie:
        raise ConfigError(f"账号{number} Cookie 格式无效：缺少 name=value")
    if "&&" in cookie or any(ord(c) < 32 or ord(c) == 127 for c in cookie):
        raise ConfigError(f"账号{number} Cookie 格式无效：含非法控制字符或分隔符")
    try:
        cookie.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ConfigError(f"账号{number} Cookie 含无法编码的字符") from exc


def build_headers(cookie: str, shared: SharedConfig) -> dict:
    headers = {
        "User-Agent": shared.user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Cookie": cookie,
    }
    headers.update(shared.extra_headers)
    headers["Cookie"] = cookie
    return headers


def classify(
    http_status: int,
    text: str,
    shared: SharedConfig,
) -> Tuple[str, str]:
    lowered = text.lower()

    for keyword in shared.already_keywords:
        if keyword.lower() in lowered:
            return ALREADY, f"今日已签到（命中关键词：{keyword}）"

    verdict = None
    if shared.success_json_path:
        try:
            verdict = check_json_path(json.loads(text), shared.success_json_path)
        except (json.JSONDecodeError, TypeError):
            verdict = None
    if verdict is True:
        return SUCCESS, "签到成功（JSON 规则命中）"

    for keyword in shared.success_keywords:
        if keyword.lower() in lowered:
            return SUCCESS, f"签到成功（命中关键词：{keyword}）"

    for keyword in shared.risk_keywords:
        if keyword.lower() in lowered:
            return RISK, f"疑似触发风控/人机验证（命中关键词：{keyword}）"

    for keyword in shared.auth_keywords:
        if keyword.lower() in lowered:
            return AUTH_FAILED, f"Cookie 可能已失效（命中关键词：{keyword}）"

    # 显式业务成功核验：禁止仅凭 HTTP 2xx 判定成功。
    if 200 <= http_status < 300:
        return FAILED, "HTTP 2xx 但未命中成功/已签到规则，按失败处理"
    return FAILED, f"签到失败，HTTP {http_status}"


def should_retry(status: str, http_status: int) -> bool:
    if status in (SUCCESS, ALREADY, AUTH_FAILED):
        return False
    return not (400 <= http_status < 500 and http_status not in (408, 429))


def run_checkin(cookie: str, shared: SharedConfig, secrets: List[str]) -> CheckinResult:
    started = time.monotonic()
    last: Optional[CheckinResult] = None
    headers = build_headers(cookie, shared)

    for attempt in range(1, shared.retries + 1):
        log(f"  发起签到请求（第 {attempt}/{shared.retries} 次）")
        try:
            response = http_request(
                method=shared.method,
                url=shared.url,
                headers=headers,
                body=shared.body or None,
                timeout=shared.timeout,
            )
        except ConnectionError as exc:
            message = redact(f"网络请求异常：{exc}", secrets)
            last = CheckinResult(
                status=FAILED,
                message=message,
                attempts=attempt,
                ok=False,
            )
            log(f"  {ICONS['warning']} {message}")
            if attempt < shared.retries:
                delay = shared.retry_backoff * attempt + random.uniform(0, 1.5)
                log(f"  等待 {delay:.1f}s 后重试")
                time.sleep(delay)
            continue

        text = normalize_unicode(response.text or "")
        status, message = classify(response.status, text, shared)
        amount = extract_amount(text)
        identity = extract_identity(text)
        last = CheckinResult(
            status=status,
            message=message,
            http_status=response.status,
            amount=amount,
            identity=identity,
            attempts=attempt,
            ok=status in (SUCCESS, ALREADY),
        )
        log(f"  HTTP {response.status} → {status}")
        if not should_retry(status, response.status):
            break
        if attempt < shared.retries:
            delay = shared.retry_backoff * attempt + random.uniform(0, 1.5)
            log(f"  {ICONS['warning']} {message}，{delay:.1f}s 后重试")
            time.sleep(delay)

    assert last is not None
    last.elapsed = time.monotonic() - started
    return last


def notify_should_send() -> bool:
    switch = (os.getenv("QINGLONG_NOTIFY", "auto") or "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    if switch != "auto":
        log(f"{ICONS['warning']} QINGLONG_NOTIFY 值无效，按 auto 处理")
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
        "doubao_daily_checkin",
        "candidate.py",
    }
    for selector in selectors:
        if selector == "*":
            return True
        for identity in identities:
            if _ql_notify_fnmatch.fnmatch(identity.lower(), selector.lower()):
                return True
    return False


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notify_should_send():
        return "skipped"
    if dry_run:
        log("通知预演：" + body.replace("\n", "；")[:300])
        return "simulated"
    send = None
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            from notify import send as notify_send  # type: ignore

            send = notify_send
        except Exception:
            send = None
        if not callable(send):
            paths: List[Path] = []
            custom = env_get("QINGLONG_NOTIFY_DIR")
            if custom:
                paths.append(Path(custom) / "notify.py")
            paths.extend(
                [
                    Path("/ql/data/scripts/notify.py"),
                    Path("/ql/scripts/notify.py"),
                ]
            )
            for path in paths:
                if not path.is_file():
                    continue
                try:
                    spec = importlib.util.spec_from_file_location("ql_notify", path)
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    candidate = getattr(module, "send", None)
                    if callable(candidate):
                        send = candidate
                        break
                except Exception:
                    continue
        if not callable(send):
            return "unavailable"
        try:
            send(title, body)
            return "sent"
        except Exception:
            return "failed"


def run_account_dry(
    index: int,
    total: int,
    cookie: str,
    shared: SharedConfig,
) -> Dict[str, Any]:
    identity = f"账号{index}"
    started = time.monotonic()
    log(f"---------- {identity}/{total} ----------")
    stats = {
        "total": 1,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }

    stage_started = time.monotonic()
    log(f"{identity} · 阶段1/1 校验配置与 Cookie")
    try:
        validate_cookie(cookie, index)
        stats["skipped"] = 1
        ok = True
        status = "dry-run"
        message = (
            f"断网预演通过：将请求 {shared.method}（URL 已隐藏主机外细节），"
            f"Header 数={3 + len(shared.extra_headers)}，"
            f"Body={'有' if shared.body else '无'}"
        )
        log(f"  {ICONS['skipped']} {message}")
    except ConfigError as exc:
        stats["failed"] = 1
        ok = False
        status = "configuration-error"
        message = str(exc)
        log(f"  {ICONS['failure']} {message}")
    elapsed_stage = time.monotonic() - stage_started
    log(f"  阶段耗时 {elapsed_stage:.2f}s")

    elapsed = time.monotonic() - started
    log(
        f"{identity} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed:.2f}秒"
    )
    return {
        "index": index,
        "identity": identity,
        "ok": ok,
        "status": status,
        "message": message,
        "stats": stats,
        "elapsed": elapsed,
    }


def run_account_live(
    index: int,
    total: int,
    cookie: str,
    shared: SharedConfig,
) -> Dict[str, Any]:
    identity = f"账号{index}"
    secrets = [cookie]
    started = time.monotonic()
    log(f"---------- {identity}/{total} ----------")
    stats = {
        "total": 1,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }

    stage_started = time.monotonic()
    log(f"{identity} · 阶段1/1 天天领额度签到")
    result = run_checkin(cookie, shared, secrets)
    if result.identity:
        identity = result.identity
        log(f"  账号身份：{identity}")
    if result.ok:
        if result.status == ALREADY:
            stats["alreadyComplete"] = 1
            icon = ICONS["alreadyComplete"]
        else:
            stats["success"] = 1
            icon = ICONS["success"]
        detail = result.message
        if result.amount:
            detail = f"{detail}；额度 +{result.amount}"
        log(f"  {icon} {detail}")
    else:
        stats["failed"] = 1
        log(f"  {ICONS['failure']} {result.message}")
        if result.status == AUTH_FAILED:
            log("  处理建议：重新抓取 Cookie，更新 DOUBAO_COOKIE 后重试。")
        elif result.status == RISK:
            log("  处理建议：降低频率、更换网络，或改为手动签到。")
    elapsed_stage = time.monotonic() - stage_started
    log(f"  阶段耗时 {elapsed_stage:.2f}s")

    elapsed = time.monotonic() - started
    log(
        f"{identity} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed:.2f}秒"
    )
    return {
        "index": index,
        "identity": identity,
        "ok": result.ok,
        "status": "success" if result.status == SUCCESS else result.status.lower(),
        "message": result.message
        + (f"；额度 +{result.amount}" if result.amount else ""),
        "stats": stats,
        "elapsed": elapsed,
    }


def main() -> int:
    task_start = now_cn()
    print("=" * 56, flush=True)
    print(f"  {TASK_NAME}", flush=True)
    print("=" * 56, flush=True)

    dry_run = False
    try:
        dry_run = env_truthy(DRY_RUN_ENV, False)
    except ConfigError as exc:
        log(f"{ICONS['failure']} 配置错误：{exc}")
        summary = {
            "script": TASK_NAME,
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
        }
        print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)
        return 2

    mode = "dry-run" if dry_run else "live"
    log(f"开始时间: {iso_now()}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    exit_code = 0
    config_error = False
    account_results: List[Dict[str, Any]] = []
    summary_status = "success"
    accounts: List[str] = []
    shared: Optional[SharedConfig] = None

    try:
        shared = load_shared_config()
        accounts = load_accounts()
        log(f"账号数量: {len(accounts)}")
        log(f"请求方法: {shared.method}；超时 {shared.timeout}s；重试 {shared.retries}")
        for index, cookie in enumerate(accounts, 1):
            if dry_run:
                account_results.append(
                    run_account_dry(index, len(accounts), cookie, shared)
                )
            else:
                account_results.append(
                    run_account_live(index, len(accounts), cookie, shared)
                )
        failed = [item for item in account_results if not item.get("ok")]
        succeeded = [item for item in account_results if item.get("ok")]
        if failed and succeeded:
            summary_status = "partial-failure"
            exit_code = 1
        elif failed:
            summary_status = "failure" if not dry_run else "configuration-error"
            exit_code = 1 if not dry_run else 2
        else:
            summary_status = "dry-run" if dry_run else "success"
            exit_code = 0
    except ConfigError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICONS['failure']} 配置错误: {exc}")
    except Exception:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICONS['failure']} 未处理异常: 已脱敏，请检查配置与运行环境")

    task_end = now_cn()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for item in account_results if item.get("ok"))
    fail_count = sum(1 for item in account_results if not item.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56, flush=True)
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
    log(f"  完成时间: {task_end.isoformat(timespec='seconds')}")

    if dry_run and not config_error and exit_code == 0:
        event = "dry-run"
    elif config_error or summary_status == "configuration-error":
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        f"任务: {TASK_NAME}",
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
        notify_status = send_notification(TASK_NAME, body, dry_run)
    except Exception:
        notify_status = "failed"
    log(f"通知状态: {notify_status}")

    final_label = {
        "success": "SUCCESS",
        "dry-run": "DRY-RUN",
        "partial-failure": "PARTIAL-FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIGURATION-ERROR",
    }.get(summary_status, summary_status.upper())
    log(f"最终状态：{final_label}")

    if dry_run and exit_code == 0:
        print(
            f"DRY_RUN_OK: validated {len(accounts)} account(s); "
            "no network requests or state changes were made",
            flush=True,
        )
        print("无网络预演通过", flush=True)

    task_summary = {
        "script": TASK_NAME,
        "catalogId": CATALOG_ID,
        "mode": mode,
        "status": summary_status,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSuccess": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notify": notify_status,
        "dryRun": dry_run,
        "exitCode": exit_code,
    }
    print("TASK_SUMMARY=" + json.dumps(task_summary, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
