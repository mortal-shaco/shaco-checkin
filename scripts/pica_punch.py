#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 哔咔漫画每日打卡
# cron: 45 5 * * *
from __future__ import annotations
#
# 来源：muzimu217/comic-auto-signin pica_punch.py（MIT）
# https://github.com/muzimu217/comic-auto-signin
# 提交：1df1ab59d25e2afcedafc52b5e367718760c464b
# 同应用参考：OreosLab/checkinpanel ck_picacomic.py（打卡状态判定与计划）
#
# MIT License
#
# Copyright (c) muzimu217 / comic-auto-signin contributors
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
"""哔咔漫画（Picacomic）每日打卡 - 青龙维护版。

功能清点（相对上游 pica_punch.py / main.py）：
- 使用邮箱（或用户名）与密码登录 picaapi.picacomic.com，再调用 users/punch-in 打卡
- 保留官方客户端签名头（api-key / signature / time / nonce 等）与可选代理
- 移除 JSON ACCOUNTS_CONFIG 多平台编排入口、原始响应打印与失败静默返回
- 不合并禁漫天堂（JM）任务：应用、凭据与风险边界不同，应独立维护
- 增加公开身份查询（users/profile）、断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

PICA_ACCOUNTS：每个非空行一个账号，格式 邮箱或用户名|密码；仅在第一个竖线处分割，
密码中后续竖线保留。不要用 & 或 @ 分隔账号。
PICA_PROXY：可选 HTTP(S) 代理 URL，对本脚本全部业务请求生效。
PICA_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
PICA_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：45 5 * * *（对齐同应用常见哔咔打卡计划）。不打印密码、Token 或原始响应。
"""
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
        _ql_notify_identities = ('4089584217b116a7', 'scripts/pica_punch.py', 'pica_punch.py', 'pica_punch')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import hmac
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

TITLE = "哔咔漫画每日打卡"
CATALOG_ID = "4089584217b116a7"
API_URL = "https://picaapi.picacomic.com"
# 官方客户端公开签名常量（非用户凭据）
API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"
SECRET_KEY = r"~d}$Q7$eIni=V)9\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"
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
ALREADY_STATUS = {"done", "already", "punched"}
IDENTITY_KEYS = (
    "name",
    "nickname",
    "nickName",
    "display_name",
    "displayName",
    "username",
    "userName",
    "uid",
    "id",
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_timeout() -> float:
    raw = env("PICA_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("PICA_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("PICA_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_proxy() -> Optional[str]:
    raw = env("PICA_PROXY")
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SafeError("PICA_PROXY 须为 http:// 或 https:// 代理 URL")
    return raw


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" not in text:
            raise SafeError("账号行缺少分隔符；格式为 邮箱或用户名|密码")
        username, password = text.split("|", 1)
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise SafeError("邮箱/用户名或密码为空")
        if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
            raise SafeError("账号行含控制字符")
        accounts.append({"username": username, "password": password})
    return accounts


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    candidates: List[Any] = []
    if isinstance(data, dict):
        candidates.append(data)
        user = data.get("user") or data.get("userInfo") or data.get("profile")
        if isinstance(user, dict):
            candidates.append(user)
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
                if key.lower() in {"token", "password", "authorization"}:
                    continue
                if len(text) > 80 and re.fullmatch(r"[A-Za-z0-9._\-]+", text):
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                return text
    return ""


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "error", "errorMessage", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value)
    return ""


def classify_punch(payload: Any) -> Tuple[str, str]:
    if not isinstance(payload, dict):
        return "failure", "响应不是可解析的业务对象"
    message = business_message(payload)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    res = data.get("res") if isinstance(data.get("res"), dict) else {}
    status = compact(res.get("status"), 32).lower()
    if message.lower() == "success" or payload.get("code") == 200:
        if status == "ok":
            return "success", "打卡成功（业务字段已核实）"
        if status in ALREADY_STATUS or status:
            return "alreadyComplete", "今日已打卡（业务状态：{}）".format(status or "done")
        return "alreadyComplete", "今日已打卡（接口返回 success）"
    if message:
        return "failure", "打卡业务失败"
    return "failure", "打卡业务失败（缺少可核实成功字段）"


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


class PicaClient:
    def __init__(self, timeout: float, proxy: Optional[str] = None) -> None:
        self.timeout = timeout
        handlers: List[Any] = []
        if proxy:
            handlers.append(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        else:
            handlers.append(urllib.request.ProxyHandler({}))
        self.opener = urllib.request.build_opener(*handlers)

    def _signed_headers(self, path: str, method: str, token: Optional[str] = None) -> Dict[str, str]:
        nonce = "".join(random.choices(string.ascii_lowercase + string.digits, k=32))
        ts = str(int(time.time()))
        raw = (path + ts + nonce + method + API_KEY).lower()
        signature = hmac.new(
            SECRET_KEY.encode("utf-8"),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "api-key": API_KEY,
            "signature": signature,
            "time": ts,
            "nonce": nonce,
            "app-channel": "2",
            "app-version": "2.2.1.2.3.3",
            "app-uuid": "defaultUuid",
            "app-platform": "android",
            "app-build-version": "44",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/3.8.1",
            "accept": "application/vnd.picacomic.com.v1+json",
            "image-quality": "original",
        }
        if token:
            headers["authorization"] = token
        return headers

    def request_json(
        self,
        path: str,
        *,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> Tuple[int, Any]:
        url = "{}/{}".format(API_URL.rstrip("/"), path.lstrip("/"))
        headers = self._signed_headers(path, method.upper(), token=token)
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
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


def do_login(client: PicaClient, username: str, password: str) -> str:
    status, result = client.request_json(
        "auth/sign-in",
        method="POST",
        payload={"email": username, "password": password},
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效或没有访问权限")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("登录响应无法解析")
    message = business_message(result).lower()
    if message != "success" and result.get("code") != 200:
        hint = business_message(result)
        if any(word in hint for word in ("密码", "账号", "邮箱", "用户", "凭证", "登录", "invalid")):
            raise SafeError("登录业务失败（账号或密码可能无效）")
        raise SafeError("登录业务失败")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise SafeError("登录成功但未返回会话令牌")
    return token.strip()


def do_profile(client: PicaClient, token: str) -> str:
    status, result = client.request_json("users/profile", method="GET", token=token)
    if status in (401, 403):
        raise SafeError("身份查询凭据无效或会话已过期")
    if status != 200:
        raise SafeError("身份查询失败（HTTP {}）".format(status))
    if not isinstance(result, dict):
        raise SafeError("身份响应无法解析")
    message = business_message(result).lower()
    if message and message != "success" and result.get("code") not in (200, None):
        raise SafeError("身份查询业务失败")
    identity = extract_identity(result)
    if not identity:
        raise SafeError("身份查询未返回可公开账号标识")
    return identity


def do_punch(client: PicaClient, token: str) -> Tuple[str, str]:
    status, result = client.request_json("users/punch-in", method="POST", token=token)
    if status in (401, 403):
        raise SafeError("打卡凭据无效或会话已过期")
    if status != 200:
        raise SafeError("打卡请求失败（HTTP {}）".format(status))
    state, detail = classify_punch(result)
    if state == "failure":
        raise SafeError(detail)
    return state, detail


def run_account(
    runner: AccountRunner,
    username: str,
    password: str,
    timeout: float,
    proxy: Optional[str],
    dry_run: bool,
) -> None:
    def parameter_check():
        return "success", "凭据本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录获取会话", "断网预演：不请求登录接口")
        runner.skip(3, "公开身份", "断网预演：无官方身份返回")
        runner.skip(4, "提交每日打卡", "断网预演：不请求打卡接口")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实凭据或业务结果".format(runner.display())
        )
        return

    client = PicaClient(timeout, proxy=proxy)
    token_box: Dict[str, str] = {}

    def login_stage():
        token = do_login(client, username, password)
        token_box["token"] = token
        return "success", "登录成功（会话令牌不输出）", token

    runner.stage(2, "登录获取会话", login_stage)

    def identity_stage():
        try:
            identity = do_profile(client, token_box["token"])
            runner.identity = identity
            return "success", "公开账号身份：{}".format(identity), identity
        except SafeError as error:
            # 身份仅用于核对，失败不阻断打卡
            detail = "未取得公开身份（{}）；继续打卡".format(error)
            return "skipped", detail, None

    runner.stage(3, "公开身份", identity_stage)

    def punch_stage():
        state, detail = do_punch(client, token_box["token"])
        return state, detail, None

    runner.stage(4, "提交每日打卡", punch_stage)
    runner.status = (
        "alreadyComplete" if runner.stats["alreadyComplete"] else "success"
    )


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
        "pica_punch.py",
        "candidate.py",
        "scripts/pica_punch.py",
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
    dry_setting = env("PICA_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    proxy: Optional[str] = None
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("PICA_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        proxy = resolve_proxy()
        raw_accounts = env("PICA_ACCOUNTS")
        if not raw_accounts:
            raise SafeError(
                "未配置 PICA_ACCOUNTS；请按每个非空行 邮箱或用户名|密码 填写"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("PICA_ACCOUNTS 没有有效账号行")
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；代理：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                "已配置" if proxy else "未使用",
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
                    proxy,
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
