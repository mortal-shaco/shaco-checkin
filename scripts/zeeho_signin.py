#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 极核ZEEHO每日签到
# cron: 32 8 * * *
# SPDX-License-Identifier: MIT
"""极核（ZEEHO）每日签到独立维护版。

来源：desfate/macOS_for_zeeho_auto_signin（MIT）scripts/zeeho_signin.py
流程对齐 MonicaGmm/zeeho-quanx 的 zeeho_checkin.js：
  GET baseInfo → GET /H5/signin（看 lastTime 是否今天）→ 未签则 POST /H5/signin
  → 再 GET /H5/signin 回查 lastTime（不信任 POST 的 code）。
  2026-10-11 起签到接口迁到 /cfmotoservermine/H5/，并换发 H5 appId；
  旧路径或旧 appId 会被网关拦成 30125 permit error。车辆接口仍走原生 tapi 密钥。

本维护版改为青龙可调度独立脚本：环境变量多账号、断网预演、超时与业务成功判定、
脱敏通知与时间轴日志；移除本地 config/local.json 写入、macOS 小组件与日志目录副作用，
不依赖私有仓库、菜单栏 App 或 build.sh。

ZEEHO_TOKEN：每个非空行一个账号 Token（UUID；可带 Bearer 前缀，脚本会规范化）。
也可使用兼容别名 ZEEHO_TOKENS。
ZEEHO_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
ZEEHO_STATUS_ONLY=1：只查询签到/积分/车辆状态，不发起签到 POST。
ZEEHO_FORCE=1：今日已签到时仍尝试再次 POST（默认跳过）。
ZEEHO_FETCH_VEHICLE=0：跳过车辆主页查询（默认开启）。
不打印 Token、Cookie、手机号、设备标识或原始响应；官方返回的昵称与公开 userId 原样展示。

MIT License

Copyright (c) 2026 desfate

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
        _ql_notify_identities = ('d95dd43dd4755fbe', 'scripts/zeeho_signin.py', 'zeeho_signin.py', 'zeeho_signin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import uuid
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

TITLE = "极核ZEEHO每日签到"
CATALOG_ID = "d95dd43dd4755fbe"
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

DEFAULT_BASE_URL = "https://h5.zeehoev.com"
DEFAULT_APP_ID = "Sw5F9uJi"
DEFAULT_APP_SECRET = "46870a8f678a09109468f5b0168818b91c292845"
# 2026-10-10 服务端换发的 H5 通道密钥（与原生 tapi 的 app_id 不是同一套）
DEFAULT_H5_APP_ID = "AiTXmBrm"
DEFAULT_H5_APP_SECRET = "70c2c7458ab88ca9504ad0521f170075bc91f2f7"
TAPI_VEHICLE = "https://tapi.zeehoev.com/v1.0/app/cfmotoserverapp/vehicleHomePage/"
H5_SIGNIN = "/cfmotoservermine/H5/signin"
H5_SIGNIN_INFO = "/cfmotoservermine/H5/signin/info"
OK_CODES = {"10000", "0", "200"}
RETRY = 2

UA = (
    "Mozilla/5.0 (Linux; Android 9; SM-G9500 Build/PPR1.180610.011; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/136.0.7103.125 "
    "Mobile Safari/537.36 Zeeho/3.0.4 (samsung SM-G9500 Build/9)"
)
ZEEHO_UA = (
    "MOBILE|Android|9|ZEEHO_APP|3.0.4|samsung SM-G9500|360*740|"
    "34cd9884-8171-41e8-a965-b10d042cae4f|4g|AndroidOS"
)
TOKEN_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

PY_NOTIFY_RUNNER = r"""
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
"""

JS_NOTIFY_RUNNER = r"""
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
"""


class SafeError(Exception):
    """仅允许脱敏说明进入日志。"""


def clock() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def shanghai_today() -> str:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def env_flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    raise SafeError("{} 必须为布尔开关值".format(name))


def parse_timeout() -> int:
    raw = os.environ.get("ZEEHO_TIMEOUT", "30").strip() or "30"
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("ZEEHO_TIMEOUT 必须是整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError("ZEEHO_TIMEOUT 允许范围 5..120")
    return value


def normalize_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return DEFAULT_BASE_URL
    if not value.startswith("https://"):
        raise SafeError("ZEEHO_BASE_URL 必须是 HTTPS")
    if any(c.isspace() for c in value):
        raise SafeError("ZEEHO_BASE_URL 格式错误")
    return value


def normalize_token(raw: str) -> str:
    text = (raw or "").strip().strip('"').strip("'")
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    found = TOKEN_UUID.search(text)
    if found:
        return found.group(0)
    if "token=" in text.lower():
        for part in re.split(r"[&?]", text):
            if part.lower().startswith("token="):
                return normalize_token(part.split("=", 1)[1])
    return text


def load_tokens() -> List[str]:
    raw = os.environ.get("ZEEHO_TOKEN", "").strip()
    if not raw:
        raw = os.environ.get("ZEEHO_TOKENS", "").strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise SafeError("缺少必填环境变量 ZEEHO_TOKEN（可用兼容别名 ZEEHO_TOKENS）")
    tokens: List[str] = []
    for index, line in enumerate(lines, 1):
        token = normalize_token(line)
        if not token:
            raise SafeError("账号 {} Token 为空".format(index))
        if not TOKEN_UUID.fullmatch(token):
            raise SafeError(
                "账号 {} Token 格式无效；请粘贴极核 App Authorization 中的 UUID".format(index)
            )
        tokens.append(token)
    return tokens


def cfmoto_sign(app_id: str, app_secret: str, query: str, body: str) -> Tuple[str, str]:
    nonce = str(uuid.uuid4())
    ts = str(int(time.time() * 1000))
    raw = f"{query}{body}appId={app_id}&nonce={nonce}&timestamp={ts}{app_secret}"
    digest = hashlib.md5(hashlib.sha1(raw.encode()).hexdigest().encode()).hexdigest()
    param = f"appId={app_id}&nonce={nonce}&timestamp={ts}"
    return digest, param


def is_ok(json_body: Any) -> bool:
    if not isinstance(json_body, dict):
        return False
    code = json_body.get("code", json_body.get("status"))
    return str(code) in OK_CODES


def _num(value: Any) -> Optional[float]:
    if value in (None, "", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_vehicle(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict) or not is_ok(payload):
        return None
    data = payload.get("data")
    if isinstance(data, list):
        vehicle = data[0] if data else None
    else:
        vehicle = data
    if not isinstance(vehicle, dict):
        return None
    lock = str(vehicle.get("headLockState") or "")
    charge = str(vehicle.get("chargeState") or "")
    loc = vehicle.get("location") if isinstance(vehicle.get("location"), dict) else {}
    battery = _num(vehicle.get("bmssoc"))
    range_km = _num(vehicle.get("hmiRidableMile"))
    mileage = _num(vehicle.get("totalRideMile"))
    return {
        "vehicleName": vehicle.get("vehicleName") or vehicle.get("vehicleType") or "",
        "battery": int(battery) if battery is not None else None,
        "rangeKm": int(range_km) if range_km is not None else None,
        "mileageKm": mileage,
        "lockText": "已锁" if lock == "1" else "未锁" if lock == "0" else "未知",
        "chargeText": "充电中" if charge == "1" else "未充电" if charge == "0" else "未知",
        "rideState": vehicle.get("rideState") or vehicle.get("onlineStatus") or "",
        "locationTime": str(loc.get("locationTime") or "").strip(),
    }


class Client:
    def __init__(
        self,
        base_url: str,
        app_id: str,
        app_secret: str,
        h5_app_id: str,
        h5_app_secret: str,
        timeout: int,
        insecure_ssl: bool,
    ) -> None:
        self.base_url = base_url
        self.app_id = app_id
        self.app_secret = app_secret
        self.h5_app_id = h5_app_id
        self.h5_app_secret = h5_app_secret
        self.timeout = timeout
        self.jar = CookieJar()
        ctx = ssl.create_default_context()
        if insecure_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(HTTPCookieProcessor(self.jar), HTTPSHandler(context=ctx))

    def _headers(self, token: str, query: str, body: str) -> Dict[str, str]:
        sign, param = cfmoto_sign(self.h5_app_id, self.h5_app_secret, query, body)
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "User-Agent": UA,
            "Zeeho-User-Agent": ZEEHO_UA,
            "Authorization": "Bearer {}".format(token),
            "Content-Type": "application/json;charset=UTF-8",
            "Cfmoto-X-Sign": sign,
            "Cfmoto-X-Sign-Type": "0",
            "Cfmoto-X-Param": param,
            "Referer": "{}/activity/signin".format(self.base_url),
            "Origin": self.base_url,
        }

    def request(
        self,
        method: str,
        path: str,
        token: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        query = urlencode(params or {}, doseq=True)
        body = ""
        url = self.base_url + path
        if query:
            url = "{}?{}".format(url, query)
        data = None if method in {"GET", "DELETE"} else body.encode("utf-8")
        req = Request(url, data=data, headers=self._headers(token, query, body), method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = exc.code
        except URLError as exc:
            return {"status": 0, "json": None, "raw": "", "err": str(exc.reason or exc)}
        except (TimeoutError, socket.timeout) as exc:
            return {"status": 0, "json": None, "raw": "", "err": "timeout: {}".format(exc)}
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return {"status": status, "json": parsed, "raw": raw}

    def request_retry(
        self,
        method: str,
        path: str,
        token: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        last: Dict[str, Any] = {"status": 0, "json": None, "raw": ""}
        for attempt in range(RETRY + 1):
            last = self.request(method, path, token, params)
            bad = last["status"] == 0 or last["status"] >= 500 or last["json"] is None
            if not bad:
                return last
            if attempt < RETRY:
                time.sleep(1.5)
        return last

    def warmup(self) -> None:
        url = "{}/activity/signin".format(self.base_url)
        req = Request(url, headers={"User-Agent": UA})
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                resp.read()
        except Exception:
            pass

    def tapi_get(self, url: str, token: str) -> Dict[str, Any]:
        nonce = uuid.uuid4().hex[:16] + str(int(time.time() * 1000))
        ts = str(int(time.time() * 1000))
        param = "appId={}&nonce={}&timestamp={}".format(self.app_id, nonce, ts)
        parsed = urlsplit(url)
        pre = "{}://{}{}".format(parsed.scheme, parsed.netloc, parsed.path)
        if parsed.query:
            pairs = sorted(
                (tuple(x.split("=", 1)) if "=" in x else (x, ""))
                for x in parsed.query.split("&")
            )
            pre += "?" + "&".join("{}={}".format(k, quote(v, safe="~")) for k, v in pairs)
        pre += param + self.app_secret
        sig = hashlib.md5(hashlib.sha1(pre.encode()).hexdigest().encode()).hexdigest()
        headers = {
            "appId": self.app_id,
            "nonce": nonce,
            "timestamp": ts,
            "signature": sig,
            "Cfmoto-X-Param": param,
            "Cfmoto-X-Sign": sig,
            "Cfmoto-X-Sign-Type": "0",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.9.2",
            "Accept": "*/*",
            "Authorization": "Bearer {}".format(token),
        }
        req = Request(url, data=None, headers=headers, method="GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = exc.code
        except URLError as exc:
            return {"status": 0, "json": None, "raw": "", "err": str(exc.reason or exc)}
        except (TimeoutError, socket.timeout) as exc:
            return {"status": 0, "json": None, "raw": "", "err": "timeout: {}".format(exc)}
        try:
            parsed_json = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed_json = None
        return {"status": status, "json": parsed_json, "raw": raw}


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def stage(self, number: int, name: str, operation: Callable[[], Tuple[str, str, Any]]) -> Any:
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        state, detail = "failure", "操作未完成"
        result = None
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
                    self.number,
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
        label = self.identity or "账号{}".format(self.number)
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


def notification_enabled() -> Tuple[bool, str]:
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False, "默认仅通知名单内脚本，未配置 QINGLONG_NOTIFY_SCRIPTS"
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    if not any(item.strip() for item in selectors):
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空，已禁用全部通知"
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "zeeho_signin.py",
        "candidate.py",
        "scripts/zeeho_signin.py",
        "macos-for-zeeho",
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
    paths: List[Path] = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters: List[Tuple[str, Optional[Path]]] = [("python", None)]
    adapters.extend(
        ("python", folder / "notify.py")
        for folder in paths
        if (folder / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", folder / "sendNotify.js")
            for folder in paths
            if (folder / "sendNotify.js").is_file()
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


def fetch_vehicle(client: Client, token: str) -> Optional[Dict[str, Any]]:
    last: Dict[str, Any] = {"json": None}
    for attempt in range(RETRY + 1):
        last = client.tapi_get(TAPI_VEHICLE, token)
        if last.get("json") is not None and last.get("status", 0) < 500:
            break
        if attempt < RETRY:
            time.sleep(1.5)
    return parse_vehicle(last.get("json"))


def run_account(
    runner: AccountRunner,
    token: str,
    client: Client,
    today: str,
    status_only: bool,
    force: bool,
    fetch_vehicle_flag: bool,
    dry_run: bool,
) -> None:
    if dry_run:
        def dry_stage() -> Tuple[str, str, Any]:
            return ("skipped", "断网预演：已校验 Token 格式，不发起网络请求", None)

        runner.stage(1, "配置预检", dry_stage)
        runner.skip(2, "读取资料", "断网预演跳过")
        runner.skip(3, "签到状态", "断网预演跳过")
        runner.skip(4, "执行签到", "断网预演跳过")
        runner.skip(5, "车辆概要", "断网预演跳过")
        runner.status = "dry-run"
        runner.identity = "账号{}".format(runner.number)
        return

    nick_name = ""
    user_id = ""
    continue_days: Any = None
    last_time: Any = None
    signed_today = False
    integral: Any = None
    total_integral: Any = None

    def stage_profile() -> Tuple[str, str, Any]:
        nonlocal nick_name, user_id
        r1 = client.request_retry("GET", "/cfmotoservermine/baseInfo", token)
        if r1["json"] is None:
            raise SafeError(
                "资料请求失败 HTTP {}".format(r1["status"])
                + ("（网络错误）" if r1.get("err") else "")
            )
        if r1["status"] in {401, 403} or (
            isinstance(r1["json"], dict) and r1["json"].get("error") == "invalid_token"
        ):
            raise SafeError("Token 失效，请从极核 App 抓包更新 Authorization")
        if is_ok(r1["json"]):
            data = r1["json"].get("data") or {}
            nick_name = str(data.get("nickName") or "")
            user_id = str(data.get("id") or "")
            if nick_name:
                runner.identity = nick_name
            elif user_id:
                runner.identity = "UID:{}".format(user_id)
            detail = "昵称={} userId={}".format(nick_name or "未返回", user_id or "未返回")
            return ("success", detail, data)
        raise SafeError("资料接口业务码异常")

    runner.stage(1, "读取资料", stage_profile)

    def stage_status() -> Tuple[str, str, Any]:
        nonlocal continue_days, last_time, signed_today, integral, total_integral, user_id
        r2 = client.request_retry("GET", H5_SIGNIN, token)
        if r2["status"] in {401, 403}:
            raise SafeError("Token 失效，请从极核 App 抓包更新 Authorization")
        if is_ok(r2["json"]):
            summary = r2["json"].get("data") or {}
            last_time = summary.get("lastTime") or ""
            continue_days = summary.get("continueDays")
            user_id = str(summary.get("userId") or user_id)
            if str(last_time).startswith(today):
                signed_today = True
        r_info = client.request_retry(
            "GET",
            H5_SIGNIN_INFO,
            token,
            {"month": "{}-{}".format(int(today[:4]), int(today[5:7]))},
        )
        if is_ok(r_info["json"]):
            info = r_info["json"].get("data") or {}
            try:
                integral = (
                    int(info["integral"]) if info.get("integral") not in (None, "") else None
                )
            except (TypeError, ValueError):
                integral = info.get("integral")
        r_total = client.request_retry("GET", "/cfmotoservermine/integral/totalIntegral", token)
        if is_ok(r_total["json"]):
            total = r_total["json"].get("data") or {}
            raw_total = total.get("integralTotal")
            try:
                total_integral = (
                    int(raw_total) if raw_total not in (None, "") else None
                )
            except (TypeError, ValueError):
                total_integral = raw_total
        if signed_today:
            return (
                "alreadyComplete",
                "今日已签到（连续 {} 天）；签到积分={} 总积分={}".format(
                    continue_days, integral, total_integral
                ),
                None,
            )
        return (
            "success",
            "今日未签到；签到积分={} 总积分={}".format(integral, total_integral),
            None,
        )

    runner.stage(2, "签到状态", stage_status)

    def stage_signin() -> Tuple[str, str, Any]:
        nonlocal continue_days, last_time, signed_today
        if status_only:
            if signed_today:
                return ("alreadyComplete", "仅查询：今日已签到", None)
            return ("success", "仅查询：今日未签到，未发起 POST", None)
        if signed_today and not force:
            return ("alreadyComplete", "今日已签到，跳过 POST", None)

        r3 = client.request_retry("POST", H5_SIGNIN, token)
        post_code = ""
        post_msg = ""
        if isinstance(r3["json"], dict):
            post_code = str(r3["json"].get("code", ""))
            post_msg = str(r3["json"].get("message") or r3["json"].get("msg") or "")
        if r3["json"] is None:
            raise SafeError("签到 POST 返回非 JSON（HTTP {}）".format(r3["status"]))

        r4 = client.request_retry("GET", H5_SIGNIN, token)
        last2 = ""
        if is_ok(r4["json"]):
            summary = r4["json"].get("data") or {}
            last2 = str(summary.get("lastTime") or "")
            last_time = last2
            continue_days = summary.get("continueDays")
        if last2.startswith(today):
            signed_today = True
            if post_code in OK_CODES or post_code == "":
                return (
                    "success",
                    "签到成功（连续 {} 天）".format(continue_days),
                    None,
                )
            return (
                "alreadyComplete",
                "今日已签到（连续 {} 天）".format(continue_days),
                None,
            )
        raise SafeError(
            "签到未生效：" + (post_msg or "未知") + ((" (code {})".format(post_code)) if post_code else "")
        )

    sign_result_state = "failure"
    try:
        # stage() already logs; capture state via stats delta
        before = dict(runner.stats)
        runner.stage(3, "执行签到", stage_signin)
        for key in STATES:
            if runner.stats[key] > before[key]:
                sign_result_state = key
                break
    except SafeError:
        runner.status = "failure"
        if fetch_vehicle_flag:
            runner.skip(4, "车辆概要", "签到失败，跳过车辆查询")
        else:
            runner.skip(4, "车辆概要", "未启用车辆查询")
        return

    def stage_vehicle() -> Tuple[str, str, Any]:
        if not fetch_vehicle_flag:
            return ("skipped", "未启用车辆查询", None)
        vehicle = fetch_vehicle(client, token)
        if not vehicle:
            return ("skipped", "车辆主页未取到有效数据", None)
        detail = "车辆 {} 电量{}% 续航{}km 里程{} {} {}".format(
            vehicle.get("vehicleName") or "未知",
            vehicle.get("battery"),
            vehicle.get("rangeKm"),
            vehicle.get("mileageKm"),
            vehicle.get("lockText"),
            vehicle.get("rideState"),
        )
        return ("success", detail, vehicle)

    try:
        runner.stage(4, "车辆概要", stage_vehicle)
    except SafeError:
        pass

    if sign_result_state in {"success", "alreadyComplete"}:
        runner.status = sign_result_state
    elif status_only and signed_today:
        runner.status = "alreadyComplete"
    elif status_only:
        runner.status = "success"
    else:
        runner.status = "failure"


def build_client() -> Tuple[Client, Dict[str, Any]]:
    timeout = parse_timeout()
    base_url = normalize_base_url(os.environ.get("ZEEHO_BASE_URL", DEFAULT_BASE_URL))
    app_id = os.environ.get("ZEEHO_APP_ID", DEFAULT_APP_ID).strip() or DEFAULT_APP_ID
    app_secret = (
        os.environ.get("ZEEHO_APP_SECRET", DEFAULT_APP_SECRET).strip() or DEFAULT_APP_SECRET
    )
    h5_app_id = (
        os.environ.get("ZEEHO_H5_APP_ID", DEFAULT_H5_APP_ID).strip() or DEFAULT_H5_APP_ID
    )
    h5_app_secret = (
        os.environ.get("ZEEHO_H5_APP_SECRET", DEFAULT_H5_APP_SECRET).strip()
        or DEFAULT_H5_APP_SECRET
    )
    insecure_ssl = env_flag("ZEEHO_INSECURE_SSL", "0")
    client = Client(
        base_url=base_url,
        app_id=app_id,
        app_secret=app_secret,
        h5_app_id=h5_app_id,
        h5_app_secret=h5_app_secret,
        timeout=timeout,
        insecure_ssl=insecure_ssl,
    )
    meta = {
        "timeout": timeout,
        "base_url": base_url,
        "insecure_ssl": insecure_ssl,
    }
    return client, meta


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = os.environ.get("ZEEHO_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts: List[AccountRunner] = []
    tokens: List[str] = []
    config_error: Optional[str] = None
    status_only = False
    force = False
    fetch_vehicle_flag = True
    client: Optional[Client] = None
    today = shanghai_today()

    log("========== {} ==========".format(TITLE))
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise SafeError("ZEEHO_DRY_RUN 配置无效，停止执行")
        status_only = env_flag("ZEEHO_STATUS_ONLY", "0")
        force = env_flag("ZEEHO_FORCE", "0")
        fetch_vehicle_flag = env_flag("ZEEHO_FETCH_VEHICLE", "1")
        tokens = load_tokens()
        if not dry_run:
            client, meta = build_client()
            log(
                "运行参数：base_url={} timeout={}s insecure_ssl={} status_only={} force={} fetch_vehicle={}".format(
                    meta["base_url"],
                    meta["timeout"],
                    meta["insecure_ssl"],
                    status_only,
                    force,
                    fetch_vehicle_flag,
                )
            )
            client.warmup()
        else:
            parse_timeout()
            normalize_base_url(os.environ.get("ZEEHO_BASE_URL", DEFAULT_BASE_URL))
    except SafeError as error:
        config_error = str(error)
        log(
            "开始时间：{}；运行模式：{}；账号数：0".format(
                started_at, "断网预演" if dry_run else "真实执行"
            )
        )
        log("阶段 0 参数配置：❌ " + config_error)
    else:
        mode_label = "断网预演" if dry_run else ("仅查询" if status_only else "真实签到")
        log(
            "开始时间：{}；运行模式：{}；账号数：{}；日期：{}".format(
                started_at, mode_label, len(tokens), today
            )
        )
        for number, token in enumerate(tokens, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                assert client is not None or dry_run
                run_account(
                    runner,
                    token,
                    client if client is not None else Client(
                        DEFAULT_BASE_URL,
                        DEFAULT_APP_ID,
                        DEFAULT_APP_SECRET,
                        DEFAULT_H5_APP_ID,
                        DEFAULT_H5_APP_SECRET,
                        30,
                        False,
                    ),
                    today,
                    status_only,
                    force,
                    fetch_vehicle_flag,
                    dry_run,
                )
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(tokens):
                time.sleep(1)

    counts = {
        "success": sum(item.status == "success" for item in accounts),
        "alreadyComplete": sum(item.status == "alreadyComplete" for item in accounts),
        "failure": sum(item.status == "failure" for item in accounts),
        "dry-run": sum(item.status == "dry-run" for item in accounts),
    }
    account_total = len(tokens) if not config_error else 0
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    if config_error and not tokens:
        failed = max(failed, 1)
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and (succeeded or counts["dry-run"])
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status,
        account_total if not config_error else 0,
        succeeded,
        failed,
        counts["dry-run"],
        "是" if config_error else "否",
    )
    log("阶段 99 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log(
        "阶段 99 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started)
    )
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total if not config_error else 0,
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
    if dry_run and not config_error:
        log("断网预演通过")
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total if not config_error else 0,
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
