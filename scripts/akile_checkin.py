#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AkileCloud 签到与保活
# cron: 44 0 * * *
# SPDX-License-Identifier: MIT
# Upstream attribution: GGBondHere/QingLongScripts, scripts/akile_checkin.py
# MIT License
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
"""
AkileCloud 签到与保活。来源：GGBondHere/QingLongScripts
原始路径：scripts/akile_checkin.py；许可证：MIT（继承上游许可）。
每天 22:00 执行；也可由 08:45 合集调用。Python 3.10+，仅使用 Python 标准库。
AKILE_TOKEN 为必填，每个非空行一个原始 JWT；不加 Bearer，不用 & 或 @ 分隔。
获取：登录 https://akile.ai/console/ak-coin-shop，浏览器开发者工具 → 应用 →
本地存储 → https://akile.ai → 复制 akile-token 原始值。凭据不可公开。
AKILE_DRY_RUN=1：完全断网，模拟请求、统计和通知，不写状态或凭据。
--check-only：仅查询，不签到、刷新或保存状态；仍按通知开关发送总结。
AKILE_REFRESH_TOKEN=1：显式开启到期前 14 小时保活及认证补救刷新；默认关闭，
以免轮换凭据却无法保存。开启时必须配置 CLIENT_ID、CLIENT_SECRET（青龙系统设置
→ 应用设置 → 创建应用并授予环境变量权限）。仅回写名称和完整原值唯一匹配的变量；
多账号顺序替换同一变量的一行，其他行原样保留。回写失败会令任务非零退出。
统计默认保存在同目录 state.json；AKILE_STATE_FILE 可指定可写文件，更新时保留。
DAILY_ALL_DISABLED 支持 akile/akile_checkin/akilecloud；DAILY_ALL_CHILD=1 保留合集 JSON。
QINGLONG_NOTIFY 未设置时按上架状态，0/false/no/off 关闭；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
签到只提交一次，必须由今日官方流水复核；不确定结果或统计异常均非零退出。
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
        _ql_notify_identities = ('48ce92fe72bec5fa', 'scripts/akile_checkin.py', 'akile_checkin.py', 'akile_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import base64
import hashlib
import ipaddress
import json
import math
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Sequence

# 运行配置

def skip_inactive_service(raw: str, disabled_value: str, daily_child: bool) -> bool:
    """未配置凭证或已停用时跳过。"""
    disabled = {item.strip().casefold() for item in re.split(r"[,;|&\n]+", disabled_value)}
    if raw.strip() and not disabled.intersection({"akile", "akile_checkin", "akilecloud"}):
        return False
    reason = "未配置凭证" if not raw.strip() else "已关闭"
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    print(f"跳过：{reason}")
    if daily_child:
        payload = {"version": 1, "status": "skip", "details": [reason]}
        print("__DAILY_ALL_RESULT__=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return True


import urllib.request
import urllib.error
import urllib.parse
import socket
from types import SimpleNamespace


class RequestException(Exception):
    pass


class RequestTimeout(RequestException):
    pass


class RequestConnectionError(RequestException):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpSession:
    """标准库 HTTP 实现：禁用代理继承、重定向与自动重试，限制响应大小。"""
    def __init__(self):
        self.headers = {}
        self.trust_env = False
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, url, *, headers=None, timeout=15, allow_redirects=False,
                params=None, json=None):
        if not (url.startswith(BASE + "/") or url.startswith(QL_OPEN_BASE + "/")):
            raise RequestException("拒绝非预期请求目标")
        if params:
            url += "?" + urllib.parse.urlencode(params)
        combined = {**self.headers, **(headers or {})}
        payload = None
        if json is not None:
            payload = globals()["json"].dumps(json).encode("utf-8")
            combined["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=combined, method=method)
        seconds = max(timeout) if isinstance(timeout, tuple) else timeout
        try:
            try:
                response = self.opener.open(request, timeout=seconds)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise RequestException("响应超过大小限制")
            class Response:
                status_code = status
                def json(self):
                    try:
                        return globals()["json"].loads(raw)
                    except (ValueError, UnicodeError):
                        raise ValueError("非 JSON 响应") from None
            return Response()
        except (TimeoutError, socket.timeout):
            raise RequestTimeout("请求超时") from None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise RequestTimeout("请求超时") from None
            raise RequestConnectionError("连接失败") from None
        except OSError:
            raise RequestConnectionError("连接失败") from None

    def close(self):
        pass


requests = SimpleNamespace(Session=HttpSession, RequestException=RequestException,
                           Timeout=RequestTimeout, ConnectionError=RequestConnectionError)



# 配置与数据模型

BASE = "https://api.akile.ai/api"
QL_OPEN_BASE = "http://127.0.0.1:5700/open"
TOKEN_ENV_NAME = "AKILE_TOKEN"
DAILY_RESULT_PREFIX = "__DAILY_ALL_RESULT__="
TIMEOUT = (5, 15)
REFRESH_AHEAD_SECONDS = 14 * 3600
LOG_PATH = "/v1/akcoin/log"
SAFE_QUERY_PATHS = frozenset({"/v1/user/index", "/v1/user/info", LOG_PATH})
RETRY_HTTP_CODES = frozenset({408, 429, 500, 502, 503, 504})
IPV6_CANDIDATE_RE = re.compile(r"(?<![0-9A-Za-z_])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:.]*(?:%[\w.-]+)?")


@dataclass
class WritebackResult:
    ok: bool
    message: str


@dataclass
class CheckinResult:
    status: str
    sign_status: str
    balance: Decimal | None = None
    earned_now: Decimal | None = None
    streak: int | None = None
    total_earned: Decimal | None = None
    checkin_executed: bool = False
    credential: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""


class ApiError(RuntimeError):
    def __init__(self, message: str, *, auth=False, retryable=False, definite=False):
        super().__init__(message)
        self.auth = auth
        self.retryable = retryable
        self.definite = definite


class StateStore:
    """共用 state.json；分区更新在跨进程锁内重读并原子保存。"""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self) -> dict:
        if self.path.is_symlink():
            raise ValueError("state.json 不能是符号链接")
        if not self.path.exists():
            return {"version": 1}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise ValueError("state.json 格式损坏，已保留原文件") from None
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("state.json 版本或结构无效，已保留原文件")
        return data

    def read(self, namespace: str) -> dict:
        section = self._load().get(namespace, {})
        if not isinstance(section, dict):
            raise ValueError(f"state.json 的 {namespace} 分区无效")
        return section

    @contextmanager
    def locked(self, scope: str = "state", timeout: float = 10):
        # 锁放在系统临时目录且不删除，避免等待进程锁住不同 inode；进程退出自动解锁。
        identity = os.path.normcase(str(self.path.resolve())) + ":" + scope
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        lock_path = Path(tempfile.gettempdir()) / ("qinglong-" + digest + ".lock")
        with lock_path.open("a+b") as file:
            if file.tell() == 0:
                file.write(b"0")
                file.flush()
            if os.name == "nt":
                import msvcrt
                def acquire():
                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                def release():
                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                def acquire():
                    fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                def release():
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    acquire()
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("状态正在被其他进程使用，请稍后运行") from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                release()

    def update(self, namespace: str, updater) -> dict:
        with self.locked():
            data = self._load()
            section = data.get(namespace, {})
            if not isinstance(section, dict):
                raise ValueError(f"state.json 的 {namespace} 分区无效")
            updated = updater(section)
            if not isinstance(updated, dict):
                raise ValueError("状态更新必须返回对象")
            if updated == section and namespace in data:
                return updated
            data[namespace] = updated
            content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                 prefix=".state-", suffix=".tmp", delete=False) as file:
                    temporary = Path(file.name)
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return updated


# 凭证解析与青龙回写

def safe_text(value: Any, *secrets: str) -> str:
    """仅展示脱敏、限长的服务端消息，不打印原始异常或响应体。"""
    text = "" if value is None else str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[已隐藏]")
    def hide_ipv6(match: re.Match) -> str:
        candidate = match.group().rstrip(".")
        try:
            ipaddress.IPv6Address(candidate)
        except ValueError:
            return match.group()
        return "[IP已隐藏]" + match.group()[len(candidate):]
    # 先处理 IPv6，避免其嵌入式 IPv4 被局部替换后漏掉完整地址。
    text = IPV6_CANDIDATE_RE.sub(hide_ipv6, text)
    text = re.sub(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[已隐藏]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP已隐藏]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[邮箱已隐藏]", text)
    return " ".join(text.split())[:200]


def token_expiry(raw: str) -> float:
    """只读取 exp，不在本地推断签名有效、用户身份或 IP 绑定。"""
    try:
        parts = raw.split(".")
        if len(parts) != 3 or not all(parts):
            raise ValueError
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
        expiry = payload.get("exp")
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
            raise ValueError
        if not math.isfinite(expiry) or expiry <= 0:
            raise ValueError
        return float(expiry)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("AKILE_TOKEN 格式无效或缺少有效 exp，请复制完整原始 JWT") from None


def coin_value(value: Any) -> Decimal:
    """余额按数值解析，避免浮点相减把实际收益变成近似数。"""
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise ValueError
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError
        return number
    except (ValueError, InvalidOperation):
        raise ValueError("AK 币余额字段无效") from None


def write_back_token(original: str, replacement: str, client_id="", client_secret="", session=None) -> WritebackResult:
    """仅更新名称及原值均匹配的唯一变量，拒绝覆盖已变化的凭证。"""
    if original == replacement:
        return WritebackResult(True, "AKILE_TOKEN 无变化")
    if not client_id or not client_secret:
        return WritebackResult(False, "未回写 AKILE_TOKEN，请配置青龙 CLIENT_ID、CLIENT_SECRET 并授予环境变量权限")
    own_session = session is None
    session = session or requests.Session()
    if own_session:
        session.trust_env = False

    def call(method, path, **kwargs):
        response = session.request(method, QL_OPEN_BASE + path, timeout=10, allow_redirects=False, **kwargs)
        body = response.json()
        if not isinstance(body, dict) or not 200 <= response.status_code < 300 or body.get("code") not in (0, 200, "0", "200"):
            raise ApiError(f"青龙 {path} 返回异常（HTTP {response.status_code}）")
        return body.get("data")

    try:
        auth = call("GET", "/auth/token", params={"client_id": client_id, "client_secret": client_secret})
        access = auth.get("token") if isinstance(auth, dict) else None
        if not isinstance(access, str) or not access:
            raise ApiError("青龙认证未返回访问令牌")
        headers = {"Authorization": f"Bearer {access}"}
        records = call("GET", "/envs", params={"searchValue": TOKEN_ENV_NAME}, headers=headers)
        if isinstance(records, dict):
            records = records.get("data", [])
        matches = [item for item in (records if isinstance(records, list) else [])
                   if isinstance(item, dict) and item.get("name") == TOKEN_ENV_NAME and item.get("value") == original]
        if len(matches) != 1:
            raise ApiError("未能唯一匹配原 AKILE_TOKEN，已拒绝覆盖；请检查是否被其他任务更新")
        target = matches[0]
        identity = "id" if "id" in target else "_id"
        if target.get(identity) is None:
            raise ApiError("青龙环境变量缺少 ID，已拒绝回写")
        payload = {identity: target[identity], "name": TOKEN_ENV_NAME, "value": replacement}
        for key in ("remarks", "labels"):
            if key in target and target[key] is not None:
                payload[key] = target[key]
        call("PUT", "/envs", json=payload, headers=headers)
        return WritebackResult(True, "AKILE_TOKEN 已自动回写")
    except ApiError as error:
        return WritebackResult(False, str(error))
    except Exception as error:
        return WritebackResult(False, f"AKILE_TOKEN 回写异常（{type(error).__name__}），请检查青龙应用权限及本机 OpenAPI")
    finally:
        if own_session:
            session.close()


# 网络请求与凭证维护

def create_http_session() -> requests.Session:
    """关闭底层 GET 自动重试，重试权限按接口路径而不是 HTTP 方法判定。"""
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://akile.ai",
        "Referer": "https://akile.ai/console/ak-coin-shop",
        "Cache-Control": "no-cache",
    })
    return session


class AkileClient:
    """维护一个进程内的登录凭证；所有业务调用共用一次刷新机会。"""
    def __init__(self, raw_token: str, *, session=None, clock=None, sleeper=None,
                 logger=None, writeback_func=None, client_id="", client_secret="", state_path=None):
        self.original_token = raw_token
        self.token = raw_token.strip()
        self.expiry = token_expiry(self.token)
        self.session = session or create_http_session()
        self.owns_session = session is None
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.log = logger or print
        self.refresh_enabled = enabled("AKILE_REFRESH_TOKEN", False)
        self.writeback_func = writeback_func or write_back_token
        self.client_id, self.client_secret = client_id, client_secret
        self.refresh_attempted = False
        self.checkin_attempted = False
        self.credential = ""
        self.warnings: list[str] = []
        self.state = StateStore(Path(state_path) if state_path is not None else Path(os.getenv("AKILE_STATE_FILE", str(Path(__file__).resolve().with_name("state.json")))))
        self.today_log: CheckinLog | None = None

    def _request_once(self, path: str, token: str, payload=None) -> Any:
        method = "POST" if path == LOG_PATH else "GET"
        kwargs = {"json": payload} if path == LOG_PATH else {}
        try:
            response = self.session.request(method, BASE + path, headers={"Authorization": token},
                                            timeout=TIMEOUT, allow_redirects=False, **kwargs)
        except requests.RequestException as error:
            message = f"{method} {path} 网络请求异常（{type(error).__name__}）"
            self.log(message)
            raise ApiError(message, retryable=isinstance(error, (requests.Timeout, requests.ConnectionError))) from None
        http = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        secrets = (self.token, token, self.client_id, self.client_secret)
        code = body.get("status_code") if isinstance(body, dict) else None
        message = "业务响应已脱敏" if isinstance(body, dict) else "非 JSON"
        self.log(f"{method} {path} → HTTP {http}, status_code={str(code) if str(code) in {'0', '200', '401', '403'} else '未知'}, status_msg={message or '未返回'}")
        auth = http in (401, 403) or str(code) in {"401", "403"}
        if not 200 <= http < 300:
            hint = "；认证或权限异常，请检查登录凭证" if auth else ""
            raise ApiError(f"{method} {path} 失败（HTTP {http}）{hint}", auth=auth,
                           retryable=http in RETRY_HTTP_CODES, definite=400 <= http < 500 and http not in (408, 429))
        if not isinstance(body, dict) or type(code) not in (int, str):
            raise ApiError(f"{method} {path} 响应格式异常，未返回有效业务状态")
        if str(code) not in {"0", "200"}:
            raise ApiError(f"{method} {path} 业务失败：{message or '未知业务码'}", auth=auth, definite=True)
        return body if path == LOG_PATH else body.get("data")

    def request(self, path: str, *, token: str | None = None, payload=None) -> Any:
        attempts = 3 if path in SAFE_QUERY_PATHS else 1
        for attempt in range(attempts):
            try:
                return self._request_once(path, token or self.token, payload)
            except ApiError as error:
                if not error.retryable or attempt + 1 == attempts:
                    raise
                self.log(f"查询：{path} 暂时异常，重试 {attempt + 1}/2")
                self.sleeper(0.8 * (attempt + 1))
        raise AssertionError("unreachable")

    def query(self, path: str, *, allow_refresh=True, payload=None) -> Any:
        if path not in SAFE_QUERY_PATHS:
            raise ValueError("仅允许安全接口使用认证补试")
        try:
            return self.request(path, payload=payload)
        except ApiError as error:
            if not error.auth or not allow_refresh or not self.refresh_enabled or self.refresh_attempted:
                raise
            index = self.refresh_once()
            return index if path == "/v1/user/index" else self.request(path, payload=payload)

    def refresh_once(self) -> dict:
        if self.refresh_attempted:
            raise ApiError("本进程已尝试刷新凭证，不再重复提交")
        if not self.refresh_enabled or not self.client_id or not self.client_secret:
            raise ApiError("保活需要显式开启并配置青龙应用凭证")
        self.refresh_attempted = True
        data = self.request("/v1/user/refreshToken")
        candidate = data.get("token") if isinstance(data, dict) else None
        if not isinstance(candidate, str) or not candidate.strip():
            raise ApiError("登录凭证刷新未返回 data.token")
        candidate = candidate.strip()
        try:
            expiry = token_expiry(candidate)
        except ValueError:
            raise ApiError("登录凭证刷新返回无效 JWT") from None
        if expiry <= self.clock() or expiry <= self.expiry:
            raise ApiError("刷新未延长凭证有效期，保活未确认")
        index = self.request("/v1/user/index", token=candidate)
        balance_from_index(index)
        # 候选凭证通过真正的查询验证之后，才替换内存值并回写。
        self.token, self.expiry = candidate, expiry
        try:
            written = self.writeback_func(self.original_token, candidate, self.client_id, self.client_secret)
            if not isinstance(written, WritebackResult):
                raise TypeError
        except Exception as error:
            written = WritebackResult(False, f"AKILE_TOKEN 回写异常（{type(error).__name__}）")
        self.credential = "登录凭证刷新并验证成功；" + safe_text(written.message, candidate, self.original_token, self.client_id, self.client_secret)
        if not written.ok:
            self.warnings.append(safe_text(written.message, candidate, self.original_token, self.client_id, self.client_secret))
        self.log(f"凭证：新凭证剩余有效期约 {max(0, int((expiry - self.clock()) / 60))} 分钟")
        return index

    def prepare(self, *, check_only=False) -> dict:
        self.log(f"凭证：当前剩余有效期约 {max(0, int((self.expiry - self.clock()) / 60))} 分钟")
        index = self.query("/v1/user/index", allow_refresh=not check_only)
        balance_from_index(index)
        if not check_only and self.refresh_enabled and not self.refresh_attempted and self.expiry - self.clock() < REFRESH_AHEAD_SECONDS:
            try:
                index = self.refresh_once()
            except ApiError as error:
                self.credential = f"提前刷新失败：{error}"
                self.warnings.append("登录凭证保活未完成：" + str(error))
        return index

    def submit_checkin(self) -> Any:
        if self.checkin_attempted:
            raise ApiError("本进程已提交签到，不再重复提交")
        self.checkin_attempted = True
        return self.request("/v1/user/Checkin")


# 签到执行与结果确认

@dataclass(frozen=True)
class CheckinLog:
    identity: int
    day: date
    amount: Decimal
    before: Decimal
    after: Decimal


def parse_checkin_log(raw: Any) -> CheckinLog | None:
    if not isinstance(raw, dict):
        raise ApiError("AK 币流水条目格式无效")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})签到", str(raw.get("remark", "")))
    if not match:
        return None
    try:
        identity = raw["id"]
        if type(identity) is not int or identity <= 0:
            raise ValueError
        amount, before, after = (coin_value(raw[key]) for key in ("amount", "before", "after"))
        if amount < 0:
            raise ValueError
        return CheckinLog(identity, date.fromisoformat(match[1]), amount, before, after)
    except (KeyError, TypeError, ValueError):
        raise ApiError("签到流水字段无效，未更新统计") from None


def valid_statistics(raw: Any) -> bool:
    try:
        if not isinstance(raw, dict):
            return False
        identity, streak = raw["last_checkin_log_id"], raw["streak"]
        if type(identity) is not int or type(streak) is not int or identity < 0 or streak < 0:
            return False
        total = coin_value(raw["total_checkin_earned"])
        if identity == 0:
            return streak == 0 and total == 0 and raw["last_checkin_date"] is None
        date.fromisoformat(raw["last_checkin_date"])
        return streak > 0 and total >= 0
    except (KeyError, TypeError, ValueError):
        return False


def accumulate_logs(previous: dict | None, records: list[CheckinLog]) -> dict:
    stats = dict(previous or {"last_checkin_date": None, "last_checkin_log_id": 0,
                              "streak": 0, "total_checkin_earned": "0"})
    total = coin_value(stats["total_checkin_earned"])
    for record in sorted(records, key=lambda item: item.identity):
        if record.identity <= stats["last_checkin_log_id"]:
            continue
        last_date = date.fromisoformat(stats["last_checkin_date"]) if stats["last_checkin_date"] else None
        if last_date and record.day < last_date:
            raise ApiError("签到流水日期顺序异常，未更新统计")
        if record.day != last_date:
            stats["streak"] = stats["streak"] + 1 if last_date and record.day == last_date + timedelta(days=1) else 1
        total += record.amount
        stats.update(last_checkin_date=record.day.isoformat(), last_checkin_log_id=record.identity,
                     total_checkin_earned=number_text(total))
    return stats


def sync_checkin_history(client: AkileClient, info: dict, *, save_state=True) -> tuple[CheckinLog | None, dict]:
    """正常只查最新页；首次初始化或找不到旧锚点时补齐历史。"""
    client.today_log = None
    today = datetime.fromtimestamp(client.clock(), timezone(timedelta(hours=8))).date()
    account, cached, anchor, usable = "", None, None, False
    found, complete, consumed, total = False, False, 0, None
    records: dict[int, CheckinLog] = {}
    seen_pages: set[str] = set()
    for page in range(1, 1001):
        body = client.query(LOG_PATH, payload={"page_num": page, "page_size": 10}, allow_refresh=False)
        items, count = body.get("list"), body.get("total")
        if not isinstance(items, list) or type(count) is not int or count < 0 or len(items) > 10:
            raise ApiError("AK 币流水分页格式无效")
        if total is None:
            total = count
        elif count != total:
            raise ApiError("查询期间流水总数变化，请下次运行校准统计")
        fingerprint = json.dumps(items, sort_keys=True, ensure_ascii=False)
        if items and fingerprint in seen_pages:
            raise ApiError("AK 币流水分页重复，未更新统计")
        seen_pages.add(fingerprint)
        consumed += len(items)
        for item in items:
            record = parse_checkin_log(item)
            if record is None:
                continue
            if record.day > today:
                raise ApiError("签到流水日期在未来，未更新统计")
            if record.identity in records and records[record.identity] != record:
                raise ApiError("相同签到流水 ID 内容冲突，未更新统计")
            records[record.identity] = record
            if record.day == today and (client.today_log is None or record.identity > client.today_log.identity):
                client.today_log = record
        if page == 1:
            # 先拿到今日流水；本地统计损坏不影响已证实的今日所得和余额。
            email = info.get("email") if isinstance(info, dict) else None
            if not email and isinstance(info, dict):
                email = str(info.get("uid") or info.get("id") or "")
            if not isinstance(email, str) or not email.strip():
                raise ApiError("用户信息缺少账号标识，未保存签到统计")
            account = hashlib.sha256(email.strip().casefold().encode("utf-8")).hexdigest()
            accounts = client.state.read("akile").get("accounts", {})
            cached = accounts.get(account) if isinstance(accounts, dict) else None
            usable = valid_statistics(cached) and (cached["last_checkin_date"] is None or date.fromisoformat(cached["last_checkin_date"]) <= today)
            anchor = cached["last_checkin_log_id"] if usable else None
        found = anchor in records if anchor else False
        if found and records[anchor].day.isoformat() != cached["last_checkin_date"]:
            found, usable, anchor = False, False, None
        complete = consumed >= total
        if found or complete:
            break
        if not items or len(items) < 10:
            raise ApiError("AK 币历史流水不完整，未保存部分统计")
    else:
        raise ApiError("AK 币流水页数过多，未保存部分统计")
    if usable and anchor and not found and max(records, default=0) < anchor:
        raise ApiError("流水快照早于已有统计，已保留统计，待下次运行校准")
    recalibrate = not usable or (anchor != 0 and not found)
    client.log(f"统计：{'历史校准' if recalibrate else '增量同步'}｜查询 {page} 页")
    selected = max((item for item in records.values() if item.day == today), key=lambda item: item.identity, default=None)
    if not save_state:
        return selected, accumulate_logs(None if recalibrate else cached, list(records.values()))

    def merge(current):
        current_accounts = current.get("accounts", {})
        current_accounts = dict(current_accounts) if isinstance(current_accounts, dict) else {}
        latest = current_accounts.get(account)
        # 在锁内重读：另一进程已推进时，不用旧查询结果覆盖较新的统计。
        if latest != cached and valid_statistics(latest):
            if latest["last_checkin_log_id"] >= max(records, default=0):
                return current
            if latest["last_checkin_log_id"] not in records:
                raise ApiError("统计已被其他进程更新，请下次运行同步")
            baseline = latest
        else:
            baseline = None if recalibrate else cached
        current_accounts[account] = accumulate_logs(baseline, list(records.values()))
        return {**current, "accounts": current_accounts}

    saved = client.state.update("akile", merge)
    return selected, saved["accounts"][account]


def balance_from_index(data: Any) -> Decimal:
    try:
        return coin_value(data["ak_coin"])
    except (KeyError, TypeError, ValueError):
        raise ApiError("用户汇总缺少有效 data.ak_coin") from None


def perform_checkin(client: AkileClient, check_only: bool) -> CheckinResult:
    before = balance_from_index(client.prepare(check_only=check_only))
    info = client.query("/v1/user/info", allow_refresh=not check_only)
    show_identity(info, client)

    def read_history():
        try:
            today_log, stats = sync_checkin_history(client, info, save_state=not check_only)
            return today_log, stats, ""
        except (ApiError, OSError, ValueError, RuntimeError) as error:
            warning = "签到统计未同步：" + safe_text(error)
            client.log(warning)
            return client.today_log, None, warning

    # 是否已签到由实际今日流水确认，不使用商城页的按钮时间公式。
    today_log, stats, history_warning = read_history()
    checked = today_log is not None
    if not checked and history_warning:
        return CheckinResult("warn", "未确认", balance=before,
                             warnings=["今日签到流水查询未完成，未提交签到", history_warning])
    if check_only and not checked:
        return CheckinResult("success", "今日未签到（仅查询）", balance=before)

    returned_balance, submit_error = None, None
    verification_errors = []
    if not checked and not check_only:
        client.log("签到：未找到今日流水，提交一次签到")
        try:
            returned_balance = coin_value(client.submit_checkin())
        except (ApiError, ValueError) as error:
            submit_error = error
        # 只复查用户信息和流水；超时也不重放签到请求。
        try:
            updated_info = client.query("/v1/user/info", allow_refresh=False)
            if isinstance(updated_info, dict):
                info = updated_info
        except ApiError as error:
            verification_errors.append(str(error))
        today_log, stats, history_warning = read_history()
    if today_log is not None:
        after = today_log.after
        verification_errors = []
    else:
        # 流水不可用时只回退查询余额，不用按钮状态或余额变化证明签到。
        after = None
        try:
            after = balance_from_index(client.query("/v1/user/index", allow_refresh=False))
        except ApiError as error:
            verification_errors.append(str(error))
        if not history_warning and isinstance(submit_error, ApiError) and submit_error.definite:
            return CheckinResult("fail", "未完成", balance=after, checkin_executed=client.checkin_attempted, error=str(submit_error))
        return CheckinResult("warn", "结果未确认", balance=after, checkin_executed=client.checkin_attempted,
                             warnings=["未找到今日签到流水，为避免重复签到未重试",
                                       *verification_errors, *([history_warning] if history_warning else [])])

    sign_status = "今日已签到" if checked else ("签到成功" if returned_balance is not None else "签到结果已确认")
    result = CheckinResult("success", sign_status, balance=after, earned_now=today_log.amount,
                          checkin_executed=client.checkin_attempted, warnings=verification_errors)
    if stats is not None:
        result.streak = stats["streak"]
        result.total_earned = coin_value(stats["total_checkin_earned"])
    if history_warning:
        result.warnings.append(history_warning)
    return result


def run_checkin(client: AkileClient, check_only=False) -> CheckinResult:
    try:
        # 合集和独立任务同时触发时，串行检查签到状态，避免同时提交和轮换凭证。
        with nullcontext() if check_only else client.state.locked("akile-run"):
            result = perform_checkin(client, check_only)
    except ApiError as error:
        result = CheckinResult("fail", "未完成", error=str(error))
    except (OSError, RuntimeError, ValueError) as error:
        result = CheckinResult("warn", "未确认", warnings=[safe_text(error)])
    result.credential = client.credential
    result.warnings = list(dict.fromkeys([*result.warnings, *client.warnings]))
    if result.status == "success" and result.warnings:
        result.status = "warn"
    return result


# 日志、通知与合集结果

def number_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _has_new_earnings(result: CheckinResult) -> bool:
    """通知只展示本次实际提交签到后确认的收益。"""
    return result.checkin_executed and result.earned_now is not None


def build_daily_details(result: CheckinResult) -> list[str]:
    if result.status == "fail":
        details = [result.error or "签到失败"]
    else:
        sign = result.sign_status
        if result.streak is not None:
            sign += f"｜连续{result.streak}天"
        details = [sign]
    coins = []
    if _has_new_earnings(result):
        coins.append(f"本次 +{number_text(result.earned_now)} AK币")
    if result.balance is not None:
        coins.append(f"余额 {number_text(result.balance)}")
    if result.total_earned is not None:
        coins.append(f"累计 {number_text(result.total_earned)}")
    if coins:
        details.append("｜".join(coins))
    if result.warnings:
        details.append("提醒：" + "；".join(result.warnings))
    return details


def format_result_log(result: CheckinResult) -> str:
    icon = {"success": "✅", "warn": "⚠️", "fail": "❌"}[result.status]
    lines = [f"{icon} 账号：AkileCloud", f"签到：{result.sign_status}"]
    if result.streak is not None:
        lines.append(f"连续：{result.streak}天")
    if result.earned_now is not None:
        label = "本次" if result.checkin_executed else "今日所得"
        lines.append(f"{label}：+{number_text(result.earned_now)} AK币")
    if result.balance is not None:
        lines.append(f"余额：{number_text(result.balance)} AK币")
    if result.total_earned is not None:
        lines.append(f"累计：{number_text(result.total_earned)} AK币")
    if result.error:
        lines.append(f"原因：{result.error}")
    if result.credential:
        lines.append(f"凭证：{result.credential}")
    if result.warnings:
        lines.append("提醒：" + "；".join(result.warnings))
    return "\n".join(lines)


def format_notification(result: CheckinResult, elapsed: float) -> str:
    icon = {"success": "✅", "warn": "⚠️", "fail": "❌"}[result.status]
    lines = ["📋 任务结果", "", f"{icon} AkileCloud", f"签到：{result.sign_status}"]
    if result.status == "fail":
        lines.append(f"原因：{result.error}")
    else:
        if result.streak is not None:
            lines.append(f"连续：{result.streak}天")
        if _has_new_earnings(result):
            lines.append(f"本次：+{number_text(result.earned_now)} AK币")
        coins = []
        if result.balance is not None:
            coins.append(f"余额：{number_text(result.balance)}")
        if result.total_earned is not None:
            coins.append(f"累计：{number_text(result.total_earned)}")
        if coins:
            lines.append("｜".join(coins))
    if result.warnings:
        lines.extend(["", "⚠️ 提醒", *result.warnings])
    lines.extend(["", f"⏱️ 耗时：{max(0, int(round(elapsed)))}秒", f"🕒 完成：{time.strftime('%m-%d %H:%M')}"])
    return "\n".join(lines)


def enabled(name, default=True):
    return os.getenv(name, "1" if default else "0").strip().casefold() not in {"0", "false", "no", "off", ""}


def show_identity(info, client):
    if not isinstance(info, dict):
        return
    for key in ("nickname", "username", "display_name", "uid"):
        value = info.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
            text = str(value)
            # 官方公开身份原样展示；敏感字段及控制字符不进入日志。
            if any(secret and secret in text for secret in (client.token, client.original_token, client.client_secret)):
                continue
            if re.search(r"[\r\n\x00-\x1f]|(?<!\d)1[3-9]\d{9}(?!\d)", text):
                continue
            client.log(f"官方账号 {key}：{text}")


class DryState:
    def __init__(self):
        self.data = {}
    def read(self, namespace):
        return self.data.get(namespace, {})
    def update(self, namespace, updater):
        self.data[namespace] = updater(self.read(namespace))
        return self.data[namespace]
    def locked(self, *args, **kwargs):
        return nullcontext()


class DrySession:
    """固定本地接口样本；不创建套接字，不发送真实业务请求。"""
    def __init__(self):
        self.signed = False
    def request(self, method, url, **kwargs):
        path = url.removeprefix(BASE)
        if path == "/v1/user/Checkin":
            self.signed = True
            data = {"data": "11"}
        elif path == "/v1/user/index":
            data = {"data": {"ak_coin": "11" if self.signed else "10"}}
        elif path == "/v1/user/info":
            data = {"data": {"uid": "预演账号", "nickname": "本地预演账号"}}
        elif path == LOG_PATH:
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            rows = [{"id": 1, "remark": today + "签到", "amount": "1", "before": "10", "after": "11"}] if self.signed else []
            data = {"list": rows, "total": len(rows)}
        else:
            raise RuntimeError("预演禁止未声明接口")
        data.update(status_code=200, status_msg="本地样本")
        class Response:
            status_code = 200
            def json(self):
                return data
        return Response()
    def close(self):
        pass


def send_summary(body, dry):
    if not enabled("QINGLONG_NOTIFY"):
        return "已关闭"
    if dry:
        return "预演通知已模拟（未联网）"
    # 通知执行在独立子进程内：异常输出被丢弃，超时不改变业务退出码。
    import subprocess
    python_code = """
import importlib.util, sys
try:
    if sys.argv[1]:
        spec = importlib.util.spec_from_file_location('ql_notice', sys.argv[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        import notify as module
    module.send('AkileCloud 签到与保活', sys.stdin.read())
except Exception:
    sys.exit(1)
"""
    directories = [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    attempts = [[sys.executable, "-c", python_code, ""]]
    for directory in directories:
        if not directory:
            continue
        path = Path(directory)
        if (path / "notify.py").is_file():
            attempts.append([sys.executable, "-c", python_code, str(path / "notify.py")])
        if (path / "sendNotify.js").is_file():
            js = "const fs=require('fs');Promise.resolve(require(process.argv[1]).sendNotify('AkileCloud 签到与保活',fs.readFileSync(0,'utf8'))).catch(()=>process.exit(1));"
            attempts.append(["node", "-e", js, str(path / "sendNotify.js")])
    for command in attempts:
        try:
            result = subprocess.run(command, input=body, text=True, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "通知不可用或失败（保留业务退出码）"


def main(argv=None):
    started = time.monotonic()
    dry = enabled("AKILE_DRY_RUN", False)
    def log(text):
        print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)
    print("==== AkileCloud 签到与保活 ====", flush=True)
    log("开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("运行模式：" + ("断网预演" if dry else "实际执行"))
    raw = os.getenv(TOKEN_ENV_NAME, "")
    lines = raw.splitlines(keepends=True)
    indexes = [i for i, line in enumerate(lines) if line.strip()]
    log(f"账号数量：{len(indexes)}")
    results = []
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    parser = argparse.ArgumentParser(description="AkileCloud 签到与保活")
    parser.add_argument("--check-only", action="store_true", help="仅查询，不签到、刷新、回写或保存统计")
    configuration_error = False
    try:
        options = parser.parse_args(argv)
    except SystemExit as error:
        if error.code == 0:
            return 0
        options = argparse.Namespace(check_only=True)
        configuration_error = True
        log("❌ 参数错误")
    disabled = {v.strip().casefold() for v in re.split(r"[,;|&\n]+", os.getenv("DAILY_ALL_DISABLED", ""))}
    service_disabled = bool(disabled.intersection({"akile", "akile_checkin", "akilecloud"}))
    client_id = os.getenv("CLIENT_ID", "").strip()
    client_secret = os.getenv("CLIENT_SECRET", "").strip()
    if not indexes:
        configuration_error = True
        log("❌ 阶段 1 参数检查：缺少必填 AKILE_TOKEN")
    if not dry and not options.check_only and enabled("AKILE_REFRESH_TOKEN", False) and not (client_id and client_secret):
        configuration_error = True
        log("❌ 阶段 1 参数检查：开启保活必须配置青龙应用凭证")
    # 回写按完整变量原值比较，保持其他账号及空行原样。
    current_value = raw
    for number, index in enumerate(indexes, 1):
        account_started = time.monotonic()
        stage = 0
        stage_started = account_started
        def account_log(text):
            nonlocal stage, stage_started
            now = time.monotonic()
            stage += 1
            log(f"账号 {number} 阶段 {stage}｜{text}｜阶段耗时 {now - stage_started:.2f}秒｜累计耗时 {now - account_started:.2f}秒")
            stage_started = now
        client = None
        try:
            account_log("参数检查")
            token = lines[index].strip()
            token_expiry(token)
            if configuration_error:
                raise ValueError("任务配置有误，未执行业务请求")
            if service_disabled:
                result = CheckinResult("skip", "已停用，未执行")
            else:
                def writeback(original, replacement, cid, secret):
                    nonlocal current_value
                    old_line = lines[index]
                    ending = "\r\n" if old_line.endswith("\r\n") else ("\n" if old_line.endswith("\n") else "")
                    new_lines = list(lines)
                    new_lines[index] = replacement + ending
                    updated = "".join(new_lines)
                    written = write_back_token(current_value, updated, cid, secret)
                    if written.ok:
                        lines[index] = new_lines[index]
                        current_value = updated
                    return written
                client = AkileClient(token, session=DrySession() if dry else None,
                                     logger=account_log, writeback_func=writeback,
                                     client_id=client_id, client_secret=client_secret)
                if dry:
                    client.refresh_enabled = False
                    client.state = DryState()
                    account_log("DRY_RUN：本地模拟签到、复核与统计，禁用真实刷新和回写")
                result = run_checkin(client, check_only=options.check_only)
        except Exception as error:
            result = CheckinResult("fail", "未完成", error="参数或执行异常（" + type(error).__name__ + "），请检查凭证格式、依赖和配置")
        finally:
            if client is not None and client.owns_session:
                client.session.close()
        results.append(result)
        if result.status == "skip":
            detail = ["⏭️ 已停用，未执行"]
        else:
            detail = format_result_log(result).splitlines()
        for text in detail:
            account_log(text)
        kind = "failure" if result.status in {"fail", "warn"} else ("skipped" if result.status == "skip" else ("alreadyComplete" if result.sign_status == "今日已签到" else "success"))
        stats["total"] += 1
        stats[kind] += 1
        log(f"账号 {number} 统计：总任务 1，成功 {int(kind == 'success')}，已完成 {int(kind == 'alreadyComplete')}，跳过 {int(kind == 'skipped')}，失败 {int(kind == 'failure')}，耗时 {time.monotonic() - account_started:.2f}秒")
    failures = sum(r.status in {"fail", "warn"} for r in results)
    successes = sum(r.status == "success" for r in results)
    skipped = sum(r.status == "skip" for r in results)
    status = "configuration-error" if configuration_error else ("partial-failure" if failures and successes else ("failure" if failures else ("dry-run" if dry else ("skipped" if skipped == len(results) else "success"))))
    code = 1 if configuration_error or failures else 0
    if os.getenv("DAILY_ALL_CHILD", "").strip() == "1":
        daily_status = "fail" if code else ("skip" if skipped == len(results) else "success")
        payload = {"version": 1, "status": daily_status, "details": [f"账号 {i}：" + "；".join(build_daily_details(r)) for i, r in enumerate(results, 1)]}
        if configuration_error:
            payload["details"].append("任务配置错误")
        print(DAILY_RESULT_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    body = f"账号总数 {len(indexes)}，成功 {successes}，失败 {failures}，跳过 {skipped}，状态 {status}"
    if configuration_error:
        body += "；任务配置错误"
    notice = send_summary(body, dry)
    elapsed = time.monotonic() - started
    print("----------------------------------------")
    log(body)
    log("子任务统计：" + json.dumps(stats, ensure_ascii=False))
    log(f"总耗时：{elapsed:.2f}秒；通知：{notice}")
    log("完成时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    log(f"最终状态：{status}；退出码 {code}")
    print("TASK_SUMMARY=" + json.dumps({"application": "AkileCloud", "mode": "dry-run" if dry else "live", "status": status,
          "accounts": len(indexes), "success": successes, "failure": failures, "skipped": skipped,
          "configurationError": configuration_error, "tasks": stats, "elapsedSeconds": round(elapsed, 3),
          "notification": notice, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
