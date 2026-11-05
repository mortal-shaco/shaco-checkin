#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: PHPWind论坛每日任务
# cron: 58 8 * * *
#
# 来源：cmt2001/forum_auto_sign day.py（MIT）
# https://github.com/cmt2001/forum_auto_sign
# 提交：f8ce2f473718803d382e9db610da11797552ad14
# 原路径：day.py
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2018 cmt2001
# Copyright (c) contributors of cmt2001/forum_auto_sign
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the Software), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""PHPWind 风格论坛每日任务领取 - 青龙维护版。

功能清点（相对上游 day.py）：
- 使用用户名与密码登录 PHPWind 论坛（login.php，成功标志「您已经顺利登录」）
- 申请每日任务：plugin.php?H_name=tasks&action=ajax&actions=job&cid=<cid>
- 领取每日任务奖励：actions=job2；响应含「完成」视为业务成功
- 移除 config.py 硬依赖、Python2 语法、无超时请求、默认 SSL 校验关闭、启动固定 sleep(10)
- 论坛地址改为环境变量配置（上游为 xxx.net 占位域名）
- 换行多账号、FORUM_AUTO_SIGN_DRY_RUN 断网预演、时间轴日志、青龙通知、TASK_SUMMARY

FORUM_AUTO_SIGN_ACCOUNTS：每个非空行一个账号，格式 用户名|密码；仅在第一个竖线处分割。
FORUM_AUTO_SIGN_BASE_URL：论坛主站根地址，如 https://www.example.net（勿带结尾路径）。
FORUM_AUTO_SIGN_JUMP_URL：可选登录 jumpurl，默认 {BASE}/index.php?
FORUM_AUTO_SIGN_TASK_CID：任务 cid，默认 15（与上游一致）。
FORUM_AUTO_SIGN_TIMEOUT：单次 HTTPS 超时秒数，默认 20，范围 5..90。
FORUM_AUTO_SIGN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：20 8 * * *。不打印密码、Cookie、Token 或原始响应；登录用户名作为公开身份展示。
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
            "44fd1f3761334ce8",
            "scripts/forum_auto_sign_day.py",
            "forum_auto_sign_day.py",
            "forum_auto_sign_day",
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
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

TITLE = "PHPWind论坛每日任务"
CATALOG_ID = "44fd1f3761334ce8"
DEFAULT_TIMEOUT = 20
DEFAULT_TASK_CID = "15"
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
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)
LOGIN_OK_MARKERS = ("您已经顺利登录",)
TASK_OK_MARKERS = ("完成",)
TASK_ALREADY_MARKERS = ("已经完成", "已完成", "已经领取", "已领取", "重复申请")


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
    raw = env("FORUM_AUTO_SIGN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("FORUM_AUTO_SIGN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 90:
        raise SafeError("FORUM_AUTO_SIGN_TIMEOUT 须在 5 到 90 秒之间")
    return value


def normalize_base_url(raw: str) -> str:
    text = (raw or "").strip().rstrip("/")
    if not text:
        raise SafeError("FORUM_AUTO_SIGN_BASE_URL 不能为空")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SafeError(
            "FORUM_AUTO_SIGN_BASE_URL 须为 http(s)://host 形式的论坛主站地址"
        )
    host = parsed.netloc.lower()
    if host in {"www.xxx.net", "xxx.net", "bbs.xxx.net"} or "xxx.net" in host:
        raise SafeError(
            "FORUM_AUTO_SIGN_BASE_URL 仍为上游占位域名，请改为真实论坛主站地址"
        )
    return "{}://{}".format(parsed.scheme, parsed.netloc)


def resolve_task_cid() -> str:
    raw = env("FORUM_AUTO_SIGN_TASK_CID", DEFAULT_TASK_CID) or DEFAULT_TASK_CID
    if not raw.isdigit() or int(raw) <= 0:
        raise SafeError("FORUM_AUTO_SIGN_TASK_CID 须为正整数")
    return raw


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
    raw = env("FORUM_AUTO_SIGN_ACCOUNTS")
    if not raw:
        raise SafeError(
            "未配置 FORUM_AUTO_SIGN_ACCOUNTS；请按每个非空行 用户名|密码 填写"
        )
    accounts = parse_accounts(raw)
    if not accounts:
        raise SafeError("FORUM_AUTO_SIGN_ACCOUNTS 没有有效账号行")
    return accounts


def build_urls(base: str, cid: str) -> Dict[str, str]:
    root = base.rstrip("/") + "/"
    jump = env("FORUM_AUTO_SIGN_JUMP_URL")
    if not jump:
        jump = urljoin(root, "index.php?")
    task_get = urljoin(
        root,
        "plugin.php?H_name=tasks&action=ajax&actions=job&cid={}".format(cid),
    )
    task_claim = urljoin(
        root,
        "plugin.php?H_name=tasks&action=ajax&actions=job2&cid={}".format(cid),
    )
    return {
        "home": root,
        "login_get": urljoin(root, "login.php?"),
        "login_post": urljoin(root, "login.php"),
        "jump": jump,
        "task_get": task_get,
        "task_claim": task_claim,
    }


def classify_task_response(text: str) -> Tuple[str, str]:
    body = text or ""
    if any(marker in body for marker in TASK_ALREADY_MARKERS):
        return "alreadyComplete", "任务已完成或奖励已领取"
    if any(marker in body for marker in TASK_OK_MARKERS):
        return "success", "任务接口返回完成"
    return "failure", "任务接口未确认完成"


class AccountRunner:
    def __init__(self, number: int, username: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = compact(username, 64)

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


class ForumClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        base_headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        if headers:
            base_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=data,
            headers=base_headers,
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
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise SafeError("响应解码失败") from exc
        return status, text

    def clear(self) -> None:
        self.jar.clear()


def do_login(
    client: ForumClient,
    urls: Dict[str, str],
    username: str,
    password: str,
) -> Tuple[str, str, Dict[str, Any]]:
    status, _ = client.request(urls["home"], "GET")
    if status >= 500:
        raise SafeError("打开主站失败（HTTP {}）".format(status))
    status, _ = client.request(
        urls["login_get"],
        "GET",
        headers={"Referer": urls["home"]},
    )
    if status >= 500:
        raise SafeError("打开登录页失败（HTTP {}）".format(status))
    body = urllib.parse.urlencode(
        {
            "jumpurl": urls["jump"],
            "step": "2",
            "cktime": "31536000",
            "lgt": "0",
            "pwuser": username,
            "pwpwd": password,
        }
    ).encode("utf-8")
    status, text = client.request(
        urls["login_post"],
        "POST",
        body,
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": urls["home"].rstrip("/"),
            "Referer": urls["login_get"],
        },
    )
    if status >= 400 and status not in (401, 403):
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not any(marker in (text or "") for marker in LOGIN_OK_MARKERS):
        raise SafeError("登录未确认业务成功")
    if not list(client.jar):
        raise SafeError("登录未获得有效会话 Cookie")
    identity = compact(username, 64)
    detail = "登录成功；公开身份：{}".format(identity)
    return "success", detail, {"identity": identity}


def do_task_get(client: ForumClient, urls: Dict[str, str]) -> Tuple[str, str, Any]:
    status, text = client.request(
        urls["task_get"],
        "GET",
        headers={"Referer": urls["home"]},
    )
    if status in (401, 403):
        raise SafeError("申请任务凭据无效或会话已过期")
    if status >= 400:
        raise SafeError("申请任务失败（HTTP {}）".format(status))
    state, detail = classify_task_response(text)
    if state == "failure":
        raise SafeError("申请每日任务未确认完成")
    return state, detail, None


def do_task_claim(client: ForumClient, urls: Dict[str, str]) -> Tuple[str, str, Any]:
    status, text = client.request(
        urls["task_claim"],
        "GET",
        headers={"Referer": urls["home"]},
    )
    if status in (401, 403):
        raise SafeError("领取奖励凭据无效或会话已过期")
    if status >= 400:
        raise SafeError("领取奖励失败（HTTP {}）".format(status))
    state, detail = classify_task_response(text)
    if state == "failure":
        raise SafeError("领取每日任务奖励未确认完成")
    return state, detail, None


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    urls: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("用户名或密码为空")
        return "success", "账号本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录", "断网预演：不请求登录接口")
        runner.skip(3, "申请每日任务", "断网预演：不请求任务申请接口")
        runner.skip(4, "领取任务奖励", "断网预演：不请求奖励领取接口")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = ForumClient(timeout)
    claim_state_box: Dict[str, str] = {"state": "failure"}

    def login_stage():
        state, detail, result = do_login(
            client, urls, account["username"], account["password"]
        )
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
        return state, detail, result

    runner.stage(2, "登录", login_stage)

    def get_stage():
        return do_task_get(client, urls)

    runner.stage(3, "申请每日任务", get_stage)

    def claim_stage():
        state, detail, result = do_task_claim(client, urls)
        claim_state_box["state"] = state
        return state, detail, result

    runner.stage(4, "领取任务奖励", claim_stage)

    try:
        client.clear()
    except Exception:
        pass

    if runner.stats["failure"] or claim_state_box["state"] == "failure":
        runner.status = "failure"
    elif claim_state_box["state"] == "alreadyComplete":
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
        "forum_auto_sign_day.py",
        "candidate.py",
        "scripts/forum_auto_sign_day.py",
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
        log("通知：⏭️ 断网预演仅生成脱敏摘要，不投递外部通知")
        log("通知摘要：" + body)
        return "dry-run-skipped"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": False,
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
                log("通知：✅ 脱敏总结已交给青龙适配器")
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用或投递失败；保留业务退出码")
    return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("FORUM_AUTO_SIGN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    urls: Dict[str, str] = {}
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
            raise SafeError("FORUM_AUTO_SIGN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        base = normalize_base_url(env("FORUM_AUTO_SIGN_BASE_URL"))
        cid = resolve_task_cid()
        urls = build_urls(base, cid)
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；任务 cid：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                cid,
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
        log("论坛主站：{}".format(base))
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number, account["username"])
            accounts.append(runner)
            try:
                run_account(runner, account, urls, timeout, dry_run)
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
        final_label = "配置错误"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
        final_label = "部分失败"
    elif failed:
        status = "failure"
        final_label = "失败"
    elif dry_run:
        status = "dry-run"
        final_label = "预演完成"
    else:
        status = "success"
        final_label = "成功"
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
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
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
