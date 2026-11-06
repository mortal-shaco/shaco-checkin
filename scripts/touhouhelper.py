#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 东方 Portal 每日签到
# cron: 50 8 * * *
#
# 来源：DeSireFire/thProxyHelper touhouHelper.py（GPL-3.0）
# https://github.com/DeSireFire/thProxyHelper
# 提交：b62af275659cd1be21ba53d90b68338f75eeb50e
#
# SPDX-License-Identifier: GPL-3.0
#
# Copyright (C) 2022 RaXianch / DeSireFire
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Author    : RaXianch
# CreatDATE : 2022/2/17
# Blog      : https://blog.raxianch.moe/
# Github    : https://github.com/DeSireFire
"""东方 Portal（portal.touhou.tel）登录签到 - 青龙维护版。

功能清点（相对上游 touhouHelper.py）：
- POST /auth/login：邮箱与密码 JSON 登录，保留会话 Cookie（字段 email/passwd/code/remember_me）
- POST /user/checkin：每日签到，按官方 ret/msg 判定成功或今日已签到
- GET /user/logout：退出登录会话
- 移除私有 config 导入、硬编码凭据路径、无业务成功判定的“签到完成”假阳性
- 标准库 urllib 实现 HTTP；去掉 requests/chardet 外部依赖
- 增加逐行多账号、TOUHOU_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

TOUHOU_ACCOUNTS：每个非空行一个账号，格式 邮箱|密码；仅在第一个竖线处分割。
兼容单账号别名：同时设置 TOUHOU_EMAIL 与 TOUHOU_PASSWD（仅当 TOUHOU_ACCOUNTS 为空）。
TOUHOU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..90。
TOUHOU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：10 8 * * *。不打印密码、Cookie、Token、邮箱或原始响应。
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
        _ql_notify_identities = ('7a1ca78b42cf5fd4', 'scripts/touhouhelper.py', 'touhouhelper.py', 'touhouhelper')
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

TITLE = "东方 Portal 每日签到"
CATALOG_ID = "7a1ca78b42cf5fd4"
BASE_URL = "https://portal.touhou.tel"
LOGIN_URL = BASE_URL + "/auth/login"
CHECKIN_URL = BASE_URL + "/user/checkin"
LOGOUT_URL = BASE_URL + "/user/logout"
DEFAULT_TIMEOUT = 15
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
ALREADY_WORDS = (
    "已经签到",
    "已签到",
    "签到过",
    "重复签到",
    "already checked",
    "already check",
    "already signed",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/98.0.4758.82 Safari/537.36"
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
    raw = env("TOUHOU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("TOUHOU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 90:
        raise SafeError("TOUHOU_TIMEOUT 须在 5 到 90 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 邮箱|密码")
    email, password = text.split("|", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        raise SafeError("邮箱或密码为空")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise SafeError("邮箱格式无效")
    if any(ord(ch) < 32 for ch in email) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    return {"email": email, "password": password}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("TOUHOU_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("TOUHOU_ACCOUNTS 没有有效账号行")
        return accounts
    email = env("TOUHOU_EMAIL")
    password = env("TOUHOU_PASSWD")
    if email or password:
        if not email or not password:
            raise SafeError(
                "兼容别名需同时提供 TOUHOU_EMAIL 与 TOUHOU_PASSWD；"
                "推荐改用 TOUHOU_ACCOUNTS（邮箱|密码）"
            )
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise SafeError("TOUHOU_EMAIL 邮箱格式无效")
        return [{"email": email, "password": password}]
    raise SafeError("未配置 TOUHOU_ACCOUNTS；请按每个非空行 邮箱|密码 填写")


def public_identity_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in (
        "nickname",
        "name",
        "username",
        "user_name",
        "display_name",
        "displayName",
        "public_uid",
        "uid",
    ):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, int)):
            text = compact(value, 64)
            if not text:
                continue
            # 邮箱、手机号、过短纯数字会话类字段不当作公开身份展示
            if "@" in text:
                continue
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                continue
            if key in ("uid", "public_uid") and re.fullmatch(r"\d{1,4}", text):
                continue
            return text
    for nest in ("data", "user", "profile", "account", "result"):
        nested = payload.get(nest)
        if isinstance(nested, dict):
            found = public_identity_from_payload(nested)
            if found:
                return found
    return ""


def safe_business_message(payload: Dict[str, Any]) -> str:
    for key in ("msg", "message", "info"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value, 120)
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


class TouhouClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def base_headers(self, method: str = "GET") -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "authority": "portal.touhou.tel",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/user",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
    ) -> Tuple[int, bytes]:
        headers = self.base_headers(method)
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
    client: TouhouClient, email: str, password: str
) -> Tuple[str, str, Dict[str, Any]]:
    body = json.dumps(
        {
            "email": email,
            "passwd": password,
            "code": "",
            "remember_me": "hour",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    status, raw = client.request(LOGIN_URL, "POST", body)
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict):
        raise SafeError("登录响应结构不符合预期")
    if payload.get("ret") != 1:
        raise SafeError("登录失败：凭据或服务状态异常")
    cookies = {cookie.name: cookie.value for cookie in client.jar}
    if not cookies:
        raise SafeError("登录未获得有效会话 Cookie")
    identity = public_identity_from_payload(payload)
    detail = "登录成功"
    if identity:
        detail = "登录成功；公开身份：{}".format(identity)
    return "success", detail, {"identity": identity, "payload": payload}


def do_checkin(client: TouhouClient) -> Tuple[str, str, Dict[str, Any]]:
    status, raw = client.request(CHECKIN_URL, "POST", b"")
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict):
        raise SafeError("签到响应结构不符合预期")
    message = safe_business_message(payload)
    lowered = message.lower()
    if payload.get("ret") == 1:
        if any(word in lowered for word in ALREADY_WORDS) or any(
            word in message for word in ALREADY_WORDS
        ):
            return "alreadyComplete", "今日已签到", {"already": True, "payload": payload}
        detail = "签到成功"
        if message:
            detail = "签到成功：{}".format(message)
        identity = public_identity_from_payload(payload)
        if identity:
            detail = "{}；公开身份：{}".format(detail, identity)
        return "success", detail, {"already": False, "identity": identity, "payload": payload}
    if any(word in lowered for word in ALREADY_WORDS) or any(
        word in message for word in ALREADY_WORDS
    ):
        return "alreadyComplete", "今日已签到", {"already": True, "payload": payload}
    raise SafeError("签到失败：未获得官方成功或已签到证明")


def do_logout(client: TouhouClient) -> Tuple[str, str, Dict[str, Any]]:
    status, raw = client.request(LOGOUT_URL, "GET")
    if status in (401, 403):
        # 会话已失效时退出可视为完成
        return "alreadyComplete", "会话已失效，视为已退出", {}
    if status not in (200, 302):
        # 部分面板 logout 返回 HTML 页面；只要非鉴权错误即接受
        if status >= 400:
            raise SafeError("退出登录失败（HTTP {}）".format(status))
    # 有的面板返回 HTML 而非 JSON；上游亦不强制解析
    if raw and raw.lstrip().startswith(b"{"):
        try:
            payload = load_json(raw)
        except SafeError:
            payload = {}
        if isinstance(payload, dict) and "ret" in payload and payload.get("ret") != 1:
            msg = safe_business_message(payload) or "业务状态异常"
            raise SafeError("退出登录失败：{}".format(msg))
    return "success", "已退出登录", {}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    stage_no = 1

    def parameter_check():
        if not account["email"] or not account["password"]:
            raise SafeError("邮箱或密码为空")
        return "success", "账号密码本地格式检查通过，内容不输出", None

    runner.stage(stage_no, "参数检查", parameter_check)
    stage_no += 1

    if dry_run:
        runner.skip(stage_no, "登录", "断网预演：不请求登录接口")
        stage_no += 1
        runner.skip(stage_no, "每日签到", "断网预演：不请求签到接口")
        stage_no += 1
        runner.skip(stage_no, "退出登录", "断网预演：不请求退出接口")
        stage_no += 1
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = TouhouClient(timeout)

    def login_stage():
        state, detail, result = do_login(
            client, account["email"], account["password"]
        )
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        return state, detail, result

    runner.stage(stage_no, "登录", login_stage)
    stage_no += 1

    checkin_box: Dict[str, str] = {"state": "failure"}

    def checkin_stage():
        state, detail, result = do_checkin(client)
        checkin_box["state"] = state
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity and not runner.identity:
                runner.identity = identity
        return state, detail, result

    try:
        runner.stage(stage_no, "每日签到", checkin_stage)
    except SafeError:
        checkin_box["state"] = "failure"
    stage_no += 1

    logout_box: Dict[str, str] = {"state": "failure"}

    def logout_stage():
        state, detail, result = do_logout(client)
        logout_box["state"] = state
        return state, detail, result

    try:
        runner.stage(stage_no, "退出登录", logout_stage)
    except SafeError:
        logout_box["state"] = "failure"
        # 签到已成功时，退出失败不覆盖签到结果，但账号记为失败以提示会话清理异常
    stage_no += 1

    if checkin_box["state"] == "failure" or logout_box["state"] == "failure":
        runner.status = "failure"
    elif checkin_box["state"] == "alreadyComplete":
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
        "touhou_portal_checkin.py",
        "candidate.py",
        "scripts/touhou_portal_checkin.py",
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
    dry_setting = env("TOUHOU_DRY_RUN", "0").lower()
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
            raise SafeError("TOUHOU_DRY_RUN 配置无效，停止执行")
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
