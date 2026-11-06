#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Holmes AI 每日签到
# cron: 14 8 * * *
#
# 来源：BamarAirdropGroup/HOLMESAI_DAILY_CHECKIN bot.py（MIT）
# https://github.com/BamarAirdropGroup/HOLMESAI_DAILY_CHECKIN
# 提交：b45c7937f4d462f2b0aa7cf8173bca92e72bcd47
#
# MIT License
#
# Copyright (c) 2026 BamarAirdropGroup
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
"""Holmes AI（api.holmesai.xyz）Web3 钱包登录后每日签到 - 青龙维护版。

功能清点（相对上游 bot.py）：
- Web3LoginGetMessage / Web3LoginVerifySign：以太坊私钥签名登录并维持会话 Cookie
- GetUser：读取积分与当日签到状态（CheckinDone）
- CheckIn：未签到时提交每日签到；RetCode=0 为成功，已签到视为已完成
- 移除交互式代理选择、accounts.txt/proxy.txt 本地文件、24 小时死循环与清屏
- 移除上游硬编码邀请码默认值（不安全默认副作用）；仅在显式配置 HOLMESAI_INVITE_CODE 时提交
- 增加逐行多账号、HOLMESAI_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

HOLMESAI_PRIVATE_KEYS：每个非空行一个 EVM 私钥（可选 0x 前缀，64 位十六进制）。
兼容单账号别名：HOLMESAI_PRIVATE_KEY（仅当规范变量为空）。
HOLMESAI_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 8 * * *。不打印私钥、Cookie、签名或原始响应；钱包地址为公开身份可直接显示。
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
        _ql_notify_identities = ('5bb7859665960364', 'scripts/bot.py', 'bot.py', 'bot')
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

TITLE = "Holmes AI 每日签到"
CATALOG_ID = "5bb7859665960364"
BASE_API = "https://api.holmesai.xyz"
LOGIN_API = "{}/api".format(BASE_API)
AGENT_API = "{}/agent-service".format(BASE_API)
DEFAULT_TIMEOUT = 20
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
PRIVATE_KEY_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{64})$")
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
    raw = env("HOLMESAI_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("HOLMESAI_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("HOLMESAI_TIMEOUT 须在 5 到 120 秒之间")
    return value


def normalize_private_key(text: str) -> str:
    match = PRIVATE_KEY_RE.fullmatch(text.strip())
    if not match:
        raise SafeError("私钥格式无效；须为可选 0x 前缀的 64 位十六进制")
    return match.group(1).lower()


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append({"private_key": normalize_private_key(text)})
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("HOLMESAI_PRIVATE_KEYS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("HOLMESAI_PRIVATE_KEYS 没有有效账号行")
        return accounts
    single = env("HOLMESAI_PRIVATE_KEY")
    if single:
        return [{"private_key": normalize_private_key(single)}]
    raise SafeError(
        "未配置 HOLMESAI_PRIVATE_KEYS；请按每个非空行一个 EVM 私钥填写"
    )


def import_eth_account():
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
        from eth_utils import to_hex
    except ImportError as exc:
        raise SafeError(
            "缺少依赖 eth-account；请在青龙环境安装：pip install eth-account"
        ) from exc
    return Account, encode_defunct, to_hex


def derive_address(private_key: str) -> str:
    Account, _, _ = import_eth_account()
    try:
        return Account.from_key(private_key).address
    except Exception as exc:
        raise SafeError("私钥无法派生钱包地址") from exc


def sign_login_message(private_key: str, message: str) -> Dict[str, str]:
    Account, encode_defunct, to_hex = import_eth_account()
    try:
        encoded = encode_defunct(text=message)
        signed = Account.sign_message(encoded, private_key=private_key)
        signature = to_hex(signed.signature)
    except Exception as exc:
        raise SafeError("本地签名失败") from exc
    return {
        "Action": "Web3LoginVerifySign",
        "Signature": signature,
        "Message": message,
    }


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("Message", "message", "msg", "error", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
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


class HolmesClient:
    def __init__(self, timeout: float, proxy: str = "") -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        handlers: List[Any] = [urllib.request.HTTPCookieProcessor(self.jar)]
        if proxy:
            handlers.append(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        else:
            handlers.append(urllib.request.ProxyHandler({}))
        self.opener = urllib.request.build_opener(*handlers)

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Host": "api.holmesai.xyz",
            "Origin": "https://www.holmesai.xyz",
            "Referer": "https://www.holmesai.xyz/",
            "User-Agent": UA,
            "Content-Type": "application/json",
        }

    def cookie_names(self) -> List[str]:
        return [cookie.name for cookie in self.jar]

    def request_json(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        allow_empty: bool = False,
    ) -> Tuple[int, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            url,
            data=body,
            headers=self._headers(),
            method="POST",
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
            if allow_empty:
                return status, None
            raise SafeError("响应为空")
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            if allow_empty:
                return status, None
            raise SafeError("响应不是合法 JSON") from exc


def do_get_message(client: HolmesClient, address: str) -> Tuple[str, str, Any]:
    status, result = client.request_json(
        LOGIN_API,
        {"Action": "Web3LoginGetMessage", "Address": address},
    )
    if status != 200:
        raise SafeError("获取登录消息失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录消息响应无法解析")
    message = result.get("Message")
    if not isinstance(message, str) or not message.strip():
        raise SafeError("登录消息字段缺失")
    if "yott_ai_session" not in client.cookie_names():
        raise SafeError("未获得登录会话 Cookie")
    return "success", "已获取待签名登录消息", {"message": message, "payload": result}


def do_verify_sign(
    client: HolmesClient, private_key: str, message: str
) -> Tuple[str, str, Any]:
    payload = sign_login_message(private_key, message)
    status, result = client.request_json(LOGIN_API, payload, allow_empty=True)
    if status not in (200, 204) and status >= 400:
        raise SafeError("签名登录失败（HTTP {}）".format(status))
    if "login_yott_ai" not in client.cookie_names():
        # 部分实现会刷新会话 Cookie；再检查是否已有登录态相关 Cookie
        names = client.cookie_names()
        if not any("login" in name.lower() or "yott" in name.lower() for name in names):
            raise SafeError("签名登录未建立会话")
    return "success", "Web3 签名登录成功", result


def do_get_user(
    client: HolmesClient, invite_code: str
) -> Tuple[str, str, Any]:
    payload: Dict[str, Any] = {"Action": "GetUser"}
    if invite_code:
        payload["InviteCode"] = invite_code
    status, result = client.request_json(AGENT_API, payload)
    if status != 200:
        raise SafeError("获取用户信息失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("用户信息响应无法解析")
    if result.get("RetCode") != 0:
        detail = business_message(result) or "业务码异常"
        raise SafeError("获取用户信息业务失败：{}".format(detail))
    points = result.get("Points")
    checkin_done = bool(result.get("CheckinDone"))
    detail = "用户信息已读取"
    if points is not None:
        detail = "用户信息已读取；积分 {}".format(compact(points, 32))
    if checkin_done:
        detail = "{}；今日已签到".format(detail)
    return "success", detail, result


def do_checkin(client: HolmesClient, address: str) -> Tuple[str, str, Any]:
    status, result = client.request_json(
        AGENT_API,
        {"Action": "CheckIn", "UserId": address},
    )
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("签到响应无法解析")
    if result.get("RetCode") == 0:
        return "success", "签到成功", result
    message = business_message(result).lower()
    already_hints = (
        "already",
        "already check",
        "already checked",
        "已签到",
        "已经签到",
        "今日已签",
        "重复签到",
    )
    if any(hint in message for hint in already_hints):
        return "alreadyComplete", "今日已签到，无需重复签到", result
    detail = business_message(result) or "业务码异常"
    raise SafeError("签到业务失败：{}".format(detail))


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
    invite_code: str,
    proxy: str,
) -> None:
    private_key = account["private_key"]

    def parameter_check():
        normalize_private_key(private_key)
        return "success", "私钥本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "派生地址", "断网预演：不加载签名库派生地址")
        runner.skip(3, "获取登录消息", "断网预演：不请求登录接口")
        runner.skip(4, "签名登录", "断网预演：不请求签名登录")
        runner.skip(5, "读取用户", "断网预演：不请求用户接口")
        runner.skip(6, "执行签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    def derive_stage():
        address = derive_address(private_key)
        runner.identity = address
        return "success", "公开钱包地址：{}".format(address), address

    address = runner.stage(2, "派生地址", derive_stage)
    client = HolmesClient(timeout, proxy)

    message_box: Dict[str, str] = {}

    def message_stage():
        state, detail, result = do_get_message(client, address)
        if isinstance(result, dict):
            message_box["message"] = str(result.get("message") or "")
        return state, detail, result

    runner.stage(3, "获取登录消息", message_stage)

    def login_stage():
        message = message_box.get("message") or ""
        if not message:
            raise SafeError("缺少待签名登录消息")
        return do_verify_sign(client, private_key, message)

    runner.stage(4, "签名登录", login_stage)

    user_box: Dict[str, Any] = {}

    def user_stage():
        state, detail, result = do_get_user(client, invite_code)
        user_box["payload"] = result
        return state, detail, result

    runner.stage(5, "读取用户", user_stage)

    checkin_state_box: Dict[str, str] = {"state": "failure"}

    def checkin_stage():
        payload = user_box.get("payload")
        if isinstance(payload, dict) and payload.get("CheckinDone"):
            checkin_state_box["state"] = "alreadyComplete"
            return "alreadyComplete", "今日已签到，无需重复签到", payload
        state, detail, result = do_checkin(client, address)
        checkin_state_box["state"] = state
        return state, detail, result

    runner.stage(6, "执行签到", checkin_stage)

    if runner.stats["failure"]:
        runner.status = "failure"
    elif checkin_state_box["state"] == "alreadyComplete":
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
        "holmesai_daily.py",
        "candidate.py",
        "scripts/holmesai_daily.py",
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
    dry_setting = env("HOLMESAI_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    invite_code = env("HOLMESAI_INVITE_CODE")
    proxy = env("HOLMESAI_PROXY")
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("HOLMESAI_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；邀请码：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                "已配置" if invite_code else "未配置（默认不提交）",
            )
        )
        if proxy:
            log("代理：已配置 HTTP(S) 代理（地址不输出）")
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, timeout, dry_run, invite_code, proxy)
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
