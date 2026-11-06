#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: EOP官网签到
# cron: 11 9 * * *
#
# 来源：mcAmiya/eop_checkin main.py + app_config.py（GPL-3.0）
# https://github.com/mcAmiya/eop_checkin
# 提交：8f038848502e6df8fe13144f800282d0a1948dd8
# SPDX-License-Identifier: GPL-3.0-only
#
# 本维护版沿用上游 GPL-3.0 许可。Copyright (C) mcAmiya / eop_checkin contributors。
# 你可以通过自由软件基金会发布的 GNU 通用公共许可证第 3 版（或你选择的任何后续版本）
# 重新分发和/或修改本程序。本程序的分发希望它有用，但不提供任何担保。
# 完整许可证文本见上游仓库 LICENSE。
#
"""Everyone Piano（EOP）官网每日签到 - 青龙维护版。

功能清点（相对上游 main.py + app_config.py）：
- 使用已登录 Cookie 向 https://www.everyonepiano.cn/Myspace/SigninClick POST 签到
- 识别官方明文响应：success（成功）、纯数字（成功且连续签到天数）、already（今日已签到）
- 移除硬编码 Pushplus、占位凭据、无超时 requests 与原始响应打印
- 统一 EOP_COOKIE 每行一个账号；兼容上游配置名 EOP_cookie（仅当规范变量为空时）
- 增加 EOP_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY
- related push/ 仅为推送库，非账号任务，不以 Pushplus 替代青龙通知

EOP_COOKIE：每个非空行一个完整 Cookie（请求头值，不含 Cookie: 前缀）。
EOP_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
EOP_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 9 * * *。不打印 Cookie、Token、会话值或原始响应。
"""

from __future__ import annotations

# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('42ad8ed62f74a64a', 'scripts/eop.py', 'eop.py', 'eop')
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
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CATALOG_ID = "42ad8ed62f74a64a"
TITLE = "EOP官网签到"
BASE_URL = "https://www.everyonepiano.cn"
CHECKIN_URL = f"{BASE_URL}/Myspace/SigninClick"
DEFAULT_TIMEOUT = 15
MAX_RESPONSE_BYTES = 65536
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
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


class SafeError(Exception):
    """可安全展示的配置或业务错误。"""


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock()}] {message}", flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default)
    if raw is None:
        raw = default
    value = str(raw).strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    raise SafeError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")


def resolve_timeout() -> float:
    raw = env("EOP_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("EOP_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("EOP_TIMEOUT 须在 5 到 60 秒之间")
    return value


def load_accounts() -> list[str]:
    raw = env("EOP_COOKIE")
    if not raw:
        raw = env("EOP_cookie")
    text = raw.replace("\r\n", "\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def validate_cookie(cookie: str) -> None:
    if not cookie:
        raise SafeError("Cookie 为空")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie):
        raise SafeError("Cookie 包含控制字符")
    if "=" not in cookie:
        raise SafeError("Cookie 至少应包含 name=value 字段")
    if "<这里填写" in cookie:
        raise SafeError("检测到上游占位凭据，请填写真实 Cookie")


def build_headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/Myspace",
        "User-Agent": USER_AGENT,
    }


def http_post_checkin(cookie: str, timeout: float) -> str:
    request = urllib.request.Request(
        CHECKIN_URL,
        data=b"",
        headers=build_headers(cookie),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise RequestFailure("响应过大")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RequestFailure(f"HTTP 状态码 {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RequestFailure("网络请求失败或超时") from exc
    if status < 200 or status >= 300:
        raise RequestFailure(f"HTTP 状态码 {status}")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RequestFailure("响应过大")
    try:
        text = raw.decode("utf-8", errors="replace").strip()
    except Exception as exc:
        raise RequestFailure("响应编码无效") from exc
    return text


def classify_checkin(body: str) -> tuple[str, str]:
    """按上游明文业务码判定：success / 数字天数 / already。"""
    text = " ".join(body.split())
    if text == "success":
        return "success", "签到成功（官方响应确认）"
    if text.isdigit():
        days = int(text)
        return "success", f"签到成功（官方响应确认）连续签到第{days}天"
    if text == "already":
        return "already", "今日已签到（官方响应确认）"
    if not text:
        return "failed", "签到未获得明确成功确认；响应为空"
    # 不回显原始正文，避免泄漏会话或页面片段
    return "failed", "签到未获得明确成功确认；请核对登录状态或接口，响应已隐藏"


def check_in(cookie: str, timeout: float) -> tuple[str, str]:
    body = http_post_checkin(cookie, timeout)
    return classify_checkin(body)


def notify_enabled() -> bool:
    value = os.environ.get("QINGLONG_NOTIFY", "1").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES or value in {"auto", ""}:
        return True
    return True


def send_notification(body: str, *, dry_run: bool) -> str:
    try:
        if not notify_enabled():
            return "已关闭"
        if dry_run:
            log("预演通知摘要：" + body)
            return "预演摘要已生成，断网模式不外发"
        module = None
        try:
            module = importlib.import_module("notify")
        except ImportError:
            candidates: list[Path] = []
            directory = os.environ.get("QINGLONG_NOTIFY_DIR")
            if directory:
                candidates.append(Path(directory) / "notify.py")
            candidates += [
                Path("/ql/data/scripts/notify.py"),
                Path("/ql/scripts/notify.py"),
            ]
            for path in candidates:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        break
        if module is None or not callable(getattr(module, "send", None)):
            return "通知组件不可用，保留业务退出码"
        module.send(TITLE, body)
        return "通知已发送"
    except Exception:
        return "通知失败，保留业务退出码（异常内容已隐藏）"


def main() -> int:
    began = time.monotonic()
    start_time = datetime.now().astimezone().isoformat(timespec="seconds")
    log("========== " + TITLE + " ==========")
    log("开始时间：" + start_time)
    log(f"目录编号：{CATALOG_ID}")

    accounts: list[str] = []
    results: list[dict[str, Any]] = []
    config_error = False
    dry = False
    timeout = float(DEFAULT_TIMEOUT)

    try:
        dry = env_flag("EOP_DRY_RUN", "0")
        env_flag("QINGLONG_NOTIFY", os.environ.get("QINGLONG_NOTIFY", "1"))
        timeout = resolve_timeout()
        accounts = load_accounts()
        if not accounts:
            raise SafeError(
                "请配置 EOP_COOKIE（或兼容别名 EOP_cookie），每个非空行一个完整 Cookie"
            )
        for cookie in accounts:
            validate_cookie(cookie)
    except SafeError as exc:
        log(f"{ICON['failure']} 配置错误：" + str(exc))
        config_error = True
    except ValueError as exc:
        log(f"{ICON['failure']} 配置错误：" + str(exc))
        config_error = True

    log(f"运行模式：{'断网预演' if dry else '正式执行'}；账号总数：{len(accounts)}")
    if not dry and not config_error:
        log(f"请求超时：{timeout:g} 秒；签到地址：{CHECKIN_URL}")

    if not config_error:
        for index, cookie in enumerate(accounts, 1):
            account_start = time.monotonic()
            log(f"----- 账号 {index} -----")
            stage_start = time.monotonic()
            step_status = "failed"
            detail = ""
            try:
                if dry:
                    validate_cookie(cookie)
                    step_status = "skipped"
                    detail = "DRY_RUN_OK 参数已解析，未发送请求，未产生业务成功记录"
                    log(f"阶段 1 签到：{ICON['skipped']} {detail}")
                else:
                    step_status, detail = check_in(cookie, timeout)
                    icon = ICON.get(
                        "alreadyComplete" if step_status == "already" else step_status,
                        ICON["failure"],
                    )
                    log(f"阶段 1 签到：{icon} {detail}")
            except RequestFailure as exc:
                step_status = "failed"
                detail = str(exc)
                log(f"阶段 1 签到：{ICON['failure']} {detail}；响应已隐藏")
            except SafeError as exc:
                step_status = "failed"
                detail = str(exc)
                log(f"阶段 1 签到：{ICON['failure']} {detail}")
            except Exception:
                step_status = "failed"
                detail = "凭据格式错误或请求失败；详情已隐藏"
                log(f"阶段 1 签到：{ICON['failure']} {detail}")
            log(f"阶段 1 耗时 {time.monotonic() - stage_start:.2f} 秒")

            stats = {
                "success": 1 if step_status == "success" else 0,
                "already": 1 if step_status == "already" else 0,
                "skipped": 1 if step_status == "skipped" else 0,
                "failed": 1 if step_status == "failed" else 0,
            }
            account_ok = stats["failed"] == 0
            result = {
                "account": index,
                "ok": account_ok,
                "identity": f"账号{index}",
                "tasks": 1,
                **stats,
                "elapsedSeconds": round(time.monotonic() - account_start, 2),
                "detail": detail,
            }
            results.append(result)
            log(
                f"账号 {index} 统计：总任务 1，成功 {stats['success']}，"
                f"已完成 {stats['already']}，跳过 {stats['skipped']}，"
                f"失败 {stats['failed']}，耗时 {result['elapsedSeconds']} 秒"
            )

    failed = sum(1 for item in results if not item["ok"])
    passed = sum(1 for item in results if item["ok"])
    ok = not config_error and failed == 0 and (bool(results) or dry)
    if config_error:
        status = "configuration-error"
    elif dry and ok:
        status = "dry-run"
    elif ok:
        status = "success"
    elif failed and passed:
        status = "partial-failure"
    else:
        status = "failure"

    summary = (
        f"账号总数 {len(accounts)}，"
        f"{'预演通过' if dry else '成功'} {passed}，失败 {failed}；状态 {status}"
    )
    notification = send_notification(summary, dry_run=dry)

    log("----------------------------------------")
    log(summary)
    totals = {
        key: sum(item[key] for item in results)
        for key in ("tasks", "success", "already", "skipped", "failed")
    }
    log(
        "子任务统计：总数 {tasks}，成功 {success}，已完成 {already}，"
        "跳过 {skipped}，失败 {failed}".format(**totals)
    )
    log("通知状态：" + notification)
    finish = datetime.now().astimezone().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - began, 2)
    log(f"完成时间：{finish}；总耗时 {elapsed} 秒；最终状态：{status}")
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "status": status,
                "dryRun": dry,
                "accountCount": len(accounts),
                "passedAccounts": passed,
                "failedAccounts": failed,
                "configurationError": config_error,
                "accounts": results,
                "taskStatistics": totals,
                "notification": notification,
                "startTime": start_time,
                "finishTime": finish,
                "elapsedSeconds": elapsed,
                "catalogId": CATALOG_ID,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
