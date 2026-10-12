#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ikuuu 签到
# cron: 0 21 * * *
# SPDX-License-Identifier: MIT
"""Standalone Qinglong check-in task for ikuuu.

Adapted from ``ikuuu_checkin.py`` in agluo/ql-script-hub and the original
project at https://github.com/bighammer-link/jichang_dailycheckin .
The upstream attribution and MIT license are preserved.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = "https://ikuuu.nl"
LOGIN_URL = f"{BASE_URL}/auth/login"
CHECKIN_URL = f"{BASE_URL}/user/checkin"
TIMEOUT_SECONDS = 15
TITLE = "ikuuu签到"
DRY_RUN_ENV = "IKUUU_DRY_RUN"
DISABLED = {"0", "false", "no", "off"}
ALREADY_WORDS = ("已经签到", "已签到", "already checked", "already check")
HEADERS = {
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/user",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Qinglong ikuuu maintained task)",
}


class TaskError(Exception):
    """A safe, user-facing task error that contains no credentials."""


def enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() not in DISABLED


def parse_accounts(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        raise TaskError(f"缺少环境变量 {name}")
    lines = raw.splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise TaskError(f"{name} 必须每行填写一个非空值，不能有空行")
    return [line.strip() for line in lines]


def parse_account_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, value in enumerate(parse_accounts("IKUUU_ACCOUNT"), 1):
        if "|" not in value:
            raise TaskError(f"IKUUU_ACCOUNT 第 {index} 行必须是邮箱|密码")
        email, password = (part.strip() for part in value.split("|", 1))
        if not email or not password:
            raise TaskError(f"IKUUU_ACCOUNT 第 {index} 行的邮箱或密码为空")
        pairs.append((email, password))
    return pairs


def masked_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.rsplit("@", 1)
    shown = local[:1] + "***" + (local[-1:] if len(local) > 1 else "")
    return f"{shown}@{domain}"


def safe_message(value: Any, fallback: str) -> str:
    """Return a short single-line business message, never a raw response."""
    if not isinstance(value, str):
        return fallback
    value = re.sub(r"\s+", " ", value).strip()
    return value[:160] or fallback


def redact_message(value: str, email: str, password: str) -> str:
    value = value.replace(email, masked_email(email))
    if password:
        value = value.replace(password, "***")
    return value


def reward_from(message: str) -> str | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?B)", message, re.I)
    return f"{match.group(1)}{match.group(2).upper()}" if match else None


@dataclass
class AccountResult:
    index: int
    account: str
    success: bool
    status: str
    detail: str


class IkuuuClient:
    def __init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor())

    def post_json(self, url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        body = urlencode(data).encode("utf-8") if data is not None else b""
        request = Request(url, data=body, headers=HEADERS, method="POST")
        try:
            with self.opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise TaskError(f"服务返回 HTTP {response.status}")
                payload = response.read(65537)
        except HTTPError as exc:
            raise TaskError(f"服务返回 HTTP {exc.code}") from None
        except (URLError, TimeoutError):
            raise TaskError("网络连接失败或请求超时") from None
        if len(payload) > 65536:
            raise TaskError("服务响应过大")
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TaskError("服务响应不是有效 JSON") from None
        if not isinstance(value, dict):
            raise TaskError("服务响应结构无效")
        return value

    def run(self, email: str, password: str) -> tuple[str, str]:
        login = self.post_json(LOGIN_URL, {"email": email, "passwd": password})
        if login.get("ret") != 1:
            # Login error text is deliberately not surfaced because a service may
            # echo submitted credentials in an otherwise legitimate JSON message.
            raise TaskError("登录失败：凭据或服务状态异常")

        checkin = self.post_json(CHECKIN_URL)
        message = redact_message(
            safe_message(checkin.get("msg"), "未返回业务说明"), email, password
        )
        lowered = message.lower()
        if checkin.get("ret") == 1:
            reward = reward_from(message)
            return "checked-in", f"签到成功" + (f"，获得流量 {reward}" if reward else "")
        if any(word in lowered for word in ALREADY_WORDS):
            return "already-checked-in", "今日已签到"
        raise TaskError("签到失败：" + message)


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except (ImportError, AttributeError):
        pass
    candidates: list[Path] = []
    custom_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, "send", None)
                if callable(sender):
                    return sender
        except Exception:
            continue
    return None


def notify_summary(body: str, dry_run: bool) -> None:
    if not enabled("QINGLONG_NOTIFY", "1"):
        print("通知已由 QINGLONG_NOTIFY 关闭")
        return
    # A dry-run is strictly no-network; importing notify.py could itself perform I/O.
    if dry_run:
        print("DRY-RUN 通知摘要（未投递以保证完全断网）：" + body)
        return
    sender = load_notify_sender()
    if sender is None:
        print("警告：未找到青龙通知模块，业务退出状态保持不变", file=sys.stderr)
        return
    try:
        sender(TITLE, body)
        print("通知投递完成")
    except Exception:
        print("警告：通知投递失败，业务退出状态保持不变", file=sys.stderr)


def delay_seconds() -> int:
    raw = os.getenv("IKUUU_MAX_RANDOM_DELAY", "0").strip()
    try:
        value = int(raw)
    except ValueError:
        raise TaskError("IKUUU_MAX_RANDOM_DELAY 必须是非负整数秒") from None
    if value < 0 or value > 3600:
        raise TaskError("IKUUU_MAX_RANDOM_DELAY 必须在 0 到 3600 之间")
    return random.randint(0, value) if value else 0


def emit_summary(event: str, total: int, succeeded: int, failed: int) -> str:
    value = {"event": event, "total": total, "succeeded": succeeded, "failed": failed}
    line = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    print("IKUUU_SUMMARY=" + line)
    return f"状态：{event}；账号总数：{total}；成功：{succeeded}；失败：{failed}"


def main() -> int:
    dry_run = enabled(DRY_RUN_ENV)
    try:
        accounts = parse_account_pairs()
        maximum_delay = delay_seconds()
    except TaskError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        body = emit_summary("configuration-error", 0, 0, 0)
        notify_summary(body, dry_run)
        return 2

    if dry_run:
        print(f"DRY-RUN OK: validated {len(accounts)} account(s); no network requests or mutations performed")
        body = emit_summary("dry-run", len(accounts), len(accounts), 0)
        notify_summary(body, True)
        return 0

    if maximum_delay:
        print(f"任务随机等待 {maximum_delay} 秒")
        time.sleep(maximum_delay)

    results: list[AccountResult] = []
    for index, (email, password) in enumerate(accounts, 1):
        account = masked_email(email)
        try:
            status, detail = IkuuuClient().run(email, password)
            result = AccountResult(index, account, True, status, detail)
            print(f"账号{index} {account}: {detail}")
        except TaskError as exc:
            result = AccountResult(index, account, False, "failed", str(exc))
            print(f"账号{index} {account}: {exc}", file=sys.stderr)
        except Exception:
            result = AccountResult(index, account, False, "failed", "未预期的执行错误")
            print(f"账号{index} {account}: 未预期的执行错误", file=sys.stderr)
        results.append(result)

    succeeded = sum(item.success for item in results)
    failed = len(results) - succeeded
    event = "success" if not failed else ("partial-failure" if succeeded else "failure")
    body = emit_summary(event, len(results), succeeded, failed)
    notify_summary(body, False)
    return 0 if not failed else 1


def handler(event: Any = None, context: Any = None) -> int:
    """Compatibility entrypoint for runtimes that call a handler."""
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
