#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NodeSeek签到
# cron: 0 0 * * *
# new Env("NodeSeek签到")
# 上游：CN-Grace/QinglongScripts，Nodeseek.py
# 来源提交：a40a2b080e0160bd8e0b0b807081115537b87153
# SPDX-License-Identifier: MIT
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""NS_COOKIE：登录 NodeSeek 后，从浏览器开发者工具的本站请求中复制
完整 Cookie 请求头值（不含 Cookie: 前缀），每个账号一行，勿公开。
NS_RANDOM=true 随机奖励，false 固定奖励；NS_IMPERSONATE=chrome110。
默认签到前随机等待 0～300 秒。NS_DRY_RUN=1 完全断网预演，不等待。
运行依赖 curl_cffi（青龙依赖管理中从公开 Python 包注册表安装）。
通知可用青龙 notify.py；QINGLONG_NOTIFY=0 关闭通知。
"""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import time
from datetime import datetime, timezone, timedelta

OFF = {"0", "false", "no", "off"}
ON = {"1", "true", "yes", "on"}


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def log(stage, message, elapsed=None):
    suffix = "" if elapsed is None else f"；耗时 {elapsed:.2f}s"
    print(f"[{now():%H:%M:%S}] {stage} {message}{suffix}", flush=True)


def identity(data, cookie):
    # 仅采用接口明确返回的非凭据身份，不输出任意业务消息。
    sources = [data]
    if isinstance(data.get("data"), dict):
        sources.append(data["data"])
    for source in list(sources):
        if isinstance(source.get("user"), dict):
            sources.append(source["user"])
    secrets = [cookie] + [v.strip() for p in cookie.split(";") if "=" in p for v in [p.split("=", 1)[1]] if v.strip()]
    for source in sources:
        for field in ("nickname", "username", "displayName", "uid"):
            value = source.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                if any(s in value for s in secrets) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
                    continue
                return value.replace("\r", " ").replace("\n", " ")
    return None


def nodeseek_checkin(cookie, ns_random, impersonate):
    try:
        from curl_cffi import requests
    except ImportError:
        return False, "failure", "缺少公开依赖 curl_cffi，请通过青龙依赖管理安装", None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "origin": "https://www.nodeseek.com",
        "referer": "https://www.nodeseek.com/board",
        "Content-Type": "application/json", "Cookie": cookie,
    }
    try:
        response = requests.post(
            f"https://www.nodeseek.com/api/attendance?random={ns_random}",
            headers=headers, json={}, timeout=25, impersonate=impersonate,
            allow_redirects=False,
        )
        if response.status_code != 200:
            return False, "failure", f"HTTP {response.status_code}，签到未确认", None
        data = response.json()
        if not isinstance(data, dict):
            return False, "failure", "接口响应结构无效", None
        who = identity(data, cookie)
        message = data.get("message")
        if data.get("status") == 404:
            return False, "failure", "接口提示凭据失效", who
        if data.get("success") is True:
            return True, "success", "签到成功（接口 success=true）", who
        if isinstance(message, str) and "已完成签到" in message:
            return True, "already", "今日已完成签到", who
        return False, "failure", "接口未明确确认签到成功", who
    except Exception:
        return False, "failure", "请求、指纹配置或响应解析异常；未确认签到成功", None


def notify_summary(body, dry_run):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in OFF:
        log("阶段 3 通知", "⏭️ 已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry_run:
        log("阶段 3 通知", "⏭️ 断网预演：通知摘要已生成，跳过外部发送")
        print(body)
        return "dry-run"
    candidates = [None]
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        candidates.append(Path(directory) / "notify.py")
    candidates.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in candidates:
        try:
            if path is None:
                module = importlib.import_module("notify")
            else:
                if not path.is_file():
                    continue
                spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if not callable(sender):
                continue
        except Exception:
            continue
        try:
            sender("NodeSeek签到", body)
            log("阶段 3 通知", "✅ 通知助手调用完成")
            return "sent"
        except Exception:
            log("阶段 3 通知", "⚠️ 通知发送失败，保留业务退出码")
            return "failed"
    log("阶段 3 通知", "⚠️ 青龙 notify.py 不可用，保留业务退出码")
    return "unavailable"


def main():
    started = time.monotonic()
    dry_run = os.getenv("NS_DRY_RUN", "0").strip().lower() in ON
    cookies = [line.strip() for line in os.getenv("NS_COOKIE", "").splitlines() if line.strip()]
    reward = os.getenv("NS_RANDOM", "true").strip().lower()
    reward = reward if reward in {"true", "false"} else "true"
    impersonate = os.getenv("NS_IMPERSONATE", "chrome110").strip() or "chrome110"
    print("══════════ NodeSeek签到 ══════════")
    log("阶段 1 配置", f"开始时间 {now():%Y-%m-%d %H:%M:%S %z}；模式 {'断网预演' if dry_run else '正式运行'}；账号数 {len(cookies)}；随机奖励 {reward}")
    results = []
    if not cookies:
        log("阶段 1 配置", "❌ 未配置必填 NS_COOKIE；每个账号一行")
    for index, cookie in enumerate(cookies, 1):
        account_started = time.monotonic()
        log(f"账号 {index} 阶段 1", "凭据已读取（隐藏）")
        if dry_run:
            log(f"账号 {index} 阶段 2", "⏭️ 跳过随机等待、HTTP 请求和签到副作用", 0)
            ok, status, message, who = True, "skipped", "DRY_RUN_OK：配置预演通过，未验证真实签到", None
        else:
            delay = random.randint(0, 300)
            log(f"账号 {index} 阶段 2", f"签到前随机延迟 {delay}s")
            time.sleep(delay)
            request_started = time.monotonic()
            ok, status, message, who = nodeseek_checkin(cookie, reward, impersonate)
            log(f"账号 {index} 阶段 2", f"{'✅' if ok else '❌'} {message}", time.monotonic() - request_started)
        if who is not None:
            log(f"账号 {index} 身份", who)
        if dry_run:
            log(f"账号 {index} 预演", message)
        counts = {"success": int(status == "success"), "already": int(status == "already"), "skipped": int(status == "skipped"), "failure": int(not ok)}
        elapsed = time.monotonic() - account_started
        log(f"账号 {index} 统计", f"总任务 1；成功 {counts['success']}；已完成 {counts['already']}；跳过 {counts['skipped']}；失败 {counts['failure']}", elapsed)
        results.append({"account": index, "ok": ok, "status": status, "tasks": counts, "elapsedSeconds": round(elapsed, 3)})
    passed = sum(r["ok"] for r in results)
    failed = len(results) - passed
    exit_code = 0 if cookies and failed == 0 else 1
    status = "configuration-error" if not cookies else "dry-run" if dry_run else "success" if failed == 0 else "partial-failure" if passed else "failure"
    totals = {key: sum(r["tasks"][key] for r in results) for key in ("success", "already", "skipped", "failure")}
    body = f"状态：{status}；账号总数：{len(cookies)}；成功数：{passed}；失败数：{failed}。子任务：成功 {totals['success']}，已完成 {totals['already']}，跳过 {totals['skipped']}，失败 {totals['failure']}。"
    if not cookies:
        body += " 配置错误：缺少 NS_COOKIE。"
    if dry_run:
        body += " 断网预演，未进行真实签到。"
    notification = notify_summary(body, dry_run)
    print("────────────────────────────────")
    log("最终统计", body, time.monotonic() - started)
    log("任务结束", f"完成时间 {now():%Y-%m-%d %H:%M:%S %z}；通知状态 {notification}；最终状态 {status}；退出码 {exit_code}")
    print("TASK_SUMMARY=" + json.dumps({"task": "NodeSeek签到", "mode": "dry-run" if dry_run else "live", "status": status, "accounts": len(cookies), "success": passed, "failure": failed, "tasks": totals, "results": results, "notification": notification, "elapsedSeconds": round(time.monotonic() - started, 3), "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
