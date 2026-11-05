#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ODDBA社区签到与任务领取
# cron: 21 0,12 * * *
#
# 来源：andywang425/oddba-looter src/oddba_looter/（MIT）
# https://github.com/andywang425/oddba-looter
# 提交：f40b923ca7ae06113df70e4c1dcdaa75aee56c65
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2026 andywang425
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
"""ODDBA（sns.oddba.cn）每日签到、累签宝箱与每日任务奖励领取（青龙独立维护版）。

功能清点（相对上游 oddba-looter）：
- 账号密码登录并校验页头 is_login
- 每日签到（已签到视为已完成成功）
- 领取累签宝箱
- 领取每日任务中 status=claimable 且未 claimed 的奖励
- 不自动点赞、评论、发帖、打赏、签到心情；不处理成长任务；不补签
- 去掉项目根 .env、磁盘会话缓存、loguru/curl_cffi/dotenv 仓库依赖
- 多账号：每行「用户名|密码」，仅在首个竖线处分割；兼容 ODDBA_USERNAME+ODDBA_PASSWORD
- ODDBA_DRY_RUN=1 完全断网预演；通知遵循 QINGLONG_NOTIFY 策略

建议 Cron：30 0,12 * * *（与上游 Linux 定时示例一致）。
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
            "d4d9e489b3cac0c4",
            "scripts/oddba_looter.py",
            "oddba_looter.py",
            "oddba_looter",
            "candidate.py",
            "output/candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import http.cookiejar
import importlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

TITLE = "ODDBA社区签到与任务领取"
CATALOG_ID = "d4d9e489b3cac0c4"
BASE_URL = "https://sns.oddba.cn"
COOKIE_DOMAIN = "sns.oddba.cn"
TOKEN_COOKIE = "lightsns_token"
HOME_PAGE = BASE_URL + "/"
SIGN_PAGE = BASE_URL + "/sign"
TASK_PAGE = BASE_URL + "/task-center"
LOGIN_ACTION = "/api/user/login"
HEADER_ACTION = "/api/pc/header/index"
SIGN_INIT = "/module/pc/page/jinsom-pc-page-default-sign/init"
SIGN_ACTION = "/api/user/checkin"
SIGN_TREASURE_ACTION = "/api/user/checkin-treasure"
TASK_INIT = "/api/task-center/init"
TASK_ACTION = "/api/task-center/claim"
READ_ONLY_PATHS = {HEADER_ACTION, SIGN_INIT, TASK_INIT}
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 2
RETRY_DELAY = 1.0
MAX_BYTES = 512 * 1024
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
FIXED_REWARD_NAMES = {"vip_days": "VIP 会员", "invite_code": "邀请码"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
HTML_TAG_RE = re.compile(r"<[^>]+>")


class SafeError(Exception):
    """可写入日志的脱敏业务/配置错误。"""


class RateLimitError(SafeError):
    """站点限流，本轮停止后续请求。"""


class UncertainResultError(SafeError):
    """写请求结果不确定，禁止盲目重发。"""


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def env_truthy(name: str) -> bool:
    return env(name).lower() in TRUE_VALUES


def now_ts() -> str:
    return time.strftime("%H:%M:%S")


def now_full() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(now_ts(), message), flush=True)


def banner_line(char: str = "═", width: int = 62) -> str:
    return char * width


def resolve_timeout() -> float:
    raw = env("ODDBA_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("ODDBA_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("ODDBA_TIMEOUT 须在 5 到 120 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少竖线分隔符；格式为 用户名|密码")
    username, password = text.split("|", 1)
    username = username.strip()
    # 密码只去掉首尾空白，保留内部内容；上游 .env 中密码可不 strip 首尾，这里统一 strip 一次
    password = password.strip()
    if not username or not password:
        raise SafeError("账号行用户名或密码为空")
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    return {"username": username, "password": password}


def load_accounts() -> List[Dict[str, str]]:
    raw = os.environ.get("ODDBA_ACCOUNTS", "")
    if raw is None:
        raw = ""
    lines = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(parse_account_line(text))
    if lines:
        return lines
    username = env("ODDBA_USERNAME")
    # 密码允许首尾空白有意义时仍建议用户避免；兼容上游取原值再判断空
    password_raw = os.environ.get("ODDBA_PASSWORD")
    password = "" if password_raw is None else password_raw
    if username or password.strip():
        if not username or not password:
            raise SafeError("单账号别名须同时提供 ODDBA_USERNAME 与 ODDBA_PASSWORD")
        return [{"username": username, "password": password}]
    raise SafeError("未配置 ODDBA_ACCOUNTS，或单账号别名 ODDBA_USERNAME/ODDBA_PASSWORD")


def strip_html(value: Any) -> str:
    if value is None:
        return ""
    text = HTML_TAG_RE.sub("", str(value))
    return " ".join(text.split()).strip()


def require_field(data: Dict[str, Any], key: str, expected: Any) -> Any:
    value = data.get(key)
    if expected is str and isinstance(value, str):
        return value
    if expected is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if expected is bool and isinstance(value, bool):
        return value
    if expected is dict and isinstance(value, dict):
        return value
    if expected is list and isinstance(value, list):
        return value
    raise SafeError("响应字段 {} 缺失或类型异常".format(key))


def require_success(result: Dict[str, Any], operation: str) -> None:
    code = result.get("code")
    if code != 1:
        message = result.get("msg") or "服务端未提供原因"
        if not isinstance(message, str):
            message = "服务端未提供原因"
        raise SafeError("{}失败（code={}）：{}".format(operation, code, compact(message)))


def compact(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def reward_amount(reward: Dict[str, Any]) -> Any:
    amount = reward.get("amount")
    if amount is None or isinstance(amount, bool):
        return None
    if isinstance(amount, (int, float, str)):
        return amount
    return None


def reward_detail(reward: Dict[str, Any]) -> str:
    kind = require_field(reward, "type", str)
    if kind == "invite_code":
        return "邀请码（内容已脱敏）"
    if kind == "user_title":
        title = strip_html(reward.get("title")) or "未知"
        return "头衔「{}」".format(title)
    name = strip_html(reward.get("name")) or FIXED_REWARD_NAMES.get(kind, "")
    if not name:
        name = "未知奖励（{}）".format(kind)
    qty = ""
    if kind == "vip_days" and reward.get("forever"):
        qty = "永久"
    else:
        amount = reward_amount(reward)
        if amount is not None and kind != "user_title":
            if kind == "currency":
                qty = "+{}".format(amount)
            elif kind == "vip_days":
                qty = "+{} 天".format(amount)
            else:
                qty = "×{}".format(amount)
    note = ""
    if kind == "currency":
        balance = reward.get("balance")
        if balance is not None:
            note = "现有 {}".format(balance)
    elif kind == "prop":
        left = reward.get("left")
        if left is not None:
            note = "剩余 {}".format(left)
    elif kind == "vip_days":
        if reward.get("forever"):
            note = "不再过期"
        else:
            until = strip_html(reward.get("until"))
            if until:
                note = "有效期至 {}".format(until)
    parts = [p for p in (name, qty) if p]
    detail = " ".join(parts)
    return "{}（{}）".format(detail, note) if note else detail


def show_rewards(data: Dict[str, Any], key: str) -> str:
    rewards = data.get(key)
    if not isinstance(rewards, list) or not rewards:
        return ""
    details: List[str] = []
    for item in rewards:
        if not isinstance(item, dict):
            continue
        try:
            details.append(reward_detail(item))
        except SafeError:
            continue
    return "，".join(details)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise SafeError("接口跳转已拒绝")


class ODDBAClient:
    def __init__(self, username: str, password: str, timeout: float, dry_run: bool = False) -> None:
        self.username = username
        self.password = password
        self.timeout = timeout
        self.dry_run = dry_run
        self._reauthenticated = False
        self._rate_limited = False
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(),
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
        )
        self.identity = ""

    def _install_token(self, token: str) -> None:
        # 先删除旧 Cookie，再写入新 token
        for cookie in list(self.cookie_jar):
            if cookie.name == TOKEN_COOKIE:
                self.cookie_jar.clear(cookie.domain, cookie.path, cookie.name)
        cookie = http.cookiejar.Cookie(
            version=0,
            name=TOKEN_COOKIE,
            value=token,
            port=None,
            port_specified=False,
            domain=COOKIE_DOMAIN,
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": ""},
            rfc2109=False,
        )
        self.cookie_jar.set_cookie(cookie)

    def _post(
        self,
        path: str,
        *,
        referer: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.dry_run:
            raise SafeError("断网预演禁止 HTTP 请求")
        if self._rate_limited:
            raise RateLimitError("站点已限流，本轮不再发送请求")
        read_only = path in READ_ONLY_PATHS
        retries = DEFAULT_RETRIES if read_only else 0
        body = None
        if data is not None:
            body = urllib.parse.urlencode(
                {k: "" if v is None else str(v) for k, v in data.items()}
            ).encode("utf-8")
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": referer,
        }
        url = BASE_URL + path
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with self.opener.open(req, timeout=self.timeout) as response:
                    status = getattr(response, "status", None) or response.getcode()
                    raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise SafeError("接口响应过大")
                if status == 429:
                    self._rate_limited = True
                    raise RateLimitError("站点返回 HTTP 429，已停止本轮请求，请稍后再运行")
                if not 200 <= int(status) < 300:
                    retryable = int(status) == 408 or int(status) >= 500
                    if retryable and attempt < retries:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    if retryable and not read_only:
                        raise UncertainResultError(
                            "HTTP {}，请求结果不确定：{}".format(status, path)
                        )
                    raise SafeError("HTTP {}：{}".format(status, path))
                try:
                    result = json.loads(raw.decode("utf-8"))
                except (UnicodeError, ValueError) as exc:
                    raise SafeError("接口未返回有效 JSON：{}".format(path)) from exc
                if not isinstance(result, dict):
                    raise SafeError("接口 JSON 信封不是对象：{}".format(path))
                if "code" not in result or not isinstance(result.get("code"), int):
                    raise SafeError("响应字段 code 缺失或类型异常")
                msg = result.get("msg")
                if msg is not None and not isinstance(msg, str):
                    raise SafeError("响应字段 msg 类型异常")
                return result
            except RateLimitError:
                raise
            except UncertainResultError:
                raise
            except SafeError:
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                if not read_only:
                    raise UncertainResultError("请求结果不确定，未自动重发：{}".format(path)) from exc
                raise SafeError("网络请求失败：{}".format(path)) from exc
        raise SafeError("网络请求失败：{}".format(path)) from last_error

    def _request(
        self,
        path: str,
        *,
        referer: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self._post(path, referer=referer, data=data)
        if result.get("code") == 401:
            if self._reauthenticated:
                raise SafeError("会话再次失效，本次不再自动登录，请在浏览器检查账号状态")
            self._reauthenticated = True
            log("⚠️ 会话已过期，重新认证一次后重发被拒绝的请求")
            self._login()
            result = self._post(path, referer=referer, data=data)
            if result.get("code") == 401:
                raise SafeError("重新认证后请求仍被拒绝，已停止")
        return result

    def _response_data(self, result: Dict[str, Any], operation: str) -> Dict[str, Any]:
        require_success(result, operation)
        data = result.get("data")
        if not isinstance(data, dict):
            raise SafeError("响应字段 data 缺失或类型异常")
        return data

    def _is_logged_in(self) -> bool:
        result = self._post(HEADER_ACTION, referer=HOME_PAGE)
        if result.get("code") == 401:
            return False
        data = self._response_data(result, "验证登录状态")
        logged_in = data.get("is_login")
        if not isinstance(logged_in, bool):
            raise SafeError("响应字段 is_login 缺失或类型异常")
        if logged_in:
            nick = strip_html(data.get("nickname"))
            uid = data.get("user_id")
            if nick:
                self.identity = nick
            elif isinstance(uid, int) and not isinstance(uid, bool):
                self.identity = str(uid)
        return logged_in

    def _login(self) -> None:
        for cookie in list(self.cookie_jar):
            if cookie.name == TOKEN_COOKIE:
                self.cookie_jar.clear(cookie.domain, cookie.path, cookie.name)
        result = self._post(
            LOGIN_ACTION,
            referer=HOME_PAGE,
            data={
                "account": self.username,
                "password": self.password,
                "captcha_token": "",
            },
        )
        if result.get("code") != 1:
            raise SafeError("登录失败，请检查账号密码或在浏览器中处理验证码")
        data = self._response_data(result, "登录")
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise SafeError("登录响应缺少 token")
        self._install_token(token)
        if not self._is_logged_in():
            raise SafeError("登录后仍未确认有效会话，已停止")

    def authenticate(self) -> None:
        self._login()

    def get_sign_state(self) -> Dict[str, Any]:
        return self._response_data(self._request(SIGN_INIT, referer=SIGN_PAGE), "初始化签到中心")

    def do_sign(self) -> Dict[str, Any]:
        return self._response_data(
            self._request(SIGN_ACTION, referer=SIGN_PAGE, data={"mark": "", "captcha_token": ""}),
            "每日签到",
        )

    def claim_treasure(self, day: int) -> Dict[str, Any]:
        return self._response_data(
            self._request(SIGN_TREASURE_ACTION, referer=SIGN_PAGE, data={"day": day}),
            "领取累签宝箱",
        )

    def get_task_state(self) -> Dict[str, Any]:
        return self._response_data(self._request(TASK_INIT, referer=TASK_PAGE), "初始化任务中心")

    def claim_task(self, group: str, task_id: Any) -> Dict[str, Any]:
        return self._response_data(
            self._request(
                TASK_ACTION,
                referer=TASK_PAGE,
                data={"group": group, "task_id": task_id},
            ),
            "领取每日任务奖励",
        )


class AccountStats:
    def __init__(self, index: int) -> None:
        self.index = index
        self.label = "账号{:02d}".format(index)
        self.identity = ""
        self.total = 0
        self.success = 0
        self.already = 0
        self.skipped = 0
        self.failed = 0
        self.status = "success"
        self.messages: List[str] = []
        self.started = time.monotonic()

    def note(self, kind: str, text: str) -> None:
        self.total += 1
        if kind == "success":
            self.success += 1
        elif kind == "alreadyComplete":
            self.already += 1
        elif kind == "skipped":
            self.skipped += 1
        else:
            self.failed += 1
            self.status = "failure"
        self.messages.append("{} {}".format(ICONS.get(kind, ""), text))

    def mark_partial(self) -> None:
        if self.failed and (self.success or self.already):
            self.status = "partial_success"
        elif self.failed:
            self.status = "failure"
        elif self.success or self.already:
            self.status = "success"
        else:
            self.status = "success"

    def elapsed(self) -> float:
        return time.monotonic() - self.started


def stage_header(account: AccountStats, stage_no: int, stage_total: int, name: str) -> float:
    log(
        "◆ {}：[{}/{}] {}".format(
            account.identity or account.label, stage_no, stage_total, name
        )
    )
    return time.monotonic()


def stage_result(ok: bool, text: str, started: float, already: bool = False) -> None:
    icon = "☑" if already else ("✓" if ok else "✗")
    elapsed = time.monotonic() - started
    log("└─ {} {}  {:.1f}s".format(icon, text, elapsed))


def confirm_claim(check: Callable[[], bool], label: str) -> bool:
    log("⚠️ {} 请求结果不确定，重新查询领取状态".format(label))
    try:
        confirmed = check()
    except RateLimitError:
        raise
    except SafeError as exc:
        log("{} 无法核验领取状态：{}".format(ICONS["failure"], compact(exc)))
        return False
    if confirmed:
        log("{} {} 已通过当前状态确认已领取".format(ICONS["success"], label))
    else:
        log("{} {} 尚未确认领取生效，本轮不再提交".format(ICONS["failure"], label))
    return confirmed


def run_sign(client: ODDBAClient, stats: AccountStats) -> Tuple[Dict[str, Any], bool]:
    started = stage_header(stats, 2, 4, "每日签到")
    try:
        state = client.get_sign_state()
        user = require_field(state, "user", dict)
        signed = require_field(user, "signed", bool)
        nick = strip_html(user.get("nickname"))
        uid = user.get("user_id")
        if nick:
            stats.identity = nick
            client.identity = nick
        elif isinstance(uid, int) and not isinstance(uid, bool):
            stats.identity = str(uid)
            client.identity = str(uid)
    except RateLimitError:
        raise
    except SafeError as exc:
        stage_result(False, "获取签到中心失败：{}".format(compact(exc)), started)
        stats.note("failure", "签到中心初始化失败")
        return {}, False

    if signed:
        stage_result(True, "今日已签到", started, already=True)
        stats.note("alreadyComplete", "今日已签到")
        return state, False

    try:
        data = client.do_sign()
    except RateLimitError:
        raise
    except UncertainResultError:
        log("⚠️ 签到请求结果不确定，重新查询签到中心")
        try:
            refreshed = client.get_sign_state()
            confirmed = require_field(require_field(refreshed, "user", dict), "signed", bool)
        except RateLimitError:
            raise
        except SafeError as exc:
            stage_result(False, "无法核验签到状态：{}".format(compact(exc)), started)
            stats.note("failure", "签到结果不确定且无法核验")
            return {}, False
        if confirmed:
            stage_result(True, "已通过状态确认今日已签到", started, already=True)
            stats.note("alreadyComplete", "签到核验已完成")
            return refreshed, False
        stage_result(False, "尚未确认签到生效，本轮不再提交", started)
        stats.note("failure", "签到未确认")
        return refreshed, False
    except SafeError as exc:
        stage_result(False, "签到失败：{}".format(compact(exc)), started)
        stats.note("failure", "签到失败")
        return state, False

    confirmed = data.get("signed") is True
    if not confirmed:
        stage_result(False, "服务端未确认签到生效", started)
        stats.note("failure", "签到未确认")
        return state, False
    detail = show_rewards(data, "granted")
    text = "签到成功" + ("，奖励：{}".format(detail) if detail else "")
    stage_result(True, text, started)
    stats.note("success", "签到成功")
    return state, True


def treasure_claimed(client: ODDBAClient, day: int) -> bool:
    for chest in require_field(client.get_sign_state(), "chests", list):
        if isinstance(chest, dict) and chest.get("day") == day:
            return require_field(chest, "claimed", bool)
    return False


def run_treasure(client: ODDBAClient, stats: AccountStats, state: Dict[str, Any], did_sign: bool) -> None:
    started = stage_header(stats, 3, 4, "累签宝箱")
    if not state:
        stage_result(False, "无签到状态，跳过累签宝箱", started)
        stats.note("failure", "累签宝箱缺少签到状态")
        return
    try:
        chests = require_field(state, "chests", list)
    except SafeError as exc:
        stage_result(False, "无法读取宝箱列表：{}".format(compact(exc)), started)
        stats.note("failure", "累签宝箱列表异常")
        return

    available: List[int] = []
    parse_failures = 0
    for chest in chests:
        if not isinstance(chest, dict):
            parse_failures += 1
            continue
        try:
            day = require_field(chest, "day", int)
            active = require_field(chest, "active", bool)
            claimed = require_field(chest, "claimed", bool)
            remain = require_field(chest, "remain", int)
        except SafeError:
            parse_failures += 1
            continue
        if not claimed and (active or (remain == 1 and did_sign)):
            available.append(day)

    if parse_failures:
        stats.note("failure", "累签宝箱有 {} 条结构异常".format(parse_failures))

    if not available:
        if parse_failures:
            stage_result(False, "暂无可领取宝箱，且存在结构异常", started)
        else:
            stage_result(True, "暂无可领取奖励", started, already=True)
            stats.note("alreadyComplete", "累签宝箱暂无可领")
        return

    claimed_any = False
    for day in available:
        try:
            data = client.claim_treasure(day)
        except RateLimitError:
            raise
        except UncertainResultError:
            if confirm_claim(lambda d=day: treasure_claimed(client, d), "累签宝箱·{} 天".format(day)):
                claimed_any = True
                stats.note("success", "{} 天宝箱（核验已领取）".format(day))
            else:
                stats.note("failure", "{} 天宝箱领取未确认".format(day))
            continue
        except SafeError as exc:
            stats.note("failure", "{} 天宝箱失败：{}".format(day, compact(exc)))
            continue
        detail = show_rewards(data, "rewards")
        claimed_any = True
        stats.note(
            "success",
            "{} 天宝箱领取成功{}".format(day, "：" + detail if detail else ""),
        )
    if claimed_any and stats.failed == 0:
        stage_result(True, "累签宝箱处理完成", started)
    elif claimed_any:
        stage_result(False, "累签宝箱部分失败", started)
    else:
        stage_result(False, "累签宝箱领取失败", started)


def daily_items(state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    sections = require_field(state, "sections", list)
    items: List[Dict[str, Any]] = []
    found_daily = False
    failures = 0
    for section in sections:
        if not isinstance(section, dict):
            failures += 1
            continue
        key = section.get("key")
        if not isinstance(key, str):
            failures += 1
            continue
        if key != "daily":
            continue
        found_daily = True
        section_items = section.get("items")
        if not isinstance(section_items, list):
            failures += 1
            continue
        for item in section_items:
            if not isinstance(item, dict):
                failures += 1
                continue
            try:
                if not isinstance(item.get("group"), str):
                    raise SafeError("group")
                tid = item.get("id")
                if not (isinstance(tid, str) or (isinstance(tid, int) and not isinstance(tid, bool))):
                    raise SafeError("id")
                if not isinstance(item.get("name"), str):
                    raise SafeError("name")
                if not isinstance(item.get("status"), str):
                    raise SafeError("status")
                if not isinstance(item.get("claimed"), bool):
                    raise SafeError("claimed")
            except SafeError:
                failures += 1
                continue
            items.append(item)
    if not found_daily:
        raise SafeError("任务中心缺少 daily 分组，不能确认每日任务状态")
    return items, failures


def task_claimed(client: ODDBAClient, group: str, task_id: Any) -> bool:
    items, _ = daily_items(client.get_task_state())
    return any(item["group"] == group and item["id"] == task_id and item["claimed"] for item in items)


def run_task(client: ODDBAClient, stats: AccountStats) -> None:
    started = stage_header(stats, 4, 4, "每日任务奖励")
    try:
        items, parse_failures = daily_items(client.get_task_state())
    except RateLimitError:
        raise
    except SafeError as exc:
        stage_result(False, "获取任务中心失败：{}".format(compact(exc)), started)
        stats.note("failure", "任务中心初始化失败")
        return

    if parse_failures:
        stats.note("failure", "每日任务有 {} 条结构异常".format(parse_failures))

    claimable = [t for t in items if t["status"] == "claimable" and not t["claimed"]]
    if not claimable:
        if parse_failures:
            stage_result(False, "暂无可领取奖励，且存在结构异常", started)
        else:
            stage_result(True, "暂无可领取奖励", started, already=True)
            stats.note("alreadyComplete", "每日任务暂无可领")
        return

    claimed = 0
    for task in claimable:
        group, task_id, name = task["group"], task["id"], task["name"]
        try:
            data = client.claim_task(group, task_id)
        except RateLimitError:
            raise
        except UncertainResultError:
            if confirm_claim(
                lambda g=group, i=task_id: task_claimed(client, g, i),
                "每日任务·{}".format(name),
            ):
                claimed += 1
                stats.note("success", "领取「{}」（核验已领取）".format(name))
            else:
                stats.note("failure", "领取「{}」未确认".format(name))
            continue
        except SafeError as exc:
            stats.note("failure", "领取「{}」失败：{}".format(name, compact(exc)))
            continue
        claimed += 1
        detail = show_rewards(data, "rewards")
        stats.note(
            "success",
            "领取「{}」成功{}".format(name, "：" + detail if detail else ""),
        )
    if claimed and stats.failed == 0:
        stage_result(True, "领取 {} 项每日任务奖励".format(claimed), started)
    elif claimed:
        stage_result(False, "每日任务部分领取失败", started)
    else:
        stage_result(False, "每日任务奖励领取失败", started)


def run_account_dry(stats: AccountStats, username: str) -> None:
    t0 = stage_header(stats, 1, 4, "参数校验")
    stage_result(True, "用户名已配置（长度 {}）".format(len(username)), t0)
    stats.note("success", "参数校验通过")
    t1 = stage_header(stats, 2, 4, "登录验证")
    stage_result(True, "dry-run 跳过登录与会话校验", t1)
    stats.note("skipped", "登录（预演跳过）")
    t2 = stage_header(stats, 3, 4, "每日签到与累签宝箱")
    stage_result(True, "dry-run 已跳过签到与宝箱副作用", t2)
    stats.note("skipped", "签到与宝箱（预演跳过）")
    t3 = stage_header(stats, 4, 4, "每日任务奖励")
    stage_result(True, "dry-run 已跳过任务领取副作用", t3)
    stats.note("skipped", "每日任务（预演跳过）")
    stats.identity = stats.label
    stats.status = "dry-run"


def run_account_live(stats: AccountStats, account: Dict[str, str], timeout: float) -> None:
    client = ODDBAClient(account["username"], account["password"], timeout=timeout)
    t0 = stage_header(stats, 1, 4, "登录验证")
    try:
        client.authenticate()
        if client.identity:
            stats.identity = client.identity
        stage_result(
            True,
            "登录成功{}".format(
                "，昵称 {}".format(stats.identity) if stats.identity else ""
            ),
            t0,
        )
        stats.note("success", "登录成功")
    except RateLimitError:
        raise
    except SafeError as exc:
        stage_result(False, compact(str(exc)), t0)
        stats.note("failure", "登录失败")
        stats.mark_partial()
        return

    try:
        state, did_sign = run_sign(client, stats)
        if state:
            run_treasure(client, stats, state, did_sign)
        else:
            t = stage_header(stats, 3, 4, "累签宝箱")
            stage_result(False, "因签到状态缺失已跳过", t)
            stats.note("skipped", "累签宝箱因签到失败跳过")
        run_task(client, stats)
    except RateLimitError:
        raise
    finally:
        if client.identity and not stats.identity:
            stats.identity = client.identity
    stats.mark_partial()


def send_qinglong_notify(title: str, content: str) -> str:
    switch = env("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE_VALUES:
        return "已关闭"
    if switch in TRUE_VALUES or switch in {"", "auto"}:
        pass
    else:
        # 未知值按 auto 处理；auto 时若未设 QINGLONG_NOTIFY 已在文件头改写
        if switch != "auto":
            return "已关闭"
    try:
        try:
            sender = importlib.import_module("notify").send
        except (ImportError, AttributeError):
            paths: List[Path] = []
            notify_dir = env("QINGLONG_NOTIFY_DIR")
            if notify_dir:
                paths.append(Path(notify_dir) / "notify.py")
            paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise RuntimeError("notify.py not found")
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            if spec is None or spec.loader is None:
                raise RuntimeError("notify load failed")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = module.send
        sender(title, content)
        return "已发送"
    except Exception:
        log("{} 通知不可用或发送失败，保留业务退出码".format(ICONS["warning"]))
        return "不可用或失败"


def print_account_summary(stats: AccountStats) -> None:
    log("◆ {}：生成账号结果".format(stats.identity or stats.label))
    if stats.status == "dry-run":
        summary = "预演完成：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            stats.success, stats.already, stats.skipped, stats.failed
        )
        icon = "!"
    elif stats.failed and (stats.success or stats.already):
        summary = "部分成功：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            stats.success, stats.already, stats.skipped, stats.failed
        )
        icon = "!"
    elif stats.failed:
        summary = "失败：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            stats.success, stats.already, stats.skipped, stats.failed
        )
        icon = "✗"
    else:
        summary = "成功：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            stats.success, stats.already, stats.skipped, stats.failed
        )
        icon = "✓"
    log("└─ {} {}  耗时 {:.1f}s".format(icon, summary, stats.elapsed()))


def main() -> int:
    started_at = now_full()
    started_mono = time.monotonic()
    dry_run = env_truthy("ODDBA_DRY_RUN")
    mode = "DRY-RUN" if dry_run else "LIVE"

    print(TITLE, flush=True)
    print(banner_line(), flush=True)
    print("运行模式  {}".format(mode), flush=True)

    try:
        accounts = load_accounts()
        timeout = resolve_timeout()
    except SafeError as exc:
        print("账号数量  0", flush=True)
        print("开始时间  {}".format(started_at), flush=True)
        print(banner_line(), flush=True)
        log("{} 配置错误：{}".format(ICONS["failure"], compact(exc)))
        notify_status = send_qinglong_notify(
            TITLE,
            "配置错误：{}\n账号总数 0\n成功 0\n失败 0\n模式 {}".format(compact(exc), mode),
        )
        finish = now_full()
        print(banner_line("═"), flush=True)
        print("最终状态  配置错误", flush=True)
        print("通知状态  {}".format(notify_status), flush=True)
        print("完成时间  {}".format(finish), flush=True)
        print(banner_line(), flush=True)
        summary = {
            "status": "configuration_error",
            "exitCode": 2,
            "mode": "dry-run" if dry_run else "live",
            "accountTotal": 0,
            "accountSuccess": 0,
            "accountFailed": 0,
            "notifyStatus": notify_status,
            "catalogId": CATALOG_ID,
        }
        print("TASK_SUMMARY={}".format(json.dumps(summary, ensure_ascii=False, separators=(",", ":"))), flush=True)
        return 2

    print("账号数量  {}".format(len(accounts)), flush=True)
    print("开始时间  {}".format(started_at), flush=True)
    print(banner_line(), flush=True)

    results: List[AccountStats] = []
    rate_limited = False
    for idx, account in enumerate(accounts, start=1):
        stats = AccountStats(idx)
        print("", flush=True)
        try:
            if dry_run:
                run_account_dry(stats, account["username"])
            else:
                run_account_live(stats, account, timeout)
        except RateLimitError as exc:
            rate_limited = True
            log("{} {}".format(ICONS["failure"], compact(exc)))
            stats.note("failure", "站点限流中止")
            stats.status = "failure"
            results.append(stats)
            print_account_summary(stats)
            # 限流后不再处理后续账号
            for rest_idx in range(idx + 1, len(accounts) + 1):
                skipped = AccountStats(rest_idx)
                skipped.note("skipped", "因站点限流未执行")
                skipped.status = "failure"
                results.append(skipped)
                print_account_summary(skipped)
            break
        except SafeError as exc:
            stats.note("failure", compact(exc))
            stats.status = "failure"
        except Exception:
            stats.note("failure", "未预期错误（已脱敏）")
            stats.status = "failure"
        results.append(stats)
        print_account_summary(stats)

    account_success = sum(1 for r in results if r.status in {"success", "dry-run"})
    account_partial = sum(1 for r in results if r.status == "partial_success")
    account_failed = sum(1 for r in results if r.status == "failure")
    task_total = sum(r.total for r in results)
    task_success = sum(r.success for r in results)
    task_already = sum(r.already for r in results)
    task_skipped = sum(r.skipped for r in results)
    task_failed = sum(r.failed for r in results)

    if dry_run:
        final_status = "dry-run"
        exit_code = 0
    elif rate_limited:
        final_status = "failure"
        exit_code = 2
    elif account_failed == 0 and account_partial == 0:
        final_status = "success"
        exit_code = 0
    elif account_success > 0 or account_partial > 0:
        final_status = "partial_success"
        exit_code = 1
    else:
        final_status = "failure"
        exit_code = 1

    body_lines = [
        "账号总数 {}".format(len(results)),
        "成功 {}".format(account_success),
        "部分成功 {}".format(account_partial),
        "失败 {}".format(account_failed),
        "子任务 成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            task_success, task_already, task_skipped, task_failed
        ),
        "最终状态 {}".format(final_status),
        "模式 {}".format(mode),
    ]
    notify_event = (
        "dry-run"
        if dry_run
        else (
            "success"
            if final_status == "success"
            else ("partial-failure" if final_status == "partial_success" else "failure")
        )
    )
    notify_status = send_qinglong_notify(TITLE, "\n".join(body_lines))
    finish = now_full()
    elapsed = time.monotonic() - started_mono

    print("", flush=True)
    print("════════════════════════ 任务统计 ════════════════════════════", flush=True)
    print("最终状态  {}".format(final_status), flush=True)
    print(
        "账号统计  总数 {} │ 成功 {} │ 部分成功 {} │ 失败 {}".format(
            len(results), account_success, account_partial, account_failed
        ),
        flush=True,
    )
    print(
        "任务统计  总数 {} │ 成功 {} │ 已完成 {} │ 跳过 {} │ 失败 {}".format(
            task_total, task_success, task_already, task_skipped, task_failed
        ),
        flush=True,
    )
    print("通知状态  {}".format(notify_status), flush=True)
    print("总耗时    {:.1f} 秒".format(elapsed), flush=True)
    print("完成时间  {}".format(finish), flush=True)
    print(banner_line(), flush=True)

    summary = {
        "status": final_status,
        "exitCode": exit_code,
        "mode": "dry-run" if dry_run else "live",
        "accountTotal": len(results),
        "accountSuccess": account_success,
        "accountPartialSuccess": account_partial,
        "accountFailed": account_failed,
        "taskTotal": task_total,
        "taskSuccess": task_success,
        "taskAlreadyComplete": task_already,
        "taskSkipped": task_skipped,
        "taskFailed": task_failed,
        "notifyStatus": notify_status,
        "notifyEvent": notify_event,
        "elapsedSeconds": round(elapsed, 3),
        "catalogId": CATALOG_ID,
    }
    print(
        "TASK_SUMMARY={}".format(json.dumps(summary, ensure_ascii=False, separators=(",", ":"))),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
