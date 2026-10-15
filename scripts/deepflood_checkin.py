#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: DeepFlood 签到
# cron: 0 0 * * *
# SPDX-License-Identifier: MIT
# Maintained from agluo/ql-script-hub deepflood_checkin.py, commit
# a8d39b97cb22c3ac657089014df754342b456ff6 (MIT licensed).
"""DeepFlood attendance and recent attendance-reward statistics.

Required environment:
  DEEPFLOOD_COOKIE  One non-empty browser Cookie header per line. Obtain it by
                    signing in at deepflood.com, opening browser developer
                    tools, selecting an authenticated deepflood.com request,
                    and copying its Request Headers -> Cookie value. Cookies
                    are secrets; never share them.

Optional environment:
  DEEPFLOOD_DRY_RUN=1       Validate configuration and simulate every account
                            without network access, mutation, or waiting.
  DF_RANDOM=true            Value sent as the attendance random query field.
  RANDOM_SIGNIN=true        Opt in to a randomized execution delay (default:
                            false).
  MAX_RANDOM_DELAY=3600     Maximum randomized delay in seconds (0..86400).
  DEEPFLOOD_STATS_DAYS=30   Reward-history window in days (1..365).
  DEEPFLOOD_TIMEOUT=15      HTTP timeout in seconds (1..120).
  QINGLONG_NOTIFY=1         青龙通知总开关；0/false/no/off 关闭。
  QINGLONG_NOTIFY_DIR       可选：包含青龙 notify.py 的目录。

预演不导入通知模块、不发送外部通知，只预览同一份脱敏通知内容。
功能清单：每日签到、近 N 天鸡腿收益统计、多账号、可选随机延迟、断网预演。
与维护候选比较：保留上述全部功能、参数、接口、成功检查和每日计划；
修复全局通知集成、配置错误通知、时间轴与任务统计。无相关来源可供合并。
副作用仅为正式运行提交签到；统计查询只读。默认不启用随机延迟。
上游来源：agluo/ql-script-hub，deepflood_checkin.py，MIT。
原源码没有额外版权声明；保留原任务标记：
cron "33 14 * * *" script-path=xxx.py,tag=匹配cron用
new Env('DeepFlood 签到')
"""

from __future__ import annotations

import json
import math
import importlib.util
import contextlib
import io
import re
from pathlib import Path
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo


BASE_URL = "https://www.deepflood.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 "
    "Safari/537.36 Edg/125.0.0.0"
)


class NoRedirect(HTTPRedirectHandler):
    """Do not forward account credentials to redirect destinations."""

    def redirect_request(self, req, fp, code, msg, response_headers, newurl):
        raise ServiceError("接口发生重定向，已停止请求以保护凭据")


class ConfigurationError(ValueError):
    """Raised for invalid environment configuration."""


class ServiceError(RuntimeError):
    """Raised when HTTP or business validation fails."""


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} 必须为 true/false 或 1/0")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须为整数") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} 必须介于 {minimum} 与 {maximum} 之间")
    return value


def cookie_accounts() -> list[str]:
    raw = os.getenv("DEEPFLOOD_COOKIE", "").replace("\r\n", "\n").replace("\r", "\n")
    accounts = [line.strip() for line in raw.split("\n") if line.strip()]
    if not accounts:
        raise ConfigurationError(
            "必须设置 DEEPFLOOD_COOKIE，每个非空行填写一个账号 Cookie"
        )
    return accounts


def safe_text(value: Any, secrets: list[str]) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for secret in secrets:
        pieces = [secret] + [part.split("=", 1)[-1].strip() for part in secret.split(";")]
        for piece in pieces:
            if piece:
                text = text.replace(piece, "[已脱敏]")
    text = re.sub(r"(?i)(cookie|token|session|authorization|device[_-]?id)\s*[:=]\s*[^\s,;]+", "[已脱敏]", text)
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    return text[:500]


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def show_identity(data: dict[str, Any], cookie: str) -> None:
    # Only explicit public identity fields; never dump response objects.
    containers = [data]
    for key in ("data", "user", "account"):
        if isinstance(data.get(key), dict):
            containers.append(data[key])
    for container in containers:
        for key in ("nickname", "username", "displayName", "display_name", "public_uid", "uid"):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                raw = str(value)
                if raw and safe_text(raw, [cookie]) == raw and not any(c in raw for c in "\r\n"):
                    log(f"官方账号身份（{key}）：{raw}")
                    return


def headers(cookie: str, json_body: bool = False) -> dict[str, str]:
    result = {
        "Accept": "application/json",
        "Cookie": cookie,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/board",
        "User-Agent": USER_AGENT,
    }
    if json_body:
        result["Content-Type"] = "application/json"
    return result


def request_json(
    path: str,
    cookie: str,
    timeout: int,
    *,
    method: str = "GET",
) -> dict[str, Any]:
    """Perform one bounded request and require a JSON object response."""
    request = Request(
        f"{BASE_URL}{path}",
        data=b"" if method == "POST" else None,
        headers=headers(cookie, json_body=method == "POST"),
        method=method,
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ServiceError("接口响应超过大小限制")
    except HTTPError as exc:
        raise ServiceError(f"HTTP request failed with status {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ServiceError("网络请求失败或超时") from exc
    if not 200 <= status < 300:
        raise ServiceError(f"HTTP request failed with status {status}")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ServiceError("service returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ServiceError("service returned an unexpected JSON type")
    show_identity(data, cookie)
    return data


def sign(cookie: str, random_value: str, timeout: int) -> tuple[str, str]:
    query = urlencode({"random": random_value})
    data = request_json(f"/api/attendance?{query}", cookie, timeout, method="POST")
    message = str(data.get("message") or "")
    if data.get("success") is True:
        return "success", "接口已确认签到成功"
    if "已完成签到" in message:
        return "already", "已完成签到"
    # Some deployed API versions express a reward only in their message. Require
    # an explicit attendance-success phrase too; merely mentioning 鸡腿 is unsafe.
    if "签到成功" in message and "鸡腿" in message:
        return "success", "接口已确认签到成功并获得鸡腿"
    status = data.get("status")
    if status in {401, 403, 404}:
        raise ServiceError(f"签到被拒绝，业务状态 {status}")
    raise ServiceError("签到接口未确认成功")


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ServiceError("reward record has no valid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceError("reward record contains an invalid timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_signin_stats(cookie: str, days: int, timeout: int) -> dict[str, Any]:
    shanghai = ZoneInfo("Asia/Shanghai")
    query_start = datetime.now(shanghai) - timedelta(days=days)
    matching: list[dict[str, Any]] = []
    reached_older_record = False

    for page in range(1, 11):
        data = request_json(f"/api/account/credit/page-{page}", cookie, timeout)
        if data.get("success") is not True:
            raise ServiceError("收益接口未确认成功")
        records = data.get("data")
        if not isinstance(records, list):
            raise ServiceError("reward API returned invalid data")
        if not records:
            break

        for record in records:
            if not isinstance(record, list) or len(record) < 4:
                raise ServiceError("reward API returned a malformed record")
            amount, _balance, description, timestamp = record[:4]
            record_time = parse_timestamp(timestamp).astimezone(shanghai)
            if record_time < query_start:
                reached_older_record = True
                continue
            if "签到收益" in str(description) and "鸡腿" in str(description):
                if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
                    raise ServiceError("reward record contains a non-numeric amount")
                matching.append(
                    {
                        "amount": amount,
                        "date": record_time.strftime("%Y-%m-%d"),
                        "description": str(description),
                    }
                )
        if reached_older_record:
            break
        if page < 10:
            time.sleep(0.2)

    total = sum(item["amount"] for item in matching)
    count = len(matching)
    return {
        "period": "今天" if days == 1 else f"近{days}天",
        "days_count": count,
        "total_amount": total,
        "average": round(total / count, 2) if count else 0,
    }


def notify_summary(body: str, dry_run: bool) -> str:
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry_run:
        log("⏭️ DRY-RUN 通知预览（不加载模块、不联网）：" + body.replace("\n", "；"))
        return "dry-run"
    try:
        # Optional Qinglong integration only; business HTTP never depends on it.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                from notify import send
            except ImportError:
                send = None
                paths = []
                directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
                if directory:
                    paths.append(Path(directory) / "notify.py")
                paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
                for path in paths:
                    if path.is_file():
                        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        send = getattr(module, "send", None)
                        if callable(send):
                            break
                if not callable(send):
                    raise ImportError("notify unavailable")
            send("DeepFlood 签到", body)
        log("✅ 脱敏通知已交给青龙 notify.py")
        return "sent"
    except Exception:
        log("⚠️ 青龙通知不可用或发送失败；保留业务退出码")
        return "unavailable-or-failed"


def run_account(index: int, cookie: str, random_value: str, days: int,
                timeout: int, dry_run: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    label = f"账号{index}"
    counts = {"total": 2, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    result = {"account": index, "ok": False, "tasks": counts}
    for stage in (1, 2):
        stage_start = time.monotonic()
        name = "每日签到" if stage == 1 else "签到收益统计"
        log(f"{label} 阶段 {stage}/2：{name} 开始")
        try:
            if dry_run:
                log(f"{label}: DRY-RUN {'attendance' if stage == 1 else str(days) + '-day reward statistics'} simulated；无网络、无等待、无副作用")
                result["attendance" if stage == 1 else "stats"] = "dry-run"
                counts["skipped"] += 1
            elif stage == 1:
                status, message = sign(cookie, random_value, timeout)
                result["attendance"] = status
                counts["already" if status == "already" else "success"] += 1
                log(f"{label}: {'☑️' if status == 'already' else '✅'} 签到已验证（{message}）")
            else:
                stats = get_signin_stats(cookie, days, timeout)
                result["stats"] = stats
                counts["success"] += 1
                log(f"{label}: ✅ {stats['period']}签到{stats['days_count']}天，共获得{stats['total_amount']}个鸡腿，平均{stats['average']}个/天")
            log(f"{label} 阶段 {stage}/2：{name} 完成，耗时 {time.monotonic() - stage_start:.2f} 秒")
        except Exception as exc:
            # Unexpected exceptions may contain secrets: expose only a type.
            error = safe_text(exc, [cookie]) if isinstance(exc, ServiceError) else "执行异常：" + type(exc).__name__
            result["error"] = error
            counts["failed"] += 1
            if stage == 1:
                counts["skipped"] += 1
            log(f"{label} 阶段 {stage}/2：❌ {name} 失败（{error}），耗时 {time.monotonic() - stage_start:.2f} 秒")
            if stage == 1:
                log(f"{label} 阶段 2/2：⏭️ 签到未确认，跳过收益查询，耗时 0 秒")
            break
    result["ok"] = counts["failed"] == 0
    result["duration"] = round(time.monotonic() - started, 2)
    log(f"{label} 统计：总任务 2，成功 {counts['success']}，已完成 {counts['already']}，跳过 {counts['skipped']}，失败 {counts['failed']}，耗时 {result['duration']} 秒")
    return result


def dry_run_account(index: int, days: int) -> dict[str, Any]:
    return run_account(index, "", "true", days, 15, dry_run=True)


def main() -> int:
    started = time.monotonic()
    log("========== DeepFlood 签到 ==========")
    log("开始时间：" + datetime.now().astimezone().isoformat(timespec="seconds"))
    # Determine preview before validating any other parameter; even config errors
    # in preview must never import a notifier or perform HTTP.
    dry_run = os.getenv("DEEPFLOOD_DRY_RUN", "").strip().lower() not in {"", "0", "false", "no", "off"}
    cookies = [line.strip() for line in os.getenv("DEEPFLOOD_COOKIE", "").splitlines() if line.strip()]
    log(f"运行模式：{'DRY-RUN 断网预演' if dry_run else '正式运行'}；账号数：{len(cookies)}")
    results = []
    configuration_error = False
    try:
        cookies = cookie_accounts()
        dry_run = env_bool("DEEPFLOOD_DRY_RUN")
        random_signin = env_bool("RANDOM_SIGNIN")
        max_delay = env_int("MAX_RANDOM_DELAY", 3600, 0, 86400)
        days = env_int("DEEPFLOOD_STATS_DAYS", 30, 1, 365)
        timeout = env_int("DEEPFLOOD_TIMEOUT", 15, 1, 120)
        random_value = os.getenv("DF_RANDOM", "true").strip() or "true"
    except ConfigurationError as exc:
        configuration_error = True
        log("❌ 配置错误：" + safe_text(exc, cookies))
    if not configuration_error:
        if dry_run:
            results = [dry_run_account(i, days) for i in range(1, len(cookies) + 1)]
        else:
            schedule = [(random.randint(0, max_delay) if random_signin else 0, index, cookie)
                        for index, cookie in enumerate(cookies, 1)]
            schedule.sort(key=lambda item: item[0])
            for delay, index, cookie in schedule:
                remaining = delay - (time.monotonic() - started)
                if remaining > 0:
                    log(f"账号{index}: 随机延迟 {int(remaining)} 秒")
                    time.sleep(remaining)
                results.append(run_account(index, cookie, random_value, days, timeout))
    failed = len(cookies) if configuration_error else sum(not r["ok"] for r in results)
    succeeded = 0 if configuration_error else len(results) - failed
    exit_code = 2 if configuration_error else (1 if failed else 0)
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and succeeded else "failure" if failed else "dry-run" if dry_run else "success")
    summary = {"event": "deepflood_summary", "dry_run": dry_run,
               "total": len(cookies), "succeeded": succeeded, "failed": failed, "ok": exit_code == 0}
    log("----------------------------------------")
    task_counts = {key: sum(r["tasks"][key] for r in results)
                   for key in ("total", "success", "already", "skipped", "failed")}
    body = f"状态：{status}\n账号总数：{len(cookies)}，成功数：{succeeded}，失败数：{failed}"
    body += f"\n子任务：成功 {task_counts['success']}，已完成 {task_counts['already']}，跳过 {task_counts['skipped']}，失败 {task_counts['failed']}"
    for result in results:
        if isinstance(result.get("stats"), dict):
            st = result["stats"]
            body += f"\n账号{result['account']}：{st['period']}签到{st['days_count']}天，共{st['total_amount']}个鸡腿，平均{st['average']}个/天"
    log(body.replace("\n", "；"))
    notification = notify_summary(body, dry_run)
    log(f"总耗时：{time.monotonic() - started:.2f} 秒；通知状态：{notification}")
    log("完成时间：" + datetime.now().astimezone().isoformat(timespec="seconds"))
    log(f"最终状态：{status}；退出码：{exit_code}")
    print("SUMMARY_JSON=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    summary.update(status=status, tasks=task_counts, notification=notification,
                   duration=round(time.monotonic() - started, 2), exit_code=exit_code)
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
