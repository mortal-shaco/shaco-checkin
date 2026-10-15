#!/usr/bin/env python3
# name: 春风动力签到
# cron: 5 0 * * *
"""CFMOTO daily points tasks for Qinglong.

cron: 5 0 * * *
new Env('春风动力签到')

Environment:
  CFMOTO_COOKIE             Required. A ticket value or full Cookie header.
                            Separate accounts with newlines.
  CFMOTO_DRY_RUN            Optional. 1 prepares requests without sending them.
  CFMOTO_RANDOM_DELAY_MAX   Optional. Maximum pre-run delay in seconds; default 0.
  CFMOTO_ACTIVITY_COUNT     Optional. Post/comment/like/share rounds; 0-3, default 3.
  CFMOTO_ACTION_DELAY      Optional. Delay between actions; 0-30 seconds, default 2.
  CFMOTO_POST_CONTENTS     Optional. Post texts separated by newlines or |.
  CFMOTO_NOTIFY             Optional. 0 disables notify.py integration.
"""

from __future__ import annotations

import json
import importlib.util
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


NAME = "春风动力签到"
SIGN_URL = "https://c.cfmoto.com/cfmotoservermall/app/integral/task/complete/v1"
PUBLISH_URL = "https://c.cfmoto.com/jv/bbs/post/create-v5/"
COMMENT_URL = "https://c.cfmoto.com/jv/bbs/article/comment-v1/"
LIKE_URL = "https://c.cfmoto.com/jv/bbs/post/thumbs_up/{post_id}"
TEXT_API_URL = "https://v1.hitokoto.cn/?encode=json"
MAX_DAILY_ACTIVITIES = 3
DEFAULT_USER_AGENT = (
    "MOBILE|iOS|15.4|KLICEN_APP|5.0.1|iPhone|iPhone|1170*2532|"
    "13C74FB1-4F8C-42FD-BCB7-836DB6AF2FB3"
)
SUCCESS_HINTS = ("成功", "完成")
ALREADY_DONE_HINTS = ("已签到", "重复签到", "已完成", "今日已签", "次数已达上限", "已达上限")
DEFAULT_CONTENTS = (
    "保持热爱，奔赴山海。",
    "一路向前，沿途都是风景。",
    "骑行不止，热爱不息。",
    "今天也是元气满满的一天。",
    "心中有方向，脚下有力量。",
    "享受旅程，也享受抵达。",
)


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    points: int | float | None = None
    already_done: bool = False


def enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_accounts(value: str) -> list[str]:
    """Return unique non-empty accounts while preserving their order."""
    accounts: list[str] = []
    seen: set[str] = set()
    for line in str(value or "").splitlines():
        account = line.strip()
        if account and account not in seen:
            accounts.append(account)
            seen.add(account)
    return accounts


def ticket_from_account(account: str) -> str:
    """Accept either a bare ticket or a full Cookie header."""
    value = account.strip()
    match = re.search(r"(?:^|;\s*)ticket=([^;]+)", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if ";" in value or re.match(r"^[A-Za-z_][A-Za-z0-9_-]*=", value):
        raise ValueError("完整 Cookie 中没有 ticket 字段")
    if not value:
        raise ValueError("ticket 为空")
    return value


def parse_response(payload: Any, action: str) -> Result:
    if not isinstance(payload, dict):
        return Result(False, "接口响应格式异常")
    code = payload.get("code")
    message = str(payload.get("msg") or payload.get("message") or "").strip()
    data = payload.get("data")
    points = data if isinstance(data, (int, float)) and not isinstance(data, bool) else None

    if str(code) == "0":
        detail = f"{action}成功，获得 {points:g} 积分" if points and points > 0 else f"{action}成功"
        return Result(True, detail, points=points)
    if any(hint in message for hint in ALREADY_DONE_HINTS):
        return Result(True, f"{action}今日已完成", already_done=True)
    if code is None and any(hint in message for hint in SUCCESS_HINTS):
        return Result(True, f"{action}成功")
    return Result(False, f"{action}失败：{message or f'业务码 {code}'}")


def request_json(
    url: str, ticket: str, method: str, payload: dict[str, Any], timeout: float = 15.0
) -> tuple[dict[str, Any] | None, str | None]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cookie": f"ticket={ticket}",
            "User-Agent": os.getenv("CFMOTO_USER_AGENT", DEFAULT_USER_AGENT),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                return None, "接口响应超过 1 MiB，已拒绝处理"
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(raw.decode(charset, errors="replace"))
            if not isinstance(payload, dict):
                return None, "接口响应格式异常"
            return payload, None
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}"
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", None)
        return None, "网络请求失败" + (f"（{type(reason).__name__}）" if reason else "")
    except TimeoutError:
        return None, "网络请求超时"
    except (UnicodeError, json.JSONDecodeError):
        return None, "接口未返回有效 JSON"


def request_task(ticket: str, task_detail: int, action: str) -> Result:
    payload, error = request_json(
        SIGN_URL, ticket, "PUT", {"completeStatu": 1, "taskDetail": task_detail}
    )
    return Result(False, f"{action}失败：{error}") if error else parse_response(payload, action)


def publish(ticket: str, content: str) -> tuple[Result, str | None]:
    payload, error = request_json(
        PUBLISH_URL,
        ticket,
        "POST",
        {
            "title": "",
            "content": content,
            "media_type": "TEXT",
            "is_vote": False,
            "address": "",
            "city_code": "0",
            "latitude": 0.0,
            "longitude": 0.0,
            "resource_list": [],
            "topic_list": [],
            "post_vote_list": [],
        },
    )
    if error:
        return Result(False, f"发帖失败：{error}"), None
    result = parse_response(payload, "发帖")
    data = payload.get("data") if payload else None
    post_id = data.get("id") if isinstance(data, dict) else None
    if result.ok and not result.already_done and not post_id:
        return Result(False, "发帖失败：响应缺少帖子 ID"), None
    return result, str(post_id) if post_id else None


def comment(ticket: str, post_id: str, content: str) -> Result:
    payload, error = request_json(
        COMMENT_URL, ticket, "POST", {"post_id": post_id, "content": content}
    )
    return Result(False, f"评论失败：{error}") if error else parse_response(payload, "评论")


def like(ticket: str, post_id: str) -> Result:
    payload, error = request_json(
        LIKE_URL.format(post_id=post_id), ticket, "POST", {"post_id": post_id}
    )
    return Result(False, f"点赞失败：{error}") if error else parse_response(payload, "点赞")


def notify(summary: str) -> str:
    if not enabled("QINGLONG_NOTIFY", default=True) or not enabled("CFMOTO_NOTIFY", default=True):
        return "⏭️ 已关闭"
    sender = None
    try:
        from notify import send as sender  # type: ignore
    except ImportError:
        search_roots = [
            os.getenv("QINGLONG_NOTIFY_DIR", ""),
            "/ql/data/scripts",
            "/ql/scripts",
            str(Path.cwd()),
        ]
        for root in filter(None, search_roots):
            notify_path = Path(root) / "notify.py"
            if not notify_path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify", notify_path)
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    sender = getattr(module, "send", None)
                    if callable(sender):
                        break
                except Exception:
                    continue
    if not callable(sender):
        print(f"[{NAME}] 未找到青龙 notify.py，已跳过任务总结推送。", file=sys.stderr)
        return "⚠️ 未找到通知组件"
    try:
        sender(NAME, summary)
        return "✅ 青龙任务总结已推送"
    except Exception as error:  # Notifications must not change the task result.
        print(f"[{NAME}] 通知发送失败：{type(error).__name__}", file=sys.stderr)
        return "⚠️ 推送失败"


def log_banner(mode: str, total: int) -> None:
    print("春风动力签到")
    print("═" * 62)
    print(f"运行模式  {mode}")
    print(f"账号数量  {total}")
    print(f"开始时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def log_task_summary(account_results: list[list[Result]], notification: str, started: float, dry_run: bool, status_override: str | None = None) -> None:
    total = sum(len(items) for items in account_results)
    succeeded = sum(result.ok and not result.already_done for items in account_results for result in items)
    completed = sum(result.already_done for items in account_results for result in items)
    failed = sum(not result.ok for items in account_results for result in items)
    account_failed = sum(any(not result.ok for result in items) for items in account_results)
    elapsed = round(time.monotonic() - started, 1)
    status = status_override or ("dry_run" if dry_run and not failed else ("success" if not failed else "partial_failure"))
    label = "配置失败" if status == "configuration_error" else ("预演通过" if status == "dry_run" else ("全部成功" if status == "success" else "部分成功"))
    payload = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts_total": len(account_results), "accounts_success": len(account_results) - account_failed, "accounts_partial_or_failed": account_failed, "tasks_total": total, "tasks_success": succeeded, "tasks_already_complete": completed, "tasks_skipped": 0, "tasks_failed": failed, "elapsed_seconds": elapsed, "notification": notification}
    timeline("生成任务总结")
    timeline(f"通知状态：{notification}", "└─")
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"最终状态  {label}")
    print(f"账号统计  总数 {len(account_results)} │ 成功 {len(account_results) - account_failed} │ 部分/失败 {account_failed}")
    print(f"任务统计  总数 {total} │ 成功 {succeeded} │ 已完成 {completed} │ 跳过 0 │ 失败 {failed}")
    print(f"通知状态  {notification}")
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def configured_delay() -> int:
    raw = os.getenv("CFMOTO_RANDOM_DELAY_MAX", "0").strip()
    try:
        maximum = int(raw)
    except ValueError as error:
        raise ValueError("CFMOTO_RANDOM_DELAY_MAX 必须是整数") from error
    if not 0 <= maximum <= 3600:
        raise ValueError("CFMOTO_RANDOM_DELAY_MAX 必须在 0 到 3600 之间")
    return random.randint(0, maximum) if maximum else 0


def bounded_number(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} 必须是整数") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def post_contents() -> list[str]:
    configured = os.getenv("CFMOTO_POST_CONTENTS", "")
    values = [item.strip() for item in re.split(r"[|\n]+", configured) if item.strip()]
    return values or list(DEFAULT_CONTENTS)


def fetch_random_text(timeout: float = 8.0) -> tuple[str | None, str | None]:
    """Fetch one public sentence without sending the CFMOTO account credential."""
    request = urllib.request.Request(
        TEXT_API_URL,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "qinglong-cfmoto-checkin/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(16_385)
            if len(raw) > 16_384:
                return None, "文案接口响应超过 16 KiB"
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(raw.decode(charset, errors="strict"))
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}"
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", None)
        return None, "网络请求失败" + (f"（{type(reason).__name__}）" if reason else "")
    except TimeoutError:
        return None, "网络请求超时"
    except (UnicodeError, json.JSONDecodeError):
        return None, "接口未返回有效 JSON"

    value = payload.get("hitokoto") if isinstance(payload, dict) else None
    text = re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""
    if not text:
        return None, "接口未返回有效文案"
    source_value = payload.get("from") if isinstance(payload, dict) else None
    author_value = payload.get("from_who") if isinstance(payload, dict) else None
    source = re.sub(r"\s+", " ", source_value).strip() if isinstance(source_value, str) else ""
    author = re.sub(r"\s+", " ", author_value).strip() if isinstance(author_value, str) else ""
    if source and author:
        text = f"{text} —— {author}《{source}》"
    elif source:
        text = f"{text} ——《{source}》"
    elif author:
        text = f"{text} —— {author}"
    if len(text) > 280:
        return None, "接口文案超过 280 字"
    return text, None


def activity_content(fallbacks: list[str], action: str, account_index: int) -> str:
    remote, error = fetch_random_text()
    if remote:
        timeline(f"账号 {account_index:02d}：✓ {action}使用接口随机文案", "├─")
        return remote
    fallback = random.choice(fallbacks)
    timeline(f"账号 {account_index:02d}：! 文案接口不可用（{error or '未知错误'}）", "├─")
    timeline(f"账号 {account_index:02d}：已切换本地兜底文案", "↳")
    return fallback


def show(index: int, result: Result) -> None:
    icon = "☑" if result.already_done else ("✓" if result.ok else "✗")
    timeline(f"账号 {index:02d}：{icon} {result.message}", "└─")


def run_account(ticket: str, index: int, activity_count: int, action_delay: int) -> list[Result]:
    timeline(f"账号 {index:02d}：[1/4] 参数校验")
    timeline(f"账号 {index:02d}：✓ ticket 字段有效（内容已隐藏）", "└─")
    timeline(f"账号 {index:02d}：[2/4] 每日签到")
    results = [request_task(ticket, 8, "签到")]
    show(index, results[-1])
    contents = post_contents()
    timeline(f"账号 {index:02d}：[3/4] 社区互动")
    timeline(f"账号 {index:02d}：计划执行 {activity_count} 轮发帖、评论、点赞和分享", "└─")

    for round_index in range(activity_count):
        timeline(f"账号 {index:02d}：第 {round_index + 1}/{activity_count} 轮社区互动")
        if action_delay:
            time.sleep(action_delay)
        content = activity_content(contents, "发帖", index)
        publish_result, post_id = publish(ticket, content)
        results.append(publish_result)
        show(index, publish_result)

        if post_id:
            if action_delay:
                time.sleep(action_delay)
            comment_content = activity_content(contents, "评论", index)
            comment_result = comment(ticket, post_id, comment_content)
            results.append(comment_result)
            show(index, comment_result)

            if action_delay:
                time.sleep(action_delay)
            like_result = like(ticket, post_id)
            results.append(like_result)
            show(index, like_result)
        elif not publish_result.already_done:
            skipped = Result(False, "发帖失败，已跳过依赖该帖子 ID 的评论和点赞")
            results.extend((skipped, skipped))
            show(index, skipped)

        if action_delay:
            time.sleep(action_delay)
        share_result = request_task(ticket, 13, "分享")
        results.append(share_result)
        show(index, share_result)

    timeline(f"账号 {index:02d}：[4/4] 生成账号结果")
    timeline(f"账号 {index:02d}：✓ 全部动作已处理", "└─")
    return results


def main() -> int:
    started = time.monotonic()
    accounts = parse_accounts(os.getenv("CFMOTO_COOKIE", ""))
    if not accounts:
        log_banner("正式执行", 0)
        message = "配置失败：缺少 CFMOTO_COOKIE。请填写 ticket 值或包含 ticket 的完整 Cookie。"
        print(f"[{NAME}] {message}", file=sys.stderr)
        notification = notify(message)
        log_task_summary([], notification, started, False, "configuration_error")
        return 2

    dry_run = enabled("CFMOTO_DRY_RUN")
    try:
        tickets = [ticket_from_account(account) for account in accounts]
        delay = configured_delay()
        activity_count = bounded_number(
            "CFMOTO_ACTIVITY_COUNT", MAX_DAILY_ACTIVITIES, 0, MAX_DAILY_ACTIVITIES
        )
        action_delay = bounded_number("CFMOTO_ACTION_DELAY", 2, 0, 30)
    except ValueError as error:
        log_banner("预演" if dry_run else "正式执行", len(accounts))
        message = f"配置错误：{error}"
        print(f"[{NAME}] {message}", file=sys.stderr)
        notification = notify(message)
        log_task_summary([], notification, started, dry_run, "configuration_error")
        return 2

    log_banner("预演" if dry_run else "正式执行", len(tickets))
    timeline(f"互动任务：{activity_count}/{MAX_DAILY_ACTIVITIES} 轮", "└─")
    if delay:
        timeline(f"随机延迟 {delay} 秒", "└─")
        time.sleep(delay)

    account_results: list[list[Result]] = []
    for index, ticket in enumerate(tickets, 1):
        account_started = time.monotonic()
        print()
        timeline(f"账号 {index:02d} 开始执行（{index}/{len(tickets)}）")
        if dry_run:
            planned = 1 + activity_count * 4
            timeline(f"账号 {index:02d}：[1/4] 参数校验")
            timeline(f"账号 {index:02d}：✓ ticket 字段有效（内容已隐藏）", "└─")
            timeline(f"账号 {index:02d}：[2/4] 每日签到")
            timeline(f"账号 {index:02d}：↳ 预演未发送请求", "└─")
            timeline(f"账号 {index:02d}：[3/4] 社区互动")
            timeline(f"账号 {index:02d}：↳ 计划 {planned - 1} 个互动请求，未发送", "└─")
            timeline(f"账号 {index:02d}：[4/4] 生成账号结果")
            results = [Result(True, f"预演完成，计划 {planned} 个请求，未发送任何请求")]
            show(index, results[0])
        else:
            results = run_account(ticket, index, activity_count, action_delay)
        account_results.append(results)
        failed = sum(not item.ok for item in results)
        success = sum(item.ok and not item.already_done for item in results)
        completed = sum(item.already_done for item in results)
        account_label = "✓ 成功" if not failed else "! 部分成功" if success or completed else "✗ 失败"
        timeline(f"账号 {index:02d}：{account_label}")
        timeline(f"总任务 {len(results)} │ 成功 {success} │ 已完成 {completed} │ 跳过 0 │ 失败 {failed} │ 用时 {time.monotonic() - account_started:.1f} 秒", "└─")

    succeeded_accounts = sum(all(result.ok for result in results) for results in account_results)
    failed_accounts = len(account_results) - succeeded_accounts
    summary = (
        f"{len(account_results)} 个账号，全部任务成功 {succeeded_accounts} 个，"
        f"存在失败 {failed_accounts} 个"
    )
    print(f"[{NAME}] 汇总：{summary}。")
    notification = notify(summary)
    log_task_summary(account_results, notification, started, dry_run)
    return 0 if failed_accounts == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
