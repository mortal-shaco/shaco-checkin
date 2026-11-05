#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NSSCTF 签到
# cron: 8 8 * * *
#
# 来源：wenject/nssctf_checkin nssctf_checkin.py（MIT）
# https://github.com/wenject/nssctf_checkin
# 提交：71a7b7d5b6ccf1d9902e70d6308ded3e0bbc93d8
#
# MIT License
#
# Copyright (c) wenject / nssctf_checkin contributors
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
"""NSSCTF（www.nssctf.cn）自动登录签到 - 青龙维护版。

功能清点（相对上游 nssctf_checkin.py / setup.sh）：
- POST /api/user/login/ 使用邮箱与密码登录并保持会话 Cookie
- POST /api/user/clockin/ 执行每日签到；业务 code=200 为成功
- HTTP 404 或「已签到」类文案视为今日已完成
- 登录成功后展示官方返回的公开用户名
- 移除交互式 input/getpass、命令行明文密码与 requests 依赖
- relatedSources 中的 setup.sh 仅为部署助手，不作为账号任务合并；仅采纳其每日 8:00 cron 建议
- 增加逐行多账号、NSSCTF_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

NSSCTF_ACCOUNTS：每个非空行一个账号，格式 邮箱|密码；仅在第一个竖线处分割，密码中可含竖线。
兼容单账号别名：同时设置 NSSCTF_USER 与 NSSCTF_PASS（仅当 NSSCTF_ACCOUNTS 为空）。
NSSCTF_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
NSSCTF_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 8 * * *。不打印密码、Cookie、Token 或原始响应。
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
            "c604755589e5c490",
            "scripts/nssctf_checkin.py",
            "nssctf_checkin.py",
            "candidate.py",
            "nssctf_checkin",
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
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "NSSCTF 签到"
CATALOG_ID = "c604755589e5c490"
BASE = "https://www.nssctf.cn/api"
LOGIN_URL = "{}/user/login/".format(BASE)
CLOCKIN_URL = "{}/user/clockin/".format(BASE)
DEFAULT_TIMEOUT = 15
MAX_BYTES = 1048576
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
    "重复签到",
    "已经签到",
    "今日已签",
    "签过到",
    "already checked in",
    "already signed",
)
IDENTITY_KEYS = (
    "username",
    "userName",
    "nickname",
    "nickName",
    "nick",
    "display_name",
    "displayName",
    "name",
    "id",
    "uid",
    "userId",
    "user_id",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
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
    raw = env("NSSCTF_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("NSSCTF_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("NSSCTF_TIMEOUT 须在 5 到 60 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 邮箱|密码")
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("邮箱或密码为空")
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
    raw = env("NSSCTF_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("NSSCTF_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("NSSCTF_USER")
    password = env("NSSCTF_PASS")
    if username or password:
        if not username or not password:
            raise SafeError(
                "兼容别名需同时提供 NSSCTF_USER 与 NSSCTF_PASS；"
                "推荐改用 NSSCTF_ACCOUNTS（邮箱|密码）"
            )
        return [{"username": username, "password": password}]
    raise SafeError(
        "未配置 NSSCTF_ACCOUNTS；请按每个非空行 邮箱|密码 填写"
    )


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "error", "detail", "Message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates: List[Any] = []
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data)
        for key in ("user", "userInfo", "profile", "account"):
            nested = data.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
    elif isinstance(data, str) and data.strip():
        # clockin 成功时 data 可能是连续签到天数；不是身份
        pass
    candidates.append(payload)
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
                if lowered in {"token", "authorization", "cookie", "session", "password"}:
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if "@" in text and key.lower() in {"username", "userName", "email"}:
                    # 邮箱本身可作为核对身份；不脱敏公开用户名/邮箱显示名以外的凭据
                    local = text.split("@", 1)[0]
                    if local:
                        return text
                if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                return text
    return ""


def is_already_signed(payload: Any) -> bool:
    message = business_message(payload)
    lowered = message.lower()
    if any(hint.lower() in lowered for hint in ALREADY_HINTS):
        return True
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, str) and any(hint in data for hint in ALREADY_HINTS):
            return True
    return False


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


class NssctfClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nssctf.cn/user/login",
            "Origin": "https://www.nssctf.cn",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def request_json(
        self,
        url: str,
        method: str = "GET",
        body: Optional[bytes] = None,
    ) -> Tuple[int, Any]:
        request = urllib.request.Request(
            url,
            data=body,
            headers=self._headers(),
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
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


def do_login(client: NssctfClient, username: str, password: str) -> Tuple[str, str, Any]:
    payload = json.dumps(
        {"username": username, "password": password, "remember": "1"},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    status, result = client.request_json(LOGIN_URL, "POST", payload)
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    if result.get("code") != 200:
        raise SafeError("登录业务失败")
    data = result.get("data")
    identity = extract_identity(result)
    detail = "登录成功"
    if identity:
        detail = "登录成功；公开身份：{}".format(identity)
    return "success", detail, {"identity": identity, "data": data, "payload": result}


def do_clockin(client: NssctfClient) -> Tuple[str, str, Any]:
    status, result = client.request_json(CLOCKIN_URL, "POST", b"{}")
    # 上游将 HTTP 404 视为今日已签到
    if status == 404:
        return "alreadyComplete", "今日已签到，无需重复签到", result
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        if isinstance(result, dict) and is_already_signed(result):
            return "alreadyComplete", "今日已签到，无需重复签到", result
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("签到响应无法解析")
    if result.get("code") == 200:
        days = result.get("data", "?")
        detail = "签到成功"
        if isinstance(days, (int, float, str)) and str(days).strip():
            detail = "签到成功；连续签到 {} 天".format(compact(days, 32))
        return "success", detail, result
    if is_already_signed(result):
        return "alreadyComplete", "今日已签到，无需重复签到", result
    raise SafeError("签到业务失败")


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("邮箱或密码为空")
        return "success", "账号密码本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录", "断网预演：不请求登录接口")
        runner.skip(3, "执行签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = NssctfClient(timeout)

    def login_stage():
        state, detail, result = do_login(client, account["username"], account["password"])
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        return state, detail, result

    runner.stage(2, "登录", login_stage)

    clockin_state_box: Dict[str, str] = {"state": "failure"}

    def clockin_stage():
        state, detail, result = do_clockin(client)
        identity = extract_identity(result)
        if identity:
            runner.identity = identity
            detail = "{}；公开身份：{}".format(detail, identity)
        clockin_state_box["state"] = state
        return state, detail, result

    runner.stage(3, "执行签到", clockin_stage)

    if runner.stats["failure"]:
        runner.status = "failure"
    elif clockin_state_box["state"] == "alreadyComplete":
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
        "nssctf_checkin.py",
        "candidate.py",
        "scripts/nssctf_checkin.py",
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
    dry_setting = env("NSSCTF_DRY_RUN", "0").lower()
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
            raise SafeError("NSSCTF_DRY_RUN 配置无效，停止执行")
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
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, timeout, dry_run)
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
