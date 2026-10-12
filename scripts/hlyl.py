#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 活力伊利
# cron: 0 8 * * *
# -------------------
# @Author: cloudcranes
# @Time: 2024/06/03 16:54
# const $ = new Env("活力伊利")
# 来源: cloudcranes/some_scripts, hlyl.py
# 原提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# SPDX-License-Identifier: MIT
# Copyright (c) cloudcranes
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
"""活力伊利每日任务（Python 3，仅标准库）。

在本人授权设备登录活力伊利微信小程序，查看发往
https://msmarket.msx.digitalyili.com 的请求头 access-token。
hlylck 每个非空行一个账号，格式 access-token 或 access-token#备注。
仅首个 # 分隔字段；备注保留后续 #，不用于请求、不打印。不可用 & 或 @ 分隔账号。
HLYL_DRY_RUN=1 完全断网预演，使用占位凭据即可，不代表真实业务成功。
默认仅查询、签到、查询积分；HLYL_LOTTERY_ATTEMPTS=1..10 显式开启抽奖，
可能消耗活动次数或积分。HLYL_LOTTERY_ACTIVITY_ID 默认使用上游活动编号，
活动可能已结束，须从本人小程序该活动请求核对，不自动寻找新活动。
上游未声明计划；推荐每天北京时间 08:00，面板时区须自行核对。
QINGLONG_NOTIFY=0 关闭通知；通知失败不改变业务退出码。
断网预演也尝试 Python 通知，但封锁套接字，远程投递不可用时仅记录状态。
"""

import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = "https://msmarket.msx.digitalyili.com"
FALSE = {"0", "false", "no", "off"}
TRUE = {"1", "true", "yes", "on"}


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，已阻止凭据转发")


class Client:
    def __init__(self, token, dry):
        self.token, self.dry = token, dry
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, method="GET"):
        if self.dry:
            raise TaskError("断网预演禁止业务请求")
        headers = {
            "Referer": "https://servicewechat.com/wx06af0ef532292cd3/459/page-frame.html",
            "Content-Type": "application/json",
            "access-token": self.token,
        }
        req = urllib.request.Request(HOST + path, headers=headers, method=method,
                                     data=b"{}" if method == "POST" else None)
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise TaskError("接口响应过大")
                value = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 状态异常：{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络连接失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口未返回有效 JSON") from None
        if not isinstance(value, dict):
            raise TaskError("接口响应结构异常")
        return value

    def data(self, path):
        value = self.request(path)
        if value.get("status") is not True or "data" not in value:
            raise TaskError("接口未确认业务成功；请核对登录凭据和活动状态")
        return value["data"]


def public_identity(data, token):
    if not isinstance(data, dict):
        return None
    for key in ("nickname", "nickName", "displayName", "username", "userName", "publicUid", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            # username 也可能是手机号；不得把手机号、会话或控制字符带入日志。
            phone_like = key not in ("publicUid", "uid") and re.search(r"\d{11}", text)
            if text and len(text) <= 120 and token not in text and not phone_like and not any(ord(c) < 32 for c in text):
                return text
    return None


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def progress(data):
    if not isinstance(data, dict) or not isinstance(data.get("signed"), bool):
        raise TaskError("签到状态字段缺失或格式异常")
    pieces = []
    for key, label in (("signedDays", "已签天数"), ("taskDays", "周任务天数"), ("monthSignDays", "月签天数")):
        if numeric(data.get(key)):
            pieces.append(f"{label}：{data[key]}")
    if pieces:
        log("；".join(pieces))
    return data["signed"]


def run_account(index, line, dry, attempts, activity):
    start = time.monotonic()
    stats = {"success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    token = line.partition("#")[0].strip()
    valid = bool(token) and not any(c.isspace() or ord(c) < 32 for c in token) and "&" not in token
    client = Client(token, dry)
    signed = None
    log(f"账号 {index} 开始")

    def stage(number, title, action):
        began = time.monotonic()
        log(f"账号 {index} 阶段 {number}/5：{title}")
        try:
            if not valid:
                raise TaskError("账号参数格式错误，请按每行一个 Token 或 Token#备注填写")
            if dry:
                result = "skipped"
                log("⏭️ 断网预演：参数已校验，未发送请求、未改变账号状态")
            else:
                result = action() or "success"
                log({"success": "✅ 阶段成功", "alreadyComplete": "☑️ 已完成", "skipped": "⏭️ 已跳过"}[result])
            stats[result] += 1
        except TaskError as exc:
            stats["failed"] += 1
            log(f"❌ {exc}")
        except Exception:
            stats["failed"] += 1
            log("❌ 阶段处理异常（未输出异常内容，以保护凭据）")
        log(f"账号 {index} 阶段 {number} 耗时 {time.monotonic() - began:.2f} 秒")

    def info():
        data = client.data("/gateway/api/auth/account/user/info")
        if not isinstance(data, dict):
            raise TaskError("账号信息结构异常")
        identity = public_identity(data, token)
        log(f"账号身份：{identity}" if identity else "账号信息查询成功；无可安全展示的公开身份")

    def status():
        nonlocal signed
        signed = progress(client.data("/gateway/api/member/sign/status"))
        log("今天已经签到" if signed else "今天未签到")

    def sign():
        if signed is None:
            raise TaskError("签到状态未确认，未执行签到")
        if signed:
            return "alreadyComplete"
        value = client.request("/gateway/api/member/daily/sign", "POST")
        # 上游签到接口 error 使用字符串 null；兼容真正的 JSON null。
        if value.get("status") is False or not (value.get("status") is True or ("error" in value and value["error"] in (None, "null"))):
            raise TaskError("签到接口未确认业务成功")
        if not progress(client.data("/gateway/api/member/sign/status")):
            raise TaskError("签到后复查仍未签到")
        log("签到成功（已复查签到状态）")
        data = value.get("data")
        reward = data.get("dailySign") if isinstance(data, dict) else None
        rewards = reward if isinstance(reward, list) else [reward]
        for item in rewards:
            if isinstance(item, dict):
                for key, label in (("bonusPoint", "获得积分"), ("bonusGrowth", "成长积分")):
                    if numeric(item.get(key)):
                        log(f"{label}：{item[key]}")

    def lottery():
        if not attempts:
            log("抽奖默认关闭；需显式设置 HLYL_LOTTERY_ATTEMPTS")
            return "skipped"
        for turn in range(attempts):
            data = client.data("/gateway/api/upgrade/lottery/luckDraw?activityId=" + activity)
            if not isinstance(data, dict) or not isinstance(data.get("name"), str) or not data["name"].strip():
                raise TaskError("抽奖响应缺少奖品字段，停止后续抽奖")
            # 仅展示已验证的奖品名称，拒绝潜在凭据及手机号。
            prize = data["name"]
            if token in prize or re.search(r"\d{11}", prize) or len(prize) > 120 or any(ord(c) < 32 for c in prize):
                log(f"抽奖 {turn + 1}/{attempts} 成功；奖品名称因敏感信息规则未显示")
            else:
                log(f"抽奖 {turn + 1}/{attempts} 成功，获得：{prize}")

    def points():
        data = client.data("/gateway/api/member/point")
        if numeric(data):
            log(f"积分：{data}")
            return
        if isinstance(data, dict):
            for key in ("point", "points", "totalPoint", "availablePoint", "balance"):
                if numeric(data.get(key)):
                    log(f"积分：{data[key]}")
                    return
        raise TaskError("积分响应缺少可确认的数值字段")

    for number, title, action in ((1, "查询账号信息", info), (2, "查询签到进度", status),
                                  (3, "每日签到及复查", sign), (4, "活动抽奖", lottery), (5, "查询积分", points)):
        stage(number, title, action)
    elapsed = round(time.monotonic() - start, 2)
    log(f"账号 {index} 统计：总任务 5，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {elapsed} 秒")
    return {"account": index, "ok": not stats["failed"], "stages": stats, "seconds": elapsed}


def notification(title, body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in FALSE:
        return "已按 QINGLONG_NOTIFY 关闭"
    # 隔离通知输出，防止通知组件打印配置、密钥或响应；设置总体超时。
    worker = r'''
import contextlib, importlib.util, io, json, os, pathlib, socket, sys
title, body, dry = json.loads(sys.stdin.read())
if dry:
    def deny(*args, **kwargs):
        raise OSError("dry-run forbids networking")
    socket.socket = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    socket.gethostbyname = deny
    socket.gethostbyname_ex = deny
paths = []
if os.getenv("QINGLONG_NOTIFY_DIR"):
    paths.append(pathlib.Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
paths.extend([pathlib.Path("/ql/data/scripts/notify.py"), pathlib.Path("/ql/scripts/notify.py")])
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        module = None
        try:
            import notify
            module = notify
        except ImportError:
            pass
        if module is None:
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, "send", None)):
            sys.exit(3)
        module.send(title, body)
except BaseException as exc:
    if isinstance(exc, SystemExit):
        raise
    sys.exit(2)
'''
    try:
        result = subprocess.run([sys.executable, "-c", worker], input=json.dumps([title, body, dry]),
                                text=True, capture_output=True, timeout=20)
        if result.returncode == 0:
            return "Python 通知函数已调用（不代表远端确认送达）"
        if dry:
            return "断网预演：通知不可用或远程投递被禁止"
        paths = []
        if os.getenv("QINGLONG_NOTIFY_DIR"):
            paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "sendNotify.js")
        paths.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
        for path in paths:
            if path.is_file():
                js = "const fs=require('fs');const [p,t,b]=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve(require(p).sendNotify(t,b)).catch(()=>process.exit(2));"
                r = subprocess.run(["node", "-e", js], input=json.dumps([str(path.resolve()), title, body]),
                                   text=True, capture_output=True, timeout=20)
                if r.returncode == 0:
                    return "JavaScript 通知函数已调用（不代表远端确认送达）"
        return "通知不可用或失败；业务退出码保持不变"
    except Exception:
        return "通知失败或超时；业务退出码保持不变"


def main():
    started = time.monotonic()
    dry = os.getenv("HLYL_DRY_RUN", "0").strip().lower() in TRUE
    lines = [line.strip() for line in os.getenv("hlylck", "").splitlines() if line.strip()]
    log("========== 活力伊利 ==========")
    log(f"开始时间：{datetime.datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}")
    log(f"运行模式：{'断网预演' if dry else '正式运行'}；账号总数：{len(lines)}")
    results = []
    configuration_error = False
    try:
        attempts = int(os.getenv("HLYL_LOTTERY_ATTEMPTS", "0"))
        if not 0 <= attempts <= 10:
            raise ValueError
        activity = os.getenv("HLYL_LOTTERY_ACTIVITY_ID", "1796131190130262018").strip()
        if not re.fullmatch(r"[0-9]{1,30}", activity):
            raise ValueError
        if not lines:
            raise ValueError
    except ValueError:
        configuration_error = True
        log("❌ 配置错误：hlylck 不能为空；抽奖次数须为 0..10；活动编号须为数字")
    if not configuration_error:
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, dry, attempts, activity))
    good = sum(r["ok"] for r in results)
    bad = len(lines) - good
    exit_code = 1 if configuration_error or bad else 0
    state = "configuration-error" if configuration_error else ("partial-failure" if bad and good else "failure" if bad else "dry-run" if dry else "success")
    totals = {key: sum(r["stages"][key] for r in results) for key in ("success", "alreadyComplete", "skipped", "failed")}
    body = f"模式：{'断网预演（非真实业务成功）' if dry else '正式运行'}；账号总数 {len(lines)}，{'预演通过' if dry else '成功'} {good}，失败 {bad}；状态 {state}；子任务统计 {json.dumps(totals, ensure_ascii=False)}"
    log("----------------------------------------")
    log(body)
    delivery = notification("活力伊利", body, dry)
    log(f"通知状态：{delivery}")
    elapsed = round(time.monotonic() - started, 2)
    log(f"总耗时：{elapsed} 秒；完成时间：{datetime.datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}")
    log(f"最终状态：{state}")
    if exit_code == 0:
        log("DRY_RUN_OK：断网预演完成" if dry else "活力伊利任务成功：所有账号业务已核验")
    summary = {"applicationKey": "hlyl", "mode": "dry-run" if dry else "live", "status": state,
               "accounts": len(lines), "successfulAccounts": good if not dry else 0,
               "dryRunAccounts": good if dry else 0, "failedAccounts": bad,
               "configurationError": configuration_error, "stages": totals,
               "results": results, "seconds": elapsed, "notification": delivery, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
