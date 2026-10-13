# name: 华润通文体未来荟签到
# cron: 1 1 1 1 1
# 来源: Cat-zaizai/ZaiZaiCat-Checkin
# 原文件: script/huaruntong/wentiweilaihui/main.py 和 api.py
# 许可: MIT（保留上游署名；输入文件未包含其他版权声明）
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""独立签到及积分查询。WENTIWEILAIHUI_ACCOUNTS 每行一个裸 JWT 或 Wechat JWT。

也可每行一个 JSON 对象，兼容 token、mobile、account_name、user_agent 字段。
在微信文体未来荟小程序登录后，从本人请求的 Authorization 获取 token；
手机号仅作兼容输入，不发送、不输出。无需原仓库的 token.json 或 api.py。
WENTIWEILAIHUI_DRY_RUN=1 完全离线演练，包含通知发送的离线模拟。
原定时表达式保留；其不是每日表达式，用户可在青龙按需调整任务定时。
"""

import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from datetime import datetime
from urllib import error, request

TITLE = "华润通文体未来荟签到"
BASE = "https://wlhmobile.crland.com.cn"
APP_ID = "wx020209beec4251e0"
PROJECT = "3a59e62a07f811f1bec0aeefcf2e061a"
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 "
    "Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) "
    "NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF "
    "MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf264171e) XWEB/18788"
)
FALSE_VALUES = {"0", "false", "no", "off"}


class TaskError(Exception):
    """仅容纳固定脱敏错误消息。"""


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def normalize_token(token):
    value = token.strip()
    if value.lower().startswith("wechat "):
        value = value[7:].strip()
    if not value or any(char.isspace() for char in value):
        raise TaskError("凭据为空或包含非法空白")
    return value


def parse_account(line):
    if line.startswith("{"):
        try:
            account = json.loads(line)
        except ValueError:
            raise TaskError("账号 JSON 格式错误") from None
        if not isinstance(account, dict) or not isinstance(account.get("token"), str):
            raise TaskError("账号缺少字符串 token")
    else:
        account = {"token": line}
    account["token"] = normalize_token(account["token"])
    ua = account.get("user_agent") or DEFAULT_UA
    if not isinstance(ua, str) or "\n" in ua or "\r" in ua:
        raise TaskError("User-Agent 格式错误")
    account["user_agent"] = ua
    return account


def extract_openid(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError()
        part = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(part).decode("utf-8"))
        value = payload.get("openid") if isinstance(payload, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError()
        return value.strip()
    except (ValueError, UnicodeError):
        raise TaskError("Token 载荷无效或缺少 openid，无法查询积分") from None


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, account):
        context = ssl.create_default_context()
        # 与参考 API 一致，仅允许旧服务连接，始终验证证书；不自动降低 TLS。
        context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
        self.opener = request.build_opener(request.HTTPSHandler(context=context), NoRedirect())
        self.headers = {
            "User-Agent": account["user_agent"], "Accept": "*/*",
            "Content-Type": "application/json", "Authorization": "Wechat " + account["token"],
            "appId": APP_ID, "projectUuid": PROJECT, "xweb_xhr": "1",
            "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty", "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"https://servicewechat.com/{APP_ID}/64/page-frame.html",
        }

    def post(self, path, payload):
        req = request.Request(BASE + path, data=json.dumps(payload).encode(),
                              headers=self.headers, method="POST")
        try:
            with self.opener.open(req, timeout=10) as response:
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError("接口响应过大")
            data = json.loads(raw)
        except error.HTTPError as exc:
            raise TaskError(f"接口 HTTP 错误 {exc.code}") from None
        except (error.URLError, TimeoutError, OSError):
            raise TaskError("网络或 TLS 请求失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口 JSON 响应无效") from None
        if not isinstance(data, dict) or type(data.get("code")) is not int or data["code"] != 200:
            raise TaskError("接口未返回业务成功码 200")
        return data.get("result")


def show_identity(result, token):
    if not isinstance(result, dict):
        return
    for key in ("nickname", "nickName", "username", "displayName", "uid"):
        value = result.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            # 只输出官方身份字段；异常字段若包含凭据或手机号则拒绝展示。
            if token in text or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                continue
            log(f"官方账号 {key}: {json.dumps(text, ensure_ascii=False)}")


def run_account(index, line, dry):
    begin = time.monotonic()
    counts = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    log(f"账号 {index} 开始")
    try:
        account = parse_account(line)
    except TaskError as exc:
        log(f"❌ 配置错误：{exc}")
        counts["failed"] = 2
        counts["elapsedSeconds"] = round(time.monotonic() - begin, 3)
        log(f"账号 {index} 统计: {json.dumps(counts, ensure_ascii=False)}")
        return {"account": index, "success": False, "configurationError": True, "tasks": counts}
    client = None if dry else Client(account)
    for stage in (1, 2):
        stage_begin = time.monotonic()
        log(f"账号 {index} 阶段 {stage}/2：{'签到记录查询及每日签到' if stage == 1 else '会员积分查询'}")
        try:
            if stage == 2:
                openid = extract_openid(account["token"])
            if dry:
                counts["skipped"] += 1
                log("⏭️ 离线预演通过，参数结构与任务阶段已核对，未发送请求")
            elif stage == 1:
                record = client.post("/marketing/client/task/sign-in/record", {"projectUuid": PROJECT})
                if not isinstance(record, dict) or type(record.get("isSignedToday")) is not bool:
                    raise TaskError("签到记录缺少布尔型 isSignedToday，禁止盲目签到")
                show_identity(record, account["token"])
                log("✅ 签到记录查询成功")
                if record["isSignedToday"]:
                    counts["alreadyComplete"] += 1
                    log("☑️ 今日已签到")
                else:
                    signed = client.post("/marketing/client/task/daily/sign-in", {"projectUuid": PROJECT})
                    show_identity(signed, account["token"])
                    counts["success"] += 1
                    log("✅ 签到成功（业务码 200）")
            else:
                member = client.post("/member/client/detail", {"projectUuid": PROJECT, "openId": openid})
                if not isinstance(member, dict):
                    raise TaskError("会员详情缺少 result 对象")
                points = member.get("points")
                if isinstance(points, bool) or not isinstance(points, (int, float, str)):
                    raise TaskError("会员详情缺少有效积分字段")
                if not re.fullmatch(r"\d+(?:\.\d+)?", str(points)):
                    raise TaskError("积分字段格式异常")
                show_identity(member, account["token"])
                counts["success"] += 1
                log(f"✅ 积分查询成功，当前积分: {points}")
        except TaskError as exc:
            counts["failed"] += 1
            log(f"❌ {exc}")
        except Exception:
            counts["failed"] += 1
            log("❌ 处理失败（详情已脱敏）")
        log(f"账号 {index} 阶段 {stage}/2 耗时 {time.monotonic() - stage_begin:.3f} 秒")
    counts["elapsedSeconds"] = round(time.monotonic() - begin, 3)
    log(f"账号 {index} 统计: {json.dumps(counts, ensure_ascii=False)}")
    return {"account": index, "success": counts["failed"] == 0, "tasks": counts}


def notify_summary(body, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in FALSE_VALUES:
        return "全局开关已关闭"
    if dry:
        log("⏭️ 离线模拟通知：" + body)
        return "离线模拟，未联网"
    # 仅通知适配器可选使用青龙文件；业务脚本不依赖其存在。
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(str(Path(directory) / "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    adapter = next((path for path in paths if Path(path).is_file()), None)
    try:
        if adapter is None and importlib.util.find_spec("notify") is None:
            js_paths = ([str(Path(directory) / "sendNotify.js")] if directory else [])
            js_paths.extend(["/ql/data/scripts/sendNotify.js", "/ql/scripts/sendNotify.js"])
            js_adapter = next((path for path in js_paths if Path(path).is_file()), None)
            if js_adapter is None:
                return "通知不可用（未找到青龙通知适配器），业务退出码保留"
            js_worker = (
                "const fs=require('fs');const [p,title,body]=JSON.parse(fs.readFileSync(0,'utf8'));"
                "Promise.resolve().then(()=>require(p).sendNotify(title,body))"
                ".catch(()=>{process.exitCode=1;});"
            )
            completed = subprocess.run(["node", "-e", js_worker],
                                       input=json.dumps([js_adapter, TITLE, body]), text=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            return "通知已发送" if completed.returncode == 0 else "通知失败，业务退出码保留"
        worker = (
            "import importlib.util,json,sys; p,title,body=json.load(sys.stdin); "
            "spec=importlib.util.spec_from_file_location('ql_notify',p) if p else None; "
            "m=importlib.util.module_from_spec(spec) if spec else __import__('notify'); "
            "spec.loader.exec_module(m) if spec else None; m.send(title,body)"
        )
        completed = subprocess.run([sys.executable, "-c", worker],
                                   input=json.dumps([adapter, TITLE, body]), text=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return "通知已发送" if completed.returncode == 0 else "通知失败，业务退出码保留"
    except Exception:
        return "通知失败或超时，业务退出码保留"


def main():
    start = time.monotonic()
    dry = os.getenv("WENTIWEILAIHUI_DRY_RUN", "0").lower() not in FALSE_VALUES
    log("=" * 50)
    log(TITLE)
    log(f"开始时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("运行模式: " + ("完全离线预演" if dry else "正式执行"))
    lines = [line.strip() for line in os.getenv("WENTIWEILAIHUI_ACCOUNTS", "").splitlines() if line.strip()]
    log(f"账号总数: {len(lines)}")
    results = []
    if not lines:
        log("❌ 配置错误：必须设置 WENTIWEILAIHUI_ACCOUNTS，每行一个账号")
    for index, line in enumerate(lines, 1):
        try:
            results.append(run_account(index, line, dry))
        except Exception:
            log(f"❌ 账号 {index} 运行异常（详情已脱敏），继续其他账号")
            results.append({"account": index, "success": False,
                            "tasks": {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 2}})
    success = sum(result["success"] for result in results)
    failed = len(lines) - success
    exit_code = 0 if lines and not failed else 1
    status = "configuration-error" if not lines or any(r.get("configurationError") for r in results) else (
        "partial-failure" if failed and success else "failure" if failed else "dry-run" if dry else "success")
    body = f"模式：{'离线预演' if dry else '正式'}；账号总数 {len(lines)}，成功 {success}，失败 {failed}；状态 {status}"
    notification = notify_summary(body, dry)
    task_counts = {key: sum(r["tasks"][key] for r in results)
                   for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    summary = {"status": status, "dryRun": dry, "accounts": len(lines), "success": success,
               "failed": failed, "tasks": task_counts, "results": results, "notification": notification,
               "elapsedSeconds": round(time.monotonic() - start, 3), "exitCode": exit_code}
    log("-" * 50)
    log(body)
    log("子任务统计: " + json.dumps(task_counts, ensure_ascii=False))
    log(f"总耗时: {summary['elapsedSeconds']:.3f} 秒")
    log(f"完成时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("通知状态: " + notification)
    log(f"最终状态: {status}，退出码 {exit_code}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
