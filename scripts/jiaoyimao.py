#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 交易猫签到
# cron: 35 6 * * *
# SPDX-License-Identifier: Apache-2.0
# 原作：WFRobert，HeiDaotu/WFRobertQL，jiaoyimao.py
# 来源：https://github.com/HeiDaotu/WFRobertQL
"""
File: jiaoyimao.py
Author: WFRobert
Date: 2023/5/24 8:57
cron: 35 6 * * *
new Env('交易猫签到');
Description: 交易猫脚本,实现每日自动签到
Update: 2023/9/1 更新cron

维护版本，按上游 Apache-2.0 许可分发。
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
https://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

功能盘点：每天 06:35 签到、查询剩余积分、发送任务通知；仅签到会修改服务端状态。
无已维护功能或相关来源可供合并。保留两个原始 GET 接口及成功字段；
不推测其他业务码代表已签到，不自动重试签到，不携带上游写死的设备标识或 CSRF。

配置：JIAOYIMAO_ACCOUNTS 每个非空行一个账号，格式为
实际 x-csrf-token 请求头值<TAB>完整 Cookie 请求头值（TAB 是一个制表符）。
仅按第一个 TAB 分割，Cookie 内的 &、@ 不拆分账号。
在自己已登录的交易猫客户端/网页调试工具中查看积分中心的网络请求，
复制 m.jiaoyimao.com/api2/account/integration/ 路径请求的 Cookie
和 x-csrf-token，必须来自同一账号、同一会话。没有抓到有效值时不要猜测或
使用示例；重新登录并重新获取。不要把凭据放进命令行、日志或公开仓库。
兼容单账号旧变量 JIAOYIMAO_COOKIE，须同时设置 JIAOYIMAO_CSRF_TOKEN；
多账号请迁移到组合变量。新旧变量不可同时配置，以免静默忽略账号。
JIAOYIMAO_DRY_RUN=1：完全离线，只检查配置并模拟执行流程，不调用通知网络。
QINGLONG_NOTIFY=1 显式通知，0 禁用；默认 auto 仅匹配
QINGLONG_NOTIFY_SCRIPTS 的脚本才通知，未配置名单时默认不通知。
名单支持目录路径、文件名、glob、catalogId，以逗号、分号或空白分隔。
可选 QINGLONG_NOTIFY_DIR 指向青龙通知模块目录。通知故障不改变业务退出码。
使用青龙本地时区调度 35 6 * * *，无需第三方依赖。
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
        _ql_notify_identities = ('53f140ed0f9a4d21', 'scripts/jiaoyimao.py', 'jiaoyimao.py', 'jiaoyimao')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

TITLE = "交易猫签到"
CATALOG_ID = "53f140ed0f9a4d21"
BASE = "https://m.jiaoyimao.com/api2/account/integration/"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，停止请求，请重新核对会话")


def parse_accounts():
    combined = os.environ.get("JIAOYIMAO_ACCOUNTS", "")
    legacy = os.environ.get("JIAOYIMAO_COOKIE", "")
    token = os.environ.get("JIAOYIMAO_CSRF_TOKEN", "")
    if combined.strip() and (legacy.strip() or token.strip()):
        raise TaskError("新旧凭据变量不能同时配置")
    if combined.strip():
        lines = [line for line in combined.splitlines() if line.strip()]
        result = []
        for line in lines:
            if "\t" not in line:
                result.append(None)
                continue
            csrf, cookie = line.split("\t", 1)
            result.append((csrf.strip(), cookie.strip()))
        return result
    if legacy.strip():
        if len(legacy.splitlines()) != 1 or len(token.splitlines()) != 1:
            raise TaskError("旧变量只支持单账号，请迁移到逐行组合变量")
        return [(token.strip(), legacy.strip())]
    raise TaskError("缺少 JIAOYIMAO_ACCOUNTS；旧单账号需同时提供 Cookie 和 CSRF")


def validate_account(account):
    if account is None:
        raise TaskError("凭据格式错误：每行需要 CSRF、制表符和 Cookie")
    csrf, cookie = account
    if not csrf or not cookie or "=" not in cookie:
        raise TaskError("凭据不完整：需要有效 CSRF 和完整 Cookie")
    for value in account:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise TaskError("凭据包含不支持的控制字符")
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            raise TaskError("请求头凭据包含不支持的字符") from None


def request_json(action, account):
    csrf, cookie = account
    req = Request(BASE + action, method="GET", headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 12) AliApp(JYM/7.0.2)",
        "Referer": "https://m.jiaoyimao.com/account/integration/center?spm=gcmall.home2022.topshortcut.0",
        "X-CSRF-Token": csrf,
        "X-Requested-With": "com.jym.mall",
        "Cookie": cookie,
        "Accept": "application/json",
    })
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError("接口 HTTP 状态异常")
            payload = response.read(262145)
        if len(payload) > 262144:
            raise TaskError("接口响应过大")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise TaskError("接口响应结构异常")
        return data
    except HTTPError as exc:
        raise TaskError(f"接口 HTTP {exc.code}，未确认业务成功") from None
    except (URLError, TimeoutError, OSError):
        raise TaskError("接口连接失败或超时，未确认业务成功") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口未返回有效 JSON") from None


def show_identity(data, account):
    # 仅读取明确的公开身份字段，绝不打印响应或任意错误消息。
    secrets = list(account)
    secrets.extend(part.split("=", 1)[1].strip() for part in account[1].split(";") if "=" in part)
    containers = [data]
    if isinstance(data.get("data"), dict):
        containers.append(data["data"])
    for obj in containers:
        for key in ("nickname", "nickName", "username", "displayName", "publicUid"):
            value = obj.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (not value or any(secret and secret in value for secret in secrets)
                    or re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", value)
                    or re.search(r"cookie|token|session|authorization", value, re.I)):
                continue
            # JSON 转义只用于避免身份中的换行/控制字符破坏日志。
            log("官方账号身份：" + json.dumps(value, ensure_ascii=False))
            return


def notification_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if switch != "auto":
        raise TaskError("QINGLONG_NOTIFY 仅支持 auto、1/0、true/false、yes/no、on/off")
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    names = {CATALOG_ID, Path(__file__).name, "jiaoyimao.py", "scripts/jiaoyimao.py",
             "scripts/" + Path(__file__).name}
    return any(fnmatch.fnmatchcase(name, selector) for selector in selectors if selector for name in names)


def notify_summary(body, enabled, dry):
    if not enabled:
        return "已禁用或未入通知名单"
    if dry:
        log("通知预演：" + body)
        return "离线预演，未调用通知模块"
    # 通知运行于有超时的独立进程，抑制第三方模块的输出与异常以防泄露。
    dirs = [os.environ.get("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    paths = [str(Path(d) / "notify.py") for d in dirs if d]
    js_paths = [str(Path(d) / "sendNotify.js") for d in dirs if d]
    py_code = """
import contextlib, importlib, importlib.util, json, sys
title, body, paths = json.load(sys.stdin)
with contextlib.redirect_stdout(sys.stderr):
    try:
        module = importlib.import_module('notify')
    except ImportError:
        module = None
        for path in paths:
            from pathlib import Path
            if Path(path).is_file():
                sys.path.insert(0, str(Path(path).parent))
                spec = importlib.util.spec_from_file_location('ql_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                break
    if module is None:
        sys.exit(3)
    result = module.send(title, body)
    if result is False:
        sys.exit(4)
"""
    try:
        result = subprocess.run([sys.executable, "-c", py_code],
                                input=json.dumps([TITLE, body, paths]), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if result.returncode == 0:
            return "通知模块调用完成"
        if result.returncode == 3:
            for path in js_paths:
                if Path(path).is_file():
                    code = ("const fs=require('fs');const d=JSON.parse(fs.readFileSync(0,'utf8'));"
                            "Promise.resolve(require(process.argv[1]).sendNotify(d[0],d[1]))"
                            ".then(r=>{if(r===false)process.exitCode=1})"
                            ".catch(()=>{process.exitCode=1});")
                    result = subprocess.run(["node", "-e", code, path],
                                            input=json.dumps([TITLE, body]), text=True,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            timeout=25)
                    return "通知模块调用完成" if result.returncode == 0 else "通知失败，保留业务退出码"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "通知不可用或发送失败，保留业务退出码"


def main():
    started = time.monotonic()
    dry_value = os.environ.get("JIAOYIMAO_DRY_RUN", "0").strip().lower()
    dry = dry_value in TRUE
    log("========== 交易猫签到 ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 模式：{'离线预演' if dry else '正式执行'}")
    accounts = []
    results = []
    configuration_error = False
    enabled = False
    try:
        if dry_value not in TRUE | FALSE:
            raise TaskError("JIAOYIMAO_DRY_RUN 值无效")
        enabled = notification_enabled()
        accounts = parse_accounts()
    except TaskError as exc:
        configuration_error = True
        log("❌ 配置错误：" + str(exc))
    log(f"账号数量：{len(accounts)}")
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    for index, account in enumerate(accounts, 1):
        begin = time.monotonic()
        counts = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        log(f"--- 账号 {index} ---")
        try:
            validate_account(account)
        except TaskError as exc:
            configuration_error = True
            counts.update(failed=1, skipped=1)
            log("❌ 账号配置错误：" + str(exc))
        else:
            for number, (action, label) in enumerate((("signin", "每日签到"), ("getMyIntegration", "查询剩余积分")), 1):
                step_start = time.monotonic()
                log(f"账号 {index} 阶段 {number}/2：{label}")
                try:
                    if dry:
                        counts["skipped"] += 1
                        log("⏭️ DRY_RUN：已检查请求配置，未发送 HTTP 请求")
                        continue
                    data = request_json(action, account)
                    show_identity(data, account)
                    if action == "signin":
                        if data.get("success") is not True:
                            raise TaskError("签到未获明确成功；不能将未知失败视作已签到")
                        log("✅ 签到成功（success=true）")
                    else:
                        inner = data.get("data")
                        amount = inner.get("amountLeft") if isinstance(inner, dict) else None
                        numeric = (type(amount) in (int, float) and math.isfinite(amount) and amount >= 0)
                        # 上游直接展示该字段；保留数字字符串的兼容，不打印任意响应文本。
                        numeric = numeric or (isinstance(amount, str) and
                                              re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount) is not None
                                              and len(amount) <= 40)
                        if (type(data.get("stateCode")) is not int or data["stateCode"] != 200 or not numeric):
                            raise TaskError("积分查询业务码或剩余积分字段异常")
                        log(f"✅ 当前剩余积分：{amount}")
                    counts["success"] += 1
                except TaskError as exc:
                    counts["failed"] += 1
                    log("❌ " + str(exc))
                except Exception:
                    counts["failed"] += 1
                    log("❌ 请求处理异常，未确认业务成功（异常详情已隐藏）")
                finally:
                    log(f"账号 {index} 阶段 {number}/2 耗时 {time.monotonic() - step_start:.2f} 秒")
        ok = counts["failed"] == 0
        results.append(ok)
        for key in totals:
            totals[key] += counts[key]
        log(f"账号 {index} 统计：总任务 {counts['total']}，成功 {counts['success']}，已完成 0，跳过 {counts['skipped']}，失败 {counts['failed']}，耗时 {time.monotonic() - begin:.2f} 秒")
    failed = sum(not result for result in results)
    successful = sum(results) if not dry else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and any(results) else
              "failure" if failed else "dry-run" if dry else "success")
    code = 1 if configuration_error or failed else 0
    body = f"状态：{status}；账号总数 {len(accounts)}，成功 {successful}，失败 {failed}，预演通过 {sum(results) if dry else 0}；子任务成功 {totals['success']}，失败 {totals['failed']}，跳过 {totals['skipped']}"
    try:
        notification = notify_summary(body, enabled, dry)
    except Exception:
        notification = "通知处理异常，保留业务退出码"
    log("----------------------------------------")
    log(body)
    log(f"子任务总数 {totals['total']}；已完成 {totals['alreadyComplete']}")
    log("通知状态：" + notification)
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 总耗时 {time.monotonic() - started:.2f} 秒 | 最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "status": status, "dryRun": dry,
          "accounts": len(accounts), "success": successful, "failed": failed,
          "dryRunPassed": sum(results) if dry else 0, "steps": totals,
          "notification": notification, "exitCode": code}, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
