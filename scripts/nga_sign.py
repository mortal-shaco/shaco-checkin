#!/usr/bin/env python3
# name: NGA社区 每日签到
# cron: 3 0 * * *
"""NGA社区每日签到，Python 3 标准库独立维护版。

来源：yongyeym/AutoSign_QingLong / nga_sign.py
原提交：f13a88e488c2d396e24cce8e9b6e27eefcbccad6；许可证：MIT。
原文件未包含作者版权声明；保留原项目归属，不主张原代码版权。

NGA_ACCOUNTS：每个非空行一个 JSON 对象，键为 uid、token、checksum，
均为字符串。不要用 & 或 @ 分隔账号。token 对应原 nga_cookie 的
access_token 值，不是完整 Cookie；checksum 对应 __ngaClientChecksum。
在自己的 NGA iOS 客户端登录后，使用自己控制的 HTTPS 抓包工具查看
ngabbs.com/nuke.php 的签到请求：从表单读取 access_uid、access_token、
__ngaClientChecksum。三个值必须属于同一账号和客户端请求。请勿公开抓包。
兼容单账号 nga_uid、nga_cookie、nga_client_checksum；NGA_ACCOUNTS 优先。
不读取私有 ini 配置。每天 00:03 执行一次，仅进行签到，不发布任何内容。
NGA_DRY_RUN=1：完全断网预演，通知也仅模拟，不能视为真实签到成功。
QINGLONG_NOTIFY 默认 1；0/false/no/off 禁用。QINGLONG_NOTIFY_DIR 可指定
青龙现有通知模块目录；通知故障不会覆盖签到退出码。请求超时 15 秒，
不自动重试有副作用的请求，不自动安装或下载任何组件。

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
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

TITLE = "NGA社区 每日签到"
URL = "https://ngabbs.com/nuke.php"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NGA_skull/10.1.36")
DISABLED = {"0", "false", "no", "off"}
SECRET_VALUES = []


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def load_accounts():
    raw = os.environ.get("NGA_ACCOUNTS", "")
    if raw.strip():
        entries = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict):
                    item = None
            except (ValueError, TypeError):
                item = None
            entries.append(item)
        return entries
    legacy = {"uid": os.environ.get("nga_uid", ""),
              "token": os.environ.get("nga_cookie", ""),
              "checksum": os.environ.get("nga_client_checksum", "")}
    return [legacy] if any(legacy.values()) else []


def validate(account):
    if not isinstance(account, dict):
        return "账号行必须为 JSON 对象"
    for field in ("uid", "token", "checksum"):
        value = account.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"缺少或格式错误：{field}"
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            return f"字段含控制字符：{field}"
    if not re.fullmatch(r"[0-9]+", account["uid"]):
        return "uid 必须为数字字符串"
    if ";" in account["token"]:
        return "token 应为 access_token 的值，不能填写完整 Cookie"
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 不允许凭据经重定向发送至其他地址。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_sign(account):
    boundary = "----WebKitFormBoundary" + secrets.token_hex(16)
    device = "iOS;" + hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    user_info = "%25" + secrets.token_hex(16)
    fields = {"__lib": "check_in", "__output": "11", "app_id": "1100",
              "device": device, "__act": "check_in", "access_uid": account["uid"],
              "access_token": account["token"], "__ngaClientChecksum": account["checksum"],
              "__inchst": "UTF-8"}
    body = b"".join((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f'\r\n\r\n{value}\r\n').encode("utf-8")
                    for key, value in fields.items())
    body += f"--{boundary}--\r\n".encode("ascii")
    cookie = (f"ngacn0comInfoCheckTime={int(time.time())}; "
              f"ngacn0comUserInfo={user_info}; "
              f"ngacn0comUserInfoCheck={hashlib.md5(user_info.encode()).hexdigest()}; "
              f"bbsmisccookies=%7B%7D; access_token={account['token']}; "
              f"access_uid={account['uid']}")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "User-Agent": UA, "X-USER-AGENT": UA, "Accept": "application/json",
        "Accept-Encoding": "identity", "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Origin": "https://ngabbs.com", "Referer": "https://ngabbs.com/misc/mission/mission.php",
        "Cookie": cookie})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError("HTTP 状态异常")
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("响应过大")
        return json.loads(raw.decode("utf-8-sig"))


def interpret(payload):
    if not isinstance(payload, dict):
        return "failure", "响应结构异常", None
    error = payload.get("error")
    if error is not None:
        message = error[0] if isinstance(error, list) and error else error
        if isinstance(message, str):
            if "你今天已经签到了" in message:
                return "already", "今天已经签到过，无需签到", None
            if "你必须先登录论坛" in message:
                return "failure", "登录失效，请更新 token", None
            if "CLIENT ERROR" in message:
                return "failure", "客户端校验失败，请更新 iOS 客户端 checksum", None
        return "failure", "业务错误（已隐藏原始响应）", None
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], str) and "签到成功" in data[0]:
        if len(data) < 2 or not isinstance(data[1], dict):
            return "failure", "签到响应缺少统计字段，无法核验", None
        stats = data[1]
        for key in ("sum", "continued"):
            val = stats.get(key)
            if isinstance(val, bool) or not re.fullmatch(r"[0-9]{1,9}", str(val)):
                return "failure", "签到统计字段异常，无法核验", None
        return "success", f"今日签到成功；连续 {stats['continued']} 天，累计 {stats['sum']} 天", stats
    return "failure", "未收到明确签到成功状态（已隐藏原始响应）", None


def public_identity(payload, stats):
    containers = [stats, payload]
    if isinstance(payload, dict):
        containers += [payload.get("user"), payload.get("userinfo")]
        data = payload.get("data")
        if isinstance(data, list):
            containers += [item for item in data if isinstance(item, dict)]
    for item in containers:
        if not isinstance(item, dict):
            continue
        for key in ("nickname", "username", "display_name", "uid"):
            value = item.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if not value or len(value) > 120 or any(ord(c) < 32 for c in value):
                continue
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
                continue
            if any(secret and secret in value for secret in SECRET_VALUES):
                continue
            return value
    return None


def notify(summary, dry_run):
    if os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        return "已关闭"
    if dry_run:
        log("⏭️ 断网预演：模拟通知投递，不加载通知模块")
        return "预演模拟"
    body = (f"状态：{summary['status']}；账号总数 {summary['accounts']}，"
            f"成功 {summary['success']}，失败 {summary['failed']}；"
            f"签到成功 {summary['tasks']['success']}，已完成 {summary['tasks']['already']}，"
            f"跳过 {summary['tasks']['skipped']}。")
    # 在受限子进程中调用青龙通知；屏蔽模块输出，避免凭据或原始响应进入日志。
    runner = '''import importlib.util, sys
from pathlib import Path
try:
    import notify
    send = notify.send
except ImportError:
    send = None
if send is None:
    for folder in sys.argv[3:]:
        path = Path(folder) / 'notify.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('ql_notification', str(path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = mod.send
            break
if send is None:
    sys.exit(3)
send(sys.argv[1], sys.argv[2])
'''
    folders = [os.environ.get("QINGLONG_NOTIFY_DIR", ""),
               "/ql/data/scripts", "/ql/scripts"]
    folders = [folder for folder in folders if folder]
    try:
        result = subprocess.run([sys.executable, "-c", runner, TITLE, body, *folders],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode == 0:
            return "已发送"
    except (OSError, subprocess.TimeoutExpired):
        pass
    for folder in folders:
        path = Path(folder) / "sendNotify.js"
        if not path.is_file():
            continue
        try:
            result = subprocess.run([
                "node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(()=>process.exit(1))",
                str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if result.returncode == 0:
                return "已发送"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 通知模块不可用或投递失败；保留业务退出码")
    return "不可用或失败"


def main():
    begin = time.monotonic()
    started = stamp()
    dry_run = os.environ.get("NGA_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    accounts = load_accounts()
    for account in accounts:
        if isinstance(account, dict):
            for key in ("token", "checksum"):
                value = account.get(key)
                if isinstance(value, str) and value:
                    SECRET_VALUES.append(value)
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{started}；模式：{'断网预演' if dry_run else '实际签到'}；账号数：{len(accounts)}")
    totals = {"success": 0, "already": 0, "skipped": 0, "failure": 0}
    rows = []
    if not accounts:
        log("❌ 配置错误：请设置 NGA_ACCOUNTS 或完整的旧版三个变量")
    for index, account in enumerate(accounts, 1):
        account_begin = time.monotonic()
        stage_begin = time.monotonic()
        log(f"账号 {index} · 阶段 1/2：验证参数")
        issue = validate(account)
        log(f"账号 {index} · 参数验证{'失败' if issue else '通过'}；耗时 {time.monotonic()-stage_begin:.2f} 秒")
        stage_begin = time.monotonic()
        log(f"账号 {index} · 阶段 2/2：{'预演签到' if dry_run else '请求并核验签到'}")
        if issue:
            result, detail = "failure", issue
        elif dry_run:
            result, detail = "skipped", "DRY_RUN_OK：参数与签到流程通过；未发送 HTTP 请求，未验证真实业务"
        else:
            try:
                payload = request_sign(account)
                result, detail, stats = interpret(payload)
                identity = public_identity(payload, stats)
                if identity:
                    log(f"账号 {index} · 官方身份：{identity}")
            except urllib.error.HTTPError as exc:
                result, detail = "failure", f"HTTP 请求失败：状态码 {exc.code}"
            except (urllib.error.URLError, TimeoutError, OSError):
                result, detail = "failure", "网络请求失败或超时；请求未重试，签到结果无法核验"
            except Exception:
                result, detail = "failure", "响应解析或请求处理失败（错误内容已脱敏）"
        totals[result] += 1
        icon = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failure": "❌"}[result]
        log(f"账号 {index} · {icon} {detail}；阶段耗时 {time.monotonic()-stage_begin:.2f} 秒")
        row = {"account": index, "result": result, "elapsedSeconds": round(time.monotonic()-account_begin, 2)}
        rows.append(row)
        counts = {key: int(key == result) for key in totals}
        log(f"账号 {index} · 统计：总任务 1，成功 {counts['success']}，已完成 {counts['already']}，"
            f"跳过 {counts['skipped']}，失败 {counts['failure']}；耗时 {row['elapsedSeconds']:.2f} 秒")
    failed = totals["failure"]
    success = totals["success"] + totals["already"]
    code = 1 if failed or not accounts else 0
    status = ("configuration-error" if not accounts else
              "partial-failure" if failed and failed < len(accounts) else
              "failure" if failed else "dry-run" if dry_run else "success")
    summary = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts": len(accounts),
               "success": success, "failed": failed, "tasks": totals, "results": rows,
               "startedAt": started, "exitCode": code}
    log("阶段 3/3：汇总与通知")
    summary["notification"] = notify(summary, dry_run)
    summary["finishedAt"] = stamp()
    summary["elapsedSeconds"] = round(time.monotonic()-begin, 2)
    log("----------------------------------------")
    log(f"账号统计：总数 {len(accounts)}，成功 {success}，失败 {failed}，预演跳过 {totals['skipped']}")
    log(f"子任务统计：总数 {len(accounts)}，成功 {totals['success']}，已完成 {totals['already']}，"
        f"跳过 {totals['skipped']}，失败 {failed}")
    log(f"通知状态：{summary['notification']}；总耗时 {summary['elapsedSeconds']:.2f} 秒")
    log(f"完成时间：{summary['finishedAt']}；最终状态：{status}；退出码：{code}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
