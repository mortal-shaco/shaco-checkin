# -*- coding: utf-8 -*-
# name: CSDN签到与可选抽奖
# cron: 30 10 * * *
# Upstream: OreosLab/checkinpanel, ck_csdn.py
# Commit: 911402e4b2e559ffd62c4949a971ddd6834edd7d
# SPDX-License-Identifier: MIT
# 原始任务标识：new Env('CSDN签到与可选抽奖');
"""CSDN 每日签到；CSDN_DRAW=1 显式开启抽奖。

CSDN_COOKIE：浏览器登录 https://www.csdn.net 后，在开发者工具的网络面板
复制发往 me.csdn.net 的请求 Cookie 头值。每个非空行一个账号，保留完整
Cookie，不含 Cookie: 前缀；不得使用 & 或 @ 分隔账号。
CSDN_DRY_RUN=1 完全离线预演，不校验凭据有效性，不发送联网通知。

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

import importlib
import importlib.util
import json
import os
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path


TITLE = "CSDN签到"
FALSE_VALUES = {"0", "false", "no", "off"}


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def switch(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    if value not in FALSE_VALUES | {"1", "true", "yes", "on"}:
        raise ValueError("开关格式错误")
    return value not in FALSE_VALUES


def parse_cookie(line):
    pairs = []
    if any(ord(char) < 32 or ord(char) > 126 for char in line):
        raise ValueError("Cookie 含不合法字符")
    for part in line.split(";"):
        part = part.strip()
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z0-9_\-]+", key) or not value:
            raise ValueError("Cookie 格式错误")
        pairs.append(f"{key}={value}")
    if not pairs:
        raise ValueError("Cookie 为空")
    return "; ".join(pairs)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("接口重定向，已阻止凭据转发")


def request(action, cookie):
    endpoint = {"sign": "signIn", "draw": "goodluck"}[action]
    req = urllib.request.Request(
        "https://me.csdn.net/api/LuckyDraw_v2/" + endpoint,
        headers={"User-Agent": "Mozilla/5.0", "Cookie": cookie,
                 "Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态异常")
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError("响应超出限制")
    payload = json.loads(body)
    if not isinstance(payload, dict) or payload.get("code") != 200:
        raise ValueError("业务码未确认成功")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("业务响应结构异常")
    return data


def business_result(action, data):
    # 上游以 code=200 为成功码；要求其任务结果字段同时完整。
    msg = data.get("msg")
    msg = msg.strip() if isinstance(msg, str) else ""
    if any(word in msg for word in ("失败", "错误", "未登录", "过期", "不足", "无机会", "没有机会")):
        raise ValueError("业务结果未确认成功")
    if action == "draw":
        prize = data.get("prize_title")
        if isinstance(prize, str) and prize.strip():
            return "success", "抽奖完成（奖品字段已确认）"
        if msg and any(word in msg for word in ("成功", "谢谢参与", "未中奖", "再接再厉")):
            return "success", "抽奖完成（结果字段已确认）"
    else:
        if "签到" in msg and any(word in msg for word in ("已", "重复")):
            return "already", "今日已签到"
        if "签到" in msg and "成功" in msg:
            return "success", "签到成功"
    raise ValueError("无法确认业务结果，需核对接口契约")


def show_identity(data, cookie):
    for key in ("nickname", "userName", "username", "displayName", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 只输出官方非敏感身份，抑制手机号和回显凭据。
            if (value and len(value) <= 128 and not any(ord(c) < 32 for c in value)
                    and not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value)
                    ):
                log(f"官方账号身份：{value}")
                return


def notify(body, dry):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in FALSE_VALUES:
        log("⏭️ 通知：QINGLONG_NOTIFY 已关闭")
        return "disabled"
    if dry:
        log("⏭️ 通知：离线预演，通知摘要已生成，联网投递跳过")
        return "dry-run-offline"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            folder = os.environ.get("QINGLONG_NOTIFY_DIR")
            if folder:
                paths.append(Path(folder) / "notify.py")
            paths += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise ImportError("通知组件不可用")
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        log("✅ 通知：摘要已交给青龙通知组件")
        return "delivered"
    except Exception:
        log("⚠️ 通知：组件不可用或投递失败，保留业务退出码")
        return "unavailable-or-failed"


def main():
    started = time.monotonic()
    dry = os.environ.get("CSDN_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    lines = [line.strip() for line in os.environ.get("CSDN_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'离线预演' if dry else '正式执行'}；账号数：{len(lines)}")
    totals = dict(success=0, already=0, skipped=0, failed=0)
    passed = failed = 0
    config_error = False
    try:
        draw = switch("CSDN_DRAW")
        switch("CSDN_DRY_RUN")
        if not lines:
            raise ValueError("请设置 CSDN_COOKIE，每行一个账号")
    except ValueError:
        log("❌ 配置错误：凭据缺失或开关格式错误，请核对契约")
        config_error = True
    if not config_error:
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            stats = dict(success=0, already=0, skipped=0, failed=0)
            cookie = None
            log(f"账号 {index}，阶段 1/3：参数检查")
            try:
                cookie = parse_cookie(line)
                log("✅ 参数格式检查通过（未验证凭据有效性）；阶段耗时：0.00秒")
            except ValueError:
                log("❌ 参数格式错误，当前账号任务无法执行；阶段耗时：0.00秒")
            for stage, action, label in ((2, "sign", "签到"), (3, "draw", "抽奖")):
                step_start = time.monotonic()
                log(f"账号 {index}，阶段 {stage}/3：{label}")
                try:
                    if action == "draw" and not draw:
                        status, detail = "skipped", "抽奖未开启；CSDN_DRAW=1 可开启"
                    elif cookie is None:
                        status, detail = "failed", "凭据格式错误，未发送请求"
                    elif dry:
                        status, detail = "skipped", "DRY_RUN_OK：请求已模拟，未验证真实业务"
                    else:
                        data = request(action, cookie)
                        show_identity(data, cookie)
                        status, detail = business_result(action, data)
                except Exception:
                    status, detail = "failed", "请求或业务校验失败；未输出原始响应，未自动重试"
                stats[status] += 1
                icon = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failed": "❌"}[status]
                log(f"{icon} {detail}；阶段耗时：{time.monotonic() - step_start:.2f}秒")
            for key in totals:
                totals[key] += stats[key]
            bad = stats["failed"] > 0
            failed += int(bad)
            passed += int(not bad)
            log(f"账号 {index} 统计：总任务 2，成功 {stats['success']}，已完成 {stats['already']}，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {time.monotonic() - account_start:.2f}秒")
    status = ("configuration-error" if config_error else "partial-failure" if failed and passed
              else "failure" if failed else "dry-run" if dry else "success")
    exit_code = 1 if config_error or failed else 0
    body = f"状态：{status}；账号总数：{len(lines)}；成功数：{passed if not dry else 0}；失败数：{failed}；预演通过数：{passed if dry else 0}；配置错误：{int(config_error)}。子任务：{json.dumps(totals, ensure_ascii=False)}"
    log("----------------------------------------")
    log(body)
    notification = notify(body, dry)
    log(f"总耗时：{time.monotonic() - started:.2f}秒；完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}；通知状态：{notification}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live",
          "status": status, "accounts": len(lines), "success": passed if not dry else 0,
          "dryRunPassed": passed if dry else 0, "failed": failed,
          "configurationError": config_error, "tasks": totals,
          "notification": notification, "exitCode": exit_code}, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
