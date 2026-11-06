#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 好豆每日签到
# cron: 14 9 * * *
#
# 来源：264768502/qiandao haodou.py
# https://github.com/264768502/qiandao
# 分支：master
# 提交：5d305a18fc0106b9ad047d271c3039ce66b9f87c
# 原路径：haodou.py
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 264768502 / qiandao contributors
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
"""好豆网（haodou.com）账号登录与每日签到（青龙维护版）。

功能清点（相对上游 haodou.py）：
- RSA 加密密码登录 login.haodou.com，完成 qunachi.com SSO 回调
- 调用 wo.haodou.com/user/sign.php 执行每日签到（业务 status=true）
- 读取 shop.haodou.com/my.php 积分展示（只读）
- 移除硬编码示例凭据、打印账号凭据、无超时请求与原始响应泄漏
- 多账号：HAODOU_ACCOUNT 每行「账号|密码」（仅拆首个 |；账号之间只用换行）
- HAODOU_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 标准库实现 HTTP（不再依赖 requests/rsa 包或仓库路径）

建议 Cron：25 8 * * *。不打印密码、Cookie、Token 或原始响应。
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
        _ql_notify_identities = ('bafb80cab6b6c282', 'scripts/haodou.py', 'haodou.py', 'haodou')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import binascii
import json
import os
import random
import re
import secrets as pysecrets
import sys
import time
import traceback
from datetime import datetime
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

SCRIPT_NAME = "好豆每日签到"
CATALOG_ID = "bafb80cab6b6c282"
SCRIPT_FILENAME = "candidate.py"
DOMAIN = "haodou.com"
MAIN_URL = f"http://www.{DOMAIN}/"
LOGIN_URL = f"http://login.{DOMAIN}/"
LOGIN_POST_URL = LOGIN_URL + "index.php?do=check"
LOGIN_CALLBACK_URL = "http://www.qunachi.com/user/login.php?do=ssoLoginCallBack"
SIGN_URL = f"http://wo.{DOMAIN}/user/sign.php"
POINT_URL = f"http://shop.{DOMAIN}/my.php"
UA = (
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/54.0.2840.99 Safari/537.36"
)
HTTP_TIMEOUT = 20
DRY_RUN_ENV = "HAODOU_DRY_RUN"
CRED_ENV = "HAODOU_ACCOUNT"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# 上游内嵌登录公钥（公开材料，非凭据）
_RSA_N_B64 = (
    b"yevTQ5C8exDUo/c0y0Lrxp+quYD9vxjkKFAgdqV0PtLefJ4FEB4VeTTGDfqaWVgQXeQeyCp0y"
    b"jCd8EGVUd/77z+Z/HlBpaavHwsE77Rjf3r9AC+aSN+ZZC4uoZL0bYDiDgYcG32CPLdVPP8zb"
    b"Kxa/BSbUb1PhxEot/fMTo+rLrU="
)
_RSA_E_B64 = b"AQAB"
HAODOU_RSA_N = int(binascii.b2a_hex(base64.b64decode(_RSA_N_B64)), 16)
HAODOU_RSA_E = int(binascii.b2a_hex(base64.b64decode(_RSA_E_B64)), 16)

TIMESTAMP_RE = re.compile(
    r'<input id="timestamp" name="timestamp" type="hidden" value="(\d+)" />'
)
SSO_TOKEN_RE = re.compile(
    r'<input type="hidden" id="sso_token" name="token" value="(.*?)" />'
)
CALLBACK_RE = re.compile(r'<iframe src="(.*?)">')
POINT_RE = re.compile(r'<span class="orange f24 fg">(\d+)</span>')

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
    raw = os.getenv("HAODOU_TIMEOUT", "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("HAODOU_TIMEOUT 须为整数秒") from exc
    if value < 5 or value > 90:
        raise SafeError("HAODOU_TIMEOUT 须在 5 到 90 秒之间")
    return value


def rsa_encrypt_password(timestamp: str, password: str) -> str:
    """PKCS#1 v1.5 加密，等价于上游 rsa.encrypt(timestamp|password) + base64。"""
    message = f"{timestamp}|{password}".encode("utf-8")
    k = (HAODOU_RSA_N.bit_length() + 7) // 8
    if len(message) > k - 11:
        raise SafeError("密码过长，无法按好豆 RSA 规则加密")
    ps_len = k - len(message) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        block = pysecrets.token_bytes(ps_len - len(ps) + 16)
        ps.extend(b for b in block if b != 0)
    em = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + message
    cipher_int = pow(int.from_bytes(em, "big"), HAODOU_RSA_E, HAODOU_RSA_N)
    return base64.b64encode(cipher_int.to_bytes(k, "big")).decode("ascii")


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    """每行一个账号；仅按第一个 | 分割账号与密码。账号之间只用换行。"""
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            raise ValueError(
                f"第 {line_no} 行账号格式无效：缺少账号与密码分隔符 |"
            )
        account, password = text.split("|", 1)
        account = account.strip()
        password = password.strip()
        if not account or not password:
            raise ValueError(f"第 {line_no} 行账号格式无效：账号或密码为空")
        if any(ord(ch) < 32 for ch in password):
            raise ValueError(f"第 {line_no} 行密码含非法控制字符")
        accounts.append({"account": account, "password": password})
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
        "scripts/haodou_checkin.py",
        "haodou_checkin.py",
        "haodou.py",
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


class HaodouClient:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.login_timestamp = str(int(time.time() * 1000))

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        if params:
            query = urlencode(params)
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"
        body = None
        req_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.8",
            "Connection": "close",
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
        }
        if headers:
            req_headers.update(headers)
        if data is not None:
            if isinstance(data, (list, tuple)):
                body = urlencode(data).encode("utf-8")
            elif isinstance(data, dict):
                body = urlencode(data).encode("utf-8")
            else:
                body = str(data).encode("utf-8")
            req_headers.setdefault(
                "Content-Type",
                "application/x-www-form-urlencoded; charset=UTF-8",
            )
        req = Request(url, data=body, headers=req_headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("响应过大，已中止读取")
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"网络错误: {type(exc.reason).__name__}") from exc
        except TimeoutError as exc:
            raise RuntimeError("请求超时") from exc
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"请求失败: {type(exc).__name__}") from exc


def login_and_sign(account: str, password: str, timeout: int) -> Dict[str, Any]:
    """登录好豆并执行每日签到；成功条件沿用上游 status=true。"""
    client = HaodouClient(timeout=timeout)
    login_html = client.request(LOGIN_URL)
    ts_m = TIMESTAMP_RE.search(login_html)
    token_m = SSO_TOKEN_RE.search(login_html)
    if not ts_m or not token_m:
        raise RuntimeError("登录页缺少 timestamp 或 sso_token")
    page_timestamp = ts_m.group(1)
    sso_token = token_m.group(1)
    enc_password = rsa_encrypt_password(page_timestamp, password)
    post_data = {
        "account": account,
        "type": "1",
        "password": enc_password,
        "referer": MAIN_URL,
        "auto_login": "1",
        "valicode": "",
        "sso_token": sso_token,
    }
    login_resp = client.request(LOGIN_POST_URL, method="POST", data=post_data)
    try:
        login_d = json.loads(login_resp)
    except Exception as exc:
        raise RuntimeError("登录接口返回无法解析") from exc
    if not isinstance(login_d, dict) or "sso_ticket" not in login_d:
        raise RuntimeError("登录失败：未返回 sso_ticket")

    p_data = [
        ("referer", MAIN_URL),
        ("sso_ticket", login_d["sso_ticket"]),
        ("auto_login", "1"),
        ("__callback", "HDAjax" + str(int(time.time() * 1000))),
        ("__domain", LOGIN_URL.replace("http://", "").replace("/", "")),
    ]
    nheader = {
        "Host": "www.qunachi.com",
        "Referer": LOGIN_URL,
        "Upgrade-Insecure-Requests": "1",
    }
    callback_html = client.request(
        LOGIN_CALLBACK_URL, method="POST", data=p_data, headers=nheader
    )
    cb_m = CALLBACK_RE.search(callback_html)
    if not cb_m:
        raise RuntimeError("SSO 回调页缺少 iframe")
    callback_url = cb_m.group(1)
    parsed = urlparse(callback_url)
    params_dict = {key: value for key, value in parse_qsl(parsed.query)}
    if "data" not in params_dict:
        raise RuntimeError("SSO 回调缺少 data 参数")
    try:
        data = json.loads(params_dict["data"])
    except Exception as exc:
        raise RuntimeError("SSO 回调 data 无法解析") from exc
    if not isinstance(data, dict) or not data.get("status"):
        raise RuntimeError("登录回调失败：status 未通过")
    user_id = str(data.get("user_id") or "").strip()
    if not user_id:
        raise RuntimeError("登录回调未返回 user_id")

    home = client.request(callback_url)
    if not home:
        raise RuntimeError("打开首页失败")
    client.login_timestamp = str(int(time.time() * 1000))

    point_before = _read_point(client)

    nheader = {
        "Host": f"wo.{DOMAIN}",
        "Referer": POINT_URL,
    }
    callback = (
        "jQuery183"
        + "{:17.16f}".format(random.random()).replace(".", "")
        + "_"
        + client.login_timestamp
    )
    payload = [
        ("do", "Sign"),
        ("callback", callback),
        ("_", str(int(time.time() * 1000))),
    ]
    sign_text = client.request(SIGN_URL, params=payload, headers=nheader)
    signed_ok = '"status":true' in sign_text or '"status": true' in sign_text
    already = False
    if not signed_ok:
        already = any(
            token in sign_text
            for token in ("已签到", "已经签到", "重复签到", "今日已签")
        )
        if not already:
            raise RuntimeError("签到失败：响应未包含 status=true")

    point_after = _read_point(client)
    return {
        "identity": f"UID:{user_id}",
        "user_id": user_id,
        "already_signed": already,
        "sign_message": "今日已签到" if already else "签到成功",
        "point_before": point_before,
        "point_after": point_after,
    }


def _read_point(client: HaodouClient) -> str:
    try:
        html = client.request(POINT_URL)
    except Exception:
        return ""
    m = POINT_RE.search(html)
    return m.group(1) if m else ""


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

    log_stage(1, "校验账号格式", "账号与密码均已提供")
    if not account.get("account") or not account.get("password"):
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
        log(f"  {ICON_SKIP} 断网预演：将登录 login.{DOMAIN} 并完成 SSO 回调")

        log_stage(3, "预演签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将请求 wo.{DOMAIN}/user/sign.php")

        log_stage(4, "预演积分读取", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将读取 shop.{DOMAIN}/my.php 积分")

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
        if not account.get("account") or not account.get("password"):
            raise RuntimeError("账号凭据不完整")
        stats["success"] += 1
        log(f"  {ICON_OK} 参数就绪（不输出凭据）")

        stage2_start = _now()
        log_stage(2, "登录好豆")
        outcome = login_and_sign(
            account["account"], account["password"], timeout=timeout
        )
        identity = outcome.get("identity") or label
        result["identity"] = identity
        stage2_ms = int((_now() - stage2_start).total_seconds() * 1000)
        log(f"  {ICON_OK} 登录成功，身份: {identity}（耗时 {stage2_ms}ms）")
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

        log_stage(4, "积分摘要")
        before = outcome.get("point_before") or ""
        after = outcome.get("point_after") or ""
        if after or before:
            stats["success"] += 1
            if before and after and before != after:
                log(f"  {ICON_OK} 积分: {before} → {after}")
                result["message"] = f"{result['message']}；积分 {before}→{after}"
            elif after:
                log(f"  {ICON_OK} 当前积分: {after}")
                result["message"] = f"{result['message']}；积分 {after}"
            else:
                log(f"  {ICON_OK} 签到前积分: {before}")
                result["message"] = f"{result['message']}；积分 {before}"
        else:
            stats["skipped"] += 1
            log(f"  {ICON_SKIP} 未解析到积分（不影响签到成功判定）")

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
                f"获取方式: 在青龙环境变量中新增 {CRED_ENV}，"
                "每行一个账号，格式 账号|密码"
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
