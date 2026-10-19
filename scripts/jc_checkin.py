#!/usr/bin/env python3
# name: 机场面板每日签到
# cron: 45 2 * * *
# 上游：kerncoola/JC_CheckIn，JC_CheckIn.py
# 原始提交：71362b20abdad2711ddc2e4321ef33b3ebcc64c5；许可证：MIT
# 原始文件未附版权声明或许可证正文。保留上述来源及许可证归属。
# MIT License
# Copyright (c) kerncoola/JC_CheckIn contributors
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
"""独立 SSPanel 风格机场签到脚本（Python 标准库，无需安装依赖）。

BASE_URL：自己使用的机场面板 HTTPS 根地址，不含 /auth/login 或 /user。
JC_ACCOUNTS：每个非空行一个 邮箱|密码，仅按首个 | 分割，密码中的 | 保留。
凭据取自本人注册的账号；仅支持邮箱及密码登录，验证码/二步验证会失败。
单账号兼容 EMAIL、PASSWORD；JC_ACCOUNTS 设置后优先使用，禁止混合分隔账号。
JC_DRY_RUN=1：断网预演，不登录、不签到、不推送，青龙通知在禁网子进程中尝试。
QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭通知。QINGLONG_NOTIFY_DIR 可指定
notify.py 所在目录。JC_PUSHPLUS=1 且 SCKEY 非空时额外发送 HTTPS PushPlus 通知，
SCKEY 为本人 PushPlus 控制台 token；默认关闭，避免未经选择向第三方发送内容。
推荐每天 08:00 执行一次；原始源码没有 cron，用户可调整面板定时规则。
仅 ret=1（或 JSON true）视为成功；未知/已签到但 ret 非成功均失败闭合。
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
        _ql_notify_identities = ('fd9b2a23e39332a5', 'scripts/jc_checkin.py', 'jc_checkin.py', 'jc_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import http.cookiejar
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

TITLE = "机场面板每日签到"
DISABLED = {"0", "false", "no", "off"}
ENABLED = {"1", "true", "yes", "on"}
TIMEOUT = 15
MAX_BYTES = 1024 * 1024


def stamp():
    return datetime.now().strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


def enabled(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    if value not in ENABLED | DISABLED:
        raise ValueError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")
    return value in ENABLED


def configuration():
    base = os.getenv("BASE_URL", "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    try:
        parsed.port
    except ValueError:
        raise ValueError("BASE_URL 端口无效") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or any(c.isspace() for c in base)):
        raise ValueError("BASE_URL 必须是无凭据、查询参数或片段的 HTTPS 面板根地址")
    lines = [s for s in os.getenv("JC_ACCOUNTS", "").splitlines() if s.strip()]
    accounts = []
    if lines:
        for index, line in enumerate(lines, 1):
            email, sep, password = line.partition("|")
            accounts.append((email.strip(), password if sep else ""))
    else:
        email, password = os.getenv("EMAIL", "").strip(), os.getenv("PASSWORD", "")
        if not email or not password:
            raise ValueError("请设置 JC_ACCOUNTS，或兼容单账号 EMAIL 和 PASSWORD")
        accounts.append((email, password))
    pushplus = enabled("JC_PUSHPLUS")
    if pushplus and not os.getenv("SCKEY", "").strip():
        raise ValueError("开启 JC_PUSHPLUS 时必须设置 SCKEY")
    return base, accounts, pushplus


class SafeError(Exception):
    """仅包含可公开的固定错误信息。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeError("接口发生重定向，请核对面板根地址；未向重定向地址发送凭据")


class HTTP:
    def __init__(self):
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, url, fields=None, referer=None, expect_json=True):
        headers = {"User-Agent": "Mozilla/5.0 Qinglong-JC-CheckIn/1.0"}
        data = None
        if fields is not None:
            data = urllib.parse.urlencode(fields).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise SafeError("HTTP 状态不符合预期")
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise SafeError("响应超出大小限制")
            if not expect_json:
                return None
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise SafeError("接口响应不是 JSON 对象")
            return payload
        except SafeError:
            raise
        except urllib.error.HTTPError as error:
            raise SafeError(f"HTTP 请求失败（状态 {error.code}）") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SafeError("网络、超时或证书校验失败") from None
        except (ValueError, UnicodeError):
            raise SafeError("接口返回无效 JSON") from None


def verify(payload, stage):
    # 上游 checkin 接口属于 SSPanel 的 ret/msg 契约；不凭文案或 HTTP 200 判成功。
    result = payload.get("ret")
    if result is True or type(result) is int and result == 1:
        return
    raise SafeError(f"{stage}业务未确认成功（ret 非 1/true）；请核对凭据及面板接口")


def show_identity(payload, credentials):
    # 只读白名单字段；不打印 msg、响应、手机号、邮箱或会话字段。
    containers = [payload]
    for key in ("user", "data"):
        if isinstance(payload.get(key), dict):
            containers.append(payload[key])
    for container in containers:
        for key in ("nickname", "username", "display_name", "displayName", "uid"):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (not value or any(secret and secret in value for secret in credentials)
                    or "@" in value or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value)
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                continue
            log(f"官方账号身份（{key}）：{value}")
            return


def run_account(index, base, credentials, dry):
    started = time.monotonic()
    stats = {"total": 3, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    log(f"账号 {index} 开始")
    client = None
    steps = ("初始化面板会话", "登录账号", "每日签到")
    for stage, title in enumerate(steps, 1):
        tick = time.monotonic()
        log(f"账号 {index} 阶段 {stage}/3：{title}")
        try:
            if stage == 1:
                if (not re.fullmatch(r"[^\s@]+@[^\s@]+", credentials[0])
                        or not credentials[1]):
                    raise SafeError("账号配置无效：每行须为有效邮箱|非空密码；其他账号继续执行")
                if not dry:
                    client = HTTP()
            if dry:
                stats["skipped"] += 1
                log(f"⏭️ 断网预演：{title}请求已模拟；耗时 {time.monotonic() - tick:.2f} 秒")
                continue
            if stage == 1:
                client.request(base, expect_json=False)
            elif stage == 2:
                payload = client.request(base + "/auth/login", {
                    "email": credentials[0], "passwd": credentials[1], "code": ""})
                verify(payload, "登录")
                show_identity(payload, credentials)
            else:
                payload = client.request(base + "/user/checkin", {}, base + "/user")
                verify(payload, "签到")
                show_identity(payload, credentials)
            stats["success"] += 1
            log(f"✅ {title}成功；耗时 {time.monotonic() - tick:.2f} 秒")
        except Exception as error:
            stats["failed"] += 1
            stats["skipped"] += 3 - stage
            message = str(error) if isinstance(error, SafeError) else "请求处理失败，异常详情已隐藏"
            log(f"❌ {message}；耗时 {time.monotonic() - tick:.2f} 秒")
            if stage < 3:
                log(f"⏭️ 后续 {3 - stage} 个阶段因前置失败跳过")
            break
    stats["seconds"] = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {stats['seconds']:.2f} 秒")
    return stats


def notification_worker():
    """隔离第三方通知输出；断网模式同时禁用套接字及外部程序启动。"""
    title, body, dry = json.loads(sys.stdin.read())
    if dry:
        import socket
        def deny(*args, **kwargs):
            raise RuntimeError("断网预演禁止网络和外部程序")
        socket.socket = deny
        socket.create_connection = deny
        for key in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
            setattr(socket, key, deny)
        subprocess.Popen = deny
        os.system = deny
        for key in ("posix_spawn", "posix_spawnp", "fork", "execv", "execve", "spawnv", "spawnve"):
            if hasattr(os, key):
                setattr(os, key, deny)
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "")
    if directory:
        paths.append(os.path.join(directory, "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            spec = importlib.util.find_spec("notify")
            if spec is None:
                path = next((p for p in paths if os.path.isfile(p)), None)
                if path:
                    spec = importlib.util.spec_from_file_location("notify", path)
            if spec is None or spec.loader is None:
                return 2
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(title, body)
            return 0
        except BaseException:
            return 3


def notify(body, dry, pushplus):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in DISABLED:
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    result = "unavailable"
    try:
        worker = subprocess.run([sys.executable, os.path.abspath(__file__), "--notify-worker"],
                                input=json.dumps([TITLE, body, dry]), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
        result = "sent" if worker.returncode == 0 else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        result = "failed"
    log("✅ 青龙通知已提交" if result == "sent" else
        "⚠️ 青龙通知不可用或发送失败，保留业务退出码" + ("（预演禁网）" if dry else ""))
    if pushplus:
        if dry:
            log("⏭️ 断网预演：HTTPS PushPlus 推送已模拟")
        else:
            try:
                payload = HTTP().request("https://www.pushplus.plus/send", {
                    "token": os.environ["SCKEY"], "title": TITLE, "content": body})
                if type(payload.get("code")) is not int or payload["code"] != 200:
                    raise SafeError("推送业务未确认成功")
                log("✅ HTTPS PushPlus 推送已提交")
            except Exception:
                log("⚠️ HTTPS PushPlus 推送失败，保留业务退出码")
    return result


def main():
    started = time.monotonic()
    start = datetime.now().isoformat(timespec="seconds")
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start}")
    dry = False
    accounts = []
    results = []
    pushplus = False
    config_error = False
    try:
        dry = enabled("JC_DRY_RUN")
        log("运行模式：断网预演" if dry else "运行模式：正式签到")
        log("阶段 1：校验配置")
        base, accounts, pushplus = configuration()
        log(f"账号总数：{len(accounts)}")
        for index, credentials in enumerate(accounts, 1):
            results.append(run_account(index, base, credentials, dry))
    except Exception as error:
        config_error = True
        log("❌ 配置错误：" + (str(error) if isinstance(error, ValueError) else "配置处理失败"))
        log(f"账号总数：{len(accounts)}")
    failures = sum(bool(item["failed"]) for item in results)
    successes = len(results) - failures
    status = ("configuration-error" if config_error else "partial-failure" if failures and successes
              else "failure" if failures else "dry-run" if dry else "success")
    code = 1 if config_error or failures else 0
    body = (f"状态：{status}；账号总数：{len(accounts)}；"
            f"成功数：{0 if dry else successes}；失败数：{failures}；"
            f"预演账号数：{successes if dry else 0}；配置错误：{int(config_error)}")
    log("阶段 2：发送脱敏通知")
    notification = notify(body, dry, pushplus)
    finish = datetime.now().isoformat(timespec="seconds")
    task_stats = {key: sum(item[key] for item in results)
                  for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    log("----------------------------------------")
    log(body)
    log(f"子任务统计：总数 {task_stats['total']}，成功 {task_stats['success']}，"
        f"已完成 {task_stats['alreadyComplete']}，跳过 {task_stats['skipped']}，失败 {task_stats['failed']}")
    log(f"完成时间：{finish}；总耗时：{time.monotonic() - started:.2f} 秒；通知状态：{notification}")
    log(f"最终状态：{status}；退出码：{code}")
    print("TASK_SUMMARY=" + json.dumps({
        "task": TITLE, "status": status, "mode": "dry-run" if dry else "live",
        "accountCount": len(accounts), "successCount": 0 if dry else successes,
        "failureCount": failures, "dryRunCount": successes if dry else 0,
        "configurationError": config_error, "stages": task_stats,
        "accounts": results, "notification": notification, "startTime": start,
        "finishTime": finish, "seconds": round(time.monotonic() - started, 2),
        "exitCode": code}, ensure_ascii=False, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    if sys.argv[1:] == ["--notify-worker"]:
        sys.exit(notification_worker())
    sys.exit(main())
