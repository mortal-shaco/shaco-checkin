#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NodeSeek 论坛签到
# cron: 41 0 * * *
"""NodeSeek 每日签到与近 N 天鸡腿收益统计（独立维护版）。

环境变量：
  NODESEEK_COOKIE   必填。每个非空行一个账号的完整浏览器 Cookie 请求头值。
                    登录 https://www.nodeseek.com 后打开开发者工具 → Network，
                    刷新页面，选择同站请求，复制 Request Headers 中的 cookie 值
                    （不含 Cookie: 前缀）。Cookie 内的 &、@、; 不会用于分割账号。
  NODESEEK_DRY_RUN  设为 1/true/yes/on 时完全断网预演，只校验配置不发起业务请求。
  NS_RANDOM         签到接口随机奖励开关，默认 true。
  RANDOM_SIGNIN     多账号错峰开关，默认 false（不默认长等待）。
  MAX_RANDOM_DELAY  错峰最大秒数，默认 3600，范围 0..86400。
  NS_STATS_DAYS     收益统计窗口天数，默认 30，范围 1..365。
  QINGLONG_NOTIFY   青龙通知开关；未设置时按 QINGLONG_NOTIFY_SCRIPTS 名单策略。
  QINGLONG_NOTIFY_DIR  可选，notify.py / sendNotify.js 所在目录。

来源与许可：
  - agluo/ql-script-hub nodeseek_checkin.py @ a8d39b97cb22c3ac657089014df754342b456ff6
  - xinycai/nodeseek_signin nodeseek_signin.py @ fa01142b1868910c2e04b72b0474e76eefa4d81c
SPDX-License-Identifier: MIT
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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

import fnmatch
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CATALOG_ID = "4196e654f2a752f8"
TITLE = "NodeSeek 论坛签到"
BASE_URL = "https://www.nodeseek.com"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 1024 * 1024
DISABLED = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 "
    "Safari/537.36"
)
ICON = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class RequestFailure(Exception):
    """可安全展示的 HTTP / 响应错误。"""


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock()}] {message}", flush=True)


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


def load_cookies() -> list[str]:
    raw = os.getenv("NODESEEK_COOKIE", "").replace("\r\n", "\n")
    return [line.strip() for line in raw.split("\n") if line.strip()]


def headers(cookie: str, content_type: bool = False) -> dict[str, str]:
    result = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, */*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/board",
        "Cookie": cookie,
    }
    if content_type:
        result["Content-Type"] = "application/json"
        result["Content-Length"] = "0"
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


def extract_identity(data: dict[str, Any], cookie: str) -> str | None:
    containers: list[Any] = [data]
    for key in ("user", "data", "account"):
        nested = data.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
            user = nested.get("user")
            if isinstance(user, dict):
                containers.append(user)
    secrets = [cookie]
    for part in cookie.split(";"):
        if "=" in part:
            value = part.split("=", 1)[1].strip()
            if len(value) >= 4:
                secrets.append(value)
    phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    for container in containers:
        if not isinstance(container, dict):
            continue
        for field in ("nickname", "username", "displayName", "display_name", "uid", "id"):
            value = container.get(field)
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                continue
            text = str(value).replace("\r", " ").replace("\n", " ").strip()
            if not text or len(text) > 120:
                continue
            if any(ord(ch) < 32 for ch in text):
                continue
            if any(secret in text for secret in secrets):
                continue
            if phone.search(text):
                continue
            return text
    return None


def sign(cookie: str, random_mode: str) -> tuple[str, str, str | None]:
    """返回 (outcome, message, identity)；outcome 为 success / already / failure。"""
    query = urllib.parse.urlencode({"random": random_mode})
    data = request_json(
        f"{BASE_URL}/api/attendance?{query}",
        method="POST",
        request_headers=headers(cookie, content_type=True),
        data=b"",
    )
    who = extract_identity(data, cookie)
    message = data.get("message")
    message = message if isinstance(message, str) else ""
    if data.get("success") is True or "鸡腿" in message:
        detail = "签到成功"
        if "鸡腿" in message and len(message) <= 80 and not any(ord(c) < 32 for c in message):
            # 官方短消息常含鸡腿数量；仅在短且无控制字符时展示。
            detail = message.strip() or detail
        return "success", detail, who
    if "已完成签到" in message or "已签到" in message:
        return "already", "今日已签到", who
    if data.get("status") == 404:
        return "failure", "凭据无效或签到接口不可用", who
    return "failure", "服务器未确认签到成功", who


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
            if (
                isinstance(description, str)
                and "签到收益" in description
                and "鸡腿" in description
            ):
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


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {
        CATALOG_ID,
        "b1e960be4d85f4e6",
        Path(__file__).name,
        "candidate.py",
        "nodeseek_checkin.py",
        "scripts/nodeseek_checkin.py",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in DISABLED:
        return False
    if value in TRUE_VALUES:
        return notification_selected()
    if value not in {"", "auto"}:
        log(f"{ICON['warning']} QINGLONG_NOTIFY 值无效，按 auto 处理")
    return notification_selected()


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


def send_notification(body: str, *, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演仅生成脱敏摘要，不调用通知网络")
        return "dry-run"
    try:
        try:
            from notify import send as sender  # type: ignore

            sender(TITLE, body)
            log("通知状态：notify.send 已调用")
            return "sent"
        except ImportError:
            pass

        notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
        python_paths: list[Path] = []
        js_paths: list[Path] = []
        if notify_dir:
            python_paths.append(Path(notify_dir) / "notify.py")
            js_paths.append(Path(notify_dir) / "sendNotify.js")
        python_paths.extend(
            [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
        )
        js_paths.extend(
            [
                Path("/ql/data/scripts/sendNotify.js"),
                Path("/ql/scripts/sendNotify.js"),
            ]
        )
        for path in python_paths:
            if path.is_file() and notify_python(path, TITLE, body):
                log("通知状态：notify.py 已调用")
                return "sent"
        node = shutil.which("node")
        if node:
            program = (
                "const m=require(process.argv[1]);"
                "const f=m.sendNotify||m.default||m;"
                "Promise.resolve(f(process.argv[2],process.argv[3]))"
                ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
            )
            for path in js_paths:
                if not path.is_file():
                    continue
                completed = subprocess.run(
                    [node, "-e", program, str(path), TITLE, body],
                    check=False,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if completed.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
        log(f"{ICON['warning']} 通知状态：未找到可用通知器，不改变业务退出码")
        return "unavailable"
    except Exception:
        log(f"{ICON['warning']} 通知发送失败，不改变业务退出码")
        return "failed"


def empty_task_stats() -> dict[str, int]:
    return {
        "total": 0,
        "success": 0,
        "already": 0,
        "skipped": 0,
        "failed": 0,
    }


def run_account(
    index: int,
    cookie: str,
    *,
    dry_run: bool,
    random_mode: str,
    stats_days: int,
    delay: int,
    started_monotonic: float,
) -> dict[str, Any]:
    account_started = time.monotonic()
    label = f"账号{index}"
    stats = empty_task_stats()
    errors: list[str] = []
    identity = ""

    print("", flush=True)
    log(f"======== {label} 开始 ========")

    include_stagger = delay > 0 and not dry_run
    total_stages = (1 if include_stagger else 0) + 2
    stage = 0
    if include_stagger:
        stage += 1
        stage_started = time.monotonic()
        remaining = delay - int(time.monotonic() - started_monotonic)
        log(f"[{label}][{stage}/{total_stages}] 错峰等待 开始")
        if remaining > 0:
            log(f"[{label}][{stage}/{total_stages}] 计划延迟 {remaining} 秒")
            time.sleep(remaining)
        log(
            f"[{label}][{stage}/{total_stages}] {ICON['skipped']} 错峰等待结束"
            f"（{time.monotonic() - stage_started:.2f}秒）"
        )

    stage += 1
    stage_started = time.monotonic()
    log(f"[{label}][{stage}/{total_stages}] 每日签到 开始")
    stats["total"] += 1
    outcome = "failure"
    message = ""
    if dry_run:
        outcome = "skipped"
        message = "断网预演：已校验 Cookie 非空，未发起签到请求"
        stats["skipped"] += 1
        log(
            f"[{label}][{stage}/{total_stages}] {ICON['skipped']} {message}"
            f"（{time.monotonic() - stage_started:.2f}秒）"
        )
    else:
        try:
            outcome, message, who = sign(cookie, random_mode)
            if who:
                identity = who
                log(f"[{label}] 官方账号身份：{who}")
            if outcome == "success":
                stats["success"] += 1
                log(
                    f"[{label}][{stage}/{total_stages}] {ICON['success']} {message}"
                    f"（{time.monotonic() - stage_started:.2f}秒）"
                )
            elif outcome == "already":
                stats["already"] += 1
                log(
                    f"[{label}][{stage}/{total_stages}] {ICON['alreadyComplete']} {message}"
                    f"（{time.monotonic() - stage_started:.2f}秒）"
                )
            else:
                stats["failed"] += 1
                errors.append(message)
                log(
                    f"[{label}][{stage}/{total_stages}] {ICON['failure']} {message}"
                    f"（{time.monotonic() - stage_started:.2f}秒）"
                )
        except RequestFailure as exc:
            outcome = "failure"
            message = str(exc)
            stats["failed"] += 1
            errors.append(message)
            log(
                f"[{label}][{stage}/{total_stages}] {ICON['failure']} 签到失败（{message}）"
                f"（{time.monotonic() - stage_started:.2f}秒）"
            )
        except Exception:
            outcome = "failure"
            message = "未预期错误"
            stats["failed"] += 1
            errors.append(message)
            log(
                f"[{label}][{stage}/{total_stages}] {ICON['failure']} 签到失败（{message}）"
                f"（{time.monotonic() - stage_started:.2f}秒）"
            )

    stage += 1
    stage_started = time.monotonic()
    log(f"[{label}][{stage}/{total_stages}] 近{stats_days}天收益统计 开始")
    stats["total"] += 1
    if dry_run:
        stats["skipped"] += 1
        log(
            f"[{label}][{stage}/{total_stages}] {ICON['skipped']} 断网预演：跳过收益统计"
            f"（{time.monotonic() - stage_started:.2f}秒）"
        )
    elif outcome in {"success", "already"}:
        try:
            reward = reward_stats(cookie, stats_days)
            stats["success"] += 1
            log(
                f"[{label}][{stage}/{total_stages}] {ICON['success']} "
                f"近{stats_days}天签到{reward['days_count']}天，"
                f"共{reward['total_amount']}个鸡腿，日均{reward['average']}个"
                f"（{time.monotonic() - stage_started:.2f}秒）"
            )
        except RequestFailure as exc:
            # 保留既有行为：收益统计失败不影响签到成功判定。
            stats["skipped"] += 1
            log(
                f"[{label}][{stage}/{total_stages}] {ICON['warning']} "
                f"收益统计不可用（{exc}）"
                f"（{time.monotonic() - stage_started:.2f}秒）"
            )
    else:
        stats["skipped"] += 1
        log(
            f"[{label}][{stage}/{total_stages}] {ICON['skipped']} 签到未成功，跳过收益统计"
            f"（{time.monotonic() - stage_started:.2f}秒）"
        )

    elapsed = time.monotonic() - account_started
    ok = stats["failed"] == 0
    if dry_run:
        status = "DRY_RUN"
    elif ok:
        status = "SUCCESS"
    else:
        status = "FAILED"
    display = identity or label
    log(
        f"[{label}] 结果={status}；身份={display}；总任务={stats['total']}，"
        f"成功={stats['success']}，已完成={stats['already']}，"
        f"跳过={stats['skipped']}，失败={stats['failed']}，耗时={elapsed:.2f}秒"
    )
    return {
        "index": index,
        "identity": identity,
        "ok": ok,
        "stats": stats,
        "elapsed": elapsed,
        "errors": errors,
    }


def print_task_summary(payload: dict[str, Any]) -> None:
    print(
        "TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = env_true("NODESEEK_DRY_RUN")

    print("=" * 56, flush=True)
    print(f"{TITLE} | 独立维护版", flush=True)
    print(f"开始时间：{started_at}", flush=True)
    print(f"运行模式：{'DRY_RUN（完全断网）' if dry_run else 'LIVE'}", flush=True)
    print("=" * 56, flush=True)

    cookies = load_cookies()
    if not cookies:
        log("账号数量：0")
        log(f"[0/0] {ICON['failure']} 配置错误：请设置 NODESEEK_COOKIE，每个账号占一行")
        body = "账号总数：0；成功：0；失败：1；状态：配置错误"
        notify_state = send_notification(body, dry_run=dry_run)
        finished_at = now_text()
        print("-" * 56, flush=True)
        print("账号结果：总数 0，成功 0，失败 1", flush=True)
        print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0", flush=True)
        print(f"总耗时：{time.monotonic() - overall_started:.2f}秒", flush=True)
        print(f"完成时间：{finished_at}", flush=True)
        print(f"通知状态：{notify_state}", flush=True)
        print("最终状态：CONFIG_ERROR", flush=True)
        print_task_summary(
            {
                "status": "configuration-error",
                "mode": "dry-run" if dry_run else "live",
                "accounts": {"total": 0, "success": 0, "failed": 1},
                "tasks": {
                    "total": 0,
                    "success": 0,
                    "alreadyComplete": 0,
                    "skipped": 0,
                    "failed": 0,
                },
                "notification": notify_state,
                "startedAt": started_at,
                "finishedAt": finished_at,
            }
        )
        return 2

    try:
        max_delay = bounded_int("MAX_RANDOM_DELAY", 3600, 0, 86400)
        stats_days = bounded_int("NS_STATS_DAYS", 30, 1, 365)
        random_raw = os.getenv("NS_RANDOM", "true").strip().lower()
        if random_raw not in TRUE_VALUES | DISABLED:
            raise ValueError("NS_RANDOM 必须是布尔值")
        random_mode = "true" if random_raw in TRUE_VALUES else "false"
        stagger = env_true("RANDOM_SIGNIN", default=False)
    except ValueError as exc:
        log(f"账号数量：{len(cookies)}")
        log(f"[0/0] {ICON['failure']} 配置错误：{exc}")
        body = f"账号总数：{len(cookies)}；成功：0；失败：{len(cookies)}；状态：配置错误"
        notify_state = send_notification(body, dry_run=dry_run)
        finished_at = now_text()
        print("-" * 56, flush=True)
        print(
            f"账号结果：总数 {len(cookies)}，成功 0，失败 {len(cookies)}",
            flush=True,
        )
        print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0", flush=True)
        print(f"总耗时：{time.monotonic() - overall_started:.2f}秒", flush=True)
        print(f"完成时间：{finished_at}", flush=True)
        print(f"通知状态：{notify_state}", flush=True)
        print("最终状态：CONFIG_ERROR", flush=True)
        print_task_summary(
            {
                "status": "configuration-error",
                "mode": "dry-run" if dry_run else "live",
                "accounts": {
                    "total": len(cookies),
                    "success": 0,
                    "failed": len(cookies),
                },
                "tasks": {
                    "total": 0,
                    "success": 0,
                    "alreadyComplete": 0,
                    "skipped": 0,
                    "failed": 0,
                },
                "notification": notify_state,
                "startedAt": started_at,
                "finishedAt": finished_at,
            }
        )
        return 2

    log(f"账号数量：{len(cookies)}")
    log(
        f"随机奖励：{random_mode}；错峰：{'开' if stagger and not dry_run else '关'}；"
        f"统计窗口：{stats_days}天；超时：{TIMEOUT_SECONDS}秒"
    )

    schedule = [
        (random.randint(0, max_delay) if stagger and not dry_run else 0, i, cookie)
        for i, cookie in enumerate(cookies, 1)
    ]
    schedule.sort(key=lambda item: item[0])
    results = [
        run_account(
            index,
            cookie,
            dry_run=dry_run,
            random_mode=random_mode,
            stats_days=stats_days,
            delay=delay,
            started_monotonic=overall_started,
        )
        for delay, index, cookie in schedule
    ]

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
        state_text = "DRY-RUN"
    elif account_failed == 0:
        status = "success"
        exit_code = 0
        state_text = "成功"
    elif account_success:
        status = "partial-failure"
        exit_code = 1
        state_text = "部分失败"
    else:
        status = "failure"
        exit_code = 1
        state_text = "失败"

    # 保留旧版机器可读摘要行，便于既有监控兼容。
    legacy = (
        f"状态: {state_text} | 账号总数: {len(results)} | "
        f"成功: {account_success} | 失败: {account_failed}"
    )
    print(legacy, flush=True)

    body = (
        f"账号总数：{len(results)}；成功：{account_success}；"
        f"失败：{account_failed}；状态：{status}"
    )
    notify_state = send_notification(body, dry_run=dry_run)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started

    print("\n" + "-" * 56, flush=True)
    print(
        f"账号结果：总数 {len(results)}，成功 {account_success}，失败 {account_failed}",
        flush=True,
    )
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {already}，"
        "跳过 {skipped}，失败 {failed}".format(**task_stats),
        flush=True,
    )
    print(f"总耗时：{elapsed:.2f}秒", flush=True)
    print(f"完成时间：{finished_at}", flush=True)
    print(f"通知状态：{notify_state}", flush=True)
    print(f"最终状态：{status.upper()}", flush=True)
    print_task_summary(
        {
            "status": status,
            "mode": "dry-run" if dry_run else "live",
            "accounts": {
                "total": len(results),
                "success": account_success,
                "failed": account_failed,
            },
            "tasks": {
                "total": task_stats["total"],
                "success": task_stats["success"],
                "alreadyComplete": task_stats["already"],
                "skipped": task_stats["skipped"],
                "failed": task_stats["failed"],
            },
            "notification": notify_state,
            "elapsedSeconds": round(elapsed, 3),
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
