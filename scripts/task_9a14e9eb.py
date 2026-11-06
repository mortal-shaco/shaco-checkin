#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: MT论坛签到
# cron: 39 0 * * *
"""
MT论坛自动签到（维护版）

上游来源: https://github.com/gaohan-cmd/mt (main.py)
原始作者与许可证: Apache-2.0 — Copyright 保留自上游仓库

功能:
  - 使用账号密码登录 MT 论坛 (bbs.binmt.cc)
  - 执行每日签到 (k_misign)

环境变量:
  MTLUNTAN          必填。每行一个账号，格式: 用户名&密码（仅按第一个 & 分割）
  mtluntan          可选兼容别名（当 MTLUNTAN 未设置时生效）
  MTLUNTAN_DRY_RUN  设为 1/true/yes/on 时启用断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS  通知开关（见青龙通知策略）

定时: 0 0 * * *
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
        _ql_notify_identities = ('9a14e9eb7997f1a3', 'scripts/task_9a14e9eb.py', 'task_9a14e9eb.py', 'task_9a14e9eb')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
SCRIPT_NAME = "MT论坛签到"
CATALOG_ID = "9a14e9eb7997f1a3"
SCRIPT_FILENAME = "candidate.py"
BASE_URL = "https://bbs.binmt.cc"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/96.0.4664.45 Safari/537.36"
)
HTTP_TIMEOUT = 20
DRY_RUN_ENV = "MTLUNTAN_DRY_RUN"
CRED_ENV = "MTLUNTAN"
CRED_ENV_ALIAS = "mtluntan"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"


# ---------------------------------------------------------------------------
# 时间 / 日志
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 环境 / 账号解析
# ---------------------------------------------------------------------------
def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_dry_run() -> bool:
    return _env_truthy(DRY_RUN_ENV)


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(CRED_ENV)
    if primary is not None and primary.strip() != "":
        return primary, CRED_ENV
    alias = os.getenv(CRED_ENV_ALIAS)
    if alias is not None and alias.strip() != "":
        return alias, CRED_ENV_ALIAS
    return "", ""


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    """每行一个账号；仅按第一个 & 分割用户名与密码。"""
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
            raise ValueError(
                f"第 {line_no} 行账号格式无效：用户名或密码为空"
            )
        accounts.append({"username": username, "password": password})
    return accounts


# ---------------------------------------------------------------------------
# 通知（青龙 notify.py / sendNotify）
# ---------------------------------------------------------------------------
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
        SCRIPT_NAME,
    }
    if sel in candidates:
        return True
    if sel.endswith("*") and SCRIPT_FILENAME.startswith(sel[:-1]):
        return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    selectors = _script_selectors()
    if selectors is None:
        # listed-only 默认：未设置脚本列表时发送
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
            import importlib.util

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


# ---------------------------------------------------------------------------
# HTTP（标准库，无第三方依赖）
# ---------------------------------------------------------------------------
class ForumClient:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, str]] = None,
    ) -> str:
        body = None
        headers = {
            "User-Agent": UA,
            "Referer": f"{BASE_URL}/forum.php",
        }
        if data is not None:
            from urllib.parse import urlencode

            body = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"网络错误: {exc.reason}") from exc
        except Exception as exc:
            raise RuntimeError(f"请求失败: {type(exc).__name__}: {exc}") from exc


def _extract_loginhash(html: str) -> str:
    m = re.search(r"loginhash=([^\"'&>]+)", html)
    if not m:
        raise RuntimeError("未能从登录页解析 loginhash")
    return m.group(1)


def _extract_formhash(html: str) -> str:
    m = re.search(r'name="formhash"\s+value="([^"]+)"', html)
    if not m:
        m = re.search(r'formhash"\s+value="([^"]+)"', html)
    if not m:
        raise RuntimeError("未能解析 formhash")
    return m.group(1)


def _parse_login_identity(login_html: str) -> str:
    m = re.search(r"欢迎您回来，(.*?)，现在", login_html)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_sign_root(xml_text: str) -> str:
    m = re.search(r"<root><([\s\S]*?)</root>", xml_text)
    if m:
        return m.group(1).strip()
    # 兼容直接返回文本
    text = xml_text.strip()
    if text:
        return text[:200]
    return ""


def login_and_sign(username: str, password: str) -> Dict[str, Any]:
    """登录并签到。成功时返回 identity / sign_message。"""
    client = ForumClient()
    login_page_url = (
        f"{BASE_URL}/member.php?mod=logging&action=login"
        "&infloat=yes&handlekey=login&inajax=1&ajaxtarget=fwin_content_login"
    )
    page = client.request(login_page_url)
    loginhash = _extract_loginhash(page)
    formhash = _extract_formhash(page)
    denurl = (
        f"{BASE_URL}/member.php?mod=logging&action=login&loginsubmit=yes"
        f"&handlekey=login&loginhash={loginhash}&inajax=1"
    )
    payload = {
        "formhash": formhash,
        "referer": f"{BASE_URL}/forum.php",
        "loginfield": "username",
        "username": username,
        "password": password,
        "questionid": "0",
        "answer": "",
    }
    login_resp = client.request(denurl, method="POST", data=payload)
    if "欢迎您回来" not in login_resp:
        # 常见失败提示（不打印原始全文）
        if "密码错误" in login_resp or "登录失败" in login_resp:
            raise RuntimeError("登录失败：账号或密码不正确")
        raise RuntimeError("登录失败：未检测到欢迎回来标识")

    identity = _parse_login_identity(login_resp)
    sign_page = client.request(f"{BASE_URL}/k_misign-sign.html")
    sign_formhash = _extract_formhash(sign_page)
    qdurl = (
        f"{BASE_URL}/plugin.php?id=k_misign:sign&operation=qiandao"
        f"&format=text&formhash={sign_formhash}"
    )
    qd_resp = client.request(qdurl)
    sign_msg = _parse_sign_root(qd_resp)
    if not sign_msg:
        raise RuntimeError("签到失败：响应为空")
    if any(m in sign_msg for m in ("需要先登录", "未登录", "请先登录")):
        raise RuntimeError("签到失败：会话无效或未登录")

    already = any(k in sign_msg for k in ("已签", "已经签到", "重复签到"))
    # k_misign 成功常见文案：签到成功 / 已签到 / 奖励积分等非空正文
    explicit_ok = any(
        k in sign_msg for k in ("成功", "签到", "积分", "奖励")
    ) or already
    if not explicit_ok and re.search(r"(?i)error|fail|失败", sign_msg):
        raise RuntimeError(f"签到未成功: {sign_msg[:80]}")

    return {
        "identity": identity,
        "sign_message": sign_msg[:120],
        "already_signed": already,
    }


# ---------------------------------------------------------------------------
# 账号执行
# ---------------------------------------------------------------------------
def run_account_dry(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
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
    }

    log_stage(1, "校验账号格式", "用户名与密码均已提供")
    stats["success"] += 1
    log(f"  {ICON_OK} 格式有效（不输出凭据）")

    log_stage(2, "预演登录与签到", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将登录 bbs.binmt.cc 并执行 k_misign 签到")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    result["stats"] = stats
    return result


def run_account_live(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
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
    try:
        log_stage(1, "登录 MT 论坛")
        # 登录+签到合并在一次会话中，分步记录
        outcome = login_and_sign(account["username"], account["password"])
        identity = outcome.get("identity") or label
        result["identity"] = identity
        log(f"  {ICON_OK} 登录成功，身份: {identity}")
        stats["success"] += 1

        log_stage(2, "执行每日签到")
        sign_msg = outcome.get("sign_message") or ""
        if outcome.get("already_signed"):
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} 今日已签到: {sign_msg}")
            result["message"] = f"已签到: {sign_msg}"
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} 签到结果: {sign_msg}")
            result["message"] = f"签到成功: {sign_msg}"
        result["ok"] = True
        result["status"] = "success"
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


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
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
        raw, source_name = _read_credential_raw()
        if not raw:
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{ICON_FAIL} 未配置必填环境变量 {CRED_ENV}")
            log(
                f"获取方式: 在青龙环境变量中新增 {CRED_ENV}，"
                "每行一个账号，格式 用户名&密码"
            )
            log(f"账号数量: 0")
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
                for idx, acc in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, acc)
                    else:
                        ar = run_account_live(idx, total, acc)
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
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 未处理异常: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    # 任务统计
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

    # 通知正文（脱敏）
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
        f"账号总数: {total_accounts if not config_error else 0}",
        f"成功: {ok_count}",
        f"失败: {fail_count}",
        f"状态: {summary_status}",
    ]
    for a in account_results:
        lines.append(
            f"- {a.get('identity')}: {a.get('status')} / {a.get('message', '')[:80]}"
        )
    body = "\n".join(lines)
    notify_status = send_notification(SCRIPT_NAME, body)
    log(f"通知状态: {notify_status}")

    final_icon = {
        "success": ICON_OK,
        "dry-run": ICON_OK,
        "partial-failure": ICON_WARN,
        "failure": ICON_FAIL,
        "configuration-error": ICON_FAIL,
    }.get(summary_status, ICON_WARN)
    log(f"最终状态: {final_icon} {summary_status}")

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
    print(f"TASK_SUMMARY={json.dumps(task_summary, ensure_ascii=False)}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
