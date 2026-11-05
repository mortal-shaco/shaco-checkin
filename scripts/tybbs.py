#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: V次元论坛签到
# cron: 30 6 * * *
#
# SPDX-License-Identifier: MIT
# Source: Takeoff0518/tybbs-checkin checkin.py
# Upstream commit: d9001e58f6c753086c9b095826181b78e5083520
# Catalog ID: 0d4996a9f8a038f6
# License: MIT
# Copyright (c) 2023 RainSpark
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""V次元（bbs.66ccff.cc）每日签到独立维护版。

环境变量：
  TYBBS_COOKIE     必填。每个非空行一个账号的完整 Cookie（请求头值，不含 Cookie: 前缀）。
                   浏览器登录 https://bbs.66ccff.cc 后，在开发者工具网络面板复制同站已登录
                   请求的 Cookie；通常需含 wordpress_logged_in_* / wordpress_sec_* 等登录字段。
                   Cookie 内的 &、@、; 不会用于分割账号。
  BBS_COOKIE       可选。上游兼容别名；仅当 TYBBS_COOKIE 为空时使用，格式相同。
  TYBBS_DRY_RUN    设为 1/true/yes/on 时完全断网预演，只校验配置不发起业务请求。
  QINGLONG_NOTIFY  青龙通知开关；未设置时按 QINGLONG_NOTIFY_SCRIPTS 名单策略。
  QINGLONG_NOTIFY_DIR  可选，notify.py / sendNotify.js 所在目录。

上游调度为每天 06:30（CST，对应 Actions cron 30 22 * * * UTC）。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "0d4996a9f8a038f6",
            "scripts/tybbs_checkin.py",
            "tybbs_checkin.py",
            "tybbs_checkin",
            "candidate.py",
        )
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
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CATALOG_ID = "0d4996a9f8a038f6"
TITLE = "V次元论坛签到"
BASE_URL = "https://bbs.66ccff.cc"
CHECKIN_URL = f"{BASE_URL}/wp-admin/ajax.php"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 262144
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 "
    "Safari/537.36 Edg/118.0.2088.76"
)
ICON = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
ALREADY_MARKERS = (
    "今日已签到",
    "今天已经签到",
    "今天已签到",
    "已经签到",
    "已签过到",
    "重复签到",
)
SUCCESS_MARKERS = (
    "签到成功",
    "签到完成",
    "打卡成功",
)


class RequestFailure(Exception):
    """可安全展示的 HTTP / 响应错误。"""


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock()}] {message}", flush=True)


def env_flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default)
    if raw is None:
        raw = default
    value = raw.strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    raise ValueError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")


def load_accounts() -> list[str]:
    raw = os.environ.get("TYBBS_COOKIE", "").strip()
    if not raw:
        raw = os.environ.get("BBS_COOKIE", "").strip()
    text = raw.replace("\r\n", "\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def validate_cookie(cookie: str) -> None:
    if not cookie:
        raise ValueError("Cookie 为空")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie):
        raise ValueError("Cookie 包含控制字符")
    if "=" not in cookie:
        raise ValueError("Cookie 至少应包含 name=value 字段")


def build_headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": cookie,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }


def http_post_form(url: str, *, cookie: str, form: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=build_headers(cookie),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
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
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequestFailure("响应编码无效") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RequestFailure("服务器返回了无效 JSON") from exc
    if not isinstance(payload, dict):
        raise RequestFailure("服务器响应结构不正确")
    return payload


def safe_message(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) > 120:
        text = text[:117] + "..."
    return text


def extract_identity(payload: dict[str, Any]) -> str | None:
    containers: list[dict[str, Any]] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        containers.append(data)
        user = data.get("user")
        if isinstance(user, dict):
            containers.append(user)
    user_root = payload.get("user")
    if isinstance(user_root, dict):
        containers.append(user_root)
    for container in containers:
        for key in (
            "display_name",
            "displayName",
            "nickname",
            "nick_name",
            "user_nicename",
            "username",
            "user_name",
            "name",
            "uid",
            "user_id",
            "id",
        ):
            value = container.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                text = str(value).strip()
                if len(text) > 64:
                    continue
                if any(token in text.lower() for token in ("cookie", "token", "wordpress_", "password")):
                    continue
                return text
    return None


def classify_checkin(payload: dict[str, Any]) -> tuple[str, str]:
    msg = safe_message(payload.get("msg") or payload.get("message") or payload.get("info"))
    error = payload.get("error")
    code = payload.get("code")
    success_flag = payload.get("success")

    if any(marker in msg for marker in ALREADY_MARKERS):
        return "already", "今日已签到（官方响应确认）"
    if error in (0, "0", False) or code in (0, "0", 200, "200") or success_flag in (True, 1, "1"):
        if msg and any(marker in msg for marker in SUCCESS_MARKERS):
            return "success", f"签到成功（官方响应确认）：{msg}"
        if msg and any(bad in msg for bad in ("失败", "未登录", "请先登录", "登录过期", "无效")):
            return "failed", "签到未获得明确成功确认；请核对登录状态或接口，响应已隐藏"
        if msg:
            return "success", f"签到成功（官方响应确认）：{msg}"
        return "success", "签到成功（官方响应确认）"
    if any(marker in msg for marker in SUCCESS_MARKERS) and not any(
        bad in msg for bad in ("失败", "未", "不能", "无法")
    ):
        return "success", f"签到成功（官方响应确认）：{msg}"
    return "failed", "签到未获得明确成功确认；请核对登录状态或接口，响应已隐藏"


def check_in(cookie: str) -> tuple[str, str, str | None]:
    payload = http_post_form(CHECKIN_URL, cookie=cookie, form={"action": "user_checkin"})
    identity = extract_identity(payload)
    status, detail = classify_checkin(payload)
    return status, detail, identity


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

    try:
        dry = env_flag("TYBBS_DRY_RUN", "0")
        env_flag("QINGLONG_NOTIFY", os.environ.get("QINGLONG_NOTIFY", "1"))
        accounts = load_accounts()
        if not accounts:
            raise ValueError(
                "请配置 TYBBS_COOKIE（或兼容别名 BBS_COOKIE），每个非空行一个完整 Cookie"
            )
        for cookie in accounts:
            validate_cookie(cookie)
    except ValueError as exc:
        log(f"{ICON['failure']} 配置错误：" + str(exc))
        config_error = True

    log(f"运行模式：{'断网预演' if dry else '正式执行'}；账号总数：{len(accounts)}")

    if not config_error:
        for index, cookie in enumerate(accounts, 1):
            account_start = time.monotonic()
            log(f"----- 账号 {index} -----")
            stage_start = time.monotonic()
            step_status = "failed"
            detail = ""
            identity: str | None = None
            try:
                if dry:
                    validate_cookie(cookie)
                    step_status = "skipped"
                    detail = "DRY_RUN_OK 参数已解析，未发送请求，未产生业务成功记录"
                    log(f"阶段 1 签到：{ICON['skipped']} {detail}")
                else:
                    step_status, detail, identity = check_in(cookie)
                    icon = ICON.get(
                        "alreadyComplete" if step_status == "already" else step_status,
                        ICON["failure"],
                    )
                    if identity:
                        log(f"官方账号身份：{identity}")
                    log(f"阶段 1 签到：{icon} {detail}")
            except RequestFailure as exc:
                step_status = "failed"
                detail = str(exc)
                log(f"阶段 1 签到：{ICON['failure']} {detail}；响应已隐藏")
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
                "identity": identity or f"账号{index}",
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
