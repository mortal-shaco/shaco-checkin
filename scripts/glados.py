#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: GLaDOS每日签到
# cron: 30 0 * * *
# SPDX-License-Identifier: Apache-2.0

"""
File: checkin.py(GLaDOS签到)
Author: Hennessey
cron: 30 0 * * *
new Env('GLaDOS每日签到');
Update: 2023/7/27

维护说明：本文件在保留原作者署名、签到和状态查询能力的基础上，增加了
多账号、超时、业务成功校验、完全断网预演、脱敏日志和青龙通知集成。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('2d633fe3129937b6', 'scripts/glados.py', 'glados.py', 'glados')
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


CATALOG_ID = "2d633fe3129937b6"
TASK_NAME = "GLaDOS每日签到"
CHECKIN_URL = "https://glados.rocks/api/user/checkin"
STATUS_URL = "https://glados.rocks/api/user/status"
REFERER = "https://glados.rocks/console/checkin"
ORIGIN = "https://glados.rocks"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
MAX_RESPONSE_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def parse_timeout() -> float:
    raw = os.getenv("GLADOS_TIMEOUT", "15").strip()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("GLADOS_TIMEOUT 必须是数字秒数")
    if value < 1 or value > 60:
        raise ValueError("GLADOS_TIMEOUT 必须在 1 到 60 秒之间")
    return value


def load_accounts() -> List[str]:
    """每个非空行是一个账号；不再把 Cookie 中合法的 & 当作账号分隔符。"""
    raw = os.getenv("GR_COOKIE", "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise ValueError("未配置 GR_COOKIE；请按每行一个完整 Cookie 填写")
    return accounts


def safe_business_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else "未提供业务消息"


def request_json(
    method: str,
    url: str,
    cookie: str,
    timeout: float,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {
        "Cookie": cookie,
        "Referer": REFERER,
        "Origin": ORIGIN,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("接口返回 HTTP {}".format(exc.code))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        reason_name = type(reason).__name__ if reason is not None else "网络错误"
        raise RuntimeError("网络请求失败（{}）".format(reason_name))
    except TimeoutError:
        raise RuntimeError("网络请求超时")

    if status < 200 or status >= 300:
        raise RuntimeError("接口返回 HTTP {}".format(status))
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("接口响应超过 1 MiB 安全上限")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("接口未返回有效 JSON")
    if not isinstance(result, dict):
        raise RuntimeError("接口 JSON 顶层结构无效")
    return result


def classify_checkin(response: Dict[str, Any]) -> Tuple[str, str]:
    code = response.get("code")
    message = safe_business_text(response.get("message"))
    if code in (0, "0"):
        return "success", message

    normalized = message.casefold()
    already_markers = (
        "checkin repeats",
        "check-in repeats",
        "already check",
        "already signed",
        "try tomorrow",
        "已签到",
        "重复签到",
        "明天再来",
    )
    if code in (1, "1") and any(marker in normalized for marker in already_markers):
        return "already", message
    raise RuntimeError("签到业务失败：code={}，message={}".format(code, message))


def parse_status(response: Dict[str, Any]) -> Tuple[str, str]:
    code = response.get("code")
    if code not in (None, 0, "0"):
        raise RuntimeError("状态业务失败：code={}".format(code))
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("状态响应缺少 data")
    identity = data.get("email") or data.get("username") or data.get("name")
    left_days = data.get("leftDays")
    if not isinstance(identity, str) or not identity.strip():
        raise RuntimeError("状态响应缺少账号身份")
    if left_days is None or not str(left_days).strip():
        raise RuntimeError("状态响应缺少剩余天数")
    return safe_business_text(identity, 120), safe_business_text(str(left_days).split(".", 1)[0], 40)


def run_account(index: int, cookie: str, timeout: float, dry_run: bool) -> Dict[str, Any]:
    started = time.monotonic()
    stats = {"total": 2, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    label = "账号{}".format(index)
    errors: List[str] = []

    print("\n========== {} ==========".format(label), flush=True)
    stage_started = time.monotonic()
    log("[{}][1/2] 签到请求开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][1/2] ⏭️ 断网预演：已校验签到请求配置，未发起网络请求（{:.2f}秒）".format(
            label, time.monotonic() - stage_started
        ))
    else:
        try:
            response = request_json("POST", CHECKIN_URL, cookie, timeout, {"token": "glados.one"})
            outcome, message = classify_checkin(response)
            if outcome == "already":
                stats["already"] += 1
                icon = "☑️"
            else:
                stats["success"] += 1
                icon = "✅"
            log("[{}][1/2] {} {}（{:.2f}秒）".format(
                label, icon, message, time.monotonic() - stage_started
            ))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            log("[{}][1/2] ❌ {}（{:.2f}秒）".format(
                label, safe_business_text(exc), time.monotonic() - stage_started
            ))

    stage_started = time.monotonic()
    log("[{}][2/2] 账号状态查询开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][2/2] ⏭️ 断网预演：已校验状态请求配置，未发起网络请求（{:.2f}秒）".format(
            label, time.monotonic() - stage_started
        ))
    else:
        try:
            response = request_json("GET", STATUS_URL, cookie, timeout)
            identity, left_days = parse_status(response)
            stats["success"] += 1
            label = identity
            log("[账号{}][2/2] ✅ 身份：{}；剩余天数：{}（{:.2f}秒）".format(
                index, identity, left_days, time.monotonic() - stage_started
            ))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            log("[账号{}][2/2] ❌ {}（{:.2f}秒）".format(
                index, safe_business_text(exc), time.monotonic() - stage_started
            ))

    elapsed = time.monotonic() - started
    ok = dry_run or stats["failed"] == 0
    log(
        "[账号{}] 结果={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            index,
            "DRY_RUN" if dry_run else ("SUCCESS" if ok else "FAILED"),
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
        "identity": label,
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
    names = {CATALOG_ID, Path(__file__).name, "candidate.py", "checkin.py", script_path}
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
        log("⚠️ QINGLONG_NOTIFY 值无效，按 auto 处理")
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

    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            log("通知状态：notify.send 已调用")
            return "sent"
    except Exception:
        pass

    for path in python_notifier_paths():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify", str(path))
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

    log("⚠️ 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码")
    return "unavailable"


def print_summary(summary: Dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("GLADOS_DRY_RUN")
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        timeout = parse_timeout()
        accounts = load_accounts()
    except ValueError as exc:
        log("❌ 配置错误：{}".format(exc))
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
        print_summary({
            "status": "configuration-error",
            "mode": "dry-run" if dry_run else "live",
            "accounts": {"total": 0, "success": 0, "failed": 1},
            "tasks": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0},
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        })
        return 2

    log("账号数量：{}".format(len(accounts)))
    results = [run_account(i, cookie, timeout, dry_run) for i, cookie in enumerate(accounts, 1)]
    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    if dry_run:
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
    print("最终状态：{}".format(status.upper()))
    print_summary({
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": {"total": len(results), "success": account_success, "failed": account_failed},
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
    })
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
