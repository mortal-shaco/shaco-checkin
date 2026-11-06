#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 爱桌游每日签到
# cron: 0 5 * * *
#
# 来源：nix18/LovezhuoyouAutoCheck index.py（GPL-3.0）
# https://github.com/nix18/LovezhuoyouAutoCheck
# 提交：79899de771327e1976a3f8ab76a457fc2010ef6d
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) nix18 and LovezhuoyouAutoCheck contributors
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
"""爱桌游（www.lovezhuoyou.com）每日签到 - 青龙维护版。

功能清点（相对上游 index.py / user.py）：
- 使用站点登录 Cookie，POST /wp-admin/admin-ajax.php，action=user_qiandao
- 按官方 JSON 的 status / msg 判定签到成功或今日已签到
- 移除硬编码空 Cookie、PushPlus 外链推送与无超时请求
- 增加逐行多账号、LOVEZHUOYOU_DRY_RUN 断网预演、请求超时、时间轴日志、
  青龙通知与 TASK_SUMMARY

LOVEZHUOYOU_COOKIE：每个非空行一个账号的完整 Cookie 头。
兼容单账号别名：LOVEZHUOYOU_COOKIE_STR（仅当规范变量为空时生效）。
LOVEZHUOYOU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
LOVEZHUOYOU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 5 * * *。不打印 Cookie、会话值或原始响应。
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
        _ql_notify_identities = ('d530fa5843da0143', 'scripts/task_d530fa58.py', 'task_d530fa58.py', 'task_d530fa58')
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
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "爱桌游每日签到"
CATALOG_ID = "d530fa5843da0143"
HOST = "https://www.lovezhuoyou.com"
CHECKIN_URL = HOST + "/wp-admin/admin-ajax.php"
USER_URL = HOST + "/user"
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
    "Chrome/97.0.4692.71 Safari/537.36"
)
SUCCESS_HINTS = ("签到成功", "打卡成功", "成功签到")
ALREADY_HINTS = ("已签到", "已经签到", "重复签到", "今日已签", "无需重复", "明天再来")
IDENTITY_KEYS = (
    "display_name",
    "displayName",
    "nickname",
    "nick_name",
    "user_nicename",
    "username",
    "name",
    "user_login",
    "uid",
    "user_id",
    "id",
)
IDENTITY_HTML_RE = re.compile(
    r"(?:当前用户|欢迎|你好)[：:\s]*"
    r"([^\s<>\"']{1,64})"
    r'|data-name=["\']([^"\']{1,64})["\']'
    r'|class=["\'][^"\']*user-name[^"\']*["\'][^>]*>\s*([^<\s]{1,64})',
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
    raw = env("LOVEZHUOYOU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("LOVEZHUOYOU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("LOVEZHUOYOU_TIMEOUT 须在 5 到 60 秒之间")
    return value


def validate_cookie(cookie: str) -> str:
    text = cookie.strip()
    if not text:
        raise SafeError("Cookie 为空")
    if any(ord(ch) < 32 for ch in text):
        raise SafeError("Cookie 含控制字符")
    if len(text) < 8:
        raise SafeError("Cookie 过短，疑似无效")
    lowered = text.lower()
    if "cookie:" in lowered:
        raise SafeError("请只填写 Cookie 头的值，不要包含 Cookie: 前缀")
    return text


def parse_accounts(raw: str) -> List[str]:
    accounts: List[str] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(validate_cookie(text))
    return accounts


def load_accounts() -> List[str]:
    raw = env("LOVEZHUOYOU_COOKIE")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("LOVEZHUOYOU_COOKIE 没有有效账号行")
        return accounts
    alias = env("LOVEZHUOYOU_COOKIE_STR")
    if alias:
        return [validate_cookie(alias)]
    raise SafeError(
        "未配置 LOVEZHUOYOU_COOKIE；请按每个非空行填写一个站点 Cookie；"
        "兼容单账号别名 LOVEZHUOYOU_COOKIE_STR"
    )


def truthy_status(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "ok", "success", "yes"}:
        return True
    if text in {"0", "false", "fail", "error", "no"}:
        return False
    return None


def message_of(payload: Dict[str, Any]) -> str:
    for key in ("msg", "message", "error_msg", "info"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return compact(value, 120)
    return ""


def identity_from_payload(payload: Dict[str, Any]) -> str:
    for key in IDENTITY_KEYS:
        if key not in payload:
            continue
        value = compact(payload.get(key), 64)
        if not value:
            continue
        if key in {"uid", "user_id", "id"}:
            if value.isdigit():
                return "UID {}".format(value)
            continue
        if "@" in value or len(value) > 48:
            continue
        return value
    data = payload.get("data")
    if isinstance(data, dict):
        return identity_from_payload(data)
    user = payload.get("user")
    if isinstance(user, dict):
        return identity_from_payload(user)
    return ""


def identity_from_html(html: str) -> str:
    match = IDENTITY_HTML_RE.search(html or "")
    if not match:
        return ""
    value = next((group for group in match.groups() if group), "")
    value = compact(value, 64)
    if not value or value.lower() in {"null", "undefined", "guest"}:
        return ""
    return value


def classify_checkin(payload: Dict[str, Any]) -> Tuple[str, str]:
    message = message_of(payload)
    lowered = message.lower()
    status = truthy_status(payload.get("status"))
    if status is None and "error" in payload:
        error_value = payload.get("error")
        if isinstance(error_value, (int, float)):
            status = True if int(error_value) == 0 else False
        elif isinstance(error_value, str) and error_value.strip().isdigit():
            status = True if int(error_value.strip()) == 0 else False
    if any(hint in message for hint in ALREADY_HINTS) or any(
        hint in lowered for hint in ("already", "signed")
    ):
        return "alreadyComplete", message or "今日已签到"
    if any(hint in message for hint in SUCCESS_HINTS):
        return "success", message or "签到成功"
    if status is True:
        return "success", message or "签到成功"
    if status is False:
        raise SafeError("签到失败：{}".format(message or "业务状态失败"))
    raise SafeError("签到响应缺少可核验的成功或已签到证明")


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = "账号{}".format(number)

    def display(self) -> str:
        return self.identity

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


class LovezhuoyouClient:
    def __init__(self, cookie: str, timeout: float) -> None:
        self.cookie = cookie
        self.timeout = timeout

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        base_headers = {
            "Host": "www.lovezhuoyou.com",
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": HOST + "/",
            "Referer": HOST + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": self.cookie,
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
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
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


def parse_json_object(text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise SafeError("签到响应不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise SafeError("签到响应 JSON 不是对象")
    return payload


def do_checkin(client: LovezhuoyouClient) -> Tuple[str, str, Dict[str, Any]]:
    body = urllib.parse.urlencode({"action": "user_qiandao"}).encode("utf-8")
    status, text = client.request(
        CHECKIN_URL,
        "POST",
        body,
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    payload = parse_json_object(text)
    state, detail = classify_checkin(payload)
    identity = identity_from_payload(payload)
    return state, detail, {"identity": identity, "message": detail}


def do_identity_probe(client: LovezhuoyouClient) -> Tuple[str, str, Dict[str, Any]]:
    status, text = client.request(
        USER_URL,
        "GET",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    if status in (401, 403):
        return "skipped", "用户页凭据无效，跳过身份核对", None
    if status != 200:
        return "skipped", "用户页不可用（HTTP {}）".format(status), None
    identity = identity_from_html(text)
    if not identity:
        return "skipped", "用户页未解析到公开身份", None
    return "success", "公开身份：{}".format(identity), {"identity": identity}


def run_account(
    runner: AccountRunner,
    cookie: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        validate_cookie(cookie)
        return "success", "账号本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "执行签到", "断网预演：不请求签到接口")
        runner.skip(3, "读取公开身份", "断网预演：不请求用户页")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = LovezhuoyouClient(cookie, timeout)
    checkin_state_box: Dict[str, str] = {"state": "failure"}

    def checkin_stage():
        state, detail, result = do_checkin(client)
        checkin_state_box["state"] = state
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
                log("账号 {} 官方账户身份：{}".format(runner.number, identity))
        return state, detail, result

    runner.stage(2, "执行签到", checkin_stage)

    def identity_stage():
        if runner.identity and not runner.identity.startswith("账号"):
            return "skipped", "签到响应已提供公开身份", None
        try:
            state, detail, result = do_identity_probe(client)
        except SafeError as error:
            return "skipped", "公开身份不可用：{}".format(error), None
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
                log("账号 {} 官方账户身份：{}".format(runner.number, identity))
        return state, detail, result

    runner.stage(3, "读取公开身份", identity_stage)

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
        "lovezhuoyou_checkin.py",
        "candidate.py",
        "scripts/lovezhuoyou_checkin.py",
        TITLE,
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
    dry_setting = env("LOVEZHUOYOU_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[str] = []
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
            raise SafeError("LOVEZHUOYOU_DRY_RUN 配置无效，停止执行")
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
        for number, cookie in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, cookie, timeout, dry_run)
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
        log("无网络预演通过")
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
