#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 阅次元论坛签到
# cron: 44 8 * * *
#
# 来源：kcenceis/abooky main.py（GPL-3.0）
# https://github.com/kcenceis/abooky
# 提交：8450f1cf16fd3c048afba41a936fc1f5bfb0885a
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# 本维护版沿用上游 GPL-3.0 许可。Copyright (C) kcenceis / abooky contributors。
# 完整 GPL-3.0 文本见上游仓库 LICENSE。
#
"""阅次元（abooky.com）Discuz 每日签到 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用账号密码登录 https://www.abooky.com（密码按上游 MD5 后提交）
- 登录页验证码：下载 seccode 图片，ddddocr 本地识别并校验（最多 5 次）
- 打开 k_misign 签到页，识别「您的签到排名」为今日已签
- 提取 formhash 后执行 plugin.php?id=k_misign:sign&operation=qiandao，再回读确认
- 移除硬编码空账号/密码、Server酱硬依赖、打印 loginhash/formhash/验证码原文、无超时请求
- 多账号：ABOOKY_ACCOUNT 每行「用户名&密码」（仅拆首个 &）
- ABOOKY_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY

建议 Cron：18 8 * * *。不打印密码、Cookie、Token、验证码原文或原始响应。
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
        _ql_notify_identities = ('5254d901222129dc', 'scripts/task_5254d901.py', 'task_5254d901.py', 'task_5254d901')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import hashlib
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

SCRIPT_NAME = "阅次元论坛签到"
CATALOG_ID = "5254d901222129dc"
SCRIPT_FILENAME = "candidate.py"
BASE_URL = "https://www.abooky.com/"
MEMBER_URL = "https://www.abooky.com/member.php"
MISC_URL = "https://www.abooky.com/misc.php"
SIGN_PAGE = "https://www.abooky.com/plugin.php?id=k_misign:sign"
SIGN_URL_TMPL = (
    "https://www.abooky.com/plugin.php?id=k_misign:sign"
    "&operation=qiandao&formhash={formhash}&format=empty&inajax=1&ajaxtarget=JD_sign"
)
UA = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
)
HTTP_TIMEOUT = 20
MAX_CAPTCHA_ATTEMPTS = 5
DRY_RUN_ENV = "ABOOKY_DRY_RUN"
CRED_ENV = "ABOOKY_ACCOUNT"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

_OCR = None


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
    raw = os.getenv("ABOOKY_TIMEOUT", "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError:
        return HTTP_TIMEOUT
    return max(5, min(90, value))


def password_md5(password: str) -> str:
    """按上游 passwordHex：提交前对明文密码做 MD5。"""
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(CRED_ENV)
    if primary is not None and primary.strip() != "":
        return primary, CRED_ENV
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
        "scripts/abooky_signin.py",
        "abooky_signin.py",
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


def _get_ocr():
    global _OCR
    if _OCR is not None:
        return _OCR
    try:
        import ddddocr  # type: ignore

        _OCR = ddddocr.DdddOcr(show_ad=False)
        return _OCR
    except Exception as exc:
        raise RuntimeError(
            "本地 OCR 依赖不可用（ddddocr）。请在运行环境安装：pip install ddddocr"
        ) from exc


class ForumClient:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))

    def request_bytes(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> bytes:
        full_url = url
        if params:
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}{urlencode(params)}"
        body = None
        headers = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Referer": referer or "https://www.abooky.com/member.php?mod=registerqq",
            "Host": "www.abooky.com",
            "DNT": "1",
            "Connection": "close",
        }
        if data is not None:
            body = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(full_url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"网络错误: {type(exc.reason).__name__}") from exc
        except Exception as exc:
            raise RuntimeError(f"请求失败: {type(exc).__name__}") from exc

    def request_text(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> str:
        raw = self.request_bytes(
            url, method=method, data=data, params=params, referer=referer
        )
        return raw.decode("utf-8", errors="replace")


def _extract_formhash(html: str) -> str:
    patterns = (
        r'name="formhash"\s+value="([^"]+)"',
        r'<input type="hidden" name="formhash" value="(.+?)"\s*/?>',
        r"formhash=([0-9a-fA-F]+)",
        r"formhash=([^\"'&>\s]+)",
    )
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    raise RuntimeError("未能解析 formhash")


def _extract_loginhash(html: str) -> str:
    m = re.search(r'<div id="main_messaqge_(.+?)">', html)
    if m:
        return m.group(1)
    m = re.search(r"loginhash=([0-9a-zA-Z]+)", html)
    if m:
        return m.group(1)
    raise RuntimeError("未能解析 loginhash")


def _extract_seccodehash(html: str) -> str:
    m = re.search(
        r"<script type=\"text/javascript\" reload=\"1\">updateseccode\('(.+?)'",
        html,
    )
    if m:
        return m.group(1)
    m = re.search(r"updateseccode\('([^']+)'", html)
    if m:
        return m.group(1)
    raise RuntimeError("未能解析验证码 seccodehash")


def _extract_display_name(html: str, username: str) -> str:
    for pattern in (
        r"欢迎您回来[，,]\s*(.+?)[，,]",
        r'title="访问我的空间">([^<]+)</a>',
        r'id="um"[^>]*>[\s\S]*?<strong>([^<]+)</strong>',
    ):
        m = re.search(pattern, html)
        if m:
            name = m.group(1).strip()
            if name:
                return name
    return username


def _already_signed(html: str) -> bool:
    return "您的签到排名" in html


def _login_looks_failed(html: str) -> bool:
    markers = (
        "密码错误",
        "登录失败",
        "用户名不存在",
        "安全提问",
        "验证码填写错误",
        "请输入验证码",
    )
    return any(m in html for m in markers)


def _solve_and_check_captcha(
    client: ForumClient, seccodehash: str
) -> str:
    update_html = client.request_text(
        MISC_URL,
        params={
            "mod": "seccode",
            "action": "update",
            "idhash": seccodehash,
            "modid": "member::logging",
        },
    )
    img_m = re.search(r'width="100" height="30" src="(.+?)"', update_html)
    if not img_m:
        img_m = re.search(r'src="(misc\.php\?[^"]*seccode[^"]*)"', update_html)
    if not img_m:
        raise RuntimeError("未能解析验证码图片地址")
    img_path = img_m.group(1)
    img_url = img_path if img_path.startswith("http") else urljoin(BASE_URL, img_path)
    img_bytes = client.request_bytes(img_url)
    if not img_bytes:
        raise RuntimeError("验证码图片为空")

    ocr = _get_ocr()
    try:
        code = ocr.classification(img_bytes)
    except Exception as exc:
        raise RuntimeError(f"验证码识别失败: {type(exc).__name__}") from exc
    if not isinstance(code, str) or not code.strip():
        raise RuntimeError("验证码识别结果为空")
    code = code.strip()

    check_html = client.request_text(
        MISC_URL,
        params={
            "mod": "seccode",
            "action": "check",
            "inajax": "1",
            "idhash": seccodehash,
            "modid": "member::logging",
            "secverify": code,
        },
    )
    if re.search(r"succeed", check_html, re.I):
        return code
    if re.search(r"invalid", check_html, re.I):
        raise RuntimeError("验证码识别未通过校验")
    raise RuntimeError("验证码校验响应异常")


def login_with_captcha(
    client: ForumClient, username: str, password: str
) -> str:
    """登录阅次元；返回可展示身份名。密码按上游 MD5 后提交。"""
    hashed = password_md5(password)
    last_error = "登录失败"
    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        log(f"  登录尝试 {attempt}/{MAX_CAPTCHA_ATTEMPTS}")
        login_html = client.request_text(
            MEMBER_URL,
            params={"referer": "", "mod": "logging", "action": "login"},
        )
        try:
            loginhash = _extract_loginhash(login_html)
            formhash = _extract_formhash(login_html)
            seccodehash = _extract_seccodehash(login_html)
        except RuntimeError as exc:
            last_error = str(exc)
            continue

        try:
            captcha = _solve_and_check_captcha(client, seccodehash)
            log(f"  {ICON_OK} 验证码识别通过（不输出原文）")
        except RuntimeError as exc:
            last_error = str(exc)
            log(f"  {ICON_WARN} {last_error}，将重试")
            continue

        post_data = {
            "formhash": formhash,
            "questionid": "0",
            "answer": "",
            "username": username,
            "password": hashed,
            "referer": "https://www.abooky.com/./",
            "seccodehash": seccodehash,
            "seccodemodid": "member::logging",
            "seccodeverify": captcha,
        }
        login_resp = client.request_text(
            MEMBER_URL,
            method="POST",
            params={
                "mod": "logging",
                "action": "login",
                "loginsubmit": "yes",
                "loginhash": loginhash,
                "inajax": "1",
            },
            data=post_data,
        )
        if _login_looks_failed(login_resp):
            if "验证码" in login_resp:
                last_error = "登录响应提示验证码相关失败"
                continue
            raise RuntimeError("登录失败：账号或密码不正确")

        identity = _extract_display_name(login_resp, username)
        # 回读签到页确认会话
        sign_page = client.request_text(SIGN_PAGE)
        if (
            username not in sign_page
            and "退出" not in sign_page
            and "退出登录" not in sign_page
            and "您的签到排名" not in sign_page
            and "JD_sign" not in sign_page
        ):
            if _login_looks_failed(login_resp):
                raise RuntimeError("登录失败：账号或密码不正确")
            last_error = "登录失败：签到页未检测到已登录会话"
            continue
        return _extract_display_name(sign_page, identity)

    raise RuntimeError(f"登录失败（已重试 {MAX_CAPTCHA_ATTEMPTS} 次）: {last_error}")


def perform_sign(client: ForumClient) -> Dict[str, Any]:
    sign_page = client.request_text(SIGN_PAGE)
    if _already_signed(sign_page):
        return {
            "already_signed": True,
            "sign_message": "今日已签到（检测到签到排名）",
        }
    formhash = _extract_formhash(sign_page)
    client.request_text(SIGN_URL_TMPL.format(formhash=formhash))
    confirm = client.request_text(SIGN_PAGE)
    if not _already_signed(confirm):
        # 兼容上游：部分站点 ajax 成功但排名文案延迟；再看一次按钮态
        if "JD_sign" in confirm and "qiandao" in confirm.lower():
            raise RuntimeError("签到失败：回读页仍可发起签到")
        raise RuntimeError("签到失败：回读页未出现签到排名")
    return {
        "already_signed": False,
        "sign_message": "签到成功（回读确认出现签到排名）",
    }


def login_and_sign(username: str, password: str, timeout: int) -> Dict[str, Any]:
    client = ForumClient(timeout=timeout)
    identity = login_with_captcha(client, username, password)
    outcome = perform_sign(client)
    outcome["identity"] = identity
    return outcome


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

    log_stage(2, "预演验证码登录", "跳过真实网络请求与 OCR")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将登录 www.abooky.com（含验证码识别）")

    log_stage(3, "预演签到", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将执行 k_misign 签到并以签到排名回读确认")

    log_stage(4, "预演汇总", "不声明业务成功")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演完成")

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
        log_stage(1, "校验账号格式")
        if not account.get("username") or not account.get("password"):
            raise RuntimeError("账号凭据不完整")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出凭据）")

        stage2_start = _now()
        log_stage(2, "验证码登录阅次元")
        client = ForumClient(timeout=timeout)
        identity = login_with_captcha(
            client, account["username"], account["password"]
        )
        result["identity"] = identity
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  {ICON_OK} 登录成功，身份: {identity}（耗时 {stage2_ms}ms）")
        stats["success"] += 1

        log_stage(3, "执行并确认签到")
        outcome = perform_sign(client)
        sign_msg = outcome.get("sign_message") or ""
        if outcome.get("already_signed"):
            stats["alreadyComplete"] += 1
            log(f"  {ICON_DONE} {sign_msg}")
            result["message"] = sign_msg
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} {sign_msg}")
            result["message"] = sign_msg
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
