# -*- coding: utf-8 -*-
# name: 奥拉星每日任务与积分
# cron: 38 0 * * *
"""独立维护版本；来源 Sitoi/dailycheckin dailycheckin/aolaxing/main.py。
原来源未声明 cron，本版本建议每天 08:00 运行。
AOLAXING_COOKIE：登录 www.100bt.com 后，从开发者工具中对应
service.100bt.com/creditmall 请求的 Cookie 请求头获取。每行一个账号；
兼容 AOLAXING 环境变量中的原配置 JSON 列表（每项含 cookie）。
AOLAXING_TASK_IDS：可选，逗号分隔已审阅的数字任务 ID；默认只查询。
原脚本自动执行任意未完成任务，因无法确认副作用，改为显式选择。
AOLAXING_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
不打印手机号、Cookie、原始响应。HTTPS 无降级；通知失败不改变业务退出码。

MIT License
Source attribution: Sitoi/dailycheckin and its original contributors.
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
        _ql_notify_identities = ('3ca8984737c9322f', 'scripts/aolaxing.py', 'aolaxing.py', 'aolaxing')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import importlib
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

TITLE = "奥拉星每日任务与积分"
BASE = "https://service.100bt.com/creditmall/"
DISABLED = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in DISABLED | {""}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口发生重定向，已阻止传递凭据")


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, params=None):
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={
            "Cookie": self.cookie, "Referer": "https://www.100bt.com/",
            "Accept": "application/json", "User-Agent": "Qinglong-AoLaXing/1.0",
        })
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise TaskError("接口响应过大")
            result = json.loads(raw.decode("utf-8"))
        except TaskError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("请求失败或超时，请检查网络和 Cookie") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口响应不是有效 JSON") from None
        if not isinstance(result, dict) or not isinstance(result.get("jsonResult"), dict):
            raise TaskError("接口响应结构变化或登录失效")
        return result["jsonResult"]

    def tasks(self):
        data = self.get("activity/daily_task_list.jsonp", {"gameId": 2, "_": int(time.time()*1000)}).get("data")
        if not isinstance(data, list):
            raise TaskError("任务列表无有效数据，无法确认登录状态")
        tasks = {}
        for item in data:
            if not isinstance(item, dict):
                raise TaskError("任务条目格式异常")
            task_id = str(item.get("taskID", ""))
            if not task_id.isdecimal() or item.get("status_desc") not in {"未完成", "已完成"} or not isinstance(item.get("name"), str):
                raise TaskError("任务字段或状态变化，停止执行")
            if task_id in tasks:
                raise TaskError("任务 ID 重复，停止执行")
            tasks[task_id] = item
        return tasks

    def user(self):
        data = self.get("my/user_info.jsonp").get("data")
        if not isinstance(data, dict):
            raise TaskError("账号信息无有效数据")
        for field in ("credit", "creditHistory", "signInTotal"):
            value = data.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float, str)) or not re.fullmatch(r"\d+(?:\.\d+)?", str(value)):
                raise TaskError("积分或签到统计字段异常")
        return data


def identity(data, cookie):
    for field in ("nickname", "nickName", "username", "displayName", "uid", "userId"):
        value = data.get(field)
        if isinstance(value, (str, int)) and str(value):
            value = str(value)
            # 只展示身份字段；抑制意外携带的凭据、手机号和日志控制符。
            if cookie in value or re.search(r"(?i)cookie|token|session|1[3-9]\d{9}", value) or any(ord(c) < 32 for c in value):
                continue
            log(f"账号身份：{value}")
            break


def accounts():
    canonical = os.getenv("AOLAXING_COOKIE", "")
    if canonical.strip():
        values = [line.strip() for line in canonical.splitlines() if line.strip()]
    else:
        legacy = os.getenv("AOLAXING", "")
        if not legacy.strip():
            raise TaskError("缺少必填变量 AOLAXING_COOKIE")
        try:
            data = json.loads(legacy)
            if not isinstance(data, list) or not data:
                raise ValueError()
            values = [item["cookie"] for item in data]
        except (ValueError, TypeError, KeyError):
            raise TaskError("兼容变量 AOLAXING 必须是含 cookie 的 JSON 列表") from None
    if any(not isinstance(v, str) or not v.strip() or "\r" in v or "\n" in v for v in values):
        raise TaskError("Cookie 格式无效，每行只能包含一个账号")
    return values


def notify(body, dry):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    # 通知发送也可能联网；预演仅演练通知内容，不调用发送函数。
    if dry:
        log("⏭️ 通知预演：" + body)
        return "断网预演"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            candidates = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                candidates.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            candidates += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
            path = next((p for p in candidates if p.is_file()), None)
            if path is None:
                log("⚠️ 未找到青龙 notify.py，业务退出码保持不变")
                return "不可用"
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # 屏蔽通知模块自身可能输出的响应或配置。
        from contextlib import redirect_stdout, redirect_stderr
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            module.send(TITLE, body)
        return "已调用"
    except Exception:
        log("⚠️ 通知投递失败，业务退出码保持不变")
        return "失败"


def run():
    start = time.monotonic()
    dry = enabled("AOLAXING_DRY_RUN")
    log("========== " + TITLE + " ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '在线'}")
    results = []
    config_error = False
    try:
        cookies = accounts()
        ids = [s.strip() for s in os.getenv("AOLAXING_TASK_IDS", "").split(",") if s.strip()]
        if any(not s.isdecimal() for s in ids) or len(set(ids)) != len(ids):
            raise TaskError("AOLAXING_TASK_IDS 必须为不重复的数字 ID，以逗号分隔")
    except TaskError as error:
        log("❌ 配置错误：" + str(error))
        cookies, ids = [], []
        config_error = True
    log(f"账号总数：{len(cookies)}")
    for index, cookie in enumerate(cookies, 1):
        begin = time.monotonic()
        counts = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        log(f"---- 账号 {index} ----")
        def stage(number, label, operation):
            counts["total"] += 1
            stamp = time.monotonic()
            log(f"账号 {index} 阶段 {number}：{label}")
            previous_complete = counts["alreadyComplete"]
            try:
                value = operation()
            except Exception as error:
                counts["failed"] += 1
                detail = str(error) if isinstance(error, TaskError) else "内部处理异常，未确认成功"
                log(f"❌ 阶段 {number} 失败：{detail}；耗时 {time.monotonic()-stamp:.2f} 秒")
                raise TaskError("阶段失败") from None
            if counts["alreadyComplete"] == previous_complete:
                counts["success"] += 1
            log(f"✅ 阶段 {number} {'预演通过（未请求接口）' if dry else '核验通过'}；耗时 {time.monotonic()-stamp:.2f} 秒")
            return value
        try:
            client = None if dry else Client(cookie)
            tasks = stage(1, "查询每日任务", lambda: {} if dry else client.tasks())
            if dry:
                counts["skipped"] += len(ids)
                counts["total"] += len(ids)
                log(f"⏭️ 阶段 2：预演显式任务数 {len(ids)}，未执行任何状态变更")
            else:
                for number, task_id in enumerate(ids, 2):
                    def execute(task_id=task_id):
                        if task_id not in tasks:
                            raise TaskError("指定任务不在今日任务列表")
                        if tasks[task_id]["status_desc"] == "已完成":
                            counts["alreadyComplete"] += 1
                            log("☑️ 指定任务已完成")
                            return
                        client.get("activity/do_task.jsonp", {"taskId": task_id, "gameId": 2, "_": int(time.time()*1000)})
                        time.sleep(2.5)
                        refreshed = client.tasks()
                        if task_id not in refreshed or refreshed[task_id]["status_desc"] != "已完成":
                            raise TaskError("任务执行后未确认完成")
                        tasks.update(refreshed)
                    try:
                        stage(number, f"核验并执行指定任务 {task_id}", execute)
                    except TaskError:
                        continue
            data = stage(len(ids)+2, "查询积分与累计签到", lambda: None if dry else client.user())
            if data is not None:
                identity(data, cookie)
                log(f"当前积分：{data['credit']}；总共获得积分：{data['creditHistory']}；总签到：{data['signInTotal']}")
                log(f"今日任务总数：{len(tasks)}；今日任务完成数：{sum(t['status_desc']=='已完成' for t in tasks.values())}")
            if not ids:
                log("⏭️ 未配置任务 ID，仅查询任务与积分")
        except TaskError:
            pass
        results.append({"account": index, "ok": counts["failed"] == 0, **counts})
        log(f"账号 {index} 统计：总阶段 {counts['total']}，通过 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic()-begin:.2f} 秒")
    failed = sum(not r["ok"] for r in results)
    success = len(results)-failed
    status = "configuration-error" if config_error else "partial-failure" if failed and success else "failure" if failed else "dry-run" if dry else "success"
    code = 1 if config_error or failed else 0
    body = f"账号总数 {len(cookies)}，成功 {success}，失败 {failed}；状态 {status}"
    notification = notify(body, dry)
    log("----------------------------------------")
    log(body + f"；子任务通过 {sum(r['success'] for r in results)}，失败 {sum(r['failed'] for r in results)}，已完成 {sum(r['alreadyComplete'] for r in results)}，跳过 {sum(r['skipped'] for r in results)}；通知：{notification}")
    log(f"完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic()-start:.2f} 秒；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"status": status, "dryRun": dry, "accounts": len(cookies), "success": success, "failed": failed, "configurationError": config_error, "results": results, "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(run())
