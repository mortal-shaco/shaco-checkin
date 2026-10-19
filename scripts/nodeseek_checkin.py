#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NodeSeek 论坛签到
# cron: 41 0 * * *
"""NodeSeek daily attendance and recent reward statistics.

Environment:
  NODESEEK_COOKIE   Required. One complete browser Cookie header per non-empty
                    line. In a logged-in browser, open Developer Tools ->
                    Network, refresh nodeseek.com, select a same-site request,
                    and copy the Request Headers value named ``cookie``.
  NODESEEK_DRY_RUN  Set to 1/true/yes/on to validate without network or changes.
  NS_RANDOM         Attendance API random-reward flag (default: true).
  RANDOM_SIGNIN     Set to true to stagger accounts (default: false).
  MAX_RANDOM_DELAY  Maximum stagger delay in seconds (default: 3600).
  NS_STATS_DAYS     Reward-history window, 1..365 days (default: 30).
  QINGLONG_NOTIFY   Set to 0/false/no/off to disable Qinglong notification.

Adapted from agluo/ql-script-hub nodeseek_checkin.py at commit
a8d39b97cb22c3ac657089014df754342b456ff6.
SPDX-License-Identifier: MIT
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('4196e654f2a752f8', 'scripts/nodeseek_checkin.py', 'nodeseek_checkin.py', 'nodeseek_checkin')
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
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TITLE = "NodeSeek 签到"
BASE_URL = "https://www.nodeseek.com"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 1024 * 1024
DISABLED = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 "
    "Safari/537.36 Edg/125.0.0.0"
)


class RequestFailure(Exception):
    """A redacted, safe-to-display HTTP or response error."""


def env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in TRUE_VALUES


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum}..{maximum} 之间")
    return value


def headers(cookie: str, content_type: bool = False) -> dict[str, str]:
    result = {
        "User-Agent": USER_AGENT,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/board",
        "Cookie": cookie,
        "Accept": "application/json",
    }
    if content_type:
        result["Content-Type"] = "application/json"
    return result


def request_json(
    url: str, *, method: str, request_headers: dict[str, str], data: bytes | None = None
) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.getcode()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise RequestFailure("响应过大")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RequestFailure(f"HTTP 状态码 {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RequestFailure("网络请求失败或超时") from exc
    if status < 200 or status >= 300:
        raise RequestFailure(f"HTTP 状态码 {status}")
    if len(body) > MAX_RESPONSE_BYTES:
        raise RequestFailure("响应过大")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestFailure("服务器返回了无效 JSON") from exc
    if not isinstance(value, dict):
        raise RequestFailure("服务器响应结构不正确")
    return value


def sign(cookie: str, random_mode: str) -> tuple[bool, str]:
    query = urllib.parse.urlencode({"random": random_mode})
    data = request_json(
        f"{BASE_URL}/api/attendance?{query}",
        method="POST",
        request_headers=headers(cookie, content_type=True),
        data=b"",
    )
    message = data.get("message")
    message = message if isinstance(message, str) else ""
    if data.get("success") is True or "鸡腿" in message:
        return True, "签到成功"
    if "已完成签到" in message or "已签到" in message:
        return True, "今日已签到"
    if data.get("status") == 404:
        return False, "凭据无效或签到接口不可用"
    return False, "服务器未确认签到成功"


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def reward_stats(cookie: str, days: int) -> dict[str, float | int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    amounts: list[float] = []
    for page in range(1, 11):
        data = request_json(
            f"{BASE_URL}/api/account/credit/page-{page}",
            method="GET",
            request_headers=headers(cookie),
        )
        records = data.get("data")
        if data.get("success") is not True:
            raise RequestFailure("收益统计未返回成功状态")
        if not records:
            break
        if not isinstance(records, list):
            raise RequestFailure("收益统计响应结构不正确")
        reached_cutoff = False
        for record in records:
            if not isinstance(record, (list, tuple)) or len(record) < 4:
                continue
            stamp = parse_time(record[3])
            if stamp is None:
                continue
            if stamp < cutoff:
                reached_cutoff = True
                continue
            description = record[2]
            if isinstance(description, str) and "签到收益" in description and "鸡腿" in description:
                amount = record[0]
                if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                    amounts.append(float(amount))
        if reached_cutoff:
            break
        if page < 10:
            time.sleep(0.2)
    total = sum(amounts)
    return {
        "days_count": len(amounts),
        "total_amount": round(total, 2),
        "average": round(total / len(amounts), 2) if amounts else 0,
    }


def notify_python(path: Path, title: str, body: str) -> bool:
    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sender = getattr(module, "send", None)
    if not callable(sender):
        return False
    sender(title, body)
    return True


def send_notification(body: str) -> None:
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        print("通知已禁用")
        return
    try:
        try:
            from notify import send as sender  # type: ignore

            sender(TITLE, body)
            print("通知已发送")
            return
        except ImportError:
            pass

        notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
        python_paths = []
        js_paths = []
        if notify_dir:
            python_paths.append(Path(notify_dir) / "notify.py")
            js_paths.append(Path(notify_dir) / "sendNotify.js")
        python_paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
        js_paths.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
        for path in python_paths:
            if path.is_file() and notify_python(path, TITLE, body):
                print("通知已发送")
                return
        for path in js_paths:
            if path.is_file():
                program = (
                    "const m=require(process.argv[1]);"
                    "const f=m.sendNotify||m.default||m;"
                    "Promise.resolve(f(process.argv[2],process.argv[3]))"
                    ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
                )
                completed = subprocess.run(
                    ["node", "-e", program, str(path), TITLE, body],
                    check=False,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if completed.returncode == 0:
                    print("通知已发送")
                    return
        print("未找到可用的青龙通知模块")
    except Exception:
        print("通知发送失败，不改变任务退出状态")


def summary(total: int, succeeded: int, failed: int, state: str) -> str:
    return f"状态: {state}\n账号总数: {total}\n成功: {succeeded}\n失败: {failed}"


def main() -> int:
    cookies = [
        line.strip()
        for line in os.getenv("NODESEEK_COOKIE", "").replace("\r\n", "\n").split("\n")
        if line.strip()
    ]
    dry_run = env_true("NODESEEK_DRY_RUN")
    if not cookies:
        print("配置错误: 请设置 NODESEEK_COOKIE，每个账号占一行")
        send_notification(summary(0, 0, 0, "配置错误"))
        return 2
    try:
        max_delay = bounded_int("MAX_RANDOM_DELAY", 3600, 0, 86400)
        stats_days = bounded_int("NS_STATS_DAYS", 30, 1, 365)
    except ValueError as exc:
        print(f"配置错误: {exc}")
        send_notification(summary(len(cookies), 0, len(cookies), "配置错误"))
        return 2

    if dry_run:
        print(f"DRY-RUN: 已验证 {len(cookies)} 个账号配置，未发起任务网络请求，未执行签到")
        send_notification(summary(len(cookies), len(cookies), 0, "DRY-RUN"))
        return 0

    random_mode = os.getenv("NS_RANDOM", "true").strip().lower()
    if random_mode not in TRUE_VALUES | DISABLED:
        print("配置错误: NS_RANDOM 必须是布尔值")
        send_notification(summary(len(cookies), 0, len(cookies), "配置错误"))
        return 2
    random_mode = "true" if random_mode in TRUE_VALUES else "false"
    stagger = env_true("RANDOM_SIGNIN", default=False)
    schedule = [(random.randint(0, max_delay) if stagger else 0, i, cookie)
                for i, cookie in enumerate(cookies, 1)]
    schedule.sort(key=lambda item: item[0])
    started = time.monotonic()
    succeeded = 0
    for delay, index, cookie in schedule:
        remaining = delay - int(time.monotonic() - started)
        if remaining > 0:
            print(f"账号{index}: 延迟 {remaining} 秒执行")
            time.sleep(remaining)
        try:
            ok, message = sign(cookie, random_mode)
            if ok:
                succeeded += 1
                print(f"账号{index}: {message}")
                try:
                    stats = reward_stats(cookie, stats_days)
                    print(
                        f"账号{index}: 近{stats_days}天签到{stats['days_count']}天，"
                        f"共{stats['total_amount']}个鸡腿，日均{stats['average']}个"
                    )
                except RequestFailure as exc:
                    print(f"账号{index}: 收益统计不可用（{exc}）")
            else:
                print(f"账号{index}: 签到失败（{message}）")
        except RequestFailure as exc:
            print(f"账号{index}: 签到失败（{exc}）")
        except Exception:
            print(f"账号{index}: 签到失败（未预期错误）")

    failed = len(cookies) - succeeded
    state = "成功" if failed == 0 else ("部分失败" if succeeded else "失败")
    result = summary(len(cookies), succeeded, failed, state)
    print(result.replace("\n", " | "))
    send_notification(result)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
