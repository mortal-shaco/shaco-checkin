#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NodeOJ每日签到
# cron: 1 10 * * *
#
# 来源：No-World/NodeOJ_SignIn index.py（GPL-3.0）
# https://github.com/No-World/NodeOJ_SignIn
# 分支：master
# 提交：ebf17cb2792897883ba768bdd4e4873ebe802835
# 原路径：index.py
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) No-World / NodeOJ_SignIn contributors
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
# 本文件为青龙维护修改版：保留 NodeOJ 欧皇签到能力，改用标准库 HTTP、
# 换行多账号、断网预演、超时、青龙通知与 TASK_SUMMARY；移除 Server酱 KEY
# 直推与无超时请求。
"""NodeOJ（nodeoj.com）每日欧皇签到 — 青龙独立维护版。

功能清点（相对上游 index.py）：
- 使用 ssid Cookie 调用 https://nodeoj.com/qiandao/ouhuang 执行每日签到
- HTML 响应视为登录失败；JSON status 文本作为业务结果并核验成功/已签
- 多账号：NODEOJ_SSID 每个非空行一个 ssid；兼容 COOKIES / NODEOJ_COOKIES
- 移除云函数 handler 与 Server酱 KEY 直推；改用青龙 notify 脱敏汇总
- NODEOJ_DRY_RUN 完全断网预演、超时、时间轴日志、TASK_SUMMARY
- 标准库 urllib 实现 HTTP；任一账号失败整体非零退出

建议 Cron：0 10 * * *（与上游 README 华为云早上 10 点示例一致）。
不打印 Cookie、ssid、Token 或原始响应。本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('046c5c66d83d3094', 'scripts/nodeoj.py', 'nodeoj.py', 'nodeoj')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import html
import importlib.util
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_NAME = "NodeOJ每日签到"
CATALOG_ID = "046c5c66d83d3094"
SCRIPT_FILENAME = "candidate.py"
SIGN_URL = "https://nodeoj.com/qiandao/ouhuang"
USER_AGENT = "No_World签到姬 NodeOJ-Qinglong/1.0"
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 256 * 1024
DRY_RUN_ENV = "NODEOJ_DRY_RUN"
CRED_ENV = "NODEOJ_SSID"
CRED_ALIASES = ("NODEOJ_COOKIES", "COOKIES")
TIMEOUT_ENV = "NODEOJ_TIMEOUT"

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

ALREADY_PATTERNS = (
    "已签到",
    "已经签到",
    "今日已签",
    "重复签到",
    "签过了",
)
SUCCESS_PATTERNS = (
    "签到成功",
    "打卡成功",
    "签到完成",
    "获得",
    "奖励",
    "欧皇",
)
AUTH_FAIL_PATTERNS = (
    "登陆失败",
    "登录失败",
    "未登录",
    "请登录",
    "cookie",
    "cookies",
    "ssid",
)


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


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = text.replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", "\n")
    text = " ".join(part.strip() for part in text.splitlines() if part.strip())
    return " ".join(text.split()).strip()


def redact(text: str, secrets: List[str]) -> str:
    out = clean_text(text)
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 4:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(
        r"(?i)(ssid|cookie|token|authorization|session|password|key)=([^;\s&]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable() or ch in "\n\t")[:280]


def normalize_ssid(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.lower().startswith("cookie:"):
        value = value[7:].strip()
    # 若用户粘贴了完整 Cookie 头，只取 ssid=
    if "ssid=" in value.lower() and ("=" in value) and (";" in value or value.lower().startswith("ssid=")):
        for part in value.split(";"):
            piece = part.strip()
            if not piece:
                continue
            if "=" not in piece:
                continue
            name, val = piece.split("=", 1)
            if name.strip().lower() == "ssid":
                value = val.strip()
                break
    if value.lower().startswith("ssid="):
        value = value.split("=", 1)[1].strip()
    return value.strip().strip('"').strip("'")


def load_accounts() -> Tuple[List[str], str]:
    raw = env(CRED_ENV)
    source = CRED_ENV
    if not raw:
        for alias in CRED_ALIASES:
            raw = env(alias)
            if raw:
                source = alias
                break
    if not raw:
        raise SafeError(
            f"请设置必填环境变量 {CRED_ENV}（或兼容别名 {' / '.join(CRED_ALIASES)}）"
        )
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        ssid = normalize_ssid(text)
        if not ssid:
            raise SafeError(f"第 {line_no} 行 ssid 为空")
        if any(ord(ch) < 32 for ch in ssid):
            raise SafeError(f"第 {line_no} 行 ssid 含控制字符")
        accounts.append(ssid)
    if not accounts:
        raise SafeError(f"{source} 未解析到任何有效账号")
    return accounts, source


def http_get(url: str, cookie_header: str, timeout: int) -> Tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_header,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            content_type = str(response.headers.get("Content-Type") or "")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES + 1) if hasattr(exc, "read") else b""
        if len(body) > MAX_RESPONSE_BYTES:
            raise SafeError("响应体过大，已中止解析") from exc
        content_type = str(exc.headers.get("Content-Type") if exc.headers else "")
        text = body.decode("utf-8", errors="replace")
        raise SafeError(f"HTTP {exc.code}: {redact(text, [])[:120] or '请求失败'}") from exc
    except urllib.error.URLError as exc:
        raise SafeError(f"网络错误: {type(exc.reason).__name__ if exc.reason else 'URLError'}") from exc
    except TimeoutError as exc:
        raise SafeError("请求超时") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise SafeError("响应体过大，已中止解析")
    text = raw.decode("utf-8", errors="replace")
    return status, content_type, text


def classify_status(status_text: str) -> Tuple[str, str]:
    """返回 (kind, message)，kind ∈ success|already|auth_fail|failure。"""
    message = clean_text(status_text)
    if not message:
        return "failure", "签到响应缺少 status 文本"
    low = message.lower()
    for pattern in AUTH_FAIL_PATTERNS:
        if pattern.lower() in low:
            return "auth_fail", message
    for pattern in ALREADY_PATTERNS:
        if pattern in message:
            return "already", message
    for pattern in SUCCESS_PATTERNS:
        if pattern in message:
            return "success", message
    # 上游只要拿到 JSON status 即打印；无明确失败关键词时视为成功业务文案
    if any(word in message for word in ("失败", "错误", "异常", "无效")):
        return "failure", message
    return "success", message


def do_signin(ssid: str, timeout: int) -> Tuple[str, str]:
    cookie_header = f"ssid={ssid}"
    status_code, content_type, body = http_get(SIGN_URL, cookie_header, timeout)
    ctype = (content_type or "").lower()
    if "text/html" in ctype:
        return "auth_fail", "登陆失败，请检查 ssid Cookie"
    if status_code >= 400:
        return "failure", f"HTTP {status_code}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # 某些失败场景可能直接返回 HTML 但未声明 Content-Type
        snippet = clean_text(body)[:80]
        if "<html" in body.lower() or "<!doctype" in body.lower():
            return "auth_fail", "登陆失败，请检查 ssid Cookie"
        return "failure", f"响应不是合法 JSON（{snippet or '空响应'}）"
    if not isinstance(payload, dict):
        return "failure", "响应 JSON 结构异常"
    status_raw = payload.get("status")
    if status_raw is None:
        return "failure", "响应缺少 status 字段"
    return classify_status(str(status_raw))


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
        "scripts/nodeoj_signin.py",
        "nodeoj_signin.py",
        "output/candidate.py",
        "nodeoj",
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
            spec = importlib.util.spec_from_file_location("ql_notify_nodeoj", path)
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


def run_account_dry(index: int, total: int, ssid: str) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始（预演）——")
    stats = {
        "total": 2,
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

    log_stage(1, "校验 ssid", "已提供非空凭据")
    if not ssid:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = "ssid 为空"
        log(f"  {ICON_FAIL} {result['message']}")
    else:
        stats["success"] += 1
        log(f"  {ICON_OK} 格式有效（不输出 ssid）")
        log_stage(2, "预演欧皇签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将请求 {SIGN_URL}")
        log(f"  {ICON_SKIP} dry-run 已跳过签到副作用")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(index: int, total: int, ssid: str, timeout: int) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始 ——")
    stats = {
        "total": 2,
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
    secrets = [ssid]
    try:
        log_stage(1, "校验 ssid")
        if not ssid:
            raise SafeError("ssid 为空")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出 ssid）")

        stage2_start = _now()
        log_stage(2, "执行欧皇签到")
        kind, message = do_signin(ssid, timeout)
        safe_message = redact(message, secrets)
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        if kind == "already":
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} {safe_message}（耗时 {stage2_ms}ms）")
            result["ok"] = True
            result["status"] = "success"
            result["message"] = safe_message or "今日已签到"
        elif kind == "success":
            stats["success"] += 1
            log(f"  {ICON_OK} {safe_message}（耗时 {stage2_ms}ms）")
            result["ok"] = True
            result["status"] = "success"
            result["message"] = safe_message or "签到成功"
        elif kind == "auth_fail":
            raise SafeError(safe_message or "登陆失败，请检查 ssid Cookie")
        else:
            raise SafeError(safe_message or "签到失败")
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
            ),
            flush=True,
        )
        return 2

    mode = "dry-run" if dry else "live"
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    exit_code = 0
    config_error = False
    account_results: List[Dict[str, Any]] = []
    summary_status = "success"

    try:
        timeout = http_timeout()
        accounts, source_name = load_accounts()
        log(f"凭据来源: {source_name}（内容已脱敏）")
        log(f"账号数量: {len(accounts)}")
        total = len(accounts)
        for idx, ssid in enumerate(accounts, start=1):
            if dry:
                account_results.append(run_account_dry(idx, total, ssid))
            else:
                account_results.append(run_account_live(idx, total, ssid, timeout))
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
        log(f"{ICON_FAIL} 配置错误: {exc}")
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
            f"{str(item.get('message') or '')[:120]}"
        )
    body = "\n".join(lines)

    notify_status = "skipped"
    try:
        if dry and not config_error:
            log(f"{ICON_SKIP} 断网预演：跳过真实通知发送")
            notify_status = "simulated"
        else:
            notify_status = send_notification(SCRIPT_NAME, body)
            if notify_status == "unavailable":
                log(f"{ICON_WARN} 未找到可用 notify.py，跳过通知并保留业务退出码")
    except Exception:
        notify_status = "failed"
        log(f"{ICON_WARN} 通知发送异常，已保留业务退出码")
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
