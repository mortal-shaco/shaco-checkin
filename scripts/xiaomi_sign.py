#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 小米VIP会员签到
# cron: 29 8 * * *
#
# 来源：James081105/xiaomiautosign xiaomi_sign.py（MIT）
# https://github.com/James081105/xiaomiautosign
# 提交：708955c2b40503ee7b38c1d8a1ba0e0690502866
# 原创标注：github：James081105原创 bilibili：James-520 公众号：James吖
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) James081105 / xiaomiautosign contributors
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
"""小米 / MIUI VIP 会员每日签到（checkinV2）- 青龙维护版。

功能清点（相对上游 xiaomi_sign.py）：
- POST https://api.vip.miui.com/mtop/planet/vip/user/checkinV2 完成 VIP 会员签到
- 从 Cookie 提取 miui_vip_ph；签到表单 token 由用户自行提供（已移除上游硬编码凭据与真实 Cookie）
- 移除原始响应打印、无超时请求与设备指纹样例；改用标准库 HTTPS
- 增加逐行多账号、XIAOMI_VIP_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY
- 与「小米社区微信小程序签到」接口/凭据路径不同，保持独立任务
- 无发帖/评论/分享类公开内容动作，不调用一言

XIAOMI_VIP_COOKIE：每个非空行一个账号，格式为 cookie|token。
仅在第一个竖线处分割，竖线后的 token 原文保留；Cookie 内分号键值对原样保留。
Cookie 须含 miui_vip_ph；token 为签到请求表单字段（抓包获取，勿使用他人样例）。
兼容别名 MIUI_VIP_COOKIE、XIAOMI_COOKIE（仅当规范变量为空时生效）。
XIAOMI_VIP_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..120。
XIAOMI_VIP_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：10 8 * * *。不打印 Cookie、Token、会话值、设备标识或原始响应。
官方响应中的昵称/用户名/公开 UID 会直接展示以便核对账号。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('201d530a0f4973ba', 'scripts/xiaomi_sign.py', 'xiaomi_sign.py', 'xiaomi_sign')
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
import random
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

TITLE = "小米VIP会员签到"
CATALOG_ID = "201d530a0f4973ba"
CHECKIN_PATH = "/mtop/planet/vip/user/checkinV2"
API_HOST = "api.vip.miui.com"
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
ALREADY_HINTS = (
    "已签到",
    "已经签到",
    "重复签到",
    "今日已签",
    "签到过",
    "already checked",
    "already signed",
)
IDENTITY_KEYS = (
    "nickname",
    "nickName",
    "display_name",
    "displayName",
    "username",
    "userName",
    "user_name",
    "name",
    "nick",
    "uid",
    "userId",
    "user_id",
)
COOKIE_ENV_CANDIDATES = (
    "XIAOMI_VIP_COOKIE",
    "MIUI_VIP_COOKIE",
    "XIAOMI_COOKIE",
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def parse_cookie_map(cookie: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields


def extract_miui_vip_ph(cookie: str) -> Optional[str]:
    match = re.search(r"(?:^|;\s*)miui_vip_ph=([^;]+)", cookie)
    if match:
        return match.group(1).strip() or None
    return None


def public_cookie_identity(cookie: str) -> str:
    fields = parse_cookie_map(cookie)
    for key in ("userId", "cUserId"):
        value = fields.get(key, "").strip()
        if not value:
            continue
        if re.search(r"[\x00-\x1f\x7f]", value):
            continue
        if re.fullmatch(r"1[3-9]\d{9}", value):
            continue
        if len(value) > 64:
            continue
        return "{}={}".format(key, value)
    return ""


def looks_like_secret(text: str) -> bool:
    lowered = text.lower()
    return any(
        tip in lowered
        for tip in (
            "servicetoken",
            "miui_vip_ph",
            "miui_vip_slh",
            "cookie",
            "token",
            "authorization",
            "session",
        )
    )


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates: List[Any] = [payload]
    entity = payload.get("entity")
    if isinstance(entity, dict):
        candidates.append(entity)
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data)
    for block in candidates:
        for key in IDENTITY_KEYS:
            value = block.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if not text or looks_like_secret(text):
                continue
            if re.search(r"[\x00-\x1f\x7f]", text):
                continue
            if key not in ("uid", "userId", "user_id") and re.fullmatch(
                r"(?:\+?86[- ]?)?1[3-9]\d{9}", text
            ):
                continue
            if len(text) > 64:
                continue
            return text
    return ""


def resolve_timeout() -> float:
    raw = env("XIAOMI_VIP_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("XIAOMI_VIP_TIMEOUT 必须是数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("XIAOMI_VIP_TIMEOUT 超出允许范围 5..120")
    return value


def load_accounts() -> List[Dict[str, str]]:
    raw = ""
    source = ""
    for name in COOKIE_ENV_CANDIDATES:
        value = os.environ.get(name)
        if value is None:
            continue
        if value.strip():
            raw = value
            source = name
            break
        if name == "XIAOMI_VIP_COOKIE":
            # 规范变量存在但为空时，仍允许回退别名
            continue
    if not raw.strip():
        raise SafeError(
            "缺少凭据：请设置 XIAOMI_VIP_COOKIE（每行 cookie|token），"
            "兼容别名 MIUI_VIP_COOKIE / XIAOMI_COOKIE"
        )
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            raise SafeError(
                "账号 {} 格式无效：须为 cookie|token，仅在第一个竖线处分割".format(line_no)
            )
        cookie, token = text.split("|", 1)
        cookie = cookie.strip()
        token = token.strip()
        if not cookie or not token:
            raise SafeError("账号 {} 的 Cookie 或签到 token 为空".format(line_no))
        if re.search(r"[\x00-\x1f\x7f]", cookie) or re.search(r"[\x00-\x1f\x7f]", token):
            raise SafeError("账号 {} 凭据含非法控制字符".format(line_no))
        ph = extract_miui_vip_ph(cookie)
        if not ph:
            raise SafeError(
                "账号 {} Cookie 缺少 miui_vip_ph，请重新抓取完整请求头".format(line_no)
            )
        if len(token) < 8:
            raise SafeError("账号 {} 签到 token 过短，疑似无效".format(line_no))
        accounts.append(
            {
                "cookie": cookie,
                "token": token,
                "miui_vip_ph": ph,
                "identity_hint": public_cookie_identity(cookie),
                "source": source,
            }
        )
    if not accounts:
        raise SafeError("XIAOMI_VIP_COOKIE 未包含任何非空账号行")
    return accounts


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


def build_checkin_url(miui_vip_ph: str) -> str:
    query = urllib.parse.urlencode(
        {
            "ref": "vipAccountShortcut",
            "pathname": "/mio/checkIn",
            "version": "dev.250321",
            "miui_version": "V14.0.27.0.TMRCNXM",
            "android_version": "13",
            "oaid": "",
            "device": "generic",
            "restrict_imei": "",
            "miui_big_version": "V130",
            "model": "Redmi Note 12 Turbo",
            "androidVersion": "13",
            "miuiBigVersion": "V130",
            "miui_vip_ph": miui_vip_ph,
        }
    )
    return "https://{}{}?{}".format(API_HOST, CHECKIN_PATH, query)


def classify_checkin(http_status: int, payload: Any) -> Tuple[str, str]:
    if http_status == 401 or http_status == 403:
        raise SafeError("登录凭据可能失效（HTTP {}）".format(http_status))
    if http_status < 200 or http_status >= 300:
        raise SafeError("HTTP 状态异常：{}".format(http_status))
    if not isinstance(payload, dict):
        raise SafeError("响应不是对象 JSON")
    status = payload.get("status")
    message = ""
    for key in ("message", "msg", "errorMsg", "error_msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            message = value.strip()
            break
    message_compact = compact(message, 80)
    if status == 200:
        detail = "签到成功"
        if message_compact and not looks_like_secret(message_compact):
            detail = "{}（{}）".format(detail, message_compact)
        return "success", detail
    joined = message.lower()
    if any(hint.lower() in joined for hint in ALREADY_HINTS):
        detail = "今日已签到"
        if message_compact and not looks_like_secret(message_compact):
            detail = "{}（{}）".format(detail, message_compact)
        return "alreadyComplete", detail
    code = "不可识别"
    if isinstance(status, int) and abs(status) <= 999999:
        code = str(status)
    elif isinstance(status, str) and re.fullmatch(r"-?\d{1,6}", status):
        code = status
    category = "未知业务错误"
    if re.search(r"未登录|登录失效|登录过期|重新登录|unauthorized|token", message, re.I):
        category = "登录凭据可能失效"
    elif re.search(r"参数|parameter|argument", message, re.I):
        category = "请求参数可能无效"
    elif re.search(r"频繁|限流|rate.?limit|too many", message, re.I):
        category = "请求频率受限"
    elif re.search(r"维护|系统繁忙|稍后再试", message, re.I):
        category = "服务暂时不可用"
    raise SafeError(
        "业务状态未确认成功：status={}；分类={}".format(code, category)
    )


def http_post_form(
    url: str, headers: Dict[str, str], form: Dict[str, str], timeout: float
) -> Tuple[int, Any]:
    body = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
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
    if not raw:
        return status, None
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SafeError("响应不是合法 UTF-8") from exc
    try:
        return status, json.loads(text)
    except ValueError as exc:
        raise SafeError("响应不是合法 JSON") from exc


def do_checkin(account: Dict[str, str], timeout: float) -> Tuple[str, str, Any]:
    url = build_checkin_url(account["miui_vip_ph"])
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; 23049RAD8C Build/TKQ1.221114.001; wv) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/108.0.5359.128 "
            "Mobile Safari/537.36 XiaoMi/HybridView/ app/vipaccount/dev.250321"
        ),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://web.vip.miui.com",
        "X-Requested-With": "com.xiaomi.vipaccount",
        "Referer": "https://web.vip.miui.com/",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": account["cookie"],
    }
    form = {
        "token": account["token"],
        "miui_vip_ph": account["miui_vip_ph"],
    }
    http_status, payload = http_post_form(url, headers, form, timeout)
    state, detail = classify_checkin(http_status, payload)
    identity = extract_identity(payload)
    if identity:
        detail = "{}；公开身份：{}".format(detail, identity)
    return state, detail, {"payload": payload, "identity": identity}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> None:
    if account.get("identity_hint"):
        runner.identity = account["identity_hint"]

    def parameter_check():
        hint = account.get("identity_hint") or ""
        if hint:
            runner.identity = hint
            return (
                "success",
                "本地格式检查通过；Cookie 公开标识：{}".format(hint),
                None,
            )
        return "success", "本地格式检查通过（含 miui_vip_ph 与签到 token）", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "提交 VIP 签到", "断网预演：不请求 checkinV2 接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    def checkin_stage():
        state, detail, result = do_checkin(account, timeout)
        identity = ""
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
        if identity:
            runner.identity = identity
        elif account.get("identity_hint"):
            runner.identity = account["identity_hint"]
        return state, detail, result

    runner.stage(2, "提交 VIP 签到", checkin_stage)
    if runner.stats["failure"]:
        runner.status = "failure"
    elif runner.stats["alreadyComplete"]:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"


PY_NOTIFY_RUNNER = r'''
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
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
        "xiaomi_vip_sign.py",
        "xiaomi_sign.py",
        "candidate.py",
        "scripts/xiaomi_vip_sign.py",
        "james081105_xiaomiautosign",
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
    dry_setting = env("XIAOMI_VIP_DRY_RUN", "0").lower()
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
    log("上游致谢：James081105 / bilibili：James-520 / 公众号：James吖")

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("XIAOMI_VIP_DRY_RUN 配置无效，停止执行")
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
                run_account(runner, item, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                delay = random.uniform(1.5, 3.5)
                log("账号间隔：等待 {:.1f} 秒后处理下一账号".format(delay))
                time.sleep(delay)

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
