#!/usr/bin/env python3
# name: 华润通999答题
# cron: 49 1 1 1 1
# 来源：Cat-zaizai/ZaiZaiCat-Checkin，script/huaruntong/999/main.py、api.py
# 上游许可：MIT；保留原作者归属。
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
"""HRT999_ACCOUNTS：每行一个 JSON 对象，含 mobile、token，可选 user_agent、account_name。
从本人登录华润通999答题页面的请求中获取 token 头与 customdata.mobile；
user_agent 可使用同一请求的 User-Agent。请勿分享抓包数据。
HRT999_DRY_RUN=1：使用本地题目预演，禁止 HTTP 和通知外发。
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
        _ql_notify_identities = ('8ea0312febc74515', 'scripts/999.py', '999.py', '999')
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
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = "华润通999答题"
BASE = "https://api4.jiankangyouyi.com/base-data/v1/api/gadgets"
DEFAULT_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26405f0) XWEB/13910'
DISABLED = {"0", "false", "no", "off"}
SECRETS = []


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def safe(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已脱敏]")
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[手机号已脱敏]", text)
    return " ".join(text.split())


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 避免重定向向其他域名泄露凭据，也避免重复提交。
        return None


class QuizAPI:
    def __init__(self, account, dry):
        self.account, self.dry = account, dry

    def request(self, route, payload):
        if self.dry:
            if route.startswith("business-"):
                return {"resultCode": "0", "data": {"knowledgeQuestionData": {
                    "questionId": "local-question", "question": {
                        "questionContents": ["本地预演：选择正确选项"], "options": [
                            {"optionCode": "A", "optionContents": ["正确"], "right": True},
                            {"optionCode": "B", "optionContents": ["错误"], "right": False}]}}}}
            return {"resultCode": "0"}
        headers = {
            "User-Agent": self.account.get("user_agent") or DEFAULT_UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "customdata": json.dumps({"mobile": self.account["mobile"], "point": 5,
                                      "entrance": "huarun-sj-mryt"}, separators=(",", ":")),
            "token": self.account["token"], "origin": "https://apps.jiankangyouyi.com",
            "referer": "https://apps.jiankangyouyi.com/", "accept-language": "zh-CN,zh;q=0.9"}
        req = Request(BASE + "/" + route + "?bizType=160107",
                      data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with build_opener(NoRedirect()).open(req, timeout=15) as response:
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise TaskError("响应超过大小限制")
                result = json.loads(raw)
        except TaskError:
            raise
        except Exception:
            raise TaskError("接口请求失败：网络、HTTP 或 JSON 异常；未自动重试提交") from None
        if not isinstance(result, dict):
            raise TaskError("接口响应结构异常")
        return result

    def get_question(self):
        return self.request("business-knowledge-challenges", {
            "userId": self.account["mobile"], "strategy": "1",
            "customerParams": ["huarun-sanjiu-prointsRewardScore"],
            "customers": ["050205"], "configId": ""})

    def submit_answer(self, question_id, codes):
        return self.request("knowledge-challenges/user-choice", {
            "userId": self.account["mobile"], "questionId": question_id,
            "userOptionCodes": codes, "customerParams": ["huarun-sanjiu-prointsRewardScore"],
            "mobile": self.account["mobile"], "configId": ""})


def require_success(result):
    if result.get("resultCode") != "0":
        # 服务端错误消息可能含凭据；不打印未知原文。
        raise TaskError("接口未返回业务成功码 resultCode=0")


def identity(result):
    data = result.get("data")
    if isinstance(data, dict):
        for obj in (data, data.get("userInfo"), data.get("accountInfo")):
            if isinstance(obj, dict):
                for key in ("nickname", "nickName", "username", "displayName", "publicUid"):
                    if isinstance(obj.get(key), (str, int)) and obj[key] != "":
                        log("账号身份：" + safe(obj[key]))


def process_account(account, index, dry):
    stats = {"account": index, "total": 3, "success": 0, "alreadyComplete": 0,
             "skipped": 0, "failed": 0}
    started = time.monotonic()
    stage_start = started
    stage = 1
    try:
        if not isinstance(account, dict):
            raise TaskError("账号行必须是 JSON 对象")
        if isinstance(account.get("account_name"), str) and account["account_name"]:
            log(f"账号 {index} 备注：{safe(account['account_name'])}")
        for key in ("mobile", "token"):
            if not isinstance(account.get(key), str) or not account[key].strip():
                raise TaskError("账号必须包含非空字符串 mobile 和 token")
            if any(c in account[key] for c in "\r\n"):
                raise TaskError("凭据不能包含换行")
        if not re.fullmatch(r"1\d{10}", account["mobile"]):
            raise TaskError("mobile 必须为十一位中国大陆手机号")
        if account.get("user_agent") is not None and (
                not isinstance(account["user_agent"], str) or
                any(c in account["user_agent"] for c in "\r\n")):
            raise TaskError("user_agent 必须是无换行字符串")
        api = QuizAPI(account, dry)
        log(f"账号 {index} · 阶段 1/3 获取题目")
        result = api.get_question()
        require_success(result)
        identity(result)
        data = result.get("data", {}).get("knowledgeQuestionData")
        if not isinstance(data, dict) or not data.get("questionId"):
            raise TaskError("题目数据或 questionId 缺失")
        stats["success"] += 1
        log(f"✅ 获取题目成功，耗时 {time.monotonic()-stage_start:.2f} 秒")
        stage, stage_start = 2, time.monotonic()
        log(f"账号 {index} · 阶段 2/3 展示题目并提取答案")
        question = data.get("question")
        if not isinstance(question, dict) or not isinstance(question.get("options"), list):
            raise TaskError("题目选项结构异常")
        contents = question.get("questionContents")
        if isinstance(contents, list) and contents:
            log("题目：" + safe(contents[0]))
        codes = []
        for option in question["options"]:
            if not isinstance(option, dict):
                raise TaskError("选项结构异常")
            code = option.get("optionCode")
            right = option.get("right") is True or option.get("right") == 1
            text = option.get("optionContents")
            log(f"选项 {safe(code)}：{safe(text[0]) if isinstance(text, list) and text else ''}" +
                (" ✅" if right else ""))
            if right:
                if not isinstance(code, str) or not code:
                    raise TaskError("正确选项缺少有效 optionCode")
                codes.append(code)
        if not codes:
            raise TaskError("未找到接口明确标记的正确答案，停止提交")
        log("正确答案：" + safe(", ".join(codes)))
        stats["success"] += 1
        log(f"✅ 答案提取成功，耗时 {time.monotonic()-stage_start:.2f} 秒")
        stage, stage_start = 3, time.monotonic()
        log(f"账号 {index} · 阶段 3/3 提交答案" + ("（本地模拟）" if dry else ""))
        result = api.submit_answer(data["questionId"], codes)
        require_success(result)
        identity(result)
        stats["success"] += 1
        log(f"✅ {'DRY_RUN_OK 本地预演成功' if dry else '答题成功'}，耗时 {time.monotonic()-stage_start:.2f} 秒")
    except Exception as exc:
        stats["failed"] = 1
        stats["skipped"] = 3 - stage
        log(f"❌ 账号 {index} 阶段 {stage}/3：" +
            (str(exc) if isinstance(exc, TaskError) else "数据结构或参数异常") +
            f"，耗时 {time.monotonic()-stage_start:.2f} 秒")
    stats["durationSeconds"] = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 3，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {stats['durationSeconds']} 秒")
    return stats


def notify(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in DISABLED:
        return "已关闭"
    if dry:
        return "断网预演：通知摘要已在本地输出，未外发"
    # 通知插件为可选青龙集成，不属于业务运行依赖。
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            module = None
        if module is not None and callable(getattr(module, "send", None)):
            module.send(TITLE, body)
            return "已发送"
        dirs = [os.getenv("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts"]
        for directory in dirs:
            if not directory:
                continue
            path = Path(directory) / "notify.py"
            if path.is_file():
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(TITLE, body)
                return "已发送"
            path = Path(directory) / "sendNotify.js"
            if path.is_file():
                proc = subprocess.run(["node", "-e",
                    "require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]).catch(()=>process.exit(1))",
                    str(path), TITLE, body], capture_output=True, timeout=30)
                return "已发送" if proc.returncode == 0 else "通知失败，保留业务退出码"
    except Exception:
        return "通知失败，保留业务退出码"
    return "通知模块不可用，保留业务退出码"


def main():
    started = time.monotonic()
    dry = os.getenv("HRT999_DRY_RUN", "0").lower() in {"1", "true", "yes", "on"}
    lines = [line for line in os.getenv("HRT999_ACCOUNTS", "").splitlines() if line.strip()]
    log("========== 华润通999答题 ==========")
    log(f"开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{'断网预演' if dry else '正式执行'}；账号数：{len(lines)}")
    accounts = []
    for line in lines:
        try:
            account = json.loads(line)
        except (ValueError, TypeError):
            account = None
        accounts.append(account)
        if isinstance(account, dict):
            for key in ("mobile", "token", "user_agent"):
                if isinstance(account.get(key), str):
                    SECRETS.append(account[key])
    if not lines:
        log("❌ 配置错误：HRT999_ACCOUNTS 未设置或没有非空账号行")
    results = [process_account(account, i, dry) for i, account in enumerate(accounts, 1)]
    success = sum(r["failed"] == 0 for r in results)
    failed = len(results) - success
    code = 0 if results and not failed else 1
    status = ("configuration-error" if not results else "partial-failure" if failed and success
              else "failure" if failed else "dry-run" if dry else "success")
    body = f"状态：{status}；账号总数：{len(results)}；成功数：{success}；失败数：{failed}"
    log(body)
    notification = notify(body, dry)
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
               "accounts": len(results), "success": success, "failed": failed,
               "configurationErrors": int(not results), "results": results,
               "durationSeconds": round(time.monotonic()-started, 2),
               "finishTime": datetime.now().isoformat(timespec="seconds"),
               "notification": notification, "exitCode": code}
    log("--------------------------------------------------")
    log(f"子任务统计：成功 {sum(r['success'] for r in results)}，已完成 0，"
        f"跳过 {sum(r['skipped'] for r in results)}，失败 {sum(r['failed'] for r in results)}")
    log(f"通知状态：{notification}；总耗时：{summary['durationSeconds']} 秒")
    log(f"完成时间：{summary['finishTime']}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
