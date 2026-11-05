#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 百度知道签到
# cron: 30 10 * * *
# SPDX-License-Identifier: MIT
# Copyright (c) 2017 YingJieGUP
# Derived from gyje/BD_zhidao_qiandao main.py
# commit 3cb56d598f029deb2905b287a516050854b95e51 (MIT).
# Source SHA256: b04a2cee447d709028d91b3f77344609df629ebbb91fbf5f337dc3b50e8e69d9
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""百度知道每日签到（青龙维护版）。

参数获取：登录本人百度知道（zhidao.baidu.com），从浏览器开发者工具本站请求
复制完整 Cookie 请求头值（不含 Cookie: 前缀），写入青龙环境变量 BD_ZHIDAO_COOKIE。
每个非空行一个账号；不以 &、@ 或其他符号分隔账号。
上游计划每日 10:30；青龙订阅使用 cron 30 10 * * *。
BD_ZHIDAO_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
仅标准库实现 HTTP；不依赖 schedule 常驻循环、私有仓库或外部可执行文件。
无发帖、评论、分享或额外奖励任务。
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
            "51f65d9bd2e5a68f",
            "scripts/bd_zhidao_qiandao.py",
            "bd_zhidao_qiandao.py",
            "bd_zhidao_qiandao",
            "output/candidate.py",
            "candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

TITLE = "百度知道签到"
CATALOG_ID = "51f65d9bd2e5a68f"
SIGN_URL = "https://zhidao.baidu.com/msubmit/signin"
SIGNINFO_REFERER = "https://zhidao.baidu.com/mmisc/signinfo"
HOST = "zhidao.baidu.com"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) "
    "AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1"
)
MAX_RESPONSE_BYTES = 262144
HTTP_TIMEOUT = 20
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
NOTIFY_IDENTITIES = (
    CATALOG_ID,
    "scripts/bd_zhidao_qiandao.py",
    "bd_zhidao_qiandao.py",
    "bd_zhidao_qiandao",
    "output/candidate.py",
    "candidate.py",
)
TZ_BJ = timezone(timedelta(hours=8))


class ConfigError(ValueError):
    """可安全展示的配置错误。"""


class ApiError(RuntimeError):
    """已脱敏的传输或响应错误。"""


class SameHostHttpsRedirect(urllib.request.HTTPRedirectHandler):
    """禁止携带 Cookie 跟随到非 HTTPS 或异站地址。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != HOST:
            raise ApiError("拒绝把账号凭据重定向到非目标 HTTPS 主机")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameHostHttpsRedirect())


def now_bj() -> datetime:
    return datetime.now(TZ_BJ)


def clock() -> str:
    return now_bj().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock()}] {message}", flush=True)


def enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def notification_enabled() -> bool:
    mode = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if mode in FALSE_VALUES:
        return False
    if mode in TRUE_VALUES:
        return True
    if mode not in {"", "auto"}:
        log("⚠️ QINGLONG_NOTIFY 值无效，为避免意外外发通知，本次不发送")
        return False
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    selectors = [item.lower() for item in re.split(r"[,;\s]+", selection.strip()) if item]
    return any(
        selector == "*"
        or any(fnmatch.fnmatch(identity.lower(), selector) for identity in NOTIFY_IDENTITIES)
        for selector in selectors
    )


def parse_accounts(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def validate_cookie(cookie: str, index: int) -> None:
    if "=" not in cookie:
        raise ConfigError(f"账号{index} Cookie 格式无效：缺少键值对")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie):
        raise ConfigError(f"账号{index} Cookie 含非法控制字符")
    try:
        cookie.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ConfigError(f"账号{index} Cookie 编码无效") from exc
    lowered = cookie.lower()
    if "复制cookie" in cookie or lowered in {"cookie", "your_cookie", "bduss"}:
        raise ConfigError(f"账号{index} 仍是占位凭据，请填入本人 Cookie")


def secret_fragments(cookie: str) -> list[str]:
    parts = [cookie]
    for item in cookie.split(";"):
        item = item.strip()
        if "=" in item:
            value = item.split("=", 1)[1].strip()
            if value:
                parts.append(value)
    return [part for part in parts if part]


def redact(text: object, secrets: list[str], limit: int = 180) -> str:
    value = str(text or "")
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[凭据已隐藏]")
    value = re.sub(r"(?i)(bduss|stoken|baiduid|cookie|token)=([^;\s&]+)", r"\1=[凭据已隐藏]", value)
    value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def extract_identity(payload: dict[str, Any], secrets: list[str]) -> Optional[str]:
    sources: list[Any] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        sources.append(data)
    elif isinstance(data, list):
        sources.extend(item for item in data if isinstance(item, dict))
    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in (
            "nickname",
            "nickName",
            "uname",
            "username",
            "userName",
            "displayName",
            "display_name",
            "name",
            "uid",
            "uk",
        ):
            value = source.get(field)
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (str, int)):
                text = str(value).strip()
                if not text:
                    continue
                if any(secret and secret in text for secret in secrets):
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if re.fullmatch(r"[0-9a-fA-F]{32,}", text):
                    continue
                return text.replace("\r", " ").replace("\n", " ")
    return None


def sign_url() -> str:
    return f"{SIGN_URL}?random={random.random()}"


def post_signin(cookie: str) -> dict[str, Any]:
    body = urllib.parse.urlencode({"ssid": "", "cifr": ""}).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie,
        "Host": HOST,
        "Origin": "https://zhidao.baidu.com",
        "Referer": SIGNINFO_REFERER,
        "User-Agent": USER_AGENT,
        "X-ik-ssl": "1",
        "X-Requested-With": "XMLHttpRequest",
    }
    request = urllib.request.Request(sign_url(), data=body, headers=headers, method="POST")
    try:
        with OPENER.open(request, timeout=HTTP_TIMEOUT) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ApiError(f"HTTP 状态异常（{exc.code}）") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ApiError("网络请求失败或超时") from None
    if status < 200 or status >= 300:
        raise ApiError(f"HTTP 状态异常（{status}）")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ApiError("响应超过安全大小限制")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ApiError("响应不是有效 JSON") from None
    if not isinstance(payload, dict):
        raise ApiError("响应结构无效")
    return payload


def evaluate_signin(payload: dict[str, Any], secrets: list[str]) -> tuple[bool, str, str, Optional[str]]:
    """返回 (ok, status, message, identity)。仅在明确业务成功时 ok=True。"""
    identity = extract_identity(payload, secrets)
    errno = payload.get("errno")
    if errno is None:
        errno = payload.get("errNo")
    if errno is None:
        errno = payload.get("err_no")
    errmsg = payload.get("errmsg")
    if errmsg is None:
        errmsg = payload.get("errMsg")
    if errmsg is None:
        errmsg = payload.get("msg")
    errmsg_text = redact(errmsg, secrets) if errmsg is not None else ""

    already_markers = ("已签到", "已经签到", "今日已签", "重复签到", "signed")
    success_markers = ("成功", "success", "ok", "签到成功")
    auth_markers = ("登录", "登陆", "未登录", "cookie", "过期", "失效", "非法")

    already = any(marker.lower() in errmsg_text.lower() for marker in already_markers)
    auth_failed = any(marker.lower() in errmsg_text.lower() for marker in auth_markers)

    if errno in (0, "0") or errno is True:
        if already:
            return True, "already", "今日已签到", identity
        if not errmsg_text or any(marker.lower() in errmsg_text.lower() for marker in success_markers):
            return True, "success", "签到成功（errno=0）", identity
        if auth_failed:
            return False, "failure", "凭据失效或未登录", identity
        # errno=0 但文案未知：仍视为业务成功（百度常见约定）
        return True, "success", "签到成功（errno=0）", identity

    if already:
        return True, "already", "今日已签到", identity
    if auth_failed:
        return False, "failure", "凭据失效或未登录", identity
    if errno is None:
        return False, "failure", "缺少明确业务成功字段（errno）", identity
    return False, "failure", f"签到未确认成功（errno={redact(errno, secrets, 40)}）", identity


def notify_summary(body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("阶段 3 通知：⏭️ 已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry_run:
        log("阶段 3 通知：⏭️ 断网预演，已生成脱敏摘要，未加载通知组件")
        print(body, flush=True)
        return "dry-run"
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(TITLE, body)
            log("阶段 3 通知：✅ 已通过 notify.py 推送")
            return "sent"
    except Exception:
        pass
    paths: list[Path] = []
    configured = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if configured:
        paths.append(Path(configured) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify_bd_zhidao", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if not callable(sender):
                continue
            sender(TITLE, body)
            log("阶段 3 通知：✅ 已通过 notify.py 推送")
            return "sent"
        except Exception:
            continue
    log("阶段 3 通知：⚠️ 通知助手不可用或发送失败，保留业务退出码")
    return "unavailable"


def run_account(index: int, cookie: str, dry_run: bool) -> dict[str, Any]:
    started = time.monotonic()
    secrets = secret_fragments(cookie)
    log(f"账号 {index} 阶段 1：凭据已读取（隐藏）")
    try:
        validate_cookie(cookie, index)
    except ConfigError as exc:
        elapsed = round(time.monotonic() - started, 3)
        log(f"账号 {index} 阶段 1：❌ {exc}")
        counts = {"success": 0, "already": 0, "skipped": 0, "failure": 1}
        log(
            f"账号 {index} 统计：总任务 1；成功 0；已完成 0；跳过 0；失败 1；耗时 {elapsed:.2f}s"
        )
        return {
            "account": index,
            "ok": False,
            "status": "failure",
            "message": str(exc),
            "identity": None,
            "tasks": counts,
            "elapsedSeconds": elapsed,
        }

    if dry_run:
        elapsed = round(time.monotonic() - started, 3)
        message = "DRY_RUN_OK：配置预演通过，未发起网络请求、未执行签到"
        log(f"账号 {index} 阶段 2：⏭️ {message}；耗时 {elapsed:.2f}s")
        counts = {"success": 0, "already": 0, "skipped": 1, "failure": 0}
        log(
            f"账号 {index} 统计：总任务 1；成功 0；已完成 0；跳过 1；失败 0；耗时 {elapsed:.2f}s"
        )
        return {
            "account": index,
            "ok": True,
            "status": "skipped",
            "message": message,
            "identity": None,
            "tasks": counts,
            "elapsedSeconds": elapsed,
        }

    request_started = time.monotonic()
    try:
        payload = post_signin(cookie)
        ok, status, message, identity = evaluate_signin(payload, secrets)
    except ApiError as exc:
        ok, status, message, identity = False, "failure", str(exc), None
    request_elapsed = time.monotonic() - request_started
    icon = "✅" if ok and status == "success" else "☑️" if ok and status == "already" else "❌"
    log(f"账号 {index} 阶段 2：{icon} {message}；耗时 {request_elapsed:.2f}s")
    if identity:
        log(f"账号 {index} 身份：{identity}")
    counts = {
        "success": int(status == "success"),
        "already": int(status == "already"),
        "skipped": 0,
        "failure": int(not ok),
    }
    elapsed = round(time.monotonic() - started, 3)
    log(
        f"账号 {index} 统计：总任务 1；成功 {counts['success']}；已完成 {counts['already']}；"
        f"跳过 {counts['skipped']}；失败 {counts['failure']}；耗时 {elapsed:.2f}s"
    )
    return {
        "account": index,
        "ok": ok,
        "status": status,
        "message": message,
        "identity": identity,
        "tasks": counts,
        "elapsedSeconds": elapsed,
    }


def main() -> int:
    started = time.monotonic()
    dry_run = enabled("BD_ZHIDAO_DRY_RUN")
    accounts = parse_accounts(os.getenv("BD_ZHIDAO_COOKIE", ""))
    print(f"══════════ {TITLE} ══════════", flush=True)
    log(
        f"阶段 0 任务横幅：开始时间 {now_bj():%Y-%m-%d %H:%M:%S %z}；"
        f"模式 {'断网预演' if dry_run else '正式运行'}；账号数 {len(accounts)}"
    )
    results: list[dict[str, Any]] = []
    if not accounts:
        log("阶段 1 配置：❌ 未配置必填 BD_ZHIDAO_COOKIE；每个非空行一个账号 Cookie")
    for index, cookie in enumerate(accounts, 1):
        results.append(run_account(index, cookie, dry_run))

    passed = sum(1 for item in results if item["ok"])
    failed = len(results) - passed
    exit_code = 0 if accounts and failed == 0 else 1
    if not accounts:
        status = "configuration-error"
    elif failed == 0 and dry_run:
        status = "dry-run"
    elif failed == 0:
        status = "success"
    elif passed:
        status = "partial-failure"
    else:
        status = "failure"
    totals = {
        key: sum(item["tasks"][key] for item in results)
        for key in ("success", "already", "skipped", "failure")
    }
    body = (
        f"状态：{status}；账号总数：{len(accounts)}；成功数：{passed}；失败数：{failed}。"
        f"子任务：成功 {totals['success']}，已完成 {totals['already']}，"
        f"跳过 {totals['skipped']}，失败 {totals['failure']}。"
    )
    if not accounts:
        body += " 配置错误：缺少 BD_ZHIDAO_COOKIE。"
    if dry_run:
        body += " 断网预演，未进行真实签到。"
    notification = notify_summary(body, dry_run)
    print("────────────────────────────────", flush=True)
    log(f"最终统计：{body}；总耗时 {time.monotonic() - started:.2f}s")
    log(
        f"任务结束：完成时间 {now_bj():%Y-%m-%d %H:%M:%S %z}；"
        f"通知状态 {notification}；最终状态 {status}；退出码 {exit_code}"
    )
    summary = {
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "mode": "dry-run" if dry_run else "live",
        "status": status,
        "accounts": len(accounts),
        "success": passed,
        "failure": failed,
        "tasks": totals,
        "results": [
            {
                "account": item["account"],
                "ok": item["ok"],
                "status": item["status"],
                "identity": item["identity"],
                "tasks": item["tasks"],
                "elapsedSeconds": item["elapsedSeconds"],
            }
            for item in results
        ],
        "notification": notification,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "exitCode": exit_code,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
