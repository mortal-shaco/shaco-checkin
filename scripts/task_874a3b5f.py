#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: PT站点每日签到
# cron: 35 9 * * *
#
# 来源：JasonL111/PT_attendance main.py（MIT）
# https://github.com/JasonL111/PT_attendance
# 提交：4aeb5915a1de1a1ef9dc94444e8394336d69ea5d
# SPDX-License-Identifier: MIT
#
# MIT License
# Copyright (c) 2025 JasonL111
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
"""NexusPHP 风格 PT 站点每日签到 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用已登录 Cookie（c_secure_*）访问用户配置的签到页 URL
- 识别「已连续签到 N 天」为业务成功，并提取连续天数
- 兼容常见「今日已签到 / 今天已经签到」等已完成文案
- 页面返回公开用户名或 UID 时直接展示以便核对账号
- 移除 Telegram Bot 默认推送、.env 依赖、打印原始 HTML、无超时请求
- 增加逐行多账号、PT_ATTENDANCE_DRY_RUN 断网预演、请求超时、
  时间轴日志、青龙通知与 TASK_SUMMARY

PT_ATTENDANCE_ACCOUNTS：每个非空行一个账号，格式
attendance_url|Cookie完整值；仅按第一个 | 分割，Cookie 中后续 | 原样保留。
Cookie 须含 NexusPHP 常见 c_secure_uid / c_secure_pass 等字段。
兼容单账号别名：attendance_url + c_secure_uid + c_secure_pass
（及可选 c_secure_ssl / c_secure_tracker_ssl / c_secure_login / domain），
仅当规范变量为空时生效。
PT_ATTENDANCE_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
PT_ATTENDANCE_DRY_RUN=1：完全断网预演，只校验配置与流程，不发起网络请求。
建议 Cron：30 8 * * *。不打印 Cookie、Token、会话值或原始响应。
本脚本不发布帖子、评论或分享文字。
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
            "874a3b5f0c910fff",
            "scripts/pt_attendance.py",
            "pt_attendance.py",
            "candidate.py",
            "output/candidate.py",
            "main.py",
            "pt_attendance",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TITLE = "PT站点每日签到"
CATALOG_ID = "874a3b5f0c910fff"
ACCOUNTS_ENV = "PT_ATTENDANCE_ACCOUNTS"
DRY_RUN_ENV = "PT_ATTENDANCE_DRY_RUN"
TIMEOUT_ENV = "PT_ATTENDANCE_TIMEOUT"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
STATES = ("success", "alreadyComplete", "skipped", "failure")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) "
    "Gecko/20100101 Firefox/137.0"
)
DAYS_RE = re.compile(r"已连续签到\s*(?:<b>)?(\d+)(?:</b>)?\s*天", re.I)
ALREADY_HINTS = (
    "今日已签到",
    "今天已签到",
    "您今天已经签到过了",
    "今天已经签到",
    "已经签到过了",
)
LOGIN_FAIL_HINTS = (
    "login.php",
    "takelogin.php",
    "userdetails.php?id=0",
)
USERNAME_RE = re.compile(
    r'(?:class=["\'][^"\']*username[^"\']*["\'][^>]*>|'
    r"欢迎[您你回来，,\s]*|"
    r"您好[，,\s]*)"
    r"\s*([^<]{1,64})",
    re.I,
)
UID_RE = re.compile(r"userdetails\.php\?id=(\d+)", re.I)
COOKIE_KEYS_REQUIRED = ("c_secure_uid", "c_secure_pass")
COOKIE_KEYS_OPTIONAL = ("c_secure_ssl", "c_secure_tracker_ssl", "c_secure_login")


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def redact(text: str, secrets: List[str]) -> str:
    result = str(text or "")
    for secret in sorted({item for item in secrets if item and len(item) >= 4}, key=len, reverse=True):
        result = result.replace(secret, "[已脱敏]")
    return result


def resolve_timeout() -> float:
    raw = env(TIMEOUT_ENV)
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(TIMEOUT_ENV)) from exc
    if value < 5 or value > 60:
        raise SafeError("{} 须在 5 到 60 秒之间".format(TIMEOUT_ENV))
    return value


def parse_cookie_header(raw: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    text = raw.strip()
    if not text:
        raise SafeError("Cookie 为空")
    # 兼容上游分散字段拼成的 Cookie，或浏览器复制的完整 Cookie 头
    for part in text.split(";"):
        piece = part.strip()
        if not piece:
            continue
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value
    return cookies


def build_cookie_header(cookies: Dict[str, str]) -> str:
    order = list(COOKIE_KEYS_REQUIRED) + list(COOKIE_KEYS_OPTIONAL)
    parts: List[str] = []
    seen = set()
    for key in order:
        if key in cookies and cookies[key]:
            parts.append("{}={}".format(key, cookies[key]))
            seen.add(key)
    for key, value in cookies.items():
        if key in seen or not value:
            continue
        parts.append("{}={}".format(key, value))
    if not parts:
        raise SafeError("Cookie 解析后无有效字段")
    return "; ".join(parts)


def validate_cookies(cookies: Dict[str, str]) -> None:
    missing = [key for key in COOKIE_KEYS_REQUIRED if not cookies.get(key)]
    if missing:
        raise SafeError(
            "Cookie 缺少必要字段：{}".format("、".join(missing))
        )


def validate_attendance_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise SafeError("签到 URL 为空")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise SafeError("签到 URL 须为 http 或 https")
    if not parsed.netloc:
        raise SafeError("签到 URL 缺少主机名")
    if parsed.username or parsed.password:
        raise SafeError("签到 URL 不得内嵌用户名或密码")
    return text


def load_accounts() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    block = env(ACCOUNTS_ENV)
    if block:
        for line_no, raw_line in enumerate(block.splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise SafeError(
                    "{} 第 {} 行缺少 |，格式应为 attendance_url|Cookie".format(
                        ACCOUNTS_ENV, line_no
                    )
                )
            url_part, cookie_part = line.split("|", 1)
            url = validate_attendance_url(url_part)
            cookies = parse_cookie_header(cookie_part)
            validate_cookies(cookies)
            cookie_header = build_cookie_header(cookies)
            host = urllib.parse.urlparse(url).netloc
            accounts.append(
                {
                    "url": url,
                    "cookie": cookie_header,
                    "host": host,
                    "label": host,
                }
            )
        if not accounts:
            raise SafeError("{} 未配置有效账号行".format(ACCOUNTS_ENV))
        return accounts

    # 兼容上游单账号分散环境变量
    url = env("attendance_url")
    uid = env("c_secure_uid")
    password = env("c_secure_pass")
    if not (url or uid or password):
        raise SafeError(
            "未配置 {}；也可使用上游单账号别名 attendance_url 与 c_secure_*".format(
                ACCOUNTS_ENV
            )
        )
    if not url or not uid or not password:
        raise SafeError(
            "单账号兼容模式须同时提供 attendance_url、c_secure_uid、c_secure_pass"
        )
    cookies = {
        "c_secure_uid": uid,
        "c_secure_pass": password,
    }
    for key in COOKIE_KEYS_OPTIONAL:
        value = env(key)
        if value:
            cookies[key] = value
    url = validate_attendance_url(url)
    validate_cookies(cookies)
    cookie_header = build_cookie_header(cookies)
    host = urllib.parse.urlparse(url).netloc or env("domain") or "account"
    accounts.append(
        {
            "url": url,
            "cookie": cookie_header,
            "host": host,
            "label": host,
        }
    )
    return accounts


def extract_identity(page: str, secrets: List[str]) -> Optional[str]:
    text = page or ""
    for match in USERNAME_RE.finditer(text):
        name = plain(match.group(1))
        if not name or len(name) > 64:
            continue
        lowered = name.lower()
        if any(token in lowered for token in ("login", "logout", "签到", "魔力")):
            continue
        redacted = redact(name, secrets)
        if "[已脱敏]" in redacted:
            continue
        return name
    uid_match = UID_RE.search(text)
    if uid_match:
        uid = uid_match.group(1)
        if uid and uid != "0":
            return "UID:{}".format(uid)
    return None


def classify_response(page: str, final_url: str) -> Tuple[str, str, Optional[int]]:
    text = page or ""
    lower_url = (final_url or "").lower()
    if any(hint in lower_url for hint in ("login.php", "takelogin.php")):
        raise SafeError("签到页跳转到登录页，Cookie 可能已失效")
    if "login.php" in text.lower() and "logout.php" not in text.lower():
        # 粗判：含登录表单且无退出链接
        if 'name="username"' in text.lower() or "takelogin.php" in text.lower():
            raise SafeError("响应疑似未登录页面，Cookie 可能已失效")

    days_match = DAYS_RE.search(text)
    if days_match or "已连续签到" in text:
        days = int(days_match.group(1)) if days_match else None
        if days is not None:
            return "success", "签到成功，已连续签到 {} 天".format(days), days
        return "success", "签到成功（已连续签到）", None

    for hint in ALREADY_HINTS:
        if hint in text:
            return "alreadyComplete", hint, None

    if "签到成功" in text:
        return "success", "签到成功", None

    raise SafeError("响应未包含可核验的签到成功或已签到消息")


def http_get(url: str, cookie: str, timeout: float) -> Tuple[int, str, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": cookie,
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1",
    }
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            final_url = response.geturl() or url
            payload = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = int(error.code)
        final_url = error.geturl() if hasattr(error, "geturl") else url
        payload = error.read(MAX_BYTES + 1) if error.fp else b""
        if status >= 400 and not payload:
            raise SafeError("HTTP {} 且无响应体".format(status)) from error
    except urllib.error.URLError as error:
        raise SafeError("网络请求失败或超时") from error
    except TimeoutError as error:
        raise SafeError("网络请求超时") from error
    if len(payload) > MAX_BYTES:
        raise SafeError("响应过大，已中止读取")
    text = payload.decode("utf-8", errors="replace")
    return status, final_url, text


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
        "main.py",
        "pt_attendance.py",
        "candidate.py",
        "scripts/pt_attendance.py",
        "pt_attendance",
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
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


class AccountResult:
    def __init__(self, number: int, label: str) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.label = label
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""


def run_account(
    result: AccountResult,
    url: str,
    cookie: str,
    timeout: float,
    dry_run: bool,
) -> None:
    secrets = [cookie]
    for part in cookie.split(";"):
        if "=" in part:
            secrets.append(part.split("=", 1)[1].strip())
    stages = [
        (1, "校验签到参数"),
        (2, "访问签到页并核验结果"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}（{}）：开始处理；子任务 {} 项".format(
            result.number, result.label, total_stages
        )
    )
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total_stages, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                validate_attendance_url(url)
                cookies = parse_cookie_header(cookie)
                validate_cookies(cookies)
                result.stats["success"] += 1
                log(
                    "{} 签到 URL 与 Cookie 字段校验通过；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                status, final_url, text = http_get(url, cookie, timeout)
                if status >= 400:
                    raise SafeError("HTTP {}，签到请求未成功".format(status))
                identity = extract_identity(text, secrets)
                if identity:
                    result.identity = identity
                    log("账号 {} 官方身份：{}".format(result.number, identity))
                else:
                    log(
                        "账号 {}：页面未返回公开身份，使用序号标识".format(
                            result.number
                        )
                    )
                outcome, message, days = classify_response(text, final_url)
                if days is not None:
                    log("连续签到天数：{}".format(days))
                if outcome == "alreadyComplete":
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    result.message = message
                    log("{} {}".format(ICONS["alreadyComplete"], message))
                else:
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = message
                    log("{} {}".format(ICONS["success"], message))
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total_stages
                    )
                )
            result.status = "failure"
            result.message = redact(str(error), secrets)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    result.message,
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
            result.message = "未预期本地错误"
            log(
                "{} 账号 {} 阶段 {} 失败：未预期本地错误，详情已抑制；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    time.monotonic() - tick,
                )
            )
            return
    if dry_run:
        result.status = "dry-run"
        result.stats["success"] = 0
    elif result.status not in {"success", "alreadyComplete"}:
        if result.stats["failure"] == 0 and result.stats["alreadyComplete"] == 0:
            result.status = "success"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total_stages,
            result.stats["success"],
            result.stats["alreadyComplete"],
            result.stats["skipped"],
            result.stats["failure"],
            elapsed,
        )
    )


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env(DRY_RUN_ENV, "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("{} 配置无效，停止执行".format(DRY_RUN_ENV))
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            item = AccountResult(number, account.get("label") or "站点")
            results.append(item)
            run_account(
                item,
                account["url"],
                account["cookie"],
                timeout,
                dry_run,
            )
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in results if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in results if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in results if item.status == "failure"),
        "dry-run": sum(1 for item in results if item.status == "dry-run"),
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
    tasks = {key: sum(item.stats[key] for item in results) for key in STATES}
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
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
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
