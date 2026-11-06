#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 安徽工业大学晚寝签到
# cron: 20 21 * * *
#
# 来源：Sull1se/ahut-auto-checkin（MIT），python/main.py
# 相关参考：python/notifier.py（通知文案结构）、油猴适配器仅作同应用参考不合并浏览器自动化
#
# MIT License
#
# Copyright (c) Sull1se / ahut-auto-checkin contributors
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
安徽工业大学（AHUT）晚寝自动签到 - 青龙维护版

功能清点（相对上游 python/main.py）：
- OAuth 登录获取凭证
- 动态拉取当日晚寝签到任务
- 微信环境校验、签到时间窗口、宿舍基准定位
- 提交晚寝签到（含宿舍围栏内轻微 GPS 抖动）
- 多账号、失败非零退出、结果通知

维护改动：
- 去掉不安全的默认密码 Ahgydx@920；密码必须显式配置
- 账号统一为 AHUT_ACCOUNTS（每行 学号|密码），兼容 STUDENT_IDS/PASSWORDS
- 标准库实现 HTTPS，请求超时与业务成功判定；AHUT_DRY_RUN 完全断网预演
- 青龙 notify.py / sendNotify.js 通知；时间轴日志与 TASK_SUMMARY
- 不依赖私有仓库、notifier.py 或云函数入口；不合并油猴浏览器自动化

环境变量：
  AHUT_ACCOUNTS   必填（规范）：每行一个账号，学号|密码（仅按首个 | 分割）
  STUDENT_IDS     兼容：学号列表（换行；兼容旧分号/逗号），需与 PASSWORDS 对齐
  PASSWORDS       兼容：密码列表，与 STUDENT_IDS 行序对齐；不再提供默认密码
  AHUT_DRY_RUN    1/true/yes/on 开启完全断网预演
  AHUT_TIMEOUT    单次 HTTP 超时秒数，默认 20
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

仅供学习交流，请遵守学校规定；请在宿舍真实可签到时使用。
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
        _ql_notify_identities = ('4e628bcec2f5fef6', 'scripts/ahut.py', 'ahut.py', 'ahut')
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
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ============================================================
# 元数据与常量
# ============================================================

CATALOG_ID = "4e628bcec2f5fef6"
TASK_NAME = "安徽工业大学晚寝签到"
SCRIPT_FILENAME = "ahut_dorm_checkin.py"

API_BASE_URL = "https://xskq.ahut.edu.cn/api"
TOKEN_API = f"{API_BASE_URL}/flySource-auth/oauth/token"
TASK_ID_API = (
    f"{API_BASE_URL}/flySource-yxgl/dormSignTask/getStudentTaskPage"
    "?userDataType=student&current=1&size=15"
)
AUTH_CHECK_API = (
    f"{API_BASE_URL}/flySource-base/wechat/getWechatMpConfig"
    "?configUrl=https://xskq.ahut.edu.cn/wise/pages/ssgl/dormsign"
    "?taskId={{TASK_ID}}&autoSign=1&scanSign=0&userId={{STUDENT_ID}}"
)
API_LOG_API = (
    f"{API_BASE_URL}/flySource-base/apiLog/save"
    "?menuTitle=%E6%99%9A%E5%AF%9D%E7%AD%BE%E5%88%B0"
)
GET_LOCATION_API = (
    f"{API_BASE_URL}/flySource-yxgl/dormSignTask/getTaskByIdForApp"
    "?taskId={{TASK_ID}}&signDate={{date_str}}"
)
SIGN_IN_API = f"{API_BASE_URL}/flySource-yxgl/dormSignRecord/stuSign"

# 校园微信端公开 OAuth 客户端标识（非用户凭据）
APP_BASIC_AUTH = (
    "Basic Zmx5c291cmNlX3dpc2VfYXBwOkRBNzg4YXNkVURqbmFzZF9mbHlzb3VyY2VfZHNkYWREQUlVaXV3cWU="
)

UA_LIST = [
    (
        "Mozilla/5.0 (Linux; Android 15; MIX Fold 4 Build/TKQ1.240502.001; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.137 "
        "Mobile Safari/537.36 MicroMessenger/8.0.61.2660(0x28003D37) WeChat/arm64 "
        "Weixin NetType/WIFI Language/zh_CN ABI/arm64"
    ),
    (
        "Mozilla/5.0 (Linux; Android 15; LYA-AL10 Build/HUAWEILYA-AL10; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.137 "
        "Mobile Safari/537.36 MicroMessenger/8.0.61.2660(0x28003D37) WeChat/arm64 "
        "Weixin NetType/5G Language/zh_CN ABI/arm64"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
        "MicroMessenger/8.0.61(0x18003D29) NetType/WIFI Language/zh_CN"
    ),
]

MAX_RETRIES = 4
MAX_TOKEN_RETRIES = 3
DEFAULT_TIMEOUT = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
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


def env_timeout() -> float:
    raw = os.getenv("AHUT_TIMEOUT", "").strip()
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("AHUT_TIMEOUT 必须是数字") from exc
    if value < 3 or value > 120:
        raise ValueError("AHUT_TIMEOUT 必须在 3 到 120 之间")
    return value


def safe_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else ""


def password_md5(pwd: str) -> str:
    return hashlib.md5(pwd.encode("utf-8")).hexdigest()


def generate_sign(url: str, token: str) -> str:
    if not token:
        return ""
    parsed_url = urlparse(url)
    api = parsed_url.path + "?sign="
    timestamp = int(time.time() * 1000)
    inner = "{}{}".format(timestamp, token)
    inner_hash = hashlib.md5(inner.encode("utf-8")).hexdigest()
    raw = "{}{}".format(api, inner_hash)
    final_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()
    encoded_time = base64.b64encode(str(timestamp).encode("utf-8")).decode("utf-8")
    return "{}.{}".format(final_hash + "1", encoded_time)


def generate_sign_code(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc) + timedelta(hours=8)
    week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    month = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    w = week[dt.weekday()]
    m = month[dt.month - 1]
    tz = "GMT+0800 (中国标准时间)"
    time_str = "{} {} {:02d} {} {} {}".format(
        w, m, dt.day, dt.year, dt.strftime("%H:%M:%S"), tz
    )
    return hashlib.md5(time_str.encode()).hexdigest()


def generate_stu_task_id(lat, lng, acc, date, task_id, file_id="") -> str:
    data = {
        "latitude": str(lat),
        "longitude": str(lng),
        "locationAccuracy": str(acc),
        "signDate": date,
        "taskId": task_id,
        "fileId": file_id,
    }
    json_str = json.dumps(data, separators=(",", ":"))
    return hashlib.md5(json_str.encode()).hexdigest()


# ============================================================
# 账号解析
# ============================================================

@dataclass
class Account:
    index: int
    student_id: str
    password: str
    display_name: str = ""
    token: str = ""
    task_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    room_id: str = ""
    user_agent: str = field(default_factory=lambda: random.choice(UA_LIST))

    @property
    def label(self) -> str:
        if self.display_name:
            return "账号{}（{}）".format(self.index, self.display_name)
        return "账号{}".format(self.index)


def _split_legacy_list(raw: str) -> List[str]:
    # 兼容旧分号/逗号；规范多账号仍以换行为主
    parts = re.split(r"[\n;，,]+", raw)
    return [p.strip() for p in parts if p.strip()]


def parse_accounts() -> List[Account]:
    accounts: List[Account] = []
    raw = os.getenv("AHUT_ACCOUNTS", "")
    if raw.strip():
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise ValueError("AHUT_ACCOUNTS 每行须为 学号|密码（仅按首个 | 分割）")
            student_id, password = line.split("|", 1)
            student_id = student_id.strip()
            password = password.strip()
            if not student_id or not password:
                raise ValueError("AHUT_ACCOUNTS 存在空学号或空密码行")
            if not student_id.isdigit():
                raise ValueError("学号须为数字：账号配置格式不合规")
            accounts.append(
                Account(index=len(accounts) + 1, student_id=student_id, password=password)
            )

    if not accounts:
        ids_raw = os.getenv("STUDENT_IDS", "").strip()
        pwds_raw = os.getenv("PASSWORDS", "").strip()
        if ids_raw:
            student_ids = _split_legacy_list(ids_raw)
            passwords = _split_legacy_list(pwds_raw) if pwds_raw else []
            if not passwords:
                raise ValueError(
                    "已配置 STUDENT_IDS 但缺少 PASSWORDS；"
                    "维护版不再使用默认密码，请显式填写或改用 AHUT_ACCOUNTS"
                )
            if len(passwords) == 1 and len(student_ids) > 1:
                passwords = passwords * len(student_ids)
            if len(passwords) != len(student_ids):
                raise ValueError("STUDENT_IDS 与 PASSWORDS 数量不一致")
            for sid, pwd in zip(student_ids, passwords):
                if not sid.isdigit():
                    raise ValueError("学号须为数字：{}".format(sid))
                if not pwd:
                    raise ValueError("存在空密码")
                accounts.append(
                    Account(index=len(accounts) + 1, student_id=sid, password=pwd)
                )

    if not accounts:
        raise ValueError(
            "缺少账号凭据：请配置必填变量 AHUT_ACCOUNTS（每行 学号|密码），"
            "或兼容别名 STUDENT_IDS + PASSWORDS（均须显式填写，无默认密码）"
        )
    return accounts


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
    here = Path(__file__).resolve().parent
    paths.append(here / "notify.py")
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
    here = Path(__file__).resolve().parent
    paths.append(here / "sendNotify.js")
    return paths


def send_qinglong_notify(title: str, content: str, dry_run: bool) -> str:
    if dry_run:
        log("{} 预演通知（不发送）：{}".format(ICONS["skipped"], safe_text(title)))
        return "dry-run-simulated"
    for path in notify_paths_py():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify_ahut", str(path))
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
# HTTP
# ============================================================

class HttpError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        raise RuntimeError("dry-run 禁止发起网络请求")
    final_url = url
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        final_url = "{}{}{}".format(url, "&" if ("?" in url) else "?", query)
    data = None
    req_headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json;charset=UTF-8")
    request = urllib.request.Request(final_url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise HttpError("响应过大，已中止解析", status=getattr(resp, "status", 0))
            text = raw.decode("utf-8", errors="replace")
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise HttpError("响应不是合法 JSON", status=getattr(resp, "status", 0)) from exc
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES) if hasattr(exc, "read") else b""
        try:
            payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        raise HttpError("HTTP {}".format(exc.code), status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise HttpError("网络错误：{}".format(safe_text(exc.reason))) from exc


# ============================================================
# 签到步骤
# ============================================================

def base_headers(account: Account) -> Dict[str, str]:
    headers = {
        "User-Agent": account.user_agent,
        "authorization": APP_BASIC_AUTH,
        "Content-Type": "application/json;charset=UTF-8",
        "X-Requested-With": "com.tencent.mm",
        "Origin": "https://xskq.ahut.edu.cn",
        "Referer": (
            "https://xskq.ahut.edu.cn/wise/pages/ssgl/dormsign?&userId={}".format(
                account.student_id
            )
        ),
    }
    if account.token:
        headers["flysource-auth"] = "bearer {}".format(account.token)
    return headers


def auth_headers(account: Account, url: Optional[str] = None) -> Dict[str, str]:
    headers = base_headers(account)
    if account.token and url:
        headers["flysource-sign"] = generate_sign(url, account.token)
    return headers


def build_sign_payload(account: Account) -> dict:
    sign_lat = account.latitude + round(random.uniform(-0.0002, 0.0002), 6)
    sign_lng = account.longitude + round(random.uniform(-0.0002, 0.0002), 6)
    location_accuracy = round(random.uniform(25, 35), 2)
    date_str = now_beijing().strftime("%Y-%m-%d")
    return {
        "signType": 0,
        "taskId": account.task_id,
        "signLat": sign_lat,
        "signLng": sign_lng,
        "locationAccuracy": location_accuracy,
        "stuTaskId": generate_stu_task_id(
            sign_lat, sign_lng, location_accuracy, date_str, account.task_id
        ),
        "scanCode": "",
        "scanType": "",
        "roomId": account.room_id,
        "signKey": account.room_id,
        "signCode": generate_sign_code(int(time.time() * 1000)),
    }


def step_login(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str]:
    log("阶段 1/6 获取登录凭证 — {}".format(account.label))
    if dry_run:
        account.display_name = "预演用户{}".format(account.index)
        account.token = "dry-run-token"
        log("{} 预演：跳过登录请求".format(ICONS["skipped"]))
        return True, "dry-run-login"
    params = {
        "tenantId": "000000",
        "username": account.student_id,
        "password": password_md5(account.password),
        "type": "account",
        "grant_type": "password",
        "scope": "all",
    }
    result = http_json(
        "POST",
        TOKEN_API,
        headers=base_headers(account),
        params=params,
        timeout=timeout,
        dry_run=dry_run,
    )
    if "refresh_token" in result:
        account.token = str(result.get("refresh_token") or "")
        account.display_name = safe_text(result.get("userName") or "")
        if account.display_name:
            log(
                "{} 登录成功，姓名：{}".format(ICONS["success"], account.display_name)
            )
        else:
            log("{} 登录成功".format(ICONS["success"]))
        return True, "login-ok"
    error_desc = safe_text(result.get("error_description") or result.get("msg") or "未知错误")
    if "Bad credentials" in error_desc or "用户名或密码错误" in error_desc:
        error_desc = "学号或密码错误"
    log("{} 登录失败：{}".format(ICONS["failure"], error_desc))
    return False, error_desc


def step_task_id(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str, int]:
    """返回 success, message, next_step_hint（0 表示需重登）。"""
    log("阶段 2/6 获取签到任务 — {}".format(account.label))
    if dry_run:
        account.task_id = "dry-run-task"
        log("{} 预演：使用模拟任务 ID".format(ICONS["skipped"]))
        return True, "dry-run-task", 2
    result = http_json(
        "GET",
        TASK_ID_API,
        headers=auth_headers(account, TASK_ID_API),
        timeout=timeout,
        dry_run=dry_run,
    )
    if result.get("code") == 200:
        records = (result.get("data") or {}).get("records") or []
        if records and records[0].get("taskId"):
            account.task_id = str(records[0].get("taskId"))
            log("{} 已获取当日晚寝任务".format(ICONS["success"]))
            return True, "task-ok", 2
        log("{} 未检索到今日有效晚寝签到任务".format(ICONS["failure"]))
        return False, "未找到签到任务", 1
    msg = safe_text(result.get("msg") or "获取任务失败")
    if any(k in msg for k in ("请求未授权", "缺失身份信息", "鉴权失败")):
        account.token = ""
        return False, "token失效", 0
    log("{} 获取任务失败：{}".format(ICONS["failure"], msg))
    return False, msg, 1


def step_wechat_auth(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str, int]:
    log("阶段 3/6 验证微信环境 — {}".format(account.label))
    if dry_run:
        log("{} 预演：跳过微信环境校验".format(ICONS["skipped"]))
        return True, "dry-run-wechat", 3
    url = AUTH_CHECK_API.format(TASK_ID=account.task_id, STUDENT_ID=account.student_id)
    result = http_json(
        "GET",
        url,
        headers=auth_headers(account, url),
        timeout=timeout,
        dry_run=dry_run,
    )
    if result.get("code") == 200:
        log("{} 微信环境验证通过".format(ICONS["success"]))
        return True, "wechat-ok", 3
    msg = safe_text(result.get("msg") or "微信环境验证失败")
    if any(k in msg for k in ("请求未授权", "缺失身份信息", "鉴权失败")):
        account.token = ""
        return False, "token失效", 0
    log("{} 微信环境验证失败：{}".format(ICONS["failure"], msg))
    return False, msg, 2


def step_open_window(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str, int]:
    log("阶段 4/6 开启签到时间窗口 — {}".format(account.label))
    if dry_run:
        log("{} 预演：跳过时间窗口请求".format(ICONS["skipped"]))
        return True, "dry-run-window", 4
    # 使用带超时的请求；上游仅检查 HTTP 200
    try:
        headers = auth_headers(account, API_LOG_API)
        request = urllib.request.Request(API_LOG_API, data=b"", headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            if 200 <= getattr(resp, "status", 200) < 300:
                # 丢弃响应体，避免保留原始内容
                _ = resp.read(MAX_RESPONSE_BYTES)
                log("{} 时间窗口已开启".format(ICONS["success"]))
                return True, "window-ok", 4
    except urllib.error.HTTPError as exc:
        if any(k in str(exc) for k in ("401", "403")):
            account.token = ""
            return False, "token失效", 0
        log("{} 开启时间窗口失败：HTTP {}".format(ICONS["failure"], exc.code))
        return False, "开启签到时间窗口失败", 3
    except Exception as exc:
        log("{} 开启时间窗口失败：{}".format(ICONS["failure"], safe_text(exc)))
        return False, "开启签到时间窗口失败", 3
    log("{} 开启时间窗口失败".format(ICONS["failure"]))
    return False, "开启签到时间窗口失败", 3


def step_location(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str, int]:
    log("阶段 5/6 获取宿舍基准定位 — {}".format(account.label))
    if dry_run:
        account.latitude = 31.670000
        account.longitude = 118.500000
        account.room_id = "dry-room"
        log("{} 预演：使用模拟宿舍坐标".format(ICONS["skipped"]))
        return True, "dry-run-location", 5
    url = GET_LOCATION_API.format(
        TASK_ID=account.task_id,
        date_str=now_beijing().strftime("%Y-%m-%d"),
    )
    result = http_json(
        "GET",
        url,
        headers=auth_headers(account, url),
        timeout=timeout,
        dry_run=dry_run,
    )
    if result.get("code") == 200:
        dorm = (result.get("data") or {}).get("dormitoryRegisterVO") or {}
        try:
            account.latitude = float(dorm.get("locationLat") or 0)
            account.longitude = float(dorm.get("locationLng") or 0)
        except (TypeError, ValueError):
            account.latitude = 0.0
            account.longitude = 0.0
        account.room_id = str(dorm.get("roomId") or "")
        log("{} 宿舍定位已就绪".format(ICONS["success"]))
        return True, "location-ok", 5
    msg = safe_text(result.get("msg") or "")
    if any(k in msg for k in ("请求未授权", "缺失身份信息", "鉴权失败")):
        account.token = ""
        return False, "token失效", 0
    # 与上游一致：定位失败时仍尝试继续提交（可能服务端另有校验）
    log("{} 定位接口异常，继续尝试签到".format(ICONS["warning"]))
    return True, "location-soft-fail", 5


def step_sign(account: Account, timeout: float, dry_run: bool) -> Tuple[bool, str, str, int]:
    """返回 success, message, outcome(success|alreadyComplete|failure), next_step."""
    log("阶段 6/6 提交晚寝签到 — {}".format(account.label))
    if dry_run:
        log("{} 预演：跳过签到提交".format(ICONS["skipped"]))
        return True, "dry-run-sign", "success", 6
    payload = build_sign_payload(account)
    # 轻微拟真间隔，避免瞬时提交
    time.sleep(round(random.uniform(1, 3), 2))
    result = http_json(
        "POST",
        SIGN_IN_API,
        headers=auth_headers(account, SIGN_IN_API),
        json_body=payload,
        timeout=timeout,
        dry_run=dry_run,
    )
    msg = safe_text(result.get("msg") or "")
    if result.get("code") == 200:
        log("{} 签到成功".format(ICONS["success"]))
        return True, "sign-ok", "success", 6
    if "您今天已完成签到" in msg:
        log("{} 今日已完成签到".format(ICONS["alreadyComplete"]))
        return True, msg, "alreadyComplete", 6
    if any(k in msg for k in ("请求未授权", "缺失身份信息", "鉴权失败")):
        account.token = ""
        return False, "token失效", "failure", 0
    if "未到签到时间" in msg:
        log("{} 未到签到开放时间".format(ICONS["failure"]))
        return False, msg, "failure", -1
    log("{} 签到失败：{}".format(ICONS["failure"], msg or "未知错误"))
    return False, msg or "签到失败", "failure", 5


def run_account(account: Account, timeout: float, dry_run: bool) -> Dict[str, Any]:
    started = time.time()
    stats = {
        "total": 1,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
        "elapsedMs": 0,
    }
    errors: List[str] = []
    outcome = "failure"
    step = 0
    retries = 0
    token_retries = 0

    log("—— 开始处理 {} ——".format(account.label))

    while retries < MAX_RETRIES and 0 <= step < 6:
        stage_started = time.time()
        ok = False
        msg = ""
        hint = step
        stage_outcome = ""

        if step == 0:
            ok, msg = step_login(account, timeout, dry_run)
            hint = 1 if ok else -1
        elif step == 1:
            ok, msg, hint = step_task_id(account, timeout, dry_run)
        elif step == 2:
            ok, msg, hint = step_wechat_auth(account, timeout, dry_run)
        elif step == 3:
            ok, msg, hint = step_open_window(account, timeout, dry_run)
        elif step == 4:
            ok, msg, hint = step_location(account, timeout, dry_run)
        elif step == 5:
            ok, msg, stage_outcome, hint = step_sign(account, timeout, dry_run)

        log(
            "阶段 {} 结果：{} 耗时={}ms 说明={}".format(
                step + 1,
                ICONS["success"] if ok else ICONS["failure"],
                int((time.time() - stage_started) * 1000),
                safe_text(msg),
            )
        )

        if step == 0:
            if ok:
                step = 1
            else:
                errors.append(msg)
                break
        elif ok:
            if step == 5:
                outcome = stage_outcome or "success"
                step = 6
            else:
                step = step + 1
        else:
            errors.append(msg)
            if hint == 0 and token_retries < MAX_TOKEN_RETRIES:
                token_retries += 1
                step = 0
            elif hint < 0:
                break
            else:
                retries += 1
                if retries >= MAX_RETRIES:
                    break

        if not dry_run and 0 <= step < 6:
            time.sleep(round(random.uniform(0.3, 1.2), 2))

    success = step == 6
    if success:
        if outcome == "alreadyComplete":
            stats["alreadyComplete"] = 1
        else:
            stats["success"] = 1
            outcome = "success"
    else:
        stats["failed"] = 1
        outcome = "failure"

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
        "displayName": account.display_name,
        "success": success,
        "outcome": outcome,
        "errors": errors,
        "stats": stats,
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
        detail = "、".join(safe_text(x) for x in item.get("errors") or []) or item.get("outcome")
        lines.append(
            "- {} {}：{}".format(mark, item.get("label") or ("账号" + str(item["index"])), detail)
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    no_notify = "--no-notify" in argv
    dry_run = truthy_env("AHUT_DRY_RUN")
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

    try:
        timeout = env_timeout()
        accounts = parse_accounts()
    except Exception as exc:
        config_error = safe_text(exc)
        log("{} 配置错误：{}".format(ICONS["failure"], config_error))
        exit_code = 2
        final_status = "CONFIG_ERROR"
        accounts = []

    log("账号数量：{}".format(len(accounts)))

    if accounts:
        for account in accounts:
            try:
                results.append(run_account(account, timeout, dry_run))
            except Exception as exc:
                log("{} {} 执行异常：{}".format(ICONS["failure"], account.label, safe_text(exc)))
                results.append(
                    {
                        "index": account.index,
                        "label": account.label,
                        "displayName": account.display_name,
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
    log("账号结果：成功 {} / 失败 {} / 总计 {}".format(account_ok, account_fail, len(results)))
    log(
        "子任务结果：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            sub_success, sub_already, sub_skip, sub_fail
        )
    )
    log("总耗时：{:.2f} 秒".format(elapsed))

    # 通知
    send_on = True
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
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    print("=" * 60, flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
