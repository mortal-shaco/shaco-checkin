#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: LaTeX工作室签到
# cron: 10 1 * * *
#
# 来源：BNDou/Auto_Check_In checkIn_LaTeX.py（GPL-3.0-only）
# https://github.com/BNDou/Auto_Check_In
# 分支：main
# 提交：3355d65c62a1d09643092de61d0e6d5175b2323f
# 原路径：checkIn_LaTeX.py
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) BNDou / Auto_Check_In contributors
# 本维护版沿用上游 GPL-3.0-only 许可。
# 你可以通过自由软件基金会发布的 GNU 通用公共许可证第 3 版
# 重新分发和/或修改本程序。
# 本程序的分发希望它有用，但不提供任何担保。
# 完整许可证文本见上游仓库 LICENSE。
#
"""LaTeX 工作室（latexstudio.net）账号每日签到（青龙维护版）。

功能清点（相对上游 checkIn_LaTeX.py）：
- 使用站点 Token 读取用户信息（昵称、会员套餐、余额、积分、累计签到天数、上次登录）
- 调用签到接口完成每日签到，并以业务 code / 文案核验成功或今日已签到
- 移除 && 账号分隔、无超时请求、配置缺失仍退出 0、失败未计入退出码等问题
- 多账号：COOKIE_LATEX_TOKEN 每个非空行一个 Token（账号之间只用换行）
- LATEX_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 标准库实现 HTTP（不再依赖 requests 或仓库内 utils.notify 路径）

建议 Cron：2 1 * * *。不打印 Token、Cookie、会话值或原始响应。
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
        _ql_notify_identities = ('0fd26bb9b65bd35b', 'scripts/checkin_latex.py', 'checkin_latex.py', 'checkin_latex')
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
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCRIPT_NAME = "LaTeX工作室签到"
CATALOG_ID = "0fd26bb9b65bd35b"
SCRIPT_FILENAME = "candidate.py"
BASE_API = "https://www.latexstudio.net/api"
USER_PATH = "/user/index"
SIGN_PATH = "/Sign/Sign"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 256 * 1024
DRY_RUN_ENV = "LATEX_DRY_RUN"
CRED_ENV = "COOKIE_LATEX_TOKEN"
TIMEOUT_ENV = "LATEX_TIMEOUT"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

ALREADY_SIGN_TOKENS = (
    "已签到",
    "已经签到",
    "今日已签",
    "重复签到",
    "签过到",
)
SUCCESS_SIGN_TOKENS = (
    "签到成功",
    "打卡成功",
    "成功",
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
    """每个非空行一个 Token；账号之间只用换行分隔。"""
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if any(ord(ch) < 32 for ch in text):
            raise ValueError(f"第 {line_no} 行 Token 含非法控制字符")
        accounts.append(text)
    return accounts


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(CRED_ENV)
    if primary is not None and primary.strip() != "":
        return primary, CRED_ENV
    return "", ""


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
        "scripts/latex_checkin.py",
        "latex_checkin.py",
        "checkIn_LaTeX.py",
        SCRIPT_NAME,
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


def _api_request(method: str, path: str, token: str, timeout: int) -> Dict[str, Any]:
    """调用 latexstudio API；Token 仅作为查询参数，不写入日志。"""
    query = urlencode({"token": token})
    url = f"{BASE_API}{path}?{query}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": UA,
        "Connection": "close",
    }
    if method.upper() == "POST":
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        data = b""
    else:
        data = None
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("响应过大，已中止读取")
            charset = resp.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
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
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise RuntimeError("接口返回无法解析为 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("接口返回结构异常")
    return payload


def _msg_of(payload: Dict[str, Any]) -> str:
    value = payload.get("msg")
    if value is None:
        value = payload.get("message")
    if value is None:
        return ""
    return str(value).strip()


def _code_of(payload: Dict[str, Any]) -> Any:
    if "code" in payload:
        return payload.get("code")
    if "status" in payload:
        return payload.get("status")
    return None


def _is_business_ok(code: Any) -> bool:
    if code is True:
        return True
    if code is False or code is None:
        return False
    if isinstance(code, (int, float)):
        return int(code) == 1
    text = str(code).strip().lower()
    return text in {"1", "ok", "success", "true"}


def _classify_sign(payload: Dict[str, Any]) -> Tuple[str, str]:
    """返回 (status, message)；status 为 success / already / failure。"""
    msg = _msg_of(payload)
    code = _code_of(payload)
    if any(token in msg for token in ALREADY_SIGN_TOKENS):
        return "already", msg or "今日已签到"
    if _is_business_ok(code):
        return "success", msg or "签到成功"
    if any(token in msg for token in SUCCESS_SIGN_TOKENS):
        return "success", msg or "签到成功"
    if msg:
        return "failure", msg
    return "failure", "签到失败：未返回可识别的成功状态"


def fetch_user(token: str, timeout: int) -> Dict[str, Any]:
    payload = _api_request("GET", USER_PATH, token, timeout)
    if not _is_business_ok(_code_of(payload)):
        raise RuntimeError(_msg_of(payload) or "获取用户信息失败，可能是 Token 失效")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("用户信息缺少 data 字段")
    nickname = str(data.get("nickname") or "").strip()
    vip_text = str(data.get("vip_text") or "").strip()
    money = data.get("money")
    score = data.get("score")
    logintime = str(data.get("logintime") or "").strip()
    tongji = data.get("tongji") if isinstance(data.get("tongji"), dict) else {}
    sign_num = tongji.get("sign_num")
    return {
        "nickname": nickname,
        "vip_text": vip_text,
        "money": money,
        "score": score,
        "logintime": logintime,
        "sign_num": sign_num,
    }


def do_sign(token: str, timeout: int) -> Tuple[str, str]:
    payload = _api_request("POST", SIGN_PATH, token, timeout)
    return _classify_sign(payload)


def run_account_dry(index: int, total: int, token: str) -> Dict[str, Any]:
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
    }

    log_stage(1, "校验 Token", "已提供非空凭据")
    if not token:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = "Token 为空"
        log(f"  {ICON_FAIL} {result['message']}")
    else:
        stats["success"] += 1
        log(f"  {ICON_OK} 格式有效（不输出 Token）")

        log_stage(2, "预演读取用户信息", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将请求 {BASE_API}{USER_PATH}")

        log_stage(3, "预演每日签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将请求 {BASE_API}{SIGN_PATH}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(index: int, total: int, token: str, timeout: int) -> Dict[str, Any]:
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
    try:
        log_stage(1, "校验 Token")
        if not token:
            raise RuntimeError("Token 为空")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出 Token）")

        stage2_start = _now()
        log_stage(2, "读取用户信息")
        user = fetch_user(token, timeout)
        nickname = user.get("nickname") or ""
        identity = nickname if nickname else label
        result["identity"] = identity
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  {ICON_OK} 身份: {identity}（耗时 {stage2_ms}ms）")
        if user.get("vip_text"):
            log(f"  会员套餐: {user['vip_text']}")
        if user.get("money") is not None:
            log(f"  余额: {user['money']}")
        if user.get("score") is not None:
            log(f"  积分: {user['score']}")
        if user.get("sign_num") is not None:
            log(f"  累计已签到: {user['sign_num']} 天")
        if user.get("logintime"):
            log(f"  上次登录: {user['logintime']}")
        stats["success"] += 1

        stage3_start = _now()
        log_stage(3, "执行每日签到")
        sign_status, sign_msg = do_sign(token, timeout)
        stage3_ms = int((_now() - stage3_start).total_seconds() * 1000)
        if sign_status == "already":
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} {sign_msg}（耗时 {stage3_ms}ms）")
            result["message"] = sign_msg
            result["ok"] = True
            result["status"] = "success"
        elif sign_status == "success":
            stats["success"] += 1
            log(f"  {ICON_OK} {sign_msg}（耗时 {stage3_ms}ms）")
            result["message"] = sign_msg
            result["ok"] = True
            result["status"] = "success"
        else:
            raise RuntimeError(sign_msg or "签到失败")
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
                f"获取方式: 登录 latexstudio.net，在个人中心或抓包获取 API Token，"
                f"写入青龙环境变量 {CRED_ENV}；每行一个账号 Token"
            )
            log("账号数量: 0")
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

            log(f"账号数量: {len(accounts)}")
            if not config_error and not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 未解析到任何有效账号")

            if not config_error:
                total = len(accounts)
                for idx, token in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, token)
                    else:
                        ar = run_account_live(idx, total, token, timeout=timeout)
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
        "TASK_SUMMARY=" + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
