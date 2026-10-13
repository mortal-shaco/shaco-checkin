#!/usr/bin/env python3
# name: 百度网盘会员成长值
# cron: 0 8 * * *
# SPDX-License-Identifier: MIT
# 来源: Sitoi/dailycheckin, dailycheckin/baiduwp/main.py
# 上游版本: 135cc236e59ac4f14bcddc44acb3cbb3ed6010b5
# 上游未声明定时规则；本独立版本默认每日 08:00 执行。
"""百度网盘会员签到、每日答题和会员信息查询。

BAIDUWP_COOKIE: 登录 https://pan.baidu.com 后，通过浏览器开发者工具的
网络面板，复制发送给 pan.baidu.com 的完整 Cookie 请求头值（不含 Cookie:）。
每个非空行为一个账号，Cookie 内的分号及等号原样保留，不用 & 或 @ 分账号。
BAIDUWP_TASKS: 可选逗号分隔 signin,quiz,info，默认全部执行。
BAIDUWP_DRY_RUN=1: 完全断网，只检查参数并模拟执行与通知，不验证真实账号。
QINGLONG_NOTIFY=0: 禁用通知。QINGLONG_NOTIFY_DIR: 可选青龙通知文件目录。

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

import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

TITLE = "百度网盘会员成长值"
BASE = "https://pan.baidu.com"
TASK_NAMES = {"signin": "会员签到", "quiz": "每日答题", "info": "会员信息查询"}
FALSE_VALUES = {"0", "false", "no", "off"}


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Cookie 不得被重定向传给其他地址；登录重定向也不算成功。
        raise TaskError("接口发生重定向，请检查登录状态")


def values_for(payload, key):
    values = []
    if isinstance(payload, dict):
        if key in payload:
            values.append(payload[key])
        for name in ("data", "result", "user_info", "userinfo"):
            if isinstance(payload.get(name), dict):
                values.extend(values_for(payload[name], key))
    return values


def number(payload, key):
    values = values_for(payload, key)
    if len(values) != 1:
        raise TaskError(f"响应缺少或包含不明确的 {key} 字段")
    value = values[0]
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise TaskError(f"响应 {key} 字段格式异常")
    return int(value)


def identity(payload, cookie):
    for key in ("nickname", "display_name", "username", "uname", "public_uid", "uid"):
        for value in values_for(payload, key):
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                # 身份原样显示，但不允许手机号、凭据或控制字符进入日志。
                secrets = [part.split("=", 1)[1].strip() for part in cookie.split(";") if "=" in part]
                if value and not re.search(r"[\x00-\x1f\x7f]|(?:\+?86)?1[3-9]\d{9}", value) and not any(s and s in value for s in secrets):
                    log(f"官方账号身份（{key}）：{value}")
                    return


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, **params):
        params = {"app_id": "250528", "web": "5", **params}
        url = BASE + path + "?" + urllib.parse.urlencode(params)
        headers = {
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
            "Referer": BASE + "/wap/svip/growth/task",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            with self.opener.open(urllib.request.Request(url, headers=headers), timeout=15) as response:
                if response.status != 200:
                    raise TaskError(f"HTTP 状态异常：{response.status}")
                raw = response.read(262145)
            if len(raw) > 262144:
                raise TaskError("响应超过大小限制")
            payload = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 请求失败：{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络请求失败或超时") from None
        except (ValueError, UnicodeError, RecursionError):
            raise TaskError("接口响应不是有效 JSON") from None
        if not isinstance(payload, dict):
            raise TaskError("接口响应结构异常")
        # 上游未提供“已签到”等业务码，不能猜测非零码的含义。
        for key in ("errno", "error_code", "code"):
            for value in values_for(payload, key):
                if isinstance(value, bool) or str(value) != "0":
                    raise TaskError("接口返回非成功业务码，请检查凭据或接口契约")
        for value in values_for(payload, "success"):
            if value is not True and str(value) != "1":
                raise TaskError("接口报告业务失败")
        identity(payload, self.cookie)
        return payload

    def run_task(self, task):
        if task == "signin":
            payload = self.get("/rest/2.0/membership/level", method="signin")
            return f"签到获得成长值 {number(payload, 'points')}"
        if task == "quiz":
            question = self.get("/act/v2/membergrowv2/getdailyquestion")
            ask_id, answer = number(question, "ask_id"), number(question, "answer")
            log("题目读取成功，答案参数完整")
            payload = self.get("/act/v2/membergrowv2/answerquestion", ask_id=ask_id, answer=answer)
            return f"答题获得成长值 {number(payload, 'score')}"
        payload = self.get("/rest/2.0/membership/user", method="query")
        return f"当前会员等级 {number(payload, 'current_level')}，成长值 {number(payload, 'current_value')}"


def notify(summary, dry):
    body = (f"模式：{summary['mode']}；状态：{summary['status']}\n"
            f"账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}\n"
            f"子任务成功：{summary['tasks_success']}；失败：{summary['tasks_failed']}；"
            f"跳过：{summary['tasks_skipped']}")
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in FALSE_VALUES:
        log("通知已禁用")
        return "disabled"
    if dry:
        log(f"断网预演通知（未发送）：{body.replace(chr(10), '；')}")
        return "simulated"
    try:
        try:
            from notify import send
        except ImportError:
            paths = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            send = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    send = getattr(module, "send", None)
                    if callable(send):
                        break
        if not callable(send):
            log("⚠️ 通知模块不可用，保留业务退出码")
            return "unavailable"
        send(TITLE, body)
        log("通知调用完成")
        return "sent"
    except BaseException:
        log("⚠️ 通知发送失败，保留业务退出码")
        return "failed"


def main():
    started = time.monotonic()
    dry = os.getenv("BAIDUWP_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    accounts = [line.strip() for line in os.getenv("BAIDUWP_COOKIE", "").splitlines() if line.strip()]
    requested = [x.strip() for x in os.getenv("BAIDUWP_TASKS", "signin,quiz,info").split(",") if x.strip()]
    tasks = list(dict.fromkeys(requested))
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "accounts": len(accounts),
               "success": 0, "failed": 0, "tasks_success": 0, "tasks_failed": 0,
               "tasks_skipped": 0, "already_complete": 0, "results": []}
    print(f"========== {TITLE} ==========", flush=True)
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{summary['mode']}；账号数：{len(accounts)}")
    config_error = not accounts or not tasks or any(t not in TASK_NAMES for t in tasks)
    if config_error:
        log("❌ 配置错误：必须提供 BAIDUWP_COOKIE，并选择有效的 BAIDUWP_TASKS")
    else:
        for index, cookie in enumerate(accounts, 1):
            account_started = time.monotonic()
            result = {"account": index, "total": len(tasks), "success": 0, "already_complete": 0, "skipped": 0, "failed": 0}
            log(f"账号 {index} 开始")
            # 不猜测账号 Cookie 中特定字段；要求至少一对非空的名称和值。
            valid = not re.search(r"[\x00-\x1f\x7f]", cookie) and any(
                "=" in p and all(v.strip() for v in p.split("=", 1)) for p in cookie.split(";"))
            client = None if dry or not valid else Client(cookie)
            for stage, task in enumerate(tasks, 1):
                stage_started = time.monotonic()
                log(f"账号 {index} 阶段 {stage}/{len(tasks)}：{TASK_NAMES[task]}")
                try:
                    if not valid:
                        raise TaskError("Cookie 格式异常，需要完整请求头值")
                    if dry:
                        message = "DRY_RUN_OK 参数检查通过，已模拟该阶段；未访问网络或改变账号状态"
                        result["skipped"] += 1
                    else:
                        message = client.run_task(task)
                        result["success"] += 1
                    log(f"{'⏭️' if dry else '✅'} {message}")
                except TaskError as exc:
                    result["failed"] += 1
                    log(f"❌ {exc}")
                except Exception:
                    result["failed"] += 1
                    log("❌ 执行异常，未输出异常详情或敏感响应")
                log(f"阶段耗时：{time.monotonic() - stage_started:.2f} 秒")
                if not dry and valid and task == "signin" and stage < len(tasks):
                    time.sleep(3)  # 保留原签到后的请求间隔，不重试状态变更。
            result["elapsed_seconds"] = round(time.monotonic() - account_started, 2)
            log(f"账号 {index} 统计：总任务 {result['total']}；成功 {result['success']}；已完成 0；跳过 {result['skipped']}；失败 {result['failed']}；耗时 {result['elapsed_seconds']} 秒")
            summary["failed" if result["failed"] else "success"] += 1
            for field in ("success", "failed", "skipped"):
                summary[f"tasks_{field}"] += result[field]
            summary["results"].append(result)
    exit_code = 2 if config_error else (1 if summary["failed"] else 0)
    summary["status"] = "configuration-error" if config_error else (
        "partial-failure" if summary["failed"] and summary["success"] else
        "failure" if summary["failed"] else "dry-run" if dry else "success")
    summary["notification"] = notify(summary, dry)
    summary["elapsed_seconds"] = round(time.monotonic() - started, 2)
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    summary["exit_code"] = exit_code
    print("----------------------------------------", flush=True)
    log(f"任务统计：账号 {summary['accounts']}；成功 {summary['success']}；失败 {summary['failed']}；子任务成功 {summary['tasks_success']}；失败 {summary['tasks_failed']}；跳过 {summary['tasks_skipped']}")
    log(f"完成时间：{summary['finished_at']}；总耗时：{summary['elapsed_seconds']} 秒；通知：{summary['notification']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
