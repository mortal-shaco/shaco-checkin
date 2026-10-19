#!/usr/bin/env python3
# name: 机场签到（速鹰666）
# cron: 27 1 * * *
# new Env("机场签到（速鹰666）")
# 上游：CN-Grace/QinglongScripts / Airport.py
# commit: a40a2b080e0160bd8e0b0b807081115537b87153
# SPDX-License-Identifier: MIT
# 原文件未包含单独的版权声明；保留上游归属及 MIT 许可。
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
"""速鹰666每日登录、签到和剩余流量查询。

SUYING_ACCOUNTS：每行 登录邮箱|密码，仅在第一个 | 分割，密码后续字符保留。
从本人速鹰666网站注册/账户资料取得邮箱，密码为本人登录密码。
未设置新变量时兼容 SUYING_USERNAME 与 SUYING_PASSWORD（单账号）。
SUYING_DRY_RUN=1 完全断网预演；不会登录、签到或调用通知渠道。
依赖：公开 Python 包 requests、lxml。保持原有每日 00:00 计划。
唯一业务写操作是每日签到；不保存原始页面、不输出凭据或原始响应。
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
        _ql_notify_identities = ('8cd72e9849a3c893', 'scripts/airport.py', 'airport.py', 'airport')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone, timedelta

BASE_URL = "https://suying00.com"
TRAFFIC_XPATH = '//*[@id="app"]/div/div[3]/section/div[3]/div[2]/div/div[2]/div[2]'
MAX_BYTES = 2 * 1024 * 1024
TITLE = "机场签到"


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    print(f"[{stamp()[11:]}] {message}", flush=True)


def enabled(value):
    return str(value).lower().strip() in {"1", "true", "yes", "on"}


def accounts_from_env():
    if "SUYING_ACCOUNTS" in os.environ:
        lines = [line for line in os.environ["SUYING_ACCOUNTS"].splitlines() if line.strip()]
        accounts = []
        for line in lines:
            fields = line.split("|", 1)
            accounts.append((fields[0].strip(), fields[1])
                            if len(fields) == 2 and fields[0].strip() and fields[1] else None)
        return accounts
    username = os.environ.get("SUYING_USERNAME", "")
    password = os.environ.get("SUYING_PASSWORD", "")
    return [(username, password) if username and password else None] if username or password else []


class TaskError(Exception):
    pass


def request(session, method, path, data=None):
    # 不自动重试签到，不跟随跳转转发账号信息；HTTP 错误不输出响应。
    with session.request(method, BASE_URL + path, data=data, timeout=(10, 10),
                         allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise TaskError(f"接口 HTTP 状态异常（{response.status_code}）")
        chunks, size = [], 0
        deadline = time.monotonic() + 30
        for chunk in response.iter_content(8192):
            size += len(chunk)
            if size > MAX_BYTES or time.monotonic() > deadline:
                raise TaskError("响应超出大小或时间限制")
            chunks.append(chunk)
        return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")


def json_response(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        raise TaskError("接口未返回有效 JSON，无法核验业务成功") from None
    if not isinstance(value, dict):
        raise TaskError("接口 JSON 结构异常")
    return value


def verified(value):
    # 兼容原有 ret 与 success，但拒绝字符串、非零失败码和仅有 Cookie。
    if "ret" in value:
        return type(value["ret"]) is int and value["ret"] == 1
    return value.get("success") is True


def identity(value, credentials):
    profile = value.get("data")
    for container in (value, profile if isinstance(profile, dict) else {}):
        for field in ("nickname", "username", "display_name", "uid"):
            name = container.get(field)
            if not isinstance(name, (str, int)) or isinstance(name, bool):
                continue
            name = str(name)
            # 身份字段原样输出；疑似手机号、凭据或注入内容不输出。
            if (not name or len(name) > 100 or any(ord(c) < 32 for c in name)
                    or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", name)
                    or any(secret and secret in name for secret in credentials)):
                continue
            log(f"官方账号身份：{name}")
            return


def checkin(session):
    value = json_response(request(session, "POST", "/user/checkin"))
    if verified(value):
        return "success", "签到业务成功已核验"
    message = value.get("msg")
    # 上游无已签到业务码说明，仅接受明确的已完成消息和 ret=0。
    if (type(value.get("ret")) is int and value["ret"] == 0
            and isinstance(message, str) and message.strip() in {
                "今日已签到", "您今天已经签到过了", "您今天已经签到过了。",
                "您已经签到过了", "您已经签到过了。", "已经签到过了"}):
        return "alreadyComplete", "接口确认今日已签到"
    raise TaskError("签到未返回明确成功或已完成结果")


def traffic(session, html_parser):
    content = request(session, "GET", "/user")
    match = re.search(r'var\s+originBody\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        try:
            content = base64.b64decode(match.group(1), validate=True).decode("utf-8")
        except (ValueError, UnicodeError):
            log("⚠️ Base64 页面解码失败，继续使用原始页面解析")
    try:
        tree = html_parser.fromstring(content)
        elements = tree.xpath(TRAFFIC_XPATH)
    except Exception:
        raise TaskError("流量页面解析失败") from None
    if not elements:
        raise TaskError("流量 XPath 未找到匹配元素")
    text = " ".join(elements[0].text_content().split())
    # 仅输出数值及流量单位，禁止将页面任意文本带入日志/通知。
    quantities = re.findall(r"(?<![\w.])\d+(?:\.\d+)?\s*(?:[KMGTPE]i?B|B)(?!\w)", text, re.I)
    if not quantities:
        raise TaskError("流量元素缺少可核验的流量数值")
    return "success", "剩余流量：" + " / ".join(quantities)


def notify(body, dry_run):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        return "已关闭"
    if dry_run:
        log("⏭️ 预演通知：已生成脱敏总结，断网模式不调用渠道")
        return "断网预演已跳过投递"
    try:
        try:
            from notify import send
        except ImportError:
            paths = []
            directory = os.environ.get("QINGLONG_NOTIFY_DIR")
            if directory:
                paths.append(Path(directory) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            selected = next((path for path in paths if path.is_file()), None)
            if selected is None:
                log("⚠️ 通知组件不可用，保留业务退出码")
                return "不可用"
            spec = importlib.util.spec_from_file_location("qinglong_notify", selected)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
        send(TITLE, body)
        return "已调用"
    except Exception:
        log("⚠️ 通知投递失败，保留业务退出码")
        return "失败"


def main():
    started = time.monotonic()
    dry_run = enabled(os.environ.get("SUYING_DRY_RUN", "0"))
    log("========== 机场签到 · 速鹰666 ==========")
    log(f"开始时间：{stamp()}；模式：{'断网预演' if dry_run else '正式执行'}")
    accounts = accounts_from_env()
    log(f"账号总数：{len(accounts)}")
    dependency_error = False
    if not dry_run:
        try:
            import requests
            from lxml import html
        except ImportError:
            dependency_error = True
            log("❌ 缺少公开依赖 requests 或 lxml，请在青龙依赖管理安装")
    results = []
    if not accounts:
        log("❌ 配置错误：请设置 SUYING_ACCOUNTS 或完整的旧版凭据")
    for index, credentials in enumerate(accounts, 1):
        account_started = time.monotonic()
        counters = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
        session = None
        login_ok = False
        log(f"--- 账号 {index} ---")
        for stage, label in enumerate(("登录", "每日签到", "查询剩余流量"), 1):
            stage_started = time.monotonic()
            status, detail = "failure", "未知错误"
            try:
                if stage == 1 and (credentials is None or dependency_error):
                    raise TaskError("账号格式无效或运行依赖缺失")
                if stage > 1 and not login_ok:
                    status, detail = "skipped", "登录未通过，跳过后续动作"
                elif dry_run:
                    status, detail = "skipped", "参数及请求计划通过，无网络请求或业务写入"
                    login_ok = True
                elif stage == 1:
                    session = requests.Session()
                    session.headers.update({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
                    value = json_response(request(session, "POST", "/auth/login", {
                        "email": credentials[0], "passwd": credentials[1], "remember_me": "on", "code": ""}))
                    if not verified(value):
                        raise TaskError("登录业务结果未确认成功")
                    identity(value, credentials)
                    login_ok = True
                    status, detail = "success", "登录业务成功已核验"
                elif stage == 2:
                    status, detail = checkin(session)
                else:
                    status, detail = traffic(session, html)
            except TaskError as error:
                status, detail = "failure", str(error)
            except Exception:
                status, detail = "failure", "请求或处理异常（详情已脱敏）"
            counters[status] += 1
            icon = {"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️", "failure": "❌"}[status]
            log(f"账号 {index} 阶段 {stage}/3 {label}：{icon} {detail}；耗时 {time.monotonic() - stage_started:.2f} 秒")
        if session is not None:
            session.close()
        ok = counters["failure"] == 0
        results.append({"account": index, "ok": ok, **counters})
        log(f"账号 {index} 统计：总任务 3，成功 {counters['success']}，已完成 {counters['alreadyComplete']}，跳过 {counters['skipped']}，失败 {counters['failure']}；耗时 {time.monotonic() - account_started:.2f} 秒")
    good = sum(item["ok"] for item in results)
    bad = len(results) - good
    code = 0 if results and bad == 0 else 1
    status = ("configuration-error" if not results or any(c is None for c in accounts)
              else "dry-run" if dry_run and code == 0
              else "success" if code == 0 else "partial-failure" if good else "failure")
    body = f"账号总数：{len(results)}；成功：{good}；失败：{bad}；状态：{status}"
    if dry_run:
        body += "；断网预演，不代表真实业务成功"
    notification = notify(body, dry_run)
    totals = {key: sum(item[key] for item in results) for key in ("success", "alreadyComplete", "skipped", "failure")}
    elapsed = round(time.monotonic() - started, 2)
    log("----------------------------------------")
    log(body)
    log(f"子任务统计：{json.dumps(totals, ensure_ascii=False)}；总耗时：{elapsed} 秒")
    log(f"完成时间：{stamp()}；通知：{notification}；最终状态：{status}；退出码：{code}")
    if dry_run and code == 0:
        log("DRY_RUN_OK：断网预演完成")
    elif code == 0:
        log("TASK_SUCCESS：全部账号登录、签到及流量查询已核验")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "status": status, "mode": "dry-run" if dry_run else "live",
          "accountCount": len(results), "successCount": good, "failureCount": bad,
          "stages": totals, "accounts": results, "durationSeconds": elapsed,
          "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
