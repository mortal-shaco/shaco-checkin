#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 旧版面板每日签到
# cron: 50 10 * * *
# Upstream: nwsuafzq/auto_checkin, autock3.py
# Original attribution (retained):
# *********************************
#        自动签到某网站
#       vresion：python 2
#         author:张琼
#       西北农林科技大学 计算机141
# *********************************
# License: MIT (effectiveLicense supplied by the source catalog).
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
"""旧版面板登录、签到，Python 3 标准库独立实现。

AUTOCK3_ACCOUNTS：每个非空行是 邮箱|密码，只在第一个 | 处分割。
从自己的站点注册/账户设置获得邮箱和密码，不使用其他人的账户。
AUTOCK3_BASE_URL：必填，从自己仍在使用的面板浏览器地址栏取得 HTTPS
源站（不含路径）；先确认它仍支持 POST /user/_login.php 和
POST /user/_checkin.php，字段 email/passwd/remember_me=week。
成功契约仅接受 JSON 对象 ret=1（整数），未知响应失败闭合。
原始代码未提供响应样例，此兼容契约未经在线验证，不代表旧站点仍有效。
AUTOCK3_DRY_RUN=1：不联网、不导入通知模块、不产生登录或签到副作用。
QINGLONG_NOTIFY、QINGLONG_NOTIFY_SCRIPTS：青龙通知开关与选择器。
默认 auto 仅在选择器匹配时发送；显式开启可为本脚本启用通知。
每天运行一次（建议 cron 0 8 * * *），替代原脚本每 86401 秒的常驻循环。
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
        _ql_notify_identities = ('d853362aaeebaf00', 'scripts/autock3.py', 'autock3.py', 'autock3')
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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

TITLE = "旧版面板每日签到"
CATALOG = "d853362aaeebaf00"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
MAX_RESPONSE = 65536


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward credentials, cookies or POST bodies to any redirect.
        raise TaskError("接口重定向，已拒绝继续请求")


def base_url(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError()
        if any(c.isspace() for c in value):
            raise ValueError()
        return value.rstrip("/")
    except ValueError:
        raise TaskError("AUTOCK3_BASE_URL 必须为无路径、无凭据的 HTTPS 源站（443 端口）") from None


def safe_identity(data, email, password):
    # Only documented public identity fields; never dump response objects.
    for fields in (data, data.get("data")):
        if not isinstance(fields, dict):
            continue
        for key in ("nickname", "username", "display_name", "public_uid"):
            value = fields.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (not value or len(value) > 120 or "@" in value
                    or (key != "public_uid" and re.search(r"\d{7,}", value))
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)
                    or email in value or password in value):
                continue
            return value
    return None


def post(opener, origin, path, email, password):
    body = urllib.parse.urlencode({"email": email, "passwd": password,
                                  "remember_me": "week"}).encode("utf-8")
    request = urllib.request.Request(origin + path, data=body, headers={
        "User-Agent": "Qinglong-Autock3/1.0",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": origin + "/user/login.php",
        "Origin": origin,
    }, method="POST")
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError("接口未返回 HTTP 200")
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise TaskError("接口响应超过大小限制")
        data = json.loads(raw.decode("utf-8-sig"))
    except urllib.error.HTTPError as exc:
        raise TaskError(f"HTTP 请求失败（状态码 {exc.code}）") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络连接、证书校验失败或请求超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("响应不是可识别的 JSON，未确认业务成功") from None
    if not isinstance(data, dict) or type(data.get("ret")) is not int or data["ret"] != 1:
        raise TaskError("业务响应未明确返回整数 ret=1，未确认成功；请核对接口兼容性及账号")
    return data


def selected_notification():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selection is not None:
        selectors = [s for s in re.split(r"[,;\s]+", selection) if s]
        names = {CATALOG, Path(__file__).name, "autock3.py", "checkin/autock3.py"}
        path = Path(__file__).as_posix()
        for marker in ("/ql/data/scripts/", "/ql/scripts/"):
            if marker in path:
                names.add(path.split(marker, 1)[1])
        return any(fnmatch.fnmatchcase(n, s) for n in names for s in selectors)
    return switch in TRUE


def notify(summary, dry):
    if not selected_notification():
        return "已关闭或未选中"
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['success']}；失败：{summary['failed']}；"
            f"跳过：{summary['skipped']}；预演：{summary['dryRun']}")
    if dry:
        log("⏭️ 通知预演（不加载通知模块，不联网）：" + body)
        return "预演完成"
    # Run optional Qinglong notification in a bounded child process. Its stdout
    # and stderr are suppressed because third-party notifiers may log secrets.
    runner = r'''
import contextlib, importlib.util, io, json, os, pathlib, subprocess, sys
title, body = json.loads(sys.stdin.read())
paths = []
custom = os.getenv("QINGLONG_NOTIFY_DIR")
if custom:
    paths.append(pathlib.Path(custom))
paths += [pathlib.Path("/ql/data/scripts"), pathlib.Path("/ql/scripts")]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        import notify
        notify.send(title, body)
        sys.exit(0)
    except Exception:
        pass
    for directory in paths:
        p = directory / "notify.py"
        if p.is_file():
            try:
                sys.path.insert(0, str(directory))
                spec = importlib.util.spec_from_file_location("ql_notify", p)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(title, body)
                sys.exit(0)
            except Exception:
                pass
        p = directory / "sendNotify.js"
        if p.is_file():
            js = "const fs=require('fs');const [p,t,b]=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve(require(p).sendNotify(t,b)).catch(()=>process.exit(1));"
            try:
                result = subprocess.run(["node", "-e", js], input=json.dumps([str(p), title, body]), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                if result.returncode == 0:
                    sys.exit(0)
            except Exception:
                pass
sys.exit(1)
'''
    try:
        result = subprocess.run([sys.executable, "-c", runner],
                                input=json.dumps([TITLE, body], ensure_ascii=False),
                                text=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=50)
        return "已交付通知模块" if result.returncode == 0 else "通知不可用或发送失败（保留业务退出码）"
    except (OSError, subprocess.TimeoutExpired):
        return "通知不可用或超时（保留业务退出码）"


def main():
    started = time.monotonic()
    dry = os.getenv("AUTOCK3_DRY_RUN", "0").strip().lower() in TRUE
    lines = [line for line in os.getenv("AUTOCK3_ACCOUNTS", "").splitlines() if line.strip()]
    summary = {"status": "failure", "accounts": len(lines), "success": 0,
               "failed": 0, "skipped": 0, "dryRun": dry,
               "tasks": {"total": 2 * len(lines), "success": 0,
                         "alreadyComplete": 0, "skipped": 0, "failed": 0}}
    log("========== " + TITLE + " ==========")
    log(f"开始时间：{stamp()}；模式：{'离线预演' if dry else '正式运行'}；账号数：{len(lines)}")
    origin = None
    configuration_error = None
    try:
        log("阶段 1：检查配置")
        origin = base_url(os.getenv("AUTOCK3_BASE_URL", "").strip())
        if not lines:
            raise TaskError("缺少 AUTOCK3_ACCOUNTS，每行填写一个 邮箱|密码")
        log("阶段 1 完成：源站配置有效；配置内容已隐藏")
    except TaskError as exc:
        configuration_error = str(exc)
        log("❌ 配置错误：" + configuration_error)
    if configuration_error:
        summary["status"] = "configuration-error"
        summary["failed"] = len(lines)
        summary["tasks"]["skipped"] = 2 * len(lines)
    else:
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            counts = {"total": 2, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            log(f"----- 账号 {index} -----")
            stage = 0
            try:
                email, delimiter, password = line.partition("|")
                if not delimiter or not email.strip() or not password or "@" not in email:
                    raise TaskError("账号格式错误，应为 邮箱|密码")
                email = email.strip()
                opener = None if dry else urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect(),
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                for stage, (label, path) in enumerate((
                        ("登录", "/user/_login.php"), ("签到", "/user/_checkin.php")), 1):
                    tick = time.monotonic()
                    log(f"账号 {index} 阶段 {stage + 1}：{label}")
                    if dry:
                        counts["skipped"] += 1
                        log(f"⏭️ {label}预演：POST 字段与步骤已检查，未发送请求；耗时 {time.monotonic() - tick:.2f} 秒")
                    else:
                        data = post(opener, origin, path, email, password)
                        counts["success"] += 1
                        identity = safe_identity(data, email, password)
                        if identity:
                            log(f"账号 {index} 官方身份：{identity}")
                        log(f"✅ {label}成功：已核验 ret=1；耗时 {time.monotonic() - tick:.2f} 秒")
                        if path == "/user/_checkin.php":
                            print("ck1", flush=True)  # 保留原签到完成标记，仅在验证成功后输出。
                if dry:
                    summary["skipped"] += 1
                else:
                    summary["success"] += 1
            except TaskError as exc:
                counts["failed"] += 1
                counts["skipped"] = 2 - counts["success"] - counts["failed"]
                summary["failed"] += 1
                log(f"❌ 账号 {index} 阶段 {stage + 1}：{exc}；后续动作跳过")
            except Exception:
                counts["failed"] += 1
                counts["skipped"] = 2 - counts["success"] - counts["failed"]
                summary["failed"] += 1
                log(f"❌ 账号 {index} 阶段 {stage + 1}：发生未预期错误（详情已隐藏）；后续动作跳过")
            for key in counts:
                if key != "total":
                    summary["tasks"][key] += counts[key]
            log(f"账号 {index} 统计：总任务 2，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic() - account_start:.2f} 秒")
        summary["status"] = (("partial-failure" if summary["success"] else "failure")
                             if summary["failed"] else ("dry-run" if dry else "success"))
    exit_code = 2 if configuration_error else (1 if summary["failed"] else 0)
    summary["notification"] = notify(summary, dry)
    summary["elapsedSeconds"] = round(time.monotonic() - started, 2)
    summary["finishedAt"] = stamp()
    log("----------------------------------------")
    log(f"账号统计：总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}，跳过 {summary['skipped']}")
    log("子任务统计：" + json.dumps(summary["tasks"], ensure_ascii=False))
    log(f"通知：{summary['notification']}；总耗时：{summary['elapsedSeconds']} 秒")
    log(f"完成时间：{summary['finishedAt']}；最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
