#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: PassNAT 签到
# cron: 13 1 * * *
# SPDX-License-Identifier: MIT
"""PassNAT daily check-in task for Qinglong.

Environment:
  PASSNAT_SK       Required. One Authorization value per non-empty line.
  PASSNAT_DRY_RUN  Set to 1/true/yes/on for a fully offline rehearsal.
  RANDOM_SIGNIN    Optional; enable random staggering (default: false).
  MAX_RANDOM_DELAY Optional maximum delay in seconds (default: 0).
  QINGLONG_NOTIFY  Set to 0/false/no/off to disable Qinglong notification.

Maintained from ``passnat_checkin.py`` in agluo/ql-script-hub, commit
a8d39b97cb22c3ac657089014df754342b456ff6. The upstream project is MIT
licensed. Copyright remains with the upstream contributors.
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
        _ql_notify_identities = ('7e0ea7b66d8114d3', 'scripts/passnat_checkin.py', 'passnat_checkin.py', 'passnat_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import importlib
import importlib.util
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.passnat.com"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 1024 * 1024
SUCCESS_CODE = 10000
ALREADY_CHECKED_IN_CODE = 6001
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def parse_nonnegative_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是非负整数") from exc
    if value < 0:
        raise ValueError(f"{name} 必须是非负整数")
    return value


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分{secs}秒"
    if minutes:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def bytes_to_readable(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "未知"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(number) < 1024.0:
            return f"{number:.2f} {unit}"
        number /= 1024.0
    return f"{number:.2f} PB"


def safe_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def api_get(path: str, secret_key: str) -> dict[str, Any]:
    """Perform a bounded PassNAT request without logging credentials or bodies."""
    request = Request(
        f"{BASE_URL}{path}",
        headers={
            "Authorization": secret_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                return {"_error": f"HTTP 状态异常 ({status})"}
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        return {"_error": f"HTTP 状态异常 ({exc.code})"}
    except (URLError, TimeoutError, OSError):
        return {"_error": "网络请求失败或超时"}

    if len(payload) > MAX_RESPONSE_BYTES:
        return {"_error": "响应体超过安全限制"}
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"_error": "服务返回了无效 JSON"}
    if not isinstance(parsed, dict):
        return {"_error": "服务返回的数据结构无效"}
    return parsed


def wait_with_progress(seconds: int, label: str) -> None:
    if seconds <= 0:
        return
    print(f"[{label}] 随机延迟 {format_duration(seconds)}")
    remaining = seconds
    while remaining > 0:
        sleep_for = min(10, remaining)
        time.sleep(sleep_for)
        remaining -= sleep_for
        if remaining <= 10 or remaining % 30 == 0:
            print(f"[{label}] 剩余 {format_duration(remaining)}")


def display_user_info(label: str, data: Any) -> None:
    if not isinstance(data, dict):
        print(f"[{label}] 用户信息结构无效")
        return
    personal = data.get("personal_info")
    plan = data.get("plan_info")
    personal = personal if isinstance(personal, dict) else {}
    plan = plan if isinstance(plan, dict) else {}
    region = personal.get("last_login_region")
    region = region if isinstance(region, dict) else {}
    total = safe_number(plan.get("plan_traffic")) + safe_number(plan.get("addon_traffic"))
    remaining = total - safe_number(plan.get("used_traffic"))

    print(f"[{label}] 套餐: {plan.get('plan_name', 'N/A')}")
    print(
        f"[{label}] 流量: 总计 {bytes_to_readable(total)}，"
        f"已用 {bytes_to_readable(plan.get('used_traffic'))}，"
        f"剩余 {bytes_to_readable(remaining)}"
    )
    print(
        f"[{label}] 签到流量 {bytes_to_readable(plan.get('check_in_traffic'))}，"
        f"隧道 {plan.get('tunnel_count', 0)}/{plan.get('tunnel_limit', 0)}"
    )
    location = "/".join(
        str(region.get(key)) for key in ("country", "province", "city") if region.get(key)
    )
    if location:
        print(f"[{label}] 最近登录地区: {location}")
    if region.get("ISP"):
        print(f"[{label}] 运营商: {region['ISP']}")
    if region.get("IP"):
        print(f"[{label}] 最近登录 IP: {region['IP']}")
    status = {1: "正常", 0: "已过期"}.get(plan.get("plan_status"))
    if status:
        print(f"[{label}] 套餐状态: {status}")
    expiry = plan.get("expire_date")
    if isinstance(expiry, (int, float)) and expiry > 0:
        try:
            when = datetime.fromtimestamp(expiry / 1000).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{label}] 到期时间: {when}")
        except (OverflowError, OSError, ValueError):
            pass


def run_account(index: int, secret_key: str, dry_run: bool) -> tuple[bool, str]:
    label = f"账号{index}"
    if dry_run:
        print(f"[{label}] DRY-RUN PASS：凭据已配置；将执行签到并查询套餐（未发起网络请求）")
        return True, "预演通过"

    checkin = api_get("/user/checkIn", secret_key)
    if "_error" in checkin:
        print(f"[{label}] 签到失败：{checkin['_error']}")
        return False, "签到请求失败"
    code = checkin.get("code")
    if code == SUCCESS_CODE:
        print(f"[{label}] 签到成功，获得流量 {bytes_to_readable(checkin.get('data'))}")
    elif code == ALREADY_CHECKED_IN_CODE:
        print(f"[{label}] 今日已签到")
    else:
        print(f"[{label}] 签到失败：业务码 {code!r}")
        return False, "签到业务校验失败"

    user_info = api_get("/user/userInfo", secret_key)
    if "_error" in user_info:
        print(f"[{label}] 用户信息查询失败：{user_info['_error']}")
        return False, "用户信息请求失败"
    if user_info.get("code") != SUCCESS_CODE:
        print(f"[{label}] 用户信息查询失败：业务码 {user_info.get('code')!r}")
        return False, "用户信息业务校验失败"
    display_user_info(label, user_info.get("data"))
    return True, "签到及用户信息校验成功"


def load_notifier() -> Optional[Callable[[str, str], Any]]:
    try:
        module = importlib.import_module("notify")
        candidate = getattr(module, "send", None)
        if callable(candidate):
            return candidate
    except Exception:
        pass

    candidates: list[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        candidates.append(Path(notify_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", path)
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


def notify_summary(total: int, succeeded: int, failed: int, dry_run: bool, config_error: bool) -> None:
    state = "配置错误" if config_error else ("预演" if dry_run else ("成功" if failed == 0 else "部分失败" if succeeded else "失败"))
    body = f"状态：{state}\n账号总数：{total}\n成功数：{succeeded}\n失败数：{failed}"
    print(f"任务汇总：状态={state}，账号总数={total}，成功数={succeeded}，失败数={failed}")

    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in FALSE_VALUES:
        print("通知已由 QINGLONG_NOTIFY 关闭")
        return
    if dry_run:
        print("预演通知摘要已生成；为保证完全断网，未调用外部通知模块")
        return
    notifier = load_notifier()
    if notifier is None:
        print("未找到 Qinglong notify.py；任务退出码不受影响")
        return
    try:
        notifier("PassNAT 签到", body)
        print("Qinglong 通知已发送")
    except Exception:
        print("Qinglong 通知发送失败；任务退出码不受影响")


def main() -> int:
    dry_run = env_enabled("PASSNAT_DRY_RUN")
    raw_accounts = os.getenv("PASSNAT_SK", "")
    accounts = [line.strip() for line in raw_accounts.replace("\r\n", "\n").split("\n") if line.strip()]
    if not accounts:
        print("配置错误：请设置 PASSNAT_SK，每个账号占一个非空行")
        notify_summary(0, 0, 0, dry_run, config_error=True)
        return 2

    try:
        max_delay = parse_nonnegative_int("MAX_RANDOM_DELAY", 0)
    except ValueError as exc:
        print(f"配置错误：{exc}")
        notify_summary(len(accounts), 0, len(accounts), dry_run, config_error=True)
        return 2
    random_signin = env_enabled("RANDOM_SIGNIN") and max_delay > 0 and not dry_run

    print(f"PassNAT 签到：共 {len(accounts)} 个账号；随机延迟={'开启' if random_signin else '关闭'}")
    plan = [(index, key, random.randint(0, max_delay) if random_signin else 0) for index, key in enumerate(accounts, 1)]
    plan.sort(key=lambda item: item[2])

    succeeded = 0
    failed = 0
    previous_delay = 0
    for index, key, delay in plan:
        # Delays are offsets within one shared window, not cumulative sleeps.
        wait_with_progress(max(0, delay - previous_delay), f"账号{index}")
        previous_delay = delay
        ok, _ = run_account(index, key, dry_run)
        if ok:
            succeeded += 1
        else:
            failed += 1

    notify_summary(len(accounts), succeeded, failed, dry_run, config_error=False)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
