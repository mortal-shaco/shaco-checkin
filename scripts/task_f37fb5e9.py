#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: M-SEC 每日签到
# cron: 6 8 * * *
from __future__ import annotations
#
# 来源：pip-in-head/EZ-Chicken-OCR main.py（MIT）
# https://github.com/pip-in-head/EZ-Chicken-OCR
# 提交：9f48e1c04a4fb02ae37ded61e96f79844538c4a4
# 基于 crazy0x70/EZ-Checkin 改造。
#
# MIT License
#
# Copyright (c) 2025 crazy0x70
# Copyright (c) 2025 dakeguo
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
"""M-SEC（https://msec.nsfocus.com）每日签到 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用 Authorization 令牌或 用户名|密码（验证码登录）完成每日签到
- 查询积分（当前 total / 累计 accrued），区分签到成功与今日已签到
- Token 失效且配置了密码时自动重新登录（本地 OCR 优先，可选云码回退）
- 移除 config.json / points_state.json 落盘、飞书/Lark Webhook、原始响应打印
- 青龙改为环境变量多账号与 cron 调度；上游 README 建议每天 08:00

MSEC_ACCOUNTS：每个非空行一个账号。支持：
  1) Authorization令牌（整行）
  2) 用户名|密码
  3) 用户名|密码|Authorization令牌（优先令牌，失效时用密码重登）
仅在第一个竖线处分割用户名，其余作为密码或 密码|令牌；不要用 & 或 @ 分隔账号。
MSEC_CAPTCHA_TOKEN：可选云码 API Token；本地 OCR 失败或不可用时用于密码登录。
MSEC_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
MSEC_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 08:00。不打印密码、Cookie、Token、验证码原文或原始响应。
"""
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
            "f37fb5e9e5ff6414",
            "scripts/msec_checkin.py",
            "msec_checkin.py",
            "candidate.py",
            "msec_checkin",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

TITLE = "M-SEC 每日签到"
CATALOG_ID = "f37fb5e9e5ff6414"
CHECKIN_URL = "https://msec.nsfocus.com/backend_api/checkin/checkin"
POINTS_URL = "https://msec.nsfocus.com/backend_api/point/common/get"
CAPTCHA_URL = "https://msec.nsfocus.com/backend_api/account/captcha"
LOGIN_URL = "https://msec.nsfocus.com/backend_api/account/login"
CLOUD_CAPTCHA_URL = "http://api.jfbym.com/api/YmServer/customApi"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 65536
MAX_LOGIN_ATTEMPTS = 10
LOGIN_GAP_SECONDS = 10.0
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}

_OCR_NORMAL = None
_OCR_BETA = None
_LOGIN_THROTTLE_LOCK = Lock()
_last_login_timestamp = 0.0


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_timeout() -> float:
    raw = env("MSEC_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("MSEC_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("MSEC_TIMEOUT 须在 5 到 60 秒之间")
    return value


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            token = text.strip()
            if not token:
                raise SafeError("账号行令牌为空")
            if any(ord(ch) < 32 for ch in token):
                raise SafeError("账号行含控制字符")
            accounts.append({"username": "", "password": "", "token": token})
            continue
        username, remainder = text.split("|", 1)
        username = username.strip()
        remainder = remainder.strip()
        if not username or not remainder:
            raise SafeError("用户名或后续凭据为空")
        if "|" in remainder:
            password, token = remainder.split("|", 1)
            password = password.strip()
            token = token.strip()
        else:
            password = remainder
            token = ""
        if not password and not token:
            raise SafeError("密码与令牌不能同时为空")
        if any(ord(ch) < 32 for ch in username + password + token):
            raise SafeError("账号行含控制字符")
        accounts.append(
            {"username": username, "password": password, "token": token}
        )
    return accounts


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "errorMsg", "error_msg", "tip", "desc"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("message", "msg", "tip", "desc"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return compact(value)
    if isinstance(data, str):
        return compact(data)
    return ""


def http_json(
    url: str,
    *,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[int, Any]:
    request_headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://msec.nsfocus.com",
        "Referer": "https://msec.nsfocus.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    if headers:
        request_headers.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method.upper()
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            raw = error.read(MAX_BYTES + 1)
        except Exception:
            raw = b""
        finally:
            error.close()
    except Exception as exc:
        raise SafeError("网络、超时或连接失败") from exc
    if len(raw) > MAX_BYTES:
        raise SafeError("响应超过大小限制")
    if not raw:
        return status, None
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SafeError("响应不是合法 JSON") from exc


def build_auth_headers(token: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = token
    return headers


def _get_ocr_engines():
    global _OCR_NORMAL, _OCR_BETA
    try:
        import ddddocr  # type: ignore
    except Exception as exc:
        raise SafeError("本地 OCR 依赖不可用（ddddocr）") from exc
    if _OCR_NORMAL is None:
        _OCR_NORMAL = ddddocr.DdddOcr(show_ad=False)
    if _OCR_BETA is None:
        _OCR_BETA = ddddocr.DdddOcr(show_ad=False, beta=True)
    return _OCR_NORMAL, _OCR_BETA


def _preprocess_strategies():
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps  # type: ignore
    import numpy as np  # type: ignore

    def grayscale_contrast(img):
        gray = img.convert("L")
        return ImageEnhance.Contrast(gray).enhance(3.0)

    def binary(img):
        gray = img.convert("L")
        arr = np.array(gray)
        binary_arr = ((arr > 80) * 255).astype(np.uint8)
        return Image.fromarray(binary_arr)

    def inverted_contrast(img):
        gray = img.convert("L")
        inverted = ImageOps.invert(gray)
        return ImageEnhance.Contrast(inverted).enhance(2.5)

    def sharpen(img):
        return img.filter(ImageFilter.SHARPEN)

    def grayscale(img):
        return img.convert("L")

    return [
        grayscale_contrast,
        binary,
        inverted_contrast,
        sharpen,
        grayscale,
    ]


def verify_captcha_local(captcha_image_b64: str) -> Optional[str]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        ocr_normal, ocr_beta = _get_ocr_engines()
        strategies = _preprocess_strategies()
    except SafeError:
        return None
    except Exception:
        return None
    try:
        img_data = base64.b64decode(captcha_image_b64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception:
        return None

    results: List[str] = []
    for preprocess_fn in strategies:
        try:
            processed = preprocess_fn(img)
            buf = io.BytesIO()
            processed.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            result_normal = ocr_normal.classification(img_bytes)
            if result_normal and len(result_normal) == 5:
                results.append(result_normal)
            result_beta = ocr_beta.classification(img_bytes)
            if result_beta and len(result_beta) == 5:
                results.append(result_beta)
        except Exception:
            continue

    if not results:
        for preprocess_fn in strategies:
            try:
                processed = preprocess_fn(img)
                buf = io.BytesIO()
                processed.save(buf, format="PNG")
                img_bytes = buf.getvalue()
                r1 = ocr_normal.classification(img_bytes)
                r2 = ocr_beta.classification(img_bytes)
                if r1 and len(r1) >= 4:
                    results.append(r1)
                if r2 and len(r2) >= 4:
                    results.append(r2)
            except Exception:
                continue

    if not results:
        return None
    most_common, count = Counter(results).most_common(1)[0]
    total = len(results)
    confidence = count / total
    if confidence < 0.4 or total < 3:
        return None
    return most_common


def verify_captcha_cloud(token: str, captcha_image: str, timeout: float) -> Optional[str]:
    if not token or token == "云码token":
        return None
    status, response = http_json(
        CLOUD_CAPTCHA_URL,
        method="POST",
        headers={"Content-Type": "application/json"},
        payload={"token": token, "type": 10103, "image": captcha_image},
        timeout=min(timeout, 15.0),
    )
    if status != 200 or not isinstance(response, dict):
        return None
    if response.get("code") != 10000:
        return None
    data = response.get("data")
    if not isinstance(data, dict):
        return None
    captcha_result = data.get("data")
    if isinstance(captcha_result, str) and len(captcha_result) == 5:
        return captcha_result
    return None


def verify_captcha(captcha_token: str, captcha_image: str, timeout: float) -> Optional[str]:
    local = verify_captcha_local(captcha_image)
    if local:
        log("验证码：本地 OCR 识别成功（不输出原文）")
        return local
    cloud = verify_captcha_cloud(captcha_token, captcha_image, timeout)
    if cloud:
        log("验证码：云码 API 识别成功（不输出原文）")
        return cloud
    return None


def get_captcha(timeout: float) -> Tuple[Optional[str], Optional[str]]:
    status, payload = http_json(CAPTCHA_URL, method="POST", payload={}, timeout=timeout)
    if status != 200 or not isinstance(payload, dict):
        return None, None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None
    captcha_id = data.get("id")
    captcha_raw = data.get("captcha") or ""
    if not isinstance(captcha_raw, str):
        return None, None
    captcha_img = captcha_raw.split(",")[-1] if "," in captcha_raw else captcha_raw
    if not captcha_id or not captcha_img:
        return None, None
    return str(captcha_id), captcha_img


def login_with_password(
    username: str,
    password: str,
    captcha_token: str,
    timeout: float,
) -> str:
    global _last_login_timestamp
    token_result = ""
    with _LOGIN_THROTTLE_LOCK:
        now = time.time()
        if _last_login_timestamp:
            wait_seconds = max(0.0, LOGIN_GAP_SECONDS - (now - _last_login_timestamp))
            if wait_seconds > 0:
                log("登录节流：等待 {:.1f} 秒".format(wait_seconds))
                time.sleep(wait_seconds)
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            if attempt > 1:
                log("登录重试：等待 {:.0f} 秒后第 {} 次尝试".format(LOGIN_GAP_SECONDS, attempt))
                time.sleep(LOGIN_GAP_SECONDS)
            captcha_id, captcha_img = get_captcha(timeout)
            if not captcha_id or not captcha_img:
                log("登录：获取验证码失败")
                continue
            captcha_result = verify_captcha(captcha_token, captcha_img, timeout)
            if not captcha_result:
                log("登录：验证码识别失败")
                continue
            status, auth_data = http_json(
                LOGIN_URL,
                method="POST",
                payload={
                    "captcha_answer": captcha_result,
                    "captcha_id": captcha_id,
                    "password": password,
                    "username": username,
                },
                timeout=timeout,
            )
            if not isinstance(auth_data, dict):
                log("登录：响应无法解析")
                continue
            if auth_data.get("status") == 200:
                data = auth_data.get("data")
                if isinstance(data, dict) and isinstance(data.get("token"), str) and data["token"]:
                    token_result = data["token"]
                    log("登录：业务成功（令牌已获取，不输出）")
                    break
            message = business_message(auth_data)
            if any(word in message for word in ("密码", "账号", "用户", "凭证")):
                raise SafeError("登录业务失败（账号或密码可能无效）")
            log("登录：业务失败，准备重试")
        _last_login_timestamp = time.time()
    if not token_result:
        raise SafeError("登录失败，已用尽重试次数")
    return token_result


def sign_in(token: str, timeout: float) -> Tuple[str, str, Any]:
    status, payload = http_json(
        CHECKIN_URL,
        method="POST",
        headers=build_auth_headers(token),
        payload={},
        timeout=timeout,
    )
    if status in (401, 403):
        return "auth-failed", "Authorization 失效", payload
    if not isinstance(payload, dict):
        raise SafeError("签到响应无法解析")
    biz_status = payload.get("status")
    message = business_message(payload)
    data = payload.get("data")
    data_text = compact(data) if isinstance(data, str) else message
    if biz_status == 400 and ("已经签到" in data_text or "已经签到" in message):
        return "alreadyComplete", "今日已签到", payload
    if biz_status == 200 or ("成功" in message):
        return "success", "签到成功", payload
    if biz_status in (401, 403):
        return "auth-failed", "Authorization 失效", payload
    if biz_status == 429:
        raise SafeError("签到请求过于频繁")
    raise SafeError("签到业务失败")


def confirm_signed(token: str, timeout: float) -> Tuple[str, str]:
    delays = [1.5, 3.0, 5.0]
    last_detail = "确认签到失败"
    for attempt in range(len(delays) + 1):
        status, payload = http_json(
            CHECKIN_URL,
            method="POST",
            headers=build_auth_headers(token),
            payload={},
            timeout=timeout,
        )
        if isinstance(payload, dict):
            biz_status = payload.get("status")
            message = business_message(payload)
            data = payload.get("data")
            data_text = compact(data) if isinstance(data, str) else message
            if biz_status == 400 and ("已经签到" in data_text or "已经签到" in message):
                return "alreadyComplete", "确认：今日已签到"
            if biz_status == 429:
                last_detail = "确认请求过于频繁"
            else:
                last_detail = "确认响应未体现已签到"
        else:
            last_detail = "确认响应无法解析（HTTP {}）".format(status)
        if attempt >= len(delays):
            break
        time.sleep(delays[attempt])
    return "failure", last_detail


def query_points(token: str, timeout: float) -> Tuple[Optional[int], Optional[int]]:
    status, payload = http_json(
        POINTS_URL,
        method="POST",
        headers=build_auth_headers(token),
        payload={},
        timeout=timeout,
    )
    if status != 200 or not isinstance(payload, dict):
        return None, None
    if payload.get("status") != 200:
        return None, None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None
    accrued = data.get("accrued")
    total = data.get("total")
    accrued_i = int(accrued) if isinstance(accrued, (int, float)) and not isinstance(accrued, bool) else None
    total_i = int(total) if isinstance(total, (int, float)) and not isinstance(total, bool) else None
    return accrued_i, total_i


class AccountRunner:
    def __init__(self, number: int, label: str) -> None:
        self.number = number
        self.identity = label
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"

    def display(self) -> str:
        return self.identity or "账号{}".format(self.number)

    def stage(self, number: int, name: str, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.display(), number, name))
        state, detail = "failure", "操作未完成"
        try:
            state, detail, result = operation()
            return result
        except SafeError as error:
            detail = str(error)
            raise
        except Exception:
            detail = "内部处理失败，已抑制异常详情"
            raise SafeError(detail) from None
        finally:
            self.stats[state] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.display(),
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number: int, name: str, reason: str) -> None:
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self) -> None:
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.display(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


def resolve_token(
    account: Dict[str, str],
    captcha_token: str,
    timeout: float,
    force_login: bool = False,
) -> str:
    if not force_login and account.get("token"):
        return account["token"]
    username = account.get("username") or ""
    password = account.get("password") or ""
    if not username or not password:
        raise SafeError("缺少可用令牌，且未配置用户名密码，无法登录")
    token = login_with_password(username, password, captcha_token, timeout)
    account["token"] = token
    return token


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    captcha_token: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if account.get("token") or (account.get("username") and account.get("password")):
            return "success", "凭据本地格式检查通过，内容不输出", None
        raise SafeError("账号缺少令牌或用户名密码")

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "准备会话", "断网预演：不请求登录或签到接口")
        runner.skip(3, "提交每日签到", "断网预演：不请求签到接口")
        runner.skip(4, "确认签到状态", "断网预演：不请求确认接口")
        runner.skip(5, "查询积分", "断网预演：不请求积分接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    token_box: Dict[str, str] = {"token": ""}
    outcome_box: Dict[str, str] = {"sign": "failure"}
    relogin_attempted = False

    def prepare_session():
        had_token = bool(account.get("token"))
        token = resolve_token(account, captcha_token, timeout, force_login=False)
        token_box["token"] = token
        mode = "令牌" if had_token else "密码登录"
        return "success", "会话已准备（{}）".format(mode), token

    runner.stage(2, "准备会话", prepare_session)

    def sign_stage():
        nonlocal relogin_attempted
        while True:
            state, detail, payload = sign_in(token_box["token"], timeout)
            if state == "auth-failed":
                if relogin_attempted:
                    raise SafeError("Authorization 仍然失效")
                if not account.get("password"):
                    raise SafeError("Authorization 失效且缺少密码，无法重登")
                log("账号 {}：令牌失效，尝试密码重新登录".format(runner.display()))
                token_box["token"] = resolve_token(
                    account, captcha_token, timeout, force_login=True
                )
                relogin_attempted = True
                time.sleep(1.0)
                continue
            outcome_box["sign"] = state
            return state, detail, payload

    runner.stage(3, "提交每日签到", sign_stage)

    def confirm_stage():
        if outcome_box["sign"] == "alreadyComplete":
            return "alreadyComplete", "首次响应已确认今日签到", None
        time.sleep(1.2)
        state, detail = confirm_signed(token_box["token"], timeout)
        if state == "alreadyComplete":
            outcome_box["sign"] = "alreadyComplete"
            return state, detail, None
        if outcome_box["sign"] == "success":
            # 上游以首次成功或确认为准
            return "success", "首次签到已成功，确认未返回已签到提示", None
        raise SafeError(detail)

    runner.stage(4, "确认签到状态", confirm_stage)

    def points_stage():
        accrued, total = query_points(token_box["token"], timeout)
        if accrued is None and total is None:
            return "skipped", "积分查询失败（不影响签到判定）", None
        detail = "积分：当前 {} ｜ 累计 {}".format(
            total if total is not None else "未知",
            accrued if accrued is not None else "未知",
        )
        return "success", detail, None

    runner.stage(5, "查询积分", points_stage)
    runner.status = (
        "alreadyComplete" if outcome_box["sign"] == "alreadyComplete" else "success"
    )


PY_NOTIFY_RUNNER = r'''
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
            setattr(os, name, denied)
sys.path.insert(0, specification["directory"])
module = None
if specification["path"] is None:
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as error:
        sys.exit(3 if error.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", specification["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
sender = getattr(module, "send", None)
if not callable(sender):
    sys.exit(3)
result = sender(specification["title"], specification["body"])
sys.exit(1 if result is False else 0)
'''

JS_NOTIFY_RUNNER = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (input.dry_run) {
  const denied = () => { throw new Error('dry-run forbids network and external processes'); };
  require('net').Socket.prototype.connect = denied;
  require('dgram').createSocket = denied;
  for (const name of ['http', 'https']) {
    require(name).request = denied;
    require(name).get = denied;
  }
  require('tls').connect = denied;
  require('http2').connect = denied;
  const dns = require('dns');
  for (const key of Object.keys(dns)) if (typeof dns[key] === 'function') dns[key] = denied;
  for (const key of Object.keys(dns.promises)) if (typeof dns.promises[key] === 'function') dns.promises[key] = denied;
  const cp = require('child_process');
  for (const key of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) cp[key] = denied;
  require('worker_threads').Worker = denied;
  globalThis.fetch = denied;
}
Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
  .then(result => process.exit(result === false ? 1 : 0))
  .catch(() => process.exit(1));
'''


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = os.path.basename(__file__)
    identities = {
        CATALOG_ID,
        script,
        "msec_checkin.py",
        "candidate.py",
        "scripts/msec_checkin.py",
    }
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    from pathlib import Path

    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(
        ("python", directory / "notify.py")
        for directory in paths
        if (directory / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", directory / "sendNotify.js")
            for directory in paths
            if (directory / "sendNotify.js").is_file()
        )
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = (
            [sys.executable, "-c", PY_NOTIFY_RUNNER]
            if kind == "python"
            else [node, "-e", JS_NOTIFY_RUNNER]
        )
        try:
            result = subprocess.run(
                command,
                input=json.dumps(specification, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                log(
                    "通知：✅ 脱敏总结已交给青龙适配器"
                    + ("（断网保护启用）" if dry_run else "")
                )
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def account_label(index: int, account: Dict[str, str]) -> str:
    username = (account.get("username") or "").strip()
    if username:
        return username
    return "账号{}".format(index)


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("MSEC_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    captcha_token = env("MSEC_CAPTCHA_TOKEN")
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("MSEC_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        raw_accounts = env("MSEC_ACCOUNTS")
        if not raw_accounts:
            raise SafeError(
                "未配置 MSEC_ACCOUNTS；请按每行 令牌 或 用户名|密码 或 用户名|密码|令牌 填写"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("MSEC_ACCOUNTS 没有有效账号行")
        for item in accounts_data:
            if not item.get("token") and not (item.get("username") and item.get("password")):
                raise SafeError("存在缺少令牌且缺少用户名密码的账号行")
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number, account_label(number, item))
            accounts.append(runner)
            try:
                run_account(runner, item, captcha_token, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(runner.display()))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        state: sum(a.status == state for a in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
