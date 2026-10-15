# -*- coding: utf-8 -*-
# name: Fa米家每日签到与发米粒查询
# cron: 47 1 * * *
# 上游：OreosLab/checkinpanel，ck_fmapp.py（MIT）
# 保留上游任务标识：new Env('Fa米家每日签到与发米粒查询');
"""Fa米家每日签到、昵称与发米粒查询。

FMAPP：每个非空行为一个 JSON 对象，包含 token、cookie、blackbox、device_id。
在自己的已登录 Fa米家 App 请求中获取这些请求头；切勿分享抓包内容。
可选字段 fmversion、os、useragent 默认分别为 2.2.3、ios、Fa。
FMAPP_DRY_RUN=1 为完全断网预演；QINGLONG_NOTIFY=0 关闭通知。

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
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

TITLE = "Fa米家"
BASE = "https://fmapp.chinafamilymart.com.cn"
STAGES = (
    ("签到", "/api/app/market/member/signin/sign", None),
    ("账号信息", "/api/app/member/info", None),
    ("发米粒余额", "/api/app/member/v1/mili/service/detail", {"pageSize": 10, "pageNo": 1}),
)
REQUIRED = ("token", "cookie", "blackbox", "device_id")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() not in ("", "0", "false", "no", "off")


def parse_account(line):
    account = json.loads(line)
    if not isinstance(account, dict):
        raise ValueError("账号必须是 JSON 对象")
    for key in REQUIRED:
        value = account.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"缺少非空字符串字段 {key}")
    for key in (*REQUIRED, "fmversion", "os", "useragent"):
        if key in account and (not isinstance(account[key], str) or "\r" in account[key] or "\n" in account[key]):
            raise ValueError(f"字段 {key} 必须为不含换行的字符串")
    return account


def headers_for(account):
    return {
        "Accept": "*/*",
        "Accept-Language": "zh-Hans;q=1.0",
        "Content-Type": "application/json",
        "loginChannel": "app",
        "token": account["token"],
        "fmVersion": account.get("fmversion", "2.2.3"),
        "deviceId": account["device_id"],
        "User-Agent": account.get("useragent", "Fa"),
        "os": account.get("os", "ios"),
        "cookie": account["cookie"],
        "blackBox": account["blackbox"],
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 禁止把凭据转发到重定向目标，也不重试可能已完成的签到。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(path, headers, payload):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method="POST")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态异常")
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("响应超过大小限制")
    result = json.loads(raw)
    if not isinstance(result, dict) or str(result.get("code")) != "200":
        raise ValueError("业务状态未确认成功，请检查登录凭据或服务状态")
    data = result.get("data")
    if not isinstance(data, dict):
        raise ValueError("响应数据结构异常")
    return data


def scalar(data, key):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or str(value).strip() == "":
        raise ValueError(f"响应缺少有效的 {key} 字段")
    return value


def number(data, key):
    value = scalar(data, key)
    # 只输出数字字段，不输出服务端任意文本或错误消息。
    if not str(value).isascii() or not str(value).isdigit():
        raise ValueError(f"响应的 {key} 字段不是非负整数")
    return value


def stage_result(index, data, account):
    if index == 1:
        return (f"再坚持 {number(data, 'nextDay')} 天即可获得 {number(data, 'nextNumber')} 个发米粒；"
                f"签到 {number(data, 'lastDay')} 天可获得 {number(data, 'lastNumber')} 个发米粒")
    if index == 2:
        nickname = scalar(data, "nickName")
        if not isinstance(nickname, str):
            raise ValueError("昵称字段类型异常")
        # 官方昵称原样显示；若异常地夹带本账号凭据则拒绝输出。
        if any(account[key] in nickname for key in REQUIRED):
            raise ValueError("账号身份字段包含敏感数据，已禁止输出")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in nickname):
            raise ValueError("昵称字段包含控制字符")
        return f"帐号信息: {nickname}"
    return f"米粒数量: {number(data, 'miliNum')}"


def notify(summary, dry_run):
    if not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry_run:
        # 通知发送器可能联网；预演仅模拟发送，保证断网契约。
        log("⏭️ 通知预演：" + summary)
        return "预演完成（未联网）"
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "")
    candidates = ([Path(directory) / "notify.py"] if directory else [])
    local_spec = None
    try:
        local_spec = importlib.util.find_spec("notify")
    except (ImportError, ValueError):
        pass
    if local_spec and local_spec.origin:
        candidates.append(Path(local_spec.origin))
    candidates.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    # 子进程隔离发送器的打印、异常和退出；凭据不传入通知子进程。
    child_env = {k: v for k, v in os.environ.items() if k != "FMAPP"}
    py_code = (
        "import importlib.util,sys; "
        "sys.path.insert(0,sys.argv[1]); "
        "s=importlib.util.spec_from_file_location('ql_notify',sys.argv[2]); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.send(sys.argv[3],sys.argv[4])"
    )
    for path in candidates:
        if path.is_file():
            try:
                result = subprocess.run(
                    [sys.executable, "-c", py_code, str(path.parent), str(path), TITLE, summary],
                    env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                )
                if result.returncode == 0:
                    return "发送器执行完成"
            except (OSError, subprocess.TimeoutExpired):
                pass
    js_candidates = ([Path(directory) / "sendNotify.js"] if directory else [])
    js_candidates.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
    for path in js_candidates:
        if path.is_file():
            try:
                code = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
                result = subprocess.run(
                    ["node", "-e", code, str(path), TITLE, summary], env=child_env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                )
                if result.returncode == 0:
                    return "发送器执行完成"
            except (OSError, subprocess.TimeoutExpired):
                pass
    log("⚠️ 通知不可用或发送失败，保留业务退出码")
    return "不可用或失败"


def main():
    started = time.monotonic()
    dry_run = enabled("FMAPP_DRY_RUN")
    lines = [line.strip() for line in os.getenv("FMAPP", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{now()}；模式：{'断网预演' if dry_run else '正式运行'}；账号数：{len(lines)}")
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    results = []
    config_error = not lines
    if not lines:
        log("❌ 配置错误：请设置 FMAPP，每个非空行填写一个账号 JSON 对象")
    for account_index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        counts = {"total": 3, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        log(f"------ 账号 {account_index} ------")
        try:
            account = parse_account(line)
        except (ValueError, TypeError):
            config_error = True
            counts["failed"] = 1
            counts["skipped"] = 2
            log("❌ 账号配置无效：核对 JSON 和 token、cookie、blackbox、device_id 字符串字段")
            for index, (label, _, _) in enumerate(STAGES, 1):
                log(f"阶段 {index}/3 {label}：{'❌ 配置失败' if index == 1 else '⏭️ 配置无效，跳过'}；耗时 0.00 秒")
        else:
            headers = headers_for(account)
            for index, (label, path, payload) in enumerate(STAGES, 1):
                stage_start = time.monotonic()
                log(f"阶段 {index}/3 {label}：开始")
                try:
                    if dry_run:
                        counts["skipped"] += 1
                        message = "⏭️ 预演通过：参数和请求结构已检查，未发送 HTTP 请求"
                    else:
                        detail = stage_result(index, post(path, headers, payload), account)
                        counts["success"] += 1
                        message = "✅ " + detail
                except urllib.error.HTTPError:
                    counts["failed"] += 1
                    message = "❌ HTTP 请求失败，请检查凭据或服务状态"
                except (urllib.error.URLError, TimeoutError, OSError):
                    counts["failed"] += 1
                    message = "❌ 网络连接失败或超时"
                except (ValueError, TypeError, KeyError):
                    counts["failed"] += 1
                    message = "❌ 业务成功或响应字段未通过核验，请检查凭据或接口变化"
                except Exception:
                    counts["failed"] += 1
                    message = "❌ 请求处理异常，已隐藏异常详情"
                log(f"阶段 {index}/3 {label}：{message}；耗时 {time.monotonic() - stage_start:.2f} 秒")
        for key in totals:
            totals[key] += counts[key]
        status = "failure" if counts["failed"] else ("dry-run" if dry_run else "success")
        results.append({"account": account_index, "status": status, **counts})
        log(f"账号 {account_index} 统计：总任务 {counts['total']}，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic() - account_start:.2f} 秒")
    failed = sum(item["status"] == "failure" for item in results)
    successful = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else
              "partial-failure" if failed and successful else
              "failure" if failed else "dry-run" if dry_run else "success")
    body = f"账号总数 {len(lines)}，成功数 {successful}，失败数 {failed}；子任务成功 {totals['success']}，失败 {totals['failed']}，跳过 {totals['skipped']}；状态 {status}"
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "不可用或失败"
        log("⚠️ 通知异常，保留业务退出码")
    finished = now()
    log("----------------------------------------")
    log(body)
    log(f"子任务总数 {totals['total']}，已完成 {totals['alreadyComplete']}；总耗时 {time.monotonic() - started:.2f} 秒")
    log(f"完成时间：{finished}；通知状态：{notification}；最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps({
        "task": TITLE, "mode": "dry-run" if dry_run else "live", "status": status,
        "accounts": len(lines), "success": successful, "failed": failed,
        "tasks": totals, "accountResults": results, "notification": notification,
        "finishedAt": finished, "exitCode": exit_code,
    }, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
