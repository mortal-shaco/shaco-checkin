#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: SF轻小说签到
# cron: 16 9 * * *
# publish-path: scripts/sfacg_checkin.py
"""SF轻小说（SFACG / 菠萝包）每日签到与日常任务（独立维护版）。

发布路径（产品专属，勿使用 scripts/sf.py）：
  scripts/sfacg_checkin.py

功能：
  - 校验登录会话并展示昵称、火券余额、VIP 等级
  - 调用 newSignInfo 完成每日签到（已签视为成功）
  - 上报阅读/听书时长，领取并完成日常任务 4/5/17
  - 支持多账号、完全断网预演、时间轴日志与青龙通知

环境变量：
  SFACG_COOKIE         必填。每个非空行一个账号 Cookie。
                       登录 SF轻小说 App 后抓包 api.sfacg.com 请求，复制 Cookie
                       （至少含 session_APP 与 .SFCommunity）。
                       同一账号若需单独 sfsecurity，可写成：
                       Cookie值|sfsecurity完整值
                       （仅按第一个 | 分割，Cookie 内的 ; = 不用于分账号）。
  SFACG_AUTHORIZATION  可选。App 客户端 Basic 鉴权头；缺省使用上游公开客户端值。
  SFACG_SFSECURITY     可选。全局 sfsecurity；账号行未附带时使用。
                       均未配置时按上游固定 nonce/device/sign 并刷新 timestamp。
  SFACG_DRY_RUN        1/true/yes/on 开启完全断网预演。
  SFACG_TIMEOUT        单次请求超时秒数，默认 20，范围 5~60。
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

来源与许可：
  Illustar0/SF_AutoCheckIn CheckIn.py
  @ 0a4af5015e664060003f7ce6f332c884221b9e14
  Copyright (c) 2021 XCwosjw
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "11d080ed77bec3d2",
            "scripts/sfacg_checkin.py",
            "sfacg_checkin.py",
            "candidate.py",
            "CheckIn.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "11d080ed77bec3d2"
TASK_NAME = "SF轻小说签到"
PUBLISH_PATH = "scripts/sfacg_checkin.py"
PUBLISH_FILENAME = "sfacg_checkin.py"
API_BASE = "https://api.sfacg.com"
DEFAULT_AUTHORIZATION = "Basic YW5kcm9pZHVzZXI6MWEjJDUxLXl0Njk7KkFjdkBxeHE="
DEFAULT_NONCE = "EE94F4D4-CC0B-43B6-BFF2-6CB72CE8698B"
DEFAULT_DEVICE = "F632BBEC-F075-39B5-A2C8-3234F5CBF99D"
DEFAULT_SIGN = "7778A67648C9D95483E466D9D341FEA1"
USER_AGENT = "boluobao/4.6.36(android;22)/OPPO"
ACCEPT = "application/vnd.sfacg.api+json;version=1"
TASK_IDS = (4, 5, 17)
MAX_RESPONSE_BYTES = 256 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
MSG_NEED_LOGIN = "需要登录才能访问该资源"
MSG_MAINTENANCE = "签到系统在每日凌晨0~1点之间进行维护,请您选在其他时间签到哦"
MSG_ALREADY = "您今天已经签过到了,请明天再来"
SECRETS: List[str] = []


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def beijing_date() -> str:
    utc_now = datetime.now(timezone.utc)
    bj = utc_now.astimezone(timezone(timedelta(hours=8)))
    return bj.strftime("%Y-%m-%d")


def parse_timeout() -> float:
    raw = os.getenv("SFACG_TIMEOUT", "20").strip() or "20"
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("SFACG_TIMEOUT 必须是 5 到 60 的整数") from exc
    if value < 5 or value > 60:
        raise ValueError("SFACG_TIMEOUT 必须是 5 到 60 的整数")
    return float(value)


def redact(text: Any, limit: int = 200) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted({item for item in SECRETS if item}, key=len, reverse=True):
        if secret and secret in value:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(
        r"(?i)(cookie|token|authorization|session_APP|\.SFCommunity|sfsecurity|sign|devicetoken|nonce)\s*[:=]\s*[^\s,;|&]+",
        "[敏感字段已隐藏]",
        value,
    )
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    return value[:limit] if value else "未提供业务消息"


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    SECRETS.append(value)
    for part in re.split(r"[;&|]", value):
        part = part.strip()
        if "=" in part:
            _, rhs = part.split("=", 1)
            rhs = rhs.strip()
            if len(rhs) >= 4:
                SECRETS.append(rhs)
        elif len(part) >= 8:
            SECRETS.append(part)


def build_sfsecurity(override: Optional[str] = None) -> str:
    raw = (override or "").strip()
    if raw:
        # 若含 timestamp= 则刷新为当前秒级时间戳，保留其余字段
        if "timestamp=" in raw:
            ts = str(int(time.time()))
            return re.sub(r"timestamp=\d+", "timestamp=" + ts, raw, count=1)
        return raw
    ts = str(int(time.time()))
    return (
        "nonce={}&timestamp={}&devicetoken={}&sign={}".format(
            DEFAULT_NONCE, ts, DEFAULT_DEVICE, DEFAULT_SIGN
        )
    )


def load_accounts() -> List[Dict[str, str]]:
    raw = os.getenv("SFACG_COOKIE", "").replace("\r\n", "\n")
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if not lines:
        raise ValueError(
            "未配置 SFACG_COOKIE；请按每行一个账号填写 Cookie（含 session_APP 与 .SFCommunity）"
        )
    global_security = os.getenv("SFACG_SFSECURITY", "").strip()
    accounts: List[Dict[str, str]] = []
    for line in lines:
        if "|" in line:
            cookie, security = line.split("|", 1)
            cookie = cookie.strip()
            security = security.strip()
        else:
            cookie = line
            security = global_security
        if "session_APP=" not in cookie and "session_APP" not in cookie.lower():
            # 宽松提示：仍允许完整 Cookie 字符串
            if ".SFCommunity=" not in cookie and "SFCommunity=" not in cookie:
                raise ValueError(
                    "SFACG_COOKIE 行缺少 session_APP / SFCommunity，请重新从 App 抓包复制"
                )
        if len(cookie) < 12:
            raise ValueError("SFACG_COOKIE 长度过短，请确认复制了完整 Cookie")
        remember_secret(cookie)
        if security:
            remember_secret(security)
        accounts.append({"cookie": cookie, "sfsecurity": security})
    return accounts


def authorization_header() -> str:
    value = os.getenv("SFACG_AUTHORIZATION", "").strip() or DEFAULT_AUTHORIZATION
    remember_secret(value)
    if value.lower().startswith("basic "):
        return value
    return "Basic " + value


def build_headers(cookie: str, sfsecurity: Optional[str], *, json_body: bool = False) -> Dict[str, str]:
    headers = {
        "Host": "api.sfacg.com",
        "accept-charset": "UTF-8",
        "authorization": authorization_header(),
        "accept": ACCEPT,
        "user-agent": USER_AGENT,
        "sfsecurity": build_sfsecurity(sfsecurity),
        "accept-encoding": "gzip",
        "Cookie": cookie,
    }
    if json_body:
        headers["content-type"] = "application/json; charset=UTF-8"
    return headers


def request_json(
    method: str,
    path: str,
    cookie: str,
    sfsecurity: Optional[str],
    timeout: float,
    data: Optional[bytes] = None,
) -> Dict[str, Any]:
    url = API_BASE + path if path.startswith("/") else path
    headers = build_headers(cookie, sfsecurity, json_body=data is not None)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1) if hasattr(exc, "read") else b""
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(payload, dict):
                    return payload
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                pass
        raise RuntimeError("接口返回 HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        reason_name = type(reason).__name__ if reason is not None else "网络错误"
        raise RuntimeError("网络请求失败（{}）".format(reason_name)) from exc
    except TimeoutError as exc:
        raise RuntimeError("网络请求超时") from exc
    if status < 200 or status >= 300:
        # SFACG 部分业务码也走 2xx；非 2xx 仍尝试解析
        pass
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("接口响应超过安全上限")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("接口未返回有效 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("接口 JSON 顶层结构无效")
    return payload


def status_msg(payload: Dict[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, dict):
        return str(status.get("msg") or "").strip()
    return str(payload.get("msg") or payload.get("message") or "").strip()


def status_http(payload: Dict[str, Any]) -> Optional[int]:
    status = payload.get("status")
    if isinstance(status, dict) and status.get("httpCode") is not None:
        try:
            return int(status.get("httpCode"))
        except (TypeError, ValueError):
            return None
    return None


def extract_identity(user_payload: Dict[str, Any]) -> Optional[str]:
    data = user_payload.get("data")
    if not isinstance(data, dict):
        data = user_payload
    for key in ("nickName", "nickname", "userName", "username", "displayName", "name"):
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and redact(text, len(text)) == text:
            return text
    return None


def money_summary(money_payload: Dict[str, Any]) -> str:
    data = money_payload.get("data")
    if not isinstance(data, dict):
        return ""
    parts = []
    if data.get("fireMoneyRemain") is not None:
        parts.append("火券{}".format(data.get("fireMoneyRemain")))
    if data.get("vipLevel") is not None:
        parts.append("VIP{}".format(data.get("vipLevel")))
    return " ".join(parts)


def classify_sign(payload: Dict[str, Any]) -> Tuple[str, str]:
    msg = status_msg(payload)
    if MSG_NEED_LOGIN in msg:
        raise RuntimeError("鉴权失败：Cookie 无效或已过期，请更新 SFACG_COOKIE")
    if MSG_MAINTENANCE in msg:
        raise RuntimeError("签到系统维护中（每日 0~1 点），请稍后再试")
    if MSG_ALREADY in msg or "已经签过" in msg:
        return "already", msg or "今日已签到"
    http_code = status_http(payload)
    if http_code is not None and http_code >= 400:
        raise RuntimeError("签到业务失败：{}".format(redact(msg or ("HTTP " + str(http_code)))))
    # 上游对其他 msg 继续执行任务，视为签到成功
    return "success", msg or "签到成功"


def reading_payload(entity_type: int) -> bytes:
    body = {
        "seconds": 3605,
        "readingDate": beijing_date(),
        "entityType": entity_type,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_login(
    cookie: str, sfsecurity: Optional[str], timeout: float
) -> Tuple[str, str]:
    user = request_json("GET", "/user?", cookie, sfsecurity, timeout)
    msg = status_msg(user)
    if MSG_NEED_LOGIN in msg:
        raise RuntimeError("鉴权失败：Cookie 无效或已过期，请更新 SFACG_COOKIE")
    identity = extract_identity(user)
    if not identity:
        http_code = status_http(user)
        raise RuntimeError(
            "无法读取账号昵称（httpCode={}）：{}".format(
                http_code if http_code is not None else "未知",
                redact(msg),
            )
        )
    summary = ""
    try:
        money = request_json("GET", "/user/money", cookie, sfsecurity, timeout)
        summary = money_summary(money)
    except Exception as exc:
        log(
            "{} 火券信息查询跳过：{}".format(
                ICONS["warning"],
                redact(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
            )
        )
    return identity, summary


def run_daily_tasks(cookie: str, sfsecurity: Optional[str], timeout: float) -> Tuple[str, str]:
    """上报时长并领取/完成任务。返回 (outcome, message)。"""
    listen_data = reading_payload(3)
    read_data = reading_payload(2)
    errors: List[str] = []

    try:
        resp = request_json(
            "PUT", "/user/readingtime", cookie, sfsecurity, timeout, data=listen_data
        )
        msg = status_msg(resp)
        if MSG_NEED_LOGIN in msg:
            raise RuntimeError("鉴权失败：Cookie 无效或已过期")
    except Exception as exc:
        errors.append("听书时长：" + (redact(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))

    for task_id in TASK_IDS:
        try:
            request_json(
                "POST",
                "/user/tasks/{}".format(task_id),
                cookie,
                sfsecurity,
                timeout,
                data=listen_data,
            )
        except Exception as exc:
            errors.append(
                "领取任务{}：{}".format(
                    task_id,
                    redact(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
                )
            )

    for _ in range(3):
        try:
            request_json(
                "PUT", "/user/readingtime", cookie, sfsecurity, timeout, data=read_data
            )
        except Exception as exc:
            errors.append(
                "阅读时长："
                + (redact(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
            )
            break
        time.sleep(0.5)
        for task_id in (5, 4, 17):
            try:
                request_json(
                    "PUT",
                    "/user/tasks/{}".format(task_id),
                    cookie,
                    sfsecurity,
                    timeout,
                    data=listen_data,
                )
            except Exception as exc:
                errors.append(
                    "完成任务{}：{}".format(
                        task_id,
                        redact(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
                    )
                )

    if errors:
        # 任务为签到后续增强；部分失败记 warning，不单独整账失败（与上游尽量继续一致）
        return "warning", "日常任务部分异常：" + "；".join(errors[:3])
    return "success", "日常任务已提交"


def run_account(
    index: int,
    account: Dict[str, str],
    dry_run: bool,
    timeout: float,
) -> Dict[str, Any]:
    started = time.monotonic()
    stages = ["登录校验", "每日签到", "日常任务"]
    total = len(stages)
    stats = {"total": total, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    identity = "账号{}".format(index)
    errors: List[str] = []
    cookie = account["cookie"]
    sfsecurity = account.get("sfsecurity") or None

    print("\n========== 账号{} ==========".format(index), flush=True)

    # Stage 1: login
    stage_started = time.monotonic()
    prefix = "[账号{}][1/{}]".format(index, total)
    log("{} 登录校验开始".format(prefix))
    if dry_run:
        stats["skipped"] += 1
        log(
            "{} {} 已校验 Cookie 配置，未发起网络请求（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
    else:
        try:
            found, money_text = verify_login(cookie, sfsecurity, timeout)
            identity = found
            stats["success"] += 1
            extra = "；{}".format(money_text) if money_text else ""
            log(
                "{} {} 身份={}{}（{:.2f}秒）".format(
                    prefix,
                    ICONS["success"],
                    identity,
                    extra,
                    time.monotonic() - stage_started,
                )
            )
        except Exception as exc:
            stats["failed"] += 1
            message = redact(exc) if isinstance(exc, RuntimeError) else "登录校验失败"
            errors.append(message)
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], message, time.monotonic() - stage_started
                )
            )
            elapsed = time.monotonic() - started
            log(
                "[账号{}] 结果=FAILED；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
                    index,
                    identity,
                    stats["total"],
                    stats["success"],
                    stats["already"],
                    stats["skipped"],
                    stats["failed"],
                    elapsed,
                )
            )
            return {
                "index": index,
                "identity": identity,
                "ok": False,
                "stats": stats,
                "elapsed": elapsed,
                "errors": errors,
            }

    # Stage 2: sign
    stage_started = time.monotonic()
    prefix = "[账号{}][2/{}]".format(index, total)
    log("{} 每日签到开始".format(prefix))
    sign_outcome = "skipped"
    if dry_run:
        stats["skipped"] += 1
        log(
            "{} {} 断网预演：跳过签到请求（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
    else:
        try:
            payload = request_json(
                "PUT",
                "/user/newSignInfo",
                cookie,
                sfsecurity,
                timeout,
                data=reading_payload(2),
            )
            sign_outcome, message = classify_sign(payload)
            if sign_outcome == "already":
                stats["already"] += 1
                icon = ICONS["alreadyComplete"]
            else:
                stats["success"] += 1
                icon = ICONS["success"]
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, icon, redact(message), time.monotonic() - stage_started
                )
            )
        except Exception as exc:
            stats["failed"] += 1
            sign_outcome = "failure"
            message = redact(exc) if isinstance(exc, RuntimeError) else "签到失败"
            errors.append(message)
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], message, time.monotonic() - stage_started
                )
            )

    # Stage 3: daily tasks — 与上游一致：仅在“新鲜签到成功”后执行；已签则跳过
    stage_started = time.monotonic()
    prefix = "[账号{}][3/{}]".format(index, total)
    log("{} 日常任务开始".format(prefix))
    if dry_run:
        stats["skipped"] += 1
        log(
            "{} {} 断网预演：跳过日常任务（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
    elif sign_outcome == "success":
        try:
            outcome, message = run_daily_tasks(cookie, sfsecurity, timeout)
            if outcome == "warning":
                stats["success"] += 1
                log(
                    "{} {} {}（{:.2f}秒）".format(
                        prefix,
                        ICONS["warning"],
                        redact(message),
                        time.monotonic() - stage_started,
                    )
                )
            else:
                stats["success"] += 1
                log(
                    "{} {} {}（{:.2f}秒）".format(
                        prefix,
                        ICONS["success"],
                        redact(message),
                        time.monotonic() - stage_started,
                    )
                )
        except Exception as exc:
            stats["failed"] += 1
            message = redact(exc) if isinstance(exc, RuntimeError) else "日常任务失败"
            errors.append(message)
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], message, time.monotonic() - stage_started
                )
            )
    elif sign_outcome == "already":
        stats["skipped"] += 1
        log(
            "{} {} 今日已签到，按上游逻辑跳过日常任务（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
    else:
        stats["skipped"] += 1
        log(
            "{} {} 签到未成功，跳过日常任务（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )

    elapsed = time.monotonic() - started
    ok = stats["failed"] == 0
    if dry_run and ok:
        result_label = "DRY_RUN"
    elif ok:
        result_label = "SUCCESS"
    else:
        result_label = "FAILED"
    log(
        "[账号{}] 结果={}；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            index,
            result_label,
            identity,
            stats["total"],
            stats["success"],
            stats["already"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return {
        "index": index,
        "identity": identity,
        "ok": ok,
        "stats": stats,
        "elapsed": elapsed,
        "errors": errors,
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
        Path(__file__).name,
        "candidate.py",
        "CheckIn.py",
        PUBLISH_FILENAME,
        PUBLISH_PATH,
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
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return notification_selected()
    if value not in {"", "auto"}:
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    return paths


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    paths: List[Optional[Path]] = [None] + [
        path for path in python_notifier_paths() if path.is_file()
    ]
    for path in paths:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    python_runner,
                    str(path) if path else "",
                    str(Path(__file__).resolve().parent),
                ],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                log("通知状态：{} 已调用".format("notify.py" if path else "notify.send"))
                return "sent"
        except Exception:
            continue

    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in js_notifier_paths():
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue

    log(
        "{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(
            ICONS["warning"]
        )
    )
    return "unavailable"


def print_summary(summary: Dict[str, Any]) -> None:
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def finish_config_error(
    started_at: str, overall_started: float, dry_run: bool, message: str
) -> int:
    log("账号数量：0")
    log("[0/0] {} 配置错误：{}".format(ICONS["failure"], message))
    body = "账号总数：0；成功：0；失败：1；状态：配置错误"
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()
    print("-" * 56, flush=True)
    print("账号结果：总数 0，成功 0，失败 1", flush=True)
    print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0", flush=True)
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started), flush=True)
    print("完成时间：{}".format(finished_at), flush=True)
    print("通知状态：{}".format(notify_state), flush=True)
    print("最终状态：CONFIG_ERROR", flush=True)
    print_summary(
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
    return 1


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("SFACG_DRY_RUN")

    print("=" * 56, flush=True)
    print("{} | 独立维护版".format(TASK_NAME), flush=True)
    print("开始时间：{}".format(started_at), flush=True)
    print(
        "运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"),
        flush=True,
    )
    print("=" * 56, flush=True)

    try:
        timeout = parse_timeout()
        accounts = load_accounts()
    except ValueError as exc:
        return finish_config_error(started_at, overall_started, dry_run, str(exc))

    log("账号数量：{}".format(len(accounts)))
    results: List[Dict[str, Any]] = []
    for index, account in enumerate(accounts, 1):
        results.append(run_account(index, account, dry_run, timeout))

    success_accounts = sum(1 for item in results if item["ok"])
    failed_accounts = len(results) - success_accounts
    task_totals = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    for item in results:
        for key in task_totals:
            task_totals[key] += item["stats"][key]

    if dry_run:
        final_status = "DRY-RUN"
        summary_status = "dry-run"
        exit_code = 0 if failed_accounts == 0 else 1
    elif failed_accounts == 0:
        final_status = "SUCCESS"
        summary_status = "success"
        exit_code = 0
    elif success_accounts == 0:
        final_status = "FAILURE"
        summary_status = "failure"
        exit_code = 1
    else:
        final_status = "PARTIAL_FAILURE"
        summary_status = "partial-failure"
        exit_code = 1

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), success_accounts, failed_accounts, final_status
    )
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()

    print("-" * 56, flush=True)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), success_accounts, failed_accounts
        ),
        flush=True,
    )
    print(
        "子任务结果：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            task_totals["total"],
            task_totals["success"],
            task_totals["already"],
            task_totals["skipped"],
            task_totals["failed"],
        ),
        flush=True,
    )
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started), flush=True)
    print("完成时间：{}".format(finished_at), flush=True)
    print("通知状态：{}".format(notify_state), flush=True)
    print("最终状态：{}".format(final_status), flush=True)
    print_summary(
        {
            "status": summary_status,
            "mode": "dry-run" if dry_run else "live",
            "accounts": {
                "total": len(results),
                "success": success_accounts,
                "failed": failed_accounts,
            },
            "tasks": {
                "total": task_totals["total"],
                "success": task_totals["success"],
                "alreadyComplete": task_totals["already"],
                "skipped": task_totals["skipped"],
                "failed": task_totals["failed"],
            },
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
