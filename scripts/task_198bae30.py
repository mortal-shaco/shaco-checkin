#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 洛谷签到
# cron: 0 10 * * *
#
# SPDX-License-Identifier: GPL-3.0-only
#
# 本文件为 kierankihn/auto-checkin（GPL-3.0）的青龙维护衍生版本。
# 上游仓库：https://github.com/kierankihn/auto-checkin
# 上游路径：main.py
# 上游提交：03a84c7abf61d75d85e81e32d1002a72ff9a78a8
# 原作者：Kieran Kihn
#
# Copyright (C) Kieran Kihn and contributors
# Copyright (C) maintained Qinglong derivative authors
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
"""洛谷（luogu.com.cn）每日打卡 - 青龙维护版。

功能清点（相对上游 kierankihn/auto-checkin/main.py）：
- GET https://www.luogu.com.cn/index/ajax_punch 使用 Cookie __client_id 与 _uid 打卡
- 业务 code=200 视为签到成功；code=201 视为今日已签到
- 多账号：上游 config.json 的 token 数组改为环境变量按行配置
- 移除常驻 schedule 守护进程与 config.json / requests 依赖；改由青龙 cron 调度
- 增加 LUOGU_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

LUOGU_ACCOUNTS：每个非空行一个账号，格式 __client_id|_uid；仅在第一个 | 处分割。
兼容单行 Cookie 文本（须同时含 __client_id= 与 _uid=）。
LUOGU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
LUOGU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
建议 Cron：0 10 * * *（对应上游默认 Asia/Shanghai 10:00）。
不打印 __client_id、Cookie、Token 或原始响应；公开 UID 原样展示以便核对。
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
        _ql_notify_identities = ('198bae30a009b250', 'scripts/task_198bae30.py', 'task_198bae30.py', 'task_198bae30')
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
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "洛谷签到"
CATALOG_ID = "198bae30a009b250"
PUNCH_URL = "https://www.luogu.com.cn/index/ajax_punch"
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
    "Chrome/120.0.0.0 Safari/537.36"
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
    raw = env("LUOGU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("LUOGU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("LUOGU_TIMEOUT 须在 5 到 60 秒之间")
    return value


def parse_cookie_pair(text: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for part in text.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        mapping[key.strip()] = value.strip()
    client_id = mapping.get("__client_id", "").strip()
    uid = mapping.get("_uid", "").strip()
    if not client_id or not uid:
        raise SafeError("Cookie 文本须同时包含 __client_id 与 _uid")
    return {"client_id": client_id, "uid": uid}


def parse_account_line(text: str) -> Dict[str, str]:
    if "__client_id=" in text and "_uid=" in text:
        return parse_cookie_pair(text)
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 __client_id|_uid")
    client_id, uid = text.split("|", 1)
    client_id = client_id.strip()
    uid = uid.strip()
    if not client_id or not uid:
        raise SafeError("__client_id 或 _uid 为空")
    if any(ord(ch) < 32 for ch in client_id) or any(ord(ch) < 32 for ch in uid):
        raise SafeError("账号行含控制字符")
    if not re.fullmatch(r"[0-9]+", uid):
        raise SafeError("_uid 须为数字")
    if len(client_id) < 8:
        raise SafeError("__client_id 长度过短")
    return {"client_id": client_id, "uid": uid}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("LUOGU_ACCOUNTS")
    if not raw:
        raise SafeError(
            "未配置 LUOGU_ACCOUNTS；请按每个非空行 __client_id|_uid 填写"
        )
    accounts = parse_accounts(raw)
    if not accounts:
        raise SafeError("LUOGU_ACCOUNTS 没有有效账号行")
    return accounts


def build_cookie(account: Dict[str, str]) -> str:
    return "__client_id={}; _uid={};".format(account["client_id"], account["uid"])


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "error", "detail", "Message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def redact_detail(text: str, secrets: List[str]) -> str:
    result = compact(text)
    for secret in secrets:
        if secret and secret in result:
            result = result.replace(secret, "[REDACTED]")
    return result


class AccountRunner:
    def __init__(self, number: int, uid: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = "uid={}".format(uid) if uid else ""

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


def request_punch(cookie: str, timeout: float) -> Tuple[int, Any]:
    request = urllib.request.Request(
        PUNCH_URL,
        headers={
            "Cookie": cookie,
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.luogu.com.cn/",
        },
        method="GET",
    )
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


def do_punch(account: Dict[str, str], timeout: float) -> Tuple[str, str, Any]:
    cookie = build_cookie(account)
    status, result = request_punch(cookie, timeout)
    if status in (401, 403):
        raise SafeError("打卡凭据无效或会话已过期")
    if status != 200:
        raise SafeError("打卡请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("打卡响应无法解析")
    code = result.get("code")
    message = business_message(result)
    if code == 200:
        detail = "打卡成功"
        if message:
            detail = "打卡成功；{}".format(redact_detail(message, [account["client_id"]]))
        return "success", detail, result
    if code == 201:
        detail = "今日已打卡"
        if message:
            detail = "今日已打卡；{}".format(redact_detail(message, [account["client_id"]]))
        return "alreadyComplete", detail, result
    raise SafeError("打卡业务失败（code={}）".format(compact(code, 32) or "未知"))


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["client_id"] or not account["uid"]:
            raise SafeError("__client_id 或 _uid 为空")
        if not re.fullmatch(r"[0-9]+", account["uid"]):
            raise SafeError("_uid 须为数字")
        return "success", "本地凭据字段检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "执行打卡", "断网预演：不请求洛谷打卡接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    punch_state_box: Dict[str, str] = {"state": "failure"}

    def punch_stage():
        state, detail, result = do_punch(account, timeout)
        punch_state_box["state"] = state
        return state, detail, result

    runner.stage(2, "执行打卡", punch_stage)

    if runner.stats["failure"]:
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
        "luogu_checkin.py",
        "candidate.py",
        "scripts/luogu_checkin.py",
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
    dry_setting = env("LUOGU_DRY_RUN", "0").lower()
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
            raise SafeError("LUOGU_DRY_RUN 配置无效，停止执行")
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
            runner = AccountRunner(number, account["uid"])
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
