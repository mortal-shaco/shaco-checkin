#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AI 积分签到
# cron: 25 8,11,14,17,20,23 * * *
# 上游 huxc573/AICreditPunch，checkin.py v1.9.2，MIT
# https://github.com/huxc573/AICreditPunch
# 来源提交 1f5823ebc42b9b68340801cb0c61af66da2a8dc8
"""独立青龙账号任务。AICREDIT_ACCOUNTS 每个非空行一个 JSON 对象。
WorkBuddy 设置 platform=workbuddy、access_token，可选 uid/domain/enterprise_id/api_base。
Trae 设置 platform=trae、accessToken、refreshToken、userId、deviceId，可选
expiresAt（秒）、claimDeviceId、fingerprint（brand/type/os）。只使用本人授权的凭据。
从官方已登录会话的请求头或本人登录授权响应复制相应字段，填入青龙敏感环境变量。
AICREDIT_DRY_RUN=1 完全离线。--status-only 只查询，--workbuddy-only / --trae-only 选择平台。
没有本机应用、其他仓库或私有文件依赖，不保存刷新后的凭据。

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('ed929736b882170c', 'scripts/task_ed929736.py', 'task_ed929736.py', 'task_ed929736')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import fnmatch
import json
import math
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.9.2-maintained"
DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 2
PLATFORM_WORKBUDDY = "WorkBuddy"
PLATFORM_TRAE = "Trae"
WB_ACCOUNT_LABEL = "WorkBuddy账号"
_LOG_BUFFER = threading.local()
DRY_RUN = False
SECRET_VALUES = set()


def log(message):
    text = str(message)
    for secret in sorted(SECRET_VALUES, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    text = text.replace("\r", " ").replace("\n", " ")
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def env_bool(name, default=False):
    return os.environ.get(name, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError("整数设置格式错误") from None
    if not minimum <= value <= maximum:
        raise ValueError("整数设置超出允许范围")
    return value


def clean_text(value):
    return str(value or "").strip()


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _business_ok(payload):
    if not isinstance(payload, dict) or payload.get("success") is False:
        return False
    if "code" in payload:
        return type(payload["code"]) is not bool and payload["code"] in (0, 200, "0", "200")
    return payload.get("success") is True


def _code_of(payload):
    return payload.get("code") if isinstance(payload, dict) else None


def _msg_of(payload):
    # 只转译已知业务状态，服务端原文可能夹带凭据或个人信息。
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    nested = data.get("message") if isinstance(data, dict) else ""
    message = str(payload.get("message") or payload.get("msg") or nested or "").lower()
    words = ("已签到", "已经签到", "已领取", "今日已领取", "明日再来", "already checked", "already claimed")
    return "已签到" if any(word in message for word in words) else ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def show_identity(payload):
    nodes = [payload]
    for key in ("data", "Result", "user", "userInfo", "account"):
        if isinstance(payload.get(key), dict):
            nodes.append(payload[key])
    for node in nodes:
        for key in ("nickname", "username", "displayName", "screenName", "ScreenName", "public_uid"):
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                log(f"官方账号身份 {value}")
                return


def http_post(url, headers, body, timeout, retries, proxy=""):
    if DRY_RUN:
        raise RuntimeError("离线预演禁止 HTTP 请求")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None, None, "请求地址校验失败"
    # 禁止自动重定向，避免鉴权头被带往其他主机。
    opener = urllib.request.build_opener(NoRedirect())
    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries + 1):
        began = time.monotonic()
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    return response.status, None, "响应超出大小限制"
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    return response.status, None, "响应结构错误"
                protect_values(payload)
                show_identity(payload)
                log(f"请求 {parsed.path} HTTP={response.status} 耗时={time.monotonic()-began:.2f}秒")
                return response.status, payload, None
        except urllib.error.HTTPError as exc:
            log(f"请求 {parsed.path} HTTP={exc.code} 耗时={time.monotonic()-began:.2f}秒")
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries:
                return exc.code, None, f"HTTP {exc.code}"
        except (OSError, ValueError, urllib.error.URLError):
            log(f"请求 {parsed.path} 网络或响应解析失败 耗时={time.monotonic()-began:.2f}秒")
            if attempt == retries:
                return None, None, "网络或响应解析失败"
        time.sleep(min(8, 2 ** attempt))
    return None, None, "请求失败"


def _num_of(value: Any) -> Optional[float]:
    """把报文里的数值字段转成 float：兼容数字与 `"146.6800001"` 这类字符串。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text) if math.isfinite(float(text)) else None
    except ValueError:
        return None


def _fmt_num(value: Any) -> str:
    """积分数字文案：整数值不带小数（`2,100`），非整数保留两位（`146.68`）。"""
    num = _num_of(value)
    if num is None:
        return str(value)
    num = round(num, 2)
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.2f}"


def _int_of(value: Any) -> Optional[int]:
    """整数取值：bool / 非数值一律 None（`0` 原样返回，是否省略交给调用方）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _md_of(value: Any) -> str:
    """报文时间戳取月日：`2026-09-16 00:00:00` → `09-16`；识别不了返回空串。"""
    text = clean_text(value)
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[5:10]
    return ""


def _date_of(value: Any) -> Optional[date]:
    """报文时间戳取日期；识别不了返回 None。"""
    try:
        return datetime.strptime(clean_text(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _window_note(active: Any, end: Any, today: Optional[date] = None) -> str:
    """活动窗口补充说明：`（剩13天，进行中）` / `（今天截止）` / `（已结束）`；无可用信息返回空串。"""
    notes: List[str] = []
    stop = _date_of(end)
    if stop is not None:
        left = (stop - (today or date.today())).days
        if left > 0:
            notes.append(f"剩{left}天")
        elif left == 0:
            notes.append("今天截止")
    if isinstance(active, bool):
        notes.append("进行中" if active else "已结束")
    return f"（{'，'.join(notes)}）" if notes else ""


def _fmt_credit(today: Optional[int] = None, balance: Any = None) -> str:
    """积分明细文本（中文）；字段缺失自动省略，保证两个平台写法一致。"""
    items = []
    if today is not None:
        items.append(f"本次 +{_fmt_num(today)}")
    if balance is not None:
        items.append(f"余额{_fmt_num(balance)}")
    return "，".join(items)


def _line(state: str, detail: str = "") -> str:
    """日志正文：`{状态}；{明细}`。"""
    return state + (f"；{detail}" if detail else "")


def _result(platform: str, name: str, state: str, detail: str = "") -> str:
    """对外结果文案（通知正文）：`[{平台}] {账号名} {状态}；{明细}`，一个账号一行。"""
    return f"[{platform}] {name} {state}" + (f"；{detail}" if detail else "")


WB_BASE_URL = "https://www.codebuddy.cn"
WB_ROUTE_STATUS = "/v2/billing/meter/checkin-activity-status"
WB_ROUTE_CLAIM = "/v2/billing/meter/daily-checkin"

# api_base 只允许这些域名：token 是 Bearer 裸传，绝不能发到第三方地址
WB_ALLOWED_HOSTS = frozenset({"codebuddy.cn", "workbuddy.cn", "copilot.tencent.com"})
WB_ALLOWED_SUFFIXES = (".codebuddy.cn", ".workbuddy.cn")

WB_ALREADY_CODE = 10001
WB_ALREADY_WORDS = ("已签到", "已经签到", "already checked", "already claimed")
WB_CHECKED_FLAGS = ("today_checked_in", "checked_in", "checkedIn", "claimed")
WB_TODAY_CREDIT_KEYS = ("daily_credit", "today_credit")
WB_STREAK_KEY = "streak_days"
WB_STREAK_BONUS_KEY = "streak_bonus_credit"
WB_DATES_KEY = "checkin_dates"
WB_ACTIVITY_NAME_KEY = "activity_name"
WB_SEASON_KEY = "season"
WB_START_KEY = "start_time"
WB_END_KEY = "end_time"
WB_ACTIVE_KEY = "active"
WB_REQUEST_ID_KEY = "requestId"
WB_ACCOUNT_LABEL = "WorkBuddy账号"

# 账号真实可用积分（与桌面端「设置 - 套餐与积分」同源）。
# 注意这三条路由**不带 `/v2`** 前缀，与签到那两条不同；网关前缀差异见客户端注释。
WB_ROUTE_RESOURCE_SUMMARY = "/billing/meter/get-user-resource-summary"
WB_ROUTE_FREE_PACKAGES = "/billing/meter/get-user-resource-free-packages"
WB_ROUTE_PAID_PACKAGES = "/billing/meter/get-user-resource-paid-packages"
WB_PACKAGE_STATUS = [0, 3]          # 0=有效、3=已用尽（与桌面端请求体一致）
WB_PACKAGE_PAGE_SIZE = 100
# 「平台奖励积分」的标识：赠送包（`sp_tcaca_codebuddyide_bonus_pack`）。
# 免费包列表里既有赠送包也有套餐本体（如 `sp_tcaca_codebuddy_ide` = 个人体验版），
# 不区分就会把套餐基础积分错算进平台奖励（实测踩过）。
WB_BONUS_MARK = "bonus_pack"


def wb_validated_base(value: Any) -> str:
    """校验并规范化 api_base；不在白名单的地址直接拒绝，避免 token 外泄。"""
    raw = clean_text(value) or WB_BASE_URL
    candidate = raw if "://" in raw else "https://" + raw
    parts = urllib.parse.urlparse(candidate)
    host = (parts.hostname or "").lower()
    allowed = host in WB_ALLOWED_HOSTS or host.endswith(WB_ALLOWED_SUFFIXES)
    if parts.scheme != "https" or not allowed or parts.username or parts.password or parts.port not in (None, 443) or parts.query or parts.fragment:
        raise ValueError("WorkBuddy API 地址校验失败")
    port = f":{parts.port}" if parts.port else ""
    return f"https://{host}{port}{parts.path.rstrip('/')}"


class WbReply:
    """一次调用的「HTTP 码 + 报文」的语义化解读。"""

    __slots__ = ("http", "payload", "transport_error")

    def __init__(self, http: Optional[int], payload: Any, transport_error: Optional[str]) -> None:
        self.http = http
        self.payload = payload if isinstance(payload, dict) else None
        self.transport_error = transport_error

    def _scope(self) -> Dict[str, Any]:
        """字段查找范围：优先 data 子对象，没有就退回顶层报文。"""
        data = (self.payload or {}).get("data")
        return data if isinstance(data, dict) else (self.payload or {})

    @property
    def code(self) -> Any:
        return (self.payload or {}).get("code")

    @property
    def message(self) -> str:
        return _msg_of(self.payload)

    @property
    def accepted(self) -> bool:
        """业务是否成功：code 缺省 / 0 / 200，且没有显式 `success: false`。"""
        return (self.http is not None and 200 <= self.http < 300 and
                self.transport_error is None and _business_ok(self.payload))

    @property
    def already_checked(self) -> bool:
        """今日是否已签到：专用 code、文案关键字、报文标记，命中任一即可。"""
        if self.payload is None or self.http is None or not 200 <= self.http < 300 or self.payload.get("success") is False:
            return False
        if str(self.code) == str(WB_ALREADY_CODE):
            return True
        text = self.message.lower()
        if any(word in text for word in WB_ALREADY_WORDS):
            return True
        scope = self._scope()
        for flag in WB_CHECKED_FLAGS:
            if flag not in scope:
                continue
            value = scope[flag]
            if isinstance(value, str):
                if value.lower() in {"true", "1"}:
                    return True
            elif value is True or (type(value) is int and value == 1):
                return True
        return False

    @property
    def paid_in(self) -> Tuple[Optional[int], Optional[int]]:
        """(本次基础积分, 连签奖励积分)；缺失一律 None。"""
        scope = self._scope()
        today = next((scope[key] for key in WB_TODAY_CREDIT_KEYS if scope.get(key) is not None), None)
        return _int_of(today), _int_of(scope.get(WB_STREAK_BONUS_KEY))

    @property
    def credit_text(self) -> str:
        """`本次 +100（含连签奖励 +50），余额…`；奖励为 0 或缺字段时不加括号。"""
        today, bonus = self.paid_in
        text = _fmt_credit(today=today)
        if bonus:
            text += f"（含连签奖励 +{_fmt_num(bonus)}）"
        return text

    @property
    def streak(self) -> Optional[int]:
        """本期连续签到天数（口径见 README §2.8：换期归零，跨期不累计）。"""
        return _int_of(self._scope().get(WB_STREAK_KEY))

    @property
    def checkin_days(self) -> Optional[int]:
        """本期已签到天数（`checkin_dates` 长度）；字段缺失 None。"""
        dates = self._scope().get(WB_DATES_KEY)
        return len(dates) if isinstance(dates, list) else None

    @property
    def activity_text(self) -> str:
        """本期活动：`高校新生攻略 第9期 09-16~09-29（剩13天，进行中）`；字段缺失逐项省略。"""
        scope = self._scope()
        title = clean_text(scope.get(WB_ACTIVITY_NAME_KEY))
        season = _int_of(scope.get(WB_SEASON_KEY))
        head = " ".join(p for p in (title, f"第{season}期" if season else "") if p)
        start, end = _md_of(scope.get(WB_START_KEY)), _md_of(scope.get(WB_END_KEY))
        window = f"{start}~{end}" if start and end else (end or start)
        note = _window_note(scope.get(WB_ACTIVE_KEY), scope.get(WB_END_KEY))
        return " ".join(p for p in (head, window) if p) + note

    @property
    def streak_text(self) -> str:
        """账号级的 `连签2/已签2`；字段缺失逐项省略（只在签到结算后用，见 `_settle`）。"""
        streak, days = self.streak, self.checkin_days
        return "/".join(p for p in [f"连签{streak}" if streak else "",
                                    f"已签{days}" if days else ""] if p)

    @property
    def request_id(self) -> str:
        """报文 requestId（顶层字段）：出错时便于自查与反馈；缺失返回空串。"""
        return ""

    @property
    def reason(self) -> str:
        """失败原因：优先报文里的 message，其次网络层错误。"""
        return self.transport_error or "业务响应未确认成功"


# 平台级活动行只打一次：同平台的账号看到的是同一期活动（同一份 `activity_name` / `season`），
# 每个账号再打一遍纯属重复。进程就是一次运行，所以这个标记不需要重置。
_ACTIVITY_SHOWN: List[str] = []
# 备好、待打印的活动行：并发跑时由主线程的收集循环随时打掉（要排在账号行前面）。
_ACTIVITY_PENDING: List[str] = []
# `_ACTIVITY_SHOWN` 的「查过没」与「记下来」要原子：并发下几个账号可能同时查到状态，
# 不锁的话这行会重复打。
_ACTIVITY_LOCK = threading.Lock()


class WorkBuddyClient:
    """一个账号的一次签到会话：发请求、把响应翻译成日志行与结果文案。"""

    def __init__(self, record: Dict[str, Any], timeout: int, retries: int) -> None:
        self.record = record
        self.timeout = timeout
        self.retries = retries
        self.name = clean_text(record.get("name")) or WB_ACCOUNT_LABEL
        self.base = wb_validated_base(record.get("api_base"))
        self._headers = self._build_headers()
        self._status: Optional[WbReply] = None      # 首次状态查询报文，供活动期字段兜底

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {clean_text(self.record.get('access_token'))}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"WorkBuddy-Checkin/{VERSION}",
        }
        uid = clean_text(self.record.get("uid"))
        if uid:
            headers["X-User-Id"] = uid
        domain = clean_text(self.record.get("domain"))
        if domain:
            headers["X-Domain"] = domain
        enterprise = clean_text(self.record.get("enterprise_id"))
        if enterprise:
            headers["X-Enterprise-Id"] = enterprise
            headers["X-Tenant-Id"] = enterprise
        return headers

    def _call(self, route: str) -> WbReply:
        http, payload, error = self._raw(route, {})
        return WbReply(http, payload, error)

    def _raw(self, route: str, body: Dict[str, Any]) -> Tuple[Optional[int], Any, Optional[str]]:
        """原样发一次 POST，返回 (HTTP 码, 报文, 传输层错误)。"""
        return http_post(self.base + route, self._headers, body, self.timeout, self.retries)

    def _packages_remain(self, route: str, codes: List[str], extra: Dict[str, Any],
                         sub_mark: str = "") -> Optional[float]:
        """某个资源包接口下各包剩余额度之和；取不到返回 None（不猜 0）。"""
        body: Dict[str, Any] = {
            "PageNumber": 1,
            "PageSize": WB_PACKAGE_PAGE_SIZE,
            "PackageCodes": codes,
            "Status": list(WB_PACKAGE_STATUS),
        }
        body.update(extra)
        _, payload, _ = self._raw(route, body)
        if not _business_ok(payload):
            return None
        data = (payload or {}).get("data") if isinstance(payload, dict) else None
        accounts = data.get("Accounts") if isinstance(data, dict) else None
        if not isinstance(accounts, list):
            return None
        total = 0.0
        for item in accounts:
            if not isinstance(item, dict):
                continue
            if sub_mark and sub_mark not in (clean_text(item.get("SubProductCode")) or "").lower():
                continue
            num = _num_of(item.get("CycleCapacityRemainPrecise"))
            if num is None:
                num = _num_of(item.get("CycleCapacityRemain"))
            if num is not None:
                total += num
        return total

    def balance(self) -> Tuple[Optional[str], Optional[str]]:
        """账号真实可用积分，返回 (余额文本, 构成文本)；查不到一律 (None, None)。"""
        _, payload, _ = self._raw(WB_ROUTE_RESOURCE_SUMMARY, {})
        if not _business_ok(payload):
            return None, None
        data = (payload or {}).get("data") if isinstance(payload, dict) else None
        packages = data.get("Packages") if isinstance(data, dict) else None
        if not isinstance(packages, list) or not packages:
            return None, None
        remains = [_num_of(p.get("CycleRemainCapacity")) for p in packages if isinstance(p, dict)]
        remains = [r for r in remains if r is not None]
        if not remains:
            return None, None
        total = sum(remains)
        codes = [clean_text(p.get("PackageCode")) for p in packages if isinstance(p, dict)]
        codes = [c for c in codes if c]
        text = _fmt_num(total)
        if not codes:
            return text, None

        reward = self._packages_remain(WB_ROUTE_FREE_PACKAGES, codes, {}, WB_BONUS_MARK)
        paid = self._packages_remain(WB_ROUTE_PAID_PACKAGES, codes, {"NeedRenewInfo": True})
        if reward is None or paid is None:
            return text, None
        base = total - reward - paid
        if base < 0:                      # 口径对不上就不报构成，避免误导
            return text, None
        parts = [("套餐", base), ("奖励", reward), ("购买", paid)]
        return text, ("+".join(f"{k}{_fmt_num(v)}" for k, v in parts if v) or None)

    def _say(self, state: str, detail: str = "") -> None:
        log(f"[{self.name}] {_line(state, detail)}")

    @staticmethod
    def _outcome(ok: bool, name: str, state: str, detail: str = "") -> Tuple[bool, str]:
        return ok, _result(PLATFORM_WORKBUDDY, name, state, detail)

    def check_in(self, status_only: bool) -> Tuple[bool, str]:
        status = self._call(WB_ROUTE_STATUS)
        self._status = status
        # 平台级活动行打在每个平台的第一行位置；整轮只打一次（见 `_ACTIVITY_SHOWN`）。
        self._say_activity(status)

        if status.already_checked:
            return self._settle("不重签", status)

        if status.accepted:
            # 正常流程不报「未签到」：紧接着的结算行（`签到成功；连签…；本次 +100`）本来就说清了，
            # 多一行只是噪声；只查不领没有结算行，那一句才有用。
            if status_only:
                self._say("今日未签到", status.credit_text)
        else:
            self._say("状态查询异常", self._err_text(status))
            return self._outcome(False, self.name, "状态查询失败，停止领取")

        if status_only:
            # 只查不领：活动行已在上面打过，连续天数此时还是签到前的旧值（会少一天），不打
            return self._outcome(True, self.name, "待签到")
        return self._claim()

    def _claim(self) -> Tuple[bool, str]:
        claim = self._call(WB_ROUTE_CLAIM)
        if claim.already_checked:
            return self._settle("不重签", claim)
        if not claim.accepted:
            self._say("签到失败", self._err_text(claim))
            return self._outcome(False, self.name, "签到失败", claim.reason[:80])

        # 接口受理不等于到账：回查一次状态才算真的签到成功。
        verify = self._call(WB_ROUTE_STATUS)
        if verify.already_checked:
            return self._settle("签到成功", verify)
        return self._outcome(False, self.name, "领取后回查未确认签到")

    @staticmethod
    def _say_activity(reply: WbReply) -> None:
        """平台级活动行（`WorkBuddy 本期活动；…`），整轮只打一次；字段全缺则不打这行。

        这行是平台级的、要排在各账号行前面：并发跑时只备好文案，由主线程的收集循环
        （`_map_accounts` 里的 `_flush_pending_activity`）先打掉；串行跑就直接打，位置天然正确。
        """
        detail = reply.activity_text
        with _ACTIVITY_LOCK:
            if not detail or _ACTIVITY_SHOWN:
                return
            _ACTIVITY_SHOWN.append(detail)
            text = f"{PLATFORM_WORKBUDDY} " + _line("本期活动", detail)
            if getattr(_LOG_BUFFER, "lines", None) is not None:
                _ACTIVITY_PENDING.append(text)
            else:
                log(text)

    @staticmethod
    def _err_text(reply: WbReply) -> str:
        """异常行：HTTP 码 + 业务码 + 原因（+ requestId，便于自查与向官方反馈）。"""
        text = f"HTTP={reply.http} code={reply.code} {reply.reason}"
        return f"{text} requestId={reply.request_id}" if reply.request_id else text

    def _settle(self, state: str, reply: WbReply) -> Tuple[bool, str]:
        """已签到 / 签到成功：打本账号的状态、连签天数与积分明细（活动行已在 `check_in` 打过）。"""
        balance, compose = self.balance()
        parts = [reply.credit_text]
        if balance:
            parts.append(f"余额{balance}")
        detail = "，".join(p for p in parts if p)
        # 日志：连签（账号级）与构成都接在同一行（连签自成一段，用 `；` 与明细隔开）；
        # 通知只要明细 —— 连签是当期活动口径，余额拆解也不该塞进推送。
        log_detail = "；".join(p for p in [reply.streak_text, detail] if p)
        if compose:
            log_detail += f"（{compose}）"
        self._say(state, log_detail)
        return self._outcome(True, self.name, state, detail)


TRAE_CLIENT_ID = "en1oxy7wnw8j9n"
TRAE_IDE_VERSION = "0.1.43"
TRAE_API_BASE = "https://api.trae.cn"
TRAE_EXCHANGE_HOST = "https://api.trae.com.cn"
TRAE_LOGIN_HOST = "https://www.trae.cn"
TRAE_EXCHANGE_URL = TRAE_EXCHANGE_HOST + "/cloudide/api/v3/trae/oauth/ExchangeToken"
TRAE_STATUS_URL = TRAE_API_BASE + "/trae/api/v2/ug/checkin_credits/status"
TRAE_CLAIM_URL = TRAE_API_BASE + "/trae/api/v2/ug/checkin_credits/claim"
TRAE_CREDITS_URL = TRAE_API_BASE + "/trae/api/v2/pay/ide_user_ent_usage"
TRAE_REFRESH_MARGIN = 24 * 3600
TRAE_CLAIM_RETRIES = 3

# 「今日是否已签到」的判读口径。实测 status 响应（未签到时）：
#   {"checked_in": false, "code": 0, "credits": 150, "did_checked_in": false,
#    "enable": true, "extra_credits": 50, "message": "success"}
# 注意 `code=0` 只代表「查询成功」——未签到时同样是 0。所以是否已签到必须
# 只看明确标记与明确文案，**绝不能用业务码兜底**（v1.7.0 及更早正是这么错的，
# 结果每次运行都判成「今日已签到」，claim 一次都没执行过）。
TRAE_CHECKED_FLAGS = ("checked_in", "did_checked_in", "today_checked_in", "is_checked_in")
TRAE_ALREADY_WORDS = ("已签到", "已经签到", "已领取", "今日已领取", "明日再来",
                      "already checked", "already claimed")
TRAE_CREDIT_KEYS = ("credits", "today_credit", "daily_credit", "sign_credit", "reward_credit",
                    "credit", "reward", "score", "points",
                    "obtain_credit", "get_credit", "add_credit", "grant_credit")
# 领奖后回查确认的等待节奏（0 = 立即回查一次，再等 4s 回查一次）
TRAE_VERIFY_WAITS = (0, 4)


def _trae_headers(acc: Dict[str, Any], device_id: str) -> Dict[str, str]:
    fp = acc.get("fingerprint") or {}
    brand = clean_text(fp.get("brand")) or "Apple"
    dev_type = clean_text(fp.get("type")) or "mac"
    os_version = clean_text(fp.get("os")) or "macOS"
    return {
        "Content-Type": "application/json",
        "Authorization": f"Cloud-IDE-JWT {acc['accessToken']}",
        "x-device-id": device_id,
        "X-Device-Id": device_id,
        "X-User-Region": "CN",
        "x-device-brand": brand,
        "x-device-type": dev_type,
        "x-os-version": os_version,
        "x-app-version": TRAE_IDE_VERSION,
        "User-Agent": f"Trae/{TRAE_IDE_VERSION}",
    }


def _trae_refresh(acc: Dict[str, Any]) -> bool:
    name = acc.get("screenName") or acc.get("userId") or "Trae账号"
    body = {
        "ClientID": TRAE_CLIENT_ID,
        "RefreshToken": acc["refreshToken"],
        "ClientSecret": "-",
        "UserID": acc.get("userId") or "",
    }
    status, payload, err = http_post(TRAE_EXCHANGE_URL, {"Content-Type": "application/json"}, body, DEFAULT_TIMEOUT, DEFAULT_RETRIES)
    if payload is None or ("code" in payload and not _business_ok(payload)):
        log(f"[{name}] {_line('token 刷新失败', str(err))}")
        return False
    data = payload.get("Result") if isinstance(payload.get("Result"), dict) else (payload.get("data") if isinstance(payload.get("data"), dict) else payload)
    tok = data.get("Token") or data.get("AccessToken") or data.get("access_token")
    if not tok:
        log(f"[{name}] {_line('token 刷新响应缺少 Token', str(_msg_of(payload)))}")
        return False
    acc["accessToken"] = tok
    if data.get("RefreshToken") or data.get("refresh_token") or data.get("refreshToken") or data.get("refreshToken"):
        acc["refreshToken"] = data.get("RefreshToken") or data.get("refresh_token") or data.get("refreshToken")
    exp = data.get("TokenExpireAt") or data.get("expiresAt")
    if exp:
        try:
            exp_v = float(exp)
            if exp_v > 1e12:
                exp_v /= 1000.0
            acc["expiresAt"] = exp_v
        except (TypeError, ValueError):
            pass
    return True


def _trae_flag(payload: Optional[Dict[str, Any]], keys: Tuple[str, ...]) -> Optional[bool]:
    """在 payload / payload.data 里按 keys 顺序找布尔标记；字段不存在返回 None。"""
    if not isinstance(payload, dict) or not _business_ok(payload):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else None
    for node in (payload, data):
        if not isinstance(node, dict):
            continue
        for key in keys:
            if key not in node:
                continue
            value = node[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                text = value.strip().lower()
                if text in ("true", "1", "yes"):
                    return True
                if text in ("false", "0", "no"):
                    return False
    return None


def _trae_status_checked(payload: Optional[Dict[str, Any]]) -> bool:
    """状态查询是否表示「今日已签到」。"""
    if not _business_ok(payload):
        return False
    flag = _trae_flag(payload, TRAE_CHECKED_FLAGS)
    if flag is not None:
        return flag
    msg = _msg_of(payload).lower()
    return any(word in msg for word in TRAE_ALREADY_WORDS)


def _trae_claim_ok(payload: Optional[Dict[str, Any]]) -> bool:
    """领奖调用是否成功：业务码成功，或明确说明今天已经领过。"""
    if _business_ok(payload):
        return True
    return _trae_status_checked(payload)


def _trae_pick_int(payload: Optional[Dict[str, Any]], *keys: str) -> Optional[int]:
    """从响应（支持 data 嵌套）里取第一个匹配 key 的整数字段。"""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    for d in (payload, data):
        if not isinstance(d, dict):
            continue
        for k in keys:
            v = d.get(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str) and v.isdigit():
                return int(v)
    return None


def _trae_declared_credit(payload: Optional[Dict[str, Any]]) -> Optional[int]:
    """平台声明的「本次签到积分」= `credits`；没有该字段则 None。"""
    return _trae_pick_int(payload, *TRAE_CREDIT_KEYS)


def _trae_gain(before: Optional[int], after: Optional[int]) -> Optional[int]:
    """本次实际到账 = 签到前后余额差；任一为空或差额非正时返回 None（交回退）。"""
    if before is None or after is None:
        return None
    gain = after - before
    return gain if gain > 0 else None


def _trae_confirm(headers: Dict[str, str], timeout: int, retries: int) -> Optional[Dict[str, Any]]:
    """领奖后回查状态：确认到账返回状态报文，否则 None。"""
    for wait in TRAE_VERIFY_WAITS:
        if wait:
            time.sleep(wait)
        status = http_post(TRAE_STATUS_URL, headers, {}, timeout, retries)
        if _trae_status_checked(status[1]):
            return status[1]
    return None


def _trae_query_credits(acc: Dict[str, Any], device_id: str, timeout: int, retries: int) -> Optional[int]:
    """查询 Trae 当前积分余额（来自 ide_user_ent_usage 接口），返回当前可用积分或 None。"""
    st, pl, err = http_post(TRAE_CREDITS_URL, _trae_headers(acc, device_id), {}, timeout, retries)
    if not _business_ok(pl):
        log(f"[{acc.get('screenName') or acc.get('userId') or 'Trae账号'}] "
            f"{_line('积分查询失败', str(err))}")
        return None
    data = pl.get("data") if isinstance(pl.get("data"), dict) else pl
    usage = data.get("usage_summary") if isinstance(data.get("usage_summary"), dict) else None
    if usage and usage.get("total_amount") is not None:
        total = _to_int(usage.get("total_amount"), 0)
        consumed = _to_int(usage.get("consumed_amount"), 0)
        left = total - consumed
        return left if consumed else total
    packs = data.get("user_entitlement_pack_list") if isinstance(data.get("user_entitlement_pack_list"), list) else None
    if packs:
        total = 0
        for p in packs:
            info = p.get("entitlement_base_info") if isinstance(p.get("entitlement_base_info"), dict) else {}
            quota = info.get("quota") if isinstance(info.get("quota"), dict) else {}
            c = quota.get("credits_limit")
            if isinstance(c, (int, float)):
                total += int(c)
        return total
    return None



def run_trae_account(acc, status_only, timeout, retries):
    if acc.get('expiresAt') and time.time() > float(acc['expiresAt']) - TRAE_REFRESH_MARGIN:
        log('阶段 2.1 刷新临期凭据')
        if not _trae_refresh(acc):
            return False, '凭据刷新失败'
    device = acc.get('claimDeviceId') or acc['deviceId']
    headers = _trae_headers(acc, device)
    log('阶段 2.2 查询签到状态')
    _, status, error = http_post(TRAE_STATUS_URL, headers, {}, timeout, retries)
    if not _business_ok(status):
        return False, '状态查询未确认成功，停止领取'
    if _trae_status_checked(status):
        balance = _trae_query_credits(acc, device, timeout, retries)
        return True, _line('不重签', _fmt_credit(balance=balance))
    if status_only:
        return True, '状态查询成功，今日待签到'
    before = _trae_query_credits(acc, device, timeout, retries)
    for attempt in range(TRAE_CLAIM_RETRIES):
        log(f'阶段 2.3 提交签到 第 {attempt+1} 次')
        _, claim, error = http_post(TRAE_CLAIM_URL, headers, {}, timeout, retries)
        if _trae_claim_ok(claim):
            log('阶段 2.4 回查确认签到')
            confirmed = _trae_confirm(headers, timeout, retries)
            if confirmed is not None:
                after = _trae_query_credits(acc, device, timeout, retries)
                gain = _trae_gain(before, after)
                if gain is None:
                    gain = _trae_declared_credit(claim) or _trae_declared_credit(confirmed)
                return True, _line('签到成功', _fmt_credit(today=gain, balance=after))
            continue
        code = _code_of(claim)
        if code == 1001 and attempt + 1 < TRAE_CLAIM_RETRIES:
            log('认证失效，尝试刷新凭据')
            if _trae_refresh(acc):
                headers = _trae_headers(acc, device)
                continue
            return False, '凭据刷新失败'
        if code == 9074:
            return False, '设备指纹校验失败，请核对本人官方会话设备字段'
        if code == 9095:
            return False, '该设备今日已用于其他账号'
        return False, '签到接口未确认成功'
    return False, '领取后回查未确认签到'


def protect_values(value, key=''):
    if isinstance(value, dict):
        for child_key, child in value.items():
            protect_values(child, child_key)
    elif isinstance(value, list):
        for child in value:
            protect_values(child, key)
    elif any(part in key.lower() for part in ('token', 'cookie', 'secret', 'device', 'authorization')):
        if isinstance(value, str) and value:
            SECRET_VALUES.add(value)


def normalize_account(record, number):
    if not isinstance(record, dict):
        raise ValueError('账号必须是 JSON 对象')
    protect_values(record)
    acc = dict(record)
    platform = acc.get('platform', 'workbuddy')
    if platform not in ('workbuddy', 'trae'):
        raise ValueError('platform 只支持 workbuddy 或 trae')
    acc['platform'] = platform
    # 不从自定义账号标签推断身份，身份以官方接口的非敏感字段为准。
    acc['name'] = f'账号 {number}'
    acc['screenName'] = f'账号 {number}'
    if platform == 'workbuddy':
        acc['access_token'] = acc.get('access_token') or acc.get('accessToken') or acc.get('token')
        required = ('access_token',)
        wb_validated_base(acc.get('api_base'))
    else:
        required = ('accessToken', 'refreshToken', 'userId', 'deviceId')
        if 'expiresAt' in acc:
            expires = float(acc['expiresAt'])
            if not math.isfinite(expires) or expires <= 0:
                raise ValueError('expiresAt 必须为正数秒时间戳')
            acc['expiresAt'] = expires
        if 'fingerprint' in acc and not isinstance(acc['fingerprint'], dict):
            raise ValueError('fingerprint 必须为对象')
    if any(not isinstance(acc.get(key), str) or not acc[key].strip() for key in required):
        raise ValueError('账号缺少必要凭据字段')
    if any('\n' in acc[key] or '\r' in acc[key] for key in required):
        raise ValueError('凭据字段包含非法换行')
    return acc


# 通知在子进程中运行，限制耗时并隔离通知模块的输出与异常。
NOTIFY_WORKER = r'''
import contextlib, importlib, importlib.util, os, socket, sys
if sys.argv[3] == '1':
    def offline(*args, **kwargs):
        raise OSError('dry-run offline')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    socket.getaddrinfo = offline
    socket.gethostbyname = offline
    socket.socket.sendto = offline
with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
            roots = [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
            for root in roots:
                if not root:
                    continue
                path = os.path.join(root, 'notify.py')
                if os.path.isfile(path):
                    spec = importlib.util.spec_from_file_location('ql_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, 'send', None)):
            sys.exit(2)
        result = module.send(sys.argv[1], sys.argv[2])
        sys.exit(1 if result is False else 0)
    except Exception:
        sys.exit(1)
'''


def notify_summary(body):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in {'0', 'false', 'no', 'off'}:
        return '已关闭'
    if 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        names = ('ed929736b882170c', Path(__file__).name, 'scripts/' + Path(__file__).name)
        selected = any(fnmatch.fnmatch(name, selector) for selector in selectors if selector for name in names)
    else:
        # 本任务属于契约声明的默认通知列表。
        selected = True
    if not selected:
        return '未选中'
    try:
        result = subprocess.run(
            [sys.executable, '-c', NOTIFY_WORKER, 'AI 积分签到', body, str(int(DRY_RUN))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
        if result.returncode == 0:
            return '已发送'
    except (OSError, subprocess.TimeoutExpired):
        pass
    return '通知不可用或失败，已保留业务退出码' + ('，预演禁止联网' if DRY_RUN else '')


def main():
    global DRY_RUN
    start = time.monotonic()
    log('========== AI 积分签到 ==========')
    log(f'开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    parser = argparse.ArgumentParser(description=__doc__.split('MIT License')[0])
    parser.add_argument('--status-only', action='store_true', help='只查询签到状态')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--workbuddy-only', action='store_true')
    selection.add_argument('--trae-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='完全离线预演')
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()
    DRY_RUN = args.dry_run or env_bool('AICREDIT_DRY_RUN')
    log('模式 ' + ('离线预演' if DRY_RUN else '只查询' if args.status_only else '正式签到'))
    lines = [line.strip() for line in os.environ.get('AICREDIT_ACCOUNTS', '').splitlines() if line.strip()]
    log(f'账号数 {len(lines)}')
    passed = failed = skipped = already = 0
    config_error = False
    try:
        timeout = env_int('WORKBUDDY_TIMEOUT', 20, 5, 120)
        retries = env_int('WORKBUDDY_RETRIES', 2, 0, 5)
        if not lines:
            raise ValueError('缺少 AICREDIT_ACCOUNTS，每个非空行填写一个账号 JSON 对象')
    except ValueError as exc:
        config_error = True
        log(f'阶段 1 配置错误 {exc}')
    if not config_error:
        for number, line in enumerate(lines, 1):
            began = time.monotonic()
            ok = False
            detail = ''
            log(f'账号 {number} 阶段 1 校验配置')
            try:
                record = json.loads(line)
                acc = normalize_account(record, number)
                if acc.get('enabled', True) is False or (args.workbuddy_only and acc['platform'] != 'workbuddy') or (args.trae_only and acc['platform'] != 'trae'):
                    skipped += 1
                    log(f'账号 {number} 统计 总任务=1 成功=0 已完成=0 跳过=1 失败=0 耗时={time.monotonic()-began:.2f}秒')
                    continue
                log(f'账号 {number} 阶段 1 完成 平台={acc["platform"]} 耗时={time.monotonic()-began:.2f}秒')
                if DRY_RUN:
                    ok, detail = True, 'DRY_RUN_OK 配置有效，未执行账号请求或写入'
                else:
                    log(f'账号 {number} 阶段 2 执行账号任务')
                    if acc['platform'] == 'workbuddy':
                        ok, detail = WorkBuddyClient(acc, timeout, retries).check_in(args.status_only)
                    else:
                        ok, detail = run_trae_account(acc, args.status_only, timeout, retries)
            except (ValueError, TypeError, KeyError):
                detail = '账号配置或接口字段格式错误'
            except Exception:
                detail = '账号执行异常，已隐藏异常内容'
            is_already = ok and '不重签' in detail
            already += int(is_already)
            passed += int(ok)
            failed += int(not ok)
            log(f'账号 {number} 结果 {detail}')
            log(f'账号 {number} 统计 总任务=1 成功={int(ok and not is_already)} 已完成={int(is_already)} 跳过=0 失败={int(not ok)} 耗时={time.monotonic()-began:.2f}秒')
    # 选择后没有可执行账号时不能宣告业务成功。
    rc = int(config_error or failed > 0 or passed == 0)
    status = 'configuration-error' if config_error else 'partial-failure' if failed and passed else 'failure' if rc else 'dry-run' if DRY_RUN else 'success'
    summary = dict(accounts=len(lines), success=passed, failure=failed, skipped=skipped,
                   alreadyComplete=already, status=status, dryRun=DRY_RUN, exitCode=rc)
    body = f'账号总数 {len(lines)}，成功 {passed}，失败 {failed}，跳过 {skipped}，状态 {status}'
    notification = notify_summary(body)
    log('----------------------------------------')
    log(f'最终任务统计 {body}，已完成 {already}，总耗时 {time.monotonic()-start:.2f}秒')
    log(f'通知状态 {notification}')
    log(f'完成时间 {datetime.now():%Y-%m-%d %H:%M:%S} 最终状态 {status}')
    summary['notification'] = notification
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return rc


if __name__ == '__main__':
    sys.exit(main())
