#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: FZQOJ每日签到
# cron: 53 8 * * *
#
# 来源：LYXOfficial/FZQOJAutoSign index.py（MIT）
# https://github.com/LYXOfficial/FZQOJAutoSign
# 提交：86fe66cda51e174c879f935fd7db54d7503e1bf3
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2023 Ariasaka
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
"""FZQOJ（qoj.fzoi.top）登录签到 - 青龙维护版。

功能清点（相对上游 index.py）：
- 读取登录页 CSRF _token 后 POST /login（用户名 + Token），校验 ok / 账号或密码错误 / banned
- GET /punch 执行每日签到；HTTP 200 为当日首次签到，HTTP 403 为今日已签到
- 读取首页连续签到天数、今日 RP 与硬币摘要
- 移除硬编码 CSRF、本地 data.conf、无超时请求与 requests/pyquery 依赖
- 增加逐行多账号、FZQOJ_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

FZQOJ_ACCOUNTS：每个非空行一个账号，格式 用户名|Token；仅在第一个竖线处分割。
兼容上游空格写法：无竖线时在首个空白处分割为 用户名 Token。
Token 来自 FZQOJ「更改个人信息」页面显示的 Token，不是登录密码明文。
兼容单账号别名：同时设置 FZQOJ_USER 与 FZQOJ_TOKEN（仅当 FZQOJ_ACCOUNTS 为空）。
FZQOJ_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
FZQOJ_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：30 8 * * *。不打印 Token、Cookie 或原始响应；OJ 用户名作为公开身份直接展示。
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
            "ed4d6d4d632e033e",
            "scripts/fzqoj_checkin.py",
            "fzqoj_checkin.py",
            "fzqoj_checkin",
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

TITLE = "FZQOJ每日签到"
CATALOG_ID = "ed4d6d4d632e033e"
BASE = "https://qoj.fzoi.top"
LOGIN_PAGE_URL = "{}/login".format(BASE)
LOGIN_POST_URL = "{}/login".format(BASE)
PUNCH_URL = "{}/punch".format(BASE)
HOME_URL = "{}/".format(BASE)
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
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82"
)
STREAK_RE = re.compile(
    r"你已经连续签到\s*(\d+)\s*天，今日获得\s*(\d+)\s*RP值(?:和\s*1\s*硬币)?"
)
TOKEN_RE = re.compile(
    r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']'
    r'|value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']'
    r'|name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']'
    r'|content=["\']([^"\']+)["\'][^>]*name=["\']csrf-token["\']',
    re.I,
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
    raw = env("FZQOJ_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("FZQOJ_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("FZQOJ_TIMEOUT 须在 5 到 60 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" in text:
        username, token = text.split("|", 1)
    else:
        parts = text.split(None, 1)
        if len(parts) != 2:
            raise SafeError("账号行缺少分隔符；格式为 用户名|Token")
        username, token = parts
    username = username.strip()
    token = token.strip()
    if not username or not token:
        raise SafeError("用户名或 Token 为空")
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in token):
        raise SafeError("账号行含控制字符")
    return {"username": username, "token": token}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("FZQOJ_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("FZQOJ_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("FZQOJ_USER")
    token = env("FZQOJ_TOKEN")
    if username or token:
        if not username or not token:
            raise SafeError(
                "兼容别名需同时提供 FZQOJ_USER 与 FZQOJ_TOKEN；"
                "推荐改用 FZQOJ_ACCOUNTS（用户名|Token）"
            )
        return [{"username": username, "token": token}]
    raise SafeError(
        "未配置 FZQOJ_ACCOUNTS；请按每个非空行 用户名|Token 填写"
    )


def extract_csrf(html: str) -> str:
    match = TOKEN_RE.search(html or "")
    if not match:
        raise SafeError("登录页未找到 CSRF _token")
    token = next((group for group in match.groups() if group), "")
    token = token.strip()
    if not token or len(token) < 8:
        raise SafeError("登录页 CSRF _token 无效")
    return token


def parse_streak(html: str) -> Optional[Tuple[int, int]]:
    match = STREAK_RE.search(html or "")
    if not match:
        return None
    try:
        return int(match.group(1)), int(match.group(2))
    except (TypeError, ValueError):
        return None


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


class FzqojClient:
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
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


def do_login(
    client: FzqojClient, username: str, token: str
) -> Tuple[str, str, Dict[str, Any]]:
    status, page = client.request(
        LOGIN_PAGE_URL,
        "GET",
        headers={"Referer": BASE + "/"},
    )
    if status != 200:
        raise SafeError("打开登录页失败（HTTP {}）".format(status))
    csrf = extract_csrf(page)
    body = urllib.parse.urlencode(
        {
            "_token": csrf,
            "username": username,
            "password": token,
            "login": "",
            "ip": "",
        }
    ).encode("utf-8")
    status, text = client.request(
        LOGIN_POST_URL,
        "POST",
        body,
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE,
            "Referer": LOGIN_PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    payload = compact(text, 64)
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if payload == "账号或密码错误":
        raise SafeError("登录凭据无效：用户名或 Token 错误")
    if payload.lower() == "banned":
        raise SafeError("账号已被封禁")
    if payload != "ok":
        raise SafeError("登录未确认业务成功")
    if not list(client.jar):
        raise SafeError("登录未获得有效会话 Cookie")
    detail = "登录成功；公开身份：{}".format(compact(username, 64))
    return "success", detail, {"identity": compact(username, 64)}


def do_punch(client: FzqojClient) -> Tuple[str, str, Dict[str, Any]]:
    status, _text = client.request(
        PUNCH_URL,
        "GET",
        headers={"Referer": HOME_URL},
    )
    if status == 200:
        return "success", "签到成功", {"httpStatus": status}
    if status == 403:
        return "alreadyComplete", "今日已签到", {"httpStatus": status}
    if status in (401, 302):
        raise SafeError("签到凭据无效或会话已过期")
    raise SafeError("签到请求失败（HTTP {}）".format(status))


def do_home_summary(client: FzqojClient) -> Tuple[str, str, Dict[str, Any]]:
    status, html = client.request(
        HOME_URL,
        "GET",
        headers={"Referer": PUNCH_URL},
    )
    if status in (401, 403):
        raise SafeError("读取签到摘要凭据无效或会话已过期")
    if status != 200:
        raise SafeError("读取签到摘要失败（HTTP {}）".format(status))
    streak = parse_streak(html)
    if streak is None:
        return "skipped", "首页未解析到连续签到摘要", None
    days, rp = streak
    detail = "连续签到 {} 天；今日获得 {} RP 与 1 硬币".format(days, rp)
    return "success", detail, {"days": days, "rp": rp}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["token"]:
            raise SafeError("用户名或 Token 为空")
        return "success", "账号本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录", "断网预演：不请求登录接口")
        runner.skip(3, "执行签到", "断网预演：不请求签到接口")
        runner.skip(4, "读取签到摘要", "断网预演：不请求首页摘要")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = FzqojClient(timeout)
    punch_state_box: Dict[str, str] = {"state": "failure"}

    def login_stage():
        state, detail, result = do_login(
            client, account["username"], account["token"]
        )
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
        return state, detail, result

    runner.stage(2, "登录", login_stage)

    def punch_stage():
        state, detail, result = do_punch(client)
        punch_state_box["state"] = state
        return state, detail, result

    runner.stage(3, "执行签到", punch_stage)

    def summary_stage():
        try:
            return do_home_summary(client)
        except SafeError as error:
            message = str(error)
            if "凭据无效" in message or "会话已过期" in message:
                raise
            return "skipped", "签到摘要不可用：{}".format(message), None

    runner.stage(4, "读取签到摘要", summary_stage)

    if runner.stats["failure"] or punch_state_box["state"] == "failure":
        runner.status = "failure"
    elif punch_state_box["state"] == "alreadyComplete":
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
        "fzqoj_checkin.py",
        "candidate.py",
        "scripts/fzqoj_checkin.py",
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
    dry_setting = env("FZQOJ_DRY_RUN", "0").lower()
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
            raise SafeError("FZQOJ_DRY_RUN 配置无效，停止执行")
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
            runner = AccountRunner(number, account["username"])
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
