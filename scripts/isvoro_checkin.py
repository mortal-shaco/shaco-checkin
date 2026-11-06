#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ISVORO 每日签到
# cron: 6 10 * * *
"""
ISVORO 每日签到。Python 3.10+，仅使用 Python 标准库。
来源 GGBondHere/QingLongScripts scripts/isvoro_checkin.py，MIT 许可。
原始版本由 daily_all.py 每日调用，未提供独立 cron。此版本独立任务建议每天 09:00。
功能清单：签到、连签/奖励/积分余额/累计积分查询、登录态刷新、可选面板回写、合集结果。
任务无已维护功能和相关来源，不存在重复覆盖或同产品待合并功能。

ISVORO_COOKIE 必填，每个非空行一个账号，保留完整 Cookie，不使用 & 或 @ 分账号。
登录 https://isvoro.com/checkin，开发者工具→网络→刷新→/api/v1/auth/me，
复制请求头 Cookie，必须包含 pmt_access、pmt_refresh、pmt_csrf。
每个 Cookie 字段仅在首个等号处分割，值中的等号得到保留。
ISVORO_DRY_RUN=1 完全断网预演，仍验证凭据字段，不发送签到、刷新、回写或通知请求。
ISVORO_WRITEBACK=1 显式开启面板回写，默认关闭以避免自动更改环境变量。
开启时 CLIENT_ID、CLIENT_SECRET 均必填，在青龙系统设置→应用设置创建有环境变量权限的应用。
仅在刷新后业务查询验证成功时更新当前进程 Cookie。所有账号结束后，按原始完整变量值
精确匹配一条面板记录，一次回写合并值，保留其他账号行。回写失败整体非零退出。
DAILY_ALL_CHILD=1 保留 __DAILY_ALL_RESULT__= 兼容输出。
DAILY_ALL_DISABLED 中 isvoro 或 isvoro_checkin 可停用业务，停用不代表验证成功。
QINGLONG_NOTIFY=auto 默认仅按 QINGLONG_NOTIFY_SCRIPTS 选择的脚本通知。
QINGLONG_NOTIFY=1 强制开启，0 关闭。选择列表支持目录路径、文件名、通配符或目录编号，
用逗号、分号、空白分隔；显式空列表禁用全部。QINGLONG_NOTIFY_DIR 可指定通知模块目录。
通知依次发现 notify.send、青龙 notify.py、sendNotify.js，通知失败不改变业务退出码。
断网预演只打印脱敏通知摘要，不运行可能联网的通知模块。
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
        _ql_notify_identities = ('1459eae4ec890c40', 'scripts/isvoro_checkin.py', 'isvoro_checkin.py', 'isvoro_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import json
import json as json_codec
import fnmatch
import subprocess
from pathlib import Path
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# 运行配置

import urllib.request
import urllib.error
import urllib.parse
from http.cookies import SimpleCookie
from types import SimpleNamespace


def configure_utf8_output() -> None:
    """确保 Windows 本地终端可输出中文和状态符号。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, TypeError, ValueError):
                pass


# 配置与数据模型

BASE = "https://isvoro.com/api/v1"
QL_OPEN_BASE = "http://127.0.0.1:5700/open"
COOKIE_ENV_NAME = "ISVORO_COOKIE"
DAILY_RESULT_PREFIX = "__DAILY_ALL_RESULT__="
TIMEOUT = 20
LOCAL_REQUEST_TIMEOUT = 10
GET_RETRY_COUNT = 2


# 环境变量与凭证解析

@dataclass
class CookieState:
    original_raw: str
    values: dict[str, str]
    order: list[str]

    @classmethod
    def from_header(cls, raw: str) -> "CookieState":
        original = (raw or "").strip()

        values: dict[str, str] = {}
        order: list[str] = []
        for part in original.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            if not name:
                continue
            if name not in values:
                order.append(name)
            values[name] = value.strip()
        return cls(original, values, order)

    def get(self, name: str) -> str:
        return self.values.get(name, "")

    def as_header(self) -> str:
        return "; ".join(
            f"{name}={self.values[name]}"
            for name in self.order
            if name in self.values
        )

    def apply_response(self, response: Any) -> set[str]:
        changed: set[str] = set()
        for cookie in getattr(response, "cookies", ()):
            name = str(getattr(cookie, "name", "") or "").strip()
            if not name:
                continue
            value = str(getattr(cookie, "value", "") or "")
            if name not in self.values:
                self.order.append(name)
            if self.values.get(name) != value:
                changed.add(name)
            self.values[name] = value
        return changed


@dataclass
class WritebackResult:
    enabled: bool
    attempted: bool
    ok: bool
    message: str


def _safe_json(response):
    try:
        data = response.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpResponse:
    def __init__(self, response):
        self.status_code = response.code
        content = response.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024:
            raise RuntimeError("响应超过安全大小限制")
        self.text = content.decode("utf-8")
        self.cookies = []
        for value in response.headers.get_all("Set-Cookie", []):
            parsed = SimpleCookie()
            parsed.load(value)
            self.cookies.extend(SimpleNamespace(name=name, value=item.value) for name, item in parsed.items())

    def json(self):
        return json.loads(self.text)


class HttpSession:
    """自行实现 HTTP 请求，禁止跳转，只有只读请求可重试。"""
    def __init__(self, retries=0):
        self.headers = {}
        self.retries = retries
        self.trust_env = False
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, url, headers=None, timeout=20, params=None, json=None, allow_redirects=False):
        if allow_redirects:
            raise ValueError("禁止自动跳转")
        method = method.upper()
        if params:
            url += "?" + urllib.parse.urlencode(params)
        merged_headers = dict(self.headers)
        merged_headers.update(headers or {})
        payload = None
        if json is not None:
            payload = json_codec.dumps(json).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=payload, headers=merged_headers, method=method)
        attempts = 1 + (self.retries if method in {"GET", "HEAD"} else 0)
        for attempt in range(attempts):
            try:
                try:
                    response = self.opener.open(request, timeout=timeout)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    result = HttpResponse(response)
                if result.status_code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                    return result
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt + 1 == attempts:
                    raise
            time.sleep(0.8 * (attempt + 1))
        raise RuntimeError("请求未获得有效响应")

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def close(self):
        pass


def create_http_session():
    return HttpSession(retries=GET_RETRY_COUNT)


def _ql_response_ok(response, data):
    status_code = int(getattr(response, "status_code", 0) or 0)
    api_code = data.get("code")
    return (
        200 <= status_code < 300
        and (not isinstance(api_code, bool) and str(api_code) in {"0", "200"})
    )


def _ql_message(data, fallback):
    return fallback  # 服务端消息可能包含会话凭据，不输出原文。


class QinglongOpenAPI:
    """保存青龙中的 ISVORO_COOKIE。"""

    def __init__(self, client_id, client_secret, session=None):
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.session = session or HttpSession()
        if session is None and hasattr(self.session, "trust_env"):
            self.session.trust_env = False

    def _get_token(self):
        try:
            response = self.session.get(
                f"{QL_OPEN_BASE}/auth/token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=LOCAL_REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            data = _safe_json(response)
        except Exception as error:
            return False, f"青龙认证请求异常（{type(error).__name__}）"

        token = (
            (data.get("data") or {}).get("token")
            if isinstance(data.get("data"), dict)
            else ""
        )
        if not _ql_response_ok(response, data) or not token:
            return False, f"青龙认证失败：{_ql_message(data, '未返回访问令牌')}"
        return True, str(token)

    @staticmethod
    def _extract_env_records(data):
        records = data.get("data") if isinstance(data, dict) else None
        if isinstance(records, dict):
            for key in ("data", "items", "rows", "list"):
                if isinstance(records.get(key), list):
                    records = records[key]
                    break
        if not isinstance(records, list):
            return []
        return [item for item in records if isinstance(item, dict)]

    def update_environment(self, original_value, new_value):
        token_ok, token_or_error = self._get_token()
        if not token_ok:
            return WritebackResult(True, True, False, token_or_error)

        headers = {
            "Authorization": f"Bearer {token_or_error}",
            "Content-Type": "application/json",
        }
        try:
            response = self.session.get(
                f"{QL_OPEN_BASE}/envs",
                params={"searchValue": COOKIE_ENV_NAME},
                headers=headers,
                timeout=LOCAL_REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            data = _safe_json(response)
        except Exception as error:
            return WritebackResult(
                True,
                True,
                False,
                f"查询青龙环境变量请求异常（{type(error).__name__}）",
            )

        if not _ql_response_ok(response, data):
            return WritebackResult(
                True,
                True,
                False,
                "查询青龙环境变量失败："
                + _ql_message(data, "接口返回异常"),
            )

        matches = [
            item
            for item in self._extract_env_records(data)
            if item.get("name") == COOKIE_ENV_NAME
            and item.get("value") == original_value
        ]
        if len(matches) != 1:
            return WritebackResult(
                True,
                True,
                False,
                "未能唯一确定 ISVORO_COOKIE，已拒绝回写",
            )

        target = matches[0]
        payload = {
            "name": COOKIE_ENV_NAME,
            "value": new_value,
        }
        if "id" in target:
            payload["id"] = target["id"]
        elif "_id" in target:
            payload["_id"] = target["_id"]
        else:
            return WritebackResult(
                True,
                True,
                False,
                "目标环境变量缺少 ID，已拒绝回写",
            )
        for key in ("remarks", "labels"):
            if key in target and target[key] is not None:
                payload[key] = target[key]

        try:
            response = self.session.put(
                f"{QL_OPEN_BASE}/envs",
                json=payload,
                headers=headers,
                timeout=LOCAL_REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            data = _safe_json(response)
        except Exception as error:
            return WritebackResult(
                True,
                True,
                False,
                f"ISVORO_COOKIE 回写请求异常（{type(error).__name__}）",
            )

        if not _ql_response_ok(response, data):
            return WritebackResult(
                True,
                True,
                False,
                "ISVORO_COOKIE 回写失败："
                + _ql_message(data, "接口返回异常"),
            )
        return WritebackResult(
            True,
            True,
            True,
            "ISVORO_COOKIE 已自动回写",
        )


def write_back_cookie(
    original_value,
    new_value,
    client_id="",
    client_secret="",
    session=None,
):
    """刷新被业务请求验证后，按原值精确回写青龙环境变量。"""
    clean_id = (client_id or "").strip()
    clean_secret = (client_secret or "").strip()

    if original_value == new_value:
        return WritebackResult(
            bool(clean_id or clean_secret),
            False,
            True,
            "ISVORO_COOKIE 无变化",
        )
    if not clean_id and not clean_secret:
        return WritebackResult(
            False,
            False,
            False,
            "登录态已刷新，但未配置 CLIENT_ID/CLIENT_SECRET",
        )
    if not clean_id or not clean_secret:
        return WritebackResult(
            True,
            False,
            False,
            "CLIENT_ID 与 CLIENT_SECRET 必须同时配置",
        )

    api = QinglongOpenAPI(clean_id, clean_secret, session=session)
    return api.update_environment(original_value, new_value)


class IsvoroClient:
    SAFE_RETRY_METHODS = {"GET", "HEAD"}
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(
        self,
        cookie_header,
        session=None,
        writeback_func=None,
        client_id="",
        client_secret="",
    ):
        self.cookies = CookieState.from_header(cookie_header)
        self.session = session or create_http_session()
        self.writeback_func = writeback_func
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.identity = ""
        self.refresh_attempted = False
        self.refreshed = False
        self.writeback_result = None

        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Origin": "https://isvoro.com",
            "Referer": "https://isvoro.com/checkin",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Cache-Control": "no-cache",
        })

    def _request_once(self, method, path, allow_empty_json=False):
        method = method.upper()
        headers = {"Cookie": self.cookies.as_header()}

        if method in self.WRITE_METHODS:
            csrf = self.cookies.get("pmt_csrf")
            if not csrf:
                raise RuntimeError(
                    "缺少 pmt_csrf Cookie，为避免无效提交，本次没有发送请求"
                )
            headers["X-CSRF-Token"] = csrf

        response = self.session.request(
            method,
            BASE + path,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=False,
        )

        try:
            body = response.json()
        except Exception:
            if response.status_code == 401 or (allow_empty_json and not (getattr(response, "text", "") or "").strip()):
                body = {}
            else:
                raise RuntimeError(
                    f"{method} {path} 返回非 JSON："
                    f"HTTP {response.status_code}"
                )

        if not isinstance(body, dict):
            raise RuntimeError(f"{method} {path} 返回格式异常")
        return response, body

    def _refresh_once(self):
        if self.refresh_attempted:
            raise RuntimeError("本进程已经尝试刷新登录凭证，不再重复刷新")
        self.refresh_attempted = True

        if not self.cookies.get("pmt_refresh"):
            raise RuntimeError("缺少 pmt_refresh Cookie，无法自动刷新登录凭证")
        if not self.cookies.get("pmt_csrf"):
            raise RuntimeError("缺少 pmt_csrf Cookie，无法自动刷新登录凭证")

        response, body = self._request_once(
            "POST",
            "/auth/refresh",
            allow_empty_json=True,
        )

        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                f"登录凭证刷新失败：HTTP {response.status_code}，"
                "服务端拒绝刷新"
            )
        if body.get("code") not in (0, None):
            raise RuntimeError(
                "登录凭证刷新失败，"
                "服务端拒绝刷新"
            )

        candidate = CookieState(
            original_raw=self.cookies.original_raw,
            values=dict(self.cookies.values),
            order=list(self.cookies.order),
        )
        changed = candidate.apply_response(response)
        if "pmt_access" not in changed or not candidate.get("pmt_access"):
            raise RuntimeError("登录凭证刷新响应未下发新的 pmt_access")

        self.cookies = candidate
        self.refreshed = True

    def _persist_verified_cookie(self):
        if self.writeback_result is not None:
            return self.writeback_result

        if self.writeback_func is None:
            result = WritebackResult(
                enabled=False,
                attempted=False,
                ok=False,
                message="登录态已刷新，但没有可用的青龙回写函数",
            )
        else:
            try:
                result = self.writeback_func(
                    self.cookies.original_raw,
                    self.cookies.as_header(),
                    self.client_id,
                    self.client_secret,
                )
                if not isinstance(result, WritebackResult):
                    result = WritebackResult(
                        enabled=True,
                        attempted=True,
                        ok=False,
                        message="登录态已刷新，但青龙回写结果格式异常",
                    )
            except Exception as error:
                result = WritebackResult(
                    enabled=True,
                    attempted=True,
                    ok=False,
                    message=(
                        "登录态已刷新，但青龙回写异常"
                        f"（{type(error).__name__}）"
                    ),
                )

        self.writeback_result = result
        return result

    def call(self, method, path):
        method = method.upper()
        response, body = self._request_once(method, path)

        if response.status_code == 401 and method in self.SAFE_RETRY_METHODS:
            self._refresh_once()
            response, body = self._request_once(method, path)

        self.identity = response_identity(body, self.cookies) or self.identity
        return response.status_code, body


@dataclass
class CheckinResult:
    status: str
    sign_status: str
    streak: Any = "?"
    earned_now: Any = "?"
    balance: Any = "?"
    total_earned: Any = "?"
    credential: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""


# 网络请求与业务逻辑
def get_data(body, name):
    if not isinstance(body, dict):
        raise RuntimeError(f"{name}返回格式异常")
    code = body.get("code")
    if code not in (0, None):
        raise RuntimeError(f"{name}业务状态失败")
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{name}缺少 data")
    return data


def get_status(client):
    http, body = client.call("GET", "/points/checkin/status")
    if http in (401, 403):
        raise RuntimeError(f"登录态无效（HTTP {http}）")
    if not 200 <= http < 300:
        raise RuntimeError(f"查询签到状态失败（HTTP {http}）")
    data = get_data(body, "查询签到状态")
    if not isinstance(data.get("checked_in"), bool):
        raise RuntimeError("签到状态缺少 checked_in 布尔值")
    if client.refreshed:
        client._persist_verified_cookie()
    return data


def get_points(client):
    http, body = client.call("GET", "/points")
    if not 200 <= http < 300:
        raise RuntimeError(f"查询积分失败（HTTP {http}）")
    data = get_data(body, "查询积分")
    for key in ("balance", "total_earned"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError("积分查询缺少有效数值")
    if client.refreshed:
        client._persist_verified_cookie()
    return data


def safe_get_points(client):
    try:
        return get_points(client)
    except Exception:
        return None


def friendly_error(error):
    text = str(error)
    lowered = text.lower()
    if "登录态无效" in text or "401" in lowered:
        return "登录状态已过期，请重新登录网站并更新 ISVORO_COOKIE"
    if "csrf" in lowered or "pmt_csrf" in lowered:
        return "登录校验信息不完整，请重新抓取完整 ISVORO_COOKIE"
    if "can_checkin" in lowered:
        return "服务端当前不允许签到，请稍后再运行"
    if any(word in lowered for word in ("timeout", "timed out", "connection", "network")):
        return "网络请求异常，请稍后再运行"
    return "请求或业务校验失败，请检查登录态及服务可用性"


def verify_checkin(client, points_before=None):
    time.sleep(1)
    status = get_status(client)
    if status.get("checked_in") is not True:
        raise RuntimeError("复查仍未签到；为避免重复提交，不进行第二次 POST")

    points_after = safe_get_points(client)
    result = CheckinResult(status="success", sign_status="签到成功", streak=status.get("streak", "?"))
    if points_after:
        result.balance = points_after.get("balance", "?")
        result.total_earned = points_after.get("total_earned", "?")
        if points_before:
            before_balance = points_before.get("balance")
            after_balance = points_after.get("balance")
            if isinstance(before_balance, (int, float)) and isinstance(after_balance, (int, float)):
                result.earned_now = after_balance - before_balance
    else:
        result.warnings.append("签到已确认，但积分信息查询失败")
    return result


# 独立执行、日志与通知
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
CATALOG_ID = "1459eae4ec890c40"
TITLE = "ISVORO 每日签到"


def enabled(name):
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def response_identity(body, cookies):
    """仅输出官方明确的非秘密身份字段，不打印响应或凭据。"""
    containers = [body]
    if isinstance(body.get("data"), dict):
        containers.append(body["data"])
        if isinstance(body["data"].get("user"), dict):
            containers.append(body["data"]["user"])
    for container in containers:
        for key in ("nickname", "username", "display_name", "displayName", "public_uid", "uid"):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            text = str(value)
            if not text or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
                continue
            if re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text):
                continue
            if any(secret and secret in text for secret in cookies.values.values()):
                continue
            return text
    return ""


def metric(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value) if abs(value) < 1e18 else "未返回"
    return "未返回"


class Stages:
    def __init__(self, number):
        self.number = number
        self.started = time.monotonic()
        self.counts = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}

    def run(self, name, action, outcome="success"):
        self.counts["total"] += 1
        start = time.monotonic()
        prefix = f"账号 {self.number} 阶段 {self.counts['total']} {name}"
        log(prefix + " 开始")
        try:
            value = action()
        except Exception:
            self.counts["failure"] += 1
            log(f"❌ {prefix} 失败，耗时 {time.monotonic() - start:.2f} 秒")
            raise
        self.counts[outcome] += 1
        icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️"}[outcome]
        log(f"{icon} {prefix} 完成，耗时 {time.monotonic() - start:.2f} 秒")
        return value

    def finish(self, ok):
        stats = self.counts
        log(f"账号 {self.number} 统计 总任务 {stats['total']}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failure']}，"
            f"耗时 {time.monotonic() - self.started:.2f} 秒，结果 {'成功' if ok else '失败'}")


def validate_cookie(raw):
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise ValueError("Cookie 存在控制字符")
    cookie = CookieState.from_header(raw)
    if any(not cookie.get(key) for key in ("pmt_access", "pmt_refresh", "pmt_csrf")):
        raise ValueError("Cookie 缺少必要字段")
    # HTTP 头仅支持 Latin-1，提前验证以保证逐账号隔离。
    cookie.as_header().encode("latin-1")
    return cookie


def run_account(raw, number, dry_run, disabled, updated, line_index):
    stages = Stages(number)
    client = None
    result = CheckinResult("fail", "未完成")
    try:
        stages.run("校验 Cookie 必要字段", lambda: validate_cookie(raw))
        if dry_run or disabled:
            reason = "断网预演" if dry_run else "显式停用"
            for name in ("查询签到与积分", "必要时刷新登录态", "签到及复查", "可选回写"):
                stages.run(f"{name}（{reason}，未执行）", lambda: None, "skipped")
            result = CheckinResult("dry-run" if dry_run else "skip", reason)
        else:
            def retain_verified(original, new, *_):
                updated[line_index] = new
                return WritebackResult(False, False, True, "已在内存更新，经显式开启后统一回写")

            client = IsvoroClient(raw, writeback_func=retain_verified)
            status = stages.run("查询签到状态（必要时安全刷新）", lambda: get_status(client))
            before = stages.run("查询签到前积分（辅助查询）", lambda: safe_get_points(client))
            if before is None:
                log(f"⚠️ 账号 {number} 签到前积分未获取，继续签到核验")
            if status.get("checked_in") is True:
                stages.run("今日已签到，跳过提交", lambda: None, "alreadyComplete")
                if before is None:
                    before = stages.run("重查已签到账号积分", lambda: get_points(client))
                result = CheckinResult("success", "今日已签到", streak=status.get("streak"),
                                       balance=before.get("balance"), total_earned=before.get("total_earned"))
            else:
                if status.get("checked_in") is not False or status.get("can_checkin") is not True:
                    raise RuntimeError("签到状态异常或当前禁止签到")

                def submit_and_verify():
                    # POST 从不自动重试。即使超时，也只通过 GET 复查实际状态。
                    try:
                        http, body = client.call("POST", "/points/checkin")
                        if not 200 <= http < 300 or body.get("code") not in (0, None):
                            log(f"账号 {number} 签到响应未确认成功，将执行只读复查")
                    except Exception:
                        log(f"账号 {number} 签到响应异常，将执行只读复查")
                    return verify_checkin(client, before)

                result = stages.run("单次签到并复查 checked_in", submit_and_verify)
                if result.warnings:
                    points = stages.run("签到后积分查询", lambda: get_points(client))
                    result.balance = points.get("balance")
                    result.total_earned = points.get("total_earned")
                    result.warnings.clear()
            if client.identity:
                log(f"账号 {number} 官方身份 {client.identity}")
            log(f"账号 {number} {result.sign_status}，连签 {metric(result.streak)} 天，"
                f"本次奖励 {metric(result.earned_now)}，余额 {metric(result.balance)}，累计 {metric(result.total_earned)}")
    except Exception:
        if not stages.counts["failure"]:
            stages.counts["total"] += 1
            stages.counts["failure"] += 1
        result = CheckinResult("fail", "未完成", error="凭据配置、网络或业务核验失败，请检查 Cookie 完整性及服务状态")
        log(f"❌ 账号 {number} {result.error}")
        if client and client.identity:
            log(f"账号 {number} 官方身份 {client.identity}")
    finally:
        if client:
            client.session.close()
    stages.finish(result.status != "fail")
    return result, stages.counts


def notification_selected():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selection is not None:
        identifiers = [CATALOG_ID, "isvoro_checkin.py", "scripts/isvoro_checkin.py", "checkin/isvoro_checkin.py", Path(__file__).name]
        for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
            try:
                identifiers.append(Path(__file__).resolve().relative_to(root).as_posix())
            except ValueError:
                pass
        return any(fnmatch.fnmatchcase(value, pattern)
                   for pattern in re.split(r"[,;\s]+", selection.strip()) if pattern
                   for value in identifiers)
    return switch in TRUE_VALUES


def send_notification(body, dry_run):
    if not notification_selected():
        return "⏭️ 通知开关或选择列表未启用"
    if dry_run:
        log("断网预演通知摘要 " + body.replace("\n", " | "))
        return "⏭️ 断网预演已生成摘要，通知模块未执行"
    # 子进程隔离通知模块的输出和异常，防止通知失败改变业务状态或泄漏配置。
    runner = '''import importlib, importlib.util, sys
kind, path, title, body = sys.argv[1:]
if kind == "module":
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as exc:
        sys.exit(3 if exc.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
send = getattr(module, "send", None)
if not callable(send):
    sys.exit(3)
send(title, body)
'''
    commands = [[sys.executable, "-c", runner, "module", "", TITLE, body]]
    directories = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        directories.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]))
    directories.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    for directory in directories:
        path = directory / "notify.py"
        if path.is_file():
            commands.append([sys.executable, "-c", runner, "file", str(path), TITLE, body])
    for directory in directories:
        path = directory / "sendNotify.js"
        if path.is_file():
            commands.append(["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))", str(path.resolve()), TITLE, body])
    for command in commands:
        try:
            completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        except FileNotFoundError:
            continue
        except Exception:
            return "⚠️ 通知执行异常，保留业务退出码"
        if completed.returncode == 3:
            continue
        return "✅ 通知已发送" if completed.returncode == 0 else "⚠️ 通知发送失败，保留业务退出码"
    return "⚠️ 未发现可用的青龙通知模块，保留业务退出码"


def main():
    configure_utf8_output()
    started = time.monotonic()
    dry_run = enabled("ISVORO_DRY_RUN")
    raw = os.getenv(COOKIE_ENV_NAME, "")
    lines = raw.splitlines(keepends=True)
    accounts = [(index, line.strip()) for index, line in enumerate(lines) if line.strip()]
    disabled_items = {part.strip().casefold() for part in re.split(r"[,;|&\n]+", os.getenv("DAILY_ALL_DISABLED", ""))}
    disabled = bool(disabled_items.intersection({"isvoro", "isvoro_checkin"}))
    log("========== ISVORO 每日签到 ==========")
    log(f"开始时间 {time.strftime('%Y-%m-%d %H:%M:%S')}，模式 {'断网预演' if dry_run else '正式'}，账号数 {len(accounts)}")
    results = []
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    updated = {}
    configuration_error = not accounts
    writeback_failed = False
    if configuration_error:
        log("❌ 配置错误，ISVORO_COOKIE 至少需要一个账号")
    for number, (index, cookie) in enumerate(accounts, 1):
        result, counts = run_account(cookie, number, dry_run, disabled, updated, index)
        results.append(result)
        for key in totals:
            totals[key] += counts[key]
    if not dry_run and not disabled and enabled("ISVORO_WRITEBACK"):
        begin = time.monotonic()
        log("任务阶段 1 合并已验证 Cookie 并精确回写 开始")
        client_id, client_secret = os.getenv("CLIENT_ID", ""), os.getenv("CLIENT_SECRET", "")
        if not client_id.strip() or not client_secret.strip():
            writeback_failed = configuration_error = True
            log("❌ 已开启回写但缺少配套青龙应用凭据")
        elif updated:
            new_lines = list(lines)
            for index, value in updated.items():
                ending = "\r\n" if lines[index].endswith("\r\n") else "\n" if lines[index].endswith("\n") else ""
                new_lines[index] = value + ending
            result = write_back_cookie(raw, "".join(new_lines), client_id, client_secret)
            writeback_failed = not result.ok
            log(("✅ " if result.ok else "❌ ") + result.message)
        else:
            log("⏭️ 无需回写 Cookie")
        log(f"任务阶段 1 结束，耗时 {time.monotonic() - begin:.2f} 秒")
    elif updated:
        log("⏭️ Cookie 已安全刷新至内存，面板回写未开启；后续可能需要手动更新凭据")
    failed = sum(result.status == "fail" for result in results)
    succeeded = sum(result.status == "success" for result in results)
    exit_code = 1 if configuration_error or failed or writeback_failed else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if exit_code and succeeded else
              "failure" if exit_code else "dry-run" if dry_run else
              "skipped" if disabled else "success")
    body = f"账号总数 {len(accounts)}，成功 {succeeded}，失败 {failed}，跳过/预演 {len(accounts) - succeeded - failed}\n最终状态 {status}，回写失败 {int(writeback_failed)}"
    account_details = []
    for number, result in enumerate(results, 1):
        detail = f"账号 {number} {result.sign_status}"
        if result.status == "success":
            detail += (f"，连签 {metric(result.streak)} 天，本次奖励 {metric(result.earned_now)}，"
                       f"余额 {metric(result.balance)}，累计 {metric(result.total_earned)}")
        elif result.error:
            detail += "，" + result.error
        account_details.append(detail)
    if account_details:
        body += "\n" + "\n".join(account_details)
    notification = send_notification(body, dry_run)
    if os.getenv("DAILY_ALL_CHILD", "").strip() == "1":
        daily_status = "fail" if exit_code else "skip" if dry_run or disabled else "success"
        print(DAILY_RESULT_PREFIX + json.dumps({"version": 1, "status": daily_status, "details": body.splitlines()}, ensure_ascii=False, separators=(",", ":")))
    log("----------------------------------------")
    log(body.replace("\n", "；"))
    log(f"子任务统计 {json.dumps(totals, ensure_ascii=False)}")
    log(f"通知状态 {notification}")
    finished = time.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = round(time.monotonic() - started, 3)
    log(f"完成时间 {finished}，总耗时 {elapsed} 秒，最终状态 {status}")
    summary = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts": len(accounts),
               "success": succeeded, "failure": failed, "skipped": len(accounts) - succeeded - failed,
               "tasks": totals, "writebackFailure": writeback_failed, "notification": notification,
               "finishedAt": finished, "elapsedSeconds": elapsed, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

# MIT License
# 上游来源与归属：GGBondHere/QingLongScripts，scripts/isvoro_checkin.py。
# 原输入文件未附独立版权行，保留上游来源并沿用任务指定的 MIT 许可。
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
