#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 长江雨课堂课堂签到
# cron: */5 8-18 * * 1-5
#
# 来源：Shirley-Hxn/AutoAttendYuKeTang src/startup.py（GPL-3.0）
# https://github.com/Shirley-Hxn/AutoAttendYuKeTang
# 提交：9b496deb7ecda102024696c51d6161bcc899132d
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) Shirley-Hxn / upstream AutoAttendYuKeTang contributors
# 本维护版在保留上游业务行为的前提下改为青龙独立脚本；完整 GPL-3.0 文本见上游 LICENSE。
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""长江雨课堂（changjiang.yuketang.cn）进行中课堂签到（青龙维护版）。

功能清点（相对上游 src/startup.py）：
- 账号密码登录（RSA PKCS#1 加密密码，内嵌原 public.pem 公钥，不再依赖仓库路径）
- 查询进行中课堂 on_lesson_courses
- 对每节课请求 lesson_info_v2，业务 success 视为签到成功并记录课程名
- 移除 while True 默认长轮询（原 900×60s）与钉钉 WEBHOOK/verify=False 推送
- 改为青龙可调度单次执行；可选短轮询由环境变量显式开启
- 换行多账号、YUKETANG_DRY_RUN 断网预演、超时、业务 success 核验、
  时间轴日志、TASK_SUMMARY、青龙脱敏通知与任一账号失败非零退出

YUKETANG_ACCOUNTS（必填）：每个非空行一个账号，格式 username|password；
  仅按第一个 | 分割，密码中后续 | 原样保留。兼容上游单账号 USER_INFO。
YUKETANG_TIMEOUT：单次请求超时秒数，默认 20，范围 5..60。
YUKETANG_POLL_ROUNDS：单次任务内轮询次数，默认 1（单次），最大 30。
YUKETANG_POLL_INTERVAL：轮询间隔秒数，默认 60，范围 10..300。
YUKETANG_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
建议 Cron：*/5 8-18 * * 1-5（上课时段周期性触发）。不打印密码、Cookie、Token 或原始响应。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('dfe95bcc2e664575', 'scripts/startup.py', 'startup.py', 'startup')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import http.cookiejar
import importlib.util
import json
import os
import re
import secrets as pysecrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "长江雨课堂课堂签到"
CATALOG_ID = "dfe95bcc2e664575"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1024 * 1024
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
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

# 上游 src/public.pem（长江雨课堂登录公钥，公开材料，非凭据）
YUKETANG_RSA_N = int(
    "10113570974308385566364515212166424156536350298135033858663414442904885105"
    "00368092391872762302012784391519882066621630186305440994290330245253600799"
    "79834383613688397745754363754439616525473931432394032755291261563492188635"
    "60541041035480274337604754057790959597167085998527313396877471977082980840"
    "8809661365999"
)
YUKETANG_RSA_E = 65537

API = {
    "login": "https://changjiang.yuketang.cn/pc/login/verify_pwd_login/",
    "onlesson": "https://changjiang.yuketang.cn/v/course_meta/on_lesson_courses",
    "attendlesson": "https://changjiang.yuketang.cn/v/lesson/lesson_info_v2",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


AccountSpec = Dict[str, str]


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def redact(text: str, secrets: List[str]) -> str:
    out = str(text).replace("\r", " ").replace("\n", " ")
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 2:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", out)
    out = re.sub(
        r"(?i)(sessionid|csrftoken|authorization|token|cookie)=([^;\s]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable())[:240]


def resolve_timeout() -> float:
    raw = env("YUKETANG_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("YUKETANG_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("YUKETANG_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_poll_rounds() -> int:
    raw = env("YUKETANG_POLL_ROUNDS", "1")
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("YUKETANG_POLL_ROUNDS 须为正整数") from exc
    if value < 1 or value > 30:
        raise SafeError("YUKETANG_POLL_ROUNDS 须在 1 到 30 之间（已取消上游默认超长轮询）")
    return value


def resolve_poll_interval() -> int:
    raw = env("YUKETANG_POLL_INTERVAL", "60")
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("YUKETANG_POLL_INTERVAL 须为正整数秒") from exc
    if value < 10 or value > 300:
        raise SafeError("YUKETANG_POLL_INTERVAL 须在 10 到 300 秒之间")
    return value


def rsa_encrypt_password(password: str) -> str:
    """PKCS#1 v1.5 加密，等价于上游 rsa.encrypt + base64。"""
    message = password.encode("utf-8")
    k = (YUKETANG_RSA_N.bit_length() + 7) // 8
    if len(message) > k - 11:
        raise SafeError("密码过长，无法按雨课堂 RSA 规则加密")
    ps_len = k - len(message) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        block = pysecrets.token_bytes(ps_len - len(ps) + 16)
        ps.extend(b for b in block if b != 0)
    em = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + message
    cipher_int = pow(int.from_bytes(em, "big"), YUKETANG_RSA_E, YUKETANG_RSA_N)
    return base64.b64encode(cipher_int.to_bytes(k, "big")).decode("ascii")


def parse_account_line(line: str) -> AccountSpec:
    text = line.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        raise SafeError("账号行为空")
    if "|" not in text:
        raise SafeError(
            "账号行须为 username|password；不要用 & 或 @ 分隔账号"
        )
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username:
        raise SafeError("用户名不能为空")
    if not password:
        raise SafeError("密码不能为空")
    if any(ord(ch) < 32 for ch in password):
        raise SafeError("密码含非法控制字符")
    return {"username": username, "password": password}


def load_accounts() -> List[AccountSpec]:
    raw = env("YUKETANG_ACCOUNTS")
    source = "YUKETANG_ACCOUNTS"
    if not raw:
        legacy = env("USER_INFO")
        if legacy:
            raw = legacy
            source = "USER_INFO"
        else:
            raise SafeError(
                "未配置凭据：请设置 YUKETANG_ACCOUNTS（每行 username|password）；"
                "兼容单账号 USER_INFO"
            )
    accounts: List[AccountSpec] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    if not accounts:
        raise SafeError("{} 中没有有效账号行".format(source))
    return accounts


def nested(data: Any, *paths: Tuple[Any, ...], default: Any = None) -> Any:
    for path in paths:
        value = data
        ok = True
        for key in path:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                ok = False
                break
        if ok and value is not None:
            return value
    return default


def extract_identity(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    candidates = [
        nested(payload, ("data", "user_info", "name")),
        nested(payload, ("data", "user_info", "nickname")),
        nested(payload, ("data", "user_info", "user_name")),
        nested(payload, ("data", "user_name")),
        nested(payload, ("data", "name")),
        nested(payload, ("data", "nickname")),
        payload.get("user_name") if isinstance(payload.get("user_name"), str) else None,
        payload.get("nickname") if isinstance(payload.get("nickname"), str) else None,
    ]
    for value in candidates:
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value).strip()
            if text and not re.fullmatch(r"1[3-9]\d{9}", text):
                return text
    return None


def cookie_header_from_jar(jar: http.cookiejar.CookieJar) -> str:
    parts = []
    for cookie in jar:
        parts.append("{}={}".format(cookie.name, cookie.value))
    return "; ".join(parts)


class ApiClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        data: Optional[bytes] = None,
        params: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if params:
            query = urllib.parse.urlencode(params)
            url = "{}{}{}".format(url, "&" if "?" in url else "?", query)
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://changjiang.yuketang.cn/",
        }
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise SafeError("响应过大，已中止解析")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as error:
            raise SafeError("HTTP {} 请求失败".format(error.code)) from error
        except urllib.error.URLError as error:
            raise SafeError("网络请求失败") from error
        except TimeoutError as error:
            raise SafeError("请求超时") from error
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError as error:
            raise SafeError("响应不是合法 JSON") from error
        if not isinstance(payload, dict):
            raise SafeError("响应结构异常")
        return payload

    def login(self, username: str, password: str) -> Dict[str, Any]:
        encrypted = rsa_encrypt_password(password)
        body = json.dumps(
            {"type": "PP", "name": username, "pwd": encrypted},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        payload = self.request(
            "POST",
            API["login"],
            data=body,
            content_type="application/json",
        )
        if payload.get("success") is not True:
            raise SafeError("登录失败：账号或密码未通过校验")
        if not cookie_header_from_jar(self.jar):
            raise SafeError("登录成功但未获得会话 Cookie")
        return payload

    def on_lessons(self) -> List[Dict[str, Any]]:
        payload = self.request("GET", API["onlesson"])
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SafeError("进行中课堂响应缺少 data")
        lessons = data.get("on_lessons")
        if lessons is None:
            raise SafeError("进行中课堂响应缺少 on_lessons")
        if not isinstance(lessons, list):
            raise SafeError("on_lessons 结构异常")
        return [item for item in lessons if isinstance(item, dict)]

    def attend(self, lesson_id: Any) -> str:
        payload = self.request(
            "GET",
            API["attendlesson"],
            params={"lesson_id": str(lesson_id)},
        )
        if payload.get("success") is not True:
            raise SafeError("课堂签到接口未返回 success")
        course_name = nested(payload, ("data", "classroom", "courseName"))
        if not isinstance(course_name, str) or not course_name.strip():
            raise SafeError("签到成功但未返回课程名称")
        return course_name.strip()


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE_VALUES:
        return False, "全局开关已关闭"
    if switch in TRUE_VALUES:
        return True, "全局开关已开启"
    # auto / unset：按名单
    selection = env("QINGLONG_NOTIFY_SCRIPTS")
    if selection == "":
        return False, "通知名单为空，已禁用全部脚本通知"
    if not selection:
        return False, "默认仅通知名单内脚本，未配置名单"
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", selection)
        if item
    ]
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name.lower(),
        "startup.py",
        "yuketang_changjiang_attend.py",
        "candidate.py",
        "scripts/yuketang_changjiang_attend.py",
        "yuketang",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix().lower())
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
        self.attended: List[str] = []


def secrets_for(account: AccountSpec) -> List[str]:
    return [account["username"], account["password"]]


def run_account(
    result: AccountResult,
    account: AccountSpec,
    timeout: float,
    dry_run: bool,
    poll_rounds: int,
    poll_interval: int,
) -> None:
    secrets = secrets_for(account)
    stages = [
        (1, "密码登录长江雨课堂"),
        (2, "查询进行中课堂并签到"),
    ]
    total = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项；轮询 {} 次".format(
            result.number, total, poll_rounds
        )
    )
    client: Optional[ApiClient] = None
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total, name))
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
                client = ApiClient(timeout)
                payload = client.login(account["username"], account["password"])
                identity = extract_identity(payload)
                if identity:
                    result.identity = identity
                    log("账号 {} 官方身份：{}".format(result.number, identity))
                else:
                    # 不回显可能为手机号的用户名
                    if re.fullmatch(r"1[3-9]\d{9}", account["username"]):
                        log(
                            "账号 {}：未返回公开身份，使用序号标识".format(
                                result.number
                            )
                        )
                    else:
                        result.identity = account["username"]
                        log(
                            "账号 {} 使用登录名标识：{}".format(
                                result.number, result.identity
                            )
                        )
                result.stats["success"] += 1
                log(
                    "{} 登录成功并已建立会话；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                assert client is not None
                attended_names: List[str] = []
                seen_ids = set()
                empty_confirmed = False
                for round_index in range(1, poll_rounds + 1):
                    if round_index > 1:
                        log(
                            "账号 {} 轮询 {}/{}：等待 {} 秒".format(
                                result.number,
                                round_index,
                                poll_rounds,
                                poll_interval,
                            )
                        )
                        time.sleep(poll_interval)
                    lessons = client.on_lessons()
                    if not lessons:
                        empty_confirmed = True
                        log(
                            "账号 {} 轮询 {}/{}：暂无进行中课堂".format(
                                result.number, round_index, poll_rounds
                            )
                        )
                        continue
                    empty_confirmed = False
                    for item in lessons:
                        lesson_id = item.get("lesson_id")
                        if lesson_id is None or lesson_id in seen_ids:
                            continue
                        course_name = client.attend(lesson_id)
                        seen_ids.add(lesson_id)
                        if course_name not in attended_names:
                            attended_names.append(course_name)
                        log(
                            "{} 签到成功：{}".format(
                                ICONS["success"], course_name
                            )
                        )
                result.attended = attended_names
                if attended_names:
                    result.stats["success"] += 1
                    detail = "已签到 {} 门：{}".format(
                        len(attended_names), "、".join(attended_names)
                    )
                    log(
                        "{} {}；耗时 {:.2f} 秒".format(
                            ICONS["success"], detail, time.monotonic() - tick
                        )
                    )
                    result.message = detail
                elif empty_confirmed or poll_rounds >= 1:
                    result.stats["alreadyComplete"] += 1
                    detail = "当前无进行中课堂，已确认查询成功"
                    log(
                        "{} {}；耗时 {:.2f} 秒".format(
                            ICONS["alreadyComplete"],
                            detail,
                            time.monotonic() - tick,
                        )
                    )
                    result.message = detail
                else:
                    raise SafeError("未确认任何课堂状态")
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total
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
            for pending in range(index + 1, total + 1):
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
        result.message = "DRY_RUN_OK"
    elif result.stats["failure"]:
        result.status = "failure"
    elif result.stats["success"]:
        result.status = "success"
    else:
        result.status = "alreadyComplete"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total,
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
    dry_setting = env("YUKETANG_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[AccountSpec] = []
    timeout = float(DEFAULT_TIMEOUT)
    poll_rounds = 1
    poll_interval = 60
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("YUKETANG_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        poll_rounds = resolve_poll_rounds()
        poll_interval = resolve_poll_interval()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；轮询：{}×{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                poll_rounds,
                poll_interval,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            item = AccountResult(number)
            results.append(item)
            run_account(
                item, account, timeout, dry_run, poll_rounds, poll_interval
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
