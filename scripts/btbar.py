#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: BT吧签到
# cron: 46 8 * * *
#
# 来源：hepsontam/BTBar_Checkin BTBar.py（GPL-3.0）
# https://github.com/hepsontam/BTBar_Checkin
# 提交：182c8750ed5ea15e075d3b8a37d34bc9a33bbb8e
#
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) hepsontam / BTBar_Checkin contributors
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
"""BT吧（u.aibtba.com）登录签到 - 青龙维护版。

功能清点（相对上游 BTBar.py）：
- POST /user/login 使用手机号/邮箱与密码登录，读取会话 Cookie
- GET /sign 提交每日签到；当日首次获得 BT 币，重复签到获得 0 BT 币
- GET /sign/select 读取连续签到天数与日历摘要
- 登录 Cookie 中的 bt_nickname / bt_user_id 作为公开身份直接展示
- 移除脚本内硬编码凭据、打印完整 Cookie、禁用 SSL 校验与无超时请求
- 增加逐行多账号、BTBAR_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

BTBAR_ACCOUNTS：每个非空行一个账号，格式 手机号或邮箱|密码；仅在第一个竖线处分割。
兼容单账号别名：同时设置 BTBAR_USER 与 BTBAR_PASSWORD（仅当 BTBAR_ACCOUNTS 为空）。
BTBAR_PAST_LOGIN_TIME：可选，Hm_lvt 曾经登录时间戳（与上游 PastLoginTime 对应）；留空则使用当前时间。
BTBAR_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
BTBAR_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：10 8 * * *。不打印密码、Cookie、Token 或原始响应。
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
            "c774ef56607cd4e3",
            "scripts/btbar_checkin.py",
            "btbar_checkin.py",
            "btbar_checkin",
            "candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import ast
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

TITLE = "BT吧签到"
CATALOG_ID = "c774ef56607cd4e3"
BASE = "https://u.aibtba.com"
LOGIN_URL = "{}/user/login".format(BASE)
SIGN_URL = (
    "{}/sign?search_referer=https%3A%2F%2Fu.aibtba.com%2F&callback=Json".format(BASE)
)
SELECT_URL = "{}/sign/select?callback=Json".format(BASE)
SEARCH_REFERER = "search_referer=https%253A%252F%252Fu.aibtba.com%252F"
BT_SIGN = "bt_sign=%25E5%25B7%25B2%25E7%25AD%25BE%25E5%2588%25B0"
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
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15"
)
HM_LPVT = "Hm_lpvt_19a24d91cbe5649b8e7449e1b7c1a97e"
HM_LVT = "Hm_lvt_19a24d91cbe5649b8e7449e1b7c1a97e"


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
    raw = env("BTBAR_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("BTBAR_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("BTBAR_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_past_login_time() -> str:
    raw = env("BTBAR_PAST_LOGIN_TIME")
    if not raw:
        return str(int(time.time()))
    if not re.fullmatch(r"\d{9,12}(,\d{9,12})*", raw):
        raise SafeError(
            "BTBAR_PAST_LOGIN_TIME 须为 Unix 时间戳，或多个逗号分隔的时间戳"
        )
    return raw


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 手机号或邮箱|密码")
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("账号或密码为空")
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
    raw = env("BTBAR_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("BTBAR_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("BTBAR_USER")
    password = env("BTBAR_PASSWORD")
    if username or password:
        if not username or not password:
            raise SafeError(
                "兼容别名需同时提供 BTBAR_USER 与 BTBAR_PASSWORD；"
                "推荐改用 BTBAR_ACCOUNTS（手机号或邮箱|密码）"
            )
        return [{"username": username, "password": password}]
    raise SafeError(
        "未配置 BTBAR_ACCOUNTS；请按每个非空行 手机号或邮箱|密码 填写"
    )


def decode_jsonp(raw: bytes) -> Any:
    if not raw:
        raise SafeError("响应为空")
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        raise SafeError("响应解码失败") from exc
    text = text.strip()
    # 上游使用 unicode_escape 处理部分中文转义；先尝试直接解析 JSONP。
    stripped = re.sub(r"^Json\s*\(", "", text, count=1, flags=re.I)
    if stripped.endswith(")"):
        stripped = stripped[:-1]
    stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    try:
        decoded = raw.decode("unicode_escape")
        stripped2 = re.sub(r"Json\(|\)", "", decoded)
        return ast.literal_eval(stripped2)
    except Exception as exc:
        raise SafeError("签到响应不是可解析的 JSONP") from exc


def cookie_map(jar: http.cookiejar.CookieJar) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for cookie in jar:
        mapping[cookie.name] = cookie.value
    return mapping


def public_identity(cookies: Dict[str, str]) -> str:
    nickname = cookies.get("bt_nickname") or ""
    if nickname:
        try:
            nickname = urllib.parse.unquote(nickname)
        except Exception:
            pass
        nickname = compact(nickname, 64)
        if nickname and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", nickname):
            return nickname
    user_id = cookies.get("bt_user_id") or ""
    if user_id and re.fullmatch(r"\d{1,12}", user_id):
        return "UID:{}".format(user_id)
    return ""


def read_gold(cookies: Dict[str, str]) -> int:
    raw = cookies.get("bt_gold") or "0"
    try:
        return int(raw)
    except ValueError:
        return 0


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


class BtbarClient:
    def __init__(self, timeout: float, past_login_time: str) -> None:
        self.timeout = timeout
        self.past_login_time = past_login_time
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def _analytics_cookie(self) -> str:
        now = str(int(time.time()))
        return "{}={}; {}={}".format(HM_LPVT, now, HM_LVT, self.past_login_time)

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        extra_cookie: str = "",
    ) -> Tuple[int, bytes]:
        base_headers = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Connection": "keep-alive",
        }
        if headers:
            base_headers.update(headers)
        if extra_cookie:
            existing = base_headers.get("Cookie", "")
            base_headers["Cookie"] = (
                "{}; {}".format(existing, extra_cookie).strip("; ").strip()
                if existing
                else extra_cookie
            )
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
        return status, raw


def do_login(
    client: BtbarClient, username: str, password: str
) -> Tuple[str, str, Dict[str, Any]]:
    body = urllib.parse.urlencode(
        {
            "mobile_email": username,
            "bt_password": password,
            "submit": "1",
        }
    ).encode("utf-8")
    status, _raw = client.request(
        LOGIN_URL,
        "POST",
        body,
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE,
            "Referer": "{}/user/login".format(BASE),
        },
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status not in (200, 302):
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    cookies = cookie_map(client.jar)
    if not cookies.get("BTBASESSID") and not cookies.get("bt_user_id"):
        raise SafeError("登录未获得有效会话 Cookie")
    identity = public_identity(cookies)
    gold = read_gold(cookies)
    detail = "登录成功；当前 BT 币 {}".format(gold)
    if identity:
        detail = "登录成功；公开身份：{}；当前 BT 币 {}".format(identity, gold)
    return "success", detail, {
        "identity": identity,
        "gold": gold,
        "cookies": cookies,
    }


def do_sign(client: BtbarClient, gold: int) -> Tuple[str, str, Dict[str, Any]]:
    analytics = client._analytics_cookie()
    cookie_extra = "{}; {}".format(analytics, SEARCH_REFERER)
    status, raw = client.request(
        SIGN_URL,
        "GET",
        headers={"Referer": "https://www.aibtba.com/"},
        extra_cookie=cookie_extra,
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    payload = decode_jsonp(raw)
    add_coin = 0
    if isinstance(payload, (list, tuple)) and len(payload) >= 3:
        try:
            add_coin = int(payload[2])
        except (TypeError, ValueError):
            add_coin = 0
    elif isinstance(payload, dict):
        for key in ("gold", "coin", "bt_gold", "add", "num"):
            if key in payload:
                try:
                    add_coin = int(payload[key])
                    break
                except (TypeError, ValueError):
                    pass
    else:
        raise SafeError("签到响应结构不符合预期")

    new_gold = gold + add_coin
    for cookie in client.jar:
        if cookie.name == "bt_gold":
            cookie.value = str(new_gold)

    if add_coin == 0:
        detail = "今日已签到，请勿重复签到；当前 BT 币 {}".format(new_gold)
        state = "alreadyComplete"
    else:
        detail = "签到成功；获得 {} BT 币；当前 BT 币 {}".format(add_coin, new_gold)
        state = "success"
    return state, detail, {
        "addCoin": add_coin,
        "gold": new_gold,
        "analytics": analytics,
    }


def do_select(
    client: BtbarClient, gold: int, analytics: str
) -> Tuple[str, str, Dict[str, Any]]:
    select_cookie = re.sub(
        r"bt_gold=\d{1,6}",
        "bt_gold={}".format(gold),
        analytics,
    )
    select_extra = "{}; {}; {}".format(select_cookie, SEARCH_REFERER, BT_SIGN)
    status, raw = client.request(
        SELECT_URL,
        "GET",
        headers={"Referer": "https://www.aibtba.com/"},
        extra_cookie=select_extra,
    )
    if status in (401, 403):
        raise SafeError("签到摘要凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到摘要请求失败（HTTP {}）".format(status))
    payload = decode_jsonp(raw)
    if not isinstance(payload, dict):
        raise SafeError("签到摘要响应结构不符合预期")
    keep = None
    count = payload.get("count")
    if isinstance(count, (int, float)):
        keep = int(count)
    elif isinstance(count, str) and count.strip().isdigit():
        keep = int(count.strip())
    if keep is None:
        raise SafeError("签到摘要缺少连续签到天数")
    detail = "连续签到 {} 天；当前 BT 币 {}".format(keep, gold)
    return "success", detail, {"keep": keep, "gold": gold, "payload": payload}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    past_login_time: str,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("账号或密码为空")
        return "success", "账号密码本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录", "断网预演：不请求登录接口")
        runner.skip(3, "执行签到", "断网预演：不请求签到接口")
        runner.skip(4, "读取签到摘要", "断网预演：不请求签到摘要接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = BtbarClient(timeout, past_login_time)
    gold_box: Dict[str, int] = {"gold": 0}
    analytics_box: Dict[str, str] = {"analytics": ""}
    checkin_state_box: Dict[str, str] = {"state": "failure"}

    def login_stage():
        state, detail, result = do_login(
            client, account["username"], account["password"]
        )
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            gold_box["gold"] = int(result.get("gold") or 0)
        if identity:
            runner.identity = identity
        return state, detail, result

    runner.stage(2, "登录", login_stage)

    def sign_stage():
        state, detail, result = do_sign(client, gold_box["gold"])
        checkin_state_box["state"] = state
        if isinstance(result, dict):
            gold_box["gold"] = int(result.get("gold") or gold_box["gold"])
            analytics_box["analytics"] = str(result.get("analytics") or "")
        return state, detail, result

    runner.stage(3, "执行签到", sign_stage)

    def summary_stage():
        try:
            return do_select(client, gold_box["gold"], analytics_box["analytics"])
        except SafeError as error:
            message = str(error)
            if "凭据无效" in message or "会话已过期" in message:
                raise
            # 摘要仅用于展示连续天数；签到主结果已在上一阶段确认。
            return "skipped", "签到摘要不可用：{}".format(message), None

    runner.stage(4, "读取签到摘要", summary_stage)

    if runner.stats["failure"] or checkin_state_box["state"] == "failure":
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
        "btbar_checkin.py",
        "candidate.py",
        "scripts/btbar_checkin.py",
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
    dry_setting = env("BTBAR_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    past_login_time = str(int(time.time()))
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("BTBAR_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        past_login_time = resolve_past_login_time()
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
                run_account(runner, account, timeout, past_login_time, dry_run)
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
