#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 龙湖天街签到
# cron: 5 8 * * *
#
# 来源：ken861222/longhu-checkin（MIT），app/longhu.py
# 编排参考：同仓库 app/runner.py 流程（续期→小程序签到→APP 签到→资料）；
# 凭据说明参考 app/parser.py；不合并 FastAPI Web、SQLite、Docker 入口。
#
# MIT License
#
# Copyright (c) 2026 ken861222
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
龙湖天街（珑珠）每日签到 - 青龙维护版

功能清点（相对上游 app/longhu.py + runner 编排）：
- token 滚动续期（token2key + key2token，有效期重置约 30 天）
- 小程序「日日签」每日签到（含日历复核 / 已签判定）
- APP「签到奖励翻倍」入口（auto 真签 / manual 只查状态 / off 跳过）
- 拉取昵称、成长值、等级、珑珠余额（公开身份字段原样展示）
- 多账号独立处理；检测同批账号共用设备指纹并暂停冲突账号签到

维护改动：
- 去掉 Web/SQLite/Bark webhook 依赖；改为青龙 notify 与时间轴日志
- 不再调用 udid/c1 现造设备指纹（会被风控拒绝）；必须使用 App 内真实指纹
- 标准库 HTTPS，强制超时与业务码判定；LONGHU_DRY_RUN 完全断网预演
- 账号变量 LONGHU_ACCOUNTS（每行 token|dx_token），失败非零退出

环境变量：
  LONGHU_ACCOUNTS     必填：每行一个账号，token|dx_token（仅按首个 | 分割）
  LONGHU_APP_CHECKIN  可选：auto / manual / off，默认 auto
  LONGHU_BU_CODE      可选：默认 C20400
  LONGHU_CHANNEL      可选：默认 C2
  LONGHU_UA           可选：自定义 User-Agent
  LONGHU_TIMEOUT      可选：单次 HTTP 超时秒数，默认 20
  LONGHU_DRY_RUN      1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

仅供学习交流；请遵守龙湖会员服务条款，自行承担使用风险。
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
        _ql_notify_identities = ('b4130175dc0a855e', 'scripts/longhu.py', 'longhu.py', 'longhu')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# 元数据与常量
# ============================================================

CATALOG_ID = "b4130175dc0a855e"
TASK_NAME = "龙湖天街签到"
SCRIPT_FILENAME = "longhu_checkin.py"

BASE = "https://gw2c-hw-open.longfor.com"
SIGN_SECRET_MICRO_APP = "Q74eKtH5LePYfSjIiflUbCL2gxjTa7rF"
API_KEY_MAIN = "c06753f1-3e68-437d-b592-b94656ea5517"
API_KEY_MEMBER = "98717e7a-a039-46af-8143-be7558a089c0"
API_KEY_WALLET = "f4a2290e-c382-45b7-949c-3253d07e9b5b"

ACTIVITY_NO = "11111111111686241863606037740000"
APP_ACTIVITY_NO = "11111111111736501868255956070000"
ACTIVITIES = (
    {"key": "mini", "name": "小程序", "activity_no": ACTIVITY_NO},
    {"key": "app", "name": "APP", "activity_no": APP_ACTIVITY_NO},
)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) "
    "UnifiedPCMacWechat(0xf2641d55) XWEB/25561"
)
DEFAULT_BU_CODE = "C20400"
DEFAULT_CHANNEL = "C2"
DEFAULT_TIMEOUT = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
APP_MODES = ("auto", "manual", "off")

CODE_HINT = {
    "801810": "风控拒绝：设备指纹不被认可（换成 App 内的真实指纹）",
    "801811": "需要滑块验证（顶象 dx-captcha）",
    "801812": "风控拒绝：设备指纹不被认可（同上）",
    "8040012": "风控拦截：设备指纹不被认可",
    "8040016": "风控拦截：设备指纹不被认可",
}
RISK_CODES = {"801810", "801811", "801812", "8040012", "8040016"}

BEIJING = timezone(timedelta(hours=8))
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class LonghuError(Exception):
    """业务层可读错误"""


@dataclass
class Account:
    index: int
    token: str
    dx_token: str = ""
    bu_code: str = DEFAULT_BU_CODE
    channel: str = DEFAULT_CHANNEL
    user_agent: str = DEFAULT_UA
    nickname: str = ""
    level_name: str = ""

    @property
    def label(self) -> str:
        if self.nickname:
            return "账号{}({})".format(self.index, self.nickname)
        return "账号{}".format(self.index)


# ============================================================
# 日志与工具
# ============================================================

def now_beijing() -> datetime:
    return datetime.now(BEIJING)


def clock() -> str:
    return now_beijing().strftime("%H:%M:%S")


def stamp_full() -> str:
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy_env(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def safe_text(value: Any, limit: int = 240) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def env_timeout() -> float:
    raw = os.getenv("LONGHU_TIMEOUT", "").strip()
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("LONGHU_TIMEOUT 必须是数字") from exc
    if value < 3 or value > 120:
        raise ValueError("LONGHU_TIMEOUT 须在 3–120 之间")
    return value


def redact_secrets(text: str, secrets: List[str]) -> str:
    out = text
    for secret in secrets:
        if secret and len(secret) >= 8:
            out = out.replace(secret, "***")
    return out


# ============================================================
# 账号解析
# ============================================================

def parse_accounts() -> List[Account]:
    raw = os.getenv("LONGHU_ACCOUNTS", "")
    if not raw.strip():
        raise ValueError(
            "缺少必填凭据 LONGHU_ACCOUNTS："
            "每行一个账号，格式 token|dx_token（仅按首个竖线分割）"
        )

    bu_code = os.getenv("LONGHU_BU_CODE", DEFAULT_BU_CODE).strip() or DEFAULT_BU_CODE
    channel = os.getenv("LONGHU_CHANNEL", DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL
    user_agent = os.getenv("LONGHU_UA", "").strip() or DEFAULT_UA

    accounts: List[Account] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "|" in text:
            token, dx_token = text.split("|", 1)
        else:
            token, dx_token = text, ""
        token = token.strip()
        dx_token = dx_token.strip()
        if not token:
            raise ValueError("第 {} 行缺少 token".format(line_no))
        if len(token) < 16:
            raise ValueError("第 {} 行 token 长度异常（通常 ≥16）".format(line_no))
        if not re.fullmatch(r"[0-9a-zA-Z]+", token):
            raise ValueError("第 {} 行 token 只能包含字母和数字".format(line_no))
        if dx_token and (" " in dx_token or len(dx_token) < 20):
            raise ValueError(
                "第 {} 行设备指纹格式异常：应类似 App 内顶象 token，长度≥20 且无空格".format(
                    line_no
                )
            )
        accounts.append(
            Account(
                index=len(accounts) + 1,
                token=token,
                dx_token=dx_token,
                bu_code=bu_code,
                channel=channel,
                user_agent=user_agent,
            )
        )

    if not accounts:
        raise ValueError("LONGHU_ACCOUNTS 未解析到有效账号行")
    return accounts


def app_checkin_mode() -> str:
    mode = (os.getenv("LONGHU_APP_CHECKIN", "auto") or "auto").strip().lower()
    if mode not in APP_MODES:
        raise ValueError("LONGHU_APP_CHECKIN 只能是 auto / manual / off")
    return mode


def dx_conflicts(accounts: List[Account]) -> Dict[int, List[int]]:
    """同一设备指纹被多个账号共用时，较小序号归属，其余冲突。"""
    usage: Dict[str, List[Account]] = {}
    for acc in accounts:
        dx = (acc.dx_token or "").strip()
        if not dx:
            continue
        usage.setdefault(dx, []).append(acc)
    conflict: Dict[int, List[int]] = {}
    for group in usage.values():
        if len(group) < 2:
            continue
        owner = min(group, key=lambda a: a.index)
        for acc in group:
            if acc.index == owner.index:
                continue
            conflict[acc.index] = [owner.index]
    return conflict


# ============================================================
# 通知
# ============================================================

def _split_selectors(raw: str) -> List[str]:
    return [p for p in re.split(r"[\s,;]+", raw.strip()) if p]


def notification_allowed(no_notify: bool = False) -> bool:
    if no_notify:
        return False
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selectors_raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selectors_raw is None:
        return True
    if not selectors_raw.strip():
        return False
    selectors = _split_selectors(selectors_raw)
    if "*" in selectors:
        return True
    candidates = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        Path(__file__).name,
        "scripts/{}".format(SCRIPT_FILENAME),
        "checkin/{}".format(SCRIPT_FILENAME),
        "longhu.py",
        "longhu",
    }
    for item in selectors:
        for cand in candidates:
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
            spec = importlib.util.spec_from_file_location("ql_notify_longhu", str(path))
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


# ============================================================
# HTTP（标准库，不依赖 requests）
# ============================================================

def _decode_body(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace") if raw else ""
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    try:
        data = json.loads(base64.b64decode(text).decode("utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"code": "parse_error", "message": text[:200]}


def http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        raise RuntimeError("dry-run 禁止发起网络请求")
    clean = {k: v for k, v in (headers or {}).items() if v not in (None, "")}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        clean.setdefault("Content-Type", "application/json;charset=UTF-8")
    request = urllib.request.Request(url, data=data, headers=clean, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise LonghuError("响应过大，已中止解析")
            return _decode_body(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES) if hasattr(exc, "read") else b""
        payload = _decode_body(raw)
        if payload and payload.get("code") not in (None, "parse_error"):
            return payload
        raise LonghuError("HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise LonghuError("网络请求失败：{}".format(safe_text(exc.reason))) from exc


def sign_headers(body: Optional[dict] = None) -> Dict[str, str]:
    parts = []
    for key in sorted((body or {}).keys()):
        value = body[key]
        if isinstance(value, (dict, list)):
            continue
        text = str(value)
        if text.strip() and text != "null":
            parts.append("{}={}".format(key, text))
    joined = "|".join(parts)
    ts = str(int(time.time() * 1000))
    raw = (joined + "&" if joined else "") + ts + "&" + SIGN_SECRET_MICRO_APP
    return {
        "X-LONGZHU-TimeStamp": ts,
        "X-Client-Type": "microApp",
        "X-LONGZHU-Sign": hashlib.md5(raw.encode("utf-8")).hexdigest(),
    }


def task_headers(account: Account) -> Dict[str, str]:
    headers = {
        "User-Agent": account.user_agent or DEFAULT_UA,
        "Origin": "https://longzhu.longfor.com",
        "Referer": "https://longzhu.longfor.com/",
        "X-LF-DXRisk-Source": "5",
        "X-LF-Bu-Code": account.bu_code or DEFAULT_BU_CODE,
        "X-GAIA-API-KEY": API_KEY_MAIN,
        "X-LF-UserToken": account.token,
        "X-LF-Channel": account.channel or DEFAULT_CHANNEL,
        "X-LF-DXRisk-Captcha-Token": "undefined",
        "token": account.token,
        "Content-Type": "application/json;charset=UTF-8",
    }
    fingerprint = (account.dx_token or "").strip()
    if fingerprint:
        headers["X-LF-DXRisk-Token"] = fingerprint
    return headers


# ============================================================
# 业务接口
# ============================================================

def refresh_token(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str]:
    if not account.token:
        return False, "缺少 token"
    headers = {
        "lmToken": account.token,
        "X-LF-Bucode": account.bu_code or DEFAULT_BU_CODE,
        "X-LF-Api-Version": "v2_6_0",
        "X-LF-Channel": account.channel or DEFAULT_CHANNEL,
        "X-LF-App-Version": "2.6.0",
        "Content-Type": "application/json",
        "User-Agent": account.user_agent or DEFAULT_UA,
        "Origin": "https://longzhu.longfor.com",
        "Referer": "https://longzhu.longfor.com/",
    }
    headers.update(sign_headers({}))
    res = http_json(
        "POST",
        "{}/supera/mine/v2_6_0/token/token2key".format(BASE),
        headers=headers,
        body={},
        timeout=timeout,
        dry_run=dry_run,
    )
    key = (res.get("data") or {}).get("key")
    if not key:
        return False, res.get("message") or "token2key 未返回 key（token 可能已失效）"

    wallet_headers = {
        "X-Gaia-Api-Key": API_KEY_WALLET,
        "systype": "WALLET",
        "Content-Type": "application/json",
        "User-Agent": account.user_agent or DEFAULT_UA,
        "Origin": "https://longball.longhu.net",
        "Referer": "https://longball.longhu.net/",
    }
    res2 = http_json(
        "POST",
        "{}/lmember-lpns-api-prod/api/lpns/auth/v1/key2token".format(BASE),
        headers=wallet_headers,
        body={
            "key": key,
            "buCode": account.bu_code or DEFAULT_BU_CODE,
            "channel": account.channel or DEFAULT_CHANNEL,
        },
        timeout=timeout,
        dry_run=dry_run,
    )
    data = res2.get("data") or {}
    if res2.get("code") == "0000" and data.get("token"):
        return True, str(data["token"])
    return False, res2.get("message") or "key2token 未返回 token"


def sign_state(
    account: Account,
    activity_no: str,
    timeout: float,
    dry_run: bool,
) -> Optional[bool]:
    try:
        res = http_json(
            "POST",
            "{}/lmarketing-task-api-mvc-prod/openapi/task/v1/signature/page-info".format(BASE),
            headers=task_headers(account),
            body={"activity_no": activity_no},
            timeout=timeout,
            dry_run=dry_run,
        )
    except LonghuError:
        return None
    if res.get("code") != "0000":
        return None
    data = res.get("data") or {}
    today = datetime.now()
    raw = data.get("current_date_time")
    if raw:
        try:
            today = datetime.fromtimestamp(int(raw) / 1000)
        except (TypeError, ValueError):
            pass
    for item in data.get("seven_days_signs") or []:
        try:
            day = (
                int(item.get("sign_year")),
                int(item.get("sign_month")),
                int(item.get("sign_day")),
            )
        except (TypeError, ValueError):
            continue
        if day == (today.year, today.month, today.day):
            return int(item.get("sign_status") or 0) == 20
    return None


def checkin(
    account: Account,
    activity_no: str,
    label: str,
    timeout: float,
    dry_run: bool,
) -> Tuple[str, str]:
    tag = label or ""
    before = sign_state(account, activity_no, timeout, dry_run)
    if before is True:
        return "already", "{}今日已签到".format(tag)

    try:
        res = http_json(
            "POST",
            "{}/lmarketing-task-api-mvc-prod/openapi/task/v1/signature/clock".format(BASE),
            headers=task_headers(account),
            body={"activity_no": activity_no},
            timeout=timeout,
            dry_run=dry_run,
        )
    except LonghuError as exc:
        return "fail", "{}签到请求失败：{}".format(tag, exc)

    code = str(res.get("code") or "")
    data = res.get("data") or {}
    message = res.get("message") or ""

    if code == "0000":
        if data.get("is_popup") == 1:
            reward = 0
            for item in data.get("reward_info") or []:
                reward += int(item.get("reward_num") or 0)
            return "ok", "{}签到成功，获得 {} 积分".format(tag, reward)
        after = sign_state(account, activity_no, timeout, dry_run)
        if after is False:
            return "fail", "{}签到接口返回成功但日历仍显示未签，请稍后重试".format(tag)
        return "already", "{}今日已签到".format(tag)

    if "未登录" in message or "登录已过期" in message or code == "801001":
        return "fail", "鉴权失败：token 已失效，需要重新导入"

    if sign_state(account, activity_no, timeout, dry_run) is True:
        return "ok", "{}签到成功（接口返回 {}，已按日历确认）".format(tag, code)

    hint = CODE_HINT.get(code, "")
    detail = "{}（code={}{}）".format(
        message or "未知错误",
        code or "无",
        "，" + hint if hint else "",
    )
    if code in RISK_CODES:
        return "risk", "{}签到失败：{}".format(tag, detail)
    return "fail", "{}签到失败：{}".format(tag, detail)


def fetch_profile(account: Account, timeout: float, dry_run: bool) -> dict:
    headers = {
        "User-Agent": account.user_agent or DEFAULT_UA,
        "lmToken": account.token,
        "X-Gaia-Api-Key": API_KEY_MEMBER,
        "X-LF-Bucode": account.bu_code or DEFAULT_BU_CODE,
        "X-LF-Channel": account.channel or DEFAULT_CHANNEL,
        "X-LF-Api-Version": "v2_6_0",
        "Content-Type": "application/json",
    }
    res = http_json(
        "GET",
        "{}/supera/member/api/bff/pages/v2_6_0/v1/user-info".format(BASE),
        headers=headers,
        timeout=timeout,
        dry_run=dry_run,
    )
    if res.get("code") != "0000":
        raise LonghuError(res.get("message") or "用户信息查询失败")
    data = res.get("data") or {}
    profile = {
        "growth_value": int(data.get("growthValue") or 0),
        "level_name": data.get("levelName") or "",
        "nickname": data.get("nickName") or data.get("nickname") or "",
    }
    try:
        res2 = http_json(
            "GET",
            "{}/supera/member/api/bff/pages/v2_6_0/v2/user-lz-balance".format(BASE),
            headers=headers,
            timeout=timeout,
            dry_run=dry_run,
        )
        if res2.get("code") == "0000":
            bdata = res2.get("data") or {}
            profile["balance"] = float(bdata.get("balance") or 0)
            profile["expiring_lz"] = float(bdata.get("expiringLz") or 0)
    except LonghuError:
        pass
    return profile


def run_app_entry(
    account: Account,
    activity_no: str,
    mode: str,
    timeout: float,
    dry_run: bool,
) -> Tuple[str, str]:
    label = "APP "
    if mode == "off":
        return "skipped", "{}已关闭".format(label)
    if not (account.dx_token or "").strip():
        return (
            "todo",
            "{}未配置设备指纹，跳过（每个账号需独立 App 内指纹）".format(label),
        )
    if mode == "auto":
        return checkin(account, activity_no, label, timeout, dry_run)
    state = sign_state(account, activity_no, timeout, dry_run)
    if state is True:
        return "already", "{}今日已签到".format(label)
    if state is False:
        return "todo", "{}未签到，需在 App 内手动签（当前为 manual 模式）".format(label)
    return "todo", "{}状态未知，需在 App 内确认".format(label)


# ============================================================
# 单账号流程
# ============================================================

def _stage_icon(status: str) -> str:
    if status in ("ok", "success"):
        return ICONS["success"]
    if status in ("already", "alreadyComplete"):
        return ICONS["alreadyComplete"]
    if status in ("skipped", "todo"):
        return ICONS["skipped"]
    if status in ("risk", "conflict", "warning"):
        return ICONS["warning"]
    return ICONS["failure"]


def run_account_dry(account: Account, mode: str, conflicted: bool) -> dict:
    started = time.time()
    stats = {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
        "elapsedMs": 0,
    }
    errors: List[str] = []
    stages = [
        (1, "参数校验", "ok", "token 已解析，设备指纹={}".format("已配置" if account.dx_token else "未配置")),
        (2, "token 续期", "skipped", "断网预演跳过续期请求"),
        (3, "小程序签到", "skipped", "断网预演跳过签到请求"),
        (4, "APP 签到", "skipped", "断网预演跳过 APP 入口（模式={}）".format(mode)),
        (5, "资料查询", "skipped", "断网预演跳过资料请求"),
    ]
    if conflicted:
        stages[2] = (3, "小程序签到", "conflict", "设备指纹与更靠前账号共用，预演标记冲突")
        stages[3] = (4, "APP 签到", "conflict", "设备指纹冲突，预演跳过")

    for num, name, status, message in stages:
        t0 = time.time()
        stats["total"] += 1
        if status in ("ok", "success"):
            stats["success"] += 1
        elif status in ("already", "alreadyComplete"):
            stats["alreadyComplete"] += 1
        elif status in ("skipped", "todo"):
            stats["skipped"] += 1
        elif status in ("conflict", "risk"):
            stats["failed"] += 1
            errors.append(message)
        else:
            stats["failed"] += 1
            errors.append(message)
        elapsed = int((time.time() - t0) * 1000)
        log(
            "  {}. {} {} {}（{}ms）".format(
                num, name, _stage_icon(status), message, elapsed
            )
        )

    # 预演：配置可解析且无指纹冲突即视为通过；冲突计失败
    success = not conflicted
    stats["elapsedMs"] = int((time.time() - started) * 1000)
    log(
        "账号统计：{} 总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={}ms".format(
            account.label,
            stats["total"],
            stats["success"],
            stats["alreadyComplete"],
            stats["skipped"],
            stats["failed"],
            stats["elapsedMs"],
        )
    )
    return {
        "index": account.index,
        "label": account.label,
        "displayName": account.nickname or "",
        "success": success,
        "outcome": "dry-run" if success else "conflict",
        "errors": errors,
        "stats": stats,
        "messages": [s[3] for s in stages],
    }


def run_account(
    account: Account,
    timeout: float,
    dry_run: bool,
    mode: str,
    conflicted: bool,
) -> dict:
    if dry_run:
        return run_account_dry(account, mode, conflicted)

    started = time.time()
    stats = {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
        "elapsedMs": 0,
    }
    errors: List[str] = []
    messages: List[str] = []
    secrets = [account.token, account.dx_token]

    def record(status: str, message: str) -> None:
        stats["total"] += 1
        clean = redact_secrets(safe_text(message), secrets)
        messages.append(clean)
        if status in ("ok", "success"):
            stats["success"] += 1
        elif status in ("already", "alreadyComplete"):
            stats["alreadyComplete"] += 1
        elif status in ("skipped", "todo"):
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
            errors.append(clean)

    log("—— {} 开始 ——".format(account.label))

    # 1. 续期
    t0 = time.time()
    try:
        ok, payload = refresh_token(account, timeout, dry_run)
    except LonghuError as exc:
        ok, payload = False, str(exc)
    if ok:
        # token 通常不变；若服务端返回新值仅更新内存，不打印
        if payload and payload != account.token:
            account.token = payload
        msg = "token 有效期已滚动续期"
        log("  1. token 续期 {} {}（{}ms）".format(ICONS["success"], msg, int((time.time() - t0) * 1000)))
        record("ok", msg)
    else:
        msg = redact_secrets(safe_text(payload), secrets)
        log("  1. token 续期 {} {}（{}ms）".format(ICONS["warning"], msg, int((time.time() - t0) * 1000)))
        record("skipped", "续期失败：{}".format(msg))

    # 2. 指纹冲突
    if conflicted:
        msg = "设备指纹与更靠前账号共用，已暂停签到（同一指纹多账号会触发风控）"
        log("  2. 指纹检查 {} {}".format(ICONS["warning"], msg))
        record("conflict", msg)
        log("  3. 小程序签到 {} 因指纹冲突跳过".format(ICONS["skipped"]))
        record("skipped", "小程序签到因指纹冲突跳过")
        log("  4. APP 签到 {} 因指纹冲突跳过".format(ICONS["skipped"]))
        record("skipped", "APP 签到因指纹冲突跳过")
    else:
        log("  2. 指纹检查 {} {}".format(
            ICONS["success"] if account.dx_token else ICONS["warning"],
            "已配置独立设备指纹" if account.dx_token else "未配置设备指纹，签到可能被风控拒绝",
        ))
        record("ok" if account.dx_token else "skipped", "设备指纹检查")

        # 3. 小程序签到
        t0 = time.time()
        try:
            status, message = checkin(account, ACTIVITY_NO, "", timeout, dry_run)
        except Exception as exc:
            status, message = "fail", "异常：{}".format(safe_text(exc))
        message = redact_secrets(safe_text(message), secrets)
        log(
            "  3. 小程序签到 {} {}（{}ms）".format(
                _stage_icon(status), message, int((time.time() - t0) * 1000)
            )
        )
        record(status, message)

        # 4. APP 签到
        t0 = time.time()
        try:
            status, message = run_app_entry(
                account, APP_ACTIVITY_NO, mode, timeout, dry_run
            )
        except Exception as exc:
            status, message = "fail", "异常：{}".format(safe_text(exc))
        message = redact_secrets(safe_text(message), secrets)
        log(
            "  4. APP 签到 {} {}（{}ms）".format(
                _stage_icon(status), message, int((time.time() - t0) * 1000)
            )
        )
        # APP：auto 下 fail/risk 计失败；manual/todo/off/skipped 不计失败
        if mode == "auto" and status in ("fail", "risk"):
            record(status, message)
        elif status in ("ok", "already"):
            record(status, message)
        else:
            record("skipped" if status in ("skipped", "todo") else status, message)

    # 5. 资料
    t0 = time.time()
    try:
        profile = fetch_profile(account, timeout, dry_run)
        account.nickname = str(profile.get("nickname") or "")
        account.level_name = str(profile.get("level_name") or "")
        parts = []
        if account.nickname:
            parts.append("昵称={}".format(account.nickname))
        if account.level_name:
            parts.append("等级={}".format(account.level_name))
        parts.append("成长值={}".format(profile.get("growth_value", 0)))
        if "balance" in profile:
            parts.append("珑珠={}".format(profile.get("balance")))
        msg = "；".join(parts) if parts else "已拉取资料"
        log(
            "  5. 资料查询 {} {}（{}ms）".format(
                ICONS["success"], msg, int((time.time() - t0) * 1000)
            )
        )
        record("ok", msg)
    except LonghuError as exc:
        msg = redact_secrets(safe_text(exc), secrets)
        log(
            "  5. 资料查询 {} {}（{}ms）".format(
                ICONS["warning"], msg, int((time.time() - t0) * 1000)
            )
        )
        record("skipped", "资料查询失败：{}".format(msg))

    # 成功判定：无失败计数（含 conflict / risk / fail；APP auto 失败已计入）
    success = stats["failed"] == 0
    outcome = "success" if success else "failure"
    if success and stats["alreadyComplete"] and not stats["success"]:
        outcome = "alreadyComplete"

    stats["elapsedMs"] = int((time.time() - started) * 1000)
    log(
        "账号统计：{} 总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={}ms".format(
            account.label,
            stats["total"],
            stats["success"],
            stats["alreadyComplete"],
            stats["skipped"],
            stats["failed"],
            stats["elapsedMs"],
        )
    )
    return {
        "index": account.index,
        "label": account.label,
        "displayName": account.nickname or "",
        "success": success,
        "outcome": outcome,
        "errors": errors,
        "stats": stats,
        "messages": messages,
    }


# ============================================================
# 主流程
# ============================================================

def build_notify_body(
    results: List[dict],
    dry_run: bool,
    final_status: str,
    elapsed: float,
) -> str:
    total = len(results)
    ok = sum(1 for r in results if r["success"])
    failed = total - ok
    lines = [
        "任务：{}".format(TASK_NAME),
        "模式：{}".format("断网预演" if dry_run else "正式运行"),
        "账号总数：{}".format(total),
        "成功：{}".format(ok),
        "失败：{}".format(failed),
        "总耗时：{:.2f} 秒".format(elapsed),
        "最终状态：{}".format(final_status),
        "",
        "明细：",
    ]
    for item in results:
        mark = ICONS["success"] if item["success"] else ICONS["failure"]
        detail = "、".join(safe_text(x) for x in item.get("errors") or []) or item.get(
            "outcome"
        )
        lines.append(
            "- {} {}：{}".format(
                mark, item.get("label") or ("账号" + str(item["index"])), detail
            )
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    no_notify = "--no-notify" in argv
    dry_run = truthy_env("LONGHU_DRY_RUN")
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
    mode = "auto"

    try:
        timeout = env_timeout()
        mode = app_checkin_mode()
        accounts = parse_accounts()
    except Exception as exc:
        config_error = safe_text(exc)
        log("{} 配置错误：{}".format(ICONS["failure"], config_error))
        exit_code = 2
        final_status = "CONFIG_ERROR"
        accounts = []

    log("账号数量：{}".format(len(accounts)))
    if accounts and not config_error:
        log("APP 入口模式：{}".format(mode))

    conflicts = dx_conflicts(accounts) if accounts else {}

    if accounts:
        for account in accounts:
            try:
                results.append(
                    run_account(
                        account,
                        timeout if not config_error else DEFAULT_TIMEOUT,
                        dry_run,
                        mode,
                        conflicted=account.index in conflicts,
                    )
                )
            except Exception as exc:
                log(
                    "{} {} 执行异常：{}".format(
                        ICONS["failure"], account.label, safe_text(exc)
                    )
                )
                results.append(
                    {
                        "index": account.index,
                        "label": account.label,
                        "displayName": account.nickname or "",
                        "success": False,
                        "outcome": "failure",
                        "errors": [safe_text(exc)],
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
