#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 顺丰快递积分任务
# cron: 56 9 * * *
"""顺丰快递积分任务。SF_ACCOUNTS 每行一个 JSON 账号对象，沿用上游字段。
Author: ZaiZaiCat
Date: 2025-01-20
来源: comeonbabyy1/qiandao-jiaob/script/sf/{main.py,api.py,code.js}
维护版采用 Python 标准库实现 HTTP、MD5 签名及 SW8，无需 JavaScript 执行器。
上游未指定 cron，维护版默认每日 08:00。任务完成须通过 SF_TASK_CODES 显式允许。

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('c1b75e3c541294ce', 'scripts/comeonbabyy1_qiandao_jiaob_sf.py', 'comeonbabyy1_qiandao_jiaob_sf.py', 'comeonbabyy1_qiandao_jiaob_sf')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

TITLE = "顺丰快递积分任务"
BASE = "https://mcs-mimp-web.sf-express.com"
CATALOG = "c1b75e3c541294ce"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1")
PATHS = {
    "sign": "/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage",
    "query": "/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES",
    "finish": "/mcs-mimp/commonPost/~memberEs~taskRecord~finishTask",
    "reward": "/mcs-mimp/commonNoLoginPost/~memberNonactivity~integralTaskStrategyService~fetchTasksReward",
}
SECRETS = []


class TaskError(Exception):
    """仅携带可安全输出的固定错误。"""


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def safe_text(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return " ".join(text.split())[:280]


def register_secrets(account):
    for key in ("cookies", "user_id", "device_id"):
        value = account.get(key)
        if isinstance(value, str) and value:
            SECRETS.append(value)
            if key == "cookies":
                for part in value.split(";"):
                    if "=" in part:
                        SECRETS.append(part.split("=", 1)[1].strip())


def parse_account(line):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError("账号必须为单行 JSON 对象") from None
    if not isinstance(account, dict):
        raise TaskError("账号必须为单行 JSON 对象")
    register_secrets(account)
    for key in ("cookies", "user_id"):
        if not isinstance(account.get(key), str) or not account[key].strip():
            raise TaskError("账号缺少 cookies 或 user_id")
    for key in ("cookies", "user_id", "device_id", "user_agent", "channel"):
        value = account.get(key)
        if value is not None and (not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise TaskError("账号字段必须为无控制字符的字符串")
    for key in ("cookies", "user_agent", "channel", "device_id"):
        try:
            (account.get(key) or "").encode("latin-1")
        except UnicodeEncodeError:
            raise TaskError("HTTP 请求头字段必须使用原始抓包值") from None
    return account


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，已阻止转发凭据")


class SFExpressAPI:
    def __init__(self, account, dry_run=False):
        self.account = account
        self.dry_run = dry_run
        self.opener = urllib.request.build_opener(NoRedirect)

    def call(self, action, payload):
        if self.dry_run:
            raise TaskError("预演禁止调用 HTTP")
        timestamp = str(int(time.time() * 1000))
        path = PATHS[action]
        encode = lambda text: base64.b64encode(text.encode()).decode()
        sw8 = "-".join(["1", encode(str(uuid.uuid4())), encode(str(uuid.uuid4())), "0",
                        encode("fb40817085be4e398e0b6f4b08177746"), encode("web"),
                        encode("/n/ryqq/toplist/4"), encode(path)])
        headers = {
            "User-Agent": self.account.get("user_agent") or UA,
            "Cookie": self.account["cookies"], "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*", "Accept-Encoding": "identity",
            "timestamp": timestamp,
            "signature": hashlib.md5(("wwesldfs29aniversaryvdld29&timestamp=" + timestamp
                                      + "&sysCode=MCS-MIMP-CORE").encode()).hexdigest(),
            "syscode": "MCS-MIMP-CORE", "platform": "SFAPP", "sw8": sw8,
            "Origin": BASE, "Referer": BASE + "/superWelfare?citycode=&cityname=&tab=0",
            "Accept-Language": "zh-CN,zh;q=0.9", "Cache-Control": "no-cache", "Pragma": "no-cache",
        }
        if self.account.get("channel"):
            headers["channel"] = self.account["channel"]
        if action == "sign":
            headers["Referer"] = BASE + "/superWelfare?" + urllib.parse.urlencode({
                "userId": self.account["user_id"], "path": "/superWelfare",
                "supportShare": "YES", "from": "appIndex", "tab": "1",
            })
            if self.account.get("device_id"):
                headers["deviceid"] = self.account["device_id"]
        if action == "finish":
            headers["Referer"] = BASE + "/home?from=qqjrwzx515&WC_AC_ID=111&WC_REPORT=111"
        request = urllib.request.Request(BASE + path, json.dumps(payload).encode(), headers, method="POST")
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise TaskError("接口响应超出大小限制")
                result = json.loads(raw)
        except (urllib.error.URLError, OSError, ValueError):
            raise TaskError("HTTP、网络或 JSON 解析失败，未输出响应内容") from None
        if not isinstance(result, dict) or result.get("success") is not True:
            raise TaskError("接口未明确返回 success=true，业务失败")
        return result

    def common_payload(self):
        return {"channelType": "1", "deviceId": self.account.get("device_id")}


def reveal_identity(result):
    obj = result.get("obj")
    if not isinstance(obj, dict):
        return
    containers = [obj]
    containers.extend(obj[key] for key in ("userInfo", "memberInfo") if isinstance(obj.get(key), dict))
    for data in containers:
        for key in ("nickname", "nickName", "username", "displayName", "publicUid"):
            if isinstance(data.get(key), (str, int)) and not isinstance(data[key], bool):
                log("官方账号身份 " + safe_text(data[key]))


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise TaskError("积分或天数响应格式异常")
    return value


class AccountRun:
    def __init__(self, index):
        self.index = index
        self.start = time.monotonic()
        self.stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        self.sign_success = False
        self.sign_days = 0
        self.points = 0

    def stage(self, name, operation):
        self.stats["total"] += 1
        started = time.monotonic()
        label = f"账号{self.index} 阶段{self.stats['total']} {name}"
        log(label + " 开始")
        try:
            outcome, detail = operation()
            self.stats[outcome] += 1
            icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️"}[outcome]
            log(f"{label} {icon} {detail} 耗时 {time.monotonic() - started:.2f}秒")
            return True
        except Exception as error:
            self.stats["failed"] += 1
            message = str(error) if isinstance(error, TaskError) else "执行异常，已隐藏详细信息"
            log(f"{label} ❌ {message} 耗时 {time.monotonic() - started:.2f}秒")
            return False

    def summary(self):
        result = {"account": self.index, **self.stats, "sign_success": self.sign_success,
                  "sign_days": self.sign_days, "total_points": self.points,
                  "duration": round(time.monotonic() - self.start, 2)}
        log(f"账号{self.index} 统计 总任务 {result['total']} 成功 {result['success']} "
            f"已完成 {result['alreadyComplete']} 跳过 {result['skipped']} 失败 {result['failed']} "
            f"连续签到 {self.sign_days}天 积分 {self.points} 耗时 {result['duration']}秒")
        return result


def run_account(run, account, codes, dry):
    api = SFExpressAPI(account, dry)
    if dry:
        run.stage("断网预演", lambda: ("success", "DRY_RUN_OK 参数有效；计划签到、查询、领取奖励；仅执行明确允许的任务；未发送请求"))
        return

    def sign():
        result = api.call("sign", {"comeFrom": "vioin", "channelFrom": "SFAPP"})
        reveal_identity(result)
        obj = result.get("obj")
        if not isinstance(obj, dict):
            raise TaskError("签到响应缺少 obj 对象")
        run.sign_days = number(obj.get("countDay", 0))
        packages = obj.get("integralTaskSignPackageVOList", [])
        if not isinstance(packages, list):
            raise TaskError("签到礼包响应格式异常")
        run.sign_success = True
        for package in packages:
            if isinstance(package, dict):
                log("签到礼包 " + safe_text(package.get("commodityName", "未命名礼包"))
                    + " 有效期 " + safe_text(package.get("invalidDate", "未提供")))
        return ("alreadyComplete" if obj.get("hasFinishSign") == 1 else "success",
                f"签到已验证，连续 {run.sign_days} 天，礼包 {len(packages)} 个")

    run.stage("签到领取礼包", sign)
    time.sleep(random.uniform(2, 5))
    tasks = []

    def query():
        result = api.call("query", api.common_payload())
        reveal_identity(result)
        obj = result.get("obj")
        if not isinstance(obj, dict) or not isinstance(obj.get("taskTitleLevels"), list):
            raise TaskError("任务列表响应结构异常")
        tasks.extend(obj["taskTitleLevels"])
        if any(not isinstance(task, dict) for task in tasks):
            raise TaskError("任务条目响应结构异常")
        return "success", f"已验证任务列表，共 {len(tasks)} 项"

    if not run.stage("查询每日积分任务", query):
        return
    reward_needed = False
    for task in tasks:
        title = safe_text(task.get("title", "未命名任务"))
        if task.get("taskPeriod") != "D":
            run.stage(title, lambda: ("skipped", "非日常任务，保持原周期"))
        elif task.get("status") == 3:
            run.stage(title, lambda: ("alreadyComplete", "官方标记已完成"))
        elif task.get("status") == 2:
            reward_needed = True
            run.stage(title, lambda: ("alreadyComplete", "任务已完成，等待统一领取奖励"))
        elif task.get("status") != 1:
            def invalid_status():
                raise TaskError("未知任务状态，停止该任务操作")
            run.stage(title, invalid_status)
        elif not isinstance(task.get("taskCode"), str) or not task["taskCode"]:
            def missing_code():
                raise TaskError("任务缺少 taskCode")
            run.stage(title, missing_code)
        elif task["taskCode"] not in codes:
            run.stage(title, lambda: ("skipped", "未列入 SF_TASK_CODES，未执行完成操作"))
        else:
            time.sleep(random.uniform(10, 15))
            def finish():
                api.call("finish", {"taskCode": task["taskCode"]})
                return "success", "完成接口明确确认成功"
            if run.stage(title, finish):
                reward_needed = True
    if reward_needed:
        def reward():
            result = api.call("reward", api.common_payload())
            items = result.get("obj")
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise TaskError("奖励响应格式异常")
            points = sum(number(item.get("point")) for item in items)
            run.points += points
            return "success", f"领取奖励已验证，本次积分 {points}"
        run.stage("领取任务积分", reward)
    else:
        run.stage("领取任务积分", lambda: ("skipped", "没有已确认可领取的任务"))


def notify(summary, dry):
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE:
        return "已关闭"
    if switch not in TRUE | {"auto"}:
        return "开关无效，未发送"
    selectors = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if switch == "auto" and selectors is not None:
        patterns = re.split(r"[,;\s]+", selectors.strip())
        names = [CATALOG, "script/sf/main.py", "candidate.py", Path(__file__).name]
        if not any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in patterns if pattern):
            return "未选中"
    if dry:
        log("通知预演 已生成脱敏摘要，断网模式不调用通知模块")
        return "断网预演"
    body = (f"状态 {summary['status']}\n账号总数 {summary['accounts']}\n成功数 {summary['succeeded']}"
            f"\n失败数 {summary['failed']}\n子任务 {json.dumps(summary['tasks'], ensure_ascii=False)}")
    # 在限时子进程加载青龙通知，隔离第三方输出，不改变业务退出码。
    code = '''import importlib.util, json, os, sys
from pathlib import Path
title, body = json.loads(sys.stdin.read())
try:
    from notify import send
except ImportError:
    paths = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    module = None
    for path in paths:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
    if module is None:
        sys.exit(3)
    send = module.send
if send(title, body) is False:
    sys.exit(4)
'''
    try:
        result = subprocess.run([sys.executable, "-c", code], input=json.dumps([TITLE, body]),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return "已调用青龙通知" if result.returncode == 0 else "通知不可用或失败，保留业务退出码"
    except (OSError, subprocess.TimeoutExpired):
        return "通知不可用或超时，保留业务退出码"


def main():
    started = time.monotonic()
    dry_value = os.environ.get("SF_DRY_RUN", "0").lower()
    dry = dry_value in TRUE
    lines = [line.strip() for line in os.environ.get("SF_ACCOUNTS", "").splitlines() if line.strip()]
    log("=" * 56)
    log(TITLE + f" 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"模式 {'断网预演' if dry else '正式执行'} 账号数 {len(lines)}")
    codes = {code.strip() for code in os.environ.get("SF_TASK_CODES", "").split(",") if code.strip()}
    results = []
    config_error = not lines or dry_value not in TRUE | FALSE
    if not lines:
        log("❌ 配置错误，SF_ACCOUNTS 至少需要一行账号")
    if dry_value not in TRUE | FALSE:
        log("❌ 配置错误，SF_DRY_RUN 必须使用布尔开关值")
    if not config_error:
        for index, line in enumerate(lines, 1):
            run = AccountRun(index)
            parsed = []
            if run.stage("校验账号配置", lambda: (parsed.append(parse_account(line)) or ("success", "必需字段有效，凭据已隐藏"))):
                try:
                    run_account(run, parsed[0], codes, dry)
                except Exception:
                    def unexpected():
                        raise TaskError("账号执行异常，继续处理其他账号")
                    run.stage("账号异常处理", unexpected)
            else:
                config_error = True
            results.append(run.summary())
            if not dry and index < len(lines):
                time.sleep(random.uniform(3, 8))
    failed = sum(result["failed"] > 0 for result in results)
    succeeded = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else
              "partial-failure" if failed and succeeded else "failure" if failed else
              "dry-run" if dry else "success")
    summary = {"status": status, "mode": "dry-run" if dry else "live", "accounts": len(lines),
               "succeeded": succeeded, "failed": failed if results else (len(lines) if config_error else 0),
               "tasks": {key: sum(result[key] for result in results)
                         for key in ("total", "success", "alreadyComplete", "skipped", "failed")},
               "results": results, "exitCode": exit_code}
    summary["notification"] = notify(summary, dry)
    summary["duration"] = round(time.monotonic() - started, 2)
    summary["finishTime"] = datetime.now().isoformat(timespec="seconds")
    log("-" * 56)
    log(f"任务统计 账号总数 {summary['accounts']} 成功 {succeeded} 失败 {summary['failed']}")
    log("子任务统计 " + json.dumps(summary["tasks"], ensure_ascii=False))
    log(f"通知状态 {summary['notification']} 总耗时 {summary['duration']}秒")
    log(f"完成时间 {summary['finishTime']} 最终状态 {status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
