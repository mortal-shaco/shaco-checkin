#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 智慧树共享课每日习惯分
# cron: 20 7 * * *
# SPDX-License-Identifier: MIT
"""
智慧树共享课 · 每日习惯分（学习时长上报）- 青龙维护版

基于 eplayn/zhihuishu-toolkit（MIT）internal/_共享课_每日习惯分.py 维护。
上游能力：校验登录态、选择视频、按前端节奏分批上报约 25 分钟学习时长以获取每日习惯分。

本维护版改动：
  - 去除交互式二维码扫码、本地 capture/ 会话文件与 os.startfile 弹窗；
  - 凭据改为环境变量，多账号每行一个（Cookie|recruitAndCourseId）；
  - 增加 ZHS_HABIT_DRY_RUN 完全断网预演、超时、业务成功判定；
  - 脱敏时间轴日志、TASK_SUMMARY、青龙通知策略；
  - 同仓库登录脚本仅作 Cookie 获取说明，不并入本定时任务；
  - 共享课全量刷视频 / 自动作业周期与风险不同，保持独立，不合并。

参数：
ZHS_HABIT_ACCOUNTS：必填。每行一个账号，格式 Cookie|recruitAndCourseId，
  或 备注|Cookie|recruitAndCourseId。Cookie 需含 jt-cas、CASLOGC 等登录态。
  浏览器登录智慧树学习页后，在开发者工具网络面板复制同域请求头 Cookie；
  recruitAndCourseId 来自共享课学习页 URL 的 recruitAndCourseId 参数。
ZHS_HABIT_COOKIE / ZHS_HABIT_RAC：单账号兼容别名（二者同时提供）。
ZHS_HABIT_MINUTES：每日目标分钟数，默认 25。
ZHS_HABIT_CHUNK：单批上报秒数，默认 540。
ZHS_HABIT_SPEED：假定倍速，默认 1.8（影响 watchPoint 密度）。
ZHS_HABIT_FORCE：设为 1 时忽略「今日已完成」本地状态，强制再跑。
ZHS_HABIT_STATE_FILE：可选本地状态文件路径，记录每日完成情况。
ZHS_HABIT_TIMEOUT：单次请求超时秒数，默认 25。
ZHS_HABIT_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：见契约。

MIT License

Copyright (c) eplayn / zhihuishu-toolkit contributors

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('887bba5f8efd3762', 'scripts/internal.py', 'internal.py', 'internal')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "智慧树共享课每日习惯分"
CATALOG_ID = "887bba5f8efd3762"
API_HOST = "studyservice-api.zhihuishu.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)
IV = b"1g3qqdh4jvbskb9x"
VIDEO_KEY = b"azp53h0kft7qi78q"
EV_KEY = "zzpttjd"
REPORT_EVERY = 300.0
SAMPLE_MS = 1.99
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}

SCRIPT_DIR = Path(__file__).resolve().parent


class TaskError(Exception):
    """配置或任务级错误。"""


class AccountError(Exception):
    """单账号业务失败。"""


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(name: str) -> bool:
    return env(name).lower() in TRUE_VALUES


def safe_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"(?i)(cookie|token|authorization|jt-cas|castgc|caslogc)\s*[:=]\s*([^\s;]+)",
        r"\1=[REDACTED]",
        text,
    )
    return text[:limit] if text else "未提供业务消息"


def hhmmss(seconds: float) -> str:
    value = int(max(0, seconds))
    return "%02d:%02d:%02d" % (value // 3600, value % 3600 // 60, value % 60)


def parse_timeout() -> float:
    raw = env("ZHS_HABIT_TIMEOUT", "25") or "25"
    try:
        value = float(raw)
    except ValueError as exc:
        raise TaskError("ZHS_HABIT_TIMEOUT 必须是数字秒数") from exc
    if value < 5 or value > 120:
        raise TaskError("ZHS_HABIT_TIMEOUT 必须在 5 到 120 秒之间")
    return value


def parse_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = env(name, str(default)) or str(default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise TaskError("{} 必须是数字".format(name)) from exc
    if value < minimum or value > maximum:
        raise TaskError("{} 必须在 {} 到 {} 之间".format(name, minimum, maximum))
    return value


def account_fingerprint(cookie: str) -> str:
    digest = base64.urlsafe_b64encode(
        (cookie[:48] + "|" + str(len(cookie))).encode("utf-8")
    ).decode("ascii")
    return digest[:24]


def extract_uuid(cookie: str) -> str:
    match = re.search(r"CASLOGC=([^;]+)", cookie)
    if not match:
        return ""
    try:
        payload = urllib.parse.unquote(match.group(1))
        data = json.loads(payload)
        uuid = str(data.get("uuid") or "").strip()
        return uuid
    except Exception:
        return ""


def jwt_exp(token: str) -> Optional[float]:
    try:
        part = token.split(".")[1]
        padded = part + "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(padded)).get("exp")
    except Exception:
        return None


def load_accounts() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    raw = os.environ.get("ZHS_HABIT_ACCOUNTS", "")
    if raw.strip():
        for line_no, line in enumerate(raw.splitlines(), 1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = [part.strip() for part in text.split("|")]
            if len(parts) < 2:
                raise TaskError(
                    "ZHS_HABIT_ACCOUNTS 第 {} 行格式无效，需要 Cookie|recruitAndCourseId".format(
                        line_no
                    )
                )
            if len(parts) == 2:
                remark, cookie, rac = "", parts[0], parts[1]
            else:
                remark, cookie, rac = parts[0], "|".join(parts[1:-1]).strip(), parts[-1]
            if not cookie or not rac:
                raise TaskError(
                    "ZHS_HABIT_ACCOUNTS 第 {} 行缺少 Cookie 或 recruitAndCourseId".format(
                        line_no
                    )
                )
            if rac.startswith("<") and rac.endswith(">"):
                raise TaskError(
                    "ZHS_HABIT_ACCOUNTS 第 {} 行 recruitAndCourseId 仍是占位符".format(
                        line_no
                    )
                )
            accounts.append(
                {
                    "remark": remark,
                    "cookie": cookie,
                    "rac": rac,
                    "fingerprint": account_fingerprint(cookie),
                }
            )
    else:
        cookie = env("ZHS_HABIT_COOKIE")
        rac = env("ZHS_HABIT_RAC")
        if cookie or rac:
            if not cookie or not rac:
                raise TaskError("单账号模式需同时提供 ZHS_HABIT_COOKIE 与 ZHS_HABIT_RAC")
            if rac.startswith("<") and rac.endswith(">"):
                raise TaskError("ZHS_HABIT_RAC 仍是占位符，请填写真实 recruitAndCourseId")
            accounts.append(
                {
                    "remark": env("ZHS_HABIT_REMARK"),
                    "cookie": cookie,
                    "rac": rac,
                    "fingerprint": account_fingerprint(cookie),
                }
            )
    if not accounts:
        raise TaskError(
            "未配置账号：请设置 ZHS_HABIT_ACCOUNTS（每行 Cookie|recruitAndCourseId），"
            "或同时设置 ZHS_HABIT_COOKIE 与 ZHS_HABIT_RAC"
        )
    return accounts


def state_path() -> Path:
    custom = env("ZHS_HABIT_STATE_FILE")
    if custom:
        return Path(custom)
    return SCRIPT_DIR / "zhihuishu_habit_state.json"


def load_state() -> Dict[str, Any]:
    path = state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(data: Dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def pkcs7(raw: bytes) -> bytes:
    n = 16 - len(raw) % 16
    return raw + bytes([n]) * n


def aes_enc(obj: Dict[str, Any]) -> str:
    from Crypto.Cipher import AES  # type: ignore

    raw = pkcs7(
        json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    return base64.b64encode(AES.new(VIDEO_KEY, AES.MODE_CBC, IV).encrypt(raw)).decode()


def ev_encode(arr: List[Any]) -> str:
    text = ";".join(str(item) for item in arr)
    out: List[str] = []
    for index, ch in enumerate(text):
        n = ord(ch) ^ ord(EV_KEY[index % len(EV_KEY)])
        h = format(n, "x")
        if len(h) < 2:
            h = "0" + h
        out.append(h[-4:])
    return "".join(out)


class WatchPoint:
    def __init__(self) -> None:
        self.wp = ["0", "1"]

    def add(self, value: float) -> None:
        self.wp.append(str(int(max(0, value) // 5) + 2))

    def get(self) -> str:
        return ",".join(self.wp)


def import_http() -> Any:
    try:
        from curl_cffi import requests as cr  # type: ignore
    except ImportError as exc:
        raise AccountError("缺少依赖：请安装 curl_cffi（pip install curl_cffi）") from exc
    return cr


def make_session(cookie: str, timeout: float) -> Any:
    cr = import_http()
    session = cr.Session(impersonate="chrome", timeout=timeout)
    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://studyvideoh5.zhihuishu.com",
            "Referer": "https://studyvideoh5.zhihuishu.com/",
            "sec-ch-ua": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Cookie": cookie,
        }
    )
    return session


def api_call(session: Any, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    stamp = int(time.time()) * 1000
    body = dict(payload)
    body["dateFormate"] = stamp
    form = {"secretStr": aes_enc(body), "dateFormate": str(stamp)}
    try:
        response = session.post("https://%s%s" % (API_HOST, path), data=form)
    except Exception as exc:
        return {"code": -999, "message": "网络异常 %s" % safe_text(exc)}
    try:
        data = json.loads(response.text)
        return data if isinstance(data, dict) else {"code": -998, "message": "响应非对象"}
    except Exception:
        return {"code": -998, "message": "响应非 JSON"}


def build_ctx(session: Any, rac: str) -> Dict[str, Any]:
    course = api_call(
        session, "/gateway/t/v1/learning/queryCourse", {"recruitAndCourseId": rac}
    )
    if course.get("code") != 0:
        raise AccountError(
            "queryCourse 失败：code={} {}".format(
                course.get("code"), safe_text(course.get("message"))
            )
        )
    videos_resp = api_call(
        session, "/gateway/t/v1/learning/videolist", {"recruitAndCourseId": rac}
    )
    if videos_resp.get("code") != 0:
        raise AccountError(
            "videolist 失败：code={} {}".format(
                videos_resp.get("code"), safe_text(videos_resp.get("message"))
            )
        )
    data = videos_resp.get("data") or {}
    videos: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    lesson_ids: List[Any] = []
    video_ids: List[Any] = []
    for chapter in data.get("videoChapterDtos") or []:
        for lesson in chapter.get("videoLessons") or []:
            lesson_ids.append(lesson["id"])
            smalls = lesson.get("videoSmallLessons") or (
                [dict(lesson, id=0)] if lesson.get("videoId") else []
            )
            for item in smalls:
                video_id = item.get("videoId")
                if video_id is None:
                    continue
                record = {
                    "videoId": video_id,
                    "lessonId": lesson["id"],
                    "smallLessonId": item.get("id", 0),
                    "chapterId": chapter["id"],
                    "name": item.get("name") or lesson.get("name") or str(video_id),
                    "videoSec": item.get("videoSec") or lesson.get("videoSec") or 0,
                }
                key = str(video_id)
                videos[key] = record
                order.append(key)
                if item.get("id"):
                    video_ids.append(item["id"])
    if not order:
        raise AccountError("课程视频列表为空")
    course_data = course.get("data") or {}
    course_info = course_data.get("courseInfo") or {}
    return {
        "recruitId": course_data.get("recruitId"),
        "courseId": course_info.get("courseId"),
        "courseName": course_info.get("name") or "未知课程",
        "hasHabbitScore": course_data.get("hasHabbitScore"),
        "studyStatus": course_data.get("studyStatus", "0"),
        "videos": videos,
        "order": order,
        "lessonIds": lesson_ids,
        "videoIds": video_ids,
    }


def get_states(session: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
    resp = api_call(
        session,
        "/gateway/t/v1/learning/queryStuyInfo",
        {
            "lessonIds": ctx["lessonIds"],
            "lessonVideoIds": ctx["videoIds"],
            "recruitId": ctx["recruitId"],
        },
    )
    return resp.get("data") or {} if resp.get("code") == 0 else {}


def state_of(states: Dict[str, Any], video: Dict[str, Any]) -> Dict[str, Any]:
    return (states.get("lv") or {}).get(str(video["smallLessonId"])) or (
        states.get("lesson") or {}
    ).get(str(video["lessonId"])) or {}


def token_for(session: Any, ctx: Dict[str, Any], video: Dict[str, Any]) -> Any:
    resp = api_call(
        session,
        "/gateway/t/v1/learning/prelearningNote",
        {
            "ccCourseId": ctx["courseId"],
            "chapterId": video["chapterId"],
            "isApply": 1,
            "lessonId": video["lessonId"],
            "lessonVideoId": video["smallLessonId"],
            "recruitId": ctx["recruitId"],
            "videoId": video["videoId"],
        },
    )
    return ((resp.get("data") or {}).get("studiedLessonDto") or {}).get("id")


def report_progress(
    session: Any,
    ctx: Dict[str, Any],
    video: Dict[str, Any],
    uuid: str,
    total_study: float,
    play_times: float,
    watch_point: WatchPoint,
) -> Dict[str, Any]:
    token = token_for(session, ctx, video)
    if not token:
        return {"code": -997, "message": "拿不到 learningTokenId"}
    encoded = [
        ctx["recruitId"],
        video["lessonId"],
        video["smallLessonId"],
        video["videoId"],
        video["chapterId"],
        ctx["studyStatus"],
        int(round(play_times)),
        int(round(total_study)),
        int(round(total_study)),
        uuid + "zhs",
    ]
    payload = {
        "ewssw": watch_point.get(),
        "sdsew": ev_encode(encoded),
        "zwsds": base64.b64encode(str(token).encode()).decode(),
        "courseId": ctx["courseId"],
    }
    return api_call(session, "/gateway/t/v1/learning/saveDatabaseIntervalTimeV2", payload)


def pick_video(
    ctx: Dict[str, Any], states: Dict[str, Any], state: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    used: Dict[str, str] = {}
    accounts = (state.get("accounts") or {}).get(fingerprint) or {}
    history = accounts.get("days") or {}
    if isinstance(history, dict):
        for day, record in history.items():
            if isinstance(record, dict):
                video_id = str(record.get("videoId") or "")
                if video_id:
                    used[video_id] = max(used.get(video_id, ""), str(day))
    order = sorted(ctx["order"], key=lambda item: used.get(str(item), ""))
    return ctx["videos"][order[0]]


def identity_of(account: Dict[str, str], index: int) -> str:
    uuid = extract_uuid(account["cookie"])
    if account.get("remark"):
        if uuid:
            return "{} ({})".format(account["remark"], uuid)
        return account["remark"]
    if uuid:
        return uuid
    return "账号{}".format(index)


def run_account_dry(
    index: int,
    account: Dict[str, str],
    *,
    minutes: float,
    chunk: float,
    speed: float,
) -> Dict[str, Any]:
    started = time.monotonic()
    stats = {"total": 1, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    identity = identity_of(account, index)
    log("-" * 56)
    log("[账号{}] 身份={}".format(index, identity))
    log("[1/4] 校验凭据格式")
    if "jt-cas=" not in account["cookie"]:
        log("{} Cookie 中未见 jt-cas，预演仍继续（正式运行可能失败）".format(ICONS["warning"]))
    else:
        match = re.search(r"jt-cas=([^;]+)", account["cookie"])
        exp = jwt_exp(match.group(1)) if match else None
        if exp:
            remain = (exp - time.time()) / 3600
            log(
                "jt-cas 过期时间：{}（剩余 {:.1f} 小时）".format(
                    datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S"), remain
                )
            )
        else:
            log("jt-cas 已检测到，无法解析过期时间")
    log("[2/4] 课程参数 recruitAndCourseId 长度={}".format(len(account["rac"])))
    need = minutes * 60
    nbatch = int(need // chunk) + (1 if need % chunk else 0)
    log(
        "[3/4] 计划上报：目标 {:.0f} 分钟（{} 秒），分 {} 批，倍速 {}".format(
            minutes, int(need), nbatch, speed
        )
    )
    log("[4/4] 断网预演完成，未发起网络请求，不声明业务成功")
    stats["success"] = 1
    elapsed = time.monotonic() - started
    log(
        "[账号{}] 身份={}；结果=预演通过；总任务=1，成功=1，已完成=0，跳过=0，失败=0，耗时={:.2f}秒".format(
            index, identity, elapsed
        )
    )
    return {
        "index": index,
        "identity": identity,
        "ok": True,
        "status": "dry-run",
        "message": "断网预演通过",
        "stats": stats,
        "elapsed": elapsed,
    }


def run_account(
    index: int,
    account: Dict[str, str],
    *,
    timeout: float,
    minutes: float,
    chunk: float,
    speed: float,
    force: bool,
) -> Dict[str, Any]:
    started = time.monotonic()
    stats = {"total": 1, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    identity = identity_of(account, index)
    fingerprint = account["fingerprint"]
    today = date.today().isoformat()
    log("-" * 56)
    log("[账号{}] 身份={}".format(index, identity))

    try:
        try:
            from Crypto.Cipher import AES  # noqa: F401
        except ImportError as exc:
            raise AccountError(
                "缺少依赖：请安装 pycryptodome（pip install pycryptodome）"
            ) from exc

        state = load_state()
        accounts_state = state.setdefault("accounts", {})
        account_state = accounts_state.setdefault(fingerprint, {"days": {}})
        days = account_state.setdefault("days", {})
        if today in days and not force:
            record = days[today] if isinstance(days[today], dict) else {}
            message = "今日已完成习惯分上报（本地状态）"
            if record.get("minutes") is not None:
                message += "，约 {} 分钟".format(record.get("minutes"))
            if record.get("videoName"):
                message += "，视频「{}」".format(safe_text(record.get("videoName"), 40))
            log("[1/4] {} {}".format(ICONS["alreadyComplete"], message))
            stats["already"] = 1
            elapsed = time.monotonic() - started
            log(
                "[账号{}] 身份={}；结果=已完成；总任务=1，成功=0，已完成=1，跳过=0，失败=0，耗时={:.2f}秒".format(
                    index, identity, elapsed
                )
            )
            return {
                "index": index,
                "identity": identity,
                "ok": True,
                "status": "alreadyComplete",
                "message": message,
                "stats": stats,
                "elapsed": elapsed,
            }

        log("[1/4] 建立会话并校验课程")
        session = make_session(account["cookie"], timeout)
        uuid = extract_uuid(account["cookie"])
        if uuid:
            log("公开 UID：{}".format(uuid))
            identity = identity_of(account, index)

        verify = api_call(
            session,
            "/gateway/t/v1/learning/queryCourse",
            {"recruitAndCourseId": account["rac"]},
        )
        if verify.get("code") != 0:
            raise AccountError(
                "会话或课程无效：code={} {}".format(
                    verify.get("code"), safe_text(verify.get("message"))
                )
            )

        log("[2/4] 读取课程与视频列表")
        ctx = build_ctx(session, account["rac"])
        states = get_states(session, ctx)
        log(
            "课程={}；hasHabbitScore={}".format(
                safe_text(ctx["courseName"], 60), ctx.get("hasHabbitScore")
            )
        )
        video = pick_video(ctx, states, state, fingerprint)
        base0 = int(state_of(states, video).get("studyTotalTime") or 0)
        log(
            "选中视频：{}；videoId={}；当前学习时长={}秒".format(
                safe_text(video.get("name"), 40), video.get("videoId"), base0
            )
        )

        server = api_call(session, "/gateway/t/v1/learning/currentSystemTime", {})
        if server.get("code") == 0 and isinstance(server.get("data"), (int, float)):
            log(
                "服务器时间：{}".format(
                    datetime.fromtimestamp(server["data"] / 1000).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
            )

        need = minutes * 60
        nbatch = int(need // chunk) + (1 if need % chunk else 0)
        log(
            "[3/4] 开始上报：目标 {:.0f} 分钟，分 {} 批".format(minutes, nbatch)
        )
        sent = 0.0
        base = float(base0)
        batch_started = time.time()
        batch = 0
        while sent < need:
            piece = min(chunk, need - sent)
            batch += 1
            live = int(state_of(get_states(session, ctx), video).get("studyTotalTime") or 0)
            if live > base:
                base = float(live)
            target = base + piece
            samples = max(2, int((piece / speed) / SAMPLE_MS))
            watch_point = WatchPoint()
            for i in range(samples):
                watch_point.add(base + (i + 1) * piece / samples)
            log(
                "第 {} 批：playTimes={:.0f}s  totalStudyTime={:.0f} → {:.0f}".format(
                    batch, piece, base, target
                )
            )
            result = report_progress(
                session, ctx, video, uuid, target, piece, watch_point
            )
            code = result.get("code")
            if code == 0:
                log("{} 上报成功".format(ICONS["success"]))
            elif code == -8:
                raise AccountError("学习总时长下降（code=-8），请稍后重试以自动对齐")
            elif code == -12:
                raise AccountError(
                    "命中易盾验证码（code=-12）。请先在浏览器打开任意视频播放几分钟后再跑"
                )
            elif code in (-9, -10, 403):
                raise AccountError("账号级问题 code={}".format(code))
            elif code == -997:
                raise AccountError(safe_text(result.get("message")))
            else:
                raise AccountError(
                    "上报失败 code={} {}".format(code, safe_text(result.get("message")))
                )
            sent += piece
            base = target
            log("已累计 {:.1f} / {:.0f} 分钟".format(sent / 60, minutes))
            if sent < need:
                waited = time.time() - batch_started - (batch - 1) * REPORT_EVERY
                wait = max(0.0, min(REPORT_EVERY - waited, REPORT_EVERY))
                log("等待 {:.0f} 秒后发下一批（对齐前端 300 秒节奏）".format(wait))
                time.sleep(wait)

        log("[4/4] 写入本地完成状态")
        days[today] = {
            "credited": int(sent),
            "minutes": round(sent / 60, 1),
            "videoId": str(video["videoId"]),
            "videoName": video.get("name"),
            "fromTotal": base0,
            "toTotal": int(base),
            "at": datetime.now().strftime("%H:%M:%S"),
            "costSec": int(time.time() - started),
            "courseName": ctx.get("courseName"),
            "uuid": uuid,
        }
        account_state["lastIdentity"] = identity
        save_state(state)
        message = "今日习惯分上报完成，计入 {:.1f} 分钟".format(sent / 60)
        log("{} {}".format(ICONS["success"], message))
        stats["success"] = 1
        elapsed = time.monotonic() - started
        log(
            "[账号{}] 身份={}；结果=成功；总任务=1，成功=1，已完成=0，跳过=0，失败=0，耗时={:.2f}秒".format(
                index, identity, elapsed
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": True,
            "status": "success",
            "message": message,
            "stats": stats,
            "elapsed": elapsed,
        }
    except AccountError as exc:
        stats["failed"] = 1
        elapsed = time.monotonic() - started
        msg = safe_text(exc)
        log("{} 账号{} 失败：{}".format(ICONS["failure"], index, msg))
        log(
            "[账号{}] 身份={}；结果=失败；总任务=1，成功=0，已完成=0，跳过=0，失败=1，耗时={:.2f}秒".format(
                index, identity, elapsed
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": False,
            "status": "failure",
            "message": msg,
            "stats": stats,
            "elapsed": elapsed,
        }
    except Exception as exc:
        stats["failed"] = 1
        elapsed = time.monotonic() - started
        msg = safe_text(exc)
        log("{} 账号{} 异常：{}".format(ICONS["failure"], index, msg))
        log(
            "[账号{}] 身份={}；结果=失败；总任务=1，成功=0，已完成=0，跳过=0，失败=1，耗时={:.2f}秒".format(
                index, identity, elapsed
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": False,
            "status": "failure",
            "message": msg,
            "stats": stats,
            "elapsed": elapsed,
        }


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {
        CATALOG_ID,
        Path(__file__).name,
        "candidate.py",
        "zhihuishu_habit_daily.py",
        "scripts/zhihuishu_habit_daily.py",
        "zhihuishu-habit-daily",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    if value != "auto":
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = env("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = env("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    return paths


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    paths = [None] + [path for path in python_notifier_paths() if path.is_file()]
    for path in paths:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    python_runner,
                    str(path) if path else "",
                    str(Path(__file__).resolve().parent),
                ],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                log(
                    "通知状态：{} 已调用".format(
                        "notify.py" if path else "notify.send"
                    )
                )
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
        for path in js_notifier_paths():
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

    log(
        "{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(
            ICONS["warning"]
        )
    )
    return "unavailable"


def emit_summary(
    *,
    status: str,
    final_label: str,
    dry_run: bool,
    results: List[Dict[str, Any]],
    account_success: int,
    account_failed: int,
    notify_state: str,
    started_at: str,
    overall_started: float,
) -> None:
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    print("\n" + "-" * 56)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), account_success, account_failed
        )
    )
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(
            **task_stats
        )
    )
    print("总耗时：{:.2f}秒".format(elapsed))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：{}".format(final_label))
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "status": status,
                "mode": "dry-run" if dry_run else "live",
                "accounts": {
                    "total": len(results),
                    "success": account_success,
                    "failed": account_failed,
                },
                "tasks": {
                    "total": task_stats["total"],
                    "success": task_stats["success"],
                    "alreadyComplete": task_stats["already"],
                    "skipped": task_stats["skipped"],
                    "failed": task_stats["failed"],
                },
                "notification": notify_state,
                "elapsedSeconds": round(elapsed, 3),
                "startedAt": started_at,
                "finishedAt": finished_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )


def build_notify_body(
    *,
    results: List[Dict[str, Any]],
    account_success: int,
    account_failed: int,
    final_label: str,
) -> str:
    lines = [
        "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
            len(results), account_success, account_failed, final_label
        )
    ]
    for item in results:
        lines.append(
            "账号{}（{}）：{} — {}".format(
                item["index"],
                item["identity"],
                item["status"],
                safe_text(item.get("message"), 80),
            )
        )
    return "\n".join(lines)


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_setting = env("ZHS_HABIT_DRY_RUN", "0").lower() or "0"
    dry_run = dry_setting in TRUE_VALUES
    print("=" * 56)
    print("{} | 独立维护版".format(TITLE))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("目录编号：{}".format(CATALOG_ID))
    print("=" * 56, flush=True)

    try:
        if dry_setting and dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise TaskError("ZHS_HABIT_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout()
        minutes = parse_float_env("ZHS_HABIT_MINUTES", 25.0, 1.0, 180.0)
        chunk = parse_float_env("ZHS_HABIT_CHUNK", 540.0, 60.0, 1800.0)
        speed = parse_float_env("ZHS_HABIT_SPEED", 1.8, 0.5, 3.0)
        force = truthy("ZHS_HABIT_FORCE")
        accounts = load_accounts()
    except TaskError as exc:
        log("账号数量：0")
        log("[0/0] {} 配置错误：{}".format(ICONS["failure"], safe_text(exc)))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误；详情：{}".format(
            safe_text(exc)
        )
        notify_state = send_notification(TITLE, body, dry_run)
        emit_summary(
            status="configuration-error",
            final_label="CONFIG_ERROR",
            dry_run=dry_run,
            results=[],
            account_success=0,
            account_failed=1,
            notify_state=notify_state,
            started_at=started_at,
            overall_started=overall_started,
        )
        return 2

    log("账号数量：{}".format(len(accounts)))
    log(
        "超时：{}秒；目标：{:.0f} 分钟；单批：{:.0f} 秒；倍速：{}".format(
            int(timeout), minutes, chunk, speed
        )
    )

    if dry_run:
        results = [
            run_account_dry(
                index, account, minutes=minutes, chunk=chunk, speed=speed
            )
            for index, account in enumerate(accounts, 1)
        ]
    else:
        results = [
            run_account(
                index,
                account,
                timeout=timeout,
                minutes=minutes,
                chunk=chunk,
                speed=speed,
                force=force,
            )
            for index, account in enumerate(accounts, 1)
        ]

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success

    if dry_run:
        status = "dry-run"
        final_label = "DRY_RUN"
    elif account_failed == 0:
        status = "success"
        final_label = "SUCCESS"
    elif account_success == 0:
        status = "failure"
        final_label = "FAILED"
    else:
        status = "partial-failure"
        final_label = "PARTIAL"

    body = build_notify_body(
        results=results,
        account_success=account_success,
        account_failed=account_failed,
        final_label=final_label,
    )
    notify_state = send_notification(TITLE, body, dry_run)
    emit_summary(
        status=status,
        final_label=final_label,
        dry_run=dry_run,
        results=results,
        account_success=account_success,
        account_failed=account_failed,
        notify_state=notify_state,
        started_at=started_at,
        overall_started=overall_started,
    )
    return 0 if account_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
