# -*- coding: utf-8 -*-
# name: 魅族社区签到
# cron: 0 9 * * *
# 原始来源: yuxian158/check, dailycheckin_scripts/ck_meizu.py
# 原始提交: 723c834f121ff4eef2dec7afe521071a7efff1a9
# SPDX-License-Identifier: MIT
# 上游文件未附单独版权声明；保留来源署名，按任务确认的 MIT 许可维护。
"""魅族社区独立维护版。

登录 https://bbs.meizu.cn/，在浏览器开发者工具的网络面板中，查看
bbs-act.meizu.cn/index.php 请求的 Cookie 请求头，复制完整值至 MEIZU_COOKIE。
每个非空行一个账号，不以 & 或 @ 分隔；Cookie 中的分号和等号原样保留。
MEIZU_DRAW_COUNT 默认 0；大于 0 时显式同意活动 id=2 的抽奖副作用，
包括可能消耗活动次数或积分。有效范围 0..100，对所有账号生效。
MEIZU_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
上游没有声明 cron，本版提供每日 09:00 的建议计划，可在青龙中调整。

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

import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "魅族社区签到"
URL = "https://bbs-act.meizu.cn/index.php"
FALSE_VALUES = {"0", "false", "no", "off"}


def log(text):
    print("[" + datetime.datetime.now().strftime("%H:%M:%S") + "] " + text,
          flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in FALSE_VALUES | {""}


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向已拒绝，请检查登录状态或接口变更")


def request(cookie, action, dry=False):
    if dry:
        raise TaskError("断网预演禁止请求")
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_2) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74",
        "Cookie": cookie,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if action == "sign":
        headers.update({"Origin": "https://bbs.meizu.cn",
                        "Referer": "https://bbs.meizu.cn/",
                        "Pragma": "no-cache", "Cache-Control": "no-cache"})
        url = URL + "?" + urllib.parse.urlencode({"mod": "signin", "action": "sign"})
        req = urllib.request.Request(url, headers=headers, method="GET")
    else:
        headers.update({"Origin": "https://bbs-act.meizu.cn",
                        "Referer": "https://bbs-act.meizu.cn/2/index.html",
                        "X-Requested-With": "XMLHttpRequest",
                        "Content-Type": "application/x-www-form-urlencoded"})
        payload = urllib.parse.urlencode({"mod": "index", "action": action,
                                          "id": "2"}).encode("ascii")
        req = urllib.request.Request(URL, data=payload, headers=headers, method="POST")
    try:
        # No retries: requests may change server state even if the response is lost.
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError("HTTP 状态未通过")
            raw = response.read(65537)
        if len(raw) > 65536:
            raise TaskError("接口响应超过大小限制")
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise TaskError("接口响应结构异常")
        return result
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError("HTTP 请求失败，状态 " + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络请求失败或超时；不自动重试有副作用的请求") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口响应不是有效 JSON") from None


def code_ok(result):
    code = result.get("code")
    return type(code) is int and code == 200 or code == "200"


def sign_status(result):
    # Upstream does not document the sign success code. Require an explicit
    # sign-specific success message; reject contradictory error codes/messages.
    message = result.get("message")
    if not isinstance(message, str):
        raise TaskError("签到缺少明确业务结果")
    if "code" in result and not code_ok(result):
        raise TaskError("签到业务状态未通过")
    if any(word in message for word in ("失败", "未登录", "请登录", "错误", "异常", "未签到")):
        raise TaskError("签到业务失败")
    if any(word in message for word in ("已经签到", "已签到", "已签过", "已经签过")):
        return "already"
    if "签到成功" in message or "签入成功" in message:
        return "success"
    raise TaskError("签到结果无法确认为成功，请核对接口契约")


def safe_label(value, cookie, public_uid=False):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value)
    # Public UID remains verbatim. Credential matches never enter logs.
    secrets = [cookie] + [part.split("=", 1)[1].strip() for part in cookie.split(";")
                          if "=" in part and part.split("=", 1)[1].strip()]
    for secret in secrets:
        if secret and secret in text:
            return ""
    if re.search(r"[\r\n\x00-\x1f]|cookie|token|session", text, re.I):
        return ""
    if not public_uid and re.search(r"1[3-9]\d{9}", text):
        return ""
    return text


def notify(body, dry):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry:
        log("通知预演：" + body + "；断网模式不调用可能联网的通知模块")
        return "断网预演"
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    commands = []
    # Execute notification separately: hangs/exception/output must not leak data
    # or alter the business exit code. Only the redacted summary is passed.
    commands.append([sys.executable, "-c",
                     "import notify,sys; notify.send(sys.argv[1],sys.argv[2])",
                     TITLE, body])
    for path in paths:
        if path.is_file():
            commands.append([sys.executable, "-c",
                             "import importlib.util,sys; "
                             "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[1]); "
                             "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                             "m.send(sys.argv[2],sys.argv[3])", str(path), TITLE, body])
    js_paths = [p.with_name("sendNotify.js") for p in paths]
    for path in js_paths:
        if path.is_file():
            commands.append(["node", "-e",
                             "Promise.resolve(require(process.argv[1]).sendNotify("
                             "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                             str(path), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "不可用或发送失败（保留业务退出码）"


def account_run(index, cookie, count, dry):
    start = time.monotonic()
    stats = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failure": 0}
    stage_number = 0

    def stage(name, operation):
        nonlocal stage_number
        stage_number += 1
        stats["total"] += 1
        before = time.monotonic()
        log(f"账号 {index} 阶段 {stage_number}：{name} 开始")
        try:
            status, detail = operation()
            stats[status] += 1
            icon = {"success": "✅", "already": "☑️", "skipped": "⏭️"}[status]
            log(f"账号 {index} 阶段 {stage_number}：{icon} {detail}；耗时 {time.monotonic()-before:.2f} 秒")
        except TaskError as exc:
            stats["failure"] += 1
            log(f"账号 {index} 阶段 {stage_number}：❌ {exc}；耗时 {time.monotonic()-before:.2f} 秒")
        except Exception:
            stats["failure"] += 1
            log(f"账号 {index} 阶段 {stage_number}：❌ 未预期处理异常（详情已隐藏）；耗时 {time.monotonic()-before:.2f} 秒")

    def sign():
        if dry:
            return "skipped", "断网预演：校验签到 GET 请求计划，未执行签到"
        status = sign_status(request(cookie, "sign"))
        return status, "今日已签到" if status == "already" else "签到成功"

    def draw():
        if dry:
            return "skipped", "断网预演：校验抽奖 POST 请求计划，未执行抽奖"
        result = request(cookie, "draw")
        if not code_ok(result):
            raise TaskError("抽奖业务状态未通过")
        data = result.get("data")
        if not isinstance(data, dict) or not data.get("award_name"):
            raise TaskError("抽奖缺少奖励结果，不能确认成功")
        award = safe_label(data["award_name"], cookie)
        return "success", "抽奖成功；奖励：" + (award or "名称已脱敏")

    def identity():
        if dry:
            return "skipped", "断网预演：校验公开 UID 查询计划，未发送请求"
        result = request(cookie, "get_user_count")
        if "code" in result and not code_ok(result):
            raise TaskError("账号查询业务状态未通过")
        data = result.get("data")
        if not isinstance(data, dict) or data.get("uid") in (None, "", 0, "0"):
            raise TaskError("账号查询未返回有效公开 UID")
        uid = safe_label(data["uid"], cookie, public_uid=True)
        if not uid:
            raise TaskError("账号身份格式无法安全显示")
        log(f"账号 {index} 官方公开 UID：{uid}")
        for field in ("nickname", "username", "display_name"):
            label = safe_label(data.get(field), cookie)
            if label:
                log(f"账号 {index} 官方 {field}：{label}")
        return "success", "公开账号信息查询成功"

    stage("签到", sign)
    if count == 0:
        stage("抽奖", lambda: ("skipped", "未开启抽奖（MEIZU_DRAW_COUNT=0）"))
    else:
        for number in range(count):
            if number and not dry:
                time.sleep(5)
            stage(f"抽奖 {number+1}/{count}", draw)
    stage("查询账号信息", identity)
    stats["elapsedSeconds"] = round(time.monotonic() - start, 3)
    stats["account"] = index
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
        f"已完成 {stats['already']}，跳过 {stats['skipped']}，失败 {stats['failure']}，"
        f"耗时 {stats['elapsedSeconds']} 秒")
    return stats


def main():
    started = time.monotonic()
    dry = enabled("MEIZU_DRY_RUN")
    cookies = [line.strip() for line in os.getenv("MEIZU_COOKIE", "").splitlines() if line.strip()]
    log("========== " + TITLE + " ==========")
    log("开始时间：" + datetime.datetime.now().isoformat(timespec="seconds"))
    log("运行模式：" + ("断网预演" if dry else "实际执行"))
    log("账号总数：" + str(len(cookies)))
    configuration_error = False
    results = []
    try:
        count = int(os.getenv("MEIZU_DRAW_COUNT", "0"))
        if not 0 <= count <= 100:
            raise ValueError
    except ValueError:
        configuration_error = True
        count = 0
        log("❌ 配置错误：MEIZU_DRAW_COUNT 必须为 0..100 的整数；没有执行账号任务")
    if not cookies:
        configuration_error = True
        log("❌ 配置错误：MEIZU_COOKIE 至少需要一个非空账号行")
    if not configuration_error:
        for index, cookie in enumerate(cookies, 1):
            if "=" not in cookie or any(ord(c) < 32 or ord(c) > 255 for c in cookie):
                log(f"账号 {index} 阶段 1：❌ Cookie 格式错误，未发送请求；耗时 0 秒")
                result = {"account": index, "total": 1, "success": 0, "already": 0,
                          "skipped": 0, "failure": 1, "elapsedSeconds": 0}
                log(f"账号 {index} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 0 秒")
            else:
                result = account_run(index, cookie, count, dry)
            results.append(result)
    failed = sum(r["failure"] > 0 for r in results)
    if configuration_error:
        failed = len(cookies)
    succeeded = len(results) - failed if not configuration_error else 0
    exit_code = 1 if configuration_error or failed else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and succeeded else "failure" if failed else
              "dry-run" if dry else "success")
    body = f"账号总数 {len(cookies)}，成功数 {succeeded}，失败数 {failed}；状态 {status}"
    notification = notify(body, dry)
    log("----------------------------------------")
    log("最终任务统计：" + body + ("；预演成功仅代表配置与流程校验" if dry else ""))
    totals = {key: sum(r[key] for r in results)
              for key in ("total", "success", "already", "skipped", "failure")}
    log(f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，已完成 {totals['already']}，"
        f"跳过 {totals['skipped']}，失败 {totals['failure']}")
    finish = datetime.datetime.now().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - started, 3)
    log(f"总耗时：{elapsed} 秒；完成时间：{finish}；通知状态：{notification}")
    log("最终状态：" + status)
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
               "accountCount": len(cookies), "succeeded": succeeded, "failed": failed,
               "configurationError": configuration_error, "accounts": results,
               "stages": totals, "elapsedSeconds": elapsed, "finishTime": finish,
               "notification": notification, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
