#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 百度网盘签到
# cron: 19 2 * * *
# SPDX-License-Identifier: MIT
# Maintained standalone adaptation of baiduwangpan_checkin.py from
# agluo/ql-script-hub, commit a8d39b97cb22c3ac657089014df754342b456ff6.

"""Baidu Netdisk daily membership sign-in and growth-question task.

Configuration:
  BAIDU_COOKIE              Required. One complete Cookie header per non-empty
                            line (one account per line).
  BAIDUWANGPAN_DRY_RUN=1    Validate configuration without network or changes.
  BAIDUWANGPAN_DELAY_MAX=0  Optional maximum random seconds between accounts.
  QINGLONG_NOTIFY=1         Set to 0/false/no/off to disable Qinglong notices.

Get a cookie by signing in at https://pan.baidu.com/, opening the browser
developer tools Network panel, refreshing, selecting a pan.baidu.com request,
and copying its complete Cookie request header. Treat it as a password.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


APP_ID = "250528"
TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
NOTIFY_DISABLED_VALUES = {"0", "false", "no", "off"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
)


class TaskError(RuntimeError):
    """A redacted, user-facing task error."""


@dataclass
class AccountResult:
    account: int
    success: bool = False
    signin: str = "not_run"
    question: str = "not_run"
    profile: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def parse_nonnegative_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise TaskError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise TaskError(f"{name} must be a non-negative integer")
    return value


def cookies_from_env() -> list[str]:
    cookies = [line.strip() for line in os.environ.get("BAIDU_COOKIE", "").splitlines() if line.strip()]
    if not cookies:
        raise TaskError(
            "BAIDU_COOKIE is required; copy the complete Cookie request header "
            "from a signed-in pan.baidu.com browser request and put one account per line"
        )
    if any("=" not in cookie for cookie in cookies):
        raise TaskError("each BAIDU_COOKIE line must be a complete Cookie header containing key=value")
    return cookies


def walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def message_from(payload: dict[str, Any]) -> str:
    for item in walk_dicts(payload):
        for key in ("show_msg", "error_msg", "errmsg", "message", "msg"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())[:160]
    return ""


def business_code(payload: dict[str, Any]) -> str:
    for key in ("errno", "error_code", "code"):
        if key in payload and payload[key] is not None:
            return str(payload[key])[:32]
    return "unknown"


class BaiduClient:
    def __init__(self, cookie: str) -> None:
        self._cookie = cookie

    def get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Cookie": self._cookie,
                "Referer": "https://pan.baidu.com/wap/svip/growth/task",
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = response.status
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise TaskError(f"HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TaskError("network request failed or timed out") from exc
        if status != 200:
            raise TaskError(f"HTTP {status}")
        if len(body) > MAX_RESPONSE_BYTES:
            raise TaskError("server response exceeded the size limit")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TaskError("server returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TaskError("server returned an unexpected JSON value")
        return payload

    def signin(self) -> str:
        data = self.get_json(
            "https://pan.baidu.com/rest/2.0/membership/level",
            {"app_id": APP_ID, "web": "5", "method": "signin"},
        )
        for item in walk_dicts(data):
            points = item.get("points")
            if isinstance(points, (int, str)) and str(points).isdigit():
                return f"success ({points} points)"
        message = message_from(data)
        if any(term in message.lower() for term in ("已签到", "重复签到", "not allow")):
            return "already completed"
        raise TaskError(
            f"sign-in rejected (business code {business_code(data)}): "
            f"{message or 'no explicit success marker'}"
        )

    def get_question(self) -> tuple[str, str]:
        data = self.get_json(
            "https://pan.baidu.com/act/v2/membergrowv2/getdailyquestion",
            {"app_id": APP_ID, "web": "5"},
        )
        for item in walk_dicts(data):
            answer, ask_id = item.get("answer"), item.get("ask_id")
            if answer is not None and ask_id is not None and str(ask_id):
                return str(answer), str(ask_id)
        message = message_from(data)
        raise TaskError(
            f"question unavailable (business code {business_code(data)}): "
            f"{message or 'answer or ask_id missing'}"
        )

    def answer_question(self, answer: str, ask_id: str) -> str:
        data = self.get_json(
            "https://pan.baidu.com/act/v2/membergrowv2/answerquestion",
            {"app_id": APP_ID, "web": "5", "ask_id": ask_id, "answer": answer},
        )
        for item in walk_dicts(data):
            score = item.get("score")
            if isinstance(score, (int, str)) and str(score).isdigit():
                return f"success ({score} points)"
        message = message_from(data)
        if any(term in message.lower() for term in ("已回答", "exceeded", "超出", "超限")):
            return "already completed"
        raise TaskError(
            f"answer rejected (business code {business_code(data)}): "
            f"{message or 'no explicit success marker'}"
        )

    def profile(self) -> dict[str, Any]:
        data = self.get_json(
            "https://pan.baidu.com/rest/2.0/membership/user",
            {"app_id": APP_ID, "web": "5", "method": "query"},
        )
        source = next(
            (item for item in walk_dicts(data) if "current_level" in item or "username" in item),
            None,
        )
        if source is None:
            raise TaskError(
                f"profile response missing expected fields (business code {business_code(data)})"
            )
        username = str(source.get("username") or "unknown")
        masked = "***" if len(username) <= 2 else f"{username[0]}***{username[-1]}"
        vip_names = {0: "standard", 1: "member", 2: "super_member", 3: "premium_member"}
        try:
            membership = vip_names.get(int(source.get("vip_type", 0)), "unknown")
        except (TypeError, ValueError):
            membership = "unknown"
        return {
            "username": masked,
            "level": source.get("current_level", "unknown"),
            "growth": source.get("current_value", "unknown"),
            "membership": membership,
        }


def run_account(cookie: str, index: int, dry_run: bool) -> AccountResult:
    result = AccountResult(account=index)
    if dry_run:
        result.signin = "dry_run"
        result.question = "dry_run"
        result.profile = {"status": "dry_run"}
        result.success = True
        return result

    client = BaiduClient(cookie)
    try:
        result.signin = client.signin()
    except TaskError as exc:
        result.errors.append(str(exc))
    try:
        answer, ask_id = client.get_question()
        result.question = client.answer_question(answer, ask_id)
    except TaskError as exc:
        result.errors.append(str(exc))
    try:
        result.profile = client.profile()
    except TaskError as exc:
        result.errors.append(f"profile verification failed: {exc}")
    result.success = not result.errors and all(
        value != "not_run" for value in (result.signin, result.question)
    )
    return result


def load_notify_sender() -> Any:
    try:
        module = importlib.import_module("notify")
        if callable(getattr(module, "send", None)):
            return module.send
    except (ImportError, AttributeError):
        pass

    candidates: list[Path] = []
    custom_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for index, path in enumerate(candidates):
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"qinglong_notify_{index}", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if callable(getattr(module, "send", None)):
                return module.send
        except Exception:
            continue
    return None


def log_banner(mode: str, total: int) -> None:
    print("百度网盘签到")
    print("═" * 62)
    print(f"运行模式  {mode}")
    print(f"账号数量  {total}")
    print(f"开始时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def notify_summary(status: str, total: int, successful: int, failed: int, dry_run: bool) -> str:
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in NOTIFY_DISABLED_VALUES:
        print("QINGLONG_NOTIFY_DISABLED")
        return "已关闭"
    mode = "dry-run" if dry_run else "live"
    body = (
        f"状态: {status}; 模式: {mode}; 账号总数: {total}; "
        f"成功数: {successful}; 失败数: {failed}"
    )
    sender = load_notify_sender()
    if sender is None:
        print("QINGLONG_NOTIFY_UNAVAILABLE", file=sys.stderr)
        return "未找到通知组件"
    try:
        sender("百度网盘每日签到与答题", body)
        print("QINGLONG_NOTIFY_SENT")
        return "青龙任务总结已推送"
    except Exception:
        print("QINGLONG_NOTIFY_FAILED", file=sys.stderr)
        return "推送失败"


def log_task_summary(summary: dict[str, Any], notification: str, started: float) -> None:
    elapsed = round(time.monotonic() - started, 1)
    payload = {**summary, "elapsed_seconds": elapsed, "notification": notification}
    label = "预演通过" if summary.get("mode") == "dry-run" and summary.get("status") == "success" else {
        "success": "全部成功",
        "partial_failure": "部分失败",
        "failure": "失败",
        "configuration_error": "配置失败",
    }.get(str(summary.get("status")), str(summary.get("status")))
    timeline("生成任务总结")
    timeline(f"通知状态：{notification}", "└─")
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"最终状态  {label}")
    print(f"账号统计  总数 {summary.get('accounts', 0)} │ 成功 {summary.get('successful', 0)} │ 失败 {summary.get('failed', 0)}")
    print(f"任务统计  总数 {summary.get('accounts', 0) * 3} │ 账号成功 {summary.get('successful', 0)} │ 账号失败 {summary.get('failed', 0)}")
    print(f"通知状态  {notification}")
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    started = time.monotonic()
    dry_run = enabled("BAIDUWANGPAN_DRY_RUN")
    try:
        cookies = cookies_from_env()
        delay_max = parse_nonnegative_int("BAIDUWANGPAN_DELAY_MAX", 0)
    except TaskError as exc:
        summary = {
            "status": "configuration_error",
            "mode": "dry-run" if dry_run else "live",
            "accounts": 0,
            "successful": 0,
            "failed": 1,
            "error": str(exc),
        }
        log_banner("预演" if dry_run else "正式执行", 0)
        timeline(f"配置失败：{exc}", "└─")
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        notification = notify_summary("configuration_error", 0, 0, 1, dry_run)
        log_task_summary(summary, notification, started)
        return 2

    log_banner("预演" if dry_run else "正式执行", len(cookies))
    results: list[AccountResult] = []
    for index, cookie in enumerate(cookies, 1):
        account_started = time.monotonic()
        print()
        timeline(f"账号 {index:02d}：[1/4] 参数校验（{index}/{len(cookies)}）")
        timeline(f"账号 {index:02d}：✓ Cookie 格式有效（内容已隐藏）", "└─")
        if index > 1 and delay_max and not dry_run:
            time.sleep(random.randint(0, delay_max))
        timeline(f"账号 {index:02d}：[2/4] 每日签到")
        try:
            account_result = run_account(cookie, index, dry_run)
        except Exception:
            account_result = AccountResult(account=index, errors=["unexpected internal account error"])
        results.append(account_result)
        signin_mark = "✓" if account_result.signin != "not_run" else "✗"
        timeline(f"账号 {index:02d}：{signin_mark} 签到状态：{account_result.signin}", "└─")
        timeline(f"账号 {index:02d}：[3/4] 每日答题")
        question_mark = "✓" if account_result.question != "not_run" else "✗"
        timeline(f"账号 {index:02d}：{question_mark} 答题状态：{account_result.question}", "└─")
        timeline(f"账号 {index:02d}：[4/4] 生成账号结果")
        for error in account_result.errors:
            timeline(f"账号 {index:02d}：✗ {error}", "├─")
        timeline(f"账号 {index:02d}：{'✓ 成功' if account_result.success else '✗ 失败'}", "└─")
        timeline(f"总任务 3 │ 用时 {time.monotonic() - account_started:.1f} 秒", "└─")

    successful = sum(result.success for result in results)
    failed = len(results) - successful
    status = "success" if failed == 0 else ("partial_failure" if successful else "failure")
    summary = {
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": len(results),
        "successful": successful,
        "failed": failed,
        "results": [asdict(result) for result in results],
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    notification = notify_summary(status, len(results), successful, failed, dry_run)
    log_task_summary(summary, notification, started)
    if dry_run and failed == 0:
        print("DRY_RUN_OK")
    elif not dry_run and failed == 0:
        print("BAIDUWANGPAN_ALL_ACCOUNTS_OK")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
