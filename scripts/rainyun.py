#!/usr/bin/env python3
# coding: utf-8
# name: 雨云服务器签到
# cron: 28 1 * * *
# 维护目标: 89f2e9b460331a75 / scripts/rainyun.py
# 原维护上游: cloudcranes/some_scripts rainyun.py
# 原维护提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 新参考上游: FalseHappiness/RainyunCheckIn app.py
# 新参考提交: 89a56473f66477f01e87ec4879f88cbd8a1bf435
# Copyright © 2025 FalseHappiness
# 许可证: MIT
"""雨云每日签到。

必填环境变量 ``rainyun_ck`` 每行填写一个 ``用户名#密码``。脚本只在第一个
``#`` 处分隔，因此密码中后续出现的 ``#`` 会完整保留。用户名和密码从雨云官网
个人账号获取，不需要 Cookie 或 API 密钥。

``RAINYUN_DRY_RUN=1`` 启用完全断网预演；``QINGLONG_NOTIFY=0`` 关闭通知。
脚本只使用 Python 标准库，不依赖原仓库、浏览器、DLL 或其他应用程序。

MIT License

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
        _ql_notify_identities = ('89f2e9b460331a75', 'scripts/rainyun.py', 'rainyun.py', 'rainyun')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime


TITLE = "雨云服务器签到"
CATALOG_ID = "89f2e9b460331a75"
SCRIPT_PATH = "scripts/rainyun.py"
BASE = "https://api.v2.rainyun.com"
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 256 * 1024
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}


def env_enabled(name, default="0"):
    """解析通用布尔开关；未知非空值保持旧版的启用语义。"""
    return os.environ.get(name, default).strip().lower() not in FALSE_VALUES | {""}


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    """可安全展示且不含响应正文的业务错误。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向，已拒绝向新地址转发凭据")


class RainYun:
    """雨云 HTTP 客户端，每个账号使用独立 CookieJar。"""

    def __init__(self, user, password):
        self.user = user.lower()
        self.password = password
        self.cookies = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(self, path, payload=None):
        headers = {
            "User-Agent": "Mozilla/5.0 Qinglong-RainYun/1.0",
            "Origin": "https://api.rainyun.com",
            "Referer": "https://api.rainyun.com/",
            "Accept": "application/json",
        }
        for cookie in self.cookies:
            if cookie.name.lower() == "x-csrf-token":
                headers["X-CSRF-Token"] = cookie.value

        body = None
        method = "GET"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"

        request = urllib.request.Request(
            BASE + path, data=body, headers=headers, method=method
        )
        try:
            with self.http.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise TaskError(f"HTTP 状态异常：{response.status}")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise TaskError("接口响应超过安全大小限制")
            result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 错误：{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络连接或请求超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口响应不是有效 JSON") from None

        if not isinstance(result, dict):
            raise TaskError("接口响应结构无效")
        code = result.get("code")
        if isinstance(code, bool) or code not in (200, "200"):
            raise TaskError("接口业务码未确认成功")
        return result.get("data")

    def login(self):
        return self.request(
            "/user/login", {"field": self.user, "password": self.password}
        )

    def signin(self):
        return self.request(
            "/user/reward/tasks", {"task_name": "每日签到", "verifyCode": ""}
        )

    def query(self):
        data = self.request("/user/")
        if not isinstance(data, dict):
            raise TaskError("用户信息结构无效")
        points = data.get("points")
        if (
            isinstance(points, bool)
            or not isinstance(points, (int, float))
            or not math.isfinite(points)
        ):
            raise TaskError("积分字段缺失或格式无效")
        return data

    def logout(self):
        return self.request("/user/logout", {})


def safe_identity(data, password):
    """返回官方非敏感身份；手机号、设备标识和凭据一律不展示。"""
    if not isinstance(data, dict):
        return None
    for key in ("nickname", "username", "display_name", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value).strip()
            if not value or password in value:
                continue
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
                continue
            return value
    return None


def notification_selected():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES or switch == "":
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch not in TRUE_VALUES | {"auto"}:
        log("⚠️ QINGLONG_NOTIFY 值无法识别，按 auto 处理")

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "默认列表"
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    if not selectors:
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空"
    candidates = (CATALOG_ID, SCRIPT_PATH, Path(SCRIPT_PATH).name)
    for selector in selectors:
        if selector == "*" or any(
            fnmatch.fnmatchcase(candidate, selector) for candidate in candidates
        ):
            return True, f"匹配选择器 {selector}"
    return False, "未被 QINGLONG_NOTIFY_SCRIPTS 选中"


def notification_body(summary):
    return (
        f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
        f"成功：{summary['success']}；失败：{summary['failed']}；"
        f"子任务成功：{summary['steps']['success']}；"
        f"子任务失败：{summary['steps']['failed']}"
    )


def python_notifiers():
    modules = []
    try:
        modules.append(importlib.import_module("notify"))
    except Exception:
        pass

    paths = []
    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    seen = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            spec = importlib.util.spec_from_file_location(
                f"qinglong_notify_{len(modules)}", resolved
            )
            if spec is None or spec.loader is None:
                raise ImportError("通知模块缺少加载器")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append(module)
        except Exception:
            log("⚠️ Python 通知模块加载失败（详情已脱敏）")
    return modules


def javascript_notifier_paths():
    paths = []
    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        (Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js"))
    )
    result = []
    seen = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in seen and resolved.is_file():
            result.append(resolved)
            seen.add(resolved)
    return result


def send_notification(summary, dry_run):
    selected, reason = notification_selected()
    if not selected:
        log(f"⏭️ 通知已跳过：{reason}")
        return "disabled"
    if dry_run:
        log("⏭️ 断网预演：已生成脱敏通知摘要，未调用通知渠道")
        return "dry-run-skipped"

    body = notification_body(summary)
    for module in python_notifiers():
        sender = getattr(module, "send", None)
        if not callable(sender):
            continue
        try:
            sender(TITLE, body)
            log("✅ Python 通知发送完成")
            return "sent"
        except Exception:
            log("⚠️ Python 通知发送失败（详情已脱敏）")

    node = shutil.which("node")
    if node:
        wrapper = (
            "const m=require(process.argv[1]);"
            "const f=typeof m==='function'?m:(m.sendNotify||m.send);"
            "if(typeof f!=='function')process.exit(2);"
            "Promise.resolve(f(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(3));"
        )
        for path in javascript_notifier_paths():
            try:
                result = subprocess.run(
                    [node, "-e", wrapper, str(path), TITLE, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("✅ JavaScript 通知发送完成")
                    return "sent"
                log("⚠️ JavaScript 通知发送失败（详情已脱敏）")
            except (OSError, subprocess.SubprocessError):
                log("⚠️ JavaScript 通知执行失败（详情已脱敏）")

    log("⚠️ 通知不可用；业务退出码保持不变")
    return "unavailable"


def account_lines():
    """忽略空行，但不改写密码中的空格和后续分隔符。"""
    return [line for line in os.environ.get("rainyun_ck", "").splitlines() if line.strip()]


def parse_account(line):
    user, delimiter, password = line.partition("#")
    user = user.strip()
    return user, password, bool(delimiter and user and password)


def empty_step_stats():
    return {
        "total": 4,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }


def run_account(index, line, dry_run):
    account_started = time.monotonic()
    stats = empty_step_stats()
    user, password, valid = parse_account(line)
    client = RainYun(user, password) if valid and not dry_run else None
    logged_in = False
    log(f"--- 账号 {index} ---")

    actions = ("登录", "每日签到", "查询积分", "退出登录")
    for number, action in enumerate(actions, 1):
        step_started = time.monotonic()
        prefix = f"账号 {index} 阶段 {number}/4 {action}"
        if not valid:
            state = "failed" if number == 1 else "skipped"
            detail = (
                "凭据格式无效，要求 用户名#密码"
                if number == 1
                else "配置错误，跳过"
            )
        elif dry_run:
            state = "skipped"
            detail = "DRY_RUN_OK：参数与执行计划已验证，未发起网络请求"
        elif number in (2, 3, 4) and not logged_in:
            state, detail = "skipped", "登录未成功，跳过"
        else:
            try:
                operation = (
                    client.login,
                    client.signin,
                    client.query,
                    client.logout,
                )[number - 1]
                data = operation()
                if number == 1:
                    logged_in = True
                state = "success"
                detail = "业务码确认成功"
                if number == 2:
                    detail = "成功签到并领取积分"
                if number in (1, 3):
                    label = safe_identity(data, password)
                    if label:
                        log(f"账号 {index} 官方身份：{label}")
                if number == 3:
                    detail = f"积分查询成功：{data['points']}"
            except TaskError as exc:
                state, detail = "failed", str(exc)
            except Exception:
                state, detail = "failed", "执行异常（详情已脱敏）"

        stats[state] += 1
        icon = {"success": "✅", "failed": "❌", "skipped": "⏭️"}[state]
        elapsed = time.monotonic() - step_started
        log(f"{icon} {prefix}：{detail}；耗时 {elapsed:.2f} 秒")

    ok = valid and stats["failed"] == 0 and (
        dry_run or stats["success"] == stats["total"]
    )
    result = {
        "account": index,
        "status": "dry-run" if ok and dry_run else "success" if ok else "failure",
        "steps": stats,
        "durationSeconds": round(time.monotonic() - account_started, 3),
    }
    log(
        f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}；耗时 {result['durationSeconds']} 秒"
    )
    return result, valid, ok


def main():
    started = time.monotonic()
    dry_run = env_enabled("RAINYUN_DRY_RUN")
    lines = account_lines()
    summary = {
        "task": TITLE,
        "mode": "dry-run" if dry_run else "live",
        "startedAt": stamp(),
        "accounts": len(lines),
        "success": 0,
        "failed": 0,
        "configurationErrors": 0,
        "steps": {
            "total": 0,
            "success": 0,
            "alreadyComplete": 0,
            "skipped": 0,
            "failed": 0,
        },
        "accountResults": [],
    }

    log(f"===== {TITLE} =====")
    log(
        f"开始时间：{summary['startedAt']}；"
        f"模式：{'断网预演' if dry_run else '正式执行'}；账号数：{len(lines)}"
    )
    if not lines:
        summary["configurationErrors"] = 1
        log("❌ 配置错误：缺少 rainyun_ck，请每行填写 用户名#密码")

    for index, line in enumerate(lines, 1):
        result, valid, ok = run_account(index, line, dry_run)
        if not valid:
            summary["configurationErrors"] += 1
        summary["success" if ok else "failed"] += 1
        summary["accountResults"].append(result)
        for key in summary["steps"]:
            summary["steps"][key] += result["steps"][key]

    failed = bool(summary["failed"] or summary["configurationErrors"])
    if summary["configurationErrors"]:
        summary["status"] = "configuration-error"
    elif failed and summary["success"]:
        summary["status"] = "partial-failure"
    elif failed:
        summary["status"] = "failure"
    elif dry_run:
        summary["status"] = "dry-run"
    else:
        summary["status"] = "success"

    summary["notification"] = send_notification(summary, dry_run)
    summary["finishedAt"] = stamp()
    summary["durationSeconds"] = round(time.monotonic() - started, 3)
    log("----------------------------------------")
    log(
        f"任务统计：账号总数 {len(lines)}，成功 {summary['success']}，"
        f"失败 {summary['failed']}；子任务 {summary['steps']}"
    )
    log(
        f"完成时间：{summary['finishedAt']}；总耗时 {summary['durationSeconds']} 秒；"
        f"通知：{summary['notification']}；最终状态：{summary['status']}"
    )
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
