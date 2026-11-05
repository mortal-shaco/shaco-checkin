#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 奥波莱大学Moodle作业监控
# cron: */5 * * * *
#
# 来源：Anav0/uo-moodle-notifier main.py（GPL-3.0-only）
# https://gitlab.com/Anav0/uo-moodle-notifier
# 提交：d5fd430e7515f13157eb034ee7ea097439fb7dd9
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) Anav0 and contributors
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See the LICENSE file distributed
# with the upstream project for the full text of the GPL-3.0 license.
#
"""奥波莱大学 Moodle 课程作业变更监控 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用 Moodle 账号登录固定站点 moodle.math.uni.opole.pl（可用环境变量覆盖基址）
- 读取指定课程页上的作业（assign）活动列表
- 与本地缓存的作业 ID 集合比较，检测新增或移除
- 变更时输出作业短列表并通过青龙通知推送脱敏摘要
- 将当前作业 ID 写入本地状态文件，供下次定时运行对比
- 移除交互式 getpass、桌面 notify-send、无限轮询 sleep、无超时请求与原始页面打印
- 改为青龙 Cron 单次检查、逐行多账号、UO_MOODLE_DRY_RUN 断网预演、
  标准库 HTTPS、时间轴日志、青龙通知与 TASK_SUMMARY

UO_MOODLE_ACCOUNTS：每个非空行一个账号，格式
username|password|course_id；先按最后一个 | 取出课程 ID，再按第一个 |
分割用户名与密码，密码中后续 | 原样保留。
兼容单账号别名：UO_MOODLE_USERNAME + UO_MOODLE_PASSWORD + UO_MOODLE_COURSE_ID
（仅当规范变量为空时生效）。
UO_MOODLE_BASE_URL：Moodle 根地址，默认 https://moodle.math.uni.opole.pl
UO_MOODLE_STATE_DIR：作业 ID 缓存目录，默认脚本旁 uo_moodle_state
UO_MOODLE_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60
UO_MOODLE_DRY_RUN=1：完全断网预演，只校验配置与流程，不发起网络请求、不写状态
建议 Cron：*/5 * * * *（对应上游默认约 5 分钟检查一次）。
不打印密码、Cookie、Token、会话值或原始响应。
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
            "6bed5fef3c9bac1c",
            "scripts/uo_moodle_notifier.py",
            "uo_moodle_notifier.py",
            "candidate.py",
            "output/candidate.py",
            "main.py",
            "uo_moodle_notifier",
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
import http.cookiejar
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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TITLE = "奥波莱大学Moodle作业监控"
CATALOG_ID = "6bed5fef3c9bac1c"
ACCOUNTS_ENV = "UO_MOODLE_ACCOUNTS"
DRY_RUN_ENV = "UO_MOODLE_DRY_RUN"
TIMEOUT_ENV = "UO_MOODLE_TIMEOUT"
BASE_URL_ENV = "UO_MOODLE_BASE_URL"
STATE_DIR_ENV = "UO_MOODLE_STATE_DIR"
DEFAULT_BASE_URL = "https://moodle.math.uni.opole.pl"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
STATES = ("success", "alreadyComplete", "skipped", "failure")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) "
    "Gecko/20100101 Firefox/137.0"
)
LOGIN_TOKEN_RE = re.compile(r'name="logintoken"\s+value="([^"]+)"', re.I)
ASSIGN_RE = re.compile(
    r'<li class="activity assign modtype_assign\s*"[^>]*>.*?'
    r'(https?://[^"\']+/mod/assign/view\.php\?id=(\d+))".*?'
    r'<span class="instancename">(.*?)<span',
    re.I | re.S,
)
COURSE_NAME_RE = re.compile(
    r'class="page-header-headings"><h1>(.*?)</h1>',
    re.I | re.S,
)
IDENTITY_RE = re.compile(
    r'(?:id="action-menu-toggle-\d+"[^>]*>\s*<span[^>]*>\s*([^<]{1,64})\s*</span>)'
    r'|(?:class="[^"]*usertext[^"]*"[^>]*>\s*([^<]{1,64}))'
    r'|(?:logininfo[^>]*>.*?>([^<]{1,64}))',
    re.I | re.S,
)
COOKIE_CONSENT_HINT = "Przyjmowanie cookies"
LOGIN_FAIL_HINTS = (
    "logintoken",
    "invalidlogin",
    "loginerrors",
    "errormessage",
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


class Assignment:
    def __init__(self, assign_id: str, name: str, link: str) -> None:
        self.id = assign_id
        self.name = plain(name)
        self.link = link

    def short(self) -> str:
        return "{} {}".format(self.id, self.name)


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def redact(text: str, secrets: List[str]) -> str:
    result = str(text or "")
    for secret in sorted(
        {item for item in secrets if item and len(item) >= 4},
        key=len,
        reverse=True,
    ):
        result = result.replace(secret, "[已脱敏]")
    return result


def resolve_timeout() -> float:
    raw = env(TIMEOUT_ENV)
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("{} 须为数字秒数".format(TIMEOUT_ENV)) from exc
    if value < 5 or value > 60:
        raise SafeError("{} 须在 5 到 60 秒之间".format(TIMEOUT_ENV))
    return value


def resolve_base_url() -> str:
    raw = env(BASE_URL_ENV, DEFAULT_BASE_URL).rstrip("/")
    if not raw:
        raise SafeError("{} 不能为空".format(BASE_URL_ENV))
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SafeError("{} 须为 https:// 开头的 Moodle 根地址".format(BASE_URL_ENV))
    return raw


def resolve_state_dir() -> Path:
    raw = env(STATE_DIR_ENV)
    if raw:
        path = Path(raw).expanduser()
    else:
        path = Path(__file__).resolve().parent / "uo_moodle_state"
    return path


def parse_account_line(line: str) -> Dict[str, str]:
    text = line.strip()
    if "|" not in text:
        raise SafeError(
            "账号行须为 username|password|course_id（密码可含 |，课程 ID 在末段）"
        )
    left, course_id = text.rsplit("|", 1)
    course_id = course_id.strip()
    if not course_id or not course_id.isdigit():
        raise SafeError("课程 ID 须为正整数字符串")
    if "|" not in left:
        raise SafeError("账号行缺少密码字段，格式 username|password|course_id")
    username, password = left.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username:
        raise SafeError("用户名不能为空")
    if not password:
        raise SafeError("密码不能为空")
    return {
        "username": username,
        "password": password,
        "course_id": course_id,
        "label": "{}#{}".format(username, course_id),
    }


def load_accounts() -> List[Dict[str, str]]:
    raw = os.environ.get(ACCOUNTS_ENV, "")
    accounts: List[Dict[str, str]] = []
    if raw.strip():
        for line in raw.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            accounts.append(parse_account_line(text))
        if not accounts:
            raise SafeError("{} 仅含空行或注释，未解析到账号".format(ACCOUNTS_ENV))
        return accounts

    username = env("UO_MOODLE_USERNAME")
    password = env("UO_MOODLE_PASSWORD")
    course_id = env("UO_MOODLE_COURSE_ID")
    if username or password or course_id:
        if not (username and password and course_id):
            raise SafeError(
                "兼容别名须同时提供 UO_MOODLE_USERNAME、"
                "UO_MOODLE_PASSWORD、UO_MOODLE_COURSE_ID"
            )
        return [
            parse_account_line("{}|{}|{}".format(username, password, course_id))
        ]
    raise SafeError(
        "未配置账号：请设置 {}，每行 username|password|course_id".format(ACCOUNTS_ENV)
    )


def state_file_for(course_id: str, state_dir: Path) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", course_id)
    return state_dir / "course-{}.txt".format(safe)


def read_ids(path: Path) -> List[str]:
    if not path.is_file():
        return []
    ids: List[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        item = line.strip()
        if item:
            ids.append(item)
    return ids


def write_ids(path: Path, ids: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = os.linesep.join(ids) + (os.linesep if ids else "")
    path.write_text(content, encoding="utf-8")


def ids_differ(left: List[str], right: List[str]) -> bool:
    return set(left) != set(right)


class MoodleClient:
    def __init__(self, base_url: str, timeout: float, secrets: List[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.secrets = secrets
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        req_headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            req_headers.update(headers)
        request = urllib.request.Request(
            url, data=data, headers=req_headers, method=method
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise SafeError("响应过大，已中止解析")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                final_url = response.geturl()
                return int(response.status), final_url, text
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_BYTES + 1) if exc.fp else b""
            if len(raw) > MAX_BYTES:
                raise SafeError("HTTP {} 且响应过大".format(exc.code)) from exc
            text = raw.decode("utf-8", errors="replace")
            return int(exc.code), exc.geturl() if hasattr(exc, "geturl") else url, text
        except urllib.error.URLError as exc:
            raise SafeError(
                "网络错误：{}".format(redact(str(exc.reason), self.secrets))
            ) from exc
        except Exception as exc:
            raise SafeError(
                "请求失败：{}".format(redact(str(exc), self.secrets))
            ) from exc

    def get(self, path_or_url: str) -> Tuple[int, str, str]:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else self.base_url + path_or_url
        )
        return self._request("GET", url)

    def post_form(self, url: str, payload: Dict[str, str]) -> Tuple[int, str, str]:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        return self._request(
            "POST",
            url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
        )

    def login(self, username: str, password: str) -> None:
        login_url = self.base_url + "/login/index.php"
        status, _, login_html = self.get(login_url)
        if status >= 400:
            raise SafeError("登录页 HTTP {}".format(status))
        tokens = LOGIN_TOKEN_RE.findall(login_html)
        if not tokens:
            raise SafeError("未能从登录页提取 logintoken")
        payload = {
            "anchor": "",
            "username": username,
            "password": password,
            "logintoken": tokens[0],
        }
        status, final_url, text = self.post_form(login_url, payload)
        if status >= 400:
            raise SafeError("登录请求 HTTP {}".format(status))
        lowered = text.lower()
        if "logintoken" in lowered and (
            "invalidlogin" in lowered
            or "loginerrors" in lowered
            or "/login/index.php" in final_url
        ):
            raise SafeError("登录失败：用户名或密码无效，或站点拒绝会话")
        if COOKIE_CONSENT_HINT in text:
            # 部分会话仍提示 Cookie 同意页，再尝试一次登录刷新会话
            status, final_url, text = self.post_form(login_url, payload)
            if status >= 400:
                raise SafeError("Cookie 同意后重登 HTTP {}".format(status))
            if "logintoken" in text.lower() and "/login/index.php" in final_url:
                raise SafeError("登录后仍停留在登录页")

    def course_page(self, course_id: str) -> Tuple[str, str]:
        url = self.base_url + "/course/view.php?id={}".format(course_id)
        status, final_url, text = self.get(url)
        if status >= 400:
            raise SafeError("课程页 HTTP {}".format(status))
        if COOKIE_CONSENT_HINT in text or (
            "logintoken" in text.lower() and "/login/index.php" in final_url
        ):
            raise SafeError("会话失效，课程页要求重新登录")
        return final_url, text


def extract_course_name(html_text: str) -> str:
    match = COURSE_NAME_RE.search(html_text or "")
    if not match:
        return ""
    return plain(match.group(1))


def extract_identity(html_text: str, secrets: List[str]) -> str:
    match = IDENTITY_RE.search(html_text or "")
    if not match:
        return ""
    value = next((group for group in match.groups() if group), "")
    value = plain(value)
    value = redact(value, secrets)
    if not value or value in {"登录", "Log in", "Guest", "游客"}:
        return ""
    return value[:64]


def search_assignments(html_text: str, base_url: str) -> List[Assignment]:
    found: List[Assignment] = []
    for link, assign_id, name in ASSIGN_RE.findall(html_text or ""):
        if not link.startswith("http"):
            link = base_url.rstrip("/") + "/" + link.lstrip("/")
        found.append(Assignment(assign_id, name, link))
    # 去重保序
    seen = set()
    unique: List[Assignment] = []
    for item in found:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique.append(item)
    return unique


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
        "main.py",
        "uo_moodle_notifier.py",
        "candidate.py",
        "scripts/uo_moodle_notifier.py",
        "uo_moodle_notifier",
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
    def __init__(self, number: int, label: str) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.label = label
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""
        self.changed = False
        self.assignment_count = 0


def run_account(
    result: AccountResult,
    account: Dict[str, str],
    base_url: str,
    state_dir: Path,
    timeout: float,
    dry_run: bool,
) -> None:
    username = account["username"]
    password = account["password"]
    course_id = account["course_id"]
    secrets = [password, username]
    stages = [
        (1, "校验账号与课程参数"),
        (2, "登录 Moodle"),
        (3, "读取课程作业并比对缓存"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}（{}）：开始处理；子任务 {} 项".format(
            result.number, result.label, total_stages
        )
    )
    client: Optional[MoodleClient] = None
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total_stages, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求、未读写状态；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                if not course_id.isdigit():
                    raise SafeError("课程 ID 无效")
                state_path = state_file_for(course_id, state_dir)
                result.stats["success"] += 1
                log(
                    "{} 用户名、课程 ID={}，状态文件 {}；耗时 {:.2f} 秒".format(
                        ICONS["success"],
                        course_id,
                        state_path.name,
                        time.monotonic() - tick,
                    )
                )
            elif index == 2:
                client = MoodleClient(base_url, timeout, secrets)
                client.login(username, password)
                result.stats["success"] += 1
                log(
                    "{} 登录流程完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                assert client is not None
                _, html_text = client.course_page(course_id)
                if COOKIE_CONSENT_HINT in html_text:
                    client.login(username, password)
                    _, html_text = client.course_page(course_id)
                course_name = extract_course_name(html_text)
                if course_name:
                    log("课程名称：{}".format(course_name))
                else:
                    log("未解析到课程名称，继续比对作业列表")
                identity = extract_identity(html_text, secrets)
                if identity:
                    result.identity = identity
                    log("账号 {} 官方身份：{}".format(result.number, identity))
                else:
                    result.identity = username
                    log(
                        "账号 {}：页面未返回公开身份，使用用户名标识".format(
                            result.number
                        )
                    )
                assignments = search_assignments(html_text, base_url)
                current_ids = [item.id for item in assignments]
                result.assignment_count = len(assignments)
                state_path = state_file_for(course_id, state_dir)
                previous_ids = read_ids(state_path)
                changed = ids_differ(current_ids, previous_ids)
                result.changed = changed
                if not previous_ids and current_ids:
                    # 首次建立缓存：写入并视为成功基线，避免误报“全部新增”
                    write_ids(state_path, current_ids)
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = "首次缓存 {} 个作业 ID".format(len(current_ids))
                    log("{} {}".format(ICONS["success"], result.message))
                elif changed:
                    short_list = "；".join(item.short() for item in assignments) or "无"
                    write_ids(state_path, current_ids)
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = "作业列表已变更，当前 {} 项".format(
                        len(assignments)
                    )
                    log("{} {}".format(ICONS["success"], result.message))
                    log("当前作业短列表：{}".format(short_list[:500]))
                else:
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    result.message = "无新作业（{} 项，与缓存一致）".format(
                        len(assignments)
                    )
                    log("{} {}".format(ICONS["alreadyComplete"], result.message))
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
            result.message = redact(str(error), secrets)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    result.message,
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
        result.message = "断网预演通过"
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
    dry_setting = env(DRY_RUN_ENV, "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    base_url = DEFAULT_BASE_URL
    state_dir = Path(__file__).resolve().parent / "uo_moodle_state"
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("{} 配置无效，停止执行".format(DRY_RUN_ENV))
        timeout = resolve_timeout()
        base_url = resolve_base_url()
        state_dir = resolve_state_dir()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；基址：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                base_url,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            item = AccountResult(number, account.get("label") or "Moodle")
            results.append(item)
            run_account(
                item,
                account,
                base_url,
                state_dir,
                timeout,
                dry_run,
            )
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
    changed_accounts = sum(1 for item in results if item.changed)
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；"
        "作业变更账号：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            changed_accounts,
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
        "任务统计：账号 {}，成功 {}（含无变更 {}），失败 {}，预演 {}，变更 {}".format(
            account_total,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
            changed_accounts,
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
                "changedAccounts": changed_accounts,
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
