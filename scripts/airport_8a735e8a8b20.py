#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 机场签到（HTM面板）
# cron: 22 2 * * *
# publish-path: scripts/airport_sg_checkin.py
# filename: airport_sg_checkin.py
#
# 发布路径（产品专属，解决 release-path-collision / path-rename-required）：
#   scripts/airport_sg_checkin.py
# 禁止占用 scripts/airport.py（已由其他产品 8cd72e9849a3c893 使用）。
# 禁止回退为通用 main.py / airport.py / index.js。
#
# 上游：ternurarl/Airport-Checkin，main.py
# https://github.com/ternurarl/Airport-Checkin
# 提交：766b0c579ae8448f4cdbf0802b092508b91b767c
# 参考：zhjc1124/ssr_autocheckin（上游 README 声明）
# SPDX-License-Identifier: MIT
# effectiveLicense: MIT
#
# MIT License
# Copyright (c) 2022 小草
# Copyright (c) ternurarl/Airport-Checkin contributors
#
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
"""机场 HTM 面板每日签到（user-login.htm / sg_sign.htm）。

功能清点（相对上游 main.py）：
- 打开面板根地址建立会话
- POST /user-login.htm 使用邮箱与密码登录（字段 email/passwd/code）
- POST /sg_sign.htm 每日签到，按明确 ret 或已知成功/已签文案判定结果
- 多账号：AIRPORT_SG_ACCOUNTS 仅按换行分隔，每非空行一个
  面板根地址|邮箱|密码（仅按前两个 | 分割，密码后续 | 保留）；禁止用 &、@ 分账号
- 兼容单账号 EMAIL + PASSWORD + BASE_URL
- 移除 verify=False、无超时请求、Server酱/Telegram URL 直推与打印原始响应
- 单个账号格式错误独立失败；服务端 msg 仅用于结果分类，不原样输出
- 默认通知按清单选择；QINGLONG_NOTIFY=1 强制开启、0 关闭，auto 使用清单
- AIRPORT_SG_DRY_RUN=1 完全断网预演；青龙 notify 脱敏汇总与 TASK_SUMMARY

面板地址取自本人机场官网地址栏（HTTPS 根地址，不含登录路径）。
邮箱与密码为该站注册账号；不支持验证码/二步验证。
建议 Cron：22 2 * * *（上游未声明计划，按每日签到维护）。
发布文件名必须使用 airport_sg_checkin.py，不得占用通用 airport.py。
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
        _ql_notify_identities = ('8a735e8a8b20c238', 'scripts/airport_8a735e8a8b20.py', 'airport_8a735e8a8b20.py', 'airport_8a735e8a8b20')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch


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
from pathlib import Path

TITLE = "机场签到（HTM面板）"
CATALOG_ID = "8a735e8a8b20c238"
SCRIPT_PATH = "scripts/airport_sg_checkin.py"
ACCOUNTS_ENV = "AIRPORT_SG_ACCOUNTS"
DRY_RUN_ENV = "AIRPORT_SG_DRY_RUN"
DISABLED = {"0", "false", "no", "off"}
ENABLED = {"1", "true", "yes", "on"}
TIMEOUT = 20
MAX_BYTES = 1024 * 1024
ALREADY_MSGS = {
    "您今天已经签到过了",
    "您今天已经签到过了。",
    "您今天已经签到过了...",
    "今天已经签到过了",
    "今天已经签到过了。",
    "今日已签到",
    "今日已签到。",
    "已经签到过了",
    "重复签到",
}


def stamp():
    return datetime.now().strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


def enabled(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    if value == "" and default:
        value = default.strip().lower()
    if value not in ENABLED | DISABLED:
        raise ValueError(f"{name} 必须为 1/0、true/false、yes/no 或 on/off")
    return value in ENABLED


def safe_text(value, secrets):
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c for c in text if c.isprintable() or c in "\n\t")[:240]


def validate_base(url):
    base = (url or "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("面板地址端口无效") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(c.isspace() for c in base)
    ):
        raise ValueError("面板地址须为不含凭据、查询参数或片段的 HTTPS 根地址")
    return base


def validate_email(email):
    text = (email or "").strip()
    if "@" not in text or text.startswith("@") or text.endswith("@") or " " in text:
        raise ValueError("邮箱格式无效")
    return text


def parse_account_line(line):
    text = line.strip()
    if not text:
        raise ValueError("账号行为空")
    if text.startswith("{"):
        item = json.loads(text)
        if not isinstance(item, dict):
            raise ValueError("账号 JSON 须为对象")
        url = item.get("url") or item.get("base_url") or item.get("BASE_URL")
        email = item.get("email") or item.get("EMAIL")
        password = item.get("password") or item.get("passwd") or item.get("PASSWORD")
        if not all(isinstance(v, str) and v.strip() for v in (url, email, password)):
            raise ValueError("账号 JSON 须含 url、email、password")
        return validate_base(url), validate_email(email), password
    parts = text.split("|", 2)
    if len(parts) != 3 or not parts[0].strip() or not parts[1].strip() or not parts[2]:
        raise ValueError("账号行须为 面板根地址|邮箱|密码，或含 url/email/password 的 JSON")
    return validate_base(parts[0]), validate_email(parts[1]), parts[2]


def load_accounts():
    # 多账号仅允许换行分隔（newline）；同一行内的 | 只用于字段，&/@ 不作账号分隔符。
    raw = os.getenv(ACCOUNTS_ENV, "")
    lines = [line for line in raw.splitlines() if line.strip()]
    accounts = []
    if lines:
        for line in lines:
            try:
                accounts.append(parse_account_line(line))
            except (ValueError, TypeError, AttributeError):
                # 不回显解析异常；JSON 错误可能包含凭据原文。
                accounts.append(None)
        return accounts
    email = os.getenv("EMAIL", "").strip()
    password = os.getenv("PASSWORD", "")
    base = os.getenv("BASE_URL", "").strip()
    if not email and not password and not base:
        raise ValueError(
            f"请设置 {ACCOUNTS_ENV}（每非空行一个账号：面板根地址|邮箱|密码；"
            "仅换行分账号），或兼容单账号 EMAIL、PASSWORD、BASE_URL"
        )
    if not email or not password or not base:
        raise ValueError("兼容单账号时须同时设置 EMAIL、PASSWORD、BASE_URL")
    try:
        return [(validate_base(base), validate_email(email), password)]
    except ValueError:
        return [None]


class SafeError(Exception):
    """仅包含可公开的固定错误信息。"""


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port):
            raise SafeError("拒绝跨站重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, base):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar),
            SameOriginRedirect(),
        )

    def request(self, path="", data=None, referer=None, expect_json=False, method=None):
        url = self.base + path
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36 QinglongAirportSG/1.0"
            )
        }
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        elif method and method.upper() == "POST":
            # 无表单字段时仍发空 POST，对齐上游 session.post('/sg_sign.htm')。
            body = b""
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise SafeError(f"HTTP 状态异常（{response.status}）")
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise SafeError("响应超出大小限制")
            text = raw.decode("utf-8", errors="replace")
            if not expect_json:
                return text
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise SafeError("接口响应不是 JSON 对象")
            return payload
        except SafeError:
            raise
        except urllib.error.HTTPError as error:
            raise SafeError(f"HTTP 请求失败（状态 {error.code}）") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SafeError("网络、超时或证书校验失败") from None
        except (ValueError, UnicodeError, json.JSONDecodeError):
            raise SafeError("接口返回无效 JSON") from None


def show_identity(payload, secrets):
    containers = [payload]
    for key in ("user", "data"):
        if isinstance(payload.get(key), dict):
            containers.append(payload[key])
    for container in containers:
        for key in ("nickname", "username", "display_name", "displayName", "uid", "public_uid"):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (
                not value
                or len(value) > 100
                or "@" in value
                or any(secret and secret in value for secret in secrets)
                or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value)
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
            ):
                continue
            log(f"官方账号身份（{key}）：{value}")
            return


def login_ok(payload):
    if not isinstance(payload, dict):
        return False
    if "ret" in payload:
        return payload["ret"] is True or payload["ret"] in (1, "1")
    msg = str(payload.get("msg", "")).strip()
    if any(word in msg for word in ("失败", "错误", "无效", "不正确", "不存在", "验证码", "未登录")):
        return False
    return msg in ("登录成功", "登录成功。", "登陆成功", "登陆成功。") or payload.get("result") in (True, 1, "1", "success")


def classify_checkin(payload):
    msg = str(payload.get("msg", "")).strip()
    ret = payload.get("ret")
    # 禁止把“未获得”“尚未签到”等失败提示当成成功。
    if any(word in msg for word in ("失败", "错误", "无效", "未登录", "尚未", "未获得", "未签到")):
        return "failure", "签到业务未确认成功"
    if msg in ALREADY_MSGS:
        return "alreadyComplete", "今日签到已完成"
    if ret is True or ret in (1, "1"):
        return "success", "签到已验证成功"
    if ret is None and msg in ("签到成功", "签到成功。", "签到完成", "签到完成。"):
        return "success", "签到已验证成功"
    return "failure", "签到业务未确认成功"


def run_account(index, base, email, password, dry):
    started = time.monotonic()
    stats = {
        "total": 3,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    secrets = [email, password, base]
    status = "failure"
    log(f"账号 {index} 开始")
    steps = ("初始化面板会话", "登录账号", "每日签到")
    client = None
    for stage, title in enumerate(steps, 1):
        tick = time.monotonic()
        log(f"账号 {index} 阶段 {stage}/3：{title}")
        try:
            if stage == 1:
                if not email or not password:
                    raise SafeError("账号配置无效：须为有效邮箱与非空密码")
                if dry:
                    stats["skipped"] += 1
                    log(f"⏭️ 断网预演：{title}已模拟；耗时 {time.monotonic() - tick:.2f} 秒")
                    continue
                client = Client(base)
                client.request("", expect_json=False)
                stats["success"] += 1
                log(f"✅ {title}成功；耗时 {time.monotonic() - tick:.2f} 秒")
                continue
            if dry:
                stats["skipped"] += 1
                log(f"⏭️ 断网预演：{title}请求已模拟；耗时 {time.monotonic() - tick:.2f} 秒")
                continue
            if stage == 2:
                assert client is not None
                login_url = base + "/user-login.htm"
                # 只发一次登录请求：JSON 则校验 ret/msg；HTML/非 JSON 交给后续签到结果闭合。
                text = client.request(
                    "/user-login.htm",
                    {"email": email, "passwd": password, "code": ""},
                    referer=login_url,
                    expect_json=False,
                )
                payload = None
                stripped = text.lstrip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        parsed = json.loads(text)
                    except (ValueError, TypeError):
                        parsed = None
                    if not isinstance(parsed, dict):
                        raise SafeError("登录接口返回无效 JSON 对象")
                    if isinstance(parsed, dict):
                        payload = parsed
                        if not login_ok(payload):
                            raise SafeError("登录业务未确认成功")
                        show_identity(payload, secrets)
                if payload is None:
                    log(f"⏭️ 登录响应未提供可验证 JSON，等待签到结果确认；耗时 {time.monotonic() - tick:.2f} 秒")
                    stats["skipped"] += 1
                else:
                    stats["success"] += 1
                    log(f"✅ {title}成功；耗时 {time.monotonic() - tick:.2f} 秒")
                continue
            assert client is not None
            payload = client.request(
                "/sg_sign.htm",
                data=None,
                referer=base + "/user-login.htm",
                expect_json=True,
                method="POST",
            )
            show_identity(payload, secrets)
            outcome, msg = classify_checkin(payload)
            detail = safe_text(msg, secrets) if msg else ""
            if outcome == "success":
                stats["success"] += 1
                log(
                    f"✅ 签到已验证成功"
                    + (f"：{detail}" if detail else "")
                    + f"；耗时 {time.monotonic() - tick:.2f} 秒"
                )
            elif outcome == "alreadyComplete":
                stats["alreadyComplete"] += 1
                log(
                    f"☑️ 今日签到已完成"
                    + (f"：{detail}" if detail else "")
                    + f"；耗时 {time.monotonic() - tick:.2f} 秒"
                )
            else:
                raise SafeError("签到业务未确认成功（ret/msg 未通过校验）")
        except Exception as error:
            stats["failed"] += 1
            remaining = 3 - stage
            stats["skipped"] += remaining
            message = (
                str(error)
                if isinstance(error, (SafeError, ValueError))
                else "请求处理失败，异常详情已隐藏"
            )
            log(f"❌ {message}；耗时 {time.monotonic() - tick:.2f} 秒")
            if remaining:
                log(f"⏭️ 后续 {remaining} 个阶段因前置失败跳过")
            status = "failure"
            break
    else:
        status = "dry-run" if dry else "success"
    stats["seconds"] = round(time.monotonic() - started, 2)
    log(
        f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {stats['seconds']:.2f} 秒；状态 {status}"
    )
    return {"account": index, "status": status, **stats}


def notification_enabled():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in DISABLED:
        return False
    if switch in ENABLED:
        return True
    if switch != "auto":
        log("⚠️ QINGLONG_NOTIFY 值无效，按自动选择处理")
    selection = os.getenv("QINGLONG_NOTIFY_SCRIPTS", "")
    selectors = [part.lower() for part in re.split(r"[,;\s]+", selection) if part]
    identities = (CATALOG_ID, SCRIPT_PATH, Path(SCRIPT_PATH).name,
                  Path(__file__).name, "output/candidate.py")
    return any(fnmatch.fnmatch(identity.lower(), selector)
               for selector in selectors for identity in identities)


def notify_summary(body, dry):
    if not notification_enabled():
        log("⏭️ 通知已由 QINGLONG_NOTIFY 关闭")
        return "disabled"
    if dry:
        log("通知预演：" + body)
        return "断网预演（未发送）"
    candidates = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        candidates.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    candidates.extend(
        [
            Path(__file__).resolve().parent / "notify.py",
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            candidates.insert(0, Path(spec.origin))
    except (ImportError, ValueError):
        pass
    for path in candidates:
        if not path.is_file():
            continue
        try:
            adapter = (
                "import importlib.util,json,sys;"
                "s=importlib.util.spec_from_file_location('notify',sys.argv[1]);"
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m);"
                "v=json.load(sys.stdin); m.send(v['title'],v['body'])"
            )
            subprocess.run(
                [sys.executable, "-c", adapter, str(path)],
                input=json.dumps({"title": TITLE, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=25,
                check=True,
            )
            log("✅ 青龙通知已提交")
            return "已调用青龙通知"
        except (OSError, subprocess.SubprocessError):
            log("⚠️ 青龙通知发送失败，保留业务退出码")
            return "通知失败（不改变业务退出码）"
    log("⚠️ 未找到青龙 notify.py，保留业务退出码")
    return "未找到青龙 notify.py（不改变业务退出码）"


def main():
    started = time.monotonic()
    start = datetime.now().isoformat(timespec="seconds")
    log(f"========== {TITLE} ==========")
    log(f"脚本路径：{SCRIPT_PATH}")
    log(f"开始时间：{start}")
    dry = False
    accounts = []
    results = []
    config_error = False
    try:
        dry = enabled(DRY_RUN_ENV)
        log("运行模式：断网预演" if dry else "运行模式：正式签到")
        log("阶段 1：校验配置")
        accounts = load_accounts()
        log(f"账号总数：{len(accounts)}")
        for index, account in enumerate(accounts, 1):
            if account is None:
                log(f"账号 {index} 阶段 1/3：校验账号配置；耗时 0.00 秒")
                log("❌ 账号配置无效：检查 HTTPS 面板地址、邮箱和密码，或 JSON 字段类型；后续两阶段跳过")
                item = {"account": index, "status": "failure", "total": 3,
                        "success": 0, "alreadyComplete": 0, "skipped": 2,
                        "failed": 1, "seconds": 0.0}
                results.append(item)
                log(f"账号 {index} 统计：总任务 3，成功 0，已完成 0，跳过 2，失败 1，耗时 0.00 秒；状态 failure")
                continue
            base, email, password = account
            results.append(run_account(index, base, email, password, dry))
    except Exception as error:
        config_error = True
        message = "配置处理失败，请检查环境变量格式和必填项"
        log(f"❌ 配置错误：{message}")
        log(f"账号总数：{len(accounts)}")
    failed = sum(1 for item in results if item["status"] == "failure")
    passed = len(results) - failed
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and passed
        else "failure"
        if failed
        else "dry-run"
        if dry
        else "success"
    )
    code = 1 if config_error or failed else 0
    body = (
        f"状态：{status}；账号总数：{len(accounts)}；"
        f"成功数：{0 if dry else passed}；失败数：{failed}；"
        f"预演通过数：{passed if dry else 0}；配置错误：{int(config_error)}"
    )
    log("阶段 2：发送脱敏通知")
    notification = notify_summary(body, dry)
    finish = datetime.now().isoformat(timespec="seconds")
    task_stats = {
        key: sum(item[key] for item in results)
        for key in ("total", "success", "alreadyComplete", "skipped", "failed")
    }
    log("----------------------------------------")
    log(body)
    log(
        f"子任务统计：总数 {task_stats['total']}，成功 {task_stats['success']}，"
        f"已完成 {task_stats['alreadyComplete']}，跳过 {task_stats['skipped']}，"
        f"失败 {task_stats['failed']}"
    )
    log(
        f"完成时间：{finish}；总耗时：{time.monotonic() - started:.2f} 秒；"
        f"通知状态：{notification}"
    )
    log(f"最终状态：{status}；退出码：{code}")
    summary = {
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "scriptPath": SCRIPT_PATH,
        "status": status,
        "mode": "dry-run" if dry else "live",
        "accountCount": len(accounts),
        "successCount": 0 if dry else passed,
        "failureCount": failed,
        "dryRunCount": passed if dry else 0,
        "configurationError": config_error,
        "stages": task_stats,
        "accounts": results,
        "notification": notification,
        "startTime": start,
        "finishTime": finish,
        "seconds": round(time.monotonic() - started, 2),
        "exitCode": code,
    }
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
