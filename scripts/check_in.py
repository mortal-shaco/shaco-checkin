#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: VManAPI 每日签到
# cron: 23 8 * * *
#
# 来源：Jasonliu-0/VManAPI-check_in check_in.py（MIT）
# https://github.com/Jasonliu-0/VManAPI-check_in
# 提交：e14fca9799a21f4756723135f3f2593b0fc1d712
#
# MIT License
#
# Copyright (c) 2025 VManAPI Auto Check-in
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
"""VManAPI（donate.avman.ai）每日签到 - 青龙维护版。

功能清点（相对上游 check_in.py）：
- POST https://donate.avman.ai/api/check_in，使用 Authorization Token 签到
- 保留请求头随机化（User-Agent / Accept-Language / Chromium Client Hints）
- 保留多账号轮询与账号间随机延迟；青龙改为每行一个账号
- 移除原始响应打印；增加超时、业务成功判定、断网预演、时间轴日志、青龙通知与 TASK_SUMMARY
- 无发帖/评论/分享类公开内容动作，不调用一言

VMAN_AUTHORIZATION：每个非空行一个 Authorization Token（JWT）。
可选格式 备注|token：仅在第一个竖线处分割，竖线后的 token 原文保留。
兼容单行内 name:token（token 以 eyJ 开头时）；不再使用逗号分隔多账号。
VMAN_TIMEOUT：单次 HTTPS 请求超时秒数，默认 30，范围 5..120。
VMAN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 8 * * *（与上游 GitHub Actions 北京时间 08:00 一致）。
不打印 Token、原始响应或设备标识；JWT 载荷中的公开 userId 可直接显示。
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
        _ql_notify_identities = ('bb9220b13809926a', 'scripts/check_in.py', 'check_in.py', 'check_in')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "VManAPI 每日签到"
CATALOG_ID = "bb9220b13809926a"
BASE_URL = "https://donate.avman.ai"
CHECK_IN_URL = "{}/api/check_in".format(BASE_URL)
DEFAULT_TIMEOUT = 30
MAX_BYTES = 65536
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
    "已签到",
    "已经签到",
    "重复签到",
    "今日已签",
    "签到过",
    "already checked in",
    "already signed in",
    "already signed",
)
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "display_name",
    "displayName",
    "username",
    "userName",
    "name",
    "nick",
    "uid",
    "userId",
    "user_id",
    "id",
)
ACCEPT_LANGUAGES = (
    "zh-CN,zh;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "zh-CN,zh;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
)
BROWSERS = (
    {
        "name": "Chrome",
        "versions": ("120.0.0.0", "121.0.0.0", "122.0.0.0", "123.0.0.0", "124.0.0.0"),
        "ua_template": (
            "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/{version} Safari/537.36"
        ),
    },
    {
        "name": "Edge",
        "versions": ("120.0.0.0", "121.0.0.0", "122.0.0.0", "123.0.0.0"),
        "ua_template": (
            "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/{chrome_ver} Safari/537.36 Edg/{version}"
        ),
    },
    {
        "name": "Firefox",
        "versions": ("121.0", "122.0", "123.0", "124.0", "125.0"),
        "ua_template": (
            "Mozilla/5.0 ({os}; rv:{version}) Gecko/20100101 Firefox/{version}"
        ),
    },
)
OS_CONFIGS = (
    {
        "os_string": "Windows NT 10.0; Win64; x64",
        "sec_ch_ua_platform": '"Windows"',
    },
    {
        "os_string": "Windows NT 11.0; Win64; x64",
        "sec_ch_ua_platform": '"Windows"',
    },
    {
        "os_string": "Macintosh; Intel Mac OS X 10_15_7",
        "sec_ch_ua_platform": '"macOS"',
    },
    {
        "os_string": "Macintosh; Intel Mac OS X 13_5_0",
        "sec_ch_ua_platform": '"macOS"',
    },
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
    raw = env("VMAN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("VMAN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("VMAN_TIMEOUT 须在 5 到 120 秒之间")
    return value


def normalize_token(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise SafeError("Authorization Token 为空")
    lowered = text.lower()
    if lowered.startswith("authorization:"):
        text = text.split(":", 1)[1].strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    if not text:
        raise SafeError("Authorization Token 为空")
    if any(ch.isspace() for ch in text):
        raise SafeError("Authorization Token 格式无效（含空白）")
    return text


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def identity_from_token(token: str) -> str:
    payload = decode_jwt_payload(token)
    for key in IDENTITY_KEYS:
        value = payload.get(key)
        if value is None or isinstance(value, bool):
            continue
        text = compact(value, 64)
        if text:
            return text
    return ""


def parse_account_line(line: str, index: int) -> Dict[str, str]:
    text = line.strip()
    label = ""
    token_raw = text
    if "|" in text:
        label, token_raw = text.split("|", 1)
        label = label.strip()
    elif ":" in text and not text.startswith("eyJ"):
        # 兼容上游 name:token；JWT 通常以 eyJ 开头，避免误拆载荷
        left, right = text.split(":", 1)
        if right.strip().startswith("eyJ") or len(right.strip()) > 20:
            label, token_raw = left.strip(), right
    token = normalize_token(token_raw)
    return {
        "label": label or "账号{}".format(index),
        "token": token,
        "identity_hint": identity_from_token(token),
    }


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text, len(accounts) + 1))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("VMAN_AUTHORIZATION")
    if not raw:
        raise SafeError(
            "未配置 VMAN_AUTHORIZATION；请按每个非空行一个 Authorization Token 填写"
        )
    accounts = parse_accounts(raw)
    if not accounts:
        raise SafeError("VMAN_AUTHORIZATION 没有有效账号行")
    return accounts


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "error", "detail", "Message", "Msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    data = payload.get("data")
    if isinstance(data, str) and data.strip():
        return compact(data)
    return ""


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    stack: List[Any] = [payload]
    seen = 0
    while stack and seen < 40:
        current = stack.pop(0)
        seen += 1
        if not isinstance(current, dict):
            continue
        for key in IDENTITY_KEYS:
            if key not in current:
                continue
            value = current.get(key)
            if value is None or isinstance(value, bool):
                continue
            text = compact(value, 64)
            if not text:
                continue
            lowered = key.lower()
            if lowered in {"token", "authorization", "cookie", "session", "password"}:
                continue
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                continue
            if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                continue
            return text
        for value in current.values():
            if isinstance(value, dict):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(item for item in value if isinstance(item, dict))
    return ""


def is_already_signed(payload: Any) -> bool:
    message = business_message(payload).lower()
    if any(hint.lower() in message for hint in ALREADY_HINTS):
        return True
    if isinstance(payload, dict):
        for key in ("code", "status", "errno", "error_code"):
            value = payload.get(key)
            if isinstance(value, str) and any(
                hint.lower() in value.lower() for hint in ALREADY_HINTS
            ):
                return True
    return False


def classify_check_in(status: int, payload: Any) -> Tuple[str, str]:
    if status in (401, 403):
        raise SafeError("签到凭据无效或已过期")
    if status != 200:
        if is_already_signed(payload):
            return "alreadyComplete", "今日已签到，无需重复签到"
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if payload is None:
        return "success", "签到成功（空响应体，HTTP 200）"
    if is_already_signed(payload):
        return "alreadyComplete", "今日已签到，无需重复签到"
    if isinstance(payload, dict):
        if payload.get("success") is False:
            message = business_message(payload)
            if message and any(hint.lower() in message.lower() for hint in ALREADY_HINTS):
                return "alreadyComplete", "今日已签到，无需重复签到"
            raise SafeError("签到业务失败")
        code = payload.get("code", payload.get("status", payload.get("errno")))
        if code is not None and code not in (0, 200, "0", "200", True, "ok", "OK", "success"):
            if is_already_signed(payload):
                return "alreadyComplete", "今日已签到，无需重复签到"
            # 上游以 HTTP 200 为准；仅在明确失败字段时拒绝
            if payload.get("success") is True:
                pass
            elif isinstance(code, (int, float)) and int(code) not in (0, 200):
                message = business_message(payload)
                if message:
                    raise SafeError("签到业务失败")
                raise SafeError("签到业务失败")
        detail = "签到成功"
        message = business_message(payload)
        if message and not any(hint.lower() in message.lower() for hint in ALREADY_HINTS):
            if "成功" in message or "签到" in message:
                detail = compact(message, 120)
        return "success", detail
    return "success", "签到成功"


def generate_headers(authorization: str) -> Dict[str, str]:
    browser = random.choice(BROWSERS)
    os_config = random.choice(OS_CONFIGS)
    version = random.choice(browser["versions"])
    if browser["name"] == "Edge":
        chrome_ver = random.choice(BROWSERS[0]["versions"])
        ua = browser["ua_template"].format(
            os=os_config["os_string"],
            chrome_ver=chrome_ver,
            version=version,
        )
        sec_ch_ua = (
            '"Microsoft Edge";v="{edge}", "Chromium";v="{chrome}", "Not?A_Brand";v="8"'
        ).format(edge=version.split(".")[0], chrome=chrome_ver.split(".")[0])
    elif browser["name"] == "Chrome":
        ua = browser["ua_template"].format(
            os=os_config["os_string"],
            version=version,
        )
        sec_ch_ua = (
            '"Google Chrome";v="{ver}", "Chromium";v="{ver}", "Not?A_Brand";v="8"'
        ).format(ver=version.split(".")[0])
    else:
        ua = browser["ua_template"].format(
            os=os_config["os_string"],
            version=version,
        )
        sec_ch_ua = None
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Origin": BASE_URL,
        "Referer": "{}/checkIn?_userMenuKey=checkIn".format(BASE_URL),
        "User-Agent": ua,
    }
    if sec_ch_ua:
        headers.update(
            {
                "Sec-Ch-Ua": sec_ch_ua,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": os_config["sec_ch_ua_platform"],
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )
    return headers


class AccountRunner:
    def __init__(self, number: int, label: str = "") -> None:
        self.number = number
        self.label = label
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def display(self) -> str:
        return self.identity or self.label or "账号{}".format(self.number)

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


def http_post_json(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, Any]:
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers=headers,
        method="POST",
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
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SafeError("响应不是合法 UTF-8") from exc
    try:
        return status, json.loads(text)
    except ValueError as exc:
        raise SafeError("响应不是合法 JSON") from exc


def do_check_in(token: str, timeout: float) -> Tuple[str, str, Any]:
    headers = generate_headers(token)
    status, payload = http_post_json(CHECK_IN_URL, headers, timeout)
    state, detail = classify_check_in(status, payload)
    identity = extract_identity(payload)
    if identity:
        detail = "{}；公开身份：{}".format(detail, identity)
    return state, detail, {"payload": payload, "identity": identity}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    if account.get("identity_hint"):
        runner.identity = account["identity_hint"]

    def parameter_check():
        token = account["token"]
        if len(token) < 8:
            raise SafeError("Authorization Token 过短，疑似无效")
        hint = account.get("identity_hint") or ""
        if hint:
            runner.identity = hint
            return (
                "success",
                "Token 本地格式检查通过；JWT 公开标识：{}".format(hint),
                None,
            )
        return "success", "Token 本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "提交每日签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    def check_in_stage():
        state, detail, result = do_check_in(account["token"], timeout)
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        elif account.get("identity_hint"):
            runner.identity = account["identity_hint"]
        return state, detail, result

    runner.stage(2, "提交每日签到", check_in_stage)
    runner.status = (
        "alreadyComplete" if runner.stats["alreadyComplete"] else "success"
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
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "vmanapi_check_in.py",
        "candidate.py",
        "check_in.py",
        "scripts/vmanapi_check_in.py",
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
    dry_setting = env("VMAN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("VMAN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
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
            runner = AccountRunner(number, item.get("label", ""))
            accounts.append(runner)
            try:
                run_account(runner, item, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                delay = random.uniform(2, 5)
                log("账号间隔：等待 {:.1f} 秒后处理下一账号".format(delay))
                time.sleep(delay)

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
