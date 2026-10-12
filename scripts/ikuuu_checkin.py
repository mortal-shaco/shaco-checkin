#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ikuuu 签到
# cron: 0 21 * * *
# SPDX-License-Identifier: MIT
"""Standalone Qinglong check-in task for ikuuu.

Adapted from ``ikuuu_checkin.py`` in agluo/ql-script-hub and the original
project at https://github.com/bighammer-link/jichang_dailycheckin .
The upstream attribution and MIT license are preserved.
同时合并 cloudcranes/some_scripts 的 ikuuu/checkin_ikuuu.py（MIT）资料读取能力。
原始脚本来源: https://github.com/bighammer-link/jichang_dailycheckin
本脚本基于原作者的代码进行了适配和优化，以符合本脚本库的统一标准
感谢原作者的贡献！

青龙每天 21:00 执行。IKUUU_ACCOUNT 每行一个邮箱|密码，在服务官网注册或
找回密码后填写；密码中后续的 | 会完整保留。兼容 ikuuu，每行邮箱#密码，
仅在未设置 IKUUU_ACCOUNT 时使用。不再用 & 分隔账号。
IKUUU_MAX_RANDOM_DELAY 可设 0..3600 秒，默认 0。
IKUUU_DRY_RUN=1 完全断网预演，不发送通知、不等待。
QINGLONG_NOTIFY 默认 1，设 0/false/no/off 关闭通知。
IKUUU_PROFILE=1 开启资料读取，默认 0 保留原维护版本的签到流程。
开启后资料读取失败仍继续签到，但该账号整体失败；不输出页面或服务端原始消息。
基础预演成功并不表示真实账号业务成功。
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
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener


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
    name = "IKUUU_ACCOUNT" if "IKUUU_ACCOUNT" in os.environ else "ikuuu"
    delimiter = "|" if name == "IKUUU_ACCOUNT" else "#"
    for index, value in enumerate(parse_accounts(name), 1):
        if delimiter not in value:
            raise TaskError(f"{name} 第 {index} 行必须是邮箱{delimiter}密码")
        email, password = (part.strip() for part in value.split(delimiter, 1))
        if not email or not password:
            raise TaskError(f"{name} 第 {index} 行的邮箱或密码为空")
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


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}")


def show_identity(payload: dict[str, Any], email: str, password: str) -> None:
    # Only explicit official identity fields; do not traverse session/token fields.
    containers = [payload]
    for key in ("data", "user", "profile"):
        value = payload.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in ("nickname", "username", "display_name", "displayName", "public_uid", "uid"):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            identity = str(value)
            # Identity values that are credentials, email addresses, phone numbers,
            # or unsafe control sequences cannot be printed as public identity.
            if (not identity or identity == email or password in identity or "@" in identity
                    or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", identity)
                    or any(ord(c) < 32 or ord(c) == 127 for c in identity)):
                continue
            log(f"官方账号身份 {key}：{identity}")
            return


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        if urlsplit(newurl).scheme != "https" or urlsplit(newurl).netloc != urlsplit(BASE_URL).netloc:
            raise TaskError("服务重定向到非同源地址，已停止请求")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class IkuuuClient:
    def __init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor(), SameOriginRedirect())

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

    def profile(self, email: str, password: str) -> None:
        request = Request(f"{BASE_URL}/user/profile", headers=HEADERS, method="GET")
        try:
            with self.opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200 or "/auth/" in response.geturl():
                    raise TaskError("资料读取失败：状态异常或会话失效")
                payload = response.read(1048577)
        except HTTPError as exc:
            raise TaskError(f"资料读取失败：HTTP {exc.code}") from None
        except (URLError, TimeoutError):
            raise TaskError("资料读取失败：网络错误或超时") from None
        if not payload.strip() or len(payload) > 1048576:
            raise TaskError("资料读取失败：响应为空或过大")
        # Upstream returns HTML: a nonempty page is only a basic read check.
        # Some compatible deployments return JSON with public identity fields.
        if payload.lstrip().startswith(b"{"):
            try:
                value = json.loads(payload)
            except (ValueError, UnicodeError):
                raise TaskError("资料读取失败：JSON 格式异常") from None
            if not isinstance(value, dict) or ("ret" in value and value["ret"] != 1):
                raise TaskError("资料读取失败：业务状态异常")
            show_identity(value, email, password)

    def run(self, email: str, password: str, stats: dict[str, int]) -> tuple[str, str]:
        def stage(number, title, action):
            started = time.monotonic()
            log(f"阶段 {number}/3 {title}：开始")
            try:
                result = action()
            except Exception:
                stats["failed"] += 1
                log(f"❌ 阶段 {number}/3 {title}：失败；耗时 {time.monotonic()-started:.2f} 秒")
                raise
            if result == "already-checked-in":
                stats["alreadyComplete"] += 1
                log(f"☑️ 阶段 {number}/3 {title}：今日已签到；耗时 {time.monotonic()-started:.2f} 秒")
            else:
                stats["succeeded"] += 1
                log(f"✅ 阶段 {number}/3 {title}：完成；耗时 {time.monotonic()-started:.2f} 秒")
            return result

        def login_action():
            value = self.post_json(LOGIN_URL, {"email": email, "passwd": password})
            if value.get("ret") != 1:
                raise TaskError("登录失败：凭据或服务状态异常")
            show_identity(value, email, password)

        try:
            stage(1, "邮箱密码登录", login_action)
        except Exception:
            stats["skipped"] += 2
            log("⏭️ 阶段 2/3 读取资料、阶段 3/3 签到：登录失败，跳过")
            raise
        profile_error = None
        if enabled("IKUUU_PROFILE"):
            try:
                stage(2, "读取个人资料", lambda: self.profile(email, password))
            except TaskError as exc:
                profile_error = exc
                log(str(exc))
            except Exception:
                profile_error = TaskError("资料读取发生执行错误")
        else:
            stats["skipped"] += 1
            log("⏭️ 阶段 2/3 读取个人资料：默认关闭，IKUUU_PROFILE=1 可开启；耗时 0.00 秒")

        detail = ""
        def checkin_action():
            nonlocal detail
            value = self.post_json(CHECKIN_URL)
            show_identity(value, email, password)
            message = redact_message(safe_message(value.get("msg"), ""), email, password)
            if value.get("ret") == 1:
                reward = reward_from(message)
                detail = "签到成功" + (f"，获得流量 {reward}" if reward else "")
                log(detail)
                return "checked-in"
            if any(word in message.lower() for word in ALREADY_WORDS):
                detail = "今日已签到"
                return "already-checked-in"
            raise TaskError("签到失败：未获得官方成功或已签到证明")

        status = stage(3, "每日签到", checkin_action)
        if profile_error:
            raise TaskError("签到已完成，但资料读取失败，账号整体失败")
        return status, detail


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except Exception:
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


def notify_summary(body: str, dry_run: bool) -> str:
    if not enabled("QINGLONG_NOTIFY", "1"):
        print("通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    # A dry-run is strictly no-network; importing notify.py could itself perform I/O.
    if dry_run:
        print("DRY-RUN 通知摘要（未投递以保证完全断网）：" + body)
        return "dry-run"
    sender = load_notify_sender()
    if sender is None:
        print("警告：未找到青龙通知模块，业务退出状态保持不变", file=sys.stderr)
        return "unavailable"
    try:
        sender(TITLE, body)
        print("通知投递完成")
        return "sent"
    except Exception:
        print("警告：通知投递失败，业务退出状态保持不变", file=sys.stderr)
        return "failed"


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
    started = time.monotonic()
    dry_run = enabled(DRY_RUN_ENV)
    log(f"========== {TITLE} ==========\n开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n模式：{'断网预演' if dry_run else '实际运行'}")
    total = succeeded = failed = 0
    task_stats = {"total": 0, "succeeded": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    results = []
    try:
        accounts = parse_account_pairs()
        maximum_delay = delay_seconds()
    except TaskError as exc:
        log(f"❌ 配置错误：{exc}")
        event, code = "configuration-error", 2
        log("账号数量：0（配置无效）")
    else:
        total = len(accounts)
        log(f"账号数量：{total}")
        if not dry_run and maximum_delay:
            log(f"随机错峰等待 {maximum_delay} 秒")
            time.sleep(maximum_delay)
        for index, (email, password) in enumerate(accounts, 1):
            account_started = time.monotonic()
            stats = {"total": 3, "succeeded": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            log(f"---------- 账号 {index}/{total} ----------")
            try:
                if dry_run:
                    for number, title, method, path in (
                        (1, "登录", "POST", "/auth/login"),
                        (2, "读取资料", "GET", "/user/profile"),
                        (3, "签到", "POST", "/user/checkin"),
                    ):
                        if number == 2 and not enabled("IKUUU_PROFILE"):
                            log("⏭️ 阶段 2/3 读取资料：默认关闭，未计划请求；耗时 0.00 秒")
                            continue
                        log(f"⏭️ 阶段 {number}/3 {title}：预演 {method} {BASE_URL}{path}；耗时 0.00 秒，未发送请求")
                    stats["skipped"] = 3
                    status, detail = "dry-run", "参数与请求计划预演通过"
                else:
                    status, detail = IkuuuClient().run(email, password, stats)
                succeeded += 1
                ok = True
            except TaskError as exc:
                status, detail, ok = "failed", str(exc), False
                failed += 1
            except Exception:
                status, detail, ok = "failed", "未预期的执行错误", False
                failed += 1
            for key in task_stats:
                task_stats[key] += stats[key]
            elapsed = round(time.monotonic() - account_started, 2)
            log(f"账号 {index} {'✅' if ok else '❌'} {detail}；总任务 3，成功 {stats['succeeded']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {elapsed:.2f} 秒")
            results.append({"index": index, "success": ok, "status": status, "statistics": stats, "elapsedSeconds": elapsed})
        event = "dry-run" if dry_run else ("success" if not failed else ("partial-failure" if succeeded else "failure"))
        code = 0 if not failed else 1
        if dry_run:
            print(f"DRY-RUN OK: validated {total} account(s); no network requests or mutations performed")
    body = emit_summary(event, total, succeeded, failed)
    log("阶段 4/4 通知：开始")
    notify_started = time.monotonic()
    notification = notify_summary(body, dry_run)
    log(f"通知状态：{notification}；耗时 {time.monotonic()-notify_started:.2f} 秒")
    elapsed = round(time.monotonic() - started, 2)
    finished = datetime.now().isoformat(timespec="seconds")
    log(f"----------------------------------------\n账号统计：总数 {total}，成功 {succeeded}，失败 {failed}\n子任务统计：{json.dumps(task_stats, ensure_ascii=False)}\n总耗时：{elapsed:.2f} 秒\n完成时间：{finished}\n最终状态：{event}；退出码：{code}")
    print("TASK_SUMMARY=" + json.dumps({"event": event, "total": total, "succeeded": succeeded,
          "failed": failed, "statistics": task_stats, "accounts": results,
          "elapsedSeconds": elapsed, "finishedAt": finished, "notification": notification,
          "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


def handler(event: Any = None, context: Any = None) -> int:
    """Compatibility entrypoint for runtimes that call a handler."""
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
