#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 新南方职培学院签到
# cron: 13 8 * * *
#
# 来源：yuwucheni/xnfedu_checkin xnfedu_checkin.py（MIT）
# https://github.com/yuwucheni/xnfedu_checkin
# 提交：9ab8aeb30364ce8c2767ce55322d7f9c220d1841
#
# MIT License
#
# Copyright (c) yuwucheni / xnfedu_checkin contributors
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
"""新南方职业培训学院（jxedu.xnfedu.com）自动登录签到 - 青龙维护版。

功能清点（相对上游 xnfedu_checkin.py）：
- ASP.NET 登录页拉取隐藏字段并提交账号密码
- 从跳转 URL 提取 TOKEN，访问门户首页执行签到
- 识别「今日已经签到」为已完成成功
- 读取个人中心剩余/累计红豆数量
- 移除源码内硬编码账号与交互式 input() 阻塞
- 增加逐行多账号、XNFEDU_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

XNFEDU_ACCOUNTS：每个非空行一个账号，格式 用户名|密码；仅在第一个竖线处分割。
兼容单账号别名：同时设置 XNFEDU_USERNAME 与 XNFEDU_PASSWORD（仅当 XNFEDU_ACCOUNTS 为空）。
XNFEDU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
XNFEDU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：10 8 * * *。不打印密码、TOKEN、Cookie 或原始响应。
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
        _ql_notify_identities = ('9bc7812c7df257df', 'scripts/xnfedu_checkin.py', 'xnfedu_checkin.py', 'xnfedu_checkin')
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
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "新南方职培学院签到"
CATALOG_ID = "9bc7812c7df257df"
LOGIN_URL = "https://jxedu.xnfedu.com/Student/Login.aspx"
PERSONAL_URL = "https://jxedu.xnfedu.com/student/personal.aspx"
INDEX_URL = "https://jxedu.xnfedu.com/Portal/Index.aspx"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
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
    raw = env("XNFEDU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("XNFEDU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("XNFEDU_TIMEOUT 须在 5 到 60 秒之间")
    return value


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
    raw = env("XNFEDU_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("XNFEDU_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("XNFEDU_USERNAME")
    password = env("XNFEDU_PASSWORD")
    if username or password:
        if not username or not password:
            raise SafeError(
                "兼容别名需同时提供 XNFEDU_USERNAME 与 XNFEDU_PASSWORD；"
                "推荐改用 XNFEDU_ACCOUNTS（用户名|密码）"
            )
        return [{"username": username, "password": password}]
    raise SafeError(
        "未配置 XNFEDU_ACCOUNTS；请按每个非空行 用户名|密码 填写"
    )


def extract_value(text: str, field_name: str) -> str:
    pattern = r'name="{}"[^>]*value="([^"]*)"'.format(re.escape(field_name))
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match:
        return unescape(match.group(1))
    pattern_alt = r'value="([^"]*)"[^>]*name="{}"'.format(re.escape(field_name))
    match = re.search(pattern_alt, text, flags=re.IGNORECASE)
    return unescape(match.group(1)) if match else ""


def extract_display_name(html: str) -> str:
    patterns = (
        r'id="[^"]*lab姓名[^"]*"[^>]*>([^<]+)',
        r'id="[^"]*lab用户名[^"]*"[^>]*>([^<]+)',
        r'id="[^"]*lab昵称[^"]*"[^>]*>([^<]+)',
        r">姓名[：:]\s*([^<\s]+)",
        r">学员姓名[：:]\s*([^<\s]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue
        name = compact(unescape(match.group(1)), 64)
        if not name:
            continue
        if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", name):
            continue
        return name
    return ""


def extract_red_beans(html: str) -> Tuple[Optional[str], Optional[str]]:
    remain_match = re.search(
        r'id="WorkContent_WorkContent_lab剩余红豆[^"]*"[^>]*>(\d+)', html
    )
    total_match = re.search(
        r'id="WorkContent_WorkContent_lab累计红豆[^"]*"[^>]*>(\d+)', html
    )
    remain = remain_match.group(1) if remain_match else None
    total = total_match.group(1) if total_match else None
    return remain, total


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""
        self.remain_beans = ""
        self.total_beans = ""

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

    def finish(self) -> None:
        extra = ""
        if self.remain_beans or self.total_beans:
            parts = []
            if self.remain_beans:
                parts.append("剩余{}".format(self.remain_beans))
            if self.total_beans:
                parts.append("累计{}".format(self.total_beans))
            extra = "；红豆 {}".format(", ".join(parts))
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}{}".format(
                self.display(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
                extra,
            )
        )


class XnfeduClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        data: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
    ) -> Tuple[str, str, int]:
        body = None
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(
            url, data=body, headers=headers, method=method.upper()
        )
        try:
            if allow_redirects:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise SafeError("响应过大，已中止解析")
                    final_url = response.geturl()
                    status = getattr(response, "status", 200) or 200
                    text = raw.decode("utf-8", errors="replace")
                    return text, final_url, int(status)
            # Manual redirect handling is not needed for this site; keep path for symmetry.
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise SafeError("响应过大，已中止解析")
                return (
                    raw.decode("utf-8", errors="replace"),
                    response.geturl(),
                    int(getattr(response, "status", 200) or 200),
                )
        except urllib.error.HTTPError as exc:
            raise SafeError("HTTP {}".format(exc.code)) from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络错误：{}".format(compact(getattr(exc, "reason", exc)))) from exc
        except TimeoutError as exc:
            raise SafeError("请求超时") from exc

    def login(self, username: str, password: str) -> str:
        html, _, status = self.request("GET", LOGIN_URL)
        if status != 200:
            raise SafeError("无法访问登录页面（状态码 {}）".format(status))
        payload = {
            "__VIEWSTATE": extract_value(html, "__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": extract_value(html, "__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": extract_value(html, "__EVENTVALIDATION"),
            "ctl00$WorkContent$txtLoginAccount": username,
            "ctl00$WorkContent$txtPassword": password,
            "ctl00$WorkContent$LoginButton": "马上登录",
        }
        html, final_url, _ = self.request("POST", LOGIN_URL, data=payload)
        if "Login.aspx" in final_url and "TOKEN" not in final_url.upper():
            if "密码输入错误" in html:
                raise SafeError("登录失败：密码错误")
            raise SafeError("登录失败：未取得会话")
        token_match = re.search(r"TOKEN=([^&]+)", final_url, flags=re.IGNORECASE)
        if not token_match:
            # Some deployments may keep TOKEN only in subsequent links
            token_match = re.search(r"TOKEN=([^&\"']+)", html, flags=re.IGNORECASE)
        if not token_match:
            raise SafeError("登录失败：未找到 TOKEN")
        return urllib.parse.unquote(token_match.group(1))

    def get_red_beans(self, token: str) -> Tuple[Optional[str], Optional[str], str]:
        url = "{}?TOKEN={}".format(PERSONAL_URL, urllib.parse.quote(token, safe=""))
        html, _, status = self.request("GET", url)
        if status != 200:
            return None, None, ""
        remain, total = extract_red_beans(html)
        return remain, total, extract_display_name(html)

    def checkin(self, token: str) -> Tuple[str, str, Optional[str], Optional[str]]:
        """返回 outcome, message, remain, total。outcome: success|alreadyComplete|failure"""
        index_url = "{}?TOKEN={}".format(INDEX_URL, urllib.parse.quote(token, safe=""))
        html, _, status = self.request("GET", index_url)
        if status != 200:
            raise SafeError("无法访问首页（状态码 {}）".format(status))

        if "今日已经签到" in html:
            match = re.search(r"今日已经签到\+?(\d+)", html)
            points = match.group(1) if match else "?"
            remain, total, _ = self.get_red_beans(token)
            return (
                "alreadyComplete",
                "今日已签到过（+{}红豆）".format(points),
                remain,
                total,
            )

        if "lbtnSign" not in html and "qd.png" not in html:
            raise SafeError("未找到签到按钮")

        payload = {
            "__VIEWSTATE": extract_value(html, "__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": extract_value(html, "__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": extract_value(html, "__EVENTVALIDATION"),
            "__EVENTTARGET": "ctl00$lbtnSign",
            "__EVENTARGUMENT": "",
        }
        html, _, _ = self.request("POST", index_url, data=payload)

        if "签到成功" in html or "今日已经签到" in html:
            match = re.search(r"签到[^\+]*\+?(\d+)", html)
            if not match:
                match = re.search(r"今日已经签到\+?(\d+)", html)
            points = match.group(1) if match else "?"
            remain, total, _ = self.get_red_beans(token)
            outcome = "alreadyComplete" if "今日已经签到" in html and "签到成功" not in html else "success"
            # After a fresh POST, prefer success if 签到成功 present
            if "签到成功" in html:
                outcome = "success"
            return outcome, "签到成功（+{}红豆）".format(points), remain, total

        if "MyAlert" in html:
            alert = re.search(r"MyAlert\([^)]*?'([^']+)'", html)
            if alert:
                message = compact(alert.group(1))
                if "今日已经签到" in message or "已签到" in message:
                    remain, total, _ = self.get_red_beans(token)
                    return "alreadyComplete", message, remain, total
                raise SafeError("签到提示：{}".format(message))

        html, _, _ = self.request("GET", index_url)
        if "今日已经签到" in html:
            match = re.search(r"今日已经签到\+?(\d+)", html)
            points = match.group(1) if match else "?"
            remain, total, _ = self.get_red_beans(token)
            return (
                "success",
                "签到成功（+{}红豆）".format(points),
                remain,
                total,
            )
        raise SafeError("签到状态未知")


def run_account(
    runner: AccountRunner,
    username: str,
    password: str,
    timeout: float,
    dry_run: bool,
) -> None:
    if dry_run:
        runner.stage(
            1,
            "校验账号格式",
            lambda: (
                "success",
                "用户名与密码格式已校验（未发送）",
                None,
            ),
        )
        runner.identity = "预演账号{}".format(runner.number)
        runner.stage(
            2,
            "登录",
            lambda: ("skipped", "断网预演：跳过登录", None),
        )
        runner.stage(
            3,
            "签到",
            lambda: ("skipped", "断网预演：跳过签到与红豆查询", None),
        )
        runner.status = "dry-run"
        return

    client = XnfeduClient(timeout)

    def do_login():
        token = client.login(username, password)
        remain, total, display = client.get_red_beans(token)
        if display:
            runner.identity = display
        if remain:
            runner.remain_beans = remain
        if total:
            runner.total_beans = total
        detail = "登录成功"
        if runner.identity:
            detail = "登录成功，身份：{}".format(runner.identity)
        return "success", detail, token

    token = runner.stage(1, "登录", do_login)

    def do_checkin():
        outcome, message, remain, total = client.checkin(token)
        if remain:
            runner.remain_beans = remain
        if total:
            runner.total_beans = total
        return outcome, message, None

    runner.stage(2, "签到", do_checkin)
    if runner.stats["failure"]:
        runner.status = "failure"
    elif runner.stats["alreadyComplete"]:
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
        "xnfedu_checkin.py",
        "candidate.py",
        "scripts/xnfedu_checkin.py",
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
    dry_setting = env("XNFEDU_DRY_RUN", "0").lower()
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
            raise SafeError("XNFEDU_DRY_RUN 配置无效，停止执行")
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
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["username"],
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
