#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 又拍云签到与每日任务
# cron: 45 8 * * *
#
# 来源：2331892928/Upyun_auto main.py（MIT）
# https://github.com/2331892928/Upyun_auto
# 提交：0668cbc900219ed1de18829c81483ee015cc36de
#
# SPDX-License-Identifier: MIT
#
# Copyright (c) 2331892928 / Upyun_auto contributors
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
"""又拍云（console.upyun.com）登录签到与每日任务 - 青龙维护版。

功能清点（相对上游 main.py）：
- POST /accounts/signin/ 使用用户名与密码登录，保留会话 Cookie
- GET/POST /activity/signin 检查并执行每日签到
- GET/POST /activity/tasks 领取每日任务（默认 unlimited；可选 limited）
- 移除脚本内硬编码空凭据、无超时请求；标准库 urllib 实现 HTTP
- 增加逐行多账号、UPYUN_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

UPYUN_ACCOUNTS：每个非空行一个账号，格式 用户名|密码；仅在第一个竖线处分割。
兼容单账号别名：同时设置 UPYUN_USER 与 UPYUN_PASS（仅当 UPYUN_ACCOUNTS 为空）。
UPYUN_ACTIONS：可选，逗号分隔 sign / task，默认 sign,task（与上游一致）。
UPYUN_TASK_SCOPE：unlimited（默认）/ limited / both；limited 含消费类任务，可能失败。
UPYUN_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..90。
UPYUN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：20 8 * * *。不打印密码、Cookie、Token 或原始响应。
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
            "d09de5880a4e46d8",
            "scripts/upyun_auto.py",
            "upyun_auto.py",
            "upyun_auto",
            "candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "又拍云签到与每日任务"
CATALOG_ID = "d09de5880a4e46d8"
LOGIN_URL = "https://console.upyun.com/accounts/signin/"
SIGN_URL = "https://console.upyun.com/activity/signin"
TASK_URL = "https://console.upyun.com/activity/tasks"
# 上游逆向得到的前端固定 x-token（非用户凭据）
TASK_X_TOKEN = "7c4ee7db-d67e-4912-b72b-9e2439352716"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1048576
MAX_ATTEMPTS = 3
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
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


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
    raw = env("UPYUN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("UPYUN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 90:
        raise SafeError("UPYUN_TIMEOUT 须在 5 到 90 秒之间")
    return value


def resolve_actions() -> List[str]:
    raw = env("UPYUN_ACTIONS", "sign,task").lower()
    if not raw:
        raw = "sign,task"
    actions: List[str] = []
    for part in re.split(r"[,;\s]+", raw):
        item = part.strip()
        if not item:
            continue
        if item not in {"sign", "task"}:
            raise SafeError("UPYUN_ACTIONS 仅允许 sign、task")
        if item not in actions:
            actions.append(item)
    if not actions:
        raise SafeError("UPYUN_ACTIONS 未包含有效动作")
    return actions


def resolve_task_scope() -> List[str]:
    raw = env("UPYUN_TASK_SCOPE", "unlimited").lower() or "unlimited"
    if raw == "unlimited":
        return ["unlimited"]
    if raw == "limited":
        return ["limited"]
    if raw == "both":
        return ["unlimited", "limited"]
    raise SafeError("UPYUN_TASK_SCOPE 仅允许 unlimited、limited、both")


def camouflage_ip() -> str:
    return "106.84.{}.{}".format(random.randint(146, 254), random.randint(1, 254))


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 用户名|密码")
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("用户名或密码为空")
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    return {"username": username, "password": password}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("UPYUN_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("UPYUN_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("UPYUN_USER")
    password = env("UPYUN_PASS")
    if username or password:
        if not username or not password:
            raise SafeError(
                "兼容别名需同时提供 UPYUN_USER 与 UPYUN_PASS；"
                "推荐改用 UPYUN_ACCOUNTS（用户名|密码）"
            )
        return [{"username": username, "password": password}]
    raise SafeError("未配置 UPYUN_ACCOUNTS；请按每个非空行 用户名|密码 填写")


def public_identity_from_payload(payload: Any, fallback_username: str) -> str:
    if isinstance(payload, dict):
        for key in (
            "nickname",
            "name",
            "username",
            "user_name",
            "display_name",
            "accountName",
            "account_name",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = compact(value, 64)
                if text and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    return text
        for nest in ("data", "user", "account", "result"):
            nested = payload.get(nest)
            if isinstance(nested, dict):
                found = public_identity_from_payload(nested, "")
                if found:
                    return found
    # 又拍云登录响应通常不含公开昵称；仅用用户名首尾脱敏展示不可用——按策略：
    # 官方未返回公开身份时使用账号序号（由调用方处理）。用户名属于登录凭据一部分，不打印。
    _ = fallback_username
    return ""


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

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


class UpyunClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.ip = camouflage_ip()
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def base_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": UA,
            "origin": "https://www.upyun.com",
            "referer": "https://www.upyun.com/onePiece",
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json; charset=utf-8",
            "Client-Ip": self.ip,
            "X-Forwarded-For": self.ip,
            "X-Real-IP": self.ip,
        }

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, bytes]:
        headers = self.base_headers()
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    status = getattr(response, "status", 200)
                    raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise SafeError("响应超过大小限制")
                return status, raw
            except urllib.error.HTTPError as error:
                status = error.code
                try:
                    raw = error.read(MAX_BYTES + 1)
                except Exception:
                    raw = b""
                finally:
                    error.close()
                if len(raw) > MAX_BYTES:
                    raise SafeError("响应超过大小限制")
                return status, raw
            except SafeError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < MAX_ATTEMPTS:
                    time.sleep(1)
                    continue
        raise SafeError("网络、超时或连接失败") from last_error


def load_json(raw: bytes) -> Any:
    if not raw:
        raise SafeError("响应为空")
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise SafeError("响应不是合法 JSON") from exc


def do_login(
    client: UpyunClient, username: str, password: str
) -> Tuple[str, str, Dict[str, Any]]:
    body = json.dumps(
        {"username": username, "password": password}, ensure_ascii=False
    ).encode("utf-8")
    status, raw = client.request(LOGIN_URL, "POST", body)
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict):
        raise SafeError("登录响应结构不符合预期")
    msg = payload.get("msg")
    if isinstance(msg, dict):
        messages = msg.get("messages")
        if isinstance(messages, list) and messages:
            first = messages[0]
            if first != "登录成功":
                raise SafeError("账号或密码错误")
    cookies = {cookie.name: cookie.value for cookie in client.jar}
    if not cookies:
        raise SafeError("登录未获得有效会话 Cookie")
    identity = public_identity_from_payload(payload, username)
    detail = "登录成功"
    if identity:
        detail = "登录成功；公开身份：{}".format(identity)
    return "success", detail, {"identity": identity, "payload": payload}


def do_sign(client: UpyunClient) -> Tuple[str, str, Dict[str, Any]]:
    status, raw = client.request(SIGN_URL, "GET")
    if status in (401, 403):
        raise SafeError("签到状态凭据无效或会话已过期")
    if status != 200:
        raise SafeError("获取签到状态失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict) or not payload.get("result"):
        raise SafeError("获取签到状态失败")
    today = str(date.today())
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("date") == today and item.get("signin") is True:
                return "alreadyComplete", "今日已签到，不可再次签到", {"already": True}
    status2, raw2 = client.request(SIGN_URL, "POST", b"")
    if status2 in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status2 != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status2))
    result = load_json(raw2)
    if not isinstance(result, dict):
        raise SafeError("签到响应结构不符合预期")
    if result.get("result") is True:
        return "success", "签到成功", {"already": False}
    message = compact(result.get("message") or result.get("msg") or "未知原因", 80)
    raise SafeError("签到失败：{}".format(message))


def do_tasks(
    client: UpyunClient, username: str, scopes: List[str]
) -> Tuple[str, str, Dict[str, Any]]:
    status, raw = client.request(TASK_URL, "GET")
    if status in (401, 403):
        raise SafeError("任务列表凭据无效或会话已过期")
    if status != 200:
        raise SafeError("获取任务列表失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict):
        raise SafeError("任务列表响应结构不符合预期")

    events: List[Tuple[str, Dict[str, Any]]] = []
    for scope in scopes:
        items = payload.get(scope)
        if items is None:
            continue
        if not isinstance(items, list):
            raise SafeError("任务列表字段 {} 结构不符合预期".format(scope))
        for item in items:
            if isinstance(item, dict) and item.get("event_id") is not None:
                events.append((scope, item))

    if not events:
        return "alreadyComplete", "当前无可执行任务", {"ok": 0, "fail": 0, "total": 0}

    ok = 0
    fail = 0
    details: List[str] = []
    for scope, item in events:
        event_id = item.get("event_id")
        description = compact(item.get("description") or event_id or "任务", 60)
        body = json.dumps(
            {"event_id": event_id, "accountName": username}, ensure_ascii=False
        ).encode("utf-8")
        try:
            status_t, raw_t = client.request(
                TASK_URL,
                "POST",
                body,
                extra_headers={"x-token": TASK_X_TOKEN},
            )
            if status_t in (401, 403):
                raise SafeError("任务提交凭据无效或会话已过期")
            if status_t != 200:
                raise SafeError("任务提交失败（HTTP {}）".format(status_t))
            task = load_json(raw_t)
            if not isinstance(task, dict):
                raise SafeError("任务响应结构不符合预期")
            if task.get("result"):
                ok += 1
                details.append("{}[{}]成功".format(description, scope))
            else:
                fail += 1
                reason = compact(task.get("message") or "未知原因", 60)
                details.append("{}[{}]失败:{}".format(description, scope, reason))
        except SafeError as error:
            # 鉴权类错误向上抛出；单任务业务失败计入 fail 后继续。
            message = str(error)
            if "凭据无效" in message or "会话已过期" in message:
                raise
            fail += 1
            details.append("{}[{}]失败:{}".format(description, scope, message))

    summary = "任务完成 {}/{}；失败 {}".format(ok, ok + fail, fail)
    if details:
        summary = "{}；明细：{}".format(summary, "；".join(details[:8]))
    if fail and not ok:
        return "failure", summary, {"ok": ok, "fail": fail, "total": ok + fail}
    if fail:
        # 部分任务失败：阶段记为 warning 语义上的 partial，但状态机仅有四态——
        # 记为 success 并由账号级汇总根据 fail 计数判定；此处记 failure 更保守。
        # 与上游一致：单个任务失败不阻断后续；账号成功要求全部任务成功。
        return "failure", summary, {"ok": ok, "fail": fail, "total": ok + fail}
    return "success", summary, {"ok": ok, "fail": fail, "total": ok + fail}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    actions: List[str],
    scopes: List[str],
    dry_run: bool,
) -> None:
    stage_no = 1

    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("用户名或密码为空")
        return "success", "账号密码本地格式检查通过，内容不输出", None

    runner.stage(stage_no, "参数检查", parameter_check)
    stage_no += 1

    if dry_run:
        runner.skip(stage_no, "登录", "断网预演：不请求登录接口")
        stage_no += 1
        if "sign" in actions:
            runner.skip(stage_no, "每日签到", "断网预演：不请求签到接口")
            stage_no += 1
        else:
            runner.skip(stage_no, "每日签到", "未启用 sign 动作")
            stage_no += 1
        if "task" in actions:
            runner.skip(stage_no, "每日任务", "断网预演：不请求任务接口")
            stage_no += 1
        else:
            runner.skip(stage_no, "每日任务", "未启用 task 动作")
            stage_no += 1
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = UpyunClient(timeout)
    business_ok = True
    any_action = False

    def login_stage():
        state, detail, result = do_login(
            client, account["username"], account["password"]
        )
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        return state, detail, result

    runner.stage(stage_no, "登录", login_stage)
    stage_no += 1

    if "sign" in actions:
        any_action = True
        sign_box: Dict[str, str] = {"state": "failure"}

        def sign_stage():
            state, detail, result = do_sign(client)
            sign_box["state"] = state
            return state, detail, result

        try:
            runner.stage(stage_no, "每日签到", sign_stage)
        except SafeError:
            # 与上游一致：签到失败不阻断后续每日任务
            business_ok = False
        if sign_box["state"] == "failure":
            business_ok = False
        stage_no += 1
    else:
        runner.skip(stage_no, "每日签到", "未启用 sign 动作")
        stage_no += 1

    if "task" in actions:
        any_action = True
        task_box: Dict[str, str] = {"state": "failure"}

        def task_stage():
            state, detail, result = do_tasks(client, account["username"], scopes)
            task_box["state"] = state
            return state, detail, result

        try:
            runner.stage(stage_no, "每日任务", task_stage)
        except SafeError:
            business_ok = False
        if task_box["state"] == "failure":
            business_ok = False
        stage_no += 1
    else:
        runner.skip(stage_no, "每日任务", "未启用 task 动作")
        stage_no += 1

    if not any_action:
        runner.status = "failure"
        return
    if runner.stats["failure"] or not business_ok:
        runner.status = "failure"
    elif runner.stats["success"] == 0 and runner.stats["alreadyComplete"] > 0:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"


PY_NOTIFY_RUNNER = r'''
import importlib.util
import json
import os
import socket
import sys
specification = json.load(sys.stdin)
if specification.get("dry_run"):
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    socket.socket = denied  # type: ignore
    socket.create_connection = denied  # type: ignore
    for name in ("system", "popen", "execv", "execve", "spawnv", "spawnve"):
        if hasattr(os, name):
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
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "upyun_auto.py",
        "candidate.py",
        "scripts/upyun_auto.py",
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


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("UPYUN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    actions = ["sign", "task"]
    scopes = ["unlimited"]
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("UPYUN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        actions = resolve_actions()
        scopes = resolve_task_scope()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；动作：{}；任务范围：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                ",".join(actions),
                ",".join(scopes),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, timeout, actions, scopes, dry_run)
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
