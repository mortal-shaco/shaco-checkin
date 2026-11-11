#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WorkBuddy 加油站每日签到
# cron: 54 10 * * *
"""WorkBuddy Buddy加油站，每日签到。来源 Xriou/buddy-checkin/checkin.py。

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

配置 BUDDY_COOKIE，每个非空行填写一个账号的完整 Cookie 请求头值。
在浏览器登录 https://www.workbuddy.cn，开发者工具 Network 中找到
/billing/meter/checkin-status 的 POST 请求，复制 Request Headers 的 Cookie 值。
Cookie 会过期，遇到认证失败时重新登录并更新。禁止分享凭据。
不拆分 Cookie 中的分号、等号、& 或 @。不读取或写入 state.json。
默认执行每日签到，--check 仅查询状态。原 --login 改为上述手动获取方式。
BUDDY_DRY_RUN=1 完全离线验证配置和流程，通知也仅模拟。
网络接口沿用上游路径、POST、空 JSON 请求体及 Cookie 会话认证。
上游未提供 cron，建议每日 09:00。仅使用 Python 标准库。
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
        _ql_notify_identities = ('f02d352e0599ff52', 'scripts/buddy.py', 'buddy.py', 'buddy')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

TITLE = "WorkBuddy 加油站每日签到"
CATALOG = "f02d352e0599ff52"
BASE = "https://www.workbuddy.cn"
STATUS_URL = "/billing/meter/checkin-status"
CLAIM_URL = "/billing/meter/daily-checkin"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


class TaskError(Exception):
    """仅包含可安全展示的固定诊断信息。"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_cookie(cookie):
    # 不重组凭据，保留第一等号之后的所有内容。
    if any(ord(char) < 32 or ord(char) == 127 for char in cookie):
        raise TaskError("Cookie 含控制字符，请重新复制请求头值")
    try:
        cookie.encode("latin-1")
    except UnicodeEncodeError:
        raise TaskError("Cookie 请求头编码无效") from None
    if cookie.lower().startswith("cookie:"):
        raise TaskError("仅填写 Cookie 值，不包含请求头名称")
    parts = cookie.split(";")
    if not all("=" in part and part.split("=", 1)[0].strip() for part in parts if part.strip()):
        raise TaskError("Cookie 格式无效，应为名称=值，多项以分号连接")
    if "=" not in cookie or not cookie.split("=", 1)[1].strip():
        raise TaskError("Cookie 内容为空或格式无效")


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = build_opener(NoRedirect(), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(self, path):
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   "Origin": BASE, "Referer": BASE + "/", "User-Agent": "Mozilla/5.0"}
        # CookieJar 处理后续 Set-Cookie，最初的 Cookie 同时保留其余字段。
        headers["Cookie"] = self.cookie
        request = Request(BASE + path, data=b"{}", headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise TaskError("接口 HTTP 状态异常")
                raw = response.read(1048577)
                # 将官方响应中的轮换 Cookie 合并到本账号内存会话。
                pairs = dict(part.strip().split("=", 1) for part in self.cookie.split(";") if part.strip())
                for item in self.opener.handlers:
                    if isinstance(item, HTTPCookieProcessor):
                        for entry in item.cookiejar:
                            domain = entry.domain.lstrip(".")
                            if domain == "workbuddy.cn" or domain == "www.workbuddy.cn":
                                pairs[entry.name] = entry.value
                self.cookie = "; ".join(f"{key}={value}" for key, value in pairs.items())
        except HTTPError as error:
            code = error.code
            error.close()
            if code in (301, 302, 303, 307, 308, 401, 403):
                raise TaskError("认证失效或发生重定向，请重新获取 Cookie") from None
            raise TaskError(f"接口 HTTP {code}，未确认业务成功") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise TaskError("接口网络、超时或请求失败，未确认业务成功") from None
        if len(raw) > 1048576:
            raise TaskError("接口响应超过大小限制")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("接口未返回有效 JSON") from None
        if not isinstance(body, dict):
            raise TaskError("接口响应结构无效")
        return body


def business_code(body):
    code = body.get("code")
    if type(code) is not int:
        raise TaskError("接口缺少有效业务码")
    return code


def print_identity(data):
    # 仅输出明确的公开身份字段，不输出整个 data 或任意服务端消息。
    for key in ("nickname", "username", "display_name", "displayName", "uid"):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            # 使用 JSON 转义控制字符，避免伪造日志行。
            log("官方账号身份 " + json.dumps(value, ensure_ascii=False))
            break


def status_data(body):
    if business_code(body) != 0:
        raise TaskError("查询业务失败，请检查登录态或活动状态")
    data = body.get("data")
    if not isinstance(data, dict) or type(data.get("today_checked_in")) is not bool:
        raise TaskError("查询缺少明确的今日签到状态，停止领取")
    print_identity(data)
    theme = data.get("theme_name")
    theme_text = json.dumps(theme, ensure_ascii=False) if isinstance(theme, str) else "未开始"
    stats = []
    for key, label in (("streak_days", "连签天数"), ("total_credits", "累计积分")):
        value = data.get(key)
        stats.append(f"{label}={value if type(value) in (int, float) else '未返回'}")
    log(f"[状态] 本期主题={theme_text} | 今日已签={data['today_checked_in']} | " + " | ".join(stats))
    return data


def run_account(cookie, dry, check_only, stats):
    started = time.monotonic()
    log("阶段 1/2 配置与状态查询")
    validate_cookie(cookie)
    if dry:
        stats["skipped"] += 2
        log("阶段 1/2 ✅ DRY_RUN 配置有效，跳过网络查询")
        log("阶段 2/2 ⏭️ DRY_RUN 跳过领取与复查，耗时 0.00 秒")
        return
    client = Client(cookie)
    data = status_data(client.post(STATUS_URL))
    stats["success"] += 1
    log(f"阶段 1/2 ✅ 状态查询完成，耗时 {time.monotonic() - started:.2f} 秒")
    stage_started = time.monotonic()
    log("阶段 2/2 每日领取")
    if data["today_checked_in"]:
        stats["alreadyComplete"] += 1
        log("[OK] 今日已签到，无需重复领取")
    elif check_only:
        stats["skipped"] += 1
        log("⏭️ 仅查询模式，今日尚未签到")
    else:
        body = client.post(CLAIM_URL)
        code = business_code(body)
        if code not in (0, 10001):
            raise TaskError("领取业务失败，服务端未确认签到")
        # 防止过期或异常响应误报成功，领取后再次查询官方状态。
        confirmed = status_data(client.post(STATUS_URL))
        if not confirmed["today_checked_in"]:
            raise TaskError("领取后复查未确认今日签到")
        if code == 10001:
            stats["alreadyComplete"] += 1
            log("[OK] 今日已签到(服务端确认)")
        else:
            stats["success"] += 1
            log("[DONE] 签到成功，官方状态复查通过")
    log(f"阶段 2/2 ✅ 完成，耗时 {time.monotonic() - stage_started:.2f} 秒")


def notify(summary, dry):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return "已关闭"
    if switch not in TRUE | {"auto"}:
        return "通知开关无效，已跳过"
    if switch == "auto":
        selectors = re.split(r"[,;\s]+", os.getenv("QINGLONG_NOTIFY_SCRIPTS", CATALOG).strip())
        names = (CATALOG, Path(__file__).name, "candidate.py", "checkin.py", "scripts/" + Path(__file__).name)
        if not any(fnmatch.fnmatch(name, pattern) for pattern in selectors if pattern for name in names):
            return "未选中通知"
    if dry:
        return "DRY_RUN 已模拟通知，未访问网络"
    text = (f"状态 {summary['status']}，账号总数 {summary['accounts']}，"
            f"成功 {summary['succeeded']}，失败 {summary['failed']}，"
            f"耗时 {summary['durationSeconds']} 秒")
    # 外部通知模块输出不可信，子进程中抑制输出并限制执行时间。
    runner = '''
import contextlib, importlib, importlib.util, io, json, pathlib, subprocess, sys
payload = json.loads(sys.stdin.read())
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        module = importlib.import_module("notify")
        module.send(payload["title"], payload["text"])
        sys.exit(0)
    except Exception:
        pass
    for directory in payload["directories"]:
        path = pathlib.Path(directory) / "notify.py"
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(payload["title"], payload["text"])
                sys.exit(0)
            except Exception:
                pass
        path = pathlib.Path(directory) / "sendNotify.js"
        if path.is_file():
            try:
                code = "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.text)).catch(()=>process.exit(1));"
                result = subprocess.run(["node", "-e", code, str(path)], input=json.dumps(payload), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if result.returncode == 0:
                    sys.exit(0)
            except Exception:
                pass
sys.exit(1)
'''
    directories = [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    payload = {"title": TITLE, "text": text, "directories": [p for p in directories if p]}
    try:
        result = subprocess.run([sys.executable, "-c", runner], input=json.dumps(payload),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30)
        return "已发送" if result.returncode == 0 else "通知不可用或发送失败，保留业务退出码"
    except (OSError, subprocess.TimeoutExpired):
        return "通知不可用或超时，保留业务退出码"


def main():
    start = time.monotonic()
    started_at = datetime.now().isoformat(timespec="seconds")
    dry_value = os.getenv("BUDDY_DRY_RUN", "0").strip().lower()
    dry = dry_value in TRUE
    check_only = "--check" in sys.argv[1:]
    lines = [line.strip() for line in os.getenv("BUDDY_COOKIE", "").splitlines() if line.strip()]
    log(f"===== {TITLE} =====")
    log(f"开始时间 {started_at} | 模式 {'离线预演' if dry else '仅查询' if check_only else '正式签到'} | 账号数 {len(lines)}")
    results = []
    error = ""
    if dry_value not in TRUE | FALSE:
        error = "BUDDY_DRY_RUN 仅支持 1/0、true/false、yes/no、on/off"
    if any(arg != "--check" for arg in sys.argv[1:]):
        error = "参数无效，仅支持 --check。登录请在官网完成后复制 Cookie 到 BUDDY_COOKIE"
    if not lines:
        error = "缺少 BUDDY_COOKIE，请从官网登录后的签到状态请求头获取，每行一个账号"
    if error:
        log("❌ 配置错误 " + error)
    else:
        for index, cookie in enumerate(lines, 1):
            account_start = time.monotonic()
            stats = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            log(f"----- 账号 {index}/{len(lines)} -----")
            try:
                run_account(cookie, dry, check_only, stats)
            except TaskError as exc:
                stats["failed"] += 1
                log("❌ " + str(exc))
            except Exception:
                stats["failed"] += 1
                log("❌ 未预期的账号处理异常，已隐藏异常内容")
            stats["skipped"] += stats["total"] - sum(stats[key] for key in ("success", "alreadyComplete", "skipped", "failed"))
            stats["durationSeconds"] = round(time.monotonic() - account_start, 2)
            stats["account"] = index
            log("账号统计 " + json.dumps(stats, ensure_ascii=False))
            results.append(stats)
    failed = sum(item["failed"] > 0 for item in results)
    succeeded = len(results) - failed
    status = ("configuration-error" if error else "partial-failure" if failed and succeeded
              else "failure" if failed else "dry-run" if dry else "success")
    summary = {"status": status, "accounts": len(lines), "succeeded": succeeded,
               "failed": len(lines) if error else failed, "results": results,
               "startedAt": started_at, "durationSeconds": round(time.monotonic() - start, 2)}
    summary["notification"] = notify(summary, dry)
    summary["finishedAt"] = datetime.now().isoformat(timespec="seconds")
    summary["durationSeconds"] = round(time.monotonic() - start, 2)
    log("----------------------------------------")
    log(f"任务统计 账号总数={len(lines)} 成功={succeeded} 失败={summary['failed']}")
    totals = {key: sum(item[key] for item in results) for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("子任务统计 " + json.dumps(totals, ensure_ascii=False))
    log(f"完成时间 {summary['finishedAt']} | 总耗时 {summary['durationSeconds']} 秒 | 最终状态 {status}")
    log("通知状态 " + summary["notification"])
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 2 if error else 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
