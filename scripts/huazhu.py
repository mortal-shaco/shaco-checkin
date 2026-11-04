#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 华住会签到
# cron: 5 9 * * *
# Copyright (C) 2026  Dimlitter
# Licensed under the GNU General Public License v3.0
#
# 维护说明：本文件基于 Dimlitter/huazhu-auto-checkin 的 checkin.py（GPL-3.0）
# 独立维护。保留纯 HTTP 签到、签到状态摘要、超时重试与青龙元信息；
# 移除 & 多账号分隔、内置 PushPlus、默认长时间随机错峰、常驻 --loop、
# 以及可选 token 文件自动覆写。账号仅按换行分隔；通知遵循青龙策略。
"""
华住会签到（独立维护版）

功能：
  - 使用 userToken Cookie 调用华住会签到接口完成每日签到
  - 查询签到头信息（积分、今年累计签到天数）；若返回公开身份则原样打印
  - 支持多账号（每行一个 token）、完全断网预演、时间轴日志与青龙通知

参数获取：
  打开华住会 App 或网页并登录，抓包任意发往 appgw.huazhu.com / *.huazhu.com
  的请求，复制 Cookie 中的 userToken 值到环境变量 HZ_TOKEN。
  每个非空行一个账号；不要用 & 或 @ 分隔账号。

环境变量：
  HZ_TOKEN           必填。userToken；每行一个账号
  HZ_DRY_RUN         1/true/yes/on 开启完全断网预演
  HZ_TIMEOUT         单次请求超时秒数，默认 25，范围 1~60
  HZ_RETRY_TIMES     遇 429/5xx/网络异常的额外重试次数，默认 3，范围 0~5
  HZ_RETRY_DELAY     重试基础间隔秒数（线性递增），默认 5，范围 0~120
  HZ_ACCOUNT_GAP     多账号间隔秒数，默认 2，范围 0~30
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略
"""

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
            "e2926d00ddd5ce46",
            "scripts/huazhu_checkin.py",
            "huazhu_checkin.py",
            "candidate.py",
            "checkin.py",
            "huazhu",
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
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "e2926d00ddd5ce46"
TASK_NAME = "华住会签到"
API_BASE = "https://appgw.huazhu.com"
SIGN_IN_PATH = "/game/sign_in"
SIGN_HEADER_PATH = "/game/sign_header"
REFERER = "https://cdn.huazhu.com/hzapp-signinfe/"
ORIGIN = "https://cdn.huazhu.com"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/114 Mobile Safari/537.36"
)
MAX_RESPONSE_BYTES = 256 * 1024
RETRY_HTTP_CODES = {429, 500, 502, 503, 504}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SECRETS: List[str] = []


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def parse_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip() or str(default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("{} 必须是 {} 到 {} 的整数".format(name, minimum, maximum)) from exc
    if value < minimum or value > maximum:
        raise ValueError("{} 必须是 {} 到 {} 的整数".format(name, minimum, maximum))
    return value


def redact(text: Any, limit: int = 200) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted({item for item in SECRETS if item}, key=len, reverse=True):
        if secret and secret in value:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(
        r"(?i)(cookie|token|userToken|authorization|session|signature|device[_-]?id)\s*[:=]\s*[^\s,;]+",
        "[敏感字段已隐藏]",
        value,
    )
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    return value[:limit] if value else "未提供业务消息"


def load_accounts() -> List[str]:
    """每行一个 userToken；token 内若含 & 或 @ 不作为账号分隔符。"""
    raw = os.getenv("HZ_TOKEN", "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise ValueError("未配置 HZ_TOKEN；请按每行一个 userToken 填写")
    for token in accounts:
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in token):
            raise ValueError("HZ_TOKEN 含控制字符，请重新复制 userToken")
        if len(token) < 8:
            raise ValueError("HZ_TOKEN 长度过短，请确认复制了完整 userToken")
        SECRETS.append(token)
    return accounts


def extract_public_identity(content: Dict[str, Any]) -> Optional[str]:
    for key in (
        "nickName",
        "nickname",
        "userName",
        "username",
        "displayName",
        "memberName",
        "name",
        "uid",
        "userId",
        "memberId",
    ):
        value = content.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
            continue
        if redact(text, len(text)) != text:
            continue
        return text
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("接口重定向已阻止，未转发凭据")


def http_get_json(path: str, token: str, timeout: float, retries: int, retry_delay: int) -> Dict[str, Any]:
    url = API_BASE + path
    headers = {
        "Cookie": "userToken=" + token,
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Origin": ORIGIN,
        "Accept": "application/json, text/plain, */*",
    }
    request = urllib.request.Request(url, headers=headers, method="GET")
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if status < 200 or status >= 300:
                raise RuntimeError("接口返回 HTTP {}".format(status))
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("接口响应超过安全上限")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("接口未返回有效 JSON") from exc
            if not isinstance(payload, dict):
                raise RuntimeError("接口 JSON 顶层结构无效")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = RuntimeError("接口返回 HTTP {}".format(exc.code))
            if exc.code in RETRY_HTTP_CODES and attempt < retries:
                wait = retry_delay * (attempt + 1)
                log(
                    "{} 请求 {} 返回 HTTP {}，{} 秒后重试（{}/{}）".format(
                        ICONS["warning"], path.split("?", 1)[0], exc.code, wait, attempt + 1, retries
                    )
                )
                if wait > 0:
                    time.sleep(wait)
                continue
            raise last_error from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            reason_name = type(reason).__name__ if reason is not None else "网络错误"
            last_error = RuntimeError("网络请求失败（{}）".format(reason_name))
            if attempt < retries:
                wait = retry_delay * (attempt + 1)
                log(
                    "{} 请求 {} 网络异常，{} 秒后重试（{}/{}）".format(
                        ICONS["warning"], path.split("?", 1)[0], wait, attempt + 1, retries
                    )
                )
                if wait > 0:
                    time.sleep(wait)
                continue
            raise last_error from exc
        except TimeoutError as exc:
            last_error = RuntimeError("网络请求超时")
            if attempt < retries:
                wait = retry_delay * (attempt + 1)
                log(
                    "{} 请求 {} 超时，{} 秒后重试（{}/{}）".format(
                        ICONS["warning"], path.split("?", 1)[0], wait, attempt + 1, retries
                    )
                )
                if wait > 0:
                    time.sleep(wait)
                continue
            raise last_error from exc
    if last_error:
        raise last_error
    raise RuntimeError("请求未取得结果")


def classify_sign(payload: Dict[str, Any]) -> Tuple[str, str]:
    code = payload.get("code")
    message = str(payload.get("message") or payload.get("msg") or "").strip()
    if code == 200 or code == "200":
        return "success", "签到成功"
    if code == 5004 or code == "5004":
        return "already", "今日已签到"
    if code in (401, "401", 403, "403"):
        raise RuntimeError("鉴权失败，可能 userToken 已过期，请更新 HZ_TOKEN")
    hint = redact(message, 80) if message else "可能 userToken 已过期，请更新 HZ_TOKEN"
    raise RuntimeError("签到业务失败（code={}）：{}".format(code, hint))


def format_header_summary(payload: Dict[str, Any]) -> Tuple[Optional[str], str]:
    if payload.get("code") not in (200, "200", 0, "0", None):
        # 部分响应仅返回 content；有明确失败码时拒绝当作成功
        if payload.get("content") is None:
            raise RuntimeError("签到状态查询业务失败（code={}）".format(payload.get("code")))
    content = payload.get("content")
    if not isinstance(content, dict):
        raise RuntimeError("签到状态响应缺少 content")
    identity = extract_public_identity(content)
    parts = []
    point = content.get("memberPoint")
    year_count = content.get("yearSignInCount")
    if point is not None:
        parts.append("积分{}".format(point))
    if year_count is not None:
        parts.append("今年累计签到{}天".format(year_count))
    if not parts:
        raise RuntimeError("签到状态响应缺少积分或累计签到天数字段")
    return identity, " ".join(parts)


def run_account(
    index: int,
    token: str,
    dry_run: bool,
    timeout: float,
    retries: int,
    retry_delay: int,
) -> Dict[str, Any]:
    started = time.monotonic()
    stages = ["每日签到", "签到状态查询"]
    total = len(stages)
    stats = {"total": total, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    identity = "账号{}".format(index)
    errors: List[str] = []
    print("\n========== {} ==========".format(identity), flush=True)

    for stage_no, stage_name in enumerate(stages, 1):
        stage_started = time.monotonic()
        prefix = "[账号{}][{}/{}]".format(index, stage_no, total)
        log("{} {}开始".format(prefix, stage_name))
        try:
            if dry_run:
                stats["skipped"] += 1
                log(
                    "{} {} {}：已校验 userToken 配置，未发起网络请求（{:.2f}秒）".format(
                        prefix, ICONS["skipped"], stage_name, time.monotonic() - stage_started
                    )
                )
                continue
            if stage_no == 1:
                path = "{}?date={}".format(SIGN_IN_PATH, int(time.time()))
                payload = http_get_json(path, token, timeout, retries, retry_delay)
                outcome, message = classify_sign(payload)
                if outcome == "already":
                    stats["already"] += 1
                    icon = ICONS["alreadyComplete"]
                else:
                    stats["success"] += 1
                    icon = ICONS["success"]
                log(
                    "{} {} {}（{:.2f}秒）".format(
                        prefix, icon, message, time.monotonic() - stage_started
                    )
                )
            else:
                payload = http_get_json(SIGN_HEADER_PATH, token, timeout, retries, retry_delay)
                found_identity, summary = format_header_summary(payload)
                if found_identity:
                    identity = found_identity
                    log("{} 公开身份：{}".format(prefix, found_identity))
                stats["success"] += 1
                log(
                    "{} {} {}（{:.2f}秒）".format(
                        prefix, ICONS["success"], summary, time.monotonic() - stage_started
                    )
                )
        except Exception as exc:
            stats["failed"] += 1
            if isinstance(exc, (RuntimeError, ValueError)):
                message = redact(exc)
            else:
                message = "处理失败（{}）".format(type(exc).__name__)
            errors.append(message)
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], message, time.monotonic() - stage_started
                )
            )

    elapsed = time.monotonic() - started
    ok = stats["failed"] == 0
    result_label = "DRY_RUN" if dry_run and ok else ("SUCCESS" if ok else "FAILED")
    log(
        "[账号{}] 结果={}；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            index,
            result_label,
            identity,
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
        "huazhu_checkin.py",
        "scripts/huazhu_checkin.py",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value not in TRUE_VALUES and value != "auto":
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
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


def print_summary(summary: Dict[str, Any]) -> None:
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def finish_config_error(started_at: str, overall_started: float, dry_run: bool, message: str) -> int:
    log("账号数量：0")
    log("[0/0] {} 配置错误：{}".format(ICONS["failure"], message))
    body = "账号总数：0；成功：0；失败：1；状态：配置错误"
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()
    print("-" * 56)
    print("账号结果：总数 0，成功 0，失败 1")
    print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0")
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：CONFIG_ERROR")
    print_summary(
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
        }
    )
    return 2


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("HZ_DRY_RUN")
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        timeout = float(parse_int_env("HZ_TIMEOUT", 25, 1, 60))
        retries = parse_int_env("HZ_RETRY_TIMES", 3, 0, 5)
        retry_delay = parse_int_env("HZ_RETRY_DELAY", 5, 0, 120)
        account_gap = parse_int_env("HZ_ACCOUNT_GAP", 2, 0, 30)
        accounts = load_accounts()
    except ValueError as exc:
        return finish_config_error(started_at, overall_started, dry_run, redact(exc))

    log("账号数量：{}".format(len(accounts)))
    results: List[Dict[str, Any]] = []
    for index, token in enumerate(accounts, 1):
        results.append(run_account(index, token, dry_run, timeout, retries, retry_delay))
        if not dry_run and index < len(accounts) and account_gap > 0:
            time.sleep(account_gap)

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
    elif account_failed == 0:
        status = "success"
        exit_code = 0
    elif account_success:
        status = "partial-failure"
        exit_code = 1
    else:
        status = "failure"
        exit_code = 1

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), account_success, account_failed, status
    )
    notify_state = send_notification(TASK_NAME, body, dry_run)
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
    final_status = {
        "dry-run": "DRY-RUN",
        "success": "SUCCESS",
        "partial-failure": "PARTIAL-FAILURE",
        "failure": "FAILURE",
    }.get(status, status.upper())
    print("最终状态：{}".format(final_status))
    print_summary(
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
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
