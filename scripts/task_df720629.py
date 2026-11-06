#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 93海山云论坛签到
# cron: 34 9 * * *
#
# 来源：kcenceis/93hsy main.py（GPL-3.0）
# https://github.com/kcenceis/93hsy
# 分支：main
# 提交：cdc64d3e0b97673bac6c23036322f22a6a6ed34f
# 原路径：main.py
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# Copyright (C) kcenceis / 93hsy contributors
#
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
# 本文件为青龙维护修改版：保留 www.93hsy.com Discuz 账号密码登录与
# k_misign 每日签到；改用标准库 HTTP、换行多账号、断网预演、超时、
# 回读确认、青龙通知与 TASK_SUMMARY；移除硬编码空凭据、Server酱 KEY
# 直推与无超时请求。
"""93海山云（www.93hsy.com）Discuz 每日签到 — 青龙独立维护版。

功能清点（相对上游 main.py）：
- 使用账号密码登录 https://www.93hsy.com（密码按上游 MD5 后提交）
- 打开 k_misign 签到页，识别「您的签到排名」为今日已签
- 提取 formhash 后执行 plugin.php?id=k_misign:sign&operation=qiandao，再回读确认
- 移除硬编码空账号/密码、Server酱直推、无超时请求与仅凭 HTTP 200 判定成功
- 多账号：HSY93_ACCOUNT 每行「用户名|密码」（仅拆首个 |）
- HSY93_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY

建议 Cron：10 8 * * *。不打印密码、Cookie、Token 或原始响应。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('df720629ed9ff0d1', 'scripts/task_df720629.py', 'task_df720629.py', 'task_df720629')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import hashlib
import importlib.util
import json
import os
import re
import sys
import traceback
from datetime import datetime
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

SCRIPT_NAME = "93海山云论坛签到"
CATALOG_ID = "df720629ed9ff0d1"
SCRIPT_FILENAME = "candidate.py"
HOST = "www.93hsy.com"
BASE_URL = "https://www.93hsy.com/"
MEMBER_URL = "https://www.93hsy.com/member.php"
SIGN_PAGE = "https://www.93hsy.com/plugin.php?id=k_misign:sign"
PLUGIN_URL = "https://www.93hsy.com/plugin.php"
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 512 * 1024
DRY_RUN_ENV = "HSY93_DRY_RUN"
CRED_ENV = "HSY93_ACCOUNT"
TIMEOUT_ENV = "HSY93_TIMEOUT"

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


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


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else str(value).strip()


def env_truthy(name: str) -> bool:
    raw = env(name)
    if not raw:
        return False
    low = raw.lower()
    if low in TRUE_VALUES:
        return True
    if low in FALSE_VALUES:
        return False
    raise SafeError(f"{name} 须为开关值（1/0、true/false、yes/no、on/off）")


def http_timeout() -> int:
    raw = env(TIMEOUT_ENV)
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{TIMEOUT_ENV} 须为整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError(f"{TIMEOUT_ENV} 须在 5 到 120 秒之间")
    return value


def password_md5(password: str) -> str:
    """按上游 passwordHex：提交前对明文密码做 MD5。"""
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    """每行一个账号；仅按第一个 | 分割用户名与密码。"""
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            raise SafeError(
                f"第 {line_no} 行账号格式无效：缺少用户名与密码分隔符 |"
            )
        username, password = text.split("|", 1)
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise SafeError(f"第 {line_no} 行账号格式无效：用户名或密码为空")
        if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
            raise SafeError(f"第 {line_no} 行账号含控制字符")
        accounts.append({"username": username, "password": password})
    return accounts


def load_accounts() -> Tuple[List[Dict[str, str]], str]:
    raw = os.environ.get(CRED_ENV)
    if raw is None or str(raw).strip() == "":
        raise SafeError(f"请设置必填环境变量 {CRED_ENV}")
    accounts = parse_accounts(str(raw))
    if not accounts:
        raise SafeError(f"{CRED_ENV} 未解析到任何有效账号")
    return accounts, CRED_ENV


def redact(text: str, secrets: List[str]) -> str:
    out = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 4:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(
        r"(?i)(cookie|token|authorization|session|password|formhash)=([^;\s&]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable() or ch in "\n\t")[:240]


class ForumClient:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))

    def request_text(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> str:
        full_url = url
        if params:
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}{urlencode(params)}"
        body = None
        headers = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Referer": referer or SIGN_PAGE,
            "Host": HOST,
            "DNT": "1",
            "Connection": "close",
        }
        if data is not None:
            body = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(full_url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            try:
                err_body = exc.read(MAX_RESPONSE_BYTES + 1) if hasattr(exc, "read") else b""
            except Exception:
                err_body = b""
            snippet = redact(err_body.decode("utf-8", errors="replace"), [])[:80]
            raise SafeError(f"HTTP {exc.code}: {snippet or '请求失败'}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            raise SafeError(
                f"网络错误: {type(reason).__name__ if reason else 'URLError'}"
            ) from exc
        except TimeoutError as exc:
            raise SafeError("请求超时") from exc
        except Exception as exc:
            raise SafeError(f"请求失败: {type(exc).__name__}") from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise SafeError("响应体过大，已中止解析")
        return raw.decode("utf-8", errors="replace")


def extract_formhash(html: str) -> str:
    patterns = (
        r'name="formhash"\s+value="([^"]+)"',
        r'<input type="hidden" name="formhash" value="(.+?)"\s*/?>',
        r"formhash=([0-9a-fA-F]+)",
        r"formhash=([^\"'&>\s]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    raise SafeError("未能解析 formhash")


def extract_display_name(html: str, username: str) -> str:
    for pattern in (
        r"欢迎您回来[，,]\s*([^，,<\s]+)",
        r'title="访问我的空间">([^<]+)</a>',
        r'id="um"[^>]*>[\s\S]*?<strong>([^<]+)</strong>',
        r"discuz_uid\s*=\s*'([1-9]\d*)'",
    ):
        match = re.search(pattern, html)
        if match:
            name = match.group(1).strip()
            if name and name != "0":
                if pattern.startswith("discuz_uid"):
                    return f"UID:{name}"
                return name
    return username


def already_signed(html: str) -> bool:
    return "您的签到排名" in html


def login_looks_failed(html: str) -> bool:
    markers = (
        "密码错误",
        "登录失败",
        "用户名或密码错误",
        "用户名不存在",
        "安全提问",
        "请先登录",
        "您尚未登录",
    )
    return any(marker in html for marker in markers)


def session_looks_logged_in(html: str, username: str) -> bool:
    if already_signed(html):
        return True
    if "JD_sign" in html or "k_misign:sign" in html:
        if "退出" in html or "退出登录" in html or username in html:
            return True
    if "欢迎您回来" in html:
        return True
    if re.search(r"discuz_uid\s*=\s*'[1-9]\d*'", html):
        return True
    return False


def login(client: ForumClient, username: str, password: str) -> str:
    """按上游 quick login：MD5 密码提交 member.php，返回可展示身份。"""
    hashed = password_md5(password)
    post_data = {
        "fastloginfield": "username",
        "username": username,
        "password": hashed,
        "quickforward": "yes",
        "handlekey": "ls",
    }
    login_resp = client.request_text(
        MEMBER_URL,
        method="POST",
        params={
            "mod": "logging",
            "action": "login",
            "loginsubmit": "yes",
            "infloat": "yes",
            "lssubmit": "yes",
            "inajax": "1",
        },
        data=post_data,
        referer=BASE_URL,
    )
    if login_looks_failed(login_resp):
        raise SafeError("登录失败：账号或密码不正确")

    identity = extract_display_name(login_resp, username)
    sign_page = client.request_text(SIGN_PAGE, referer=BASE_URL)
    if login_looks_failed(sign_page) or not session_looks_logged_in(sign_page, username):
        raise SafeError("登录失败：签到页未检测到已登录会话")
    return extract_display_name(sign_page, identity)


def perform_sign(client: ForumClient) -> Dict[str, Any]:
    sign_page = client.request_text(SIGN_PAGE)
    if already_signed(sign_page):
        return {
            "already_signed": True,
            "sign_message": "今日已签到（检测到签到排名）",
        }
    formhash = extract_formhash(sign_page)
    client.request_text(
        PLUGIN_URL,
        params={
            "id": "k_misign:sign",
            "operation": "qiandao",
            "formhash": formhash,
            "format": "empty",
            "inajax": "1",
            "ajaxtarget": "JD_sign",
        },
        referer=SIGN_PAGE,
    )
    confirm = client.request_text(SIGN_PAGE, referer=SIGN_PAGE)
    if already_signed(confirm):
        return {
            "already_signed": False,
            "sign_message": "签到成功（回读确认出现签到排名）",
        }
    if "JD_sign" in confirm and "qiandao" in confirm.lower():
        raise SafeError("签到失败：回读页仍可发起签到")
    raise SafeError("签到失败：回读页未出现签到排名")


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
        "scripts/hsy93_signin.py",
        "hsy93_signin.py",
        "output/candidate.py",
        "hsy93_signin",
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
        log("通知: 已跳过（全局开关或脚本选择未启用）")
        return "skipped"
    try:
        from notify import send as notify_send  # type: ignore

        notify_send(title, body)
        log(f"{ICON_OK} 通知: 已发送")
        return "sent"
    except Exception:
        pass
    search_dirs: List[str] = []
    custom = env("QINGLONG_NOTIFY_DIR")
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify_hsy93", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                send(title, body)
                log(f"{ICON_OK} 通知: 已发送")
                return "sent"
        except Exception:
            continue
    log(f"{ICON_WARN} 通知: 未找到 notify.py，已跳过发送")
    return "unavailable"


def run_account_dry(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始（预演）——")
    stats = {
        "total": 3,
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

    log_stage(1, "校验账号格式", "用户名与密码均已提供")
    if not account.get("username") or not account.get("password"):
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = "账号凭据不完整"
        log(f"  {ICON_FAIL} {result['message']}")
    else:
        stats["success"] += 1
        log(f"  {ICON_OK} 格式有效（不输出凭据）")

        log_stage(2, "预演登录", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将登录 {HOST}（MD5 密码提交）")

        log_stage(3, "预演签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将执行 k_misign 签到并以签到排名回读确认")
        log(f"  {ICON_SKIP} dry-run 已跳过登录与签到副作用")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(
    index: int, total: int, account: Dict[str, str], timeout: int
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始 ——")
    stats = {
        "total": 3,
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
    secrets = [
        account.get("password", ""),
        password_md5(account.get("password", "")) if account.get("password") else "",
    ]
    try:
        log_stage(1, "校验账号格式")
        if not account.get("username") or not account.get("password"):
            raise SafeError("账号凭据不完整")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出凭据）")

        stage2_start = _now()
        log_stage(2, "登录论坛")
        client = ForumClient(timeout=timeout)
        identity = login(client, account["username"], account["password"])
        result["identity"] = identity
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  {ICON_OK} 登录成功，身份: {identity}（耗时 {stage2_ms}ms）")
        stats["success"] += 1

        stage3_start = _now()
        log_stage(3, "执行并确认签到")
        outcome = perform_sign(client)
        stage3_ms = int((_now() - stage3_start).total_seconds() * 1000)
        sign_msg = redact(str(outcome.get("sign_message") or ""), secrets)
        if outcome.get("already_signed"):
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} {sign_msg}（耗时 {stage3_ms}ms）")
            result["message"] = sign_msg
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} {sign_msg}（耗时 {stage3_ms}ms）")
            result["message"] = sign_msg
        result["ok"] = True
        result["status"] = "success"
    except SafeError as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = redact(str(exc), secrets)[:200]
        log(f"  {ICON_FAIL} {result['message']}")
    except Exception as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = f"未处理异常: {type(exc).__name__}"
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
    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)

    dry = False
    try:
        dry = env_truthy(DRY_RUN_ENV)
    except SafeError as exc:
        log(f"{ICON_FAIL} 配置错误：{exc}")
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
                separators=(",", ":"),
            )
        )
        return 2

    mode = "dry-run" if dry else "live"
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        timeout = http_timeout()
        accounts, source_name = load_accounts()
        log(f"凭据来源: {source_name}（内容已脱敏）")
        log(f"账号数量: {len(accounts)}")
        total = len(accounts)
        for idx, acc in enumerate(accounts, start=1):
            if dry:
                ar = run_account_dry(idx, total, acc)
            else:
                ar = run_account_live(idx, total, acc, timeout=timeout)
            account_results.append(ar)

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
        log(f"{ICON_FAIL} {exc}")
        log(
            f"获取方式: 在青龙环境变量中新增 {CRED_ENV}，"
            "每行一个账号，格式 用户名|密码"
        )
        log("账号数量: 0")
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 未处理异常: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(
        int((a.get("stats") or {}).get("success") or 0) for a in account_results
    )
    sub_fail = sum(
        int((a.get("stats") or {}).get("failed") or 0) for a in account_results
    )
    sub_skip = sum(
        int((a.get("stats") or {}).get("skipped") or 0) for a in account_results
    )
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0)
        for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {_iso(task_end)}")

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
            f"{str(item.get('message', ''))[:80]}"
        )
    notify_status = send_notification(SCRIPT_NAME, "\n".join(lines))
    log(f"通知状态: {notify_status}")

    final_icon = {
        "success": ICON_OK,
        "dry-run": ICON_OK,
        "partial-failure": ICON_WARN,
        "failure": ICON_FAIL,
        "configuration-error": ICON_FAIL,
    }.get(summary_status, ICON_WARN)
    log(f"最终状态: {final_icon} {summary_status}")
    if dry and not config_error:
        print("DRY_RUN_OK", flush=True)

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
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
