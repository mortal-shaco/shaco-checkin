#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: CordCloud 每日签到
# cron: 38 8 * * *
#
# 来源：yanglbme/cordcloud-action app/action.py（MIT）
# https://github.com/yanglbme/cordcloud-action
# 提交：16b0b61483ac99124b6ea1ced39b4b16d7139a8d
# 合并入口行为参考同仓库 main.py（登录、签到、流量、多站点回退、可选 TOTP）
#
# The MIT License (MIT)
# Copyright © 2020 <copyright Yang Libin>
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
"""CordCloud 每日签到 - 青龙维护版。

功能清点（相对上游 action.py + main.py）：
- 邮箱与密码登录 CordCloud SSPanel 站点（POST /auth/login）
- 可选两步验证 TOTP 密钥，生成登录验证码
- 多站点主机名依次尝试，网络异常时回退下一站点；账号/密码错误立即停止
- POST /user/checkin 完成每日签到，识别「您似乎已经签到过」为已完成
- 从签到响应 trafficInfo 或用户页 HTML 读取今日已用 / 过去已用 / 剩余流量
- 统一多账号为 CORDCLOUD_ACCOUNTS 每行 邮箱|密码，可选 ||TOTP密钥
- 移除 verify=False、requests 依赖、GitHub Actions toolkit 与凭据/原始响应打印
- 增加 CORDCLOUD_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

CORDCLOUD_ACCOUNTS：每个非空行一个账号，格式 邮箱|密码；启用两步验证时为 邮箱|密码||TOTP密钥。
仅在首个 | 分割邮箱与后续字段；密码中后续单个 | 保留。TOTP 使用 || 引入。
未设置本变量时兼容 CORDCLOUD_EMAIL + CORDCLOUD_PASSWD（可选 CORDCLOUD_SECRET）。
CORDCLOUD_HOST：逗号分隔的官方主机名列表，默认 cordcloud.us,cordcloud.one,cordcloud.biz,c-cloud.xyz。
CORDCLOUD_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
CORDCLOUD_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
建议 Cron：0 8 * * *（对齐上游 Actions 的 UTC 0:00）。不打印密码、Cookie、TOTP 或原始响应。
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
            "acd4b880b9d34d61",
            "scripts/cordcloud_checkin.py",
            "cordcloud_checkin.py",
            "cordcloud_checkin",
            "candidate.py",
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
import hashlib
import hmac
import http.cookiejar
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "CordCloud 每日签到"
CATALOG_ID = "acd4b880b9d34d61"
DEFAULT_HOSTS = "cordcloud.us,cordcloud.one,cordcloud.biz,c-cloud.xyz"
DEFAULT_TIMEOUT = 15
MAX_BYTES = 1024 * 1024
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
ALREADY_HINTS = (
    "您似乎已经签到过",
    "已经签到",
    "已签到",
    "签到过",
    "重复签到",
    "already checked",
    "already check",
)
CREDENTIAL_HINTS = (
    "密码错误",
    "邮箱不存在",
    "邮箱或密码",
    "用户不存在",
    "账号不存在",
    "帐号不存在",
    "登录失败",
    "凭证",
    "验证码错误",
    "两步验证",
    "二次验证",
    "2fa",
    "totp",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)
HOST_RE = re.compile(
    r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


class CredentialError(SafeError):
    """账号或密码类错误，不应再尝试其他站点。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env("CORDCLOUD_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("CORDCLOUD_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("CORDCLOUD_TIMEOUT 须在 5 到 60 秒之间")
    return value


def normalize_host(raw: str) -> str:
    host = raw.strip()
    host = re.sub(r"^https?://", "", host, flags=re.I)
    host = host.split("/", 1)[0].strip().lower()
    if not host or not HOST_RE.fullmatch(host) or "." not in host:
        raise SafeError("CORDCLOUD_HOST 含无效主机名，仅允许官方 HTTPS 域名")
    return host


def resolve_hosts() -> List[str]:
    raw = env("CORDCLOUD_HOST") or DEFAULT_HOSTS
    hosts: List[str] = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        hosts.append(normalize_host(text))
    if not hosts:
        raise SafeError("CORDCLOUD_HOST 未提供有效站点")
    # 保序去重
    unique: List[str] = []
    seen = set()
    for item in hosts:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def totp_now(secret: str) -> str:
    cleaned = re.sub(r"\s+", "", secret or "").upper()
    if not cleaned:
        raise SafeError("TOTP 密钥为空")
    padding = "=" * ((8 - len(cleaned) % 8) % 8)
    try:
        key = base64.b32decode(cleaned + padding, casefold=True)
    except Exception as exc:
        raise SafeError("TOTP 密钥不是合法 Base32") from exc
    if not key:
        raise SafeError("TOTP 密钥解码后为空")
    counter = int(time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return str(code % 1000000).zfill(6)


def validate_account(email: str, password: str, secret: str = "") -> Dict[str, str]:
    email = email.strip()
    password = password.strip()
    secret = secret.strip()
    if not email or not password:
        raise SafeError("邮箱或密码为空")
    if any(ord(ch) < 32 for ch in email + password + secret):
        raise SafeError("账号行含控制字符")
    if "@" not in email:
        raise SafeError("邮箱格式无效：缺少 @")
    return {"email": email, "password": password, "secret": secret}


def parse_account_line(text: str) -> Dict[str, str]:
    # 仅在首个 | 分割邮箱；可选 TOTP 通过 || 引入，避免密码中的单个 | 被切开。
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 邮箱|密码 或 邮箱|密码||TOTP密钥")
    email, rest = text.split("|", 1)
    if "||" in rest:
        password, secret = rest.split("||", 1)
        if "||" in secret or "|" in secret:
            raise SafeError("TOTP 密钥不得包含 |；请检查账号行格式")
        return validate_account(email, password, secret)
    return validate_account(email, rest, "")


def load_accounts() -> List[Dict[str, str]]:
    raw = env("CORDCLOUD_ACCOUNTS")
    accounts: List[Dict[str, str]] = []
    if raw:
        for line in raw.replace("\r\n", "\n").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            accounts.append(parse_account_line(text))
        if not accounts:
            raise SafeError("CORDCLOUD_ACCOUNTS 中没有有效账号行")
        log("凭据来源：CORDCLOUD_ACCOUNTS")
        return accounts

    email = env("CORDCLOUD_EMAIL") or env("CC_EMAIL")
    password = env("CORDCLOUD_PASSWD") or env("CC_PASSWD")
    secret = env("CORDCLOUD_SECRET") or env("CC_SECRET")
    if email or password or secret:
        if not email or not password:
            raise SafeError(
                "兼容凭据不完整：请成对填写 CORDCLOUD_EMAIL 与 CORDCLOUD_PASSWD，"
                "或改用 CORDCLOUD_ACCOUNTS"
            )
        if "|" in email:
            raise SafeError("兼容凭据 CORDCLOUD_EMAIL 不应包含字段分隔符")
        accounts.append(validate_account(email, password, secret))
        log("凭据来源：CORDCLOUD_EMAIL/CORDCLOUD_PASSWD（兼容模式）")
        return accounts

    raise SafeError(
        "未配置凭据：请设置 CORDCLOUD_ACCOUNTS（每行 邮箱|密码 或 邮箱|密码||TOTP密钥）；"
        "兼容 CORDCLOUD_EMAIL + CORDCLOUD_PASSWD（可选 CORDCLOUD_SECRET）"
    )


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("msg", "message", "error", "errorMessage", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def looks_like_credential_error(message: str) -> bool:
    lowered = message.lower()
    return any(hint.lower() in lowered for hint in CREDENTIAL_HINTS)


def classify_checkin(payload: Any) -> Tuple[str, str]:
    if not isinstance(payload, dict):
        return "failure", "签到响应不是可解析的业务对象"
    message = business_message(payload)
    ret = payload.get("ret")
    for hint in ALREADY_HINTS:
        if hint.lower() in message.lower():
            return "alreadyComplete", "今日已签到（{}）".format(message or hint)
    if ret == 1:
        return "success", "签到成功" + ("：{}".format(message) if message else "")
    if message:
        return "failure", "签到业务失败"
    return "failure", "签到业务失败（缺少可核实成功字段）"


def parse_traffic_from_html(html: str) -> Optional[Dict[str, str]]:
    today = re.search(
        r'<span class="traffic-info">今日已用</span>.*?'
        r'<code class="card-tag tag-red">(.*?)</code>',
        html,
        re.S,
    )
    total = re.search(
        r'<span class="traffic-info">过去已用</span>.*?'
        r'<code class="card-tag tag-orange">(.*?)</code>',
        html,
        re.S,
    )
    rest = re.search(
        r'<span class="traffic-info">剩余流量</span>.*?'
        r'<code class="card-tag tag-green"[^>]*>(.*?)</code>',
        html,
        re.S,
    )
    if today and total and rest:
        return {
            "todayUsedTraffic": compact(today.group(1), 64),
            "lastUsedTraffic": compact(total.group(1), 64),
            "unUsedTraffic": compact(rest.group(1), 64),
        }
    return None


def traffic_from_payload(payload: Any) -> Optional[Dict[str, str]]:
    if not isinstance(payload, dict):
        return None
    info = payload.get("trafficInfo")
    if not isinstance(info, dict):
        return None
    today = info.get("todayUsedTraffic")
    last = info.get("lastUsedTraffic")
    unused = info.get("unUsedTraffic")
    if today is None or last is None or unused is None:
        return None
    return {
        "todayUsedTraffic": compact(today, 64),
        "lastUsedTraffic": compact(last, 64),
        "unUsedTraffic": compact(unused, 64),
    }


def format_traffic(info: Dict[str, str]) -> str:
    return "今日已用 {}，过去已用 {}，剩余流量 {}".format(
        info["todayUsedTraffic"],
        info["lastUsedTraffic"],
        info["unUsedTraffic"],
    )


class AccountRunner:
    def __init__(self, number: int, email: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = email
        self.message = ""
        self.traffic = ""
        self.host = ""

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


class CordClient:
    def __init__(self, host: str, timeout: float) -> None:
        self.host = host
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def url(self, path: str) -> str:
        return "https://{}/{}".format(self.host, path.lstrip("/"))

    def _headers(self, referer: str, ajax: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": "https://{}".format(self.host),
            "Referer": referer,
        }
        if ajax:
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        else:
            headers["Accept"] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            )
        return headers

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        form: Optional[Dict[str, str]] = None,
        ajax: bool = False,
        referer: Optional[str] = None,
    ) -> Tuple[int, bytes, str]:
        body = None
        if form is not None:
            body = urllib.parse.urlencode(form).encode("utf-8")
        request = urllib.request.Request(
            self.url(path),
            data=body,
            headers=self._headers(
                referer or self.url("user"),
                ajax=ajax or form is not None,
            ),
            method=method.upper(),
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read(MAX_BYTES + 1)
                ctype = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            status = error.code
            try:
                raw = error.read(MAX_BYTES + 1)
            except Exception:
                raw = b""
            finally:
                error.close()
            ctype = error.headers.get("Content-Type", "") if error.headers else ""
        except Exception as exc:
            raise SafeError("网络、超时或连接失败") from exc
        if len(raw) > MAX_BYTES:
            raise SafeError("响应超过大小限制")
        return status, raw, ctype

    def request_json(
        self,
        path: str,
        *,
        method: str = "POST",
        form: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> Tuple[int, Any]:
        status, raw, _ctype = self.request(
            path, method=method, form=form or {}, ajax=True, referer=referer
        )
        if not raw:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise SafeError("响应不是合法 JSON") from exc


def do_login(client: CordClient, email: str, password: str, secret: str) -> str:
    code = totp_now(secret) if secret else ""
    status, result = client.request_json(
        "auth/login",
        method="POST",
        form={"email": email, "passwd": password, "code": code},
        referer=client.url("auth/login"),
    )
    if status in (401, 403):
        raise CredentialError("登录凭据无效或没有访问权限")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    message = business_message(result)
    ret = result.get("ret")
    if ret == 1:
        return message or "登录成功"
    if looks_like_credential_error(message) or ret == 0:
        raise CredentialError("登录业务失败（账号、密码或两步验证可能无效）")
    raise SafeError("登录业务失败")


def do_checkin(client: CordClient) -> Tuple[str, str, Optional[Dict[str, str]]]:
    status, result = client.request_json(
        "user/checkin",
        method="POST",
        form={},
        referer=client.url("user"),
    )
    if status in (401, 403):
        raise CredentialError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    state, detail = classify_checkin(result)
    if state == "failure":
        raise SafeError(detail)
    return state, detail, traffic_from_payload(result)


def do_traffic_page(client: CordClient) -> Dict[str, str]:
    status, raw, _ctype = client.request("user", method="GET", referer=client.url("user"))
    if status in (401, 403):
        raise CredentialError("用户页凭据无效或会话已过期")
    if status != 200:
        raise SafeError("用户页请求失败（HTTP {}）".format(status))
    try:
        html = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        raise SafeError("用户页解码失败") from exc
    info = parse_traffic_from_html(html)
    if not info:
        raise SafeError("用户页未解析到流量信息")
    return info


def run_account(
    runner: AccountRunner,
    email: str,
    password: str,
    secret: str,
    hosts: List[str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if secret:
            totp_now(secret)
            return "success", "凭据与 TOTP 密钥本地格式检查通过，内容不输出", None
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "选择站点并登录", "断网预演：不请求登录接口")
        runner.skip(3, "提交每日签到", "断网预演：不请求签到接口")
        runner.skip(4, "读取流量信息", "断网预演：不请求用户页")
        runner.status = "dry-run"
        log("账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display()))
        return

    last_error = "全部站点均失败"
    checkin_box: Dict[str, Any] = {}

    def login_and_prepare():
        nonlocal last_error
        for host in hosts:
            log("账号 {}：尝试站点 {}".format(runner.display(), host))
            client = CordClient(host, timeout)
            try:
                message = do_login(client, email, password, secret)
                runner.host = host
                checkin_box["client"] = client
                return "success", "登录成功（{}）：{}".format(host, message or "会话已建立"), client
            except CredentialError as error:
                raise CredentialError("{}（站点 {}）".format(error, host)) from error
            except SafeError as error:
                last_error = "{}（站点 {}）".format(error, host)
                log(
                    "账号 {}：站点 {} 失败，尝试下一站点 — {}".format(
                        runner.display(), host, last_error
                    )
                )
                continue
        raise SafeError(last_error)

    runner.stage(2, "选择站点并登录", login_and_prepare)

    def checkin_stage():
        client = checkin_box["client"]
        state, detail, traffic = do_checkin(client)
        runner.message = detail
        checkin_box["traffic"] = traffic
        checkin_box["state"] = state
        return state, detail, None

    runner.stage(3, "提交每日签到", checkin_stage)

    def traffic_stage():
        traffic = checkin_box.get("traffic")
        if isinstance(traffic, dict):
            runner.traffic = format_traffic(traffic)
            return "success", runner.traffic, traffic
        client = checkin_box["client"]
        try:
            info = do_traffic_page(client)
            runner.traffic = format_traffic(info)
            return "success", runner.traffic, info
        except SafeError as error:
            # 流量查询为核对能力，失败不回滚已成功签到，但账号记为失败
            return "failure", "流量信息查询失败（{}）".format(error), None

    runner.stage(4, "读取流量信息", traffic_stage)

    if runner.stats["failure"]:
        runner.status = "failure"
        return
    if checkin_box.get("state") == "alreadyComplete" or runner.stats["alreadyComplete"]:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"
    if runner.traffic:
        log("账号 {} 流量：{}".format(runner.display(), runner.traffic))


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "cordcloud_checkin.py",
        "candidate.py",
        "scripts/cordcloud_checkin.py",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
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
    if dry_run:
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("CORDCLOUD_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    hosts = [normalize_host(item) for item in DEFAULT_HOSTS.split(",") if item.strip()]
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("CORDCLOUD_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        hosts = resolve_hosts()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；站点：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                ",".join(hosts),
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number, item["email"])
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["email"],
                    item["password"],
                    item.get("secret", ""),
                    hosts,
                    timeout,
                    dry_run,
                )
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in accounts if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in accounts if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in accounts if item.status == "failure"),
        "dry-run": sum(1 for item in accounts if item.status == "dry-run"),
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
    tasks = {key: sum(item.stats[key] for item in accounts) for key in STATES}
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
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log("最终状态：{}".format(final_label))
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
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
