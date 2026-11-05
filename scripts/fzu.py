#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 智汇福大晚点名签到
# cron: 35 21 * * *
#
# 来源：Mahiroa/fzu-auto-checkin src/checkin.py + main.py（MIT）
# 协议逆向自智汇福大 App 晚点名 H5（yzsxg.fzu.edu.cn）。
# 不合并 Auto.js/Hamibot 无障碍脚本（需本机 App/无障碍，非青龙 HTTP 任务）。
# 不写入本地 config.yaml、不内置学号密码 SSO（login.py 未纳入本修复包）。
#
# MIT License
#
# Copyright (c) Mahiroa / fzu-auto-checkin contributors
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
"""
智汇福大（福州大学）晚点名签到 - 青龙维护版

功能清点（相对上游）：
- checkin.py：AES 加密 GET（check / clockIn / currentTimestamp）、明文 POST init、
  定位校验与打卡链路
- main.py：晚点名时段窗口、已签跳过、无计划/失败通知语义
- 未合并：Auto.js UI 自动化、YAML 回写 token、CAS/SSO 学号密码登录、假期日历模块

维护改动：
- 独立标准库 HTTP + 公开包 pycryptodome；强制超时与业务成功判定
- 凭据改为青龙环境变量；FZU_ATTN_DRY_RUN 完全断网预演
- 多账号每行一个；任一账号失败整体非零退出；青龙通知与时间轴日志

环境变量：
  FZU_ATTN_ACCOUNTS   必填：每行 token|经度|纬度|实际地点(可选)
  FZU_ATTN_TOKEN      可选兼容：单账号 token（需配合经纬度变量）
  FZU_ATTN_LONGITUDE / FZU_ATTN_LATITUDE / FZU_ATTN_ACTUAL_LOCATION
                      可选：账号行缺坐标时的默认值 / 兼容单账号坐标
  FZU_ATTN_ENFORCE_WINDOW  可选：1（默认）在 21:30-23:59 外跳过；0 关闭
  FZU_ATTN_TIMEOUT    可选：单次 HTTP 超时秒数，默认 15
  FZU_ATTN_DRY_RUN    1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

仅供学习交流与本人考勤使用；请遵守学校规定，后果自负。
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
        _ql_notify_identities = ('0a782191e8bccbe2', 'scripts/fzu.py', 'fzu.py', 'fzu')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOG_ID = "0a782191e8bccbe2"
TASK_NAME = "智汇福大晚点名签到"
SCRIPT_FILENAME = "fzu_attn_checkin.py"

BASE_URL = "https://yzsxg.fzu.edu.cn"
API_PREFIX = "/livecloud/project/fzu/attn"
AES_KEY = b"apexinfoapexinfo"  # KEY == IV（前端源码硬编码，非账号密钥）
DEFAULT_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "Chrome/120 Mobile Safari/537.36"
)

BEIJING = timezone(timedelta(hours=8), "Asia/Shanghai")
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
DONE_STATES = {"SUCCESS", "已签到"}
IDENTITY_KEYS = (
    "FName",
    "FStuName",
    "stuName",
    "studentName",
    "userName",
    "username",
    "nickName",
    "nickname",
    "displayName",
    "realName",
    "name",
)

WINDOW_START = dt_time(21, 30)
WINDOW_END = dt_time(23, 59, 59)

ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class FzuError(Exception):
    """业务层可读错误"""


@dataclass
class Account:
    index: int
    token: str
    longitude: float
    latitude: float
    actual_location: str = ""
    display_name: str = ""

    @property
    def label(self) -> str:
        if self.display_name:
            return "账号{}({})".format(self.index, self.display_name)
        return "账号{}".format(self.index)


@dataclass
class StageStats:
    total: int = 0
    success: int = 0
    alreadyComplete: int = 0
    skipped: int = 0
    failed: int = 0
    elapsedMs: int = 0


def now_beijing() -> datetime:
    return datetime.now(BEIJING)


def beijing_from_ms(ts_ms: Optional[float] = None) -> datetime:
    if ts_ms:
        return datetime.fromtimestamp(float(ts_ms) / 1000.0, BEIJING)
    return now_beijing()


def clock() -> str:
    return now_beijing().strftime("%H:%M:%S")


def stamp_full() -> str:
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy_env(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    value = str(raw).strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise FzuError("{} 取值无效，请使用 1/0/true/false".format(name))


def safe_text(value: Any, limit: int = 240) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def redact_secrets(text: str, secrets: List[str]) -> str:
    out = safe_text(text, limit=500)
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "***")
    return out


def load_aes():
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad, unpad
    except ImportError as exc:
        raise FzuError(
            "缺少公开依赖 pycryptodome，请在青龙依赖管理中执行：pip install pycryptodome"
        ) from exc
    return AES, pad, unpad


def encrypt_payload(obj: Any) -> str:
    AES, pad, _unpad = load_aes()
    data = obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":"))
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_KEY)
    return base64.b64encode(cipher.encrypt(pad(data.encode("utf-8"), AES.block_size))).decode(
        "ascii"
    )


def env_timeout() -> float:
    raw = os.getenv("FZU_ATTN_TIMEOUT", str(DEFAULT_TIMEOUT)).strip() or str(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise FzuError("FZU_ATTN_TIMEOUT 必须是数字") from exc
    if value < 3 or value > 120:
        raise FzuError("FZU_ATTN_TIMEOUT 需在 3–120 之间")
    return value


def parse_float_field(raw: str, field_name: str) -> float:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise FzuError("{} 必须是有效数字".format(field_name)) from exc


def parse_account_line(index: int, line: str, defaults: Dict[str, str]) -> Account:
    text = line.strip()
    if text.lower().startswith("token="):
        text = text[6:].strip()
    if "|" in text:
        token, rest = text.split("|", 1)
        parts = rest.split("|")
        lon_s = (parts[0] if len(parts) >= 1 else "").strip() or defaults.get("longitude", "")
        lat_s = (parts[1] if len(parts) >= 2 else "").strip() or defaults.get("latitude", "")
        loc = (parts[2] if len(parts) >= 3 else "").strip()
        if len(parts) > 3:
            loc = "|".join(p.strip() for p in parts[2:]).strip()
        if not loc:
            loc = defaults.get("actual_location", "")
    else:
        token = text
        lon_s = defaults.get("longitude", "")
        lat_s = defaults.get("latitude", "")
        loc = defaults.get("actual_location", "")

    token = token.strip()
    if not token:
        raise FzuError("账号{}缺少 token".format(index))
    if not lon_s or not lat_s:
        raise FzuError(
            "账号{}缺少经纬度：请在账号行写 token|经度|纬度[|地点]，"
            "或设置 FZU_ATTN_LONGITUDE / FZU_ATTN_LATITUDE".format(index)
        )
    return Account(
        index=index,
        token=token,
        longitude=parse_float_field(lon_s, "经度"),
        latitude=parse_float_field(lat_s, "纬度"),
        actual_location=loc.strip(),
    )


def parse_accounts() -> List[Account]:
    defaults = {
        "longitude": os.getenv("FZU_ATTN_LONGITUDE", "").strip(),
        "latitude": os.getenv("FZU_ATTN_LATITUDE", "").strip(),
        "actual_location": os.getenv("FZU_ATTN_ACTUAL_LOCATION", "").strip(),
    }
    raw = os.getenv("FZU_ATTN_ACCOUNTS", "")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    accounts: List[Account] = []
    if lines:
        for idx, line in enumerate(lines, start=1):
            accounts.append(parse_account_line(idx, line, defaults))
        return accounts

    legacy = os.getenv("FZU_ATTN_TOKEN", "").strip()
    if legacy:
        accounts.append(parse_account_line(1, legacy, defaults))
        return accounts

    raise FzuError(
        "未配置账号：请设置 FZU_ATTN_ACCOUNTS（每行 token|经度|纬度[|实际地点]），"
        "或兼容变量 FZU_ATTN_TOKEN + FZU_ATTN_LONGITUDE + FZU_ATTN_LATITUDE"
    )


def in_checkin_window(now: Optional[datetime] = None) -> bool:
    current = (now or now_beijing()).timetz().replace(tzinfo=None)
    return WINDOW_START <= current <= WINDOW_END


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in IDENTITY_KEYS:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"null", "none", "undefined"}:
            return safe_text(text, 80)
    user = payload.get("userData")
    if isinstance(user, dict):
        return extract_identity(user)
    return ""


def http_json(
    method: str,
    url: str,
    *,
    token: str,
    body: Optional[dict] = None,
    timeout: float,
    dry_run: bool,
) -> dict:
    if dry_run:
        raise FzuError("断网预演模式禁止发起网络请求")
    data = None
    headers = {
        "User-Agent": UA,
        "token": token,
        "Accept": "application/json, text/plain, */*",
    }
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise FzuError("响应过大，已中止读取")
            status = getattr(resp, "status", None) or resp.getcode()
            if status and int(status) >= 400:
                raise FzuError("HTTP {}".format(status))
    except urllib.error.HTTPError as exc:
        raise FzuError("HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise FzuError("网络错误：{}".format(safe_text(getattr(exc, "reason", exc)))) from exc
    except TimeoutError as exc:
        raise FzuError("请求超时") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise FzuError("响应不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise FzuError("响应 JSON 类型异常")
    return payload


def assert_biz_ok(path: str, body: dict) -> Any:
    if not (body.get("success") and body.get("code") == 1):
        msg = body.get("msg") or body.get("message") or "业务失败"
        raise FzuError("{} 失败：{}".format(path, safe_text(msg)))
    return body.get("data")


def enc_get(token: str, path: str, payload: dict, timeout: float, dry_run: bool) -> Any:
    # 前端 axios 会对已 encodeURIComponent 的值再编码一次（双重编码）
    param = urllib.parse.quote(urllib.parse.quote(encrypt_payload(payload), safe=""), safe="")
    url = "{}{}/{}?param={}".format(BASE_URL, API_PREFIX, path, param)
    body = http_json("GET", url, token=token, timeout=timeout, dry_run=dry_run)
    return assert_biz_ok(path, body)


def api_init(token: str, timeout: float, dry_run: bool) -> dict:
    url = "{}{}/init.action".format(BASE_URL, API_PREFIX)
    body = http_json("POST", url, token=token, body={}, timeout=timeout, dry_run=dry_run)
    data = assert_biz_ok("init", body)
    return data if isinstance(data, dict) else {}


def api_server_time(token: str, timeout: float, dry_run: bool) -> Optional[float]:
    try:
        data = enc_get(token, "currentTimestamp.action", {}, timeout, dry_run)
        if isinstance(data, dict):
            return data.get("timestamp")
    except FzuError:
        return None
    return None


def api_check(
    token: str,
    longitude: float,
    latitude: float,
    school_position: dict,
    timeout: float,
    dry_run: bool,
) -> list:
    payload = {
        "mapType": "amap",
        "longitude": longitude,
        "latitude": latitude,
        "range": json.dumps(school_position, separators=(",", ":")),
    }
    data = enc_get(token, "check.action", payload, timeout, dry_run)
    return data if isinstance(data, list) else []


def api_clock_in(
    token: str,
    *,
    campus_id: Any,
    longitude: float,
    latitude: float,
    start_time: str,
    end_time: str,
    actual_location: str,
    coll_unit: Any,
    way: Any,
    is_late: bool,
    timeout: float,
    dry_run: bool,
) -> dict:
    payload = {
        "campus": campus_id or "",
        "lon": longitude,
        "lat": latitude,
        "startTime": start_time,
        "endTime": end_time,
        "actualLocation": actual_location,
        "caIsNo": "0",
        "collUnit": coll_unit,
        "way": way,
        "isLate": 1 if is_late else 0,
    }
    data = enc_get(token, "clockIn.action", payload, timeout, dry_run)
    return data if isinstance(data, dict) else {}


def need_checkin(init_data: dict) -> bool:
    user = init_data.get("userData") or {}
    if not isinstance(user, dict):
        return True
    return user.get("FState") not in DONE_STATES


def build_polygons(init_data: dict) -> list:
    polygons = []
    for sd in init_data.get("schoolData") or []:
        if not isinstance(sd, dict):
            continue
        try:
            pos = json.loads(sd.get("FPosition") or "{}")
            polygons.extend(pos.get("range") or [])
        except Exception:
            continue
    return polygons


def compute_is_late(params: dict, ts_ms: Optional[float]) -> bool:
    now = beijing_from_ms(ts_ms)
    late_line = (params.get("FLateTime") or params.get("FEndTime") or "23:59").strip()
    try:
        parts = late_line.split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        return now.hour * 60 + now.minute > h * 60 + m
    except Exception:
        return False


def notification_allowed(no_notify: bool = False) -> bool:
    if no_notify:
        return False
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
        if item
    ]
    if not selectors:
        return False
    if "*" in selectors:
        return True
    identities = {
        CATALOG_ID.lower(),
        SCRIPT_FILENAME.lower(),
        "scripts/{}".format(SCRIPT_FILENAME).lower(),
        "candidate.py",
        "fzu",
        "fzu_attn",
        "fzu_attn_checkin.py",
    }
    for item in selectors:
        for cand in identities:
            if fnmatch.fnmatch(cand, item) or cand == item:
                return True
    return False


def notify_paths_py() -> List[Path]:
    paths: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        paths.append(Path(custom) / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    paths.append(Path(__file__).resolve().parent / "notify.py")
    return paths


def notify_paths_js() -> List[Path]:
    paths: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        paths.append(Path(custom) / "sendNotify.js")
    paths.extend(
        [
            Path("/ql/data/scripts/sendNotify.js"),
            Path("/ql/scripts/sendNotify.js"),
        ]
    )
    paths.append(Path(__file__).resolve().parent / "sendNotify.js")
    return paths


def send_qinglong_notify(title: str, content: str, dry_run: bool) -> str:
    if dry_run:
        log("{} 预演通知（不发送）：{}".format(ICONS["skipped"], safe_text(title)))
        return "dry-run-simulated"
    for path in notify_paths_py():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify_fzu", str(path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send_fn = getattr(module, "send", None)
            if callable(send_fn):
                send_fn(title, content)
                log("{} 已通过 notify.py 发送通知".format(ICONS["success"]))
                return "notify.py:{}".format(path)
        except Exception as exc:
            log("{} notify.py 发送失败：{}".format(ICONS["warning"], safe_text(exc)))
    for path in notify_paths_js():
        if not path.is_file():
            continue
        try:
            script = (
                "const n=require({});"
                "const t=process.argv[1];"
                "const c=process.argv[2];"
                "Promise.resolve(n.sendNotify?n.sendNotify(t,c):n(t,c))"
                ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
            ).format(json.dumps(str(path)))
            proc = subprocess.run(
                ["node", "-e", script, title, content],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                log("{} 已通过 sendNotify.js 发送通知".format(ICONS["success"]))
                return "sendNotify.js:{}".format(path)
            log(
                "{} sendNotify.js 发送失败：{}".format(
                    ICONS["warning"], safe_text(proc.stderr or proc.stdout)
                )
            )
        except Exception as exc:
            log("{} sendNotify.js 调用失败：{}".format(ICONS["warning"], safe_text(exc)))
    log("{} 未找到可用通知模块，已保留业务退出码".format(ICONS["warning"]))
    return "unavailable"


def build_notify_body(
    results: List[dict], dry_run: bool, final_status: str, elapsed: float
) -> str:
    lines = [
        "状态：{}".format(final_status),
        "模式：{}".format("断网预演" if dry_run else "正式运行"),
        "账号总数：{}".format(len(results)),
        "成功：{}  失败：{}".format(
            sum(1 for r in results if r.get("success")),
            sum(1 for r in results if not r.get("success")),
        ),
        "耗时：{:.2f} 秒".format(elapsed),
        "",
    ]
    for item in results:
        mark = ICONS["success"] if item.get("success") else ICONS["failure"]
        lines.append(
            "{} {}：{}".format(
                mark,
                item.get("label") or "账号",
                "成功" if item.get("success") else "失败",
            )
        )
        for err in item.get("errors") or []:
            lines.append("  - {}".format(safe_text(err)))
    return "\n".join(lines)


def run_stage(stage_no: int, stage_name: str, fn):
    started = time.time()
    log("阶段{}：{}".format(stage_no, stage_name))
    try:
        result = fn()
        elapsed_ms = int((time.time() - started) * 1000)
        log(
            "{} 阶段{}完成：{}（{} ms）".format(
                ICONS["success"], stage_no, stage_name, elapsed_ms
            )
        )
        return result, elapsed_ms, None
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        log(
            "{} 阶段{}失败：{}（{} ms）→ {}".format(
                ICONS["failure"], stage_no, stage_name, elapsed_ms, safe_text(exc)
            )
        )
        return None, elapsed_ms, safe_text(exc)


def run_account(
    account: Account,
    timeout: float,
    dry_run: bool,
    enforce_window: bool,
) -> dict:
    t0 = time.time()
    stats = StageStats()
    errors: List[str] = []
    log("-" * 48)
    log("开始处理 {}".format(account.label))

    if dry_run:
        stage_no = 1
        log("阶段{}：断网预演校验".format(stage_no))
        # 预演校验 AES 依赖是否可导入（不发起网络）
        try:
            load_aes()
            log("{} pycryptodome 可用".format(ICONS["success"]))
        except FzuError as exc:
            log("{} {}".format(ICONS["warning"], safe_text(exc)))
            log("{} 预演仍可通过配置校验；正式运行前请安装依赖".format(ICONS["warning"]))
        log(
            "{} DRY_RUN_OK：token 已配置；经度={}；纬度={}；地点={}；窗口强制={}".format(
                ICONS["success"],
                account.longitude,
                account.latitude,
                account.actual_location or "（空）",
                "是" if enforce_window else "否",
            )
        )
        stats.total = 1
        stats.skipped = 1
        log("{} 预演计划：init → check → clockIn（不访问网络）".format(ICONS["skipped"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        log(
            "账号统计：总任务 {} / 成功 {} / 已完成 {} / 跳过 {} / 失败 {} / 耗时 {} ms".format(
                stats.total,
                stats.success,
                stats.alreadyComplete,
                stats.skipped,
                stats.failed,
                stats.elapsedMs,
            )
        )
        return {
            "index": account.index,
            "label": account.label,
            "displayName": account.display_name,
            "success": True,
            "outcome": "dry-run",
            "errors": errors,
            "stats": {
                "total": stats.total,
                "success": stats.success,
                "alreadyComplete": stats.alreadyComplete,
                "skipped": stats.skipped,
                "failed": stats.failed,
                "elapsedMs": stats.elapsedMs,
            },
        }

    if enforce_window and not in_checkin_window():
        stats.total = 1
        stats.skipped = 1
        log(
            "{} 当前北京时间不在晚点名窗口（21:30-23:59），跳过打卡".format(
                ICONS["skipped"]
            )
        )
        stats.elapsedMs = int((time.time() - t0) * 1000)
        log(
            "账号统计：总任务 {} / 成功 {} / 已完成 {} / 跳过 {} / 失败 {} / 耗时 {} ms".format(
                stats.total,
                stats.success,
                stats.alreadyComplete,
                stats.skipped,
                stats.failed,
                stats.elapsedMs,
            )
        )
        return {
            "index": account.index,
            "label": account.label,
            "displayName": account.display_name,
            "success": True,
            "outcome": "skipped-window",
            "errors": errors,
            "stats": {
                "total": stats.total,
                "success": stats.success,
                "alreadyComplete": stats.alreadyComplete,
                "skipped": stats.skipped,
                "failed": stats.failed,
                "elapsedMs": stats.elapsedMs,
            },
        }

    stage_no = 1
    init_data, _, err = run_stage(
        stage_no,
        "查询今日晚点名计划",
        lambda: api_init(account.token, timeout, dry_run),
    )
    stage_no += 1
    if err or not isinstance(init_data, dict):
        stats.total = 1
        stats.failed = 1
        errors.append(err or "init 返回异常")
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)

    identity = extract_identity(init_data)
    if identity:
        account.display_name = identity
        log("{} 公开身份：{}".format(ICONS["success"], identity))

    if not need_checkin(init_data):
        stats.total = 1
        stats.alreadyComplete = 1
        log("{} 今日已签到 / 无需操作".format(ICONS["alreadyComplete"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=True, outcome="already-complete")

    if not init_data.get("schoolData"):
        stats.total = 1
        stats.skipped = 1
        log("{} 今日无考勤计划（未返回签到范围），跳过".format(ICONS["skipped"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=True, outcome="no-plan")

    user = init_data.get("userData") or {}
    params = init_data.get("paramsData") or {}
    if not isinstance(user, dict) or not isinstance(params, dict):
        stats.total = 1
        stats.failed = 1
        errors.append("init 缺少 userData/paramsData")
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)

    polygons = build_polygons(init_data)
    matched, _, err = run_stage(
        stage_no,
        "定位范围校验",
        lambda: api_check(
            account.token,
            account.longitude,
            account.latitude,
            {"range": polygons},
            timeout,
            dry_run,
        ),
    )
    stage_no += 1
    if err:
        stats.total = 1
        stats.failed = 1
        errors.append(err)
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)
    if not matched:
        stats.total = 1
        stats.failed = 1
        errors.append("定位校验未命中任何校区，请确认经纬度")
        log("{} 不在签到范围".format(ICONS["failure"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)

    ts = api_server_time(account.token, timeout, dry_run)
    is_late = compute_is_late(params, ts)
    log(
        "{} 迟到判定：{}（服务器时间校准={}）".format(
            ICONS["warning"] if is_late else ICONS["success"],
            "迟到" if is_late else "未迟到",
            "是" if ts else "否",
        )
    )

    campus_id = (matched[0] or {}).get("id") if isinstance(matched[0], dict) else None
    if not campus_id:
        campus_id = user.get("FDefaultCampus")

    _, _, err = run_stage(
        stage_no,
        "提交晚点名打卡",
        lambda: api_clock_in(
            account.token,
            campus_id=campus_id,
            longitude=account.longitude,
            latitude=account.latitude,
            start_time=(params.get("FStartTime") or "").strip(),
            end_time=(params.get("FEndTime") or "").strip(),
            actual_location=account.actual_location,
            coll_unit=user.get("FCollUnit"),
            way=user.get("FWay"),
            is_late=is_late,
            timeout=timeout,
            dry_run=dry_run,
        ),
    )
    stage_no += 1
    if err:
        stats.total = 1
        stats.failed = 1
        errors.append(err)
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)

    # 二次确认签到状态
    verify, _, verify_err = run_stage(
        stage_no,
        "复核签到状态",
        lambda: api_init(account.token, timeout, dry_run),
    )
    stats.total = 1
    if verify_err or not isinstance(verify, dict):
        # clockIn 已业务成功，复核失败记警告但仍算成功
        stats.success = 1
        log(
            "{} 打卡接口已成功，但复核失败：{}".format(
                ICONS["warning"], safe_text(verify_err or "未知")
            )
        )
        log("{} 晚点名签到成功".format(ICONS["success"]))
    elif not need_checkin(verify):
        stats.success = 1
        log("{} 晚点名签到成功（状态已确认）".format(ICONS["success"]))
    else:
        # clockIn 返回成功但状态未变：仍以接口业务码为准记成功，附警告
        stats.success = 1
        log(
            "{} 打卡接口返回成功，但状态仍显示未签到，请稍后在 App 核对".format(
                ICONS["warning"]
            )
        )

    stats.elapsedMs = int((time.time() - t0) * 1000)
    return _account_result(account, stats, errors, success=True, outcome="success")


def _account_result(
    account: Account,
    stats: StageStats,
    errors: List[str],
    *,
    success: bool,
    outcome: str = "",
) -> dict:
    log(
        "账号统计：总任务 {} / 成功 {} / 已完成 {} / 跳过 {} / 失败 {} / 耗时 {} ms".format(
            stats.total,
            stats.success,
            stats.alreadyComplete,
            stats.skipped,
            stats.failed,
            stats.elapsedMs,
        )
    )
    if not outcome:
        outcome = "success" if success else "failure"
    return {
        "index": account.index,
        "label": account.label,
        "displayName": account.display_name,
        "success": success,
        "outcome": outcome,
        "errors": errors,
        "stats": {
            "total": stats.total,
            "success": stats.success,
            "alreadyComplete": stats.alreadyComplete,
            "skipped": stats.skipped,
            "failed": stats.failed,
            "elapsedMs": stats.elapsedMs,
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    no_notify = "--no-notify" in argv
    dry_run = truthy_env("FZU_ATTN_DRY_RUN")
    started_at = now_beijing()
    task_t0 = time.time()

    print("=" * 60, flush=True)
    log("任务：{}".format(TASK_NAME))
    log("开始时间：{}".format(stamp_full()))
    log("运行模式：{}".format("断网预演" if dry_run else "正式运行"))
    print("=" * 60, flush=True)

    notify_status = "disabled"
    results: List[dict] = []
    config_error = ""
    exit_code = 0
    final_status = "SUCCESS"
    accounts: List[Account] = []
    timeout = float(DEFAULT_TIMEOUT)
    enforce_window = True

    try:
        timeout = env_timeout()
        enforce_window = env_bool("FZU_ATTN_ENFORCE_WINDOW", True)
        accounts = parse_accounts()
    except Exception as exc:
        config_error = safe_text(exc)
        log("{} 配置错误：{}".format(ICONS["failure"], config_error))
        exit_code = 2
        final_status = "CONFIG_ERROR"
        accounts = []

    log("账号数量：{}".format(len(accounts)))
    if accounts and not config_error:
        log("签到窗口强制：{}".format("开启" if enforce_window else "关闭"))
        log("HTTP 超时：{} 秒".format(timeout))

    if accounts and not config_error:
        for account in accounts:
            try:
                results.append(
                    run_account(account, timeout, dry_run, enforce_window)
                )
            except Exception as exc:
                masked = redact_secrets(safe_text(exc), [account.token])
                log("{} {} 执行异常：{}".format(ICONS["failure"], account.label, masked))
                results.append(
                    {
                        "index": account.index,
                        "label": account.label,
                        "displayName": account.display_name,
                        "success": False,
                        "outcome": "failure",
                        "errors": [masked],
                        "stats": {
                            "total": 1,
                            "success": 0,
                            "alreadyComplete": 0,
                            "skipped": 0,
                            "failed": 1,
                            "elapsedMs": 0,
                        },
                    }
                )

    account_ok = sum(1 for r in results if r["success"])
    account_fail = sum(1 for r in results if not r["success"])
    sub_success = sum(r["stats"]["success"] for r in results)
    sub_already = sum(r["stats"]["alreadyComplete"] for r in results)
    sub_skip = sum(r["stats"]["skipped"] for r in results)
    sub_fail = sum(r["stats"]["failed"] for r in results)
    elapsed = time.time() - task_t0

    if config_error:
        exit_code = 2
        final_status = "CONFIG_ERROR"
    elif dry_run and accounts and account_fail == 0:
        exit_code = 0
        final_status = "DRY_RUN_SUCCESS"
        log("{} DRY_RUN_OK 断网预演通过".format(ICONS["success"]))
    elif not accounts and not config_error:
        exit_code = 2
        final_status = "CONFIG_ERROR"
    elif account_fail == 0:
        exit_code = 0
        final_status = "SUCCESS"
    elif account_ok > 0:
        exit_code = 1
        final_status = "PARTIAL_FAILURE"
    else:
        exit_code = 1
        final_status = "FAILURE"

    print("-" * 60, flush=True)
    log("任务统计")
    log(
        "账号结果：成功 {} / 失败 {} / 总计 {}".format(
            account_ok, account_fail, len(results)
        )
    )
    log(
        "子任务结果：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            sub_success, sub_already, sub_skip, sub_fail
        )
    )
    log("总耗时：{:.2f} 秒".format(elapsed))

    if notification_allowed(no_notify=no_notify):
        if config_error:
            title = "{} {}".format(ICONS["failure"], TASK_NAME)
        elif dry_run:
            title = "{} {}（预演）".format(ICONS["skipped"], TASK_NAME)
        elif final_status == "SUCCESS":
            title = "{} {}".format(ICONS["success"], TASK_NAME)
        elif final_status == "PARTIAL_FAILURE":
            title = "{} {}".format(ICONS["warning"], TASK_NAME)
        else:
            title = "{} {}".format(ICONS["failure"], TASK_NAME)
        body = build_notify_body(results, dry_run, final_status, elapsed)
        if config_error:
            body = "配置错误：{}\n\n{}".format(config_error, body)
        notify_status = send_qinglong_notify(title, body, dry_run=dry_run)
    else:
        notify_status = "skipped-by-policy"
        log("{} 按通知策略跳过推送".format(ICONS["skipped"]))

    finished_at = now_beijing()
    log("完成时间：{}".format(finished_at.strftime("%Y-%m-%d %H:%M:%S")))
    log("最终状态：{}".format(final_status))
    log("通知状态：{}".format(notify_status))

    summary = {
        "catalogId": CATALOG_ID,
        "task": TASK_NAME,
        "status": final_status.lower().replace("_", "-"),
        "dryRun": dry_run,
        "accounts": len(results) if results else len(accounts),
        "success": account_ok,
        "failed": account_fail if not config_error else max(account_fail, 1),
        "alreadyComplete": sub_already,
        "skipped": sub_skip,
        "elapsedSec": round(elapsed, 3),
        "notify": notify_status,
        "exitCode": exit_code,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
    }
    if dry_run and exit_code == 0:
        summary["status"] = "dry-run"
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    print("=" * 60, flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
