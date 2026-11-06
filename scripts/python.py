#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 佛山职院企微学工签到
# cron: */5 7-22 * * *
#
# 来源：Yaklo/AutoCheckFvtiWeCom python/main.py（GPL-3.0）
# https://github.com/Yaklo/AutoCheckFvtiWeCom
# 提交：26acd5ee84e8d849e529bcedcf9ccb612c603a93
# 未合并：php/ 企微授权捕获站点（需自建 nginx/php/redis 部署）、Redis Token 队列、
# schedule 常驻守护、交互式 config.json、pyinstaller 打包入口。
#
# SPDX-License-Identifier: GPL-3.0-only
# effectiveLicense: GPL-3.0
#
# 本维护版沿用上游 GPL-3.0 许可。
# Copyright (C) Yaklo / AutoCheckFvtiWeCom contributors
# 完整 GPL-3.0 文本见上游仓库 LICENSE。
#
"""佛山职业技术学院（FVTI）企微学工 GPS 签到 - 青龙独立维护版。

功能清点（相对上游 python/main.py）：
- GET GetStuSignInList 拉取待签到任务列表
- 按 QD / QDTimeText 判断是否在签到窗口且尚未签到
- POST SaveStuSignIn 提交 GPS 坐标签到（经纬度末两位随机偏移，保留上游定位抖动）
- 业务码 errcode==0 视为签到成功；任务已签到记为已完成
- 多账号：FVTI_ACCOUNTS 每非空行一个账号；格式 BearerToken|纬度|经度|备注(可选)
- 兼容别名 FVTI_TOKEN（需配合 FVTI_LAT / FVTI_LNG）
- 移除 Redis、schedule 常驻循环、交互 input、config.json、打印授权码/学号/原始响应
- FVTI_DRY_RUN=1 完全断网预演；超时、脱敏时间轴日志、青龙通知与 TASK_SUMMARY

参数获取：
1. 企业微信打开学工系统 OAuth：
   https://open.weixin.qq.com/connect/oauth2/authorize?appid=wxf4d2e5e90c26ff0e&redirect_uri=http%3a%2f%2fzhxg.fvti.edu.cn%2fcode
2. 在跳转后的页面复制链接或抓包 Authorization: Bearer ... 中的 Token
3. 在签到地点用地图取纬度、经度（与上游 Redis 记录中的坐标一致即可）
注意：学工授权通常约 24 小时有效，过期需重新获取。不要把 Token 发给他人或写入公开仓库。
建议 Cron：*/5 7-22 * * *（按学校签到窗口自行调整）。
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
        _ql_notify_identities = ('1a77e89326b6c406', 'scripts/python.py', 'python.py', 'python')
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
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "佛山职院企微学工签到"
CATALOG_ID = "1a77e89326b6c406"
SCRIPT_FILENAME = "fvti_wecom_checkin.py"

API_URL_GET = "http://zhxg.fvti.edu.cn/PhoneApi/api/SignIn/GetStuSignInList"
API_URL_POST = "http://zhxg.fvti.edu.cn/PhoneApi/api/SignIn/SaveStuSignIn"

ACCOUNTS_ENV = "FVTI_ACCOUNTS"
TOKEN_ALIAS_ENV = "FVTI_TOKEN"
LAT_ENV = "FVTI_LAT"
LNG_ENV = "FVTI_LNG"
DRY_RUN_ENV = "FVTI_DRY_RUN"
TIMEOUT_ENV = "FVTI_TIMEOUT"
FORCE_SIGN_ENV = "FVTI_FORCE_SIGN"

DEFAULT_TIMEOUT = 15
MAX_BYTES = 1048576
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

BEIJING = timezone(timedelta(hours=8), "Asia/Shanghai")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class FvtiError(Exception):
    """业务层可读错误"""


@dataclass
class Account:
    index: int
    token: str
    latitude: float
    longitude: float
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


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def safe_text(value: Any, limit: int = 240) -> str:
    text = str(value if value is not None else "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def redact_secrets(text: str, secrets: List[str]) -> str:
    result = text
    for secret in secrets:
        secret = (secret or "").strip()
        if len(secret) >= 6:
            result = result.replace(secret, "***")
    result = re.sub(r"(?i)bearer\s+[a-z0-9._\-]{8,}", "Bearer ***", result)
    return result


def env_timeout() -> float:
    raw = os.getenv(TIMEOUT_ENV, "").strip()
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise FvtiError("{} 必须是数字秒".format(TIMEOUT_ENV)) from exc
    if value < 5 or value > 120:
        raise FvtiError("{} 取值范围 5-120".format(TIMEOUT_ENV))
    return value


def parse_coord(raw: str, kind: str) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise FvtiError("{} 不是有效数字".format(kind)) from exc
    if kind == "纬度" and not (-90.0 <= value <= 90.0):
        raise FvtiError("纬度超出范围 -90~90")
    if kind == "经度" and not (-180.0 <= value <= 180.0):
        raise FvtiError("经度超出范围 -180~180")
    return value


def parse_account_line(line: str, index: int, default_lat: str, default_lng: str) -> Account:
    text = line.strip()
    if not text or text.startswith("#"):
        raise FvtiError("空行")

    # 兼容上游 Redis CSV：token,...,lat,lng,...（字段较多）
    if "|" not in text and text.count(",") >= 6:
        parts = text.split(",")
        token = parts[0].strip()
        if not token:
            raise FvtiError("缺少 Bearer Token")
        lat = parse_coord(parts[5], "纬度")
        lng = parse_coord(parts[6], "经度")
        display = ""
        if len(parts) > 9 and parts[9].strip():
            display = parts[9].strip()
        return Account(index=index, token=token, latitude=lat, longitude=lng, display_name=display)

    # 规范格式：BearerToken|纬度|经度|备注(可选)；仅按 | 分割，Token 本身不含 |
    parts = [p.strip() for p in text.split("|")]
    if len(parts) == 1:
        token = parts[0]
        if not default_lat or not default_lng:
            raise FvtiError(
                "账号行仅有 Token 时必须同时配置 {} 与 {}".format(LAT_ENV, LNG_ENV)
            )
        lat = parse_coord(default_lat, "纬度")
        lng = parse_coord(default_lng, "经度")
        return Account(index=index, token=token, latitude=lat, longitude=lng)

    if len(parts) < 3:
        raise FvtiError("账号格式应为 BearerToken|纬度|经度|备注(可选)")
    token = parts[0]
    if not token:
        raise FvtiError("缺少 Bearer Token")
    lat = parse_coord(parts[1], "纬度")
    lng = parse_coord(parts[2], "经度")
    display = parts[3] if len(parts) > 3 and parts[3] else ""
    return Account(index=index, token=token, latitude=lat, longitude=lng, display_name=display)


def parse_accounts() -> List[Account]:
    raw = os.getenv(ACCOUNTS_ENV, "").strip()
    alias = os.getenv(TOKEN_ALIAS_ENV, "").strip()
    default_lat = os.getenv(LAT_ENV, "").strip()
    default_lng = os.getenv(LNG_ENV, "").strip()

    source = raw if raw else alias
    if not source:
        raise FvtiError(
            "未配置账号：请设置 {}（每行一个）或兼容别名 {}".format(
                ACCOUNTS_ENV, TOKEN_ALIAS_ENV
            )
        )

    accounts: List[Account] = []
    index = 0
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        index += 1
        accounts.append(parse_account_line(line, index, default_lat, default_lng))

    if not accounts:
        raise FvtiError("账号列表为空")
    return accounts


def modify_decimal_part(num: float) -> str:
    """保留上游定位抖动：改写小数点后第 5-6 位为随机两位。"""
    num_str = "{:.6f}".format(float(num))
    decimal_index = num_str.find(".")
    if decimal_index < 0:
        return num_str
    random_offset = random.randint(0, 99)
    new_decimal_str = "{:02d}".format(random_offset)
    # 与上游一致：保留到小数点后 4 位，再拼接随机两位
    prefix = num_str[: decimal_index + 5]
    suffix = num_str[decimal_index + 7 :] if len(num_str) > decimal_index + 7 else ""
    return prefix + new_decimal_str + suffix


def should_sign(qd_time_text: str, now: Optional[datetime] = None) -> bool:
    try:
        start_str, end_str = qd_time_text.split(" 至 ")
        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
        current_time = (now or now_beijing()).time()
        return start_time <= current_time <= end_time
    except (ValueError, AttributeError):
        return False


def http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    form: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    secrets: Optional[List[str]] = None,
) -> Any:
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        req_headers.update(headers)
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(512).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        masked = redact_secrets("{} {}".format(exc, safe_text(body)), secrets or [])
        raise FvtiError("HTTP {}：{}".format(exc.code, masked)) from exc
    except urllib.error.URLError as exc:
        raise FvtiError("网络错误：{}".format(safe_text(exc.reason))) from exc
    except Exception as exc:
        raise FvtiError("请求失败：{}".format(safe_text(exc))) from exc

    if len(raw) > MAX_BYTES:
        raise FvtiError("响应过大，已中止解析")
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FvtiError("响应不是合法 JSON") from exc


def get_tasks(token: str, timeout: float) -> List[dict]:
    headers = {"Authorization": "Bearer {}".format(token)}
    data = http_json("GET", API_URL_GET, headers=headers, timeout=timeout, secrets=[token])
    if not isinstance(data, dict):
        raise FvtiError("任务列表响应结构异常")
    # 部分失败响应可能带 errcode
    errcode = data.get("errcode")
    if errcode not in (None, 0, "0"):
        raise FvtiError(
            "获取任务失败：{}".format(safe_text(data.get("errmsg") or errcode))
        )
    items = ((data.get("List") or {}) if isinstance(data.get("List"), dict) else {}).get(
        "Items", []
    )
    if items is None:
        return []
    if not isinstance(items, list):
        raise FvtiError("任务 Items 不是列表")
    return [item for item in items if isinstance(item, dict)]


def sign_task(
    token: str,
    task: dict,
    latitude: float,
    longitude: float,
    timeout: float,
) -> Tuple[bool, str]:
    new_lat = modify_decimal_part(latitude)
    new_lng = modify_decimal_part(longitude)
    headers = {"Authorization": "Bearer {}".format(token)}
    form = {
        "ApplyInfo[OrderId]": str(task.get("Id", "")),
        "ApplyInfo[SingnSite]": "{},{}".format(new_lat, new_lng),
    }
    result = http_json(
        "POST",
        API_URL_POST,
        headers=headers,
        form=form,
        timeout=timeout,
        secrets=[token],
    )
    if not isinstance(result, dict):
        return False, "签到响应结构异常"
    if result.get("errcode") == 0 or result.get("errcode") == "0":
        return True, "使用纬度{}经度{}签到成功".format(new_lat, new_lng)
    return False, safe_text(result.get("errmsg") or "未知业务错误")


def extract_identity(task: dict) -> str:
    for key in ("StuName", "StudentName", "Name", "UserName", "nickName", "nickname"):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            # 任务 Name 是签到活动名，不是账号身份；跳过通用 Name 若像任务名
            if key == "Name":
                continue
            return value.strip()
    return ""


def notification_allowed(*, no_notify: bool = False) -> bool:
    if no_notify:
        return False
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    if switch != "auto":
        return False
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selection is None:
        return False
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", selection.strip())
        if item
    ]
    if not selectors:
        return False
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID.lower(),
        script.name.lower(),
        SCRIPT_FILENAME.lower(),
        "candidate.py",
        "output/candidate.py",
        "scripts/fvti_wecom_checkin.py",
        "main.py",
        TITLE.lower(),
    }
    return any(
        fnmatch.fnmatch(identity, selector)
        for selector in selectors
        for identity in identities
    )


def discover_notify_python() -> Optional[Path]:
    candidates: List[Path] = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        candidates.append(Path(directory) / "notify.py")
    candidates.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    cwd = Path.cwd()
    candidates.append(cwd / "notify.py")
    for path in candidates:
        if path.is_file():
            return path
    return None


def send_qinglong_notify(title: str, body: str, *, dry_run: bool = False) -> str:
    if dry_run:
        log("{} 预演模式：跳过真实通知发送".format(ICONS["skipped"]))
        return "dry-run-skipped"
    py_notify = discover_notify_python()
    if py_notify is not None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("ql_notify_module", str(py_notify))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                send = getattr(module, "send", None)
                if callable(send):
                    send(title, body)
                    log("{} 已通过 notify.py 发送通知".format(ICONS["success"]))
                    return "sent-python"
        except Exception as exc:
            log(
                "{} notify.py 发送失败：{}".format(
                    ICONS["warning"], safe_text(exc)
                )
            )

    js_candidates: List[Path] = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        js_candidates.append(Path(directory) / "sendNotify.js")
    js_candidates.extend(
        [
            Path("/ql/data/scripts/sendNotify.js"),
            Path("/ql/scripts/sendNotify.js"),
        ]
    )
    for js_path in js_candidates:
        if not js_path.is_file():
            continue
        try:
            subprocess.run(
                [
                    "node",
                    "-e",
                    "const n=require(process.argv[1]);"
                    "const t=process.argv[2];const b=process.argv[3];"
                    "const fn=n.sendNotify||n.send||n.default;"
                    "Promise.resolve(fn(t,b)).then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1);})",
                    str(js_path),
                    title,
                    body,
                ],
                check=True,
                timeout=30,
                capture_output=True,
                text=True,
            )
            log("{} 已通过 sendNotify.js 发送通知".format(ICONS["success"]))
            return "sent-js"
        except Exception as exc:
            log(
                "{} sendNotify.js 发送失败：{}".format(
                    ICONS["warning"], safe_text(exc)
                )
            )
    log("{} 未找到可用通知模块，保留业务退出码".format(ICONS["warning"]))
    return "unavailable"


def build_notify_body(
    results: List[dict], dry_run: bool, final_status: str, elapsed: float
) -> str:
    lines = [
        "模式：{}".format("断网预演" if dry_run else "正式运行"),
        "状态：{}".format(final_status),
        "账号：成功 {} / 失败 {} / 总计 {}".format(
            sum(1 for r in results if r.get("success")),
            sum(1 for r in results if not r.get("success")),
            len(results),
        ),
        "耗时：{:.2f} 秒".format(elapsed),
    ]
    for item in results:
        name = item.get("displayName") or item.get("label") or "账号"
        outcome = item.get("outcome") or ("success" if item.get("success") else "failure")
        lines.append("- {}：{}".format(name, outcome))
        for err in item.get("errors") or []:
            lines.append("  · {}".format(safe_text(err, 120)))
    return "\n".join(lines)


def run_stage(stage_no: int, name: str, func):
    started = time.time()
    log("阶段{}. {} — 开始".format(stage_no, name))
    try:
        result = func()
        elapsed = int((time.time() - started) * 1000)
        log(
            "阶段{}. {} — 完成（{} ms）{}".format(
                stage_no, name, elapsed, ICONS["success"]
            )
        )
        return result, elapsed, None
    except Exception as exc:
        elapsed = int((time.time() - started) * 1000)
        err = safe_text(exc)
        log(
            "阶段{}. {} — 失败（{} ms）{} {}".format(
                stage_no, name, elapsed, ICONS["failure"], err
            )
        )
        return None, elapsed, err


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


def run_account(
    account: Account,
    timeout: float,
    dry_run: bool,
    force_sign: bool,
) -> dict:
    t0 = time.time()
    stats = StageStats()
    errors: List[str] = []
    secrets = [account.token]

    log("---------- {} ----------".format(account.label))
    log(
        "坐标：纬度 {:.6f} / 经度 {:.6f}".format(account.latitude, account.longitude)
    )

    if dry_run:
        stats.total = 1
        stats.skipped = 1
        log(
            "{} 预演计划：拉取任务列表 → 校验签到窗口 → 提交 GPS 签到（不访问网络）".format(
                ICONS["skipped"]
            )
        )
        log("{} DRY_RUN：参数与流程检查通过，不发送请求".format(ICONS["skipped"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(
            account, stats, errors, success=True, outcome="dry-run"
        )

    stage_no = 1
    tasks, _, err = run_stage(
        stage_no,
        "拉取签到任务列表",
        lambda: get_tasks(account.token, timeout),
    )
    stage_no += 1
    if err is not None:
        stats.total = 1
        stats.failed = 1
        errors.append(redact_secrets(err, secrets))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(account, stats, errors, success=False)

    assert isinstance(tasks, list)
    log("共获取到 {} 个任务".format(len(tasks)))
    if not tasks:
        stats.total = 1
        stats.skipped = 1
        log("{} 当前无签到任务，跳过".format(ICONS["skipped"]))
        stats.elapsedMs = int((time.time() - t0) * 1000)
        return _account_result(
            account, stats, errors, success=True, outcome="no-task"
        )

    signed = 0
    already = 0
    skipped = 0
    failed = 0
    eligible_pending = 0

    for task in tasks:
        task_name = safe_text(task.get("Name") or "未知任务", 80)
        qd_status = str(task.get("QD") or "")
        qd_time = str(task.get("QDTimeText") or "")
        identity = extract_identity(task)
        if identity and not account.display_name:
            account.display_name = identity
            log("{} 公开身份：{}".format(ICONS["success"], identity))

        log("任务：{}｜状态：{}｜时间：{}".format(task_name, qd_status, qd_time or "-"))

        if qd_status != "否":
            already += 1
            log("{} 任务已签到，记为已完成".format(ICONS["alreadyComplete"]))
            continue

        in_window = force_sign or should_sign(qd_time)
        if not in_window:
            skipped += 1
            log("{} 未到签到窗口，跳过".format(ICONS["skipped"]))
            continue

        eligible_pending += 1

        def _do_sign(current=task):
            return sign_task(
                account.token,
                current,
                account.latitude,
                account.longitude,
                timeout,
            )

        result, _, sign_err = run_stage(
            stage_no, "提交签到：{}".format(task_name), _do_sign
        )
        stage_no += 1
        if sign_err is not None:
            failed += 1
            errors.append(redact_secrets(sign_err, secrets))
            continue
        ok, detail = result if isinstance(result, tuple) else (False, "未知结果")
        if ok:
            signed += 1
            log("{} {}".format(ICONS["success"], detail))
        else:
            failed += 1
            msg = redact_secrets(str(detail), secrets)
            errors.append("{}：{}".format(task_name, msg))
            log("{} 签到失败：{}".format(ICONS["failure"], msg))

    stats.total = signed + already + skipped + failed
    if stats.total == 0:
        stats.total = 1
        stats.skipped = 1
    stats.success = signed
    stats.alreadyComplete = already
    stats.skipped = skipped
    stats.failed = failed
    stats.elapsedMs = int((time.time() - t0) * 1000)

    if failed > 0:
        return _account_result(account, stats, errors, success=False, outcome="failure")
    if signed > 0:
        return _account_result(account, stats, errors, success=True, outcome="success")
    if already > 0 and eligible_pending == 0 and skipped == 0:
        return _account_result(
            account, stats, errors, success=True, outcome="already-complete"
        )
    # 窗口外待签或无可签任务：视为本轮成功跳过（适配高频 cron）
    return _account_result(account, stats, errors, success=True, outcome="skipped-window")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    no_notify = "--no-notify" in argv
    dry_run = truthy_env(DRY_RUN_ENV)
    started_at = now_beijing()
    task_t0 = time.time()

    print("=" * 60, flush=True)
    log("任务：{}".format(TITLE))
    log("开始时间：{}".format(stamp_full()))
    log("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 60, flush=True)

    notify_status = "disabled"
    results: List[dict] = []
    config_error = ""
    exit_code = 0
    final_status = "SUCCESS"
    accounts: List[Account] = []
    timeout = float(DEFAULT_TIMEOUT)
    force_sign = False

    try:
        timeout = env_timeout()
        force_sign = env_bool(FORCE_SIGN_ENV, False)
        accounts = parse_accounts()
    except Exception as exc:
        config_error = safe_text(exc)
        log("{} 配置错误：{}".format(ICONS["failure"], config_error))
        exit_code = 2
        final_status = "CONFIG_ERROR"
        accounts = []

    log("账号数量：{}".format(len(accounts)))
    if accounts and not config_error:
        log("HTTP 超时：{} 秒".format(timeout))
        log("强制忽略时间窗：{}".format("开启" if force_sign else "关闭"))

    if accounts and not config_error:
        for account in accounts:
            try:
                results.append(run_account(account, timeout, dry_run, force_sign))
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
        final_status = "DRY-RUN"
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
            title = "{} {}".format(ICONS["failure"], TITLE)
        elif dry_run:
            title = "{} {}（预演）".format(ICONS["skipped"], TITLE)
        elif final_status == "SUCCESS":
            title = "{} {}".format(ICONS["success"], TITLE)
        elif final_status == "PARTIAL_FAILURE":
            title = "{} {}".format(ICONS["warning"], TITLE)
        else:
            title = "{} {}".format(ICONS["failure"], TITLE)
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

    summary_status = final_status.lower().replace("_", "-")
    if dry_run and exit_code == 0:
        summary_status = "dry-run"
    summary = {
        "catalogId": CATALOG_ID,
        "task": TITLE,
        "status": summary_status,
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
    print("TASK_SUMMARY={}".format(json.dumps(summary, ensure_ascii=False)), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
