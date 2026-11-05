#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 百度搭子每日签到
# cron: 24 9 * * *
#
# 来源：wang448721577/agent-auto-signin scripts/dumate_signin.py（MIT）
# https://github.com/wang448721577/agent-auto-signin
# 分支：main
# 提交：99c5ad9a3e6a8e20659892ca8c4c6d645fe8a18c
# 原路径：scripts/dumate_signin.py
# SPDX-License-Identifier: MIT
#
# Copyright (c) wang448721577 / agent-auto-signin contributors
# 本维护版沿用上游 MIT 许可，保留原作者版权与归属声明。
#
"""百度搭子（DuMate / 千帆桌面端）每日登录积分签到（青龙维护版）。

功能清点（相对上游 dumate_signin.py）：
- 查询登录积分状态（累计积分、已签天数、今日是否已发放）
- 未领取时调用领取接口（每日约 500 积分，业务幂等）
- 上游依赖桌面端 auth.json/.cookie-key AES 解密：维护版改为环境变量 Cookie，
  不再要求预装桌面端、私有路径或 cryptography
- 多账号：DUMATE_COOKIE 每个非空行一份 Cookie（账号之间只用换行）
- DUMATE_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 标准库 urllib 实现 HTTP；超时与业务 success 核验；任一账号失败非零退出

建议 Cron：15 8 * * *。不打印 Cookie、csrftoken、会话值或原始响应。
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
            "6a8f3b3e39d831f5",
            "scripts/dumate_signin.py",
            "dumate_signin.py",
            "candidate.py",
            "dumate",
            "百度搭子每日签到",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import importlib.util
import json
import os
import re
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_NAME = "百度搭子每日签到"
CATALOG_ID = "6a8f3b3e39d831f5"
SCRIPT_FILENAME = "candidate.py"
API_BASE = "https://console.bce.baidu.com"
STATUS_PATH = "/api/dumate/points/loginBonusInfo"
CLAIM_PATH = "/api/dumate/points/loginBonus"
CSRF_COOKIE = "bce-user-info"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 256 * 1024
DRY_RUN_ENV = "DUMATE_DRY_RUN"
CRED_ENV = "DUMATE_COOKIE"
TIMEOUT_ENV = "DUMATE_TIMEOUT"

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


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_dry_run() -> bool:
    return _env_truthy(DRY_RUN_ENV)


def _http_timeout() -> int:
    raw = os.getenv(TIMEOUT_ENV, "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{TIMEOUT_ENV} 须为整数秒") from exc
    if value < 5 or value > 90:
        raise SafeError(f"{TIMEOUT_ENV} 须在 5 到 90 秒之间")
    return value


def parse_accounts(raw: str) -> List[str]:
    """每个非空行一份 Cookie；账号之间只用换行分隔。"""
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if any(ord(ch) < 32 for ch in text):
            raise ValueError(f"第 {line_no} 行 Cookie 含非法控制字符")
        accounts.append(text)
    return accounts


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(CRED_ENV)
    if primary is not None and primary.strip() != "":
        return primary, CRED_ENV
    # 兼容旧别名（仅文档为可选；canonical 仍是 DUMATE_COOKIE）
    for alias in ("COOKIE_DUMATE", "BAIDU_DUMATE_COOKIE"):
        value = os.getenv(alias)
        if value is not None and value.strip() != "":
            return value, alias
    return "", ""


def extract_csrf(cookie_str: str) -> Optional[str]:
    """从 Cookie 中提取 bce-user-info 作为 csrftoken（与上游一致）。"""
    for part in cookie_str.split(";"):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        name, value = piece.split("=", 1)
        if name.strip() == CSRF_COOKIE:
            csrf = value.strip().strip("\"'")
            return csrf or None
    return None


def _num(v: Any) -> Optional[int]:
    """只把真正的数字当数值用（排除 bool）。"""
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _notify_global_mode() -> str:
    raw = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in {"1", "true", "yes", "on"}:
        return "enabled"
    if raw in {"0", "false", "no", "off"}:
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
        "scripts/dumate_signin.py",
        "dumate_signin.py",
        SCRIPT_NAME,
        "dumate",
    }
    sel_l = sel.lower()
    if sel in candidates or sel_l in {c.lower() for c in candidates}:
        return True
    if sel.endswith("*") and SCRIPT_FILENAME.startswith(sel[:-1]):
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
    search_dirs = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
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
    """发送脱敏通知；失败仅记录，不影响业务退出码。"""
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


def api_request(
    path: str,
    cookie_str: str,
    csrf: Optional[str],
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    timeout: int = HTTP_TIMEOUT,
) -> Tuple[int, Dict[str, Any]]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": API_BASE,
        "Referer": API_BASE + "/",
        "User-Agent": UA,
        "Cookie": cookie_str,
        "Connection": "close",
    }
    if csrf:
        headers["csrftoken"] = csrf
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if method.upper() == "POST" and data is None:
        data = b"{}"
    url = API_BASE + path
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("响应过大，已中止读取")
            charset = resp.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            status = getattr(resp, "status", 200) or 200
            try:
                payload = json.loads(text) if text.strip() else {}
            except Exception as exc:
                raise RuntimeError("接口返回无法解析为 JSON") from exc
            if not isinstance(payload, dict):
                raise RuntimeError("接口返回结构异常")
            return int(status), payload
    except HTTPError as exc:
        try:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            text = raw.decode("utf-8", errors="replace") if raw else ""
            payload = json.loads(text) if text.strip() else {}
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        return int(exc.code), payload
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        name = type(reason).__name__ if reason is not None else type(exc).__name__
        raise RuntimeError(f"网络错误: {name}") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求超时") from exc
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"请求失败: {type(exc).__name__}") from exc


def emit_machine(out: Dict[str, Any]) -> None:
    """保留上游单行 JSON 机器可读输出（不包含凭据）。"""
    safe = {k: v for k, v in out.items() if k not in {"cookie", "csrf", "raw"}}
    print(json.dumps(safe, ensure_ascii=False, default=str), flush=True)


def run_account_dry(index: int, total: int, cookie: str) -> Dict[str, Any]:
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
        "resultCode": "DRY_RUN",
        "elapsedMs": 0,
    }

    log_stage(1, "校验 Cookie", "已提供非空凭据")
    if not cookie:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = "Cookie 为空"
        result["resultCode"] = "NO_AUTH"
        log(f"  {ICON_FAIL} {result['message']}")
    else:
        csrf = extract_csrf(cookie)
        stats["success"] += 1
        if csrf:
            log(f"  {ICON_OK} 格式有效，已检测到 {CSRF_COOKIE}（不输出值）")
        else:
            log(f"  {ICON_WARN} 未检测到 {CSRF_COOKIE}，正式请求可能被拒绝")

        log_stage(2, "预演查询签到状态", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 GET {API_BASE}{STATUS_PATH}")

        log_stage(3, "预演领取登录积分", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 POST {API_BASE}{CLAIM_PATH}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats
    emit_machine(
        {
            "result": result["resultCode"],
            "report": result["message"],
            "account": index,
            "dry_run": True,
        }
    )
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(
    index: int, total: int, cookie: str, timeout: int
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
        "resultCode": "ERROR",
        "elapsedMs": 0,
        "stats": stats,
    }
    machine: Dict[str, Any] = {"result": "ERROR", "report": "", "account": index}

    try:
        log_stage(1, "校验 Cookie")
        if not cookie:
            raise RuntimeError("Cookie 为空")
        csrf = extract_csrf(cookie)
        stats["success"] += 1
        if csrf:
            log(f"  {ICON_OK} 参数就绪，已提取 csrftoken（不输出）")
        else:
            log(f"  {ICON_WARN} 未找到 {CSRF_COOKIE}，仍尝试请求")

        stage2_start = _now()
        log_stage(2, "查询签到状态")
        scode, sbody = api_request(
            STATUS_PATH, cookie, csrf, method="GET", timeout=timeout
        )
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)

        if scode in (401, 403) or sbody.get("code") == "Unauthorized":
            raise RuntimeError(f"登录态已失效（HTTP {scode}），请重新获取 Cookie")
        if scode != 200 or not sbody.get("success"):
            msg = sbody.get("message") or sbody.get("code") or ""
            raise RuntimeError(f"状态接口异常（HTTP {scode}）" + (f"：{msg}" if msg else ""))

        payload = sbody.get("result") or {}
        if not isinstance(payload, dict):
            payload = {}
        days = payload.get("signInDays") or []
        if not isinstance(days, list):
            days = []
        total_points = _num(payload.get("totalPoints"))
        has_issued = bool(payload.get("hasIssued"))
        # 官方状态接口未返回昵称/UID；用累计积分作为可核对的非凭据信息
        identity = label
        if total_points is not None:
            identity = f"{label}(积分{total_points})"
        result["identity"] = identity
        tail = ""
        if total_points is not None:
            tail = f"（累计 {total_points} 积分，已签 {len(days)} 天）"
        log(
            f"  {ICON_OK} 状态已取得{tail}；今日已发放="
            f"{'是' if has_issued else '否'}（耗时 {stage2_ms}ms）"
        )
        stats["success"] += 1

        stage3_start = _now()
        log_stage(3, "领取登录积分")
        if has_issued:
            stats["alreadyComplete"] += 1
            stage3_ms = int((_now() - stage3_start).total_seconds() * 1000)
            msg = f"今日已签过{tail}"
            log(f"  {ICON_DONE} {msg}（耗时 {stage3_ms}ms）")
            result["ok"] = True
            result["status"] = "success"
            result["message"] = msg
            result["resultCode"] = "ALREADY"
            machine = {
                "result": "ALREADY",
                "report": msg,
                "account": index,
                "total_points": total_points,
                "sign_in_days": days,
            }
        else:
            ccode, cbody = api_request(
                CLAIM_PATH, cookie, csrf, method="POST", body={}, timeout=timeout
            )
            stage3_ms = int((_now() - stage3_start).total_seconds() * 1000)
            if ccode in (401, 403):
                raise RuntimeError(f"登录态已失效（HTTP {ccode}），请重新获取 Cookie")
            if ccode == 200 and cbody.get("success"):
                got = _num(cbody.get("result"))
                show = (f"成功领取 {got} 积分" if got is not None else "签到成功") + tail
                stats["success"] += 1
                log(f"  {ICON_OK} {show}（耗时 {stage3_ms}ms）")
                result["ok"] = True
                result["status"] = "success"
                result["message"] = show
                result["resultCode"] = "CLAIMED"
                machine = {
                    "result": "CLAIMED",
                    "report": show,
                    "account": index,
                    "total_points": total_points,
                }
            else:
                # 业务幂等：重查一次状态
                scode2, sbody2 = api_request(
                    STATUS_PATH, cookie, csrf, method="GET", timeout=timeout
                )
                result2 = (sbody2.get("result") or {}) if isinstance(sbody2, dict) else {}
                if (
                    scode2 == 200
                    and sbody2.get("success")
                    and isinstance(result2, dict)
                    and result2.get("hasIssued")
                ):
                    tp2 = _num(result2.get("totalPoints"))
                    msg = f"今日已签过（累计 {tp2} 积分）" if tp2 is not None else "今日已签过"
                    stats["alreadyComplete"] += 1
                    log(f"  {ICON_DONE} {msg}（领取接口幂等）")
                    result["ok"] = True
                    result["status"] = "success"
                    result["message"] = msg
                    result["resultCode"] = "ALREADY"
                    machine = {
                        "result": "ALREADY",
                        "report": msg,
                        "account": index,
                        "total_points": tp2,
                    }
                else:
                    err = cbody.get("message") or cbody.get("code") or f"HTTP {ccode}"
                    raise RuntimeError(f"领取失败：{err}")
    except Exception as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = str(exc)[:200]
        result["resultCode"] = "ERROR"
        machine = {
            "result": "ERROR",
            "report": result["message"],
            "account": index,
        }
        log(f"  {ICON_FAIL} {result['message']}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    emit_machine(machine)
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

    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        timeout = _http_timeout()
        raw, source_name = _read_credential_raw()
        if not raw:
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{ICON_FAIL} 未配置必填环境变量 {CRED_ENV}")
            log(
                "获取方式: 登录百度智能云控制台 / 百度搭子（千帆桌面端）后，"
                f"在浏览器开发者工具网络请求中复制发往 {API_BASE} 的 Cookie，"
                f"写入青龙环境变量 {CRED_ENV}；建议包含 {CSRF_COOKIE}；每行一个账号"
            )
            log("账号数量: 0")
            emit_machine(
                {
                    "result": "NO_AUTH",
                    "report": f"未配置必填环境变量 {CRED_ENV}",
                }
            )
        else:
            log(f"凭据来源: {source_name}（内容已脱敏）")
            try:
                accounts = parse_accounts(raw)
            except ValueError as exc:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 账号解析失败: {exc}")
                accounts = []
                emit_machine({"result": "ERROR", "report": str(exc)})

            log(f"账号数量: {len(accounts)}")
            if not config_error and not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 未解析到任何有效账号")
                emit_machine({"result": "NO_AUTH", "report": "未解析到任何有效账号"})

            if not config_error:
                total = len(accounts)
                for idx, cookie in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, cookie)
                    else:
                        ar = run_account_live(idx, total, cookie, timeout=timeout)
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
        log(f"{ICON_FAIL} 配置错误: {exc}")
        emit_machine({"result": "ERROR", "report": str(exc)})
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 未处理异常: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        emit_machine(
            {
                "result": "ERROR",
                "report": f"脚本运行异常（{type(exc).__name__}）",
            }
        )

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
    for a in account_results:
        lines.append(
            f"- {a.get('identity')}: {a.get('status')} / {a.get('message', '')[:120]}"
        )
    body = "\n".join(lines)
    notify_status = send_notification(SCRIPT_NAME, body)
    log(f"通知状态: {notify_status}")

    final_status = summary_status
    if exit_code == 0 and dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        final_status = "dry-run-success"
    elif exit_code == 0:
        log(f"{ICON_OK} 最终状态: 成功")
    elif config_error:
        log(f"{ICON_FAIL} 最终状态: 配置错误")
    else:
        log(f"{ICON_FAIL} 最终状态: 失败")

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "task": SCRIPT_NAME,
        "mode": mode,
        "status": final_status if exit_code == 0 else summary_status,
        "exitCode": exit_code,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSucceeded": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notifyStatus": notify_status,
        "finishedAt": _iso(task_end),
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
