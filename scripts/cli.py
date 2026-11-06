#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 中山大学人脸签到
# cron: */5 7-22 * * *
#
# 来源：undefined443/sysu-check-in（MIT）
# https://github.com/undefined443/sysu-check-in
# 分支：main
# 提交：531bdf0638e98510a8e556db85c78ca146393244
# 原路径：src/sysu_check_in/cli.py（及相关 core.py / __init__.py / __main__.py）
#
# MIT License
#
# Copyright (c) undefined443 / sysu-check-in contributors
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
"""中山大学（SYSU）人脸识别签到 - 青龙维护版。

功能清点（相对上游 cli.py + core.py）：
- 查询当前可见签到活动列表（getActivityList）
- 选择进行中活动（iSignStatus=2）；已签到（iSignStatus=3）视为已完成成功
- 提交人脸 JPEG 完成签到（submitSignFace），并再次拉列表核验 iSignStatus=3
- GPS 定位提交（submitPosition）默认关闭（与上游注释一致），仅 SYSU_SUBMIT_GPS=1 时启用
- 移除 Rich CLI、默认 face.jpg 隐式路径依赖、无超时风险；改为青龙环境变量驱动

维护改动：
- 合并为单文件独立脚本；标准库 HTTP + 公开包 pycryptodome（AES-128-ECB）
- 多账号：SYSU_ACCOUNTS 每行 学号 或 学号|图片路径/Base64（仅按首个 | 分割）
- SYSU_DRY_RUN 完全断网预演；超时、业务核验、时间轴日志、青龙通知、TASK_SUMMARY
- 任一账号失败整体非零退出；不打印学号以外的敏感材料、人脸 Base64 或原始响应

环境变量：
  SYSU_ACCOUNTS      必填：每行一个账号，学号 或 学号|人脸图片（路径或 Base64）
  SYSU_STUDENT_ID    可选兼容：未设置 SYSU_ACCOUNTS 时使用，格式同上
  SYSU_FACE_IMAGE    可选：账号行未带图片时的共用 JPEG 路径或 Base64
  SYSU_SUBMIT_GPS    可选：1/true/yes/on 时额外提交定位（默认关闭）
  SYSU_LONGITUDE     可选：经度，默认 113.9539（仅启用 GPS 时使用）
  SYSU_LATITUDE      可选：纬度，默认 22.801604（仅启用 GPS 时使用）
  SYSU_TIMEOUT       可选：单次 HTTP 超时秒数，默认 30
  SYSU_DRY_RUN       1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略

仅供本人课程签到学习使用；请遵守学校规定，后果自负。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('d6e397f627b3716b', 'scripts/cli.py', 'cli.py', 'cli')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import importlib.util
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "d6e397f627b3716b"
SCRIPT_NAME = "中山大学人脸签到"
SCRIPT_FILENAME = "candidate.py"

# AES-128 key shared by every request; the hex decodes to b"sh12345678901234".
_AES_KEY = bytes.fromhex("73683132333435363738393031323334")

_BASE_URL = "https://facerecog.sysu.edu.cn/sign"
_ACTIVE_SIGN_STATUS = 2
_SIGNED_STATUS = 3

_DEFAULT_LONGITUDE = "113.9539"
_DEFAULT_LATITUDE = "22.801604"
_DEFAULT_TIMEOUT = 30
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; FLC-AN00 Build/HONORFLC-AN00; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        "Chrome/138.0.7204.180 Mobile Safari/537.36 XWEB/1380347 "
        "MMWEBSDK/20250202 MMWEBID/6351 wxwork/5.0.6.66174 "
        "MicroMessenger/8.0.28.48(0x28001c30) MiniProgramEnv/android "
        "Luggage/3.0.2.95ef3f83 NetType/WIFI Language/en ABI/arm64"
    ),
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/plain, */*",
    "charset": "utf-8",
}

DRY_RUN_ENV = "SYSU_DRY_RUN"
CRED_ENV = "SYSU_ACCOUNTS"
CRED_ALIAS_ENV = "SYSU_STUDENT_ID"
FACE_ENV = "SYSU_FACE_IMAGE"
TIMEOUT_ENV = "SYSU_TIMEOUT"
GPS_ENV = "SYSU_SUBMIT_GPS"
LON_ENV = "SYSU_LONGITUDE"
LAT_ENV = "SYSU_LATITUDE"

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


class SysuError(Exception):
    """可安全打印的业务错误。"""


class AlreadyCheckedInError(SysuError):
    """当前活动已签到。"""


class NoActiveActivityError(SysuError):
    """无进行中的签到活动。"""


class CheckInRejectedError(SysuError):
    """服务拒绝签到提交。"""


@dataclass
class Account:
    index: int
    student_id: str
    face_material: str = ""
    display_name: str = ""

    @property
    def label(self) -> str:
        if self.display_name:
            return "账号{}({})".format(self.index, self.display_name)
        return "账号{}({})".format(self.index, self.student_id)


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


def log_stage(index: int, title: str, detail: str = "") -> None:
    suffix = " — {}".format(detail) if detail else ""
    log("阶段{} {}{}".format(index, title, suffix))


def truthy_env(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def safe_text(value: Any, limit: int = 240) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def env_timeout() -> float:
    raw = os.getenv(TIMEOUT_ENV, "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("{} 必须是数字".format(TIMEOUT_ENV)) from exc
    if value < 5 or value > 120:
        raise ValueError("{} 须在 5–120 之间".format(TIMEOUT_ENV))
    return value


def _timestamp() -> int:
    return int(time.time())


def _timestamp_milliseconds() -> int:
    return int(time.time() * 1000)


def _load_aes():
    try:
        from Crypto.Cipher import AES  # type: ignore
        from Crypto.Util.Padding import pad  # type: ignore

        return AES, pad
    except Exception as exc:
        raise SysuError(
            "缺少公开依赖 pycryptodome，请在青龙依赖管理中执行：pip install pycryptodome"
        ) from exc


def _encrypt(plaintext: str) -> str:
    AES, pad = _load_aes()
    cipher = AES.new(_AES_KEY, AES.MODE_ECB)
    return cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size)).hex()


def _looks_like_base64(text: str) -> bool:
    cleaned = text.strip()
    if cleaned.startswith("data:image"):
        return True
    if len(cleaned) < 64:
        return False
    sample = cleaned[:200].replace("\n", "").replace("\r", "")
    return bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", sample))


def _normalize_face_b64(material: str) -> str:
    text = material.strip()
    if not text:
        raise SysuError("人脸图片材料为空")
    if text.startswith("data:image"):
        if "," not in text:
            raise SysuError("人脸 data URL 格式无效")
        text = text.split(",", 1)[1].strip()
    if _looks_like_base64(text) and not os.path.isfile(text):
        try:
            raw = base64.b64decode(text, validate=False)
        except Exception as exc:
            raise SysuError("人脸 Base64 无法解码") from exc
        if len(raw) < 32:
            raise SysuError("人脸图片过小，可能不是有效 JPEG")
        return base64.b64encode(raw).decode("ascii")
    path = os.path.expanduser(text)
    if not os.path.isfile(path):
        raise SysuError("人脸图片文件不存在")
    with open(path, "rb") as handle:
        content = handle.read()
    if len(content) < 32:
        raise SysuError("人脸图片文件过小")
    return base64.b64encode(content).decode("ascii")


def shared_face_material() -> str:
    return os.getenv(FACE_ENV, "").strip()


def parse_account_line(index: int, line: str, fallback_face: str) -> Account:
    text = line.strip()
    if not text or text.startswith("#"):
        raise ValueError("空账号行")
    if "|" in text:
        student_id, face = text.split("|", 1)
    else:
        student_id, face = text, ""
    student_id = student_id.strip()
    face = face.strip() or fallback_face
    if not student_id:
        raise ValueError("账号{}缺少学号".format(index))
    if any(ord(ch) < 32 for ch in student_id):
        raise ValueError("账号{}学号含非法控制字符".format(index))
    return Account(index=index, student_id=student_id, face_material=face)


def parse_accounts() -> Tuple[List[Account], str]:
    raw = os.getenv(CRED_ENV, "")
    source_name = CRED_ENV
    if not raw.strip():
        raw = os.getenv(CRED_ALIAS_ENV, "")
        source_name = CRED_ALIAS_ENV
    if not raw.strip():
        raise ValueError(
            "缺少必填凭据 {}：每行一个账号，格式 学号 或 学号|人脸图片路径/Base64"
            "（仅按首个竖线分割）；也可兼容使用 {}".format(CRED_ENV, CRED_ALIAS_ENV)
        )
    fallback_face = shared_face_material()
    accounts: List[Account] = []
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        accounts.append(parse_account_line(len(accounts) + 1, line, fallback_face))
    if not accounts:
        raise ValueError("{} 未解析到有效账号".format(source_name))
    return accounts, source_name


def _http_post_form(
    endpoint_path: str,
    form_data: Dict[str, str],
    timeout: float,
    dry_run: bool,
) -> Dict[str, Any]:
    if dry_run:
        raise RuntimeError("dry-run 禁止发起网络请求")
    url = "{}/{}".format(_BASE_URL, endpoint_path)
    body = urllib.parse.urlencode(form_data).encode("utf-8")
    headers = dict(_HEADERS)
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SysuError("响应过大，已中止解析")
            text = raw.decode("utf-8", errors="replace") if raw else ""
    except urllib.error.HTTPError as exc:
        raise SysuError("HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise SysuError("网络请求失败：{}".format(safe_text(getattr(exc, "reason", exc)))) from exc
    except TimeoutError as exc:
        raise SysuError("请求超时") from exc
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SysuError("响应不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise SysuError("响应结构异常")
    return payload


def _raise_for_rejection(payload: Dict[str, Any]) -> None:
    code = payload.get("code")
    if code != 1:
        msg = safe_text(payload.get("msg") or "服务拒绝提交")
        raise CheckInRejectedError(msg)


def fetch_activities(student_id: str, timeout: float, dry_run: bool) -> List[dict]:
    plaintext = "{}##{}".format(student_id, _timestamp())
    payload = _http_post_form(
        "getActivityList",
        {"sKey": _encrypt(plaintext)},
        timeout=timeout,
        dry_run=dry_run,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SysuError("活动列表缺少 data")
    rows = data.get("rows")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise SysuError("活动列表格式异常")
    return [row for row in rows if isinstance(row, dict)]


def get_active_activity(
    student_id: str, timeout: float, dry_run: bool
) -> Tuple[str, str]:
    activities = fetch_activities(student_id, timeout=timeout, dry_run=dry_run)
    for activity in activities:
        if activity.get("iSignStatus") == _ACTIVE_SIGN_STATUS:
            act_id = str(activity.get("sActId") or "").strip()
            act_name = str(activity.get("sActName") or act_id or "未命名活动").strip()
            if not act_id:
                raise SysuError("活动缺少 sActId")
            return act_id, act_name
    for activity in activities:
        if activity.get("iSignStatus") == _SIGNED_STATUS:
            act_name = str(activity.get("sActName") or "已签到活动").strip()
            raise AlreadyCheckedInError("已签到：{}".format(act_name))
    raise NoActiveActivityError("当前没有进行中的签到活动")


def submit_gps(
    student_id: str,
    activity_id: str,
    longitude: str,
    latitude: str,
    timeout: float,
    dry_run: bool,
) -> None:
    plaintext = "{}##{}####{}##{}##{}".format(
        student_id,
        activity_id,
        longitude,
        latitude,
        _timestamp_milliseconds(),
    )
    payload = _http_post_form(
        "submitPosition",
        {"sKey": _encrypt(plaintext)},
        timeout=timeout,
        dry_run=dry_run,
    )
    _raise_for_rejection(payload)


def submit_face(
    student_id: str,
    activity_id: str,
    face_b64: str,
    timeout: float,
    dry_run: bool,
) -> None:
    plaintext = "{}##{}##{}".format(student_id, activity_id, _timestamp())
    form_data = {
        "sKey": _encrypt(plaintext),
        "sImage": "data:image/jpeg;base64,{}".format(face_b64),
    }
    payload = _http_post_form(
        "submitSignFace",
        form_data,
        timeout=timeout,
        dry_run=dry_run,
    )
    _raise_for_rejection(payload)


def verify_signed(
    student_id: str, activity_id: str, timeout: float, dry_run: bool
) -> None:
    activities = {
        str(row.get("sActId")): row
        for row in fetch_activities(student_id, timeout=timeout, dry_run=dry_run)
    }
    activity = activities.get(activity_id)
    if activity is None:
        raise CheckInRejectedError("核验失败：活动已不在列表中")
    if activity.get("iSignStatus") != _SIGNED_STATUS:
        status_text = safe_text(activity.get("sSignStatus") or activity.get("iSignStatus"))
        raise CheckInRejectedError("核验失败：状态为 {}".format(status_text))


def _notify_global_mode() -> str:
    raw = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in TRUE_VALUES:
        return "enabled"
    if raw in FALSE_VALUES:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if raw is None:
        return None
    if raw.strip() == "":
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _selector_match(selector: str) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if sel == "*":
        return True
    candidates = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        "scripts/{}".format(SCRIPT_FILENAME),
        "scripts/sysu_check_in.py",
        "sysu_check_in.py",
        "sysu-check-in",
        SCRIPT_NAME,
    }
    sel_l = sel.lower()
    if sel in candidates or sel_l in {c.lower() for c in candidates}:
        return True
    if "*" in sel:
        return any(
            _ql_notify_fnmatch.fnmatch(item.lower(), sel_l) for item in candidates
        )
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    if mode == "enabled":
        return True
    selectors = _script_selectors()
    if selectors is None:
        return True
    if not selectors:
        return False
    return any(_selector_match(s) for s in selectors)


def _load_notify_send():
    try:
        from notify import send as notify_send  # type: ignore

        return notify_send
    except Exception:
        pass
    search_dirs = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, body: str) -> str:
    if not _should_notify():
        log("通知: 已跳过（全局开关或脚本选择未启用）")
        return "skipped"
    sender = _load_notify_send()
    if sender is None:
        log("{} 通知: 未找到 notify.py，已跳过发送".format(ICONS["warning"]))
        return "unavailable"
    try:
        sender(title, body)
        log("{} 通知: 已发送".format(ICONS["success"]))
        return "sent"
    except Exception:
        log("{} 通知发送失败: 已忽略".format(ICONS["warning"]))
        return "failed"


def run_account_dry(account: Account, total: int, submit_gps_flag: bool) -> Dict[str, Any]:
    started = time.monotonic()
    label = account.label
    log("—— {}/{}/{} 开始（预演）——".format(label, account.index, total))
    stats = StageStats(total=5 if submit_gps_flag else 4)
    result: Dict[str, Any] = {
        "index": account.index,
        "identity": label,
        "ok": True,
        "status": "success",
        "message": "预演通过",
        "elapsedMs": 0,
    }

    log_stage(1, "校验学号与人脸材料")
    try:
        if not account.student_id:
            raise SysuError("学号为空")
        # dry-run：校验材料可解析，但不输出内容
        if account.face_material:
            if os.path.isfile(os.path.expanduser(account.face_material)):
                log("  {} 人脸材料：本地文件路径已就绪".format(ICONS["success"]))
            elif _looks_like_base64(account.face_material):
                log("  {} 人脸材料：Base64 形态已就绪（不输出内容）".format(ICONS["success"]))
            else:
                # 路径当前不存在也允许预演通过配置检查，正式运行再失败
                log(
                    "  {} 人脸材料：将按路径/Base64 读取（预演不访问网络）".format(
                        ICONS["success"]
                    )
                )
        else:
            raise SysuError(
                "缺少人脸图片：请在账号行用 学号|图片 或设置 {}".format(FACE_ENV)
            )
        _load_aes()
        stats.success += 1
        log("  {} 学号与加密依赖检查通过".format(ICONS["success"]))
    except Exception as exc:
        stats.failed += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = safe_text(exc)
        log("  {} {}".format(ICONS["failure"], result["message"]))
        result["elapsedMs"] = int((time.monotonic() - started) * 1000)
        result["stats"] = stats.__dict__
        log(
            "{} 统计: 总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={}ms".format(
                label,
                stats.total,
                stats.success,
                stats.alreadyComplete,
                stats.skipped,
                stats.failed,
                result["elapsedMs"],
            )
        )
        return result

    stage = 2
    log_stage(stage, "预演查询活动列表", "跳过真实网络请求")
    stats.skipped += 1
    log("  {} 断网预演：将 POST {}/getActivityList".format(ICONS["skipped"], _BASE_URL))

    if submit_gps_flag:
        stage += 1
        log_stage(stage, "预演提交定位", "可选副作用，默认正式运行亦需显式开启")
        stats.skipped += 1
        log("  {} 断网预演：将 POST {}/submitPosition".format(ICONS["skipped"], _BASE_URL))

    stage += 1
    log_stage(stage, "预演提交人脸签到", "跳过真实网络请求")
    stats.skipped += 1
    log("  {} 断网预演：将 POST {}/submitSignFace".format(ICONS["skipped"], _BASE_URL))

    stage += 1
    log_stage(stage, "预演核验签到状态", "跳过真实网络请求")
    stats.skipped += 1
    log("  {} 断网预演：将再次查询活动列表核验已签到".format(ICONS["skipped"]))

    elapsed = int((time.monotonic() - started) * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats.__dict__
    log(
        "{} 统计: 总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={}ms".format(
            label,
            stats.total,
            stats.success,
            stats.alreadyComplete,
            stats.skipped,
            stats.failed,
            elapsed,
        )
    )
    return result


def run_account_live(
    account: Account,
    total: int,
    timeout: float,
    submit_gps_flag: bool,
    longitude: str,
    latitude: str,
) -> Dict[str, Any]:
    started = time.monotonic()
    label = account.label
    log("—— {}/{}/{} 开始 ——".format(label, account.index, total))
    stats = StageStats(total=5 if submit_gps_flag else 4)
    result: Dict[str, Any] = {
        "index": account.index,
        "identity": label,
        "ok": False,
        "status": "failure",
        "message": "",
        "elapsedMs": 0,
        "stats": stats.__dict__,
    }
    try:
        log_stage(1, "查询进行中活动")
        try:
            activity_id, activity_name = get_active_activity(
                account.student_id, timeout=timeout, dry_run=False
            )
        except AlreadyCheckedInError as exc:
            stats.alreadyComplete += 1
            result["ok"] = True
            result["status"] = "success"
            result["message"] = str(exc)
            log("  {} {}".format(ICONS["alreadyComplete"], result["message"]))
            raise _AccountDone() from exc

        account.display_name = activity_name
        result["identity"] = account.label
        stats.success += 1
        log(
            "  {} 活动: {}（id 已核验，不输出原始响应）".format(
                ICONS["success"], safe_text(activity_name, 80)
            )
        )

        log_stage(2, "准备人脸图片")
        face_b64 = _normalize_face_b64(account.face_material)
        stats.success += 1
        log("  {} 人脸 JPEG 已载入（不输出内容）".format(ICONS["success"]))

        stage = 3
        if submit_gps_flag:
            log_stage(stage, "提交定位")
            submit_gps(
                account.student_id,
                activity_id,
                longitude,
                latitude,
                timeout=timeout,
                dry_run=False,
            )
            stats.success += 1
            log("  {} 定位已提交".format(ICONS["success"]))
            stage += 1
        else:
            log("  {} 跳过定位提交（默认关闭，与上游一致）".format(ICONS["skipped"]))

        log_stage(stage, "提交人脸签到")
        submit_face(
            account.student_id,
            activity_id,
            face_b64,
            timeout=timeout,
            dry_run=False,
        )
        stats.success += 1
        log("  {} 人脸签到已提交".format(ICONS["success"]))
        stage += 1

        log_stage(stage, "核验签到状态")
        verify_signed(
            account.student_id, activity_id, timeout=timeout, dry_run=False
        )
        stats.success += 1
        result["ok"] = True
        result["status"] = "success"
        result["message"] = "签到成功：{}".format(safe_text(activity_name, 80))
        log("  {} {}".format(ICONS["success"], result["message"]))
    except _AccountDone:
        pass
    except Exception as exc:
        stats.failed += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = safe_text(exc)
        log("  {} {}".format(ICONS["failure"], result["message"]))

    elapsed = int((time.monotonic() - started) * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats.__dict__
    log(
        "{} 统计: 总任务={} 成功={} 已完成={} 跳过={} 失败={} 耗时={}ms".format(
            result["identity"],
            stats.total,
            stats.success,
            stats.alreadyComplete,
            stats.skipped,
            stats.failed,
            elapsed,
        )
    )
    return result


class _AccountDone(Exception):
    """内部：账号已成功结束（如已签到）。"""


def main() -> int:
    task_start = now_beijing()
    dry = truthy_env(DRY_RUN_ENV)
    mode = "dry-run" if dry else "live"

    print("=" * 56)
    print("  {}".format(SCRIPT_NAME))
    print("=" * 56)
    log("开始时间: {}".format(stamp_full()))
    log("运行模式: {}".format(mode))
    log("目录 ID: {}".format(CATALOG_ID))

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"
    submit_gps_flag = truthy_env(GPS_ENV)
    longitude = os.getenv(LON_ENV, _DEFAULT_LONGITUDE).strip() or _DEFAULT_LONGITUDE
    latitude = os.getenv(LAT_ENV, _DEFAULT_LATITUDE).strip() or _DEFAULT_LATITUDE

    try:
        timeout = env_timeout()
        accounts, source_name = parse_accounts()
        log("凭据来源: {}（内容已脱敏）".format(source_name))
        log("账号数量: {}".format(len(accounts)))
        log("定位提交: {}".format("开启" if submit_gps_flag else "关闭（默认）"))
        if not dry:
            _load_aes()

        total = len(accounts)
        for account in accounts:
            if dry:
                ar = run_account_dry(account, total, submit_gps_flag)
            else:
                ar = run_account_live(
                    account,
                    total,
                    timeout=timeout,
                    submit_gps_flag=submit_gps_flag,
                    longitude=longitude,
                    latitude=latitude,
                )
            account_results.append(ar)

        failed = [a for a in account_results if not a.get("ok")]
        succeeded = [a for a in account_results if a.get("ok")]
        if failed and succeeded:
            summary_status = "partial-failure"
            exit_code = 1
        elif failed:
            summary_status = "failure"
            exit_code = 1
        else:
            summary_status = "dry-run" if dry else "success"
            exit_code = 0
    except ValueError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log("{} 配置错误: {}".format(ICONS["failure"], safe_text(exc)))
        log(
            "获取方式: 准备中山大学人脸签到学号，以及本人 JPEG 人脸照片路径或 Base64；"
            "写入青龙环境变量 {}，每行一个账号".format(CRED_ENV)
        )
        log("账号数量: 0")
    except SysuError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log("{} 配置错误: {}".format(ICONS["failure"], safe_text(exc)))
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(
            "{} 未处理异常: {}: {}".format(
                ICONS["failure"], type(exc).__name__, safe_text(exc)
            )
        )
        traceback.print_exc()

    task_end = now_beijing()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56)
    log("任务统计")
    log("  账号结果: 总数={} 成功={} 失败={}".format(total_accounts, ok_count, fail_count))
    sub_success = sum(int((a.get("stats") or {}).get("success") or 0) for a in account_results)
    sub_fail = sum(int((a.get("stats") or {}).get("failed") or 0) for a in account_results)
    sub_skip = sum(int((a.get("stats") or {}).get("skipped") or 0) for a in account_results)
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0) for a in account_results
    )
    log(
        "  子任务结果: 成功={} 已完成={} 跳过={} 失败={}".format(
            sub_success, sub_done, sub_skip, sub_fail
        )
    )
    log("  总耗时: {}ms".format(elapsed_ms))
    log("  完成时间: {}".format(stamp_full()))

    if dry and not config_error:
        event = "dry-run"
    elif config_error:
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        "任务: {}".format(SCRIPT_NAME),
        "模式: {}".format(mode),
        "事件: {}".format(event),
        "账号总数: {}".format(total_accounts if not config_error else 0),
        "成功: {}".format(ok_count),
        "失败: {}".format(fail_count),
        "状态: {}".format(summary_status),
    ]
    for item in account_results:
        lines.append(
            "- {}: {} / {}".format(
                item.get("identity"),
                item.get("status"),
                safe_text(item.get("message", ""), 120),
            )
        )
    body = "\n".join(lines)
    notify_status = send_notification(SCRIPT_NAME, body)
    log("通知状态: {}".format(notify_status))

    final_status = summary_status
    if exit_code == 0 and dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        final_status = "dry-run-success"
        log("{} 最终状态: 预演成功".format(ICONS["success"]))
    elif exit_code == 0:
        log("{} 最终状态: 成功".format(ICONS["success"]))
    elif config_error:
        log("{} 最终状态: 配置错误".format(ICONS["failure"]))
    else:
        log("{} 最终状态: 失败".format(ICONS["failure"]))

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "task": SCRIPT_NAME,
        "mode": mode,
        "status": final_status if exit_code == 0 else summary_status,
        "exitCode": exit_code,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSucceeded": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notifyStatus": notify_status,
        "finishedAt": stamp_full(),
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
