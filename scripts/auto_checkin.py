#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 厦门大学畅课自动签到
# cron: */2 8-18 * * 1-5
# SPDX-License-Identifier: MIT

"""
厦门大学畅课（Tronclass）自动签到 - 青龙维护版

基于 spicysuimai/XMU-AC（MIT，Copyright (c) 2026 YixuAnsensei；源自 ch-z-hc/XMU-AC）维护。

保留用户可见能力：
- xmulogin 纯 API CAS 登录（Tronclass type=3）与可选 Cookie 持久化
- 数字签到（详情接口取码 + 课表日期接口备用通道）
- GPS 签到（双探针三角定位，提交后按名单本人 rollcall_status 确认）
- 签到门控（已签超过 1/4 或超过 20 人再签；超时/临近结束保底）

维护改动：
- 去掉交互输入、清屏看板与无限看门狗；改为青龙可调度的有界扫描/轮询
- 多账号每行一个（学号|密码）；任一账号失败整体非零退出
- 完全断网预演 XMU_AC_DRY_RUN、时间轴日志、TASK_SUMMARY、青龙通知
- 登录与业务 HTTP 使用可安装的公开依赖（requests、xmulogin）；预演不发起网络请求

仅供学习交流，请遵守学校规定。
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
        _ql_notify_identities = ('f0ed23d57cf865a3', 'scripts/auto_checkin.py', 'auto_checkin.py', 'auto_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# 元数据与常量
# ============================================================

CATALOG_ID = "f0ed23d57cf865a3"
TASK_NAME = "厦门大学畅课自动签到"
SCRIPT_FILENAME = "xmu_tronclass_checkin.py"

BASE_URL = "https://lnt.xmu.edu.cn"
DEFAULT_INTERVAL = 15
DEFAULT_POLL_SECONDS = 0  # 0 = 单次扫描后退出；>0 时在本轮内有界轮询

CHECKIN_GATE_DEFAULT = True
CHECKIN_RATIO = 0.25
CHECKIN_MIN_SIGNED = 20
CHECKIN_MAX_WAIT = 120
CHECKIN_MIN_REMAINING = 30

GPS_DISTANCE_TOLERANCE = 5.0
PROBE_LAT1, PROBE_LON1 = 24.3, 118.0
PROBE_LAT2, PROBE_LON2 = 24.6, 118.2
MAX_UNKNOWN_RETRIES = 10
HTTP_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

SIGNED_STUDENT_STATUS = "on_call_fine"
TERMINAL_STATUSES = {
    "finished", "expired", "closed", "on_call_fine", "on_personal_leave",
}
ACTIVE_STATUSES = {
    "active", "on_going", "on_coming", "started", "in_progress",
    "waiting", "pending", "not_started", "absent",
}

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
BEIJING = timezone(timedelta(hours=8))

HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
}

SCRIPT_DIR = Path(__file__).resolve().parent


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


def truthy(name: str, default: str = "") -> bool:
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
    return default


def env_int(name: str, default: int, minimum: int = 0, maximum: int = 86400) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("{} 必须是整数".format(name)) from exc
    if value < minimum or value > maximum:
        raise ValueError("{} 必须在 {} 到 {} 之间".format(name, minimum, maximum))
    return value


def env_float(name: str, default: float, minimum: float = 1.0, maximum: float = 120.0) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("{} 必须是数字".format(name)) from exc
    if value < minimum or value > maximum:
        raise ValueError("{} 必须在 {} 到 {} 之间".format(name, minimum, maximum))
    return value


def safe_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else ""


def mask_account_label(index: int, display_name: str = "", public_id: str = "") -> str:
    if display_name:
        return "账号{}（{}）".format(index, display_name)
    if public_id:
        return "账号{}（uid {}）".format(index, public_id)
    return "账号{}".format(index)


# ============================================================
# 账号解析
# ============================================================

def parse_accounts() -> List[Dict[str, str]]:
    """解析账号：优先 XMU_AC_ACCOUNTS（学号|密码，仅按第一个 | 分割）。"""
    accounts: List[Dict[str, str]] = []
    raw = os.getenv("XMU_AC_ACCOUNTS", "")
    if raw.strip():
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise ValueError("XMU_AC_ACCOUNTS 每行须为 学号|密码")
            student_id, password = line.split("|", 1)
            student_id = student_id.strip()
            password = password.strip()
            if not student_id or not password:
                raise ValueError("XMU_AC_ACCOUNTS 存在空学号或空密码行")
            accounts.append({"student_id": student_id, "password": password})
    if not accounts:
        student_id = os.getenv("STUDENT_ID", "").strip()
        password = os.getenv("PASSWORD", "").strip()
        # 兼容：STUDENT_ID / PASSWORD 也可按换行提供多账号，按行对齐
        sid_lines = [x.strip() for x in student_id.splitlines() if x.strip()]
        pwd_lines = [x.strip() for x in password.splitlines() if x.strip()]
        if sid_lines and pwd_lines:
            if len(sid_lines) != len(pwd_lines):
                raise ValueError("STUDENT_ID 与 PASSWORD 行数不一致")
            for sid, pwd in zip(sid_lines, pwd_lines):
                accounts.append({"student_id": sid, "password": pwd})
    if not accounts:
        raise ValueError(
            "缺少账号凭据：请配置必填变量 XMU_AC_ACCOUNTS（每行 学号|密码），"
            "或兼容别名 STUDENT_ID + PASSWORD"
        )
    return accounts


# ============================================================
# 通知策略
# ============================================================

def _split_selectors(raw: str) -> List[str]:
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def notification_allowed() -> bool:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    # auto：按脚本选择列表
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
    paths.extend([
        Path("/ql/data/scripts/notify.py"),
        Path("/ql/scripts/notify.py"),
    ])
    return paths


def notify_paths_js() -> List[Path]:
    paths: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        paths.append(Path(custom) / "sendNotify.js")
    paths.extend([
        Path("/ql/data/scripts/sendNotify.js"),
        Path("/ql/scripts/sendNotify.js"),
    ])
    return paths


def send_notification(title: str, body: str) -> str:
    if not notification_allowed():
        log("通知状态：已跳过（开关或脚本选择未启用）")
        return "skipped"
    try:
        mod = importlib.import_module("notify")
        sender = getattr(mod, "send", None)
        if callable(sender):
            sender(title, body)
            log("通知状态：notify.send 已调用")
            return "sent"
    except Exception:
        pass
    for path in notify_paths_py():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify_dyn", str(path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                log("通知状态：notify.py 已调用")
                return "sent"
        except Exception:
            continue
    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in notify_paths_js():
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue
    log("⚠️ 通知状态：未找到可用通知器或发送失败，不改变业务退出码")
    return "unavailable"


# ============================================================
# HTTP / 登录（live 才加载第三方依赖）
# ============================================================

class HttpError(RuntimeError):
    pass


def _load_requests():
    try:
        import requests
    except ImportError as exc:
        raise HttpError(
            "缺少依赖 requests，请执行: pip install requests xmulogin pycryptodome"
        ) from exc
    return requests


def _install_no_proxy_session(requests_mod) -> None:
    """与上游一致：忽略失效系统代理，避免 ProxyError。"""
    if getattr(requests_mod.Session, "_xmu_ac_no_proxy", False):
        return

    class _NoProxySession(requests_mod.Session):
        _xmu_ac_no_proxy = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.trust_env = False
            self.proxies = {}

    requests_mod.Session = _NoProxySession


def session_file_for(student_id: str) -> Path:
    base = os.getenv("XMU_AC_SESSION_DIR", "").strip()
    folder = Path(base) if base else SCRIPT_DIR / ".xmu_ac_sessions"
    digest = uuid.uuid5(uuid.NAMESPACE_URL, "xmu-ac:" + student_id).hex[:16]
    return folder / ("session_{}.json".format(digest))


def save_cookies(session: Any, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cookies = []
        for cookie in session.cookies:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires,
                "secure": cookie.secure,
                "rest": getattr(cookie, "_rest", {}),
            })
        path.write_text(json.dumps(cookies), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        log("阶段：Cookie 已持久化（路径已脱敏）")
    except Exception as exc:
        log("⚠️ Cookie 保存失败：{}".format(safe_text(exc)))


def load_cookies(session: Any, path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        cookies = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cookies, list):
            return False
        for item in cookies:
            if not isinstance(item, dict):
                continue
            session.cookies.set(
                name=item["name"],
                value=item["value"],
                domain=item.get("domain") or "",
                path=item.get("path") or "/",
                expires=None,
                secure=bool(item.get("secure", False)),
                rest=item.get("rest") or {},
            )
        return True
    except Exception as exc:
        log("⚠️ Cookie 加载失败：{}".format(safe_text(exc)))
        return False


def do_login(student_id: str, password: str, timeout: float) -> Tuple[Any, str, str]:
    """返回 (session, tronclass_user_id, display_name)。"""
    requests = _load_requests()
    _install_no_proxy_session(requests)
    session = requests.Session()
    session.headers.update(HEADERS_BASE)

    persist = env_bool("XMU_AC_PERSIST_COOKIE", True)
    path = session_file_for(student_id)
    if persist and load_cookies(session, path):
        try:
            response = session.get("{}/api/profile".format(BASE_URL), timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                uid = str(data.get("id") or "").strip()
                if uid:
                    name = str(
                        data.get("name")
                        or data.get("user_name")
                        or data.get("nickname")
                        or ""
                    ).strip()
                    log("登录：复用 Cookie 有效")
                    return session, uid, name
            log("登录：Cookie 已失效，改为 CAS 登录")
        except Exception as exc:
            log("登录：Cookie 校验失败（{}），改为 CAS 登录".format(safe_text(exc)))

    try:
        from xmulogin import xmulogin
    except ImportError as exc:
        raise HttpError(
            "缺少依赖 xmulogin，请执行: pip install requests xmulogin pycryptodome"
        ) from exc

    log("登录：xmulogin CAS（Tronclass）进行中")
    session = xmulogin(type=3, username=student_id, password=password)
    if not session:
        raise HttpError("CAS 登录失败")
    response = session.get("{}/api/profile".format(BASE_URL), timeout=timeout)
    if response.status_code != 200:
        raise HttpError("获取用户资料失败（HTTP {}）".format(response.status_code))
    data = response.json()
    uid = str(data.get("id") or "").strip()
    if not uid:
        raise HttpError("用户资料缺少公开 id")
    name = str(
        data.get("name") or data.get("user_name") or data.get("nickname") or ""
    ).strip()
    if persist:
        save_cookies(session, path)
    return session, uid, name


def response_json(response: Any) -> Any:
    raw = response.content or b""
    if len(raw) > MAX_RESPONSE_BYTES:
        raise HttpError("接口响应超过安全上限")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HttpError("接口未返回有效 JSON") from exc


# ============================================================
# 业务 API（保留上游口径）
# ============================================================

def get_semester(session: Any, timeout: float) -> Tuple[str, str]:
    try:
        response = session.get(
            "{}/api/current-semester-info".format(BASE_URL), timeout=timeout
        )
        if response.status_code == 200:
            data = response_json(response)
            return str(data["semester"]["id"]), str(data["academic_year"]["id"])
    except Exception as exc:
        log("⚠️ 获取学期信息失败：{}，使用默认值".format(safe_text(exc)))
    return "29", "12"


def get_courses(session: Any, timeout: float) -> List[Dict[str, Any]]:
    semester_id, year_id = get_semester(session, timeout)
    payload = {
        "conditions": {
            "semester_id": [semester_id],
            "academic_year_id": [year_id],
            "keyword": "",
            "classify_type": "recently_started",
            "display_studio_list": False,
        },
        "fields": "id,name,display_name",
        "page": 1,
        "page_size": 30,
        "showScorePassedStatus": False,
    }
    response = session.post(
        "{}/api/my-courses".format(BASE_URL), json=payload, timeout=timeout
    )
    data = response_json(response)
    if isinstance(data, list):
        courses = data
    elif isinstance(data, dict):
        courses = data.get("courses") or data.get("data") or []
    else:
        courses = []
    unique: List[Dict[str, Any]] = []
    seen = set()
    for course in courses:
        if not isinstance(course, dict):
            continue
        cid = course.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(course)
    return unique


def get_rollcalls(
    session: Any, course_id: Any, student_id: str, timeout: float
) -> List[Dict[str, Any]]:
    url = "{}/api/course/{}/student/{}/rollcalls?page=1&page_size=20".format(
        BASE_URL, course_id, student_id
    )
    response = session.get(url, timeout=timeout)
    data = response_json(response)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        items = data.get("rollcalls") or data.get("data") or []
        return [x for x in items if isinstance(x, dict)]
    return []


def get_rollcall_detail(
    session: Any, rollcall_id: Any, timeout: float
) -> Tuple[Optional[str], Optional[str], Any]:
    url = "{}/api/rollcall/{}/student_rollcalls".format(BASE_URL, rollcall_id)
    try:
        response = session.get(url, timeout=timeout)
        data = response_json(response)
        if not isinstance(data, dict):
            return None, None, None
        code = data.get("number_code")
        return (
            str(code) if code not in (None, "") else None,
            data.get("status"),
            data.get("end_time"),
        )
    except Exception as exc:
        log("⚠️ 读取点名详情失败：{}".format(safe_text(exc)))
        return None, None, None


def get_number_code_from_timetable(
    session: Any,
    rollcall_id: Any,
    course_id: Any,
    rollcall_time: Any,
    timeout: float,
    cache: Dict[Any, str],
) -> Optional[str]:
    if rollcall_id in cache:
        return cache[rollcall_id]
    try:
        dt = datetime.fromisoformat(str(rollcall_time).replace("Z", "+00:00"))
        date_str = dt.astimezone(timezone.utc).date().isoformat()
    except Exception:
        date_str = datetime.now(timezone.utc).date().isoformat()
    try:
        response = session.get(
            "{}/api/timetable_rollcalls".format(BASE_URL),
            params=[("course_ids", str(course_id)), ("rollcall_date", date_str)],
            timeout=timeout,
        )
        if response.status_code != 200:
            return None
        items = response_json(response).get("rollcalls") or []
        for item in items:
            if not isinstance(item, dict) or str(item.get("id")) != str(rollcall_id):
                continue
            code = item.get("number_code")
            if code:
                cache[rollcall_id] = str(code)
                return str(code)
    except Exception as exc:
        log("⚠️ 课表取码失败：{}".format(safe_text(exc)))
    return None


def find_me(students: List[Dict[str, Any]], student_no: str) -> Optional[Dict[str, Any]]:
    for item in students:
        if not isinstance(item, dict):
            continue
        if item.get("user_no") is None:
            continue
        if str(item["user_no"]) == str(student_no):
            return item
    return None


def check_my_checkin_status(
    session: Any,
    rollcall_id: Any,
    student_no: str,
    timeout: float,
    retries: int = 3,
    delay: float = 0.4,
) -> Optional[str]:
    url = "{}/api/rollcall/{}/student_rollcalls".format(BASE_URL, rollcall_id)
    status = None
    for index in range(retries):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code != 200:
                return None
            students = response_json(response).get("student_rollcalls")
            if not isinstance(students, list):
                return None
            me = find_me([s for s in students if isinstance(s, dict)], student_no)
            if me is None:
                log("⚠️ 名单中未找到本人记录，无法确认签到结果")
                return None
            status = me.get("rollcall_status")
            if status == SIGNED_STUDENT_STATUS:
                return status
        except Exception as exc:
            log("⚠️ 回查本人状态失败：{}".format(safe_text(exc)))
            return None
        if index < retries - 1:
            time.sleep(delay)
    return status


def get_signed_stats(
    session: Any, rollcall_id: Any, student_no: str, timeout: float
) -> Tuple[Optional[int], Optional[int], Any]:
    try:
        response = session.get(
            "{}/api/rollcall/{}/student_rollcalls".format(BASE_URL, rollcall_id),
            timeout=timeout,
        )
        if response.status_code != 200:
            return None, None, None
        data = response_json(response)
        students = data.get("student_rollcalls") if isinstance(data, dict) else None
        if not isinstance(students, list):
            return None, None, None
        students = [s for s in students if isinstance(s, dict)]
        if not students:
            return None, None, None
        me = find_me(students, student_no)
        if me is not None and me.get("rollcall_status") == SIGNED_STUDENT_STATUS:
            log("⚠️ 本人已签上却仍在门控流程，直接放行")
            return None, None, None
        signed = sum(
            1 for s in students if s.get("rollcall_status") == SIGNED_STUDENT_STATUS
        )
        return signed, len(students), data.get("end_time")
    except Exception as exc:
        log("⚠️ 查询签到人数失败：{}".format(safe_text(exc)))
        return None, None, None


def time_remaining(end_time: Any) -> Optional[float]:
    if not end_time:
        return None
    try:
        dt = datetime.fromisoformat(str(end_time).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - datetime.now(timezone.utc)).total_seconds()
    except Exception:
        return None


def end_time_passed(end_time: Any) -> bool:
    remaining = time_remaining(end_time)
    return remaining is not None and remaining <= 0


def is_terminal(status: Any, end_time: Any) -> bool:
    if status in TERMINAL_STATUSES:
        return True
    if status in ACTIVE_STATUSES:
        return end_time_passed(end_time)
    if end_time and end_time_passed(end_time):
        return True
    return False


def checkin_gate(
    session: Any,
    rollcall_id: Any,
    student_no: str,
    waited_sec: float,
    timeout: float,
    gate_enabled: bool,
) -> Tuple[bool, str]:
    if not gate_enabled:
        return False, ""
    signed, total, end_time = get_signed_stats(session, rollcall_id, student_no, timeout)
    if signed is None or total is None or total <= 0:
        return False, "查不到签到人数，直接签"
    msg = "已签 {}/{}".format(signed, total)
    if signed / total > CHECKIN_RATIO or signed > CHECKIN_MIN_SIGNED:
        return False, "{}，达标开签".format(msg)
    remaining = time_remaining(end_time)
    if waited_sec >= CHECKIN_MAX_WAIT:
        return False, "{}，等待超 {}s，直接签".format(msg, CHECKIN_MAX_WAIT)
    if remaining is not None and remaining <= CHECKIN_MIN_REMAINING:
        return False, "{}，剩余 {}s，直接签".format(msg, int(remaining))
    return True, "{}，未达标继续等".format(msg)


def answer_number(session: Any, rollcall_id: Any, code: str, timeout: float) -> bool:
    url = "{}/api/rollcall/{}/answer_number_rollcall".format(BASE_URL, rollcall_id)
    payload = {"deviceId": str(uuid.uuid4()), "numberCode": str(code)}
    try:
        response = session.put(url, json=payload, timeout=timeout)
        return response.status_code == 200
    except Exception as exc:
        log("❌ 提交数字签到失败：{}".format(safe_text(exc)))
        return False


def _latlon_to_xy(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    radius = 6371000.0
    x = math.radians(lon - lon0) * radius * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * radius
    return x, y


def _xy_to_latlon(x: float, y: float, lat0: float, lon0: float) -> Tuple[float, float]:
    radius = 6371000.0
    lat = lat0 + math.degrees(y / radius)
    lon = lon0 + math.degrees(x / (radius * math.cos(math.radians(lat0))))
    return lat, lon


def _circle_intersections(
    x1: float, y1: float, d1: float, x2: float, y2: float, d2: float
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    x1, y1, d1 = float(x1), float(y1), float(d1)
    x2, y2, d2 = float(x2), float(y2), float(d2)
    distance = math.hypot(x2 - x1, y2 - y1)
    if distance < 1e-9:
        return None
    if distance > d1 + d2:
        gap = distance - (d1 + d2)
        if gap <= GPS_DISTANCE_TOLERANCE:
            adjust = gap / 2.0 + 0.1
            d1 += adjust
            d2 += adjust
        else:
            return None
    if distance < abs(d1 - d2):
        gap = abs(d1 - d2) - distance
        if gap <= GPS_DISTANCE_TOLERANCE:
            if d1 > d2:
                d1 = distance + d2 - 0.1
            else:
                d2 = distance + d1 - 0.1
        else:
            return None
    a = (d1 ** 2 - d2 ** 2 + distance ** 2) / (2 * distance)
    h = math.sqrt(max(0.0, d1 ** 2 - a ** 2))
    xm = x1 + a * (x2 - x1) / distance
    ym = y1 + a * (y2 - y1) / distance
    rx = -(y2 - y1) * (h / distance)
    ry = (x2 - x1) * (h / distance)
    return (xm + rx, ym + ry), (xm - rx, ym - ry)


def _solve_target(
    lat1: float, lon1: float, lat2: float, lon2: float, d1: float, d2: float
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    lat0 = (lat1 + lat2) / 2
    lon0 = (lon1 + lon2) / 2
    x1, y1 = _latlon_to_xy(lat1, lon1, lat0, lon0)
    x2, y2 = _latlon_to_xy(lat2, lon2, lat0, lon0)
    sols = _circle_intersections(x1, y1, d1, x2, y2, d2)
    if sols is None:
        return None
    p1 = _xy_to_latlon(sols[0][0], sols[0][1], lat0, lon0)
    p2 = _xy_to_latlon(sols[1][0], sols[1][1], lat0, lon0)
    return p1, p2


def answer_radar_auto(
    session: Any, rollcall_id: Any, student_no: str, timeout: float
) -> Tuple[bool, Optional[float], Optional[float]]:
    url = "{}/api/rollcall/{}/answer".format(BASE_URL, rollcall_id)

    def payload(lat: float, lon: float) -> Dict[str, Any]:
        return {
            "accuracy": 35,
            "altitude": 0,
            "altitudeAccuracy": None,
            "deviceId": str(uuid.uuid4()),
            "heading": None,
            "latitude": str(lat),
            "longitude": str(lon),
            "speed": None,
        }

    try:
        r1 = session.put(url, json=payload(PROBE_LAT1, PROBE_LON1), timeout=timeout)
        r2 = session.put(url, json=payload(PROBE_LAT2, PROBE_LON2), timeout=timeout)
    except Exception as exc:
        log("❌ GPS 探针请求失败：{}".format(safe_text(exc)))
        return False, None, None

    hit = None
    for response, lat, lon in (
        (r1, PROBE_LAT1, PROBE_LON1),
        (r2, PROBE_LAT2, PROBE_LON2),
    ):
        if response.status_code == 200:
            hit = (lat, lon)
    if hit is not None and check_my_checkin_status(
        session, rollcall_id, student_no, timeout
    ) == SIGNED_STUDENT_STATUS:
        log("✅ 探针命中，本人状态已确认")
        return True, hit[0], hit[1]

    try:
        d1 = response_json(r1).get("distance")
        d2 = response_json(r2).get("distance")
    except Exception:
        log("❌ 服务器未返回距离信息")
        return False, None, None
    if d1 is None or d2 is None:
        log("❌ 未获取到距离")
        return False, None, None
    log("GPS 探针距离：d1={}m d2={}m".format(d1, d2))
    sols = _solve_target(PROBE_LAT1, PROBE_LON1, PROBE_LAT2, PROBE_LON2, d1, d2)
    if sols is None:
        log("❌ 两圆无交点（已尝试误差容忍）")
        return False, None, None
    (lat_a, lon_a), (lat_b, lon_b) = sols
    for lat, lon in ((lat_a, lon_a), (lat_b, lon_b)):
        try:
            response = session.put(url, json=payload(lat, lon), timeout=timeout)
            if response.status_code == 200:
                status = check_my_checkin_status(
                    session, rollcall_id, student_no, timeout
                )
                if status == SIGNED_STUDENT_STATUS:
                    log("✅ 精确坐标命中，本人状态已确认")
                    return True, lat, lon
                log("⚠️ 坐标提交 200 但本人状态为 {}，尝试下一个".format(status))
        except Exception as exc:
            log("⚠️ 候选坐标提交异常：{}".format(safe_text(exc)))
    log("❌ 两个候选坐标均未确认成功")
    return False, None, None


def rollcall_label(rollcall: Dict[str, Any]) -> str:
    if rollcall.get("is_radar"):
        return "GPS"
    if rollcall.get("is_number"):
        return "数字"
    return "其他"


# ============================================================
# 单账号执行
# ============================================================

def run_account_dry(
    index: int, account: Dict[str, str], gate_enabled: bool, poll_seconds: int, interval: int
) -> Dict[str, Any]:
    label = mask_account_label(index)
    started = time.monotonic()
    stats = {
        "total": 4,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    log("{} 开始预演".format(label))

    stage = time.monotonic()
    log("{}[1/4] 校验账号配置与登录请求构造".format(label))
    _ = session_file_for(account["student_id"])
    login_url = "{}/api/profile".format(BASE_URL)
    log(
        "{}[1/4] ⏭️ 断网预演：将使用 xmulogin(type=3) 登录后访问 {}（{:.2f}秒）".format(
            label, login_url, time.monotonic() - stage
        )
    )
    stats["skipped"] += 1

    stage = time.monotonic()
    log("{}[2/4] 校验课程列表请求".format(label))
    log(
        "{}[2/4] ⏭️ 断网预演：POST {}/api/my-courses（{:.2f}秒）".format(
            label, BASE_URL, time.monotonic() - stage
        )
    )
    stats["skipped"] += 1

    stage = time.monotonic()
    log("{}[3/4] 校验数字/GPS 签到与门控参数".format(label))
    log(
        "{}[3/4] ⏭️ 断网预演：门控={} 比例>{:.0%} 或 >{} 人；"
        "轮询间隔={}s 本轮时长={}s；不发起取码/提交（{:.2f}秒）".format(
            label,
            "开" if gate_enabled else "关",
            CHECKIN_RATIO,
            CHECKIN_MIN_SIGNED,
            interval,
            poll_seconds,
            time.monotonic() - stage,
        )
    )
    stats["skipped"] += 1

    stage = time.monotonic()
    log("{}[4/4] 校验成功判定口径".format(label))
    log(
        "{}[4/4] ⏭️ 断网预演：成功需名单本人 rollcall_status=={}（{:.2f}秒）".format(
            label, SIGNED_STUDENT_STATUS, time.monotonic() - stage
        )
    )
    stats["skipped"] += 1

    elapsed = time.monotonic() - started
    log("{} ✅ 断网预演通过".format(label))
    log(
        "{} 统计：总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={:.2f}秒".format(
            label,
            stats["total"],
            stats["success"],
            stats["alreadyComplete"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return {
        "ok": True,
        "label": label,
        "stats": stats,
        "messages": ["断网预演通过"],
        "elapsed": elapsed,
    }


def process_rollcall(
    session: Any,
    student_no: str,
    course_name: str,
    course_id: Any,
    rollcall: Dict[str, Any],
    timeout: float,
    gate_enabled: bool,
    gate_since: Dict[Any, float],
    code_cache: Dict[Any, str],
) -> Tuple[str, str]:
    """
    返回 (outcome, message)
    outcome: success | already | wait | fail | unsupported | retry
    """
    rid = rollcall.get("id") or rollcall.get("rollcall_id")
    if not rid:
        return "unsupported", "缺少点名 id"
    is_num = bool(rollcall.get("is_number") and not rollcall.get("is_radar"))
    is_radar = bool(rollcall.get("is_radar"))
    code = None
    end_time = None
    if is_num or is_radar:
        code, _, end_time = get_rollcall_detail(session, rid, timeout)
    status = rollcall.get("status") if (is_num or is_radar) else None

    if is_terminal(status, end_time):
        if status == SIGNED_STUDENT_STATUS:
            return "already", "{} 已签到".format(course_name)
        return "already", "{} 点名已结束（{}）".format(course_name, status or "ended")

    if status is None and (is_num or is_radar):
        return "retry", "{} 暂时无法读取本人状态".format(course_name)

    rtype = rollcall_label(rollcall)
    if is_num or is_radar:
        now_ts = time.time()
        since = gate_since.setdefault(rid, now_ts)
        need_wait, gate_msg = checkin_gate(
            session, rid, student_no, now_ts - since, timeout, gate_enabled
        )
        if need_wait:
            return "wait", "{} ({}) {}".format(course_name, rtype, gate_msg)
        gate_since.pop(rid, None)
        if gate_msg:
            log("门控放行：{} {}".format(course_name, gate_msg))

    if is_num:
        if not code:
            code = get_number_code_from_timetable(
                session, rid, course_id, rollcall.get("rollcall_time"), timeout, code_cache
            )
        if not code:
            return "retry", "{} 数字码暂未获取".format(course_name)
        ok = answer_number(session, rid, code, timeout)
        if not ok:
            return "fail", "{} 数字签到提交失败".format(course_name)
        verified = check_my_checkin_status(session, rid, student_no, timeout)
        if verified == SIGNED_STUDENT_STATUS:
            return "success", "{} 数字签到成功".format(course_name)
        return "fail", "{} 数字签到未确认（状态={}）".format(course_name, verified)

    if is_radar:
        ok, _lat, _lon = answer_radar_auto(session, rid, student_no, timeout)
        if ok:
            return "success", "{} GPS 签到成功".format(course_name)
        return "fail", "{} GPS 签到失败".format(course_name)

    return "unsupported", "{} 不支持的签到类型".format(course_name)


def run_account_live(
    index: int,
    account: Dict[str, str],
    timeout: float,
    gate_enabled: bool,
    poll_seconds: int,
    interval: int,
) -> Dict[str, Any]:
    started = time.monotonic()
    stats = {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    messages: List[str] = []
    label = mask_account_label(index)

    stage = time.monotonic()
    log("{}[1/3] CAS/Cookie 登录开始".format(label))
    try:
        session, uid, display_name = do_login(
            account["student_id"], account["password"], timeout
        )
    except Exception as exc:
        stats["total"] = 1
        stats["failed"] = 1
        log("{}[1/3] ❌ {}（{:.2f}秒）".format(label, safe_text(exc), time.monotonic() - stage))
        return {
            "ok": False,
            "label": label,
            "stats": stats,
            "messages": [safe_text(exc)],
            "elapsed": time.monotonic() - started,
        }
    label = mask_account_label(index, display_name=display_name, public_id=uid)
    log("{}[1/3] ✅ 登录成功（{:.2f}秒）".format(label, time.monotonic() - stage))

    stage = time.monotonic()
    log("{}[2/3] 拉取课程列表".format(label))
    try:
        courses = get_courses(session, timeout)
    except Exception as exc:
        stats["total"] = 1
        stats["failed"] = 1
        log("{}[2/3] ❌ {}（{:.2f}秒）".format(label, safe_text(exc), time.monotonic() - stage))
        return {
            "ok": False,
            "label": label,
            "stats": stats,
            "messages": [safe_text(exc)],
            "elapsed": time.monotonic() - started,
        }
    if not courses:
        stats["total"] = 1
        stats["failed"] = 1
        log("{}[2/3] ❌ 课程列表为空（{:.2f}秒）".format(label, time.monotonic() - stage))
        return {
            "ok": False,
            "label": label,
            "stats": stats,
            "messages": ["课程列表为空"],
            "elapsed": time.monotonic() - started,
        }
    log(
        "{}[2/3] ✅ 共 {} 门课（{:.2f}秒）".format(
            label, len(courses), time.monotonic() - stage
        )
    )

    log("{}[3/3] 扫描进行中的点名并尝试签到".format(label))
    gate_since: Dict[Any, float] = {}
    code_cache: Dict[Any, str] = {}
    seen_terminal: set = set()
    unknown_retries: Dict[Any, int] = {}
    deadline = time.time() + max(0, poll_seconds)
    first_pass = True
    had_actionable_failure = False
    checked_any = False

    while first_pass or time.time() < deadline:
        first_pass = False
        for course in courses:
            cid = course.get("id")
            name = course.get("display_name") or course.get("name") or "?"
            try:
                rollcalls = get_rollcalls(session, cid, uid, timeout)
            except Exception as exc:
                log("⚠️ 获取 {} 签到列表失败：{}".format(name, safe_text(exc)))
                continue
            for rollcall in rollcalls:
                rid = rollcall.get("id") or rollcall.get("rollcall_id")
                if not rid or rid in seen_terminal:
                    continue
                checked_any = True
                stats["total"] += 1
                outcome, message = process_rollcall(
                    session,
                    account["student_id"],
                    name,
                    cid,
                    rollcall,
                    timeout,
                    gate_enabled,
                    gate_since,
                    code_cache,
                )
                if outcome == "success":
                    stats["success"] += 1
                    seen_terminal.add(rid)
                    messages.append(message)
                    log("✅ {}".format(message))
                elif outcome == "already":
                    stats["alreadyComplete"] += 1
                    seen_terminal.add(rid)
                    messages.append(message)
                    log("☑️ {}".format(message))
                elif outcome == "wait":
                    stats["skipped"] += 1
                    log("⏭️ {}".format(message))
                elif outcome == "unsupported":
                    stats["skipped"] += 1
                    seen_terminal.add(rid)
                    log("⏭️ {}".format(message))
                elif outcome == "retry":
                    retries = unknown_retries.get(rid, 0) + 1
                    unknown_retries[rid] = retries
                    if retries >= MAX_UNKNOWN_RETRIES:
                        stats["failed"] += 1
                        had_actionable_failure = True
                        seen_terminal.add(rid)
                        log("❌ {}（连续失败 {} 次）".format(message, retries))
                    else:
                        stats["skipped"] += 1
                        log("⏭️ {}，稍后重试".format(message))
                else:
                    stats["failed"] += 1
                    had_actionable_failure = True
                    messages.append(message)
                    log("❌ {}".format(message))

        if poll_seconds <= 0:
            break
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval, max(1, int(remaining))))

    if not checked_any and stats["total"] == 0:
        stats["total"] = 1
        stats["alreadyComplete"] = 1
        messages.append("当前无进行中的可处理点名")
        log("☑️ 当前无进行中的可处理点名")

    elapsed = time.monotonic() - started
    ok = not had_actionable_failure and stats["failed"] == 0
    log(
        "{} 统计：总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={:.2f}秒".format(
            label,
            stats["total"],
            stats["success"],
            stats["alreadyComplete"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return {
        "ok": ok,
        "label": label,
        "stats": stats,
        "messages": messages,
        "elapsed": elapsed,
    }


# ============================================================
# 主流程
# ============================================================

def build_notify_body(
    results: List[Dict[str, Any]], dry_run: bool, final_status: str
) -> str:
    total = len(results)
    success = sum(1 for item in results if item.get("ok"))
    failed = total - success
    lines = [
        "任务：{}".format(TASK_NAME),
        "模式：{}".format("DRY_RUN" if dry_run else "LIVE"),
        "账号总数：{}".format(total),
        "成功：{}".format(success),
        "失败：{}".format(failed),
        "最终状态：{}".format(final_status),
    ]
    for item in results:
        lines.append(
            "- {}：{}".format(
                item.get("label") or "账号",
                "成功" if item.get("ok") else "失败",
            )
        )
    return "\n".join(lines)


def main() -> int:
    start_ts = stamp_full()
    started_mono = time.monotonic()
    dry_run = truthy("XMU_AC_DRY_RUN")

    print("=" * 52, flush=True)
    print("任务：{}".format(TASK_NAME), flush=True)
    print("目录 ID：{}".format(CATALOG_ID), flush=True)
    print("开始时间：{}".format(start_ts), flush=True)
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"), flush=True)
    print("=" * 52, flush=True)

    notify_status = "pending"
    results: List[Dict[str, Any]] = []
    config_error = None

    try:
        accounts = parse_accounts()
        timeout = env_float("XMU_AC_TIMEOUT", float(HTTP_TIMEOUT), 3.0, 120.0)
        interval = env_int("XMU_AC_INTERVAL", DEFAULT_INTERVAL, 1, 600)
        poll_seconds = env_int("XMU_AC_POLL_SECONDS", DEFAULT_POLL_SECONDS, 0, 86400)
        gate_enabled = env_bool("XMU_AC_CHECKIN_GATE", CHECKIN_GATE_DEFAULT)
    except Exception as exc:
        config_error = safe_text(exc) or "配置错误"
        log("❌ 配置错误：{}".format(config_error))
        accounts = []
        timeout = float(HTTP_TIMEOUT)
        interval = DEFAULT_INTERVAL
        poll_seconds = DEFAULT_POLL_SECONDS
        gate_enabled = CHECKIN_GATE_DEFAULT

    account_count = len(accounts)
    log("账号数量：{}".format(account_count))
    if not config_error:
        log(
            "参数：timeout={}s interval={}s poll_seconds={} gate={}".format(
                timeout, interval, poll_seconds, "开" if gate_enabled else "关"
            )
        )

    if config_error:
        final_status = "CONFIG_ERROR"
        exit_code = 2
        notify_body = build_notify_body([], dry_run, final_status)
        notify_body += "\n错误：{}".format(config_error)
        notify_status = send_notification(TASK_NAME, notify_body)
    else:
        for index, account in enumerate(accounts, start=1):
            log("---------- 账号 {}/{} ----------".format(index, account_count))
            if dry_run:
                result = run_account_dry(
                    index, account, gate_enabled, poll_seconds, interval
                )
            else:
                result = run_account_live(
                    index, account, timeout, gate_enabled, poll_seconds, interval
                )
            results.append(result)

        success_accounts = sum(1 for item in results if item.get("ok"))
        failed_accounts = account_count - success_accounts
        if failed_accounts == 0:
            final_status = "DRY_RUN_SUCCESS" if dry_run else "SUCCESS"
            exit_code = 0
        elif success_accounts == 0:
            final_status = "FAILURE"
            exit_code = 1
        else:
            final_status = "PARTIAL_FAILURE"
            exit_code = 1

        notify_body = build_notify_body(results, dry_run, final_status)
        event = "dry-run" if dry_run else (
            "success" if exit_code == 0 else (
                "partial-failure" if success_accounts else "failure"
            )
        )
        log("通知事件：{}".format(event))
        notify_status = send_notification(TASK_NAME, notify_body)

    elapsed = time.monotonic() - started_mono
    finish_ts = stamp_full()
    sub_success = sum(int(item.get("stats", {}).get("success") or 0) for item in results)
    sub_fail = sum(int(item.get("stats", {}).get("failed") or 0) for item in results)
    sub_skip = sum(int(item.get("stats", {}).get("skipped") or 0) for item in results)
    sub_done = sum(
        int(item.get("stats", {}).get("alreadyComplete") or 0) for item in results
    )

    print("-" * 52, flush=True)
    log("账号结果：成功 {} / 失败 {}".format(
        sum(1 for item in results if item.get("ok")),
        sum(1 for item in results if not item.get("ok")),
    ))
    log(
        "子任务结果：成功 {} / 已完成 {} / 跳过 {} / 失败 {}".format(
            sub_success, sub_done, sub_skip, sub_fail
        )
    )
    log("总耗时：{:.2f}秒".format(elapsed))
    log("完成时间：{}".format(finish_ts))
    log("通知状态：{}".format(notify_status))
    log("最终状态：{}".format(final_status))

    summary = {
        "catalogId": CATALOG_ID,
        "task": TASK_NAME,
        "mode": "dry-run" if dry_run else "live",
        "accountTotal": account_count,
        "accountSuccess": sum(1 for item in results if item.get("ok")),
        "accountFailed": sum(1 for item in results if not item.get("ok")),
        "taskSuccess": sub_success,
        "taskAlreadyComplete": sub_done,
        "taskSkipped": sub_skip,
        "taskFailed": sub_fail,
        "dryRun": dry_run,
        "finalStatus": final_status,
        "notifyStatus": notify_status,
        "elapsedSeconds": round(elapsed, 2),
        "finishedAt": finish_ts,
        "exitCode": exit_code,
    }
    if config_error:
        summary["configError"] = config_error
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
