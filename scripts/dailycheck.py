#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 电子科大返校疫情健康打卡
# cron: 33 9 * * *
# SPDX-License-Identifier: Apache-2.0
"""电子科技大学 jzsz 返校疫情健康登记（维护版）。

上游: tualatinlz/web-dailycheckin python/dailyCheck.py
Commit: df172e193ffdcc944629a87e1f825eea9f6639f5
License: Apache-2.0

功能对照（主源）:
  - GET checkRegisterNew 查询当日是否已登记（appliedTimes）
  - 未登记时 POST monitorRegisterForReturned 提交健康与位置信息
  - 再次查询 appliedTimes==1 核验成功
  - 可用 sessionId 调用 getLoginUser 换取 Cookie
关联来源 web/sou.js 为站点百度搜索建议前端，非账号任务，不合并。
已发布「电子科大晚安成电打卡」使用同主机不同接口与晚间窗口，功能不重复，保持独立。

WEB_DAILY_COOKIE: 必填。每个非空行一个账号：sessionId 或 Cookie；可选 |显示名。
仅按首个 | 分割；账号只用换行分隔，不支持 &/@。
在微信「电子科技大学」相关小程序登录后，从 jzsz.uestc.edu.cn 业务请求复制
Cookie，或复制登录 sessionId；不要把凭据发给他人。
WEB_DAILY_LOCATION / WEB_DAILY_HEALTH_CONDITION / WEB_DAILY_HEALTH_COLOR /
WEB_DAILY_TEMP_MORNING / WEB_DAILY_TEMP_MIDDAY / WEB_DAILY_TEMP_EVENING:
可选填报表单字段，默认与上游一致。
WEB_DAILY_DRY_RUN=1: 完全断网预演。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR: 通知控制。

Copyright notice: based on tualatinlz/web-dailycheckin (Apache-2.0).
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
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
        _ql_notify_identities = ('92874903eb80e31d', 'scripts/dailycheck.py', 'dailycheck.py', 'dailycheck')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

SCRIPT_NAME = "电子科大返校疫情健康打卡"
BASE = "https://jzsz.uestc.edu.cn"
URL_STATUS = BASE + "/wxvacation/api/epidemic/checkRegisterNew"
URL_REGISTER = BASE + "/wxvacation/api/epidemic/monitorRegisterForReturned"
URL_LOGIN_USER = BASE + "/wxvacation/api/user/getLoginUser"
UA = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36 "
    "MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat"
)
REFERER = "https://servicewechat.com/wx521c0c16b77041a0/28/page-frame.html"
TIMEOUT = 20
MAX_BYTES = 1048576
CRED_ENV = "WEB_DAILY_COOKIE"
DRY_ENV = "WEB_DAILY_DRY_RUN"
DISABLED = {"0", "false", "no", "off"}
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def enabled(name, default="0"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def log(text):
    print("[{}] {}".format(datetime.datetime.now().strftime("%H:%M:%S"), text), flush=True)


class TaskError(Exception):
    """脱敏业务错误。"""


def base_headers(cookie=""):
    return {
        "Host": "jzsz.uestc.edu.cn",
        "Connection": "keep-alive",
        "Cookie": cookie or "",
        "User-Agent": UA,
        "X-Tag": "flyio",
        "content-type": "application/json",
        "encode": "false",
        "Referer": REFERER,
        "Accept-Encoding": "gzip, deflate, br",
    }


def parse_set_cookie(header_value):
    if not isinstance(header_value, str) or not header_value.strip():
        raise TaskError("登录接口未返回可用 Cookie")
    # 只取首个 name=value，丢弃 Path/HttpOnly 等属性，避免把属性塞进 Cookie 头。
    first = header_value.split(",", 1)[0]
    pair = first.split(";", 1)[0].strip()
    if "=" not in pair or pair.startswith("="):
        raise TaskError("登录接口 Cookie 格式异常")
    return pair


def safe_identity(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(secret and secret in text for secret in secrets):
        return None
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
        return None
    if any(ord(c) < 32 for c in text):
        return None
    return text


def http_json(method, url, cookie="", payload=None):
    headers = base_headers(cookie)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
            set_cookie = resp.headers.get("Set-Cookie")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        raise TaskError("接口 HTTP 错误 {}".format(exc.code)) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise TaskError("接口网络或超时失败") from None
    if status != 200:
        raise TaskError("接口 HTTP 状态异常")
    if len(raw) > MAX_BYTES:
        raise TaskError("接口响应超过大小限制")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise TaskError("接口 JSON 解析失败") from None
    if not isinstance(data, dict):
        raise TaskError("接口响应结构异常")
    return data, set_cookie


def form_payload():
    return {
        "healthCondition": os.getenv("WEB_DAILY_HEALTH_CONDITION", "正常").strip() or "正常",
        "todayMorningTemperature": os.getenv(
            "WEB_DAILY_TEMP_MORNING", "36°C~36.5°C"
        ).strip()
        or "36°C~36.5°C",
        "yesterdayEveningTemperature": os.getenv(
            "WEB_DAILY_TEMP_EVENING", "36°C~36.5°C"
        ).strip()
        or "36°C~36.5°C",
        "yesterdayMiddayTemperature": os.getenv(
            "WEB_DAILY_TEMP_MIDDAY", "36°C~36.5°C"
        ).strip()
        or "36°C~36.5°C",
        "location": os.getenv(
            "WEB_DAILY_LOCATION",
            "四川省成都市郫都区西源大道2006号电子科技大学",
        ).strip()
        or "四川省成都市郫都区西源大道2006号电子科技大学",
        "healthColor": os.getenv("WEB_DAILY_HEALTH_COLOR", "绿色").strip() or "绿色",
    }


def notify(summary, dry):
    body = "账号总数 {accounts}，成功 {succeeded}，失败 {failed}；状态 {status}。".format(
        **summary
    )
    if os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() in DISABLED:
        log("⏭️ 通知已关闭")
        return "disabled"
    if dry:
        log("⏭️ 断网预演：通知摘要 " + body)
        return "dry-run"
    worker = """import importlib, importlib.util, os, sys
try:
    module = importlib.import_module("notify")
except ImportError:
    module = None
    paths = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(os.path.join(directory, "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    for path in paths:
        if os.path.isfile(path):
            sys.path.insert(0, os.path.dirname(path))
            spec = importlib.util.spec_from_file_location("notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
if module is None or not callable(getattr(module, "send", None)):
    sys.exit(2)
module.send(sys.argv[1], sys.argv[2])
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", worker, SCRIPT_NAME, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            log("✅ 通知适配器调用完成")
            return "sent"
    except (OSError, subprocess.TimeoutExpired):
        pass
    log("⚠️ 青龙通知不可用或调用失败，保留业务退出码")
    return "unavailable-or-failed"


class Account:
    def __init__(self, number, line, dry, secrets, payload):
        cred, sep, label = line.partition("|")
        self.number = number
        self.credential = cred.strip()
        self.label = label.strip()
        self.dry = dry
        self.secrets = secrets
        self.payload = payload
        self.cookie = ""
        self.display = self.label or "账号{}".format(number)
        self.counts = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
        self.started = time.monotonic()
        self.stage_number = 0

    def stage(self, name, operation, validate=False, already=False):
        self.stage_number += 1
        start = time.monotonic()
        log("账号 {} 阶段 {}：{}".format(self.number, self.stage_number, name))
        try:
            if self.dry and not validate:
                log("⏭️ DRY_RUN：参数与流程检查通过，不发送请求")
                self.counts["skipped"] += 1
                return None
            result = operation()
            if already:
                self.counts["alreadyComplete"] += 1
                log("☑️ {}：今日已打卡".format(name))
            else:
                self.counts["success"] += 1
                log("✅ {}完成".format(name))
            return result
        except TaskError as exc:
            self.counts["failed"] += 1
            log("❌ {}：{}".format(name, exc))
            return None
        except Exception:
            self.counts["failed"] += 1
            log("❌ {}：响应契约或本地处理异常（已隐藏原始数据）".format(name))
            return None
        finally:
            log(
                "账号 {} 阶段 {} 耗时 {:.2f} 秒".format(
                    self.number, self.stage_number, time.monotonic() - start
                )
            )

    def resolve_cookie(self):
        cred = self.credential
        if not cred or any(ord(c) < 32 for c in cred):
            raise TaskError("凭据为空或含非法控制字符")
        if "@" in cred or "&" in cred:
            raise TaskError("账号分隔符非法，请改用换行分隔账号")
        # sessionId（UUID）走 getLoginUser；已是 Cookie 则直接使用。
        if UUID_RE.fullmatch(cred):
            data, set_cookie = http_json(
                "GET", URL_LOGIN_USER + "?sessionId=" + cred, cookie=""
            )
            self.cookie = parse_set_cookie(set_cookie)
            self._maybe_identity(data)
            return self.cookie
        self.cookie = cred
        return self.cookie

    def _maybe_identity(self, data):
        payload = data.get("data") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            payload = data if isinstance(data, dict) else {}
        for field in (
            "nickName",
            "nickname",
            "userName",
            "username",
            "realName",
            "name",
            "displayName",
            "uid",
            "userId",
        ):
            identity = safe_identity(payload.get(field), self.secrets)
            if identity is not None:
                self.display = identity
                log("账号 {} 官方身份 {}：{}".format(self.number, field, identity))
                return

    def query_status(self):
        data, _ = http_json("GET", URL_STATUS, cookie=self.cookie)
        message = data.get("message")
        body = data.get("data")
        if body is None:
            text = safe_identity(message, self.secrets) or "业务未返回登记数据"
            raise TaskError(text)
        if not isinstance(body, dict):
            raise TaskError("登记状态结构异常")
        applied = body.get("appliedTimes")
        if type(applied) is not int or applied < 0:
            raise TaskError("appliedTimes 字段缺失或异常")
        self._maybe_identity(body)
        return applied

    def submit(self):
        data, _ = http_json("POST", URL_REGISTER, cookie=self.cookie, payload=self.payload)
        if data.get("status") is not True:
            message = safe_identity(data.get("message"), self.secrets) or "提交未确认成功"
            raise TaskError(message)
        return True

    def verify(self):
        applied = self.query_status()
        if applied != 1:
            raise TaskError("复查询未确认已打卡")
        return True

    def validate_params(self):
        if not self.credential:
            raise TaskError("缺少凭据")
        if any(ord(c) < 32 for c in self.credential):
            raise TaskError("凭据含非法控制字符")
        if "@" in self.credential or "&" in self.credential:
            raise TaskError("账号分隔符非法，请改用换行分隔账号")
        return True

    def skip_stage(self, name):
        self.stage_number += 1
        self.counts["skipped"] += 1
        log(
            "账号 {} 阶段 {}：⏭️ {}，前置步骤失败；耗时 0.00 秒".format(
                self.number, self.stage_number, name
            )
        )

    def run(self):
        ok = self.stage("账号参数检查", self.validate_params, validate=True)
        if ok is None:
            duration = round(time.monotonic() - self.started, 2)
            log(
                "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {} 秒".format(
                    self.number,
                    self.display,
                    sum(self.counts.values()),
                    self.counts["success"],
                    self.counts["alreadyComplete"],
                    self.counts["skipped"],
                    self.counts["failed"],
                    duration,
                )
            )
            return dict(
                account=self.number,
                display=self.display,
                **self.counts,
                durationSeconds=duration,
            )
        cookie = self.stage("解析会话并准备 Cookie", self.resolve_cookie)
        if self.dry:
            self.stage("查询打卡状态", lambda: 0)
            self.stage("提交健康打卡", lambda: True)
            self.stage("复查询核验", lambda: True)
        elif cookie is None:
            self.skip_stage("查询打卡状态")
            self.skip_stage("提交健康打卡")
            self.skip_stage("复查询核验")
        else:
            applied = self.stage("查询打卡状态", self.query_status)
            if applied is None:
                self.skip_stage("提交健康打卡")
                self.skip_stage("复查询核验")
            elif applied >= 1:
                self.stage("确认已打卡", lambda: True, already=True)
            else:
                submitted = self.stage("提交健康打卡", self.submit)
                if submitted is not None:
                    self.stage("复查询核验", self.verify)
                else:
                    self.skip_stage("复查询核验")
        duration = round(time.monotonic() - self.started, 2)
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {} 秒".format(
                self.number,
                self.display,
                sum(self.counts.values()),
                self.counts["success"],
                self.counts["alreadyComplete"],
                self.counts["skipped"],
                self.counts["failed"],
                duration,
            )
        )
        return dict(
            account=self.number,
            display=self.display,
            **self.counts,
            durationSeconds=duration,
        )


def main():
    start = time.monotonic()
    dry = enabled(DRY_ENV)
    raw = os.getenv(CRED_ENV, "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    payload = form_payload()
    print("========== {} ==========".format(SCRIPT_NAME), flush=True)
    log("开始时间：" + datetime.datetime.now().isoformat(timespec="seconds"))
    log("模式：{}；账号数：{}".format("断网预演" if dry else "正式运行", len(lines)))
    config_error = not lines
    results = []
    if config_error:
        log(
            "❌ 阶段 1：配置错误；请设置 {}，每行一个 sessionId 或 Cookie；耗时 0.00 秒".format(
                CRED_ENV
            )
        )
    else:
        secrets = []
        for line in lines:
            cred = line.partition("|")[0].strip()
            if cred:
                secrets.append(cred)
        for i, line in enumerate(lines, 1):
            results.append(Account(i, line, dry, secrets, payload).run())
    failed = sum(1 for r in results if r["failed"] > 0)
    succeeded = len(results) - failed
    if config_error:
        status = "configuration-error"
    elif failed and succeeded:
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry:
        status = "dry-run"
    else:
        status = "success"
    summary = dict(
        accounts=len(lines),
        succeeded=succeeded,
        failed=failed,
        status=status,
        mode="dry-run" if dry else "live",
        configurationErrors=int(bool(config_error)),
        accountResults=results,
        subtasks={
            k: sum(r[k] for r in results)
            for k in ("success", "alreadyComplete", "skipped", "failed")
        },
    )
    if config_error:
        summary["failed"] = len(lines) or 1
    summary["notification"] = notify(summary, dry)
    summary["durationSeconds"] = round(time.monotonic() - start, 2)
    summary["finishedAt"] = datetime.datetime.now().isoformat(timespec="seconds")
    print("----------------------------------------", flush=True)
    log(
        "任务统计：账号总数 {}，成功 {}，失败 {}；子任务 {}".format(
            summary["accounts"],
            summary["succeeded"],
            summary["failed"],
            json.dumps(summary["subtasks"], ensure_ascii=False),
        )
    )
    log(
        "总耗时 {} 秒；完成时间 {}；通知状态 {}".format(
            summary["durationSeconds"], summary["finishedAt"], summary["notification"]
        )
    )
    log("最终状态：" + status)
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return 1 if config_error or failed else 0


if __name__ == "__main__":
    sys.exit(main())
