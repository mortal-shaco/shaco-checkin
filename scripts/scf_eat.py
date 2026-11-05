#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: eatASMR每日签到
# cron: 37 8 * * *
#
# 来源：trojblue/TSDM-coin-farmer dist/SCF_eat.py（GPL-3.0）
# https://github.com/trojblue/TSDM-coin-farmer
# 提交：f2d93d01564a09ee996ee6a673c572f8743c6cd6
# SPDX-License-Identifier: GPL-3.0-only
#
# 本维护版沿用上游 GPL-3.0 许可。
# Copyright (C) trojblue / TSDM-coin-farmer contributors
# 你可以通过自由软件基金会发布的 GNU 通用公共许可证第 3 版（或你选择的任何后续版本）
# 重新分发和/或修改本程序。本程序的分发希望它有用，但不提供任何担保。
# 完整许可证文本见上游仓库 LICENSE。
#
"""eatASMR（eatasmr.com）每日任务签到 - 青龙维护版。

功能清点（相对上游 SCF_eat.py）：
- 使用已登录 Cookie 访问 https://eatasmr.com/tasks/attendance
- 从页面提取 /tasks/attendance?a=check&__v= 后的校验参数并 POST 签到
- 依据登录态、签到按钮是否存在、响应文案核验“签到成功 / 今日已签到”
- 展示页面公开昵称（若返回）以便核对账号
- 移除 cookies.json 读写、错误 Cookie 头字段 cookie_list、无超时请求与原始响应打印
- 相关同源脚本（TSDM 签到/打工、S1 刷在线）属于不同站点与凭据边界，保持独立，不合并
- 增加逐行多账号、EATASMR_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

EATASMR_COOKIE：每个非空行一个已登录 Cookie（浏览器请求头中的完整 Cookie 值）。
兼容别名 EAT_COOKIE / EATASMR_COOKIES（仅当规范变量为空时生效）。
可选账号备注：备注|Cookie，仅按第一个 | 分割，右侧 Cookie 原样保留。
EATASMR_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
EATASMR_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：15 8 * * *。不打印 Cookie、Token、会话值或原始响应。
本脚本不发布帖子、评论或分享文字。
"""
from __future__ import annotations

# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re

if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "e2ef382ec73c4e6d",
            "scripts/eatasmr_checkin.py",
            "eatasmr_checkin.py",
            "SCF_eat.py",
            "candidate.py",
            "eatasmr_attendance",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TITLE = "eatASMR每日签到"
CATALOG_ID = "e2ef382ec73c4e6d"
HOST = "eatasmr.com"
BASE = "https://eatasmr.com"
ATTENDANCE_URL = BASE + "/tasks/attendance"
SIGN_URL_PREFIX = BASE + "/tasks/attendance?a=check&__v="
CHECK_MARKER = "/tasks/attendance?a=check&__v="
LOGIN_OK_HINT = "过去30天中, 我连续签到了"
DEFAULT_TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SUCCESS_HINTS = (
    "签到成功",
    "簽到成功",
    "打卡成功",
    "连续签到",
    "連續簽到",
    LOGIN_OK_HINT,
)
ALREADY_HINTS = (
    "今日已签到",
    "今日已簽到",
    "今天已经签到",
    "今天已經簽到",
    "您今日已经签到",
    "已经签到过",
    "已經簽到",
    "请勿重复签到",
    "請勿重複簽到",
    "已签到",
    "已簽到",
)
LOGIN_FAIL_HINTS = (
    "🔑 登錄",
    "🔑 登录",
    ">登錄</",
    ">登录</",
    "请先登录",
    "請先登錄",
    "需要登录",
    "需要登錄",
    "/login",
    "action=login",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
# URL-encoded “簽到”
SIGN_FORM_BODY = "check=%E7%B0%BD%E5%88%B0"


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def resolve_timeout() -> float:
    raw = env("EATASMR_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("EATASMR_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("EATASMR_TIMEOUT 须在 5 到 60 秒之间")
    return value


def validate_cookie(cookie: str) -> str:
    text = cookie.strip()
    if not text:
        raise SafeError("Cookie 为空")
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    if "=" not in text:
        raise SafeError("Cookie 格式错误：缺少键值对")
    if any(ord(ch) < 32 for ch in text):
        raise SafeError("Cookie 含非法控制字符")
    try:
        text.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise SafeError("Cookie 含非 Latin-1 字节，请使用浏览器原始 Cookie 头") from exc
    return text


def parse_account_line(line: str) -> str:
    text = line.strip()
    if "|" in text:
        label, rest = text.split("|", 1)
        if label.strip() and "=" not in label and rest.strip():
            return validate_cookie(rest)
    return validate_cookie(text)


def load_accounts() -> List[str]:
    raw = env("EATASMR_COOKIE")
    source = "EATASMR_COOKIE"
    if not raw:
        for alias in ("EAT_COOKIE", "EATASMR_COOKIES"):
            raw = env(alias)
            if raw:
                source = alias
                break
    if not raw:
        raise SafeError(
            "未配置凭据：请设置 EATASMR_COOKIE（每行一个 Cookie）；"
            "兼容别名 EAT_COOKIE / EATASMR_COOKIES"
        )
    accounts: List[str] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    if not accounts:
        raise SafeError("{} 中没有有效账号行".format(source))
    return accounts


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.netloc.lower() not in {
            HOST,
            "www." + HOST,
        }:
            raise SafeError("拒绝跨站或不安全重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, cookie: str, timeout: float) -> None:
        self.cookie = cookie
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            SameHostRedirect(),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )

    def _headers(self, *, content_type: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": ATTENDANCE_URL,
            "Origin": BASE,
            "Connection": "close",
            "Cookie": self.cookie,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def request(self, url: str, *, data: Optional[bytes] = None) -> str:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {
            HOST,
            "www." + HOST,
        }:
            raise SafeError("拒绝访问非目标站点地址")
        method = "POST" if data is not None else "GET"
        request = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(
                content_type="application/x-www-form-urlencoded" if data is not None else None
            ),
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                if int(status) < 200 or int(status) >= 300:
                    raise SafeError("HTTP 状态异常")
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise SafeError("响应过大")
                charset = response.headers.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raise SafeError("HTTP 请求失败（状态 {}）".format(exc.code)) from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络请求失败或超时") from exc
        except TimeoutError as exc:
            raise SafeError("网络请求超时") from exc
        except Exception as exc:
            raise SafeError("请求过程异常") from exc


def extract_identity(page: str, cookie: str) -> Optional[str]:
    patterns = (
        r'class=["\'][^"\']*username[^"\']*["\'][^>]*>(.*?)</',
        r'class=["\'][^"\']*display-name[^"\']*["\'][^>]*>(.*?)</',
        r'itemprop=["\']name["\'][^>]*>(.*?)</',
        r'欢迎[您你]，?\s*([^<>\r\n]{1,40})',
        r'您好[，,]\s*([^<>\r\n]{1,40})',
        r'<a\b[^>]*href=["\'][^"\']*/(?:u|user|member|profile)[^"\']*["\'][^>]*>(.*?)</a>',
    )
    secrets = [cookie]
    for part in cookie.split(";"):
        if "=" in part:
            value = part.split("=", 1)[1].strip()
            if len(value) >= 4:
                secrets.append(value)
    phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    for pattern in patterns:
        match = re.search(pattern, page, re.I | re.S)
        if not match:
            continue
        name = plain(match.group(1))
        if not name or len(name) > 40:
            continue
        if any(secret and secret in name for secret in secrets):
            continue
        if phone.search(name):
            continue
        if re.search(r"cookie|token|session|password|登录|登錄|签到|簽到", name, re.I):
            continue
        return name
    return None


def looks_logged_in(page: str) -> bool:
    if LOGIN_OK_HINT in page:
        return True
    if CHECK_MARKER in page:
        return True
    fail_hits = sum(1 for hint in LOGIN_FAIL_HINTS if hint in page)
    return fail_hits == 0 and ("attendance" in page.lower() or "签到" in page or "簽到" in page)


def looks_logged_out(page: str) -> bool:
    if LOGIN_OK_HINT in page or CHECK_MARKER in page:
        return False
    return sum(1 for hint in LOGIN_FAIL_HINTS if hint in page) >= 1


def extract_form_token(page: str) -> Optional[str]:
    match = re.search(
        r"/tasks/attendance\?a=check&__v=([0-9A-Za-z_-]{6,32})",
        page,
    )
    if match:
        return match.group(1)
    # 兼容上游固定偏移截取（校验串通常 10 位）
    anchor = page.find(CHECK_MARKER)
    if anchor < 0:
        return None
    start = anchor + len(CHECK_MARKER)
    token = page[start : start + 16]
    token = re.split(r'[^0-9A-Za-z_-]', token, maxsplit=1)[0]
    if 6 <= len(token) <= 32:
        return token
    return None


def classify_sign_response(page: str, *, had_check_button: bool) -> str:
    haystack = plain(page[:4000])
    for hint in ALREADY_HINTS:
        if hint in haystack or hint in page:
            return "alreadyComplete"
    still_has_button = CHECK_MARKER in page and extract_form_token(page)
    for hint in SUCCESS_HINTS:
        if hint in haystack or hint in page:
            if still_has_button and had_check_button and hint == LOGIN_OK_HINT:
                # 仅连续签到文案且仍有签到按钮，视为未完成
                continue
            if still_has_button and hint not in ALREADY_HINTS:
                continue
            return "success"
    if LOGIN_OK_HINT in page and not still_has_button:
        return "alreadyComplete" if not had_check_button else "success"
    if still_has_button:
        raise SafeError("签到后仍存在签到入口，未能核验成功")
    if looks_logged_out(page):
        raise SafeError("签到后登录态失效，请重新获取 Cookie")
    raise SafeError("响应未包含可核验的签到成功或已签到消息")


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "SCF_eat.py",
        "eatasmr_checkin.py",
        "candidate.py",
        "scripts/eatasmr_checkin.py",
        "eatasmr_attendance",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    if dry_run:
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


class AccountResult:
    def __init__(self, number: int) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""


def run_account(
    result: AccountResult, cookie: str, timeout: float, dry_run: bool
) -> None:
    stages = [
        (1, "读取签到页及账号身份"),
        (2, "执行签到"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项".format(
            result.number, total_stages
        )
    )
    need_sign = False
    form_token = ""
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total_stages, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                client = Client(cookie, timeout)
                page = client.request(ATTENDANCE_URL)
                if looks_logged_out(page) or not looks_logged_in(page):
                    raise SafeError("未登录或 Cookie 已失效，请重新获取")
                nickname = extract_identity(page, cookie)
                if nickname:
                    result.identity = nickname
                    log("账号 {} 官方昵称：{}".format(result.number, nickname))
                else:
                    log("账号 {}：页面未返回公开昵称，使用序号标识".format(result.number))
                token = extract_form_token(page)
                if token:
                    need_sign = True
                    form_token = token
                    log("检测到签到入口，待提交签到")
                else:
                    need_sign = False
                    if LOGIN_OK_HINT in page or any(h in page for h in ALREADY_HINTS):
                        log(
                            "{} 页面无签到入口，视为今日已签到".format(
                                ICONS["alreadyComplete"]
                            )
                        )
                    else:
                        raise SafeError("已登录但未找到签到入口，页面结构可能已变更")
                result.stats["success"] += 1
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                if not need_sign:
                    result.stats["alreadyComplete"] += 1
                    result.message = "今日已签到（无签到入口）"
                    result.status = "alreadyComplete"
                    log("{} {}".format(ICONS["alreadyComplete"], result.message))
                    log(
                        "{} 阶段完成；耗时 {:.2f} 秒".format(
                            ICONS["alreadyComplete"], time.monotonic() - tick
                        )
                    )
                    continue
                client = Client(cookie, timeout)
                sign_url = SIGN_URL_PREFIX + form_token
                response = client.request(
                    sign_url, data=SIGN_FORM_BODY.encode("ascii")
                )
                outcome = classify_sign_response(response, had_check_button=True)
                if outcome == "alreadyComplete":
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    result.message = "今日已签到"
                    log("{} {}".format(ICONS["alreadyComplete"], result.message))
                else:
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = "签到成功"
                    log("{} {}".format(ICONS["success"], result.message))
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total_stages
                    )
                )
            result.status = "failure"
            result.message = str(error)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    str(error),
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
            result.message = "未预期本地错误"
            log(
                "{} 账号 {} 阶段 {} 失败：未预期本地错误，详情已抑制；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    time.monotonic() - tick,
                )
            )
            return
    if dry_run:
        result.status = "dry-run"
        result.stats["success"] = 0
    elif result.status not in {"success", "alreadyComplete"}:
        if result.stats["failure"] == 0 and result.stats["alreadyComplete"] == 0:
            result.status = "success"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total_stages,
            result.stats["success"],
            result.stats["alreadyComplete"],
            result.stats["skipped"],
            result.stats["failure"],
            elapsed,
        )
    )


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("EATASMR_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[str] = []
    timeout = float(DEFAULT_TIMEOUT)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("EATASMR_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, cookie in enumerate(accounts_data, 1):
            account = AccountResult(number)
            results.append(account)
            run_account(account, cookie, timeout, dry_run)
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in results if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in results if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in results if item.status == "failure"),
        "dry-run": sum(1 for item in results if item.status == "dry-run"),
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(item.stats[key] for item in results) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
