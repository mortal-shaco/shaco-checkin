#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 喵御宅每日签到
# cron: 9 9 * * *
# new Env("喵御宅每日签到")
# 上游：Kou-JunHao/Neko_mfuns_login，mfuns_sign.py
# 来源提交：69d939349956d6b1da6b28b25a5e54a4bd39330d
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2025 SKKK
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
"""喵御宅(MFUNS)每日签到。

NEKO_MFUNS_COOKIE：每个非空行填写一个账号的 Authorization 头值（不是整段 Cookie
请求头）。登录 https://www.mfuns.net 后，打开浏览器开发者工具 → Network，
刷新或发起任意已登录请求，在 Request Headers 中复制 Authorization 字段的值。
不要公开或打印该值。多账号只按换行分隔，不使用 & 或 @。

上游定时建议每天 09:00（0 9 * * *）。正式模式先校验凭证，再执行签到；
code=1 视为签到成功，code=0 视为今日已签到。失败时最多额外重试 1 次。
NEKO_MFUNS_DRY_RUN=1：完全断网预演，只校验参数与流程，不发起任何网络请求。
QINGLONG_NOTIFY 默认 auto（仅名单命中才通知）；1 强制启用，0 关闭。
QINGLONG_NOTIFY_SCRIPTS 支持目录编号、文件名、相对路径与通配符；* 全选，
显式空值全关。通知失败不改变业务退出码。本脚本不发帖、评论或分享。
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
        _ql_notify_identities = ('bacc70efebb57480', 'scripts/mfuns_sign.py', 'mfuns_sign.py', 'mfuns_sign')
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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "喵御宅每日签到"
CATALOG_ID = "bacc70efebb57480"
APPLICATION_KEY = "kou-junhao/neko_mfuns_login::mfuns"
HISTORY_URL = "https://api.mfuns.net/v1/history/get"
SIGN_URL = "https://api.mfuns.net/v1/sign/sign"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
)
MAX_RESPONSE_BYTES = 65536
MAX_RETRY_COUNT = 1
CONNECT_READ_TIMEOUT = 30
DISABLED = {"0", "false", "no", "off"}
ENABLED = {"1", "true", "yes", "on"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(stamp(), message), flush=True)


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ENABLED


def build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": token,
        "User-Agent": USER_AGENT,
        "Origin": "https://www.mfuns.net",
        "Referer": "https://www.mfuns.net",
        "Accept": "application/json, text/plain, */*",
        "sec-fetch-mode": "cors",
    }


def validate_token_format(token: str) -> Optional[str]:
    if not token or not token.strip():
        return "Token 为空"
    token = token.strip()
    if len(token) < 10:
        return "Token 格式异常，长度过短"
    if any(ord(ch) < 32 for ch in token):
        return "Token 含有非法控制字符"
    return None


def load_accounts() -> List[str]:
    raw = os.getenv("NEKO_MFUNS_COOKIE", "")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def http_get_json(url: str, headers: Dict[str, str], timeout: int = CONNECT_READ_TIMEOUT) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read(MAX_RESPONSE_BYTES + 1) if error.fp is not None else b""
    except Exception as exc:
        raise RuntimeError("网络连接失败或超时") from exc
    if status != 200:
        raise RuntimeError("HTTP 状态异常: {}".format(status))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("响应过大")
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("响应不是有效 JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("响应结构无效")
    return data


def extract_identity(data: Any, token: str) -> Optional[str]:
    sources: List[Any] = []
    if isinstance(data, dict):
        sources.append(data)
        nested = data.get("data")
        if isinstance(nested, dict):
            sources.append(nested)
            for key in ("user", "user_info", "profile", "member"):
                if isinstance(nested.get(key), dict):
                    sources.append(nested[key])
        for key in ("user", "user_info", "profile", "member"):
            if isinstance(data.get(key), dict):
                sources.append(data[key])
    secrets = [token]
    if token.lower().startswith("bearer "):
        secrets.append(token[7:].strip())
    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in (
            "nickname",
            "nick_name",
            "username",
            "user_name",
            "displayName",
            "display_name",
            "name",
            "uid",
            "user_id",
            "id",
        ):
            value = source.get(field)
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (str, int)):
                text = str(value).strip()
                if not text:
                    continue
                if any(secret and secret in text for secret in secrets):
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                if field in {"id", "uid", "user_id"} and not re.fullmatch(r"\d{1,18}", text):
                    # 避免把非公开数字标识或长会话片段当 UID。
                    if field != "uid":
                        continue
                return text.replace("\r", " ").replace("\n", " ")
    return None


def test_token_validity(token: str) -> Tuple[bool, str, Optional[str], Optional[Dict[str, Any]]]:
    data = http_get_json(HISTORY_URL, build_headers(token), timeout=10)
    code = data.get("code")
    who = extract_identity(data, token)
    if code == 401:
        return False, "Token 已过期或无效", who, data
    if code == 1:
        return True, "Token 有效性测试通过", who, data
    if "code" not in data:
        # 与上游一致：无 code 但 HTTP 成功时视为有效。
        return True, "Token 有效性测试通过", who, data
    return False, "Token 有效性测试未获业务确认", who, data


def sign_in(token: str, retry_count: int = MAX_RETRY_COUNT) -> Tuple[str, str, Optional[str], int]:
    last_message = "签到失败"
    who: Optional[str] = None
    for attempt in range(retry_count + 1):
        try:
            data = http_get_json(SIGN_URL, build_headers(token), timeout=CONNECT_READ_TIMEOUT)
            who = extract_identity(data, token) or who
            code = data.get("code")
            msg = data.get("msg")
            if not isinstance(msg, str):
                msg = ""
            msg = msg.strip()
            if code == 1:
                return "success", (msg or "签到成功"), who, attempt + 1
            if code == 0:
                return "alreadyComplete", (msg or "今日已签到"), who, attempt + 1
            last_message = "签到失败: {}".format(msg or "未知业务码")
        except RuntimeError as error:
            last_message = str(error)
        except Exception:
            last_message = "网络、超时或响应处理失败"
        if attempt < retry_count:
            log("{} 第{}次签到未确认成功，3秒后重试...".format(ICONS["warning"], attempt + 1))
            time.sleep(3)
            continue
    return "failure", last_message, who, retry_count + 1


def script_selectors() -> List[str]:
    script = Path(__file__).resolve()
    return [
        CATALOG_ID,
        script.name,
        "candidate.py",
        "mfuns_sign.py",
        "output/candidate.py",
        "scripts/mfuns_sign.py",
        script.as_posix(),
    ]


def notification_selected() -> bool:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in DISABLED:
        return False
    if switch in ENABLED:
        return True
    selected = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selected is None:
        return False
    stripped = selected.strip()
    if stripped == "":
        return False
    if stripped == "*":
        return True
    patterns = [part for part in re.split(r"[,;\s]+", stripped) if part]
    choices = script_selectors()
    return any(
        fnmatch.fnmatchcase(choice, pattern)
        for pattern in patterns
        for choice in choices
    )


def discover_notify_paths() -> Tuple[List[Path], List[Path]]:
    dirs: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        dirs.append(Path(custom))
    dirs.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    py_paths = [directory / "notify.py" for directory in dirs]
    js_paths = [directory / "sendNotify.js" for directory in dirs]
    return py_paths, js_paths


def send_via_python(title: str, body: str, paths: List[Path]) -> bool:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            return True
    except Exception:
        pass
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_mfuns_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                return True
        except Exception:
            continue
    return False


def send_via_node(title: str, body: str, paths: List[Path]) -> bool:
    node = None
    for candidate in ("node", "nodejs"):
        from shutil import which

        node = which(candidate)
        if node:
            break
    if not node:
        return False
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    worker = (
        "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));"
        "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body))"
        ".then(r=>process.exit(r===false?1:0)).catch(()=>process.exit(1));"
    )
    for path in paths:
        if not path.is_file():
            continue
        try:
            completed = subprocess.run(
                [node, "-e", worker, str(path.resolve())],
                input=payload,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                return True
        except Exception:
            continue
    return False


def notify(summary: str, dry_run: bool) -> str:
    if not notification_selected():
        log("{} 通知：未启用或未命中通知名单".format(ICONS["skipped"]))
        return "disabled"
    if dry_run:
        log("{} 通知预演：{}".format(ICONS["skipped"], summary))
        return "dry-run"
    py_paths, js_paths = discover_notify_paths()
    try:
        if send_via_python(TITLE, summary, py_paths):
            log("{} 通知已通过 notify.py 发送".format(ICONS["success"]))
            return "sent"
        if send_via_node(TITLE, summary, js_paths):
            log("{} 通知已通过 sendNotify.js 发送".format(ICONS["success"]))
            return "sent"
        log("{} 通知工具不可用；保留业务退出码".format(ICONS["warning"]))
        return "unavailable"
    except Exception:
        log("{} 通知发送失败；保留业务退出码".format(ICONS["warning"]))
        return "failed"


def process_account(index: int, total: int, token: str, dry_run: bool) -> Dict[str, Any]:
    account_started = time.monotonic()
    label = "账号{}".format(index)
    result = {
        "account": index,
        "ok": False,
        "status": "failure",
        "identity": None,
        "message": "",
        "attempts": 0,
        "elapsedSeconds": 0.0,
        "tasks": {"total": 1, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0},
    }
    log("---------- 账号 {}/{} ----------".format(index, total))
    stage1 = time.monotonic()
    log("账号 {} / 阶段 1 参数检查".format(index))
    format_error = validate_token_format(token)
    if format_error:
        log("{} {}".format(ICONS["failure"], format_error))
        result["message"] = format_error
        result["tasks"]["failure"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
        log(
            "账号 {} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 {:.2f}秒".format(
                index, result["elapsedSeconds"]
            )
        )
        return result
    log("{} 参数检查通过；阶段 1 耗时 {:.2f}秒".format(ICONS["success"], time.monotonic() - stage1))

    if dry_run:
        stage2 = time.monotonic()
        log("账号 {} / 阶段 2 凭证预检（预演）".format(index))
        log("{} DRY_RUN_OK：已预演凭证校验，未发送请求".format(ICONS["skipped"]))
        log("阶段 2 耗时 {:.2f}秒".format(time.monotonic() - stage2))
        stage3 = time.monotonic()
        log("账号 {} / 阶段 3 每日签到（预演）".format(index))
        log("{} DRY_RUN_OK：已预演签到，未发送请求、无副作用".format(ICONS["skipped"]))
        log("阶段 3 耗时 {:.2f}秒".format(time.monotonic() - stage3))
        result.update(ok=True, status="skipped", message="DRY_RUN_OK")
        result["tasks"]["skipped"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
        log(
            "账号 {} 统计：总任务 1，成功 0，已完成 0，跳过 1，失败 0，耗时 {:.2f}秒".format(
                index, result["elapsedSeconds"]
            )
        )
        return result

    stage2 = time.monotonic()
    log("账号 {} / 阶段 2 凭证有效性测试".format(index))
    try:
        valid, message, who, _ = test_token_validity(token)
    except Exception:
        valid, message, who = False, "凭证测试网络或响应处理失败", None
    if who:
        label = who
        result["identity"] = who
        log("账号 {} 官方身份：{}".format(index, who))
    if not valid:
        log("{} {}".format(ICONS["failure"], message))
        result["message"] = message
        result["tasks"]["failure"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
        log("阶段 2 耗时 {:.2f}秒".format(time.monotonic() - stage2))
        log(
            "账号 {} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 {:.2f}秒".format(
                index, result["elapsedSeconds"]
            )
        )
        return result
    log("{} {}；阶段 2 耗时 {:.2f}秒".format(ICONS["success"], message, time.monotonic() - stage2))

    stage3 = time.monotonic()
    log("账号 {} / 阶段 3 每日签到（最多重试 {} 次）".format(index, MAX_RETRY_COUNT))
    status, message, who, attempts = sign_in(token, retry_count=MAX_RETRY_COUNT)
    result["attempts"] = attempts
    if who:
        label = who
        result["identity"] = who
        log("账号 {} 官方身份：{}".format(index, who))
    icon = ICONS.get(status, ICONS["failure"])
    log("{} {}（尝试 {} 次）；阶段 3 耗时 {:.2f}秒".format(icon, message, attempts, time.monotonic() - stage3))
    result["message"] = message
    result["status"] = status
    result["ok"] = status in {"success", "alreadyComplete"}
    if status == "success":
        result["tasks"]["success"] = 1
    elif status == "alreadyComplete":
        result["tasks"]["alreadyComplete"] = 1
    else:
        result["tasks"]["failure"] = 1
    result["elapsedSeconds"] = round(time.monotonic() - account_started, 3)
    log(
        "账号 {}（{}）统计：总任务 1，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒".format(
            index,
            label,
            result["tasks"]["success"],
            result["tasks"]["alreadyComplete"],
            result["tasks"]["skipped"],
            result["tasks"]["failure"],
            result["elapsedSeconds"],
        )
    )
    return result


def main() -> int:
    started = time.monotonic()
    dry_run = env_flag("NEKO_MFUNS_DRY_RUN", "0")
    accounts = load_accounts()
    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；模式：{}；账号数：{}".format(
            now_text(),
            "断网预演" if dry_run else "正式运行",
            len(accounts),
        )
    )
    config_error = not accounts
    results: List[Dict[str, Any]] = []
    if config_error:
        log("{} 阶段 1 参数检查：缺少 NEKO_MFUNS_COOKIE；每个非空行填写一个账号 Authorization 值".format(ICONS["failure"]))

    for index, token in enumerate(accounts, 1):
        results.append(process_account(index, len(accounts), token, dry_run))

    success = sum(1 for item in results if item["status"] == "success")
    already = sum(1 for item in results if item["status"] == "alreadyComplete")
    skipped = sum(1 for item in results if item["status"] == "skipped")
    failure = sum(1 for item in results if item["status"] == "failure")
    passed = sum(1 for item in results if item["ok"])
    failed_accounts = len(results) - passed
    exit_code = 1 if config_error or failed_accounts > 0 or not accounts else 0
    if config_error:
        final_status = "configuration-error"
    elif dry_run and exit_code == 0:
        final_status = "dry-run"
    elif exit_code == 0:
        final_status = "success"
    elif passed > 0 and failed_accounts > 0:
        final_status = "partial-failure"
    else:
        final_status = "failure"

    body = (
        "账号总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}；状态 {}".format(
            len(accounts), success, already, skipped, failure, final_status
        )
    )
    if config_error:
        body += "。配置错误：缺少 NEKO_MFUNS_COOKIE"
    if dry_run:
        body += "。断网预演，未进行真实签到"
    notification = notify(body, dry_run)

    log("----------------------------------------")
    log("任务统计：" + body)
    log(
        "子任务统计：成功 {}，已完成 {}，跳过 {}，失败 {}；通知状态：{}".format(
            success, already, skipped, failure, notification
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；最终状态：{}；退出码 {}".format(
            now_text(), time.monotonic() - started, final_status, exit_code
        )
    )
    summary = {
        "applicationKey": APPLICATION_KEY,
        "task": TITLE,
        "mode": "dry-run" if dry_run else "live",
        "status": final_status,
        "accounts": len(accounts),
        "success": success,
        "alreadyComplete": already,
        "skipped": skipped,
        "failure": failure,
        "passedAccounts": passed,
        "failedAccounts": failed_accounts,
        "configurationError": config_error,
        "dryRun": dry_run,
        "notification": notification,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "exitCode": exit_code,
        "results": [
            {
                "account": item["account"],
                "ok": item["ok"],
                "status": item["status"],
                "identity": item["identity"],
                "attempts": item["attempts"],
                "elapsedSeconds": item["elapsedSeconds"],
                "tasks": item["tasks"],
            }
            for item in results
        ],
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
