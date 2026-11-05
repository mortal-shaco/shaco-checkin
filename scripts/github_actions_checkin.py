#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Mirror O3 Pro 每日签到
# cron: 32 9 * * *
from __future__ import annotations
#
# 来源：fengyunzaidushi/mirroro3_autocheckin
# - github_actions_checkin.py（主源）
# - pve_checkin_cron.py（同应用参考，合并签到/积分/Token 刷新逻辑）
# https://github.com/fengyunzaidushi/mirroro3_autocheckin
# 提交：619d6933f0da84e187274011fed27a42ff762501
#
# 基于 billrice 原始代码；上游仓库 Copyright (c) 2025 Mirror O3 Pro Auto Checkin
#
# MIT License
#
# Copyright (c) 2025 Mirror O3 Pro Auto Checkin
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
"""Mirror O3 Pro（https://mirror.o3pro.pro）每日签到 - 青龙维护版。

功能清点（相对上游 github_actions_checkin.py / pve_checkin_cron.py）：
- 邮箱密码登录 /api/auth/login 获取 Bearer Token
- 校验 /api/auth/user，展示公开身份（用户名/邮箱/UID）
- 提交 /api/checkin 每日签到，并区分成功与今日已签到
- 查询 /api/credits/balance 积分余额（只读）
- 移除本地配置文件读写、状态文件落盘、SMTP 邮件、原始响应打印与无超时请求
- 青龙改为环境变量多账号与 cron 调度；上游建议每天 09:00

MIRRORO3_ACCOUNTS：每个非空行一个账号，格式 邮箱|密码；仅在第一个竖线处分割，
密码中后续竖线保留。不要用 & 或 @ 分隔账号。使用在 https://mirror.o3pro.pro 注册的邮箱与明文密码。
MIRRORO3_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
MIRRORO3_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 09:00（与上游 README / 安装脚本推荐一致）。不打印密码、Cookie、Token 或原始响应。
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
            "fadf97b9ea306b1b",
            "scripts/mirroro3_checkin.py",
            "mirroro3_checkin.py",
            "mirroro3_checkin",
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
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "Mirror O3 Pro 每日签到"
CATALOG_ID = "fadf97b9ea306b1b"
BASE_URL = "https://mirror.o3pro.pro"
LOGIN_PATH = "/api/auth/login"
USER_PATH = "/api/auth/user"
CHECKIN_PATH = "/api/checkin"
CREDITS_PATH = "/api/credits/balance"
DEFAULT_TIMEOUT = 20
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
ALREADY_MARKERS = (
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
    "username",
    "userName",
    "nickname",
    "nickName",
    "display_name",
    "displayName",
    "name",
    "nick",
    "email",
    "uid",
    "userId",
    "user_id",
    "id",
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
    "Content-Type": "application/json",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_timeout() -> float:
    raw = env("MIRRORO3_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("MIRRORO3_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("MIRRORO3_TIMEOUT 须在 5 到 60 秒之间")
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
            raise SafeError("账号行缺少分隔符；格式为 邮箱|密码")
        email, password = text.split("|", 1)
        email = email.strip()
        password = password.strip()
        if not email or not password:
            raise SafeError("邮箱或密码为空")
        if "@" not in email or "." not in email.split("@", 1)[-1]:
            raise SafeError("邮箱格式无效")
        if any(ord(ch) < 32 for ch in email) or any(ord(ch) < 32 for ch in password):
            raise SafeError("账号行含控制字符")
        accounts.append({"email": email, "password": password})
    return accounts


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates: List[Any] = [payload]
    for nest_key in ("user", "userInfo", "profile", "data"):
        nested = payload.get(nest_key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for mapping in candidates:
        if not isinstance(mapping, dict):
            continue
        for key in IDENTITY_KEYS:
            value = mapping.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                text = compact(value, 64)
                if not text:
                    continue
                lowered = key.lower()
                if lowered in {"token", "password", "access_token", "authtoken"}:
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if lowered == "email" or ("@" in text and "." in text.split("@", 1)[-1]):
                    return text
                if len(text) > 48 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                return text
    return ""


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "errorMsg", "error_msg", "tip", "desc", "error"):
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


def is_already_checked(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker.lower() in lowered for marker in ALREADY_MARKERS)


def classify_checkin(payload: Any, http_status: int) -> Tuple[str, str]:
    if http_status != 200:
        return "failure", "签到请求失败（HTTP {}）".format(http_status)
    message = business_message(payload) if isinstance(payload, dict) else ""
    if is_already_checked(message):
        return "alreadyComplete", "今日已签到（业务提示）"
    if isinstance(payload, dict):
        success_flag = payload.get("success")
        if success_flag is True:
            detail = "签到成功（业务字段已核实）"
            if message and len(message) <= 64:
                detail = "签到成功；{}".format(message)
            return "success", detail
        if success_flag is False:
            if message:
                return "failure", "签到业务失败"
            return "failure", "签到业务失败（success=false）"
        # 上游默认 success 缺省视为成功（HTTP 200）
        detail = "签到成功（HTTP 200）"
        if message and len(message) <= 64:
            detail = "签到成功；{}".format(message)
        return "success", detail
    if payload is None:
        return "success", "签到成功（HTTP 200，无 JSON 体）"
    return "failure", "签到业务失败（缺少可核实成功字段）"


def format_credits(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    balance = payload.get("balance")
    if not isinstance(balance, dict):
        return ""
    available = balance.get("available")
    used = balance.get("used")
    parts = []
    if isinstance(available, (int, float)) and not isinstance(available, bool):
        parts.append("可用 {}".format(available))
    if isinstance(used, (int, float)) and not isinstance(used, bool):
        parts.append("已用 {}".format(used))
        if isinstance(available, (int, float)) and not isinstance(available, bool):
            parts.append("合计 {}".format(available + used))
    return "；".join(parts)


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


class MirrorO3Client:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.token = ""
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def auth_headers(self) -> Dict[str, str]:
        headers = dict(BROWSER_HEADERS)
        if self.token:
            headers["Authorization"] = "Bearer {}".format(self.token)
        return headers

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        authenticated: bool = False,
    ) -> Tuple[int, Any]:
        url = BASE_URL + path
        headers = self.auth_headers() if authenticated else dict(BROWSER_HEADERS)
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("content-type", "")
                raw = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            content_type = error.headers.get("content-type", "") if error.headers else ""
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
        if "application/json" not in content_type.lower() and not raw.lstrip().startswith(
            (b"{", b"[")
        ):
            raise SafeError("响应不是可解析的业务 JSON")
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise SafeError("响应不是合法 JSON") from exc


def do_login(client: MirrorO3Client, email: str, password: str) -> str:
    status, result = client.request_json(
        LOGIN_PATH,
        method="POST",
        payload={"email": email, "password": password},
        authenticated=False,
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效或没有访问权限")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    token = result.get("token") or result.get("access_token")
    if not isinstance(token, str) or not token.strip():
        data = result.get("data")
        if isinstance(data, dict):
            token = data.get("token") or data.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise SafeError("登录成功但未返回可用 Token")
    client.token = token.strip()
    return client.token


def do_fetch_user(client: MirrorO3Client) -> Tuple[str, Any]:
    status, result = client.request_json(USER_PATH, method="GET", authenticated=True)
    if status in (401, 403):
        raise SafeError("用户信息凭据无效或会话已过期")
    if status != 200:
        raise SafeError("用户信息请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("用户信息响应无法解析")
    identity = extract_identity(result)
    if not identity:
        raise SafeError("用户信息成功但未返回可公开身份")
    return identity, result


def do_credits(client: MirrorO3Client) -> Tuple[str, Any]:
    status, result = client.request_json(CREDITS_PATH, method="GET", authenticated=True)
    if status in (401, 403):
        raise SafeError("积分查询凭据无效或会话已过期")
    if status != 200:
        raise SafeError("积分查询失败（HTTP {}）".format(status))
    detail = format_credits(result)
    if not detail:
        return "success", "积分查询成功（无明细字段）"
    return "success", "积分余额：{}".format(detail)


def do_checkin(client: MirrorO3Client) -> Tuple[str, str]:
    status, result = client.request_json(
        CHECKIN_PATH, method="POST", payload={}, authenticated=True
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    state, detail = classify_checkin(result, status)
    if state == "failure":
        raise SafeError(detail)
    return state, detail


def run_account(
    runner: AccountRunner,
    email: str,
    password: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录获取 Token", "断网预演：不请求登录接口")
        runner.skip(3, "公开身份", "断网预演：无官方身份返回")
        runner.skip(4, "查询签到前积分", "断网预演：不请求积分接口")
        runner.skip(5, "提交每日签到", "断网预演：不请求签到接口")
        runner.skip(6, "查询签到后积分", "断网预演：不请求积分接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = MirrorO3Client(timeout)

    def login_stage():
        do_login(client, email, password)
        return "success", "登录成功，已获取会话 Token（内容不输出）", None

    runner.stage(2, "登录获取 Token", login_stage)

    def identity_stage():
        identity, _payload = do_fetch_user(client)
        runner.identity = identity
        return "success", "公开账号身份：{}".format(identity), None

    runner.stage(3, "公开身份", identity_stage)

    def credits_before():
        state, detail = do_credits(client)
        return state, detail, None

    runner.stage(4, "查询签到前积分", credits_before)

    def checkin_stage():
        state, detail = do_checkin(client)
        return state, detail, None

    runner.stage(5, "提交每日签到", checkin_stage)

    def credits_after():
        state, detail = do_credits(client)
        return state, detail, None

    runner.stage(6, "查询签到后积分", credits_after)
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
        "mirroro3_checkin.py",
        "candidate.py",
        "scripts/mirroro3_checkin.py",
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
    dry_setting = env("MIRRORO3_DRY_RUN", "0").lower()
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
            raise SafeError("MIRRORO3_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        raw_accounts = env("MIRRORO3_ACCOUNTS")
        if not raw_accounts:
            raise SafeError(
                "未配置 MIRRORO3_ACCOUNTS；请按每个非空行 邮箱|密码 填写"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("MIRRORO3_ACCOUNTS 没有有效账号行")
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
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["email"],
                    item["password"],
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
