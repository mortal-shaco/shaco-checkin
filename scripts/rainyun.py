#!/usr/bin/env python3
# coding: utf-8
# name: 雨云服务器签到
# cron: 23 1 * * *
# 上游: cloudcranes/some_scripts rainyun.py
# 提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 许可证: MIT（根据任务提供的有效许可证；上游文件没有版权声明）
"""雨云每日签到。rainyun_ck 每行 用户名#密码，密码中的 # 会完整保留。
用户名和密码从雨云官网个人账号获取；不需要 Cookie 或 API 密钥。
RAINYUN_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。

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

import http.cookiejar
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from datetime import datetime


TITLE = "雨云服务器签到"
BASE = "https://api.v2.rainyun.com"
FALSE_VALUES = {"0", "false", "no", "off"}


def enabled(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in FALSE_VALUES | {""}


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向，已拒绝转发凭据")


class RainYun:
    def __init__(self, user, password):
        self.user = user.lower()
        self.password = password
        self.cookies = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, path, payload=None):
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://api.rainyun.com",
                   "Referer": "https://api.rainyun.com", "Accept": "application/json"}
        for cookie in self.cookies:
            if cookie.name == "X-CSRF-Token":
                headers["X-CSRF-Token"] = cookie.value
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=body, headers=headers,
                                     method="GET" if payload is None else "POST")
        try:
            with self.http.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError("HTTP 状态非 200")
                raw = response.read(262145)
            if len(raw) > 262144:
                raise TaskError("响应过大")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 错误 {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络或超时错误") from None
        except (ValueError, UnicodeError):
            raise TaskError("响应不是有效 JSON") from None
        if not isinstance(result, dict) or type(result.get("code")) not in (int, str) or result["code"] not in (200, "200"):
            raise TaskError("接口业务码未确认成功")
        return result.get("data")

    def login(self):
        return self.request("/user/login", {"field": self.user, "password": self.password})

    def signin(self):
        return self.request("/user/reward/tasks", {"task_name": "每日签到", "verifyCode": ""})

    def query(self):
        data = self.request("/user/")
        if not isinstance(data, dict):
            raise TaskError("用户信息结构无效")
        points = data.get("points")
        if isinstance(points, bool) or not isinstance(points, (int, float)) or not math.isfinite(points):
            raise TaskError("积分字段缺失或格式无效")
        return data

    def logout(self):
        return self.request("/user/logout", {})


def identity(data, password):
    if not isinstance(data, dict):
        return None
    for key in ("nickname", "username", "display_name", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            if value and password not in value and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
                return value
    return None


def notify(summary, dry):
    if not enabled("QINGLONG_NOTIFY", "1"):
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry:
        log("⏭️ 断网预演：通知摘要已生成，跳过可能联网的通知发送")
        return "dry-run-skipped"
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['success']}；失败：{summary['failed']}；"
            f"子任务成功：{summary['steps']['success']}；子任务失败：{summary['steps']['failed']}")
    modules = []
    try:
        modules.append(importlib.import_module("notify"))
    except Exception:
        pass
    paths = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in paths:
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                modules.append(module)
            except Exception:
                log("⚠️ 通知模块加载失败（详情已脱敏）")
    for module in modules:
        try:
            module.send(TITLE, body)
            log("✅ 通知发送完成")
            return "sent"
        except Exception:
            log("⚠️ 通知发送失败（详情已脱敏）")
    log("⚠️ 通知不可用；保留业务退出码")
    return "unavailable"


def main():
    started = time.monotonic()
    dry = enabled("RAINYUN_DRY_RUN")
    lines = [line for line in os.environ.get("rainyun_ck", "").splitlines() if line.strip()]
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "startedAt": stamp(),
               "accounts": len(lines), "success": 0, "failed": 0,
               "configurationErrors": 0, "steps": {"total": 0, "success": 0,
               "alreadyComplete": 0, "skipped": 0, "failed": 0}, "accountResults": []}
    log(f"===== {TITLE} =====")
    log(f"开始时间：{summary['startedAt']}；模式：{'断网预演' if dry else '正式执行'}；账号数：{len(lines)}")
    if not lines:
        summary["configurationErrors"] = 1
        log("❌ 配置错误：缺少 rainyun_ck，请每行填写 用户名#密码")
    for index, line in enumerate(lines, 1):
        begin = time.monotonic()
        stats = {"total": 4, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        user, delimiter, password = line.partition("#")
        valid = bool(delimiter and user.strip() and password)
        client = RainYun(user.strip(), password) if valid and not dry else None
        logged_in = False
        log(f"--- 账号 {index} ---")
        if not valid:
            summary["configurationErrors"] += 1
        for number, action in enumerate(("登录", "每日签到", "查询积分", "退出登录"), 1):
            step_start = time.monotonic()
            prefix = f"账号 {index} 阶段 {number}/4 {action}"
            if not valid:
                state = "failed" if number == 1 else "skipped"
                detail = "凭据格式无效，要求 用户名#密码" if number == 1 else "配置错误，跳过"
            elif dry:
                state, detail = "skipped", "DRY_RUN_OK 已验证参数和执行计划，未发起请求"
            elif number in (2, 3, 4) and not logged_in:
                state, detail = "skipped", "登录未成功，跳过"
            else:
                try:
                    data = (client.login, client.signin, client.query, client.logout)[number - 1]()
                    if number == 1:
                        logged_in = True
                    state, detail = "success", ("成功签到并领取积分" if number == 2 else "业务码确认成功")
                    if number in (1, 3):
                        label = identity(data, password)
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
            log(f"{icon} {prefix}：{detail}；耗时 {time.monotonic() - step_start:.2f} 秒")
        ok = valid and stats["failed"] == 0 and (dry or stats["success"] == 4)
        summary["success" if ok else "failed"] += 1
        result = {"account": index, "status": "dry-run" if ok and dry else "success" if ok else "failure",
                  "steps": stats, "durationSeconds": round(time.monotonic() - begin, 3)}
        summary["accountResults"].append(result)
        for key in stats:
            summary["steps"][key] += stats[key]
        log(f"账号 {index} 统计：总任务 4，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {result['durationSeconds']} 秒")
    failed = bool(summary["failed"] or summary["configurationErrors"])
    summary["status"] = ("configuration-error" if summary["configurationErrors"] else
                         "partial-failure" if failed and summary["success"] else
                         "failure" if failed else "dry-run" if dry else "success")
    summary["notification"] = notify(summary, dry)
    summary["finishedAt"] = stamp()
    summary["durationSeconds"] = round(time.monotonic() - started, 3)
    log("----------------------------------------")
    log(f"任务统计：账号总数 {len(lines)}，成功 {summary['success']}，失败 {summary['failed']}；子任务 {summary['steps']}")
    log(f"完成时间：{summary['finishedAt']}；总耗时 {summary['durationSeconds']} 秒；通知：{summary['notification']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
