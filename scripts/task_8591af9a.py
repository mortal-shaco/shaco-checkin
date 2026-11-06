#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 棕色尘埃2网页商店签到
# cron: 29 9 * * *
#
# 来源：XiaoYiWeio/brown-dust-2 scripts/signin.py（MIT）
# https://github.com/XiaoYiWeio/brown-dust-2
# 提交：010a7f1f82ea224a70c14700443ba4768b62476b
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2026 XiaoYiWeio
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
"""棕色尘埃 2（Brown Dust 2）Web Shop 签到（青龙独立维护版）。

功能清点（相对上游 scripts/signin.py）：
- 每日出席签到（type=0）
- 每周出席签到（type=1）
- 活动出席签到（查询活动 → 用户状态 → attend-reward）
- 去掉本地 .token 落盘、--save-token、命令行明文 token 与未脱敏 JSON 原始响应
- 多账号：BD2_ACCESS_TOKEN 每行一个 accessToken；兼容别名 BD2_TOKEN
- BD2_DRY_RUN=1 完全断网预演；可选 BD2_SKIP_EVENT / BD2_DAILY_ONLY
- 时间轴脱敏日志、青龙通知、TASK_SUMMARY；任一账号失败整体非零退出
- 同仓库兑换码脚本（redeem.py）凭据与副作用边界不同，保持独立任务

建议 Cron：15 9 * * *
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
        _ql_notify_identities = ('8591af9ab9d3293b', 'scripts/task_8591af9a.py', 'task_8591af9a.py', 'task_8591af9a')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import importlib.util
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "8591af9ab9d3293b"
SCRIPT_NAME = "棕色尘埃2网页商店签到"
SCRIPT_FILENAME = "candidate.py"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    SCRIPT_FILENAME,
    "output/candidate.py",
    "bd2_webshop_signin.py",
    "scripts/bd2_webshop_signin.py",
    "signin.py",
    SCRIPT_NAME,
)

TOKEN_ENV = "BD2_ACCESS_TOKEN"
TOKEN_ALIAS_ENV = "BD2_TOKEN"
DRY_RUN_ENV = "BD2_DRY_RUN"
TIMEOUT_ENV = "BD2_TIMEOUT"
SKIP_EVENT_ENV = "BD2_SKIP_EVENT"
DAILY_ONLY_ENV = "BD2_DAILY_ONLY"
ACCOUNT_DELAY_ENV = "BD2_ACCOUNT_DELAY_SEC"

API_BASE = "https://bd2-webshop-api.bd2.pmang.cloud"
API_HOST = "bd2-webshop-api.bd2.pmang.cloud"
ATTEND_DAILY = 0
ATTEND_WEEKLY = 1
DEFAULT_TIMEOUT = 15
MAX_RESPONSE_BYTES = 512 * 1024
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

STATUS_ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


def _now() -> datetime:
    return datetime.now().astimezone()


def _clock() -> str:
    return _now().strftime("%H:%M:%S")


def _full_ts() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str = "") -> None:
    if msg:
        print(f"[{_clock()}] {msg}", flush=True)
    else:
        print(flush=True)


def env_raw(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def compact(text: Any, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)] + "…"


def int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env_raw(name).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{name} 须为整数") from exc
    if value < minimum or value > maximum:
        raise SafeError(f"{name} 须在 {minimum} 到 {maximum} 之间")
    return value


def parse_accounts(raw: str) -> List[str]:
    """每个非空行一个 accessToken；账号之间只用换行分隔。"""
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.lower().startswith("bearer "):
            text = text[7:].strip()
        if any(ord(ch) < 32 for ch in text):
            raise SafeError(f"第 {line_no} 行凭据含非法控制字符")
        if len(text) < 16:
            raise SafeError(f"第 {line_no} 行 accessToken 过短，疑似无效")
        accounts.append(text)
    return accounts


def load_token_raw() -> str:
    primary = env_raw(TOKEN_ENV)
    if primary.strip():
        return primary
    alias = env_raw(TOKEN_ALIAS_ENV)
    if alias.strip():
        return alias
    return ""


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def identity_label(index: int, token: str) -> str:
    data = decode_jwt_payload(token) or {}
    for key in (
        "nickname",
        "nickName",
        "displayName",
        "username",
        "userName",
        "name",
        "preferred_username",
    ):
        value = str(data.get(key) or "").strip()
        if value and not _looks_like_secret(value):
            return value
    for key in ("uid", "userId", "user_id", "sub", "id"):
        value = str(data.get(key) or "").strip()
        if value and not _looks_like_secret(value) and len(value) <= 64:
            return f"UID:{value}"
    return f"账号{index}"


def _looks_like_secret(value: str) -> bool:
    lower = value.lower()
    if lower.startswith("eyj"):
        return True
    if "bearer " in lower:
        return True
    if len(value) > 80 and re.search(r"[A-Za-z0-9+/=_-]{40,}", value):
        return True
    return False


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def _notify_global_mode() -> str:
    raw = env_raw("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in TRUE_VALUES:
        return "enabled"
    if raw in FALSE_VALUES:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if raw is None:
        return None
    if raw.strip() == "":
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _selector_match(selector: str) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if sel == "*":
        return True
    candidates = {c.lower() for c in SCRIPT_IDENTITIES}
    sel_l = sel.lower()
    if sel_l in candidates:
        return True
    for identity in SCRIPT_IDENTITIES:
        if _ql_notify_fnmatch.fnmatch(identity.lower(), sel_l):
            return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    if mode == "enabled":
        return True
    selectors = _script_selectors()
    if selectors is None:
        return True
    if not selectors:
        return False
    return any(_selector_match(s) for s in selectors)


def _load_notify_send():
    try:
        from notify import send as notify_send  # type: ignore

        return notify_send
    except Exception:
        pass
    candidates: List[str] = []
    custom = env_raw("QINGLONG_NOTIFY_DIR").strip()
    if custom:
        candidates.append(os.path.join(custom, "notify.py"))
    candidates.extend(
        [
            "/ql/data/scripts/notify.py",
            "/ql/scripts/notify.py",
        ]
    )
    for path in candidates:
        try:
            if not os.path.isfile(path):
                continue
            spec = importlib.util.spec_from_file_location("ql_notify_mod", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = getattr(module, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, content: str) -> str:
    if not _should_notify():
        return "skipped"
    send = _load_notify_send()
    if send is None:
        log(f"{STATUS_ICONS['warning']} 未找到可用 notify.py，跳过通知并保留业务退出码")
        return "unavailable"
    try:
        send(title, content)
        return "sent"
    except Exception:
        log(f"{STATUS_ICONS['warning']} 通知发送失败，已忽略并保留业务退出码")
        return "failed"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def http_json(
    method: str,
    path: str,
    token: Optional[str] = None,
    body: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Host": API_HOST,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SafeError("响应过大，已中止读取")
            text = raw.decode("utf-8", errors="replace")
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError as exc:
                raise SafeError(f"响应不是合法 JSON（HTTP {resp.status}）") from exc
            return {"ok": True, "status": int(resp.status), "json": payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1)
        text = raw[:MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = {"code": "FAIL", "message": f"HTTP {exc.code}"}
        return {"ok": False, "status": int(exc.code), "json": payload}
    except urllib.error.URLError as exc:
        raise SafeError(f"网络错误：{compact(getattr(exc, 'reason', exc))}") from exc
    except TimeoutError as exc:
        raise SafeError("请求超时") from exc


def extract_safe_error(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "业务失败"
    msg = str(payload.get("message") or "").strip()
    data = payload.get("data")
    err = ""
    if isinstance(data, dict):
        err = str(data.get("errorMsg") or "").strip()
    for candidate in (err, msg):
        if not candidate:
            continue
        if candidate.lower() in {"success", "ok"}:
            continue
        if "already" in candidate.lower():
            continue
        return compact(candidate, 120)
    code = payload.get("code")
    if code not in (None, "", 0, "0", "OK", "SUCCESS"):
        return compact(f"业务码 {code}", 120)
    return "业务失败"


def parse_attend(payload: Any) -> Tuple[str, str]:
    """返回 (status, message)；status in success|alreadyComplete|failure。"""
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, dict):
        return "failure", "响应结构异常"
    success = bool(data.get("success", False))
    error_type = data.get("errorType", 0)
    error_msg = str(data.get("errorMsg") or "")
    already = error_type == 3 or "Already attendance" in error_msg
    if success:
        return "success", "签到成功"
    if already:
        return "alreadyComplete", "今日或本周期已签到"
    # 顶层 Unauthorized / token 失效
    top_msg = ""
    if isinstance(payload, dict):
        top_msg = str(payload.get("message") or "")
    combined = f"{top_msg} {error_msg}".lower()
    if "unauthorized" in combined or "token" in combined and (
        "invalid" in combined or "expired" in combined or "过期" in combined
    ):
        return "failure", "Token 无效或已过期，请重新获取"
    return "failure", extract_safe_error(payload)


# ---------------------------------------------------------------------------
# account runners
# ---------------------------------------------------------------------------


def stage_log(
    index: int,
    name: str,
    status: str,
    detail: str,
    stats: Dict[str, int],
    messages: List[str],
) -> None:
    icon = STATUS_ICONS.get(status, STATUS_ICONS["warning"])
    log(f"  阶段{index} {name}: {icon} {detail}")
    if status == "success":
        stats["success"] += 1
    elif status == "alreadyComplete":
        stats["alreadyComplete"] += 1
    elif status == "skipped":
        stats["skipped"] += 1
    elif status == "failure":
        stats["failed"] += 1
    else:
        stats["skipped"] += 1
    messages.append(f"{name}:{status}")


def run_account_dry(
    index: int,
    total: int,
    token: str,
    skip_event: bool,
    daily_only: bool,
) -> Dict[str, Any]:
    identity = identity_label(index, token)
    started = time.monotonic()
    stats = {
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    messages: List[str] = []
    log(f"── 账号 {index}/{total}：{identity} ──")
    stage_log(1, "凭据检查", "success", "accessToken 格式通过（预演）", stats, messages)
    stage_log(2, "每日签到", "skipped", "dry-run 已跳过网络请求与签到副作用", stats, messages)
    if daily_only:
        stage_log(3, "每周签到", "skipped", "已启用仅每日签到", stats, messages)
        stage_log(4, "活动出席", "skipped", "已启用仅每日签到", stats, messages)
    else:
        stage_log(3, "每周签到", "skipped", "dry-run 已跳过网络请求与签到副作用", stats, messages)
        if skip_event:
            stage_log(4, "活动出席", "skipped", "已设置跳过活动出席", stats, messages)
        else:
            stage_log(4, "活动出席", "skipped", "dry-run 已跳过网络请求与签到副作用", stats, messages)
    elapsed = time.monotonic() - started
    log(
        f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
    )
    return {
        "ok": True,
        "identity": identity,
        "status": "dry-run",
        "message": "；".join(messages)[:240],
        "stats": stats,
    }


def run_account_live(
    index: int,
    total: int,
    token: str,
    timeout: float,
    skip_event: bool,
    daily_only: bool,
) -> Dict[str, Any]:
    identity = identity_label(index, token)
    started = time.monotonic()
    stats = {
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    messages: List[str] = []
    account_ok = True
    log(f"── 账号 {index}/{total}：{identity} ──")

    # 1) Daily
    stage_t0 = time.monotonic()
    try:
        resp = http_json(
            "POST",
            "/api/user/attend",
            token=token,
            body={"type": ATTEND_DAILY},
            timeout=timeout,
        )
        status, detail = parse_attend(resp.get("json"))
        if status == "failure" and resp.get("status") in (401, 403):
            status, detail = "failure", "Token 无效或已过期，请重新获取"
        if status == "failure":
            account_ok = False
        stage_log(
            1,
            "每日签到",
            status,
            f"{detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
            stats,
            messages,
        )
        if status == "failure" and "Token" in detail:
            elapsed = time.monotonic() - started
            log(
                f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
                f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
                f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
            )
            return {
                "ok": False,
                "identity": identity,
                "status": "failure",
                "message": detail,
                "stats": stats,
            }
    except SafeError as exc:
        account_ok = False
        stage_log(1, "每日签到", "failure", str(exc), stats, messages)
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": str(exc),
            "stats": stats,
        }

    if daily_only:
        stage_log(2, "每周签到", "skipped", "已启用仅每日签到", stats, messages)
        stage_log(3, "活动出席", "skipped", "已启用仅每日签到", stats, messages)
    else:
        time.sleep(0.5)
        # 2) Weekly
        stage_t0 = time.monotonic()
        try:
            resp = http_json(
                "POST",
                "/api/user/attend",
                token=token,
                body={"type": ATTEND_WEEKLY},
                timeout=timeout,
            )
            status, detail = parse_attend(resp.get("json"))
            if status == "failure":
                account_ok = False
            stage_log(
                2,
                "每周签到",
                status,
                f"{detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
                stats,
                messages,
            )
        except SafeError as exc:
            account_ok = False
            stage_log(2, "每周签到", "failure", str(exc), stats, messages)

        # 3) Event
        if skip_event:
            stage_log(3, "活动出席", "skipped", "已设置跳过活动出席", stats, messages)
        else:
            time.sleep(0.5)
            stage_t0 = time.monotonic()
            try:
                info_resp = http_json(
                    "GET",
                    "/api/event/event-info",
                    token=None,
                    body=None,
                    timeout=timeout,
                )
                info_payload = info_resp.get("json") if isinstance(info_resp, dict) else {}
                event_data = (
                    info_payload.get("data", {})
                    if isinstance(info_payload, dict)
                    else {}
                )
                if not isinstance(event_data, dict):
                    event_data = {}
                schedule = event_data.get("scheduleInfo", {})
                if not isinstance(schedule, dict):
                    schedule = {}
                schedule_id = int(schedule.get("eventScheduleId") or 0)
                if schedule_id <= 0:
                    stage_log(
                        3,
                        "活动出席",
                        "alreadyComplete",
                        f"当前没有进行中的出席活动（耗时 {time.monotonic() - stage_t0:.2f}秒）",
                        stats,
                        messages,
                    )
                else:
                    user_resp = http_json(
                        "POST",
                        "/api/event/event-user-info",
                        token=token,
                        body=None,
                        timeout=timeout,
                    )
                    user_payload = user_resp.get("json") if isinstance(user_resp, dict) else {}
                    user_event = (
                        user_payload.get("data", user_payload)
                        if isinstance(user_payload, dict)
                        else {}
                    )
                    if not isinstance(user_event, dict):
                        user_event = {}
                    count = user_event.get("attendanceCount", -1)
                    try:
                        count_num = int(count)
                    except (TypeError, ValueError):
                        count_num = -1
                    is_last = bool(user_event.get("isLastAttendance", False))
                    reward_list = schedule.get("rewardInfoList", [])
                    total_days = len(reward_list) if isinstance(reward_list, list) else 0
                    start = str(schedule.get("startDate") or "").split(" ")[0]
                    end = str(schedule.get("endDate") or "").split(" ")[0]
                    can_attend = count_num >= 0 and not is_last
                    log(
                        f"  活动窗口: {start} ~ {end}，进度 {count_num}/{total_days}，"
                        f"scheduleId={schedule_id}"
                    )
                    if can_attend:
                        time.sleep(0.5)
                        attend_resp = http_json(
                            "POST",
                            "/api/event/attend-reward",
                            token=token,
                            body={"eventScheduleId": schedule_id},
                            timeout=timeout,
                        )
                        attend_json = attend_resp.get("json")
                        data = (
                            attend_json.get("data", attend_json)
                            if isinstance(attend_json, dict)
                            else {}
                        )
                        success = bool(data.get("success", False)) if isinstance(data, dict) else False
                        if success:
                            stage_log(
                                3,
                                "活动出席",
                                "success",
                                f"今日活动签到成功（{count_num + 1}/{total_days}，"
                                f"耗时 {time.monotonic() - stage_t0:.2f}秒）",
                                stats,
                                messages,
                            )
                        else:
                            # 可能已签到
                            err = ""
                            if isinstance(data, dict):
                                err = str(data.get("errorMsg") or "")
                            if "Already" in err or "already" in err.lower():
                                stage_log(
                                    3,
                                    "活动出席",
                                    "alreadyComplete",
                                    f"今日活动已签到（{count_num}/{total_days}，"
                                    f"耗时 {time.monotonic() - stage_t0:.2f}秒）",
                                    stats,
                                    messages,
                                )
                            else:
                                account_ok = False
                                stage_log(
                                    3,
                                    "活动出席",
                                    "failure",
                                    f"{extract_safe_error(attend_json)}（耗时 "
                                    f"{time.monotonic() - stage_t0:.2f}秒）",
                                    stats,
                                    messages,
                                )
                    else:
                        if is_last or (total_days > 0 and count_num >= total_days):
                            detail = (
                                f"今日活动已签到（{count_num}/{total_days}天）"
                                if is_last or count_num < total_days
                                else f"已完成全部 {total_days} 天活动"
                            )
                        else:
                            detail = f"活动状态不可出席（{count_num}/{total_days}）"
                        stage_log(
                            3,
                            "活动出席",
                            "alreadyComplete",
                            f"{detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
                            stats,
                            messages,
                        )
            except SafeError as exc:
                account_ok = False
                stage_log(3, "活动出席", "failure", str(exc), stats, messages)

    elapsed = time.monotonic() - started
    log(
        f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
    )
    status = "success" if account_ok and stats["failed"] == 0 else "failure"
    return {
        "ok": account_ok and stats["failed"] == 0,
        "identity": identity,
        "status": status,
        "message": "；".join(messages)[:240],
        "stats": stats,
    }


def main() -> int:
    task_start = _now()
    dry = env_truthy(DRY_RUN_ENV, False)
    mode = "dry-run" if dry else "live"

    print("=" * 56, flush=True)
    log(f"任务: {SCRIPT_NAME}")
    log(f"开始时间: {task_start.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        timeout = float(int_env(TIMEOUT_ENV, DEFAULT_TIMEOUT, 5, 120))
        account_delay_sec = float(int_env(ACCOUNT_DELAY_ENV, 1, 0, 600))
        skip_event = env_truthy(SKIP_EVENT_ENV, False)
        daily_only = env_truthy(DAILY_ONLY_ENV, False)
        log(
            "任务开关: "
            f"每日签到=开 / 每周签到={'关' if daily_only else '开'} / "
            f"活动出席={'关' if (daily_only or skip_event) else '开'}"
        )

        raw = load_token_raw()
        if not raw.strip():
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{STATUS_ICONS['failure']} 未配置必填环境变量 {TOKEN_ENV}")
            log(
                "获取方式: 登录 https://webshop.browndust2.global/CT/ 后按 F12 → Console，"
                "执行 JSON.parse(localStorage.getItem(\"session-storage\"))"
                ".state.session.accessToken，将结果写入青龙环境变量 "
                f"{TOKEN_ENV}；每行一个账号。"
            )
            log("账号数量: 0")
        else:
            accounts = parse_accounts(raw)
            log(f"账号数量: {len(accounts)}")
            if not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{STATUS_ICONS['failure']} 未解析到任何有效账号")
            else:
                total = len(accounts)
                for idx, token in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(
                            idx, total, token, skip_event=skip_event, daily_only=daily_only
                        )
                    else:
                        ar = run_account_live(
                            idx,
                            total,
                            token,
                            timeout=timeout,
                            skip_event=skip_event,
                            daily_only=daily_only,
                        )
                    account_results.append(ar)
                    if idx < total and account_delay_sec > 0 and not dry:
                        log(f"账号间隔等待 {account_delay_sec:.0f} 秒")
                        time.sleep(account_delay_sec)

                failed = [a for a in account_results if not a.get("ok")]
                succeeded = [a for a in account_results if a.get("ok")]
                if failed and succeeded:
                    summary_status = "partial-failure"
                    exit_code = 1
                elif failed:
                    summary_status = "failure"
                    exit_code = 1
                else:
                    summary_status = "dry-run" if dry else "success"
                    exit_code = 0
    except SafeError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{STATUS_ICONS['failure']} 配置错误: {exc}")
    except Exception:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{STATUS_ICONS['failure']} 未处理异常")
        traceback.print_exc()

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56, flush=True)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(int((a.get("stats") or {}).get("success") or 0) for a in account_results)
    sub_fail = sum(int((a.get("stats") or {}).get("failed") or 0) for a in account_results)
    sub_skip = sum(int((a.get("stats") or {}).get("skipped") or 0) for a in account_results)
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0) for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {task_end.strftime('%Y-%m-%d %H:%M:%S')}")

    if dry and not config_error:
        event = "dry-run"
    elif config_error:
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        f"任务: {SCRIPT_NAME}",
        f"模式: {mode}",
        f"事件: {event}",
        f"账号总数: {total_accounts if not config_error else 0}",
        f"成功: {ok_count}",
        f"失败: {fail_count}",
        f"状态: {summary_status}",
    ]
    for a in account_results:
        lines.append(
            f"- {a.get('identity')}: {a.get('status')} / {compact(str(a.get('message', '')), 120)}"
        )
    notify_status = send_notification(SCRIPT_NAME, "\n".join(lines))
    log(f"通知状态: {notify_status}")

    final_status = summary_status
    if exit_code == 0 and dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        final_status = "dry-run-success"
        log(f"{STATUS_ICONS['success']} 最终状态: dry-run-success")
    elif exit_code == 0:
        log(f"{STATUS_ICONS['success']} 最终状态: success")
    elif config_error:
        log(f"{STATUS_ICONS['failure']} 最终状态: configuration-error")
    else:
        log(f"{STATUS_ICONS['failure']} 最终状态: {summary_status}")

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "task": SCRIPT_NAME,
        "mode": mode,
        "status": final_status if exit_code == 0 else summary_status,
        "exitCode": exit_code,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSucceeded": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notifyStatus": notify_status,
        "finishedAt": task_end.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
