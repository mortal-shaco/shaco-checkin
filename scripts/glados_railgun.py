#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: GLaDOS/Railgun 签到
# cron: 21 1 * * *
# SPDX-License-Identifier: GPL-3.0-only
"""GLaDOS / Railgun 双站点签到与可选积分兑换（仅标准库）。

来源：zzguang83325/Glados-Railgun-checkin，checkin.py 与 logging_config.py；
许可证 GPL-3.0。上游提交 97109b0ca9eabb56341fe78454e54a0f6163d9db。
本维护版转为青龙可调度独立任务，内联日志配置，移除 PushDeer / pypushdeer
与私有仓库依赖；HTTP 由标准库实现。

保留上游能力：在 glados.cloud 与 railgun.info 查询剩余天数、签到、查询积分，
以及可选积分兑换（默认不兑换）；设备不匹配时按 loginDevice 切换 UA 重试。
与已发布 scripts/glados.py（单站点 rocks/cloud、无兑换、无 railgun）产品边界不同。

参数：
GLADOS_COOKIES：每个非空行一个完整 Cookie；不用 & 或 @ 分隔账号。
  登录 https://glados.cloud 或 https://railgun.info 后，在开发者工具网络面板
  找到 /api/user/status 或 /api/user/checkin 请求，复制请求头 Cookie 完整值。
GLADOS_EXCHANGE_PLAN：可选 none/plan100/plan200/plan500；默认 none（不自动兑换）。
GLADOS_RAILGUN_SITES：可选站点列表，逗号分隔；默认 glados.cloud,railgun.info。
GLADOS_RAILGUN_TIMEOUT：单次请求超时秒数，默认 30，范围 5..120。
GLADOS_RAILGUN_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：见契约。
上游未声明 cron；本版建议每天 01:15。不打印 Cookie、Token、原始响应。

Copyright (C) 上游作者及贡献者（zzguang83325/Glados-Railgun-checkin）
本程序为自由软件：你可以按自由软件基金会发布的 GNU 通用公共许可证第 3 版
（或你选择的更高版本）重新分发和/或修改它。本程序不提供任何担保。
完整许可证文本见 https://www.gnu.org/licenses/gpl-3.0.html
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
            "6c2dc52b4d88710b",
            "scripts/glados_railgun.py",
            "glados_railgun.py",
            "candidate.py",
            "checkin.py",
            "glados-railgun",
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
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "GLaDOS/Railgun 签到"
CATALOG_ID = "6c2dc52b4d88710b"
DEFAULT_SITES = ("glados.cloud", "railgun.info")
EXCHANGE_PLANS = {"plan100": 100, "plan200": 200, "plan500": 500}
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
MAX_RESPONSE_BYTES = 1024 * 1024
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
PLATFORM_UA = {
    "Windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "macOS": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Linux": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "iPhone": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Android": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
}
SECRETS: List[str] = []


class TaskError(Exception):
    """仅承载脚本生成的安全错误文案。"""


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


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if value and value not in SECRETS:
        SECRETS.append(value)


def safe_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(
        r"(?i)(cookie|token|session|authorization|signature|device[_-]?id)\s*[:=]\s*[^\s,;]+",
        "[敏感字段已隐藏]",
        text,
    )
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit] if text else "未提供业务消息"


def parse_timeout() -> float:
    raw = env("GLADOS_RAILGUN_TIMEOUT", "30") or "30"
    try:
        value = float(raw)
    except ValueError as exc:
        raise TaskError("GLADOS_RAILGUN_TIMEOUT 必须是数字秒数") from exc
    if value < 5 or value > 120:
        raise TaskError("GLADOS_RAILGUN_TIMEOUT 必须在 5 到 120 秒之间")
    return value


def parse_sites() -> List[str]:
    raw = env("GLADOS_RAILGUN_SITES", ",".join(DEFAULT_SITES)) or ",".join(DEFAULT_SITES)
    sites = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not sites:
        raise TaskError("GLADOS_RAILGUN_SITES 未包含有效站点")
    allowed = set(DEFAULT_SITES)
    for site in sites:
        if site not in allowed:
            raise TaskError("GLADOS_RAILGUN_SITES 仅支持 glados.cloud 与 railgun.info")
    # 保序去重
    ordered: List[str] = []
    for site in sites:
        if site not in ordered:
            ordered.append(site)
    return ordered


def parse_exchange_plan() -> str:
    raw = env("GLADOS_EXCHANGE_PLAN", "none").lower() or "none"
    if raw in ("none", "", "0", "off", "false", "no"):
        return "none"
    if raw not in EXCHANGE_PLANS:
        raise TaskError("GLADOS_EXCHANGE_PLAN 只能是 none、plan100、plan200 或 plan500")
    return raw


def load_accounts() -> List[str]:
    raw = os.environ.get("GLADOS_COOKIES", "")
    if not raw.strip():
        raise TaskError(
            "未配置 GLADOS_COOKIES；请按每行一个完整 Cookie 填写，"
            "从官网请求头复制 Cookie，不要使用 & 或 @ 分隔账号"
        )
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise TaskError("GLADOS_COOKIES 已设置但没有有效账号行")
    for cookie in accounts:
        if any(ord(c) < 32 or ord(c) == 127 for c in cookie):
            raise TaskError("Cookie 含控制字符，请重新复制完整请求头")
        if not any(
            key.strip() and value.strip()
            for key, sep, value in (item.partition("=") for item in cookie.split(";"))
            if sep
        ):
            raise TaskError("Cookie 格式无效，需要非空的名称=值")
        remember_secret(cookie)
        for item in cookie.split(";"):
            _key, delimiter, value = item.strip().partition("=")
            if delimiter and value.strip():
                remember_secret(value.strip())
    return accounts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向已阻止，未转发凭据")


def request_json(
    method: str,
    url: str,
    cookie: str,
    timeout: float,
    form: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise TaskError("仅允许 HTTPS 业务地址")
    headers = {
        "Origin": "https://{}".format(parsed.hostname),
        "Referer": "https://{}/".format(parsed.hostname),
        "User-Agent": user_agent or PLATFORM_UA["Windows"],
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie,
    }
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise TaskError("接口返回 HTTP {}".format(exc.code)) from None
    except urllib.error.URLError:
        raise TaskError("网络请求失败") from None
    except TimeoutError:
        raise TaskError("网络请求超时") from None

    if status < 200 or status >= 300:
        raise TaskError("接口返回 HTTP {}".format(status))
    if len(body) > MAX_RESPONSE_BYTES:
        raise TaskError("接口响应超过 1 MiB 安全上限")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TaskError("接口未返回有效 JSON") from None
    if not isinstance(payload, dict):
        raise TaskError("接口 JSON 顶层结构无效")
    return payload


def extract_identity(data: Dict[str, Any]) -> Optional[str]:
    for key in ("nickname", "displayName", "username", "name", "email", "uid", "id"):
        value = data.get(key)
        if type(value) in (str, int) and str(value).strip():
            identity = str(value).strip()
            if any(ord(c) < 32 or ord(c) == 127 for c in identity):
                continue
            if safe_text(identity, len(identity)) != identity:
                continue
            return identity
    return None


def query_status(domain: str, cookie: str, timeout: float, ua: str) -> Tuple[str, Optional[str]]:
    url = "https://{}/api/user/status".format(domain)
    payload = request_json("GET", url, cookie, timeout, user_agent=ua)
    code = payload.get("code")
    if code is not None and code not in (0, "0"):
        raise TaskError("状态查询业务失败")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TaskError("状态响应缺少 data")
    left = data.get("leftDays")
    if left is None:
        raise TaskError("状态响应缺少剩余天数")
    try:
        days = int(float(left))
    except (TypeError, ValueError):
        raise TaskError("剩余天数字段无效") from None
    return "{} 天".format(days), extract_identity(data)


def classify_checkin(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    code = payload.get("code")
    message = str(payload.get("message") or payload.get("msg") or "")
    points = str(payload.get("points", "0"))
    if code in (0, "0"):
        return "success", "签到成功", points
    if code in (1, "1"):
        return "alreadyComplete", "重复签到", "0"
    if code in (4, "4") and payload.get("reason") == "device-mismatch":
        device = str(payload.get("loginDevice") or "")
        raise TaskError("设备平台不匹配:{}".format(device or "unknown"))
    raise TaskError("签到业务失败")


def perform_checkin(
    domain: str,
    cookie: str,
    timeout: float,
    ua_cache: Dict[str, str],
) -> Tuple[str, str, str, str]:
    url = "https://{}/api/user/checkin".format(domain)
    form = {"token": domain}
    start_ua = ua_cache.get("_last") or PLATFORM_UA["Windows"]
    payload = request_json("POST", url, cookie, timeout, form=form, user_agent=start_ua)
    if payload.get("code") in (4, "4") and payload.get("reason") == "device-mismatch":
        login_device = str(payload.get("loginDevice") or "")
        recover = ua_cache.get(login_device) or PLATFORM_UA.get(login_device)
        if recover and recover != start_ua:
            if login_device in PLATFORM_UA:
                ua_cache[login_device] = PLATFORM_UA[login_device]
            payload = request_json("POST", url, cookie, timeout, form=form, user_agent=recover)
            start_ua = recover
    outcome, message, points = classify_checkin(payload)
    if outcome in ("success", "alreadyComplete"):
        ua_cache["_last"] = start_ua
    return outcome, message, points, start_ua


def query_points(domain: str, cookie: str, timeout: float, ua: str) -> str:
    url = "https://{}/api/user/points".format(domain)
    payload = request_json("GET", url, cookie, timeout, user_agent=ua)
    code = payload.get("code")
    if code is not None and code not in (0, "0"):
        raise TaskError("积分查询业务失败")
    points = payload.get("points")
    if points is None:
        raise TaskError("积分响应缺少 points")
    try:
        value = int(float(points))
    except (TypeError, ValueError):
        raise TaskError("积分数值无效") from None
    return "{} 积分".format(value)


def perform_exchange(
    domain: str,
    cookie: str,
    timeout: float,
    ua: str,
    plan: str,
) -> Tuple[str, str]:
    url = "https://{}/api/user/exchange".format(domain)
    payload = request_json(
        "POST",
        url,
        cookie,
        timeout,
        form={"planType": plan},
        user_agent=ua,
    )
    code = payload.get("code")
    if code in (0, "0"):
        return "success", "兑换成功:{}".format(plan)
    return "failure", "兑换失败"


def run_stage(
    prefix: str,
    name: str,
    dry_run: bool,
    action,
) -> Tuple[str, str]:
    started = time.monotonic()
    log("{} {}开始".format(prefix, name))
    try:
        if dry_run:
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, ICONS["skipped"], "断网预演：已校验配置，未发起网络请求", time.monotonic() - started
                )
            )
            return "skipped", "断网预演跳过"
        outcome, message = action()
        icon = ICONS.get(outcome, ICONS["success"])
        log("{} {} {}（{:.2f}秒）".format(prefix, icon, message, time.monotonic() - started))
        return outcome, message
    except TaskError as exc:
        message = safe_text(exc)
        log("{} {} {}（{:.2f}秒）".format(prefix, ICONS["failure"], message, time.monotonic() - started))
        return "failure", message
    except Exception:
        message = "处理失败"
        log("{} {} {}（{:.2f}秒）".format(prefix, ICONS["failure"], message, time.monotonic() - started))
        return "failure", message


def run_account(
    index: int,
    cookie: str,
    sites: List[str],
    exchange_plan: str,
    timeout: float,
    dry_run: bool,
) -> Dict[str, Any]:
    started = time.monotonic()
    identity = "账号{}".format(index)
    stats = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    errors: List[str] = []
    domain_ok = 0
    print("\n========== {} ==========".format(identity), flush=True)

    stages_per_domain = 3 + (1 if exchange_plan != "none" else 0)
    total_stages = len(sites) * stages_per_domain
    stage_no = 0

    for domain in sites:
        ua_cache: Dict[str, str] = {}
        current_ua = PLATFORM_UA["Windows"]
        log("[账号{}] 站点 {} 开始".format(index, domain))

        stage_no += 1
        prefix = "[账号{}][{}/{}]".format(index, stage_no, total_stages)
        stats["total"] += 1

        def status_action(domain=domain, ua=current_ua):
            days, found = query_status(domain, cookie, timeout, ua)
            nonlocal identity
            if found:
                identity = found
                return "success", "身份：{}；剩余：{}".format(found, days)
            return "success", "剩余：{}".format(days)

        outcome, message = run_stage(prefix, "查询剩余天数", dry_run, status_action)
        if outcome == "skipped":
            stats["skipped"] += 1
        elif outcome == "success":
            stats["success"] += 1
        else:
            stats["failed"] += 1
            errors.append("{}:{}".format(domain, message))
            # 状态失败不阻断签到

        stage_no += 1
        prefix = "[账号{}][{}/{}]".format(index, stage_no, total_stages)
        stats["total"] += 1
        checkin_outcome = "failure"

        def checkin_action(domain=domain):
            nonlocal current_ua, checkin_outcome
            outcome_local, msg, points, used_ua = perform_checkin(domain, cookie, timeout, ua_cache)
            current_ua = used_ua
            checkin_outcome = outcome_local
            detail = msg if points in ("0", "") else "{}，获得 {} 积分".format(msg, points)
            return outcome_local, detail

        outcome, message = run_stage(prefix, "执行签到", dry_run, checkin_action)
        if outcome == "skipped":
            stats["skipped"] += 1
            domain_ok += 1
        elif outcome == "alreadyComplete":
            stats["already"] += 1
            domain_ok += 1
        elif outcome == "success":
            stats["success"] += 1
            domain_ok += 1
        else:
            stats["failed"] += 1
            errors.append("{}:{}".format(domain, message))

        stage_no += 1
        prefix = "[账号{}][{}/{}]".format(index, stage_no, total_stages)
        stats["total"] += 1

        def points_action(domain=domain, ua=current_ua):
            return "success", "总积分：{}".format(query_points(domain, cookie, timeout, ua))

        outcome, message = run_stage(prefix, "查询总积分", dry_run, points_action)
        if outcome == "skipped":
            stats["skipped"] += 1
        elif outcome == "success":
            stats["success"] += 1
        else:
            stats["failed"] += 1
            errors.append("{}:{}".format(domain, message))

        if exchange_plan != "none":
            stage_no += 1
            prefix = "[账号{}][{}/{}]".format(index, stage_no, total_stages)
            stats["total"] += 1
            required = EXCHANGE_PLANS[exchange_plan]

            def exchange_action(domain=domain, ua=current_ua, plan=exchange_plan):
                # 仅在签到成功或已签到后尝试兑换；失败计入统计但不否决账号签到结果
                if checkin_outcome not in ("success", "alreadyComplete"):
                    return "skipped", "签到未成功，跳过兑换"
                outcome_local, msg = perform_exchange(domain, cookie, timeout, ua, plan)
                if outcome_local != "success":
                    return "failure", "{}（需要约 {} 积分）".format(msg, required)
                return "success", msg

            outcome, message = run_stage(
                prefix,
                "积分兑换 {}".format(exchange_plan),
                dry_run,
                exchange_action,
            )
            if outcome == "skipped":
                stats["skipped"] += 1
            elif outcome == "success":
                stats["success"] += 1
            else:
                stats["failed"] += 1
                errors.append("{}:{}".format(domain, message))
                log(
                    "[账号{}] {} 兑换未成功，不影响签到业务判定".format(
                        index, ICONS["warning"]
                    )
                )

    elapsed = time.monotonic() - started
    # 账号成功：每个配置站点的签到均为成功/重复（或断网预演跳过）；状态/积分/兑换失败不否决
    ok = domain_ok == len(sites)
    if dry_run and ok:
        result = "DRY_RUN"
    elif ok:
        result = "SUCCESS"
    else:
        result = "FAILED"
    log(
        "[账号{}] 身份={}；结果={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            index,
            identity,
            result,
            stats["total"],
            stats["success"],
            stats["already"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return {
        "index": index,
        "identity": identity,
        "ok": ok,
        "stats": stats,
        "elapsed": elapsed,
        "errors": errors,
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
        "checkin.py",
        "glados_railgun.py",
        "scripts/glados_railgun.py",
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
    if value not in TRUE_VALUES and value != "auto":
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
    paths.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
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
                log("通知状态：{} 已调用".format("notify.py" if path else "notify.send"))
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

    log("{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(ICONS["warning"]))
    return "unavailable"


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("GLADOS_RAILGUN_DRY_RUN")
    print("=" * 56)
    print("{} | 独立维护版".format(TITLE))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        timeout = parse_timeout()
        sites = parse_sites()
        exchange_plan = parse_exchange_plan()
        accounts = load_accounts()
    except TaskError as exc:
        log("账号数量：0")
        log("[0/0] {} 配置错误：{}".format(ICONS["failure"], safe_text(exc)))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误"
        notify_state = send_notification(TITLE, body, dry_run)
        finished_at = now_text()
        print("-" * 56)
        print("账号结果：总数 0，成功 0，失败 1")
        print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0")
        print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
        print("完成时间：{}".format(finished_at))
        print("通知状态：{}".format(notify_state))
        print("最终状态：CONFIG_ERROR")
        print(
            "TASK_SUMMARY="
            + json.dumps(
                {
                    "status": "configuration-error",
                    "mode": "dry-run" if dry_run else "live",
                    "accounts": {"total": 0, "success": 0, "failed": 1},
                    "tasks": {
                        "total": 0,
                        "success": 0,
                        "alreadyComplete": 0,
                        "skipped": 0,
                        "failed": 0,
                    },
                    "notification": notify_state,
                    "startedAt": started_at,
                    "finishedAt": finished_at,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 2

    log("账号数量：{}".format(len(accounts)))
    log(
        "站点：{}；兑换计划：{}；超时：{}秒".format(
            ",".join(sites), exchange_plan, int(timeout) if timeout == int(timeout) else timeout
        )
    )
    results = [
        run_account(i, cookie, sites, exchange_plan, timeout, dry_run)
        for i, cookie in enumerate(accounts, 1)
    ]
    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }

    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
        final_label = "DRY_RUN"
        log("断网预演通过")
    elif account_failed == 0:
        status = "success"
        exit_code = 0
        final_label = "SUCCESS"
    elif account_success:
        status = "partial-failure"
        exit_code = 1
        final_label = "PARTIAL_FAILURE"
    else:
        status = "failure"
        exit_code = 1
        final_label = "FAILURE"

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), account_success, account_failed, status
    )
    notify_state = send_notification(TITLE, body, dry_run)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    print("\n" + "-" * 56)
    print("账号结果：总数 {}，成功 {}，失败 {}".format(len(results), account_success, account_failed))
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
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
