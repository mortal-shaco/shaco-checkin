#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 头歌平台课堂签到
# cron: 54 8,10,14,16 * * 1-5
#
# 来源：relaxcn/educoder_auto_signin src/sign.py（GPL-3.0）
# https://github.com/relaxcn/educoder_auto_signin
# 上游衍生自 easechen/educoder_auto_signin
# 提交：33bf230d1377c8e67477c52c36bcff719f328767
#
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# 本维护版沿用上游 GPL-3.0 许可。
# Copyright (C) easechen / relaxcn / educoder_auto_signin contributors
# 完整 GPL-3.0 文本见上游仓库 LICENSE。
#
"""头歌（Educoder）课堂签到 - 青龙维护版。

功能清点（相对上游 src/sign.py）：
- POST /api/accounts/login.json 使用账号密码登录，读取 name / school / login / user_id
- 按配置的课程 ID 查询课堂考勤列表，对进行中的考勤提交签到码
- 支持查询考勤历史（只读）；可选短时轮询等待考勤开始（替代上游无限交互等待）
- 移除交互式 input()、硬编码示例凭据、无超时请求与无限阻塞轮询
- 增加逐行多账号、EDUCODER_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

EDUCODER_ACCOUNTS：每个非空行一个账号，格式 登录名#密码 或 登录名#密码#课程ID；
仅在第一个 # 处分割登录名，再在剩余部分的第一个 # 处分割密码与可选课程 ID。
兼容单账号别名：EDUCODER_USER + EDUCODER_PASSWORD（可选 EDUCODER_COURSE_ID）。
EDUCODER_COURSE_ID：全局课程 ID，账号行未带课程 ID 时使用。
EDUCODER_ACTION：sign（默认）或 history。
EDUCODER_WAIT_SECONDS：无进行中考勤时最多等待秒数，默认 0（只尝试一次）。
EDUCODER_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
EDUCODER_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：5 8,10,14,16 * * 1-5（按课堂时间自行调整）。
不打印密码、Cookie、Token 或原始响应；官方返回的姓名作为公开身份直接展示。
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
        _ql_notify_identities = ('56a92f26b6487e35', 'scripts/educoder.py', 'educoder.py', 'educoder')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import json
import os
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

TITLE = "头歌平台课堂签到"
CATALOG_ID = "56a92f26b6487e35"
BASE = "https://data.educoder.net"
LOGIN_API = BASE + "/api/accounts/login.json"
SIGN_API = BASE + "/api/weapps/course_member_attendances.json"
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
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/89.0.4389.90 Safari/537.36"
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
    raw = env("EDUCODER_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("EDUCODER_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("EDUCODER_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_wait_seconds() -> int:
    raw = env("EDUCODER_WAIT_SECONDS")
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("EDUCODER_WAIT_SECONDS 须为整数秒数") from exc
    if value < 0 or value > 600:
        raise SafeError("EDUCODER_WAIT_SECONDS 须在 0 到 600 秒之间")
    return value


def resolve_action() -> str:
    raw = env("EDUCODER_ACTION", "sign").lower() or "sign"
    if raw not in {"sign", "history"}:
        raise SafeError("EDUCODER_ACTION 仅支持 sign 或 history")
    return raw


def parse_account_line(text: str, default_course: str) -> Dict[str, str]:
    if "#" not in text:
        raise SafeError("账号行缺少分隔符；格式为 登录名#密码 或 登录名#密码#课程ID")
    login, rest = text.split("#", 1)
    login = login.strip()
    course_id = default_course
    if "#" in rest:
        password, course_part = rest.split("#", 1)
        password = password.strip()
        course_part = course_part.strip()
        if course_part:
            course_id = course_part
    else:
        password = rest.strip()
    if not login or not password:
        raise SafeError("登录名或密码为空")
    if any(ord(ch) < 32 for ch in login) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    return {"login": login, "password": password, "course_id": course_id}


def parse_accounts(raw: str, default_course: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text, default_course))
    return accounts


def load_accounts() -> Tuple[List[Dict[str, str]], str]:
    action = resolve_action()
    default_course = env("EDUCODER_COURSE_ID")
    raw = env("EDUCODER_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw, default_course)
        if not accounts:
            raise SafeError("EDUCODER_ACCOUNTS 没有有效账号行")
    else:
        login = env("EDUCODER_USER") or env("EDUCODER_LOGIN")
        password = env("EDUCODER_PASSWORD") or env("EDUCODER_PASSWD")
        if login or password:
            if not login or not password:
                raise SafeError(
                    "兼容别名需同时提供 EDUCODER_USER 与 EDUCODER_PASSWORD；"
                    "推荐改用 EDUCODER_ACCOUNTS（登录名#密码）"
                )
            accounts = [
                {
                    "login": login,
                    "password": password,
                    "course_id": default_course,
                }
            ]
        else:
            raise SafeError(
                "未配置 EDUCODER_ACCOUNTS；请按每个非空行 登录名#密码 填写"
            )
    if action in {"sign", "history"}:
        missing = [str(i) for i, a in enumerate(accounts, 1) if not a.get("course_id")]
        if missing:
            raise SafeError(
                "缺少课程 ID：请设置 EDUCODER_COURSE_ID，"
                "或在账号行使用 登录名#密码#课程ID（缺失账号序号：{}）".format(
                    ",".join(missing)
                )
            )
    return accounts, action


class AccountRunner:
    def __init__(self, number: int, login: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = compact(login, 64)

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


class EducoderClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.ProxyHandler({}),
        )

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, Dict[str, str]]:
        base_headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
        }
        if headers:
            base_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=data,
            headers=base_headers,
            method=method,
        )
        response_headers: Dict[str, str] = {}
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read(MAX_BYTES + 1)
                response_headers = {k.lower(): v for k, v in response.headers.items()}
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
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise SafeError("响应解码失败") from exc
        return status, text, response_headers

    def has_session_cookie(self) -> bool:
        names = {getattr(cookie, "name", "") for cookie in self.jar}
        return "_educoder_session" in names or "autologin_trustie" in names


def parse_json_object(text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise SafeError("响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise SafeError("响应 JSON 结构异常")
    return payload


def do_login(
    client: EducoderClient, login: str, password: str
) -> Tuple[str, str, Dict[str, Any]]:
    body = urllib.parse.urlencode(
        {
            "login": login,
            "password": password,
            "autologin": "true",
        }
    ).encode("utf-8")
    status, text, _headers = client.request(
        LOGIN_API,
        "POST",
        body,
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.educoder.net",
            "Referer": "https://www.educoder.net/",
        },
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status != 200:
        raise SafeError("登录请求失败（HTTP {}）".format(status))
    if "user_id" not in text:
        message = "登录未确认业务成功"
        try:
            payload = parse_json_object(text)
            msg = compact(payload.get("message"), 80)
            if msg:
                message = "登录失败：{}".format(msg)
        except SafeError:
            pass
        raise SafeError(message)
    payload = parse_json_object(text)
    if "user_id" not in payload:
        raise SafeError("登录响应缺少 user_id")
    if not client.has_session_cookie():
        raise SafeError("登录未获得有效会话 Cookie")
    name = compact(payload.get("name"), 64)
    school = compact(payload.get("school"), 64)
    login_name = compact(payload.get("login") or login, 64)
    user_id = compact(payload.get("user_id"), 32)
    identity = name or login_name
    detail_parts = ["登录成功"]
    if identity:
        detail_parts.append("公开身份：{}".format(identity))
    if school:
        detail_parts.append("学校：{}".format(school))
    if user_id:
        detail_parts.append("UID：{}".format(user_id))
    return (
        "success",
        "；".join(detail_parts),
        {
            "identity": identity,
            "login": login_name,
            "school": school,
            "user_id": user_id,
        },
    )


def fetch_attendances(
    client: EducoderClient, course_id: str
) -> Dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "coursesId": course_id,
            "id": course_id,
            "status": "all",
            "page": "1",
        }
    )
    url = "{}/api/courses/{}/attendances.json?{}".format(BASE, course_id, query)
    status, text, _headers = client.request(
        url,
        "GET",
        headers={"Referer": "https://www.educoder.net/"},
    )
    if status in (401, 403):
        raise SafeError("考勤列表凭据无效或会话已过期")
    if status != 200:
        raise SafeError("查询考勤列表失败（HTTP {}）".format(status))
    payload = parse_json_object(text)
    attendances = payload.get("attendances")
    if not isinstance(attendances, list):
        raise SafeError("考勤列表结构异常")
    return payload


def do_history(
    client: EducoderClient, course_id: str
) -> Tuple[str, str, Dict[str, Any]]:
    payload = fetch_attendances(client, course_id)
    attendances = payload.get("attendances") or []
    count = len(attendances)
    if count == 0:
        return "alreadyComplete", "考勤历史为空", {"count": 0}
    latest = attendances[0] if isinstance(attendances[0], dict) else {}
    date = compact(latest.get("attendance_date"), 32)
    detail = "已读取考勤历史 {} 条".format(count)
    if date:
        detail += "；最近日期 {}".format(date)
    return "success", detail, {"count": count}


def pick_active_attendance(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    attendances = payload.get("attendances") or []
    if not attendances:
        return None
    first = attendances[0]
    if not isinstance(first, dict):
        return None
    if compact(first.get("status")).lower() == "history":
        return None
    return first


def do_sign_once(
    client: EducoderClient, course_id: str
) -> Tuple[str, str, Dict[str, Any]]:
    payload = fetch_attendances(client, course_id)
    active = pick_active_attendance(payload)
    if active is None:
        return "alreadyComplete", "当前没有进行中的课堂签到", {"active": False}

    attendance_id = active.get("id")
    attendance_mode = active.get("mode")
    code = active.get("attendance_code")
    if attendance_id is None or attendance_mode is None or code is None:
        raise SafeError("进行中考勤缺少必要字段")

    form = urllib.parse.urlencode(
        {
            "attendance_id": str(attendance_id),
            "attendance_mode": str(attendance_mode),
            "code": str(code),
        }
    ).encode("utf-8")
    status, text, _headers = client.request(
        SIGN_API,
        "POST",
        form,
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.educoder.net",
            "Referer": "https://www.educoder.net/",
        },
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或会话已过期")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if "success" not in text:
        raise SafeError("签到未确认业务成功")
    return "success", "课堂签到成功", {"active": True, "attendance_id": attendance_id}


def do_sign_with_wait(
    client: EducoderClient, course_id: str, wait_seconds: int
) -> Tuple[str, str, Dict[str, Any]]:
    deadline = time.monotonic() + wait_seconds
    attempt = 0
    while True:
        attempt += 1
        state, detail, result = do_sign_once(client, course_id)
        if state == "success":
            if attempt > 1:
                detail = "{}（轮询 {} 次后）".format(detail, attempt)
            return state, detail, result
        if wait_seconds <= 0 or time.monotonic() >= deadline:
            if wait_seconds > 0:
                detail = "{}；已等待 {} 秒仍未开始".format(detail, wait_seconds)
            return state, detail, result
        time.sleep(1)


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    wait_seconds: int,
    action: str,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["login"] or not account["password"]:
            raise SafeError("登录名或密码为空")
        if not account.get("course_id"):
            raise SafeError("课程 ID 为空")
        course = compact(account["course_id"], 32)
        return (
            "success",
            "账号本地格式检查通过；课程 ID {}；动作 {}".format(course, action),
            None,
        )

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "登录", "断网预演：不请求登录接口")
        if action == "history":
            runner.skip(3, "查询考勤历史", "断网预演：不请求考勤接口")
        else:
            runner.skip(3, "执行课堂签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = EducoderClient(timeout)
    business_state = {"state": "failure"}

    def login_stage():
        state, detail, result = do_login(
            client, account["login"], account["password"]
        )
        if isinstance(result, dict):
            identity = str(result.get("identity") or "")
            if identity:
                runner.identity = identity
        return state, detail, result

    runner.stage(2, "登录", login_stage)

    if action == "history":

        def history_stage():
            state, detail, result = do_history(client, account["course_id"])
            business_state["state"] = state
            return state, detail, result

        runner.stage(3, "查询考勤历史", history_stage)
    else:

        def sign_stage():
            state, detail, result = do_sign_with_wait(
                client, account["course_id"], wait_seconds
            )
            business_state["state"] = state
            return state, detail, result

        runner.stage(3, "执行课堂签到", sign_stage)

    if runner.stats["failure"] or business_state["state"] == "failure":
        runner.status = "failure"
    elif business_state["state"] == "alreadyComplete":
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
        "educoder_signin.py",
        "candidate.py",
        "scripts/educoder_signin.py",
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
    if dry_run:
        log("通知：⏭️ 断网预演仅生成脱敏摘要，不投递外部通知")
        log("通知摘要：" + body)
        return "dry-run-skipped"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": False,
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
                log("通知：✅ 脱敏总结已交给青龙适配器")
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用或投递失败；保留业务退出码")
    return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("EDUCODER_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    wait_seconds = 0
    action = "sign"
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("EDUCODER_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        wait_seconds = resolve_wait_seconds()
        accounts_data, action = load_accounts()
        log(
            "运行模式：{}；账号数：{}；动作：{}；等待：{}秒；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                action,
                wait_seconds,
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number, account["login"])
            accounts.append(runner)
            try:
                run_account(
                    runner, account, timeout, wait_seconds, action, dry_run
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
        final_label = "配置错误"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
        final_label = "部分失败"
    elif failed:
        status = "failure"
        final_label = "失败"
    elif dry_run:
        status = "dry-run"
        final_label = "预演完成"
    else:
        status = "success"
        final_label = "成功"
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
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
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
                "action": action,
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
