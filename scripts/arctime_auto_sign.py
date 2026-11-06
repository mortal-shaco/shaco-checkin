#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Arctime每日签到
# cron: 56 8 * * *
#
# 来源：TYHH1323/zdqd arctime_auto_sign.py（MIT）
# https://github.com/TYHH1323/zdqd
# 提交：196288112544bb4fcc969cbd186ec9cfcd0c4dfc
# 上游同源作者：雪山凌狐 / xueshanlinghu/arctime-auto-sign
# http://www.xueshanlinghu.com
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2020 雪山凌狐
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
"""Arctime（m.arctime.cn）账户每日签到 - 青龙维护版。

功能清点（相对上游 arctime_auto_sign.py）：
- 打开登录页获取会话 Cookie
- 使用用户名与密码 POST 登录（login_type=2），校验业务文案「登录成功」
- 访问个人中心读取积分摘要，识别「立即签到领取积分」或「今日已经签到」
- 待签到时 POST 签到接口并校验返回业务文案
- 移除 argv 明文传参、打印 Cookie、本地 log.log 落盘与无超时请求
- 增加换行多账号、ARCTIME_DRY_RUN 断网预演、超时、时间轴日志、青龙通知与 TASK_SUMMARY

ARCTIME_ACCOUNTS（必填）：每个非空行一个账号，格式 用户名|密码；仅按第一个 | 分割。
兼容单账号别名：ARCTIME_USERNAME + ARCTIME_PASSWORD（仅当规范变量为空）。
ARCTIME_TIMEOUT：单次 HTTP 请求超时秒数，默认 20，范围 5..60。
ARCTIME_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：30 8 * * *。不打印密码、Cookie、Token、手机号或原始响应。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('3c8ee1df1aee7324', 'scripts/arctime_auto_sign.py', 'arctime_auto_sign.py', 'arctime_auto_sign')
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

TITLE = "Arctime每日签到"
CATALOG_ID = "3c8ee1df1aee7324"
BASE = "http://m.arctime.cn"
INIT_LOGIN_URL = BASE + "/home/user/login.html"
LOGIN_URL = BASE + "/home/user/login_save.html"
UCENTER_URL = BASE + "/home/ucenter/index.html"
SIGN_URL = BASE + "/home/ucenter/attendance.html"
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
UA = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/65.0.3314.0 Safari/537.36 SE 2.X MetaSr 1.0"
)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
NICK_RE = re.compile(
    r"(?:昵称|用户名|欢迎您?|您好?|账号)[:：\s]*"
    r"([^\s<>\"']{1,64})",
    re.I,
)
POINTS_RE = re.compile(r"共获得\s*([0-9]+(?:\.[0-9]+)?)\s*积分")
SIGN_OK_HINTS = ("签到成功", "领取成功", "积分领取成功", "签到完成")
SIGN_ALREADY_HINTS = ("今日已经签到", "已经签到", "已签到", "重复签到")
LOGIN_OK = "登录成功"


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


def public_identity(username: str, page_identity: str = "") -> str:
    candidate = compact(page_identity, 64)
    if candidate and not PHONE_RE.fullmatch(candidate):
        return candidate
    raw = compact(username, 64)
    if not raw:
        return ""
    if PHONE_RE.fullmatch(raw):
        return ""
    return raw


def resolve_timeout() -> float:
    raw = env("ARCTIME_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("ARCTIME_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("ARCTIME_TIMEOUT 须在 5 到 60 秒之间")
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
    raw = env("ARCTIME_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("ARCTIME_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("ARCTIME_USERNAME")
    password = env("ARCTIME_PASSWORD")
    if username or password:
        if not username or not password:
            raise SafeError(
                "兼容别名需同时提供 ARCTIME_USERNAME 与 ARCTIME_PASSWORD；"
                "推荐改用 ARCTIME_ACCOUNTS（用户名|密码）"
            )
        return [{"username": username, "password": password}]
    raise SafeError(
        "未配置 ARCTIME_ACCOUNTS；请按每个非空行 用户名|密码 填写"
    )


def extract_mid(html: str, start_str: str, end_str: str) -> str:
    start = html.find(start_str)
    if start < 0:
        return ""
    start += len(start_str)
    end = html.find(end_str, start)
    if end < 0:
        return ""
    return html[start:end].strip()


def extract_points(html: str) -> str:
    match = POINTS_RE.search(html or "")
    if match:
        return match.group(1)
    return extract_mid(html or "", "共获得", "积分")


def extract_page_identity(html: str) -> str:
    match = NICK_RE.search(html or "")
    if not match:
        return ""
    return compact(match.group(1), 64)


def classify_sign_message(msg: str) -> Optional[str]:
    text = compact(msg, 120)
    if not text:
        return None
    if any(hint in text for hint in SIGN_ALREADY_HINTS):
        return "alreadyComplete"
    if any(hint in text for hint in SIGN_OK_HINTS):
        return "success"
    if "成功" in text and "失败" not in text and "错误" not in text:
        return "success"
    return None


class AccountRunner:
    def __init__(self, number: int, username: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = public_identity(username)

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


class ArctimeClient:
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
            "Host": "m.arctime.cn",
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


def do_init_session(client: ArctimeClient) -> Tuple[str, str, None]:
    status, _text = client.request(
        INIT_LOGIN_URL,
        "GET",
        headers={"Referer": UCENTER_URL, "Cache-Control": "max-age=0"},
    )
    if status != 200:
        raise SafeError("打开登录页失败（HTTP {}）".format(status))
    if not list(client.jar):
        raise SafeError("登录页未返回会话 Cookie")
    return "success", "已建立登录前会话（Cookie 不输出）", None


def do_login(
    client: ArctimeClient, username: str, password: str
) -> Tuple[str, str, Dict[str, Any]]:
    body = urllib.parse.urlencode(
        {
            "username": username,
            "password": password,
            "login_type": "2",
        }
    ).encode("utf-8")
    status, text = client.request(
        LOGIN_URL,
        "POST",
        body,
        {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": INIT_LOGIN_URL,
        },
    )
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise SafeError("登录响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise SafeError("登录响应结构异常")
    msg = compact(payload.get("msg"), 80)
    if msg != LOGIN_OK:
        raise SafeError("登录未确认业务成功")
    identity = public_identity(username)
    detail = "登录成功"
    if identity:
        detail += "；公开身份：{}".format(identity)
    return "success", detail, {"identity": identity}


def do_ucenter_and_sign(
    client: ArctimeClient, username: str
) -> Tuple[str, str, Dict[str, Any]]:
    status, html = client.request(
        UCENTER_URL,
        "GET",
        headers={"Referer": INIT_LOGIN_URL},
    )
    if status != 200:
        raise SafeError("访问个人中心失败（HTTP {}）".format(status))
    points = extract_points(html)
    page_identity = extract_page_identity(html)
    identity = public_identity(username, page_identity)
    if "立即签到领取积分" in html:
        status, text = client.request(
            SIGN_URL,
            "POST",
            b" ",
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": UCENTER_URL,
            },
        )
        if status != 200:
            raise SafeError("签到请求失败（HTTP {}）".format(status))
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise SafeError("签到响应不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise SafeError("签到响应结构异常")
        msg = compact(payload.get("msg"), 80)
        kind = classify_sign_message(msg)
        if kind is None:
            raise SafeError("签到未确认业务成功")
        detail_parts = []
        if kind == "alreadyComplete":
            detail_parts.append("今日已经签到")
        else:
            detail_parts.append("签到成功")
        if points:
            detail_parts.append("当前积分 {}".format(points))
        if identity:
            detail_parts.append("公开身份：{}".format(identity))
        return kind, "；".join(detail_parts), {
            "points": points,
            "identity": identity,
            "signState": kind,
        }
    if "今日已经签到" in html:
        detail_parts = ["今日已经签到"]
        if points:
            detail_parts.append("当前积分 {}".format(points))
        if identity:
            detail_parts.append("公开身份：{}".format(identity))
        return "alreadyComplete", "；".join(detail_parts), {
            "points": points,
            "identity": identity,
            "signState": "alreadyComplete",
        }
    raise SafeError("个人中心未识别到可签到或已签到状态")


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("用户名或密码为空")
        return "success", "账号本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "建立会话", "断网预演：不请求登录页")
        runner.skip(3, "登录", "断网预演：不请求登录接口")
        runner.skip(4, "个人中心与签到", "断网预演：不请求个人中心或签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = ArctimeClient(timeout)
    sign_state_box: Dict[str, str] = {"state": "failure"}

    runner.stage(2, "建立会话", lambda: do_init_session(client))

    def login_stage():
        state, detail, result = do_login(
            client, account["username"], account["password"]
        )
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
        return state, detail, result

    runner.stage(3, "登录", login_stage)

    def sign_stage():
        state, detail, result = do_ucenter_and_sign(client, account["username"])
        sign_state_box["state"] = state
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
        return state, detail, result

    runner.stage(4, "个人中心与签到", sign_stage)

    if runner.stats["failure"] or sign_state_box["state"] == "failure":
        runner.status = "failure"
    elif sign_state_box["state"] == "alreadyComplete":
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
        "arctime_auto_sign.py",
        "arctime_checkin.py",
        "candidate.py",
        "scripts/arctime_auto_sign.py",
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
    dry_setting = env("ARCTIME_DRY_RUN", "0").lower()
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
            raise SafeError("ARCTIME_DRY_RUN 配置无效，停止执行")
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
