#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NDNU第二课堂签到签退
# cron: */5 7-22 * * *
#
# 来源：Dobona/NDNU-checkin main.py（MIT）
# 照片 Base64 说明参考同仓库 tools/make_img.py（MIT）；不合并 mitmproxy 插件入口、
# Windows 系统代理、安装器或启动器。
#
# MIT License
#
# Copyright (c) 2026 lacimoc
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
NDNU（宁德师范学院）第二课堂课程签到 / 签退 - 青龙维护版

功能清点（相对上游 mitmproxy 插件 main.py）：
- 查询待签到课程（filter=5）与待签退课程（filter=3）
- 读取课程详情中的签到 / 签退时间窗口与地点
- 时间窗口内上传签到照片并提交签到（type=1）或签退（type=2）
- 地点坐标可配置；默认内置校园常见地点
- 业务码 000121（已签到 / 已签退）视为已完成成功

维护改动：
- 去掉 mitmproxy / winproxy / 系统代理开关 / 常驻轮询线程 / 写本地 locations.json
- 凭据改为青龙环境变量 SESSION Cookie；照片改为环境变量 Base64（不再依赖 img.json）
- 标准库 HTTP，强制超时与业务成功判定；NDNU_DRY_RUN 完全断网预演
- 多账号每行一个；任一账号失败整体非零退出；青龙通知与时间轴日志

环境变量：
  NDNU_ACCOUNTS      必填：每行 SESSION 或 SESSION|照片Base64（仅按首个 | 分割）
  NDNU_SESSION       可选兼容：未设置 NDNU_ACCOUNTS 时使用，格式同上
  NDNU_IMG_BASE64    可选：账号行未带照片时的共用 Base64（type 固定 17）
  NDNU_LOCATIONS     可选：地点 JSON，如 {"求是楼":[纬度,经度],...}
  NDNU_TASK          可选：all / sign / signout，默认 all
  NDNU_TIMEOUT       可选：单次 HTTP 超时秒数，默认 20
  NDNU_DRY_RUN       1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

仅供学习交流与本人课程使用；请遵守学校规定，后果自负。
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
        _ql_notify_identities = ('1b92bf9b58ea5e07', 'scripts/ndnu.py', 'ndnu.py', 'ndnu')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "1b92bf9b58ea5e07"
TASK_NAME = "NDNU第二课堂签到签退"
SCRIPT_FILENAME = "ndnu_checkin.py"

NDNU_HOST = "dekt.ndnu.edu.cn"
BASE_URL = "http://{}".format(NDNU_HOST)
DEFAULT_TIMEOUT = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
IMG_UPLOAD_TYPE = "17"
DEFAULT_ACCURACY = 29.5444

DEFAULT_LOCATIONS: Dict[str, Tuple[float, float]] = {
    "求是楼": (26.661232, 119.58768),
    "操场": (26.657608, 119.59045),
    "讲堂群": (26.661919, 119.58603),
    "第一食堂": (26.6599, 119.5917),
    "图书馆": (26.6592, 119.5855),
    "体育馆": (26.6574, 119.5874),
    "求真楼": (26.660158, 119.589031),
    "逸夫实训楼": (26.657772, 119.585003),
}

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 NetType/WIFI "
    "MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090c11) XWEB/11275 Flue"
)

BEIJING = timezone(timedelta(hours=8))
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
TASK_MODES = {"all", "sign", "signout"}

ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class NdnuError(Exception):
    """业务层可读错误"""


@dataclass
class Account:
    index: int
    session: str
    img_base64: str = ""
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
    raw = os.getenv("NDNU_TIMEOUT", "").strip()
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("NDNU_TIMEOUT 必须是数字") from exc
    if value < 3 or value > 120:
        raise ValueError("NDNU_TIMEOUT 须在 3–120 之间")
    return value


def task_mode() -> str:
    raw = os.getenv("NDNU_TASK", "all").strip().lower() or "all"
    if raw not in TASK_MODES:
        raise ValueError("NDNU_TASK 仅支持 all / sign / signout")
    return raw


def get_timestamp_ms() -> int:
    return int(time.time() * 1000)


def parse_locations() -> Dict[str, Tuple[float, float]]:
    locations = dict(DEFAULT_LOCATIONS)
    raw = os.getenv("NDNU_LOCATIONS", "").strip()
    if not raw:
        return locations
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ValueError("NDNU_LOCATIONS 必须是合法 JSON 对象") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("NDNU_LOCATIONS 必须是非空 JSON 对象")
    parsed: Dict[str, Tuple[float, float]] = {}
    for name, value in data.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                parsed[name.strip()] = (float(value[0]), float(value[1]))
            except (TypeError, ValueError) as exc:
                raise ValueError("地点“{}”坐标无法解析".format(name)) from exc
        else:
            raise ValueError("地点“{}”须为 [纬度, 经度]".format(name))
    if not parsed:
        raise ValueError("NDNU_LOCATIONS 未解析到有效地点")
    return parsed


def shared_img_base64() -> str:
    return os.getenv("NDNU_IMG_BASE64", "").strip()


def parse_account_line(index: int, line: str, fallback_img: str) -> Account:
    text = line.strip()
    if not text or text.startswith("#"):
        raise ValueError("空账号行")
    if "|" in text:
        session, img = text.split("|", 1)
    else:
        session, img = text, ""
    session = session.strip()
    img = img.strip() or fallback_img
    if not session:
        raise ValueError("账号{}缺少 SESSION".format(index))
    if session.lower().startswith("session="):
        session = session.split("=", 1)[1].strip()
    return Account(index=index, session=session, img_base64=img)


def parse_accounts() -> List[Account]:
    raw = os.getenv("NDNU_ACCOUNTS", "")
    source_name = "NDNU_ACCOUNTS"
    if not raw.strip():
        raw = os.getenv("NDNU_SESSION", "")
        source_name = "NDNU_SESSION"
    if not raw.strip():
        raise ValueError(
            "缺少必填凭据 NDNU_ACCOUNTS："
            "每行一个账号，格式 SESSION 或 SESSION|照片Base64（仅按首个竖线分割）；"
            "也可兼容使用 NDNU_SESSION"
        )
    fallback_img = shared_img_base64()
    accounts: List[Account] = []
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        accounts.append(parse_account_line(len(accounts) + 1, line, fallback_img))
    if not accounts:
        raise ValueError("{} 未解析到有效账号".format(source_name))
    return accounts


def make_headers(json_content: bool = False) -> Dict[str, str]:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/",
        "Accept": "application/json, text/plain, */*",
    }
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def cookie_header(session: str) -> str:
    return "SESSION={}".format(session)


def http_json(
    method: str,
    url: str,
    *,
    session: str,
    body: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        raise RuntimeError("dry-run 禁止发起网络请求")
    headers = make_headers(json_content=body is not None)
    headers["Cookie"] = cookie_header(session)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise NdnuError("响应过大，已中止解析")
            text = raw.decode("utf-8", errors="replace") if raw else ""
            if not text:
                return {}
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise NdnuError("响应结构异常")
            return payload
    except urllib.error.HTTPError as exc:
        raise NdnuError("HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise NdnuError("网络请求失败：{}".format(safe_text(exc.reason))) from exc
    except json.JSONDecodeError as exc:
        raise NdnuError("响应不是有效 JSON") from exc


def extract_identity(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in (
        "studentName",
        "stuName",
        "nickName",
        "nickname",
        "realName",
        "userName",
        "username",
        "name",
        "displayName",
    ):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("studentId", "stuId", "userId", "uid", "id"):
        value = obj.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            text = str(value).strip()
            if len(text) <= 32 and not re.fullmatch(r"[0-9a-fA-F]{32,}", text):
                # 仅展示较短公开学号 / UID；避免像 SESSION 的长串
                if key in ("studentId", "stuId", "userId", "uid"):
                    return text
    return ""


def time_to_timestamp_ms(time_str: str) -> int:
    dt_local = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    return int(time.mktime(dt_local.timetuple()) * 1000)


def in_window(start_str: Any, end_str: Any) -> bool:
    try:
        if not start_str or not end_str:
            return False
        start_ts = time_to_timestamp_ms(str(start_str))
        end_ts = time_to_timestamp_ms(str(end_str))
        now_ts = get_timestamp_ms()
        return start_ts < now_ts < end_ts
    except (TypeError, ValueError):
        return False


def fetch_wait_courses(
    session: str, filter_code: str, timeout: float, dry_run: bool
) -> List[dict]:
    url = (
        "{}/web/student/course/findMyCoursePage"
        "?t={}&filter={}&pageNo=1&pageSize=10"
    ).format(BASE_URL, get_timestamp_ms(), filter_code)
    payload = http_json("GET", url, session=session, timeout=timeout, dry_run=dry_run)
    info = payload.get("info")
    if info is None:
        return []
    if not isinstance(info, list):
        raise NdnuError("课程列表返回格式异常")
    return [item for item in info if isinstance(item, dict)]


def get_lesson_info(
    session: str, lesson_id: Any, timeout: float, dry_run: bool
) -> dict:
    url = (
        "{}/web/student/courseExt/getStudentCourseDetail?t={}&id={}"
    ).format(BASE_URL, get_timestamp_ms(), lesson_id)
    payload = http_json("GET", url, session=session, timeout=timeout, dry_run=dry_run)
    info = payload.get("info")
    return info if isinstance(info, dict) else {}


def upload_img(
    session: str, img_base64: str, timeout: float, dry_run: bool, max_attempts: int = 3
) -> str:
    if not img_base64:
        raise NdnuError("缺少签到照片 Base64（请在账号行或 NDNU_IMG_BASE64 配置）")
    body = {"base64": img_base64, "type": IMG_UPLOAD_TYPE}
    url = "{}/web/weixin/upload/uploadFile?t={}".format(BASE_URL, get_timestamp_ms())
    last_error = "照片上传失败"
    for attempt in range(1, max_attempts + 1):
        try:
            payload = http_json(
                "POST", url, session=session, body=body, timeout=timeout, dry_run=dry_run
            )
            if payload.get("status") is True and payload.get("info"):
                return str(payload["info"])
            last_error = "照片上传未确认成功"
        except NdnuError as exc:
            last_error = safe_text(exc)
        if attempt < max_attempts:
            time.sleep(1)
    raise NdnuError(last_error)


def do_sign(
    session: str, payload: dict, timeout: float, dry_run: bool, max_attempts: int = 3
) -> Tuple[str, str]:
    """返回 (outcome, message)；outcome 为 success / alreadyComplete / failure。"""
    url = "{}/web/student/course/doSign?t={}".format(BASE_URL, get_timestamp_ms())
    last_error = "签到 / 签退请求失败"
    for attempt in range(1, max_attempts + 1):
        try:
            resp = http_json(
                "POST",
                url,
                session=session,
                body=payload,
                timeout=timeout,
                dry_run=dry_run,
            )
            if resp.get("status") is True:
                return "success", "服务器确认成功"
            if str(resp.get("code", "")) == "000121":
                return "alreadyComplete", "服务器提示已签到 / 签退过（000121）"
            last_error = "服务器未确认成功"
        except NdnuError as exc:
            last_error = safe_text(exc)
        if attempt < max_attempts:
            time.sleep(1)
    return "failure", last_error


def notification_allowed(no_notify: bool = False) -> bool:
    if no_notify:
        return False
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    # auto
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
        "ndnu.py",
        "ndnu",
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
            spec = importlib.util.spec_from_file_location("ql_notify_ndnu", str(path))
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


def handle_courses(
    account: Account,
    courses: List[dict],
    sign_type: str,
    locations: Dict[str, Tuple[float, float]],
    timeout: float,
    dry_run: bool,
    stats: StageStats,
) -> List[str]:
    errors: List[str] = []
    if not courses:
        return errors
    label = "签到" if sign_type == "1" else "签退"
    start_field = "signStartTimeStr" if sign_type == "1" else "signOutStartTimeStr"
    end_field = "signEndTimeStr" if sign_type == "1" else "signOutEndTimeStr"

    for lesson in courses:
        stats.total += 1
        lesson_id = lesson.get("id")
        course_name = safe_text(
            lesson.get("courseName")
            or lesson.get("name")
            or lesson.get("title")
            or "课程{}".format(lesson_id)
        )
        if not lesson_id:
            stats.failed += 1
            errors.append("{}缺少课程 id".format(label))
            continue

        if not account.display_name:
            identity = extract_identity(lesson)
            if identity:
                account.display_name = identity
                log("{} 公开身份：{}".format(ICONS["success"], identity))

        if dry_run:
            stats.skipped += 1
            log(
                "{} 预演计划{}：{}（课程 {}）".format(
                    ICONS["skipped"], label, course_name, lesson_id
                )
            )
            continue

        try:
            info = get_lesson_info(account.session, lesson_id, timeout, dry_run)
        except NdnuError as exc:
            stats.failed += 1
            errors.append("{}详情失败：{}".format(course_name, safe_text(exc)))
            continue

        if not account.display_name:
            identity = extract_identity(info)
            if identity:
                account.display_name = identity
                log("{} 公开身份：{}".format(ICONS["success"], identity))

        if not in_window(info.get(start_field), info.get(end_field)):
            stats.skipped += 1
            log(
                "{} {} 未到时间窗口，本轮跳过".format(ICONS["skipped"], course_name)
            )
            continue

        location = info.get("location")
        if not location:
            stats.failed += 1
            errors.append("{}未返回地点".format(course_name))
            log("{} {} 未返回地点".format(ICONS["failure"], course_name))
            continue
        if location not in locations:
            stats.failed += 1
            msg = "地点“{}”不在 NDNU_LOCATIONS / 内置地点中".format(location)
            errors.append("{}：{}".format(course_name, msg))
            log("{} {} {}".format(ICONS["failure"], course_name, msg))
            continue

        latitude, longitude = locations[location]
        try:
            img_url = upload_img(account.session, account.img_base64, timeout, dry_run)
            log("{} {} 照片上传成功".format(ICONS["success"], course_name))
        except NdnuError as exc:
            stats.failed += 1
            errors.append("{}照片失败：{}".format(course_name, safe_text(exc)))
            log("{} {} 照片上传失败".format(ICONS["failure"], course_name))
            continue

        payload = {
            "accuracy": DEFAULT_ACCURACY,
            "courseId": lesson_id,
            "imgUrl": img_url,
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "type": sign_type,
        }
        log(
            "{} 时间窗口内开始{}：{} @ {}".format(
                ICONS["warning"], label, course_name, location
            )
        )
        outcome, message = do_sign(account.session, payload, timeout, dry_run)
        if outcome == "success":
            stats.success += 1
            log("{} {}{}成功".format(ICONS["success"], course_name, label))
        elif outcome == "alreadyComplete":
            stats.alreadyComplete += 1
            log("{} {}{}".format(ICONS["alreadyComplete"], course_name, message))
        else:
            stats.failed += 1
            errors.append("{}{}失败：{}".format(course_name, label, message))
            log("{} {}{}失败".format(ICONS["failure"], course_name, label))
    return errors


def run_account(
    account: Account,
    locations: Dict[str, Tuple[float, float]],
    mode: str,
    timeout: float,
    dry_run: bool,
) -> dict:
    t0 = time.time()
    stats = StageStats()
    errors: List[str] = []
    log("-" * 48)
    log("开始处理 {}".format(account.label))

    if dry_run:
        stage_no = 1
        log("阶段{}：断网预演校验".format(stage_no))
        log(
            "{} DRY_RUN_OK：账号配置有效；任务模式={}；地点 {} 个；照片={}".format(
                ICONS["success"],
                mode,
                len(locations),
                "已配置" if account.img_base64 else "未配置",
            )
        )
        if mode in ("all", "sign"):
            stats.total += 1
            stats.skipped += 1
            log("{} 预演计划：查询待签到并在窗口内签到".format(ICONS["skipped"]))
        if mode in ("all", "signout"):
            stats.total += 1
            stats.skipped += 1
            log("{} 预演计划：查询待签退并在窗口内签退".format(ICONS["skipped"]))
        # 无照片时在正式运行会失败；预演给出警告但仍算配置通过（SESSION 已具备）
        if not account.img_base64:
            log(
                "{} 未配置照片 Base64：正式运行若进入签到窗口将失败".format(
                    ICONS["warning"]
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

    stage_no = 1
    sign_courses: List[dict] = []
    out_courses: List[dict] = []

    if mode in ("all", "sign"):
        fetched, _, err = run_stage(
            stage_no,
            "查询待签到课程",
            lambda: fetch_wait_courses(account.session, "5", timeout, dry_run),
        )
        stage_no += 1
        if err:
            errors.append(err)
            stats.total += 1
            stats.failed += 1
        else:
            sign_courses = fetched or []
            log("{} 待签到课程 {} 门".format(ICONS["success"], len(sign_courses)))

    if mode in ("all", "signout"):
        fetched, _, err = run_stage(
            stage_no,
            "查询待签退课程",
            lambda: fetch_wait_courses(account.session, "3", timeout, dry_run),
        )
        stage_no += 1
        if err:
            errors.append(err)
            stats.total += 1
            stats.failed += 1
        else:
            out_courses = fetched or []
            log("{} 待签退课程 {} 门".format(ICONS["success"], len(out_courses)))

    if mode in ("all", "sign") and sign_courses:
        log("阶段{}：处理签到".format(stage_no))
        errors.extend(
            handle_courses(
                account, sign_courses, "1", locations, timeout, dry_run, stats
            )
        )
        stage_no += 1
    elif mode in ("all", "sign"):
        log("{} 无待签到课程".format(ICONS["alreadyComplete"]))

    if mode in ("all", "signout") and out_courses:
        log("阶段{}：处理签退".format(stage_no))
        errors.extend(
            handle_courses(
                account, out_courses, "2", locations, timeout, dry_run, stats
            )
        )
    elif mode in ("all", "signout"):
        log("{} 无待签退课程".format(ICONS["alreadyComplete"]))

    if stats.total == 0 and not errors:
        # 本轮无可执行课程：记为跳过成功
        stats.total = 1
        stats.skipped = 1
        log("{} 本轮无需签到 / 签退动作".format(ICONS["skipped"]))

    stats.elapsedMs = int((time.time() - t0) * 1000)
    success = stats.failed == 0 and not errors
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
        "success": success,
        "outcome": "success" if success else "failure",
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
    dry_run = truthy_env("NDNU_DRY_RUN")
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
    locations: Dict[str, Tuple[float, float]] = dict(DEFAULT_LOCATIONS)
    mode = "all"
    timeout = float(DEFAULT_TIMEOUT)

    try:
        timeout = env_timeout()
        mode = task_mode()
        locations = parse_locations()
        accounts = parse_accounts()
    except Exception as exc:
        config_error = safe_text(exc)
        log("{} 配置错误：{}".format(ICONS["failure"], config_error))
        exit_code = 2
        final_status = "CONFIG_ERROR"
        accounts = []

    log("账号数量：{}".format(len(accounts)))
    if accounts and not config_error:
        log("任务开关：{}".format(mode))
        log("地点数量：{}".format(len(locations)))

    if accounts and not config_error:
        for account in accounts:
            try:
                results.append(
                    run_account(account, locations, mode, timeout, dry_run)
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
