#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NGA 论坛签到
# cron: 1 17 * * *
# SPDX-License-Identifier: MIT
# Maintained from nga_checkin.py in agluo/ql-script-hub (commit
# a8d39b97cb22c3ac657089014df754342b456ff6). Original and modifications MIT.
"""NGA daily check-in and optional mission actions for Qinglong.

Accounts are configured as ``access_uid|access_token`` lines in NGA_ACCOUNT.
The script never logs either value. Optional mission actions
are off by default because they mutate reward/task state beyond check-in.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


TITLE = "NGA论坛签到"
API_URL = "https://ngabbs.com/nuke.php"
APP_ID = "1010"
MAX_RESPONSE_BYTES = 65536
DISABLED_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = DISABLED_VALUES


class ConfigError(ValueError):
    """A safe-to-display configuration error."""


class ApiError(RuntimeError):
    """A redacted transport or response error."""


@dataclass(frozen=True)
class Config:
    uids: list[str]
    tokens: list[str]
    user_agent: str
    dry_run: bool
    daily_missions: bool
    video_missions: bool
    share_missions: bool
    query_stats: bool
    random_delay_max: int
    action_delay: float
    video_delay: float
    timeout: float


@dataclass
class AccountResult:
    index: int
    success: bool = True
    outcomes: list[str] = field(default_factory=list)

    def add(self, action: str, ok: bool, detail: str) -> None:
        self.outcomes.append(f"{action}: {detail}")
        if not ok:
            self.success = False


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ConfigError(f"{name} 必须是 1/0、true/false、yes/no 或 on/off")


def env_number(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数字") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return value


def account_lines(name: str) -> dict[int, str]:
    value = os.getenv(name, "").replace("\r\n", "\n").replace("\r", "\n")
    if not value.strip():
        raise ConfigError(f"缺少必填环境变量 {name}")
    return {index: line.strip() for index, line in enumerate(value.split("\n"), 1) if line.strip()}


def load_config() -> Config:
    account_values = account_lines("NGA_ACCOUNT")
    uids: list[str] = []
    tokens: list[str] = []
    for index, value in account_values.items():
        if "|" not in value:
            raise ConfigError(f"NGA_ACCOUNT 第 {index} 行必须是 access_uid|access_token")
        uid, token = (part.strip() for part in value.split("|", 1))
        if not uid or not token:
            raise ConfigError(f"NGA_ACCOUNT 第 {index} 行的 UID 或 Token 为空")
        uids.append(uid)
        tokens.append(token)
    if any("\n" in item or not item for item in uids + tokens):
        raise ConfigError("账号配置包含无效值")
    user_agent = os.getenv("NGA_UA", "Nga_Official/90409").strip()
    if not user_agent or "\r" in user_agent or "\n" in user_agent:
        raise ConfigError("NGA_UA 不能为空或包含换行")
    return Config(
        uids=uids,
        tokens=tokens,
        user_agent=user_agent,
        dry_run=env_bool("NGA_DRY_RUN", False),
        daily_missions=env_bool("NGA_ENABLE_DAILY_MISSIONS", False),
        video_missions=env_bool("NGA_ENABLE_VIDEO_MISSIONS", False),
        share_missions=env_bool("NGA_ENABLE_SHARE_MISSIONS", False),
        query_stats=env_bool("NGA_QUERY_STATS", True),
        random_delay_max=int(env_number("NGA_RANDOM_DELAY_MAX", 0, 0, 21600)),
        action_delay=env_number("NGA_ACTION_DELAY_SECONDS", 1, 0, 30),
        video_delay=env_number("NGA_VIDEO_DELAY_SECONDS", 30, 0, 120),
        timeout=env_number("NGA_HTTP_TIMEOUT", 20, 3, 60),
    )


class NgaClient:
    def __init__(self, uid: str, token: str, user_agent: str, timeout: float):
        self.uid = uid
        self.token = token
        self.user_agent = user_agent
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context())
        )

    def request(self, lib: str, act: str, extra: Optional[dict[str, str]] = None) -> dict[str, Any]:
        form = {
            "access_uid": self.uid,
            "access_token": self.token,
            "app_id": APP_ID,
            "__act": act,
            "__lib": lib,
            "__output": "11",
        }
        if extra:
            form.update(extra)
        request = urllib.request.Request(
            API_URL,
            data=urllib.parse.urlencode(form).encode("utf-8"),
            headers={
                "User-Agent": self.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP 状态异常 ({exc.code})") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ApiError("网络请求失败或超时") from None
        if status < 200 or status >= 300:
            raise ApiError(f"HTTP 状态异常 ({status})")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ApiError("响应超过安全大小限制")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError("响应不是有效 JSON") from None
        if not isinstance(payload, dict):
            raise ApiError("响应结构无效")
        return payload


def error_text(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, list) and error:
        return str(error[0])
    if isinstance(error, str):
        return error
    return ""


def explicit_success(payload: dict[str, Any]) -> bool:
    if error_text(payload):
        return False
    if "data" in payload and payload["data"] not in (None, False, ""):
        return True
    if payload.get("code") in (0, "0"):
        return True
    return bool(payload.get("time"))


def pause(seconds: float, dry_run: bool) -> None:
    if not dry_run and seconds > 0:
        time.sleep(seconds)


def run_live_account(index: int, config: Config) -> AccountResult:
    result = AccountResult(index=index)
    client = NgaClient(config.uids[index - 1], config.tokens[index - 1], config.user_agent, config.timeout)
    print(f"账号{index}: 开始执行（凭据已隐藏）")
    try:
        checkin = client.request("check_in", "check_in")
    except ApiError as exc:
        result.add("签到", False, str(exc))
        return result

    message = error_text(checkin)
    already_done = "已经签到" in message or "今天已经签到了" in message
    checked_in = isinstance(checkin.get("data"), list) and bool(checkin["data"])
    if checked_in:
        result.add("签到", True, "成功")
    elif already_done:
        result.add("签到", True, "今日已签到")
    else:
        result.add("签到", False, "服务端未确认成功")
        return result

    def perform(action: str, lib: str, act: str, extra: Optional[dict[str, str]] = None) -> bool:
        try:
            payload = client.request(lib, act, extra)
            ok = explicit_success(payload)
            result.add(action, ok, "成功" if ok else "服务端未确认成功")
            return ok
        except ApiError as exc:
            result.add(action, False, str(exc))
            return False

    if config.daily_missions:
        for mission_id in ("2", "131", "30"):
            perform(
                f"日常任务{mission_id}",
                "mission",
                "checkin_count_add",
                {"mid": mission_id, "get_success_repeat": "1", "no_compatible_fix": "1"},
            )
            pause(config.action_delay, False)

    if config.video_missions:
        perform("免广告任务初始化", "mission", "video_view_task_counter_add_v2_for_adfree_sp1")
        for number in range(1, 5):
            pause(config.video_delay, False)
            perform(f"免广告任务{number}/4", "mission", "video_view_task_counter_add_v2_for_adfree")
        for number in range(1, 6):
            pause(config.video_delay, False)
            perform(f"N币视频任务{number}/5", "mission", "video_view_task_counter_add_v2")

    if config.share_missions:
        topic_id = str(random.SystemRandom().randint(12345678, 24692245))
        for number in range(1, 6):
            perform(
                f"分享记录{number}/5",
                "data_query",
                "topic_share_log_v2",
                {"event": "4", "tid": topic_id},
            )
            pause(config.action_delay, False)
        perform(
            "分享奖励",
            "mission",
            "check_mission",
            {"mid": "149", "get_success_repeat": "1", "no_compatible_fix": "1"},
        )

    if config.query_stats:
        try:
            stats = client.request("check_in", "get_stat")
            data = stats.get("data")
            ok = isinstance(data, list) and len(data) >= 3 and all(isinstance(item, dict) for item in data[:3])
            result.add("资产查询", ok, "成功" if ok else "响应结构未确认")
        except ApiError as exc:
            result.add("资产查询", False, str(exc))
    return result


def dry_run_account(index: int, config: Config) -> AccountResult:
    actions = ["签到"]
    if config.daily_missions:
        actions.extend(["日常任务2", "日常任务131", "日常任务30"])
    if config.video_missions:
        actions.extend(["免广告任务初始化", "免广告任务×4", "N币视频任务×5"])
    if config.share_missions:
        actions.extend(["分享记录×5", "分享奖励"])
    if config.query_stats:
        actions.append("资产查询")
    print(f"账号{index}: DRY-RUN，凭据格式已验证，未发起网络请求")
    print(f"账号{index}: 计划动作: {', '.join(actions)}")
    result = AccountResult(index=index)
    result.add("预演", True, "配置有效且无网络请求")
    return result


def notification_enabled() -> bool:
    return os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in DISABLED_VALUES


def load_notify_send() -> Optional[Callable[[str, str], Any]]:
    try:
        module = importlib.import_module("notify")
        candidate = getattr(module, "send", None)
        if callable(candidate):
            return candidate
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
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            candidate = getattr(module, "send", None)
            if callable(candidate):
                return candidate
        except Exception:
            continue
    return None


def notify(summary: str) -> None:
    if not notification_enabled():
        print("通知: 已由 QINGLONG_NOTIFY 关闭")
        return
    sender = load_notify_send()
    if sender is None:
        print("通知: 未找到可用的 notify.py，业务退出码不变")
        return
    try:
        sender(TITLE, summary)
        print("通知: 已提交脱敏汇总")
    except Exception:
        print("通知: 发送失败，业务退出码不变")


def make_summary(results: list[AccountResult], dry_run: bool) -> str:
    total = len(results)
    succeeded = sum(item.success for item in results)
    failed = total - succeeded
    state = "预演" if dry_run else ("成功" if failed == 0 else "部分失败" if succeeded else "失败")
    lines = [f"NGA论坛签到{state}", f"账号总数: {total}", f"成功数: {succeeded}", f"失败数: {failed}"]
    for item in results:
        status = "成功" if item.success else "失败"
        lines.append(f"账号{item.index}: {status}；" + "；".join(item.outcomes))
    return "\n".join(lines)


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        summary = f"NGA论坛签到配置错误\n账号总数: 0\n成功数: 0\n失败数: 0\n原因: {exc}"
        print(summary)
        notify(summary)
        return 2

    if config.dry_run:
        results = [dry_run_account(index, config) for index in range(1, len(config.uids) + 1)]
    else:
        if config.random_delay_max:
            delay = random.SystemRandom().randint(0, config.random_delay_max)
            print(f"执行前随机延迟: {delay} 秒")
            pause(delay, False)
        results = []
        for index in range(1, len(config.uids) + 1):
            results.append(run_live_account(index, config))

    summary = make_summary(results, config.dry_run)
    print(summary)
    notify(summary)
    return 0 if all(item.success for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
