#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 魅魔AI每日签到
# cron: 26 9 * * *
#
# 来源：KingPlustar/Meimodu-auto-signin（MIT）
# https://github.com/KingPlustar/Meimodu-auto-signin
# 分支：main
# 提交：d091efc1137e1981d9c96ba116d59cbf941f3625
# 原路径：config.py（合并同仓 main.py / meimo_crawler.py / meimo_logger.py / schemas/config.py）
# SPDX-License-Identifier: MIT
#
# Copyright (c) KingPlustar / Meimodu-auto-signin contributors
# 本维护版沿用上游 MIT 许可，保留原作者版权与归属声明。
#
"""魅魔 AI（Meimodu / Meimoai / sexyai）每日签到（青龙维护版）。

功能清点（相对上游同仓脚本）：
- 连接站点并可选邮箱密码登录，或使用 Cookie 跳过登录
- 查询用户信息（昵称、电量/余额）
- 调用 /api/user/sign-in 完成每日签到，并核验业务成功或今日已签
- 签到前后对比电量变化（可取得时）
- 多账号：MEIMODU_ACCOUNT 每个非空行一个账号
- MEIMODU_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 标准库 urllib 实现 HTTP；超时与业务 success 核验；任一账号失败非零退出
- 移除 cloudscraper / dotenv / pydantic / 本地 logs 写文件 / 打印 Cookie 与会话头

建议 Cron：20 9 * * *。不打印 Cookie、Token、密码或原始响应。
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
            "03d0e66b5d71fba8",
            "scripts/meimodu_signin.py",
            "meimodu_signin.py",
            "candidate.py",
            "meimodu",
            "魅魔AI每日签到",
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
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SCRIPT_NAME = "魅魔AI每日签到"
CATALOG_ID = "03d0e66b5d71fba8"
SCRIPT_FILENAME = "candidate.py"
DEFAULT_BASE_URL = "https://www.sexyai.ai/"
API_LOGIN = "/user/login"
API_SIGN_IN = "/user/sign-in"
API_INFO = "/user/info"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 15
MAX_RESPONSE_BYTES = 256 * 1024
DRY_RUN_ENV = "MEIMODU_DRY_RUN"
ACCOUNT_ENV = "MEIMODU_ACCOUNT"
BASE_URL_ENV = "MEIMODU_BASE_URL"
TIMEOUT_ENV = "MEIMODU_TIMEOUT"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

ALREADY_SIGN_MARKERS = (
    "已签到",
    "已经签到",
    "重复签到",
    "今日已签",
    "签到过了",
    "already",
    "signed",
)


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


@dataclass
class Account:
    """单个账号凭据。email/password 与 cookie 可并存；有 cookie 时优先跳过登录。"""

    email: str = ""
    password: str = ""
    cookie: str = ""

    def has_login(self) -> bool:
        return bool(self.email and self.password)

    def has_cookie(self) -> bool:
        return bool(self.cookie.strip())

    def usable(self) -> bool:
        return self.has_login() or self.has_cookie()


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


def _base_url() -> str:
    raw = (os.getenv(BASE_URL_ENV) or os.getenv("TARGET_URL") or DEFAULT_BASE_URL).strip()
    if not raw:
        return DEFAULT_BASE_URL
    if not raw.startswith(("http://", "https://")):
        raise SafeError(f"{BASE_URL_ENV} 须以 http:// 或 https:// 开头")
    if not raw.endswith("/"):
        raw += "/"
    return raw


def _api_root(base: str) -> str:
    return urljoin(base, "api")


def _looks_like_email_password(line: str) -> bool:
    if "#" not in line:
        return False
    email, _rest = line.split("#", 1)
    email = email.strip()
    return "@" in email and "." in email.split("@")[-1]


def parse_account_line(line: str, line_no: int) -> Account:
    text = line.strip()
    if not text or text.startswith("#"):
        raise ValueError("空行")
    if any(ord(ch) < 32 for ch in text):
        raise ValueError(f"第 {line_no} 行含非法控制字符")

    lower = text.lower()
    if lower.startswith("cookie:"):
        cookie = text.split(":", 1)[1].strip()
        if not cookie:
            raise ValueError(f"第 {line_no} 行 cookie: 后为空")
        return Account(cookie=cookie)

    if _looks_like_email_password(text):
        email, rest = text.split("#", 1)
        email = email.strip()
        # 允许 email#password 或 email#password#cookie:...
        if "#cookie:" in rest.lower():
            # 在不区分大小写的 cookie: 处分隔，保留密码中可能出现的 #
            marker = re.search(r"#cookie:", rest, flags=re.IGNORECASE)
            assert marker is not None
            password = rest[: marker.start()].strip()
            cookie = rest[marker.end() :].strip()
            if not password:
                raise ValueError(f"第 {line_no} 行密码为空")
            return Account(email=email, password=password, cookie=cookie)
        password = rest.strip()
        if not password:
            raise ValueError(f"第 {line_no} 行密码为空")
        return Account(email=email, password=password)

    # 其余非空行按 Cookie 处理（浏览器复制的原始 Cookie）
    return Account(cookie=text)


def parse_accounts(raw: str) -> List[Account]:
    accounts: List[Account] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text, line_no))
    return accounts


def _read_credential_raw() -> Tuple[str, str]:
    primary = os.getenv(ACCOUNT_ENV)
    if primary is not None and primary.strip() != "":
        return primary, ACCOUNT_ENV

    # 兼容上游 EMAIL/PASSWORD/COOKIE（单账号）
    email = (os.getenv("EMAIL") or os.getenv("MEIMODU_EMAIL") or "").strip()
    password = (os.getenv("PASSWORD") or os.getenv("MEIMODU_PASSWORD") or "").strip()
    cookie = (os.getenv("COOKIE") or os.getenv("MEIMODU_COOKIE") or "").strip()
    if cookie:
        return f"cookie:{cookie}", "COOKIE" if os.getenv("COOKIE") else "MEIMODU_COOKIE"
    if email and password:
        return f"{email}#{password}", "EMAIL+PASSWORD"
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
        "scripts/meimodu_signin.py",
        "meimodu_signin.py",
        SCRIPT_NAME,
        "meimodu",
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


def _safe_message(text: Any, limit: int = 120) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    s = re.sub(r"(?i)(authorization|cookie|token|password)\s*[:=]\s*\S+", r"\1=[已隐藏]", s)
    return s[:limit]


def _is_success_code(code: Any) -> bool:
    if code is None:
        return False
    if isinstance(code, bool):
        return code
    if isinstance(code, int):
        return code in (0, 200, 1)
    if isinstance(code, str):
        t = code.strip().lower()
        return t in {"0", "200", "1", "ok", "success", "true"}
    return False


def _is_already_signed(message: str) -> bool:
    lower = message.lower()
    return any(m.lower() in lower for m in ALREADY_SIGN_MARKERS)


def parse_api_payload(payload: Any) -> Tuple[str, Any, int, str]:
    """解析上游风格 JSON。

    返回 (kind, data, code, message)：
    - kind=data：业务数据体
    - kind=msg：业务消息/错误
    - kind=raw：无法归类
    """
    if not isinstance(payload, dict):
        return "raw", payload, -1, "响应非对象"

    code_raw = payload.get("code", payload.get("status", payload.get("errno")))
    message = (
        payload.get("message")
        or payload.get("msg")
        or payload.get("error")
        or payload.get("detail")
        or ""
    )
    message = str(message)

    try:
        code = int(code_raw) if code_raw is not None and str(code_raw).strip() != "" else 0
    except (TypeError, ValueError):
        code = -1

    if "data" in payload:
        if _is_success_code(code_raw) or (
            code_raw is None and payload.get("success") in (True, "true", 1, "1")
        ):
            return "data", payload.get("data"), code, message
        if code == 401 or code_raw == 401:
            return "msg", None, 401, message or "未授权"
        if message:
            return "msg", None, code, message

    if payload.get("success") in (True, "true", 1, "1") and "data" not in payload:
        return "data", True, code, message

    if code == 401 or code_raw == 401:
        return "msg", None, 401, message or "未授权"

    if _is_success_code(code_raw) and message == "":
        return "data", payload.get("result", True), code, message

    if message or code_raw is not None:
        return "msg", None, code if code_raw is not None else -1, message or f"业务码 {code_raw}"

    return "raw", payload, -1, "无法识别的响应结构"


def http_request(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]] = None,
    timeout: int = HTTP_TIMEOUT,
) -> Tuple[int, Any]:
    data = None
    req_headers = dict(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    elif method.upper() == "POST":
        data = b"{}"
        req_headers.setdefault("Content-Type", "application/json")

    req = Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("响应过大，已中止读取")
            charset = resp.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
            if not text.strip():
                return status, {}
            try:
                payload = json.loads(text)
            except Exception as exc:
                raise RuntimeError("接口返回无法解析为 JSON") from exc
            return status, payload
    except HTTPError as exc:
        try:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            text = raw.decode("utf-8", errors="replace") if raw else ""
            payload: Any = json.loads(text) if text.strip() else {}
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


class MeimoClient:
    def __init__(self, base_url: str, account: Account, timeout: int) -> None:
        self.base_url = base_url
        self.api_base = _api_root(base_url)
        self.account = account
        self.timeout = timeout
        self.authorization = ""
        self.headers: Dict[str, str] = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": UA,
            "Referer": base_url,
            "Origin": base_url.rstrip("/"),
            "Connection": "close",
        }
        if account.has_cookie():
            self.headers["Cookie"] = account.cookie.strip()

    def _url(self, endpoint: str) -> str:
        return f"{self.api_base}{endpoint}"

    def _auth_headers(self) -> Dict[str, str]:
        headers = dict(self.headers)
        if self.authorization:
            headers["Authorization"] = self.authorization
        return headers

    def connect(self) -> None:
        status, _payload = http_request(
            "GET", self.base_url, headers=self._auth_headers(), timeout=self.timeout
        )
        if status != 200:
            raise RuntimeError(f"无法连接站点（HTTP {status}）")

    def login(self, forced: bool = False) -> str:
        if not forced and self.account.has_cookie():
            return ""
        if not self.account.has_login():
            raise RuntimeError("缺少邮箱密码，无法登录")
        if forced:
            self.headers.pop("Cookie", None)

        status, payload = http_request(
            "POST",
            self._url(API_LOGIN),
            headers=self._auth_headers(),
            body={
                "username": self.account.email,
                "password": self.account.password,
            },
            timeout=self.timeout,
        )
        if status != 200:
            raise RuntimeError(f"登录失败（HTTP {status}）")

        kind, data, code, message = parse_api_payload(payload)
        if kind == "data" and isinstance(data, dict):
            token = str(data.get("token") or data.get("access_token") or "").strip()
            nickname = str(data.get("nickname") or data.get("username") or "").strip()
            if not token:
                raise RuntimeError("登录成功但未返回 token")
            self.authorization = token
            return nickname
        raise RuntimeError(f"登录失败：{_safe_message(message) or f'业务码 {code}'}")

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        status, payload = http_request(
            "POST",
            self._url(API_INFO),
            headers=self._auth_headers(),
            body={},
            timeout=self.timeout,
        )
        if status != 200:
            return None
        kind, data, code, message = parse_api_payload(payload)
        if kind == "msg" and code == 401:
            raise RuntimeError("未授权")
        if kind == "data" and isinstance(data, dict):
            return data
        if kind == "msg":
            return None
        return None

    def sign_in(self) -> Tuple[str, str]:
        """返回 (result_code, message)。result_code: OK / ALREADY。"""
        status, payload = http_request(
            "POST",
            self._url(API_SIGN_IN),
            headers=self._auth_headers(),
            body={},
            timeout=self.timeout,
        )
        if status != 200:
            raise RuntimeError(f"签到失败（HTTP {status}）")

        kind, _data, code, message = parse_api_payload(payload)
        if kind == "data":
            return "OK", "签到成功"
        if kind == "msg":
            if code == 401:
                raise RuntimeError("未授权")
            if _is_already_signed(message):
                return "ALREADY", _safe_message(message) or "今日已签到"
            raise RuntimeError(f"签到失败：{_safe_message(message) or f'业务码 {code}'}")
        raise RuntimeError("签到响应无法识别")


def emit_machine(out: Dict[str, Any]) -> None:
    safe = {
        k: v
        for k, v in out.items()
        if k not in {"cookie", "password", "token", "authorization", "raw"}
    }
    print(json.dumps(safe, ensure_ascii=False, default=str), flush=True)


def _identity_from_info(index: int, info: Optional[Dict[str, Any]]) -> str:
    label = f"账号{index}"
    if not info:
        return label
    nick = str(info.get("nickname") or info.get("username") or info.get("name") or "").strip()
    uid = info.get("id") or info.get("uid") or info.get("user_id")
    if nick:
        return nick
    if uid is not None and str(uid).strip():
        return f"{label}(UID {uid})"
    return label


def _balance_of(info: Optional[Dict[str, Any]]) -> Optional[float]:
    if not info:
        return None
    for key in ("balance", "power", "energy", "coin", "points"):
        val = info.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str) and val.strip():
            try:
                return float(val.strip())
            except ValueError:
                continue
    return None


def run_account_dry(index: int, total: int, account: Account, base_url: str) -> Dict[str, Any]:
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
        "resultCode": "DRY_RUN",
        "elapsedMs": 0,
    }

    log_stage(1, "校验账号凭据")
    if not account.usable():
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = "账号缺少 Cookie 或邮箱密码"
        result["resultCode"] = "NO_AUTH"
        log(f"  {ICON_FAIL} {result['message']}")
    else:
        mode = []
        if account.has_cookie():
            mode.append("Cookie")
        if account.has_login():
            mode.append("邮箱密码")
        stats["success"] += 1
        log(f"  {ICON_OK} 凭据就绪（{'+'.join(mode)}，不输出值）")

        api_base = _api_root(base_url)
        log_stage(2, "预演连接与登录", "跳过真实网络请求")
        stats["skipped"] += 1
        if account.has_cookie():
            log(f"  {ICON_SKIP} 断网预演：将使用 Cookie 跳过登录，探测 {base_url}")
        else:
            log(f"  {ICON_SKIP} 断网预演：将 POST {api_base}{API_LOGIN}")

        log_stage(3, "预演查询用户信息", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 POST {api_base}{API_INFO}")

        log_stage(4, "预演签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 POST {api_base}{API_SIGN_IN}")

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
    index: int, total: int, account: Account, base_url: str, timeout: int
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
        "resultCode": "ERROR",
        "elapsedMs": 0,
        "stats": stats,
    }
    machine: Dict[str, Any] = {"result": "ERROR", "report": "", "account": index}
    client = MeimoClient(base_url, account, timeout)
    info_before: Optional[Dict[str, Any]] = None

    try:
        log_stage(1, "校验账号凭据")
        if not account.usable():
            raise RuntimeError("账号缺少 Cookie 或邮箱密码")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪")

        stage2_start = _now()
        log_stage(2, "连接站点并登录")
        client.connect()
        nickname = ""
        if account.has_cookie():
            log(f"  {ICON_OK} 已配置 Cookie，跳过登录")
        else:
            nickname = client.login()
            if nickname:
                result["identity"] = nickname
                log(f"  {ICON_OK} 登录成功，昵称：{nickname}")
            else:
                log(f"  {ICON_OK} 登录成功")
        stats["success"] += 1
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  连接/登录阶段耗时 {stage2_ms}ms")

        def _fetch_info(reauth: bool = True) -> Optional[Dict[str, Any]]:
            try:
                return client.get_user_info()
            except RuntimeError as exc:
                if "未授权" in str(exc) and reauth and account.has_login():
                    log(f"  {ICON_WARN} 用户信息未授权，尝试重新登录")
                    nick = client.login(forced=True)
                    if nick:
                        result["identity"] = nick
                    return client.get_user_info()
                raise

        stage3_start = _now()
        log_stage(3, "查询用户信息")
        info_before = _fetch_info()
        stage3_ms = int((_now() - stage3_start).total_seconds() * 1000)
        identity = _identity_from_info(index, info_before)
        result["identity"] = identity
        bal = _balance_of(info_before)
        if info_before is None:
            stats["skipped"] += 1
            log(f"  {ICON_WARN} 获取用户信息失败，跳过电量对比（耗时 {stage3_ms}ms）")
        else:
            stats["success"] += 1
            bal_txt = f"，当前电量：{bal:g}" if bal is not None else ""
            log(f"  {ICON_OK} 用户昵称：{identity}{bal_txt}（耗时 {stage3_ms}ms）")

        stage4_start = _now()
        log_stage(4, "执行签到")

        def _do_sign(reauth: bool = True) -> Tuple[str, str]:
            try:
                return client.sign_in()
            except RuntimeError as exc:
                if "未授权" in str(exc) and reauth and account.has_login():
                    log(f"  {ICON_WARN} 签到未授权，尝试重新登录")
                    nick = client.login(forced=True)
                    if nick:
                        result["identity"] = nick
                    return client.sign_in()
                raise

        code, msg = _do_sign()
        stage4_ms = int((_now() - stage4_start).total_seconds() * 1000)

        info_after = None
        try:
            info_after = _fetch_info(reauth=False)
        except Exception:
            info_after = None
        bal_after = _balance_of(info_after)
        delta_txt = ""
        if bal is not None and bal_after is not None:
            delta = bal_after - bal
            delta_txt = f"；签到前电量 {bal:g}，签到后 {bal_after:g}，变化 {delta:g}"
            if code == "OK" and delta <= 0:
                log(f"  {ICON_WARN} 签到后电量未增加，可能今日已签过")

        if code == "ALREADY":
            stats["alreadyComplete"] += 1
            show = f"{msg}{delta_txt}" if delta_txt else msg
            log(f"  {ICON_DONE} {show}（耗时 {stage4_ms}ms）")
            result["ok"] = True
            result["status"] = "success"
            result["message"] = show
            result["resultCode"] = "ALREADY"
            machine = {
                "result": "ALREADY",
                "report": show,
                "account": index,
                "identity": result["identity"],
                "balance": bal_after if bal_after is not None else bal,
            }
        else:
            stats["success"] += 1
            show = f"签到成功{delta_txt}" if delta_txt else "签到成功"
            log(f"  {ICON_OK} {show}（耗时 {stage4_ms}ms）")
            result["ok"] = True
            result["status"] = "success"
            result["message"] = show
            result["resultCode"] = "SIGNED"
            machine = {
                "result": "SIGNED",
                "report": show,
                "account": index,
                "identity": result["identity"],
                "balance": bal_after if bal_after is not None else bal,
            }
    except Exception as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = _safe_message(exc, 200)
        result["resultCode"] = "ERROR"
        machine = {
            "result": "ERROR",
            "report": result["message"],
            "account": index,
            "identity": result["identity"],
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
        base_url = _base_url()
        log(f"目标站点: {base_url}")
        raw, source_name = _read_credential_raw()
        if not raw:
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{ICON_FAIL} 未配置必填环境变量 {ACCOUNT_ENV}")
            log(
                "获取方式: 打开魅魔 AI / Meimoai 网站注册并登录后，"
                f"可在浏览器开发者工具复制站点 Cookie，按 cookie:完整Cookie 写入 {ACCOUNT_ENV}；"
                "或使用 邮箱#密码。每行一个账号。"
            )
            log("账号数量: 0")
            emit_machine(
                {
                    "result": "NO_AUTH",
                    "report": f"未配置必填环境变量 {ACCOUNT_ENV}",
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
                for idx, account in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, account, base_url)
                    else:
                        ar = run_account_live(
                            idx, total, account, base_url, timeout=timeout
                        )
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
