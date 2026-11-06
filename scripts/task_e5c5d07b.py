#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: hao4k每日签到
# cron: 55 8 * * *
#
# 来源（合并）：
# 1) zhoushanbao1994/hao4k_auto_chech_in signin.py
#    https://github.com/zhoushanbao1994/hao4k_auto_chech_in
#    提交：009d83bf00a9439f977a537a9b6690ff030c65ea
# 2) cy920820/hao4k-signin-action signin.py（已发布维护基线）
#    https://github.com/cy920820/hao4k-signin-action
#    提交：687e628f799d53f8db8d8e6e225013e1904c0f25
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2021 Zlzzzupup
# Copyright (c) contributors of zhoushanbao1994/hao4k_auto_chech_in
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the Software), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
"""hao4k.cn Discuz 每日签到（k_misign）- 青龙维护版。

功能清点（相对 zhoushanbao1994/hao4k_auto_chech_in signin.py）：
- 使用账号密码登录 https://www.hao4k.cn
- 打开 k_misign 签到页，识别「您的签到排名」为今日已签
- 提取 formhash 后执行 plugin.php?id=k_misign:sign&operation=qiandao
- 回读签到页验证成功，并解析签到排名/连续天数/等级/积分奖励/总天数/今日签到人数
- 读取积分页 H币、K币摘要（只读展示）
- 移除 Bark 硬依赖、打印密码/form_data/原始响应、无超时请求、临近午夜 sleep 等待
- 多账号：HAO4K_ACCOUNT 每行「用户名&密码」（仅拆首个 &；账号之间只用换行）
- 兼容旧变量 HAO4K_USERNAME + HAO4K_PASSWORD（单账号）
- HAO4K_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY

建议 Cron：41 8 * * *。不打印密码、Cookie、Token 或原始响应。
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
        _ql_notify_identities = ('e5c5d07b8910c44e', 'scripts/task_e5c5d07b.py', 'task_e5c5d07b.py', 'task_e5c5d07b')
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
import traceback
from datetime import datetime
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

SCRIPT_NAME = "hao4k每日签到"
CATALOG_ID = "e5c5d07b8910c44e"
SCRIPT_FILENAME = "candidate.py"
BASE_URL = "https://www.hao4k.cn/"
LOGIN_PAGE = "https://www.hao4k.cn/member.php?mod=logging&action=login"
SIGN_PAGE = "https://www.hao4k.cn/k_misign-sign.html"
SIGN_URL_TMPL = (
    "https://www.hao4k.cn/plugin.php?id=k_misign:sign"
    "&operation=qiandao&formhash={formhash}&format=empty"
)
CREDIT_URL = "https://www.hao4k.cn/home.php?mod=spacecp&ac=credit"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.106 Safari/537.36"
)
HTTP_TIMEOUT = 20
DRY_RUN_ENV = "HAO4K_DRY_RUN"
CRED_ENV = "HAO4K_ACCOUNT"
LEGACY_USER_ENV = "HAO4K_USERNAME"
LEGACY_PASS_ENV = "HAO4K_PASSWORD"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"


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
    raw = os.getenv("HAO4K_TIMEOUT", "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError:
        return HTTP_TIMEOUT
    return max(5, min(90, value))


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(CRED_ENV)
    if primary is not None and primary.strip() != "":
        return primary, CRED_ENV
    user = (os.getenv(LEGACY_USER_ENV) or "").strip()
    password = os.getenv(LEGACY_PASS_ENV)
    if user and password is not None and str(password).strip() != "":
        return f"{user}&{password}", f"{LEGACY_USER_ENV}+{LEGACY_PASS_ENV}"
    return "", ""


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    """每行一个账号；仅按第一个 & 分割用户名与密码。账号之间只用换行。"""
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
        "7a56bf211c074a00",
        SCRIPT_FILENAME,
        f"scripts/{SCRIPT_FILENAME}",
        "scripts/hao4k_signin.py",
        "hao4k_signin.py",
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
            "Referer": BASE_URL,
            "Connection": "close",
        }
        if data is not None:
            body = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"网络错误: {type(exc.reason).__name__}") from exc
        except Exception as exc:
            raise RuntimeError(f"请求失败: {type(exc).__name__}") from exc


def _extract_login_action(html: str) -> str:
    for action in re.findall(r'action="(.*?)"', html):
        if "loginhash" in action:
            action = action.replace("&amp;", "&").replace("amp;", "")
            if action.startswith("http"):
                return action + ("&inajax=1" if "inajax=" not in action else "")
            return urljoin(BASE_URL, action) + (
                "&inajax=1" if "inajax=" not in action else ""
            )
    raise RuntimeError("未能从登录页解析 loginhash/action")


def _extract_formhash(html: str) -> str:
    patterns = (
        r'name="formhash"\s+value="([^"]+)"',
        r"formhash=([0-9a-fA-F]+)",
        r"formhash=([^\"'&>\s]+)",
    )
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    raise RuntimeError("未能解析 formhash")


def _extract_display_name(html: str, username: str) -> str:
    for pattern in (
        r"欢迎您回来[，,]\s*(.+?)[，,]",
        r'title="访问我的空间">([^<]+)</a>',
        r'id="um"[^>]*>[\s\S]*?<strong>([^<]+)</strong>',
    ):
        m = re.search(pattern, html)
        if m:
            name = m.group(1).strip()
            if name and name != username:
                return name
            if name:
                return name
    return username


def _already_signed(html: str) -> bool:
    return "您的签到排名" in html


def _input_value(html: str, element_id: str) -> str:
    patterns = (
        rf'id="{element_id}"[^>]*value="([^"]*)"',
        rf'value="([^"]*)"[^>]*id="{element_id}"',
    )
    for pattern in patterns:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return ""


def parse_sign_stats(html: str) -> Dict[str, str]:
    """从签到页解析可展示的非敏感统计字段。"""
    stats: Dict[str, str] = {}
    rank = re.search(r"您的签到排名：\s*(\d+)", html)
    if rank:
        stats["signin_ranking"] = f"签到排名：{rank.group(1)}"
    today = re.search(r"(\d+)\s*<span>\s*人\s*</span>", html)
    if not today:
        today = re.search(r"今日签到[^\d]*(\d+)\s*人", html)
    if today:
        stats["today_signin"] = f"今日签到人数：{today.group(1)}"
    consecutive = _input_value(html, "lxdays")
    if consecutive:
        stats["consecutive_days"] = f"连续天数：{consecutive}天"
    level = _input_value(html, "lxlevel")
    if level:
        stats["signin_level"] = f"签到等级：{level}"
    reward = _input_value(html, "lxreward")
    if reward:
        stats["points_reward"] = f"积分奖励：{reward}"
    total = _input_value(html, "lxtdays")
    if total:
        stats["total_days"] = f"总天数：{total}天"
    return stats


def parse_credit_summary(html: str) -> Dict[str, str]:
    """从积分页解析 H币/K币只读摘要。"""
    credits: Dict[str, str] = {}
    h = re.search(r"<em>\s*H币\s*:\s*</em>\s*(\d+)", html, re.I)
    if not h:
        h = re.search(r"H币\s*[:：]\s*(\d+)", html)
    if h:
        credits["h_currency"] = f"H币: {h.group(1)}"
    k = re.search(r"<em>\s*K币\s*:\s*</em>\s*(\d+)", html, re.I)
    if not k:
        k = re.search(r"K币\s*[:：]\s*(\d+)", html)
    if k:
        credits["k_currency"] = f"K币: {k.group(1)}"
    return credits


def _log_stats(stats: Dict[str, str]) -> None:
    order = (
        "signin_ranking",
        "consecutive_days",
        "signin_level",
        "points_reward",
        "total_days",
        "today_signin",
        "h_currency",
        "k_currency",
    )
    for key in order:
        value = stats.get(key)
        if value:
            log(f"  {ICON_OK} {value}")


def login_and_sign(username: str, password: str, timeout: int) -> Dict[str, Any]:
    """登录 hao4k 并执行 k_misign 签到；成功条件沿用上游回读校验。"""
    client = ForumClient(timeout=timeout)
    login_html = client.request(LOGIN_PAGE)
    login_url = _extract_login_action(login_html)
    formhash = _extract_formhash(login_html)
    payload = {
        "formhash": formhash,
        "referer": BASE_URL,
        "username": username,
        "password": password,
        "questionid": "0",
        "answer": "",
    }
    login_resp = client.request(login_url, method="POST", data=payload)
    identity_hint = _extract_display_name(login_resp, username)

    sign_page = client.request(SIGN_PAGE)
    if username not in sign_page and "退出" not in sign_page and "退出登录" not in sign_page:
        if any(k in login_resp for k in ("密码错误", "登录失败", "用户名不存在")):
            raise RuntimeError("登录失败：账号或密码不正确")
        raise RuntimeError("登录失败：签到页未检测到已登录会话")

    identity = _extract_display_name(sign_page, identity_hint or username)

    if _already_signed(sign_page):
        extras = parse_sign_stats(sign_page)
        try:
            credit_html = client.request(CREDIT_URL)
            extras.update(parse_credit_summary(credit_html))
        except Exception:
            pass
        return {
            "identity": identity,
            "already_signed": True,
            "sign_message": "今日已签到（检测到签到排名）",
            "extras": extras,
        }

    sign_formhash = _extract_formhash(sign_page)
    client.request(SIGN_URL_TMPL.format(formhash=sign_formhash))
    confirm = client.request(SIGN_PAGE)
    if not _already_signed(confirm):
        raise RuntimeError("签到失败：回读页未出现签到排名")

    extras = parse_sign_stats(confirm)
    try:
        credit_html = client.request(CREDIT_URL)
        extras.update(parse_credit_summary(credit_html))
    except Exception:
        pass

    return {
        "identity": identity,
        "already_signed": False,
        "sign_message": "签到成功（回读确认出现签到排名）",
        "extras": extras,
    }


def run_account_dry(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始（预演）——")
    stats = {
        "total": 4,
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

    log_stage(2, "预演登录", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将登录 www.hao4k.cn")

    log_stage(3, "预演签到", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将执行 k_misign 签到并以签到排名回读确认")

    log_stage(4, "预演积分摘要", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将读取签到统计与 H币/K币摘要")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats
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
        "total": 4,
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
        log_stage(1, "校验账号格式")
        if not account.get("username") or not account.get("password"):
            raise RuntimeError("账号凭据不完整")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出凭据）")

        stage2_start = _now()
        log_stage(2, "登录 hao4k")
        outcome = login_and_sign(
            account["username"], account["password"], timeout=timeout
        )
        identity = outcome.get("identity") or label
        result["identity"] = identity
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  {ICON_OK} 登录成功，身份: {identity}（含签到会话，耗时 {stage2_ms}ms）")
        stats["success"] += 1

        log_stage(3, "确认签到结果")
        sign_msg = outcome.get("sign_message") or ""
        if outcome.get("already_signed"):
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} {sign_msg}")
            result["message"] = sign_msg
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} {sign_msg}")
            result["message"] = sign_msg

        log_stage(4, "签到统计与积分摘要")
        extras = outcome.get("extras") or {}
        if extras:
            stats["success"] += 1
            _log_stats(extras)
            detail_parts = [extras[k] for k in (
                "signin_ranking",
                "consecutive_days",
                "signin_level",
                "points_reward",
                "total_days",
                "today_signin",
                "h_currency",
                "k_currency",
            ) if extras.get(k)]
            if detail_parts:
                result["message"] = f"{result['message']}；" + "；".join(detail_parts)
        else:
            stats["skipped"] += 1
            log(f"  {ICON_SKIP} 未解析到签到统计或积分摘要（不影响签到成功判定）")

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


def main() -> int:
    task_start = _now()
    dry = _is_dry_run()
    mode = "dry-run" if dry else "live"
    timeout = _http_timeout()

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
    log(f"最终状态：{summary_status}")
    if dry and not config_error:
        print("DRY_RUN_OK")

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
