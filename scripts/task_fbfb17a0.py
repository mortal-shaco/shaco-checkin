#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 起点阅读 App 签到
# cron: 4 1 * * *
# new Env("起点阅读 App 签到")
#
# 来源：BRSblackshoot/qd_autosign 某阅读软件app自动签到.py（MIT）
# https://github.com/BRSblackshoot/qd_autosign
# 提交：006557e86f4095ff16ea5c96c59987864c907464
#
# MIT License
#
# Copyright (c) BRSblackshoot / qd_autosign contributors
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
"""起点阅读 App（druidv6.if.qidian.com）每日签到 - 青龙维护版。

功能清点（相对上游 某阅读软件app自动签到.py）：
- 使用抓包 Cookie 与 QDSign 材料，按上游 DES3 算法重算 QDSign 后 POST 签到
- 上游硬编码单账号、无限死循环定时、yagmail 邮件与原始响应写日志
- 本版改为环境变量多账号、青龙 cron、标准库 HTTP、超时、业务成功判定、
  脱敏时间轴日志、青龙通知与 QIDIAN_DRY_RUN 完全断网预演
- 已维护同产品覆盖为空，无并行脚本；不合并其他应用

QIDIAN_ACCOUNTS：每个非空行一个账号，格式 QDSign|Cookie
  仅在第一个竖线处分割：首段为任意一次 argus/api/v2 请求抓到的 QDSign（Base64），
  其余整段为同账号 Cookie；Cookie 可含竖线。不要用 & 或 @ 分隔账号。
兼容单账号别名：同时设置 QIDIAN_QDSIGN 与 QIDIAN_COOKIE（仅当 QIDIAN_ACCOUNTS 为空）。
QIDIAN_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..90。
QIDIAN_DRY_RUN=1：完全断网预演，只校验参数与本地签名材料，不发起网络请求。
建议 Cron：5 0 * * *（对齐上游约 00:00 签到习惯，略错开整点）。
正式运行依赖公开包 pycryptodome；预演若未安装仅警告，正式执行必装。
不打印 Cookie、QDSign、签名材料、设备标识或原始响应。
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
        _ql_notify_identities = ('fbfb17a0c5ba2e60', 'scripts/task_fbfb17a0.py', 'task_fbfb17a0.py', 'task_fbfb17a0')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
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

TITLE = "起点阅读 App 签到"
CATALOG_ID = "fbfb17a0c5ba2e60"
APPLICATION_KEY = "brsblackshoot/qd_autosign::某阅读软件app自动签到"
SIGN_URL = "https://druidv6.if.qidian.com/argus/api/v2/checkin/checkin"
SIGN_QUERY = (
    "sessionKey=&banId=0&captchaTicket=&captchaRandStr="
    "&challenge=&validate=&seccode="
)
# 上游逆向得到的固定 DES3 密钥与 CBC IV（非用户凭据）
DES3_KEY = b"{1dYgqE)h9,R)hKqEcv4]k[h"
DES3_IV = b"01234567"
SIGN_STATIC_TAIL = (
    "1|66cbf4b006fdedd1712e3a3bb1f861fb|f189adc92b816b3e9da29ea304d4a7e4"
)
DEFAULT_TIMEOUT = 20
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
ALREADY_HINTS = ("已签到", "已经签到", "重复签到", "今日已签", "已完成签到", "无需重复")
UA = (
    "Mozilla/5.0 (Linux; Android 12; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(stamp(), message), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env("QIDIAN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("QIDIAN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 90:
        raise SafeError("QIDIAN_TIMEOUT 须在 5 到 90 秒之间")
    return value


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少分隔符；格式为 QDSign|Cookie")
    qdsign, cookie = text.split("|", 1)
    qdsign = qdsign.strip()
    cookie = cookie.strip()
    if not qdsign or not cookie:
        raise SafeError("QDSign 或 Cookie 为空")
    if any(ord(ch) < 32 for ch in qdsign) or any(ord(ch) < 32 for ch in cookie):
        raise SafeError("账号行含控制字符")
    # Base64 粗校验，避免把 Cookie 误写到首段
    try:
        base64.b64decode(qdsign, validate=False)
    except Exception as exc:
        raise SafeError("首段 QDSign 不是合法 Base64") from exc
    if len(qdsign) < 16:
        raise SafeError("首段 QDSign 过短，请确认抓包材料")
    return {"qdsign": qdsign, "cookie": cookie}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("QIDIAN_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("QIDIAN_ACCOUNTS 没有有效账号行")
        return accounts
    qdsign = env("QIDIAN_QDSIGN")
    cookie = env("QIDIAN_COOKIE")
    if qdsign or cookie:
        if not qdsign or not cookie:
            raise SafeError(
                "兼容别名需同时提供 QIDIAN_QDSIGN 与 QIDIAN_COOKIE；"
                "推荐改用 QIDIAN_ACCOUNTS（QDSign|Cookie）"
            )
        return [parse_account_line("{}|{}".format(qdsign, cookie))]
    raise SafeError("未配置 QIDIAN_ACCOUNTS；请按每个非空行 QDSign|Cookie 填写")


def load_crypto():
    try:
        from Crypto.Cipher import DES3  # type: ignore
        from Crypto.Util.Padding import pad, unpad  # type: ignore
    except Exception as exc:
        raise SafeError(
            "缺少公开依赖 pycryptodome，请在青龙依赖管理中执行：pip install pycryptodome"
        ) from exc
    return DES3, pad, unpad


def decode_qdsign_parts(catch_qdsign: str) -> List[str]:
    DES3, _pad, unpad = load_crypto()
    try:
        raw = base64.b64decode(catch_qdsign)
    except Exception as exc:
        raise SafeError("QDSign Base64 解码失败") from exc
    try:
        cryptor = DES3.new(DES3_KEY, DES3.MODE_CBC, DES3_IV)
        plain = unpad(cryptor.decrypt(raw), 8)
    except Exception as exc:
        raise SafeError("QDSign 解密失败，请确认材料来自起点 argus 请求") from exc
    try:
        text = plain.decode("utf-8")
    except Exception as exc:
        raise SafeError("QDSign 明文不是合法 UTF-8") from exc
    parts = text.split("|")
    # 上游 calc_qdsign 使用 list[2], list[3], list[5]
    if len(parts) < 6:
        raise SafeError("QDSign 明文字段不足，无法重算签名")
    if not parts[2] or not parts[3] or not parts[5]:
        raise SafeError("QDSign 明文缺少签名必要字段")
    return parts


def calc_qdsign(parts: List[str]) -> str:
    DES3, pad, _unpad = load_crypto()
    token = parts[2]
    did = parts[3]
    version = parts[5]
    ts = int(round(time.time() * 1000))
    payload = "Rv1rPTnczce|{}|{}|{}|1|{}|{}".format(
        ts, token, did, version, SIGN_STATIC_TAIL
    ).encode("utf-8")
    try:
        cryptor = DES3.new(DES3_KEY, DES3.MODE_CBC, DES3_IV)
        encrypted = cryptor.encrypt(pad(payload, 8))
        return base64.b64encode(encrypted).decode("ascii")
    except Exception as exc:
        raise SafeError("重算 QDSign 失败") from exc


def public_identity_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in (
        "NickName",
        "Nickname",
        "nickname",
        "UserName",
        "userName",
        "username",
        "DisplayName",
        "displayName",
        "name",
        "Name",
        "Uid",
        "uid",
        "UserId",
        "userId",
    ):
        value = payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            text = compact(value, 64)
            if text and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                return text
    for nest in ("data", "Data", "user", "User", "result", "Result"):
        nested = payload.get(nest)
        if isinstance(nested, dict):
            found = public_identity_from_payload(nested)
            if found:
                return found
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


def http_post(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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


def load_json(raw: bytes) -> Any:
    if not raw:
        raise SafeError("响应为空")
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except Exception:
        # 上游曾用 literal_eval；仅接受标准 JSON，拒绝任意字面量
        raise SafeError("响应不是合法 JSON")


def classify_checkin(payload: Dict[str, Any]) -> Tuple[str, str]:
    result = payload.get("Result")
    if result is None:
        result = payload.get("result")
    message = compact(
        payload.get("Message")
        or payload.get("message")
        or payload.get("msg")
        or "",
        80,
    )
    identity = public_identity_from_payload(payload)
    suffix = "；公开身份：{}".format(identity) if identity else ""

    if result == 0 or result == "0":
        return "success", "签到成功" + suffix

    lowered = message
    if any(hint in lowered for hint in ALREADY_HINTS):
        return "alreadyComplete", (message or "今日已签到") + suffix

    if result in (401, 403, "401", "403") or any(
        token in lowered for token in ("登录", "未登录", "过期", "无效", "鉴权", "授权")
    ):
        raise SafeError("签到凭据无效或会话已过期")

    detail = message or "业务结果非成功（Result={}）".format(result)
    raise SafeError("签到失败：{}".format(detail))


def do_checkin(cookie: str, catch_qdsign: str, timeout: float) -> Tuple[str, str, Dict[str, Any]]:
    parts = decode_qdsign_parts(catch_qdsign)
    qdsign = calc_qdsign(parts)
    url = SIGN_URL + "?" + SIGN_QUERY
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie,
        "QDSign": qdsign,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    status, raw = http_post(url, headers, timeout)
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    payload = load_json(raw)
    if not isinstance(payload, dict):
        raise SafeError("签到响应结构不符合预期")
    state, detail = classify_checkin(payload)
    identity = public_identity_from_payload(payload)
    return state, detail, {"identity": identity, "payload_ok": True}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    stage_no = 1

    def parameter_check():
        parse_account_line("{}|{}".format(account["qdsign"], account["cookie"]))
        return "success", "账号材料本地格式检查通过，内容不输出", None

    runner.stage(stage_no, "参数检查", parameter_check)
    stage_no += 1

    if dry_run:
        material_note = "依赖与材料可用"

        def crypto_check():
            nonlocal material_note
            try:
                load_crypto()
            except SafeError as error:
                material_note = "正式运行前请安装 pycryptodome"
                return "skipped", str(error) + "；预演继续", None
            try:
                decode_qdsign_parts(account["qdsign"])
                return "success", "pycryptodome 可用且 QDSign 可本地解密", None
            except SafeError as error:
                material_note = "正式运行前请核对有效 QDSign 抓包材料"
                return "skipped", str(error) + "；预演继续", None

        runner.stage(stage_no, "签名材料校验", crypto_check)
        stage_no += 1
        runner.skip(stage_no, "每日签到", "断网预演：不请求签到接口")
        stage_no += 1
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果；{}".format(
                runner.display(), material_note
            )
        )
        return

    def crypto_prepare():
        parts = decode_qdsign_parts(account["qdsign"])
        _ = calc_qdsign(parts)
        return "success", "本地重算 QDSign 完成，签名值不输出", None

    runner.stage(stage_no, "签名准备", crypto_prepare)
    stage_no += 1

    def checkin_stage():
        state, detail, result = do_checkin(
            account["cookie"], account["qdsign"], timeout
        )
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        return state, detail, result

    runner.stage(stage_no, "每日签到", checkin_stage)
    stage_no += 1

    if runner.stats["failure"]:
        runner.status = "failure"
    elif runner.stats["success"] == 0 and runner.stats["alreadyComplete"] > 0:
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
        "qidian_app_checkin.py",
        "candidate.py",
        "scripts/qidian_app_checkin.py",
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
    dry_setting = env("QIDIAN_DRY_RUN", "0").lower()
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
            raise SafeError("QIDIAN_DRY_RUN 配置无效，停止执行")
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
                "catalogId": CATALOG_ID,
                "applicationKey": APPLICATION_KEY,
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
