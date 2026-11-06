#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 京东每日签到领京豆
# cron: 40 8 * * *
# 上游：tech-shrimp/GithubActionSample，daily_sign.py
# 来源提交：4176ae42863fb06898226000d5419bd41766eb99
# SPDX-License-Identifier: MIT
# Copyright (c) 2024 TechShrimp技术爬爬虾
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""京东每日签到领取京豆。

JD_COOKIE：登录京东网页后，在浏览器开发者工具网络面板复制完整 Cookie
（需含 pt_key 与 pt_pin），每个非空行一个账号；勿公开、勿写入日志。
账号仅按换行分隔，不使用 & 或 @。
JD_BEAN_SIGN_DRY_RUN=1 完全断网预演，不访问京东接口、不发送外部通知。
定时对应上游 UTC 00:00（北京时间 08:00）。
QINGLONG_NOTIFY 未设置时按上架/脚本选择列表决定；1 强制开启，0 强制关闭。
通知失败不改变业务退出码。
"""

from __future__ import annotations
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
        _ql_notify_identities = ('e0697a36d583ab53', 'scripts/daily_sign.py', 'daily_sign.py', 'daily_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TITLE = "京东每日签到领京豆"
CATALOG_ID = "e0697a36d583ab53"
SIGN_URL = "https://api.m.jd.com/client.action"
SIGN_BODY = (
    '{"fp":"-1","shshshfp":"-1","shshshfpa":"-1","referUrl":"-1",'
    '"userAgent":"-1","jda":"-1","rnVersion":"3.9"}'
)
# 与上游样例保持一致的客户端占位字段；不来自账号凭据。
CLIENT_QUERY = {
    "functionId": "signBeanAct",
    "appid": "ld",
    "client": "apple",
    "clientVersion": "10.0.4",
    "networkType": "wifi",
    "osVersion": "14.8.1",
    "uuid": "3acd1f6361f86fc0a1bc23971b2e7bbe6197afb6",
    "openudid": "3acd1f6361f86fc0a1bc23971b2e7bbe6197afb6",
}
USER_AGENT = "okhttp/3.12.1;jdmall;android;version/10.3.4;build/92451;"
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 1048576
ON = {"1", "true", "yes", "on"}
OFF = {"0", "false", "no", "off"}
TZ_CN = timezone(timedelta(hours=8))


class TaskError(Exception):
    """仅携带已脱敏的固定说明。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("接口重定向已拒绝，防止凭据发送到其他地址")


def now_cn():
    return datetime.now(TZ_CN)


def stamp():
    return now_cn().strftime("%H:%M:%S")


def log(message):
    print("[%s] %s" % (stamp(), message), flush=True)


def env_on(name, default="0"):
    return os.getenv(name, default).strip().lower() in ON


def dry_run_enabled():
    return env_on("JD_BEAN_SIGN_DRY_RUN")


def parse_accounts():
    raw = os.getenv("JD_COOKIE", "")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def cookie_secrets(cookie):
    secrets = [cookie]
    for part in cookie.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        value = part.split("=", 1)[1].strip()
        if value:
            secrets.append(value)
    return secrets


def clean_public(value, secrets=(), limit=160):
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value)).strip()
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit]


def identity_from_payload(payload, secrets):
    sources = []
    if isinstance(payload, dict):
        sources.append(payload)
        data = payload.get("data")
        if isinstance(data, dict):
            sources.append(data)
            for key in ("userInfo", "user", "customerInfo"):
                nested = data.get(key)
                if isinstance(nested, dict):
                    sources.append(nested)
    for source in sources:
        for field in ("nickname", "nickName", "username", "userName", "displayName", "uid", "pin"):
            value = source.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value).strip()
                if not text:
                    continue
                if any(secret and secret in text for secret in secrets):
                    continue
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
                    continue
                return clean_public(text, secrets, limit=80)
    return None


def parse_json_payload(raw_text):
    text = raw_text.strip()
    if not text:
        raise TaskError("接口响应为空")
    # 兼容上游 URL 曾带 jsonp 参数时的包装响应。
    if text[0] not in "{[":
        match = re.match(r"^[^(]+\((.*)\)\s*;?\s*$", text, re.S)
        if not match:
            raise TaskError("接口响应不是可解析 JSON")
        text = match.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TaskError("接口响应 JSON 解析失败") from exc
    if not isinstance(payload, dict):
        raise TaskError("接口响应结构无效")
    return payload


def sign_bean(cookie):
    query = dict(CLIENT_QUERY)
    query["body"] = SIGN_BODY
    url = SIGN_URL + "?" + urllib.parse.urlencode(query)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cache-Control": "no-cache",
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Cookie": cookie,
    }
    request = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=HTTP_TIMEOUT) as response:
            if response.status != 200:
                raise TaskError("HTTP %s，签到未确认" % response.status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError("HTTP %s，签到未确认" % exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError("网络连接失败或超时") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TaskError("响应超过大小限制")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise TaskError("响应编码异常") from exc
    payload = parse_json_payload(text)
    secrets = cookie_secrets(cookie)
    who = identity_from_payload(payload, secrets)
    code = payload.get("code", payload.get("errorCode"))
    code_text = "" if code is None else str(code).strip()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    status = data.get("status")
    bean_count = data.get("beanCount")
    if code_text in {"3", "1001"}:
        return False, "failure", "凭据失效或未登录", who
    if code_text not in {"0", "200", ""}:
        return False, "failure", "业务码未确认成功", who
    if status == 1 or status == "1":
        detail = "签到成功"
        if bean_count is not None and str(bean_count).strip() != "":
            detail += "，获得京豆 %s" % clean_public(bean_count, secrets, limit=32)
        return True, "success", detail, who
    if status == 2 or status == "2":
        return True, "already", "今日已签到", who
    # 部分返回仅有成功文案而无 status。
    message = payload.get("errorMessage") or payload.get("message") or data.get("msg")
    if isinstance(message, str):
        lowered = message.lower()
        if "已签" in message or "已经签" in message:
            return True, "already", "今日已签到", who
        if "login" in lowered or "登录" in message or "未登录" in message:
            return False, "failure", "凭据失效或未登录", who
    return False, "failure", "接口未明确确认签到成功", who


def script_identities():
    script = Path(__file__).resolve()
    names = [
        CATALOG_ID,
        script.name,
        script.stem,
        "candidate.py",
        "output/candidate.py",
        "daily_sign.py",
        "scripts/daily_sign.py",
        "jd_bean_sign.py",
        "scripts/jd_bean_sign.py",
    ]
    return tuple(dict.fromkeys(item.lower() for item in names if item))


def notify_enabled():
    if "QINGLONG_NOTIFY" in os.environ:
        switch = os.environ.get("QINGLONG_NOTIFY", "").strip().lower()
        if switch in OFF:
            return False
        if switch in ON:
            return True
        # auto / 其他值：继续看选择列表
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selection is None:
        # 候选默认未上架：未显式开启时不推送外部渠道。
        if "QINGLONG_NOTIFY" not in os.environ:
            return False
        switch = os.environ.get("QINGLONG_NOTIFY", "").strip().lower()
        return switch not in OFF and switch not in {"", "auto"}
    selectors = [item.lower() for item in re.split(r"[,;\s]+", selection.strip()) if item]
    if not selectors:
        return False
    if "*" in selectors:
        return True
    identities = script_identities()
    return any(
        fnmatch.fnmatchcase(identity, selector)
        for selector in selectors
        for identity in identities
    )


def send_notify(body, dry_run):
    if not notify_enabled():
        log("阶段 3 通知 ⏭️ 未启用或未列入通知清单")
        return "disabled"
    if dry_run:
        log("阶段 3 通知 ⏭️ 断网预演：通知摘要已生成，跳过外部发送")
        print(body, flush=True)
        return "dry-run"
    candidates = []
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        candidates.append(Path(directory) / "notify.py")
    candidates.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    # 优先可导入的 notify 模块，再尝试青龙路径。
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(TITLE, body)
            log("阶段 3 通知 ✅ 通知助手调用完成")
            return "sent"
    except Exception:
        pass
    for path in candidates:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if not callable(sender):
                continue
            sender(TITLE, body)
            log("阶段 3 通知 ✅ 通知助手调用完成")
            return "sent"
        except Exception:
            continue
    log("阶段 3 通知 ⚠️ 青龙 notify.py 不可用或发送失败，保留业务退出码")
    return "unavailable"


def main():
    started = time.monotonic()
    start_at = now_cn().isoformat(timespec="seconds")
    dry = dry_run_enabled()
    accounts = parse_accounts()
    print("══════════ %s ══════════" % TITLE)
    log(
        "开始时间 %s；模式 %s；账号数 %d"
        % (start_at, "断网预演" if dry else "正式运行", len(accounts))
    )
    results = []
    if not accounts:
        log("阶段 1 配置 ❌ 未配置必填 JD_COOKIE；每个非空行一个账号 Cookie")

    for index, cookie in enumerate(accounts, 1):
        account_started = time.monotonic()
        log("账号 %d 阶段 1 凭据已读取（隐藏）" % index)
        who = None
        if dry:
            log("账号 %d 阶段 2 ⏭️ 跳过 HTTP 请求与签到副作用" % index)
            ok, status, message = True, "skipped", "DRY_RUN_OK：配置预演通过，未验证真实签到"
        else:
            request_started = time.monotonic()
            try:
                ok, status, message, who = sign_bean(cookie)
            except TaskError as exc:
                ok, status, message, who = False, "failure", str(exc), None
            except Exception:
                ok, status, message, who = False, "failure", "请求或解析异常；未确认签到成功", None
            icon = "✅" if ok else "❌"
            if status == "already":
                icon = "☑️"
            log(
                "账号 %d 阶段 2 %s %s；耗时 %.2fs"
                % (index, icon, message, time.monotonic() - request_started)
            )
        if who:
            log("账号 %d 身份 %s" % (index, who))
        if dry:
            log("账号 %d 预演 %s" % (index, message))
        counts = {
            "success": int(status == "success"),
            "already": int(status == "already"),
            "skipped": int(status == "skipped"),
            "failure": int(not ok),
        }
        elapsed = time.monotonic() - account_started
        log(
            "账号 %d 统计 总任务 1；成功 %d；已完成 %d；跳过 %d；失败 %d；耗时 %.2fs"
            % (index, counts["success"], counts["already"], counts["skipped"], counts["failure"], elapsed)
        )
        results.append(
            {
                "account": index,
                "ok": ok,
                "status": status,
                "identity": who,
                "tasks": counts,
                "elapsedSeconds": round(elapsed, 3),
            }
        )

    passed = sum(1 for item in results if item["ok"])
    failed = len(results) - passed
    exit_code = 0 if accounts and failed == 0 else 1
    if not accounts:
        final_status = "configuration-error"
    elif dry:
        final_status = "dry-run"
    elif failed == 0:
        final_status = "success"
    elif passed:
        final_status = "partial-failure"
    else:
        final_status = "failure"
    totals = {
        key: sum(item["tasks"][key] for item in results)
        for key in ("success", "already", "skipped", "failure")
    }
    body = (
        "状态：%s；账号总数：%d；成功数：%d；失败数：%d。"
        "子任务：成功 %d，已完成 %d，跳过 %d，失败 %d。"
        % (
            final_status,
            len(accounts),
            passed,
            failed,
            totals["success"],
            totals["already"],
            totals["skipped"],
            totals["failure"],
        )
    )
    if not accounts:
        body += " 配置错误：缺少 JD_COOKIE。"
    if dry:
        body += " 断网预演，未进行真实签到。"
    notification = send_notify(body, dry)
    print("────────────────────────────────")
    log("最终统计 %s；总耗时 %.2fs" % (body, time.monotonic() - started))
    finish_at = now_cn().isoformat(timespec="seconds")
    log(
        "任务结束 完成时间 %s；通知状态 %s；最终状态 %s；退出码 %d"
        % (finish_at, notification, final_status, exit_code)
    )
    summary = {
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "mode": "dry-run" if dry else "live",
        "status": final_status,
        "accounts": len(accounts),
        "success": passed,
        "failure": failed,
        "tasks": totals,
        "results": results,
        "notification": notification,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "exitCode": exit_code,
        "startedAt": start_at,
        "finishedAt": finish_at,
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
