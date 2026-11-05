#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 欧文 Soul-Mates 每日签到
# cron: 0 18 * * *
from __future__ import annotations
#
# 来源：yangsongh/OuwenAutoSignIn main.py（MIT）
# https://github.com/yangsongh/OuwenAutoSignIn
# 提交：874784ab7a298b7514a116c6cc95d9ab18c3e580
#
# MIT License
#
# Copyright (c) yangsongh / OuwenAutoSignIn contributors
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
"""欧文 Soul-Mates（pc.chatclient.soul-mates.ai）每日签到 - 青龙维护版。

功能清点（相对上游 main.py）：
- 账号密码登录（密码 MD5），获取会话 token 后调用 H5 签到接口
- 上游内置 APScheduler 长期驻留、每日 18:00 触发；青龙改由 cron 调度，已移除常驻调度器
- 上游命令行 --account/--password；本版改为环境变量多账号，并保留同名 CLI 兼容

OUWEN_ACCOUNTS：每个非空行一个账号，格式 账号|密码；仅在第一个竖线处分割，
密码中后续竖线保留。不要用 & 或 @ 分隔账号。浏览器或 App 注册的登录账号与明文密码。
OUWEN_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
OUWEN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 18:00（与上游调度一致）。不打印密码、Token 或原始响应。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('51cc62b8a3878ec3', 'scripts/ouwen.py', 'ouwen.py', 'ouwen')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import fnmatch
import hashlib
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

TITLE = "欧文 Soul-Mates 每日签到"
CATALOG_ID = "51cc62b8a3878ec3"
LOGIN_URL = "https://pc.chatclient.soul-mates.ai/user/login/login"
SIGN_URL = "https://pc.chatclient.soul-mates.ai/user/activity/signIn/h5"
DEFAULT_TIMEOUT = 15
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
ALREADY_MARKERS = ("已签到", "已经签到", "重复签到", "今日已签", "签到过")
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "username",
    "userName",
    "displayName",
    "name",
    "nick",
    "uid",
    "userId",
    "user_id",
    "id",
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(name: str) -> bool:
    return env(name, "0").lower() in TRUE_VALUES


def resolve_timeout() -> float:
    raw = env("OUWEN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("OUWEN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("OUWEN_TIMEOUT 须在 5 到 60 秒之间")
    return value


def md5_encode(text: str) -> str:
    digest = hashlib.md5()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def ms_timestamp() -> str:
    return str(int(time.time() * 1000))


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
            raise SafeError("账号行缺少分隔符；格式为 账号|密码")
        account, password = text.split("|", 1)
        account = account.strip()
        password = password.strip()
        if not account or not password:
            raise SafeError("账号或密码为空")
        if any(ord(ch) < 32 for ch in account) or any(ord(ch) < 32 for ch in password):
            raise SafeError("账号行含控制字符")
        accounts.append({"account": account, "password": password})
    return accounts


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    candidates: List[Any] = []
    if isinstance(data, dict):
        candidates.append(data)
        user = data.get("user") or data.get("userInfo") or data.get("profile")
        if isinstance(user, dict):
            candidates.append(user)
    candidates.append(payload)
    for mapping in candidates:
        if not isinstance(mapping, dict):
            continue
        for key in IDENTITY_KEYS:
            value = mapping.get(key)
            if isinstance(value, (str, int, float)):
                text = compact(value, 64)
                if text and key.lower() not in {"token", "password"}:
                    # 过滤疑似 token / 长凭据
                    if len(text) > 48 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                        continue
                    return text
    return ""


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("msg", "message", "errorMsg", "error_msg", "tip", "desc"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("msg", "message", "tip", "desc"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return compact(value)
    if isinstance(data, str):
        return compact(data)
    return ""


def classify_sign(payload: Any) -> Tuple[str, str]:
    if not isinstance(payload, dict):
        return "failure", "响应不是可解析的业务对象"
    message = business_message(payload)
    if any(marker in message for marker in ALREADY_MARKERS):
        return "alreadyComplete", "今日已签到（业务提示）"
    code = payload.get("code")
    if code == 1:
        reward = payload.get("data")
        detail = "签到成功（业务字段已核实）"
        if isinstance(reward, (int, float)) or (
            isinstance(reward, str) and reward.strip() and len(reward) < 32
        ):
            detail = "签到成功；奖励积分 {}".format(compact(reward, 32))
        return "success", detail
    if message:
        return "failure", "签到业务失败"
    return "failure", "签到业务失败（缺少可核实成功字段）"


class AccountRunner:
    def __init__(self, number: int, label: str) -> None:
        self.number = number
        self.label = label
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


def http_json(
    url: str,
    *,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[int, Any]:
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
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


def login_headers() -> Dict[str, str]:
    return {
        "accept": "application/json",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "platid": "7",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        "x-timestamp": ms_timestamp(),
    }


def sign_headers(token: str) -> Dict[str, str]:
    headers = login_headers()
    headers["accept"] = "*/*"
    headers.pop("content-type", None)
    headers["token"] = token
    headers["x-timestamp"] = ms_timestamp()
    return headers


def do_login(account: str, password: str, timeout: float) -> Tuple[str, str]:
    payload = {
        "type": 3,
        "ip": "",
        "clientType": 2,
        "channelCode": 7012,
        "platId": 7,
        "parentId": "0",
        "password": md5_encode(password),
        "account": account,
        "registerType": 2,
        "regDevice": "ZH_H5",
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    status, result = http_json(
        LOGIN_URL, method="POST", headers=login_headers(), body=body, timeout=timeout
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效或没有访问权限")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    code = result.get("code")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    token = data.get("token") if isinstance(data, dict) else None
    if code == 1 and isinstance(token, str) and token.strip():
        identity = extract_identity(result)
        return token.strip(), identity
    message = business_message(result)
    if any(word in message for word in ("密码", "账号", "用户", "凭证", "登录")):
        raise SafeError("登录业务失败（账号或密码可能无效）")
    raise SafeError("登录业务失败")


def do_sign(token: str, timeout: float) -> Tuple[str, str]:
    status, result = http_json(
        SIGN_URL, method="POST", headers=sign_headers(token), timeout=timeout
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    return classify_sign(result)


def run_account(
    runner: AccountRunner,
    account: str,
    password: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录获取会话", "断网预演：不请求登录接口")
        runner.skip(3, "公开身份", "断网预演：无官方身份返回")
        runner.skip(4, "提交每日签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    token_box: Dict[str, str] = {}

    def login_stage():
        token, identity = do_login(account, password, timeout)
        token_box["token"] = token
        if identity:
            runner.identity = identity
            return "success", "登录成功；公开身份：{}".format(identity), token
        return "success", "登录成功；官方未返回可展示身份，使用账号序号", token

    runner.stage(2, "登录获取会话", login_stage)

    def identity_stage():
        if runner.identity:
            return "success", "公开账号身份：{}".format(runner.identity), None
        return "success", "公开账号身份：账号{}".format(runner.number), None

    runner.stage(3, "公开身份", identity_stage)

    def sign_stage():
        state, detail = do_sign(token_box["token"], timeout)
        if state == "failure":
            raise SafeError(detail)
        return state, detail, None

    runner.stage(4, "提交每日签到", sign_stage)
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
        "ouwen_signin.py",
        "candidate.py",
        "scripts/ouwen_signin.py",
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


def load_accounts_from_env_and_cli() -> str:
    raw = env("OUWEN_ACCOUNTS")
    if raw:
        return raw
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--account", "-a", default="")
    parser.add_argument("--password", "-p", default="")
    args, _ = parser.parse_known_args()
    account = (args.account or "").strip()
    password = (args.password or "").strip()
    if account and password:
        return "{}|{}".format(account, password)
    return ""


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("OUWEN_DRY_RUN", "0").lower()
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
            raise SafeError("OUWEN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        raw_accounts = load_accounts_from_env_and_cli()
        if not raw_accounts:
            raise SafeError(
                "未配置 OUWEN_ACCOUNTS；请按每个非空行 账号|密码 填写（也可临时使用 --account/--password）"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("OUWEN_ACCOUNTS 没有有效账号行")
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
            runner = AccountRunner(number, "账号{}".format(number))
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["account"],
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
