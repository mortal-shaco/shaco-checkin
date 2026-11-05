#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 微助教课堂签到
# cron: */3 7-22 * * 1-5
#
# 来源：Gaomengkai/weizhujiaoqiandao AsyncCheckIn.py（GPL-3.0）
# https://github.com/Gaomengkai/weizhujiaoqiandao
# 提交：c552e0194fce274d2dd2910d056d08a5c3818543
# 上游相关：AsyncQR.py（二维码仅为终端 ASCII 展示，依赖 websockets/qrcode，
# 需人工扫码，青龙无头定时任务无法完成，维护版对二维码签到明确跳过）。
#
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# 本维护版沿用上游 GPL-3.0 许可。
# Copyright (C) Gaomengkai / weizhujiaoqiandao contributors
# 完整 GPL-3.0 文本见上游仓库 LICENSE。
#
"""微助教（TeacherMate）课堂签到 - 青龙独立维护版。

功能清点（相对上游 AsyncCheckIn.py）：
- 使用 openid 调用 active_signs 查询进行中的课堂签到
- 对普通签到 POST student-sign-in（courseId/signId），按 Rank / repeat 判定成功或已签
- 可选附带经纬度（仅当同时配置 TEACHERMATE_LAT 与 TEACHERMATE_LON；移除上游硬编码西十二默认坐标）
- 从 SSR 页面解析公开姓名并原样展示
- 多账号：TEACHERMATE_OPENID 每非空行一个账号；支持 备注#openid，仅在首个 # 处分割
- 兼容别名 WZJ_OPENID
- 移除 users.json 读写、交互式 input 续期、Windows Toast、无限 2000 次守护轮询、打印 openid/原始响应
- 可选短时轮询（TEACHERMATE_WAIT_SECONDS）替代上游长驻守护
- 二维码签到（isQR）在青龙无头环境无法人工扫码，记为跳过并说明原因
- TEACHERMATE_DRY_RUN=1 完全断网预演；超时、脱敏时间轴日志、青龙通知与 TASK_SUMMARY

参数获取：用微信打开微助教学生端，在浏览器/抓包工具中复制带 openid= 的链接或纯 openid；
参考上游 README 与 yun-mu/wzj-sign-in-weixin 的获取说明。不要把 openid 发给他人或写入公开仓库。
建议 Cron：*/3 7-22 * * 1-5（按上课时间自行调整）。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "6e492a5f641ac92d",
            "scripts/teachermate_checkin.py",
            "teachermate_checkin.py",
            "candidate.py",
            "output/candidate.py",
            "AsyncCheckIn.py",
            "微助教课堂签到",
        )
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

TITLE = "微助教课堂签到"
CATALOG_ID = "6e492a5f641ac92d"
HOST = "v18.teachermate.cn"
BASE = "https://" + HOST
URL_CHECKIN = BASE + "/wechat-api/v1/class-attendance/student-sign-in"
URL_ACTIVESIGNS = BASE + "/wechat-api/v1/class-attendance/student/active_signs"
URL_REFERER_T = BASE + "/wechat-pro-ssr/student/sign?openid={}"
URL_GETNAME_T = BASE + "/wechat-pro-ssr/?openid={}&from=wzj"
URL_CHECKINREFER_T = BASE + "/wechat-pro-ssr/student/sign/list/{}"

OPENID_ENV = "TEACHERMATE_OPENID"
OPENID_ALIAS_ENV = "WZJ_OPENID"
DRY_RUN_ENV = "TEACHERMATE_DRY_RUN"
TIMEOUT_ENV = "TEACHERMATE_TIMEOUT"
DELAY_ENV = "TEACHERMATE_DELAY_SECONDS"
WAIT_ENV = "TEACHERMATE_WAIT_SECONDS"
POLL_ENV = "TEACHERMATE_POLL_INTERVAL"
LAT_ENV = "TEACHERMATE_LAT"
LON_ENV = "TEACHERMATE_LON"

DEFAULT_TIMEOUT = 15
DEFAULT_DELAY = 6
DEFAULT_WAIT = 0
DEFAULT_POLL = 30
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
    "Mozilla/5.0 (Linux; Android 11; Mi 10 Build/RKQ1.200826.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 "
    "XWEB/3165 MMWEBSDK/20210902 Mobile Safari/537.36 MMWEBID/3949 "
    "MicroMessenger/8.0.15.2020(0x28000F3D) Process/toolsmp WeChat/arm64 "
    "Weixin NetType/WIFI Language/zh_CN ABI/arm64"
)
NAME_RE = re.compile(r'name":"([^"]+)')
OPENID_URL_RE = re.compile(r"openid=([^&]+)", re.IGNORECASE)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str = "") -> None:
    if text:
        print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)
    else:
        print(flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def resolve_timeout() -> float:
    raw = env(TIMEOUT_ENV)
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(TIMEOUT_ENV)) from exc
    if value < 5 or value > 60:
        raise SafeError("{} 须在 5 到 60 秒之间".format(TIMEOUT_ENV))
    return value


def resolve_delay() -> float:
    raw = env(DELAY_ENV)
    if not raw:
        return float(DEFAULT_DELAY)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(DELAY_ENV)) from exc
    if value < 0 or value > 120:
        raise SafeError("{} 须在 0 到 120 秒之间".format(DELAY_ENV))
    return value


def resolve_wait_seconds() -> int:
    raw = env(WAIT_ENV)
    if not raw:
        return int(DEFAULT_WAIT)
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("{} 须为整数秒数".format(WAIT_ENV)) from exc
    if value < 0 or value > 600:
        raise SafeError("{} 须在 0 到 600 秒之间".format(WAIT_ENV))
    return value


def resolve_poll_interval() -> float:
    raw = env(POLL_ENV)
    if not raw:
        return float(DEFAULT_POLL)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(POLL_ENV)) from exc
    if value < 5 or value > 300:
        raise SafeError("{} 须在 5 到 300 秒之间".format(POLL_ENV))
    return value


def resolve_location() -> Optional[Tuple[str, str]]:
    lat_raw = env(LAT_ENV)
    lon_raw = env(LON_ENV)
    if not lat_raw and not lon_raw:
        return None
    if not lat_raw or not lon_raw:
        raise SafeError("{} 与 {} 须同时配置，或同时留空".format(LAT_ENV, LON_ENV))
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except ValueError as exc:
        raise SafeError("经纬度须为有效数字") from exc
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise SafeError("经纬度超出合法范围")
    # 与上游一致：提交时加微小随机抖动
    lat_text = "{:.6f}".format(lat + random.randint(-4, 4) * 0.000001)
    lon_text = "{:.6f}".format(lon + random.randint(-4, 4) * 0.000001)
    return lat_text, lon_text


def extract_openid(raw: str) -> str:
    text = raw.strip()
    if "teachermate" in text.lower() or "openid=" in text.lower():
        match = OPENID_URL_RE.search(text)
        if not match:
            raise SafeError("链接中未找到 openid 参数")
        text = urllib.parse.unquote(match.group(1)).strip()
    if not text:
        raise SafeError("openid 为空")
    if any(ord(ch) < 32 for ch in text):
        raise SafeError("openid 含控制字符")
    if len(text) > 512:
        raise SafeError("openid 过长")
    return text


def parse_account_line(text: str) -> Dict[str, str]:
    label = ""
    payload = text
    if "#" in text:
        label, payload = text.split("#", 1)
        label = compact(label, 64)
        payload = payload.strip()
    openid = extract_openid(payload)
    return {"label": label, "openid": openid}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env(OPENID_ENV) or env(OPENID_ALIAS_ENV)
    if not raw:
        raise SafeError(
            "未配置 {}；请按每个非空行填写 openid 或 备注#openid".format(OPENID_ENV)
        )
    accounts = parse_accounts(raw)
    if not accounts:
        raise SafeError("{} 没有有效账号行".format(OPENID_ENV))
    return accounts


class AccountRunner:
    def __init__(self, number: int, label: str) -> None:
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = label or str(number)

    def display(self) -> str:
        return self.identity or str(self.number)

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


class TeacherMateClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _headers(
        self, openid: str, referer: Optional[str] = None
    ) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Host": HOST,
            "openid": openid,
            "Referer": referer or URL_REFERER_T.format(openid),
        }
        return headers

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str]:
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers or {},
            method=method,
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
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise SafeError("响应解码失败") from exc
        return status, text


def parse_json_value(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception as exc:
        raise SafeError("响应不是有效 JSON") from exc


def fetch_identity(client: TeacherMateClient, openid: str) -> str:
    status, text = client.request(
        URL_GETNAME_T.format(openid),
        headers=client._headers(openid),
    )
    if status in (401, 403):
        raise SafeError("读取公开身份凭据无效")
    if status != 200:
        raise SafeError("读取公开身份失败（HTTP {}）".format(status))
    match = NAME_RE.search(text)
    if not match:
        return ""
    return compact(match.group(1), 64)


def fetch_active_signs(
    client: TeacherMateClient, openid: str
) -> List[Dict[str, Any]]:
    status, text = client.request(
        URL_ACTIVESIGNS,
        headers=client._headers(openid),
    )
    if status in (401, 403):
        raise SafeError("openid 无效或已失效")
    if status != 200:
        raise SafeError("查询进行中签到失败（HTTP {}）".format(status))
    payload = parse_json_value(text)
    if not isinstance(payload, list):
        raise SafeError("进行中签到列表结构异常")
    signs: List[Dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            signs.append(item)
    return signs


def do_checkin(
    client: TeacherMateClient,
    openid: str,
    course_id: Any,
    sign_id: Any,
    location: Optional[Tuple[str, str]],
) -> Tuple[str, str]:
    form: Dict[str, str] = {
        "courseId": str(course_id),
        "signId": str(sign_id),
    }
    if location:
        form["lat"] = location[0]
        form["lon"] = location[1]
    body = urllib.parse.urlencode(form).encode("utf-8")
    status, text = client.request(
        URL_CHECKIN,
        "POST",
        body,
        {
            **client._headers(openid, URL_CHECKINREFER_T.format(course_id)),
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE,
        },
    )
    if status in (401, 403):
        raise SafeError("签到凭据无效或已失效")
    if status != 200:
        raise SafeError("签到请求失败（HTTP {}）".format(status))
    if "Rank" in text:
        rank = ""
        try:
            payload = parse_json_value(text)
            if isinstance(payload, dict):
                rank = compact(payload.get("studentRank"), 32)
        except SafeError:
            pass
        detail = "课堂签到成功"
        if rank:
            detail += "；排名 {}".format(rank)
        return "success", detail
    if "repeat" in text:
        return "alreadyComplete", "该课堂已签到"
    raise SafeError("签到未确认业务成功")


def process_signs(
    client: TeacherMateClient,
    openid: str,
    signs: List[Dict[str, Any]],
    delay: float,
    location: Optional[Tuple[str, str]],
) -> Tuple[str, str, Dict[str, int]]:
    if not signs:
        return "alreadyComplete", "当前没有进行中的课堂签到", {
            "total": 0,
            "success": 0,
            "alreadyComplete": 0,
            "skipped": 0,
            "failure": 0,
        }

    counts = {
        "total": len(signs),
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failure": 0,
    }
    details: List[str] = []
    for index, item in enumerate(signs, 1):
        course_name = compact(item.get("name"), 64) or "未命名课堂"
        course_id = item.get("courseId")
        sign_id = item.get("signId")
        is_qr = bool(item.get("isQR"))
        if course_id is None or sign_id is None:
            counts["failure"] += 1
            details.append("{}：缺少 courseId/signId".format(course_name))
            continue
        if is_qr:
            counts["skipped"] += 1
            details.append(
                "{}：二维码签到需人工扫码，青龙定时任务已跳过".format(course_name)
            )
            log(
                "  · 签到项 {}/{} {}：{} {}".format(
                    index,
                    len(signs),
                    course_name,
                    ICONS["skipped"],
                    "二维码签到需人工扫码，已跳过",
                )
            )
            continue
        if delay > 0:
            time.sleep(delay)
        try:
            state, detail = do_checkin(
                client, openid, course_id, sign_id, location
            )
            counts[state] += 1
            details.append("{}：{}".format(course_name, detail))
            log(
                "  · 签到项 {}/{} {}：{} {}".format(
                    index, len(signs), course_name, ICONS.get(state, ""), detail
                )
            )
        except SafeError as error:
            counts["failure"] += 1
            details.append("{}：{}".format(course_name, str(error)))
            log(
                "  · 签到项 {}/{} {}：{} {}".format(
                    index, len(signs), course_name, ICONS["failure"], str(error)
                )
            )
        if index < len(signs):
            time.sleep(random.uniform(1.0, 2.0))

    if counts["failure"]:
        overall = "failure"
    elif counts["success"]:
        overall = "success"
    elif counts["alreadyComplete"] and not counts["skipped"]:
        overall = "alreadyComplete"
    elif counts["alreadyComplete"]:
        overall = "alreadyComplete"
    elif counts["skipped"] and not counts["success"] and not counts["alreadyComplete"]:
        # 仅有二维码签到被跳过：对定时任务视为失败，避免误报成功
        overall = "failure"
    else:
        overall = "failure"
    summary = "共 {} 项；成功 {}，已完成 {}，跳过 {}，失败 {}".format(
        counts["total"],
        counts["success"],
        counts["alreadyComplete"],
        counts["skipped"],
        counts["failure"],
    )
    if details:
        summary += "；" + "；".join(details[:6])
    return overall, summary, counts


def do_sign_with_wait(
    client: TeacherMateClient,
    openid: str,
    delay: float,
    wait_seconds: int,
    poll_interval: float,
    location: Optional[Tuple[str, str]],
) -> Tuple[str, str, Dict[str, Any]]:
    deadline = time.monotonic() + wait_seconds
    attempt = 0
    last_state = "alreadyComplete"
    last_detail = "当前没有进行中的课堂签到"
    last_counts: Dict[str, Any] = {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failure": 0,
    }
    while True:
        attempt += 1
        signs = fetch_active_signs(client, openid)
        state, detail, counts = process_signs(
            client, openid, signs, delay, location
        )
        last_state, last_detail, last_counts = state, detail, counts
        if state == "success":
            if attempt > 1:
                detail = "{}（轮询 {} 次后）".format(detail, attempt)
            return state, detail, counts
        if state == "failure":
            return state, detail, counts
        if wait_seconds <= 0 or time.monotonic() >= deadline:
            if wait_seconds > 0 and state == "alreadyComplete":
                detail = "{}；已等待 {} 秒仍未开始".format(detail, wait_seconds)
            return state, detail, counts
        sleep_for = min(poll_interval, max(1.0, deadline - time.monotonic()))
        time.sleep(sleep_for)
    return last_state, last_detail, last_counts


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    timeout: float,
    delay: float,
    wait_seconds: int,
    poll_interval: float,
    location: Optional[Tuple[str, str]],
    dry_run: bool,
) -> None:
    def parameter_check():
        openid = account.get("openid") or ""
        if not openid:
            raise SafeError("openid 为空")
        loc_text = "已配置" if location else "未配置"
        return (
            "success",
            "账号本地格式检查通过；地理位置 {}；等待 {} 秒".format(
                loc_text, wait_seconds
            ),
            None,
        )

    runner.stage(1, "参数检查", parameter_check)

    if dry_run:
        runner.skip(2, "读取公开身份", "断网预演：不请求身份接口")
        runner.skip(3, "查询并签到", "断网预演：不请求签到接口")
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = TeacherMateClient(timeout)
    business_state = {"state": "failure"}

    def identity_stage():
        name = fetch_identity(client, account["openid"])
        if name:
            runner.identity = name
            return "success", "公开身份：{}".format(name), {"name": name}
        # 身份读取失败不阻塞签到；仍用备注或账号序号
        return (
            "skipped",
            "未返回公开姓名，继续使用账号序号/备注",
            {"name": ""},
        )

    runner.stage(2, "读取公开身份", identity_stage)

    def sign_stage():
        state, detail, result = do_sign_with_wait(
            client,
            account["openid"],
            delay,
            wait_seconds,
            poll_interval,
            location,
        )
        business_state["state"] = state
        return state, detail, result

    runner.stage(3, "查询并签到", sign_stage)

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
        "teachermate_checkin.py",
        "candidate.py",
        "scripts/teachermate_checkin.py",
        "AsyncCheckIn.py",
        TITLE,
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
    dry_setting = env(DRY_RUN_ENV, "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    delay = float(DEFAULT_DELAY)
    wait_seconds = 0
    poll_interval = float(DEFAULT_POLL)
    location: Optional[Tuple[str, str]] = None
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("{} 配置无效，停止执行".format(DRY_RUN_ENV))
        timeout = resolve_timeout()
        delay = resolve_delay()
        wait_seconds = resolve_wait_seconds()
        poll_interval = resolve_poll_interval()
        location = resolve_location()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；签到前延时：{}秒；等待：{}秒；轮询间隔：{}秒；请求超时：{}秒".format(
                "DRY_RUN（完全断网）" if dry_run else "LIVE",
                len(accounts_data),
                int(delay) if float(delay).is_integer() else delay,
                wait_seconds,
                int(poll_interval) if float(poll_interval).is_integer() else poll_interval,
                int(timeout) if float(timeout).is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number, account.get("label") or "")
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    account,
                    timeout,
                    delay,
                    wait_seconds,
                    poll_interval,
                    location,
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
        final_label = "配置错误"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
        final_label = "部分失败"
    elif failed:
        status = "failure"
        final_label = "失败"
    elif dry_run:
        status = "dry-run"
        final_label = "DRY-RUN"
    else:
        status = "success"
        final_label = "SUCCESS"
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
