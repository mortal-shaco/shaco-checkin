#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 大物是也签到
# cron: 7 8 * * *
#
# 来源：Transmigration-zhou/dawushiye-checkin sign.py（MIT）
# https://github.com/Transmigration-zhou/dawushiye-checkin
# 提交：c3b44d4b77f8e22fb0e16ec2fdea7407de14eda6
#
# MIT License
#
# Copyright (c) Transmigration-zhou / dawushiye-checkin contributors
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
"""大物是也微信小程序自动签到 - 青龙维护版。

功能清点（相对上游 sign.py）：
- 查询签到状态 GetMiniUserSignData
- 执行小程序签到 MiniUserSign
- 识别业务成功码与「已签到」文案
- 移除原始响应打印与 requests 依赖，改用标准库 HTTPS
- 增加逐行多账号、DAWU_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

DAWU_TOKEN：每个非空行一个账号的 Authorization 值（通常含 Bearer 前缀的 JWT），
直接复制微信开发者工具中签到接口请求头 Authorization；账号之间只用换行分隔。
DAWU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
DAWU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：0 8 * * *。不打印 Token、Authorization 或原始响应。
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
        _ql_notify_identities = ('e787b4b7d6d30c4b', 'scripts/dawushiye.py', 'dawushiye.py', 'dawushiye')
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

TITLE = "大物是也签到"
CATALOG_ID = "e787b4b7d6d30c4b"
BASE_URL = "https://api.dawushiye.com"
SIGN_URL = "{}/api/MarketingWechat/Sign/MiniUserSign".format(BASE_URL)
QUERY_URL = "{}/api/MarketingWechat/Sign/GetMiniUserSignData".format(BASE_URL)
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
SUCCESS_CODES = {0, 200, "0", "200", True, "success", "Success", "SUCCESS"}
ALREADY_HINTS = ("已签到", "重复签到", "已经签到", "今日已签", "签过到")
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "nick",
    "userName",
    "username",
    "displayName",
    "display_name",
    "name",
    "uid",
    "userId",
    "user_id",
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Mac MacWechat/WMPF "
    "MacWechat/3.8.7(0x13080712) "
    "UnifiedPCMacWechat(0xf2641701) XWEB/18788"
)
REFERER = "https://servicewechat.com/wx9d7354501dec9fe8/21/page-frame.html"


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
    raw = env("DAWU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("DAWU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("DAWU_TIMEOUT 须在 5 到 60 秒之间")
    return value


def validate_token(token: str) -> str:
    text = token.strip()
    if not text:
        raise SafeError("Authorization 令牌为空")
    if any(ord(ch) < 32 for ch in text):
        raise SafeError("令牌含控制字符")
    if len(text) < 16:
        raise SafeError("令牌过短，疑似未完整复制 Authorization")
    return text


def parse_accounts(raw: str) -> List[str]:
    accounts: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(validate_token(text))
    return accounts


def load_accounts() -> List[str]:
    raw = env("DAWU_TOKEN")
    if not raw:
        raise SafeError(
            "未配置 DAWU_TOKEN；请按每个非空行一个 Authorization 令牌填写"
        )
    accounts = parse_accounts(raw)
    if not accounts:
        raise SafeError("DAWU_TOKEN 没有有效账号行")
    return accounts


def business_code(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in ("resultCode", "code", "Code", "status", "Status"):
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return None


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("errorMessage", "msg", "message", "Message", "error", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    candidates: List[Any] = []
    if isinstance(data, dict):
        candidates.append(data)
        for key in ("user", "userInfo", "profile", "member", "account", "miniUser"):
            nested = data.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
    candidates.append(payload)
    for mapping in candidates:
        if not isinstance(mapping, dict):
            continue
        for key in IDENTITY_KEYS:
            value = mapping.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                text = compact(value, 64)
                if not text:
                    continue
                lowered = key.lower()
                if lowered in {"token", "authorization"}:
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                return text
    return ""


def extract_integral(payload: Any) -> Optional[Any]:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and "integral" in data:
        return data.get("integral")
    if "integral" in payload:
        return payload.get("integral")
    return None


def is_success_code(code: Any) -> bool:
    return code in SUCCESS_CODES


def is_already_signed(payload: Any) -> bool:
    message = business_message(payload)
    if any(hint in message for hint in ALREADY_HINTS):
        return True
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        for key in ("isSign", "signed", "hasSigned", "todaySigned"):
            value = data.get(key)
            if value in (True, 1, "1", "true", "True"):
                return True
    return False


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""
        self.integral: Optional[Any] = None

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
        extra = ""
        if self.integral is not None:
            extra = "；积分 {}".format(compact(self.integral, 32))
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


class DawushiyeClient:
    def __init__(self, token: str, timeout: float) -> None:
        self.token = token
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _headers(self) -> Dict[str, str]:
        return {
            "Host": "api.dawushiye.com",
            "Connection": "keep-alive",
            "User-Agent": UA,
            "xweb_xhr": "1",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "*/*",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": REFERER,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Authorization": self.token,
        }

    def request_json(self, url: str) -> Tuple[int, Any]:
        # 上游使用 data="null"（JSON null 字面量），保持相同请求体。
        body = b"null"
        request = urllib.request.Request(
            url, data=body, headers=self._headers(), method="POST"
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
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise SafeError("响应不是合法 JSON") from exc


def query_sign(client: DawushiyeClient) -> Tuple[str, str, Any]:
    status, result = client.request_json(QUERY_URL)
    if status in (401, 403):
        raise SafeError("查询凭据无效或会话已过期")
    if status != 200:
        raise SafeError("查询签到状态失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("查询响应无法解析")
    code = business_code(result)
    if is_success_code(code) or code is None:
        detail = "已获取签到状态"
        if is_already_signed(result):
            detail = "查询显示今日已签到"
        return "success", detail, result
    hint = business_message(result)
    if is_already_signed(result):
        return "success", "查询显示今日已签到", result
    if hint:
        raise SafeError("查询业务失败")
    raise SafeError("查询业务失败（缺少可核实成功字段）")


def do_sign(client: DawushiyeClient) -> Tuple[str, str, Any]:
    status, result = client.request_json(SIGN_URL)
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("签到响应无法解析")
    code = business_code(result)
    integral = extract_integral(result)
    if is_success_code(code):
        detail = "签到成功（业务码已核实）"
        if integral is not None:
            detail = "签到成功，获得 {} 积分".format(compact(integral, 32))
        return "success", detail, result
    if is_already_signed(result):
        return "alreadyComplete", "今日已签到，无需重复签到", result
    hint = business_message(result)
    if hint:
        raise SafeError("签到业务失败")
    raise SafeError("签到业务失败（缺少可核实成功字段）")


def run_account(
    runner: AccountRunner,
    token: str,
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        validate_token(token)
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "查询签到状态", "断网预演：不请求查询接口")
        runner.skip(3, "执行签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = DawushiyeClient(token, timeout)
    query_failed = False

    def query_stage():
        nonlocal query_failed
        try:
            state, detail, result = query_sign(client)
        except SafeError as error:
            message = str(error)
            if "凭据无效" in message or "会话已过期" in message:
                raise
            query_failed = True
            return "skipped", "查询跳过：{}".format(message), None
        identity = extract_identity(result)
        if identity:
            runner.identity = identity
            detail = "{}；公开身份：{}".format(detail, identity)
        integral = extract_integral(result)
        if integral is not None:
            runner.integral = integral
        return state, detail, result

    runner.stage(2, "查询签到状态", query_stage)

    sign_state_box: Dict[str, str] = {"state": "failure"}

    def sign_stage():
        state, detail, result = do_sign(client)
        identity = extract_identity(result)
        if identity:
            runner.identity = identity
            detail = "{}；公开身份：{}".format(detail, identity)
        integral = extract_integral(result)
        if integral is not None:
            runner.integral = integral
        sign_state_box["state"] = state
        if query_failed:
            detail = "{}（查询阶段已跳过）".format(detail)
        return state, detail, result

    runner.stage(3, "执行签到", sign_stage)

    if runner.stats["failure"]:
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
        "dawushiye_checkin.py",
        "candidate.py",
        "sign.py",
        "scripts/dawushiye_checkin.py",
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
    dry_setting = env("DAWU_DRY_RUN", "0").lower()
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
            raise SafeError("DAWU_DRY_RUN 配置无效，停止执行")
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
        for number, token in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, token, timeout, dry_run)
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
