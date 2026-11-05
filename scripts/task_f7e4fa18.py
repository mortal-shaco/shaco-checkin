#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 网易云音乐人签到
# cron: 21 9 * * *
#
# 来源：ghaction/Musician-Auto-Check main.py（MIT）
# https://github.com/ghaction/Musician-Auto-Check
# 提交：23e1f798d7ebfcb75fd7178a685556c822ac9be3
# SPDX-License-Identifier: MIT
#
# Copyright (c) 2021 Demontisa
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
"""网易云音乐人签到（青龙维护版）。

功能清点（相对上游 main.py / config.ini）：
- 手机号+密码登录（支持明文或已 MD5）；兼容整段 Cookie（含 MUSIC_U）
- 调用兼容 Binaryify/NeteaseCloudMusicApi 路径的音乐人签到、任务列表、云豆领取与余额查询
- 移除默认第三方 API 地址（原 vercel 公共服务会接收账号密码，不安全）
- 移除硬编码任务下标领取；改为按任务状态识别可领取项
- 移除企业微信机器人默认推送与原始响应打印；改用青龙通知
- 增加换行多账号、NETEASE_MUSICIAN_DRY_RUN 断网预演、超时、业务码核验、
  时间轴日志、TASK_SUMMARY 与失败非零退出

NETEASE_MUSICIAN_ACCOUNTS（必填）：每个非空行一个账号。
  - 密码账号：phone|password，仅按第一个 | 分割，密码中后续 | 原样保留
  - Cookie 账号：同一行完整 Cookie，须含 MUSIC_U（建议同时含 __csrf）
兼容：NETEASE_MUSICIAN_PHONE + NETEASE_MUSICIAN_PASSWORD（仅当规范变量为空）；
      NETEASE_MUSICIAN_COOKIE（多行 Cookie，仅当规范变量为空）。
NETEASE_MUSICIAN_PASSWORD_MD5=1：表示账号行中的密码字段已是 32 位小写 MD5。
NETEASE_MUSICIAN_API_BASE：真实执行必填；指向本人信任的兼容 HTTPS API 根地址
（形如 https://your-api.example，末尾无 /）。本脚本只发起 HTTP，不安装、不启动
任何外部应用；禁止把凭据交给来源不明的公共服务。
NETEASE_MUSICIAN_TIMEOUT：单次请求超时秒数，默认 20，范围 5..60。
NETEASE_MUSICIAN_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
建议 Cron：20 9 * * *。不打印密码、Cookie、Token、手机号或原始响应。
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
            "f7e4fa182acc7d66",
            "scripts/netease_musician_checkin.py",
            "netease_musician_checkin.py",
            "candidate.py",
            "main.py",
            "netease_musician",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
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
from typing import Any, Dict, List, Optional, Tuple

TITLE = "网易云音乐人签到"
CATALOG_ID = "f7e4fa182acc7d66"
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
OK_CODES = {0, 200}
CLAIMABLE_STATUS = {2, "2", "completed", "done", "finished", "reward", "claimable"}
ALREADY_CLAIM_HINTS = ("已领取", "已经领取", "重复领取", "already")


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
    out = re.sub(r"(?i)(MUSIC_U|__csrf|MUSIC_A_T|MUSIC_R_T)=([^;\s]+)", r"\1=[敏感值]", out)
    return "".join(ch for ch in out if ch.isprintable())[:240]


def resolve_timeout() -> float:
    raw = env("NETEASE_MUSICIAN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("NETEASE_MUSICIAN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("NETEASE_MUSICIAN_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_api_base() -> str:
    raw = env("NETEASE_MUSICIAN_API_BASE")
    if not raw:
        raise SafeError(
            "请显式设置本人信任的 NETEASE_MUSICIAN_API_BASE（HTTPS，兼容 "
            "NeteaseCloudMusicApi 路径）；禁止使用来源不明的公共服务"
        )
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SafeError("NETEASE_MUSICIAN_API_BASE 必须是不含凭据的 HTTPS 根地址")
    if parsed.username or parsed.password:
        raise SafeError("NETEASE_MUSICIAN_API_BASE 不得包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise SafeError("NETEASE_MUSICIAN_API_BASE 不得包含查询参数或片段")
    host = parsed.hostname.lower()
    # 阻断上游默认的第三方公开实例，避免把账号密码交给未知运营方。
    blocked_hosts = {
        "netease-cloud-music-api-binaryify.vercel.app",
        "netease-cloud-music-api.vercel.app",
    }
    if host in blocked_hosts:
        raise SafeError(
            "拒绝使用上游默认公共 API；请改为本人可控的 HTTPS 服务根地址"
        )
    try:
        _ = parsed.port
    except ValueError as exc:
        raise SafeError("NETEASE_MUSICIAN_API_BASE 端口无效") from exc
    path = (parsed.path or "").rstrip("/")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc.lower(), path, "", "")
    )


def password_is_md5() -> bool:
    return env("NETEASE_MUSICIAN_PASSWORD_MD5", "0").lower() in TRUE_VALUES


def looks_like_cookie(line: str) -> bool:
    lower = line.lower()
    return "music_u=" in lower or ("__csrf=" in lower and "=" in line and ";" in line)


def parse_account_line(line: str) -> AccountSpec:
    text = line.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        raise SafeError("账号行为空")
    if looks_like_cookie(text):
        fields = {}
        for part in text.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            fields[key.strip()] = value.strip()
        if not fields.get("MUSIC_U"):
            raise SafeError("Cookie 账号行必须包含非空 MUSIC_U")
        return {"kind": "cookie", "cookie": text, "label": "cookie"}
    if "|" not in text:
        raise SafeError(
            "账号行须为 phone|password，或含 MUSIC_U 的完整 Cookie；"
            "不要用 & 或 @ 分隔账号"
        )
    phone, password = text.split("|", 1)
    phone = phone.strip()
    password = password.strip()
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise SafeError("手机号格式无效（须为 11 位国内号，不含 +86）")
    if not password:
        raise SafeError("密码不能为空")
    if any(ord(ch) < 32 for ch in password):
        raise SafeError("密码含非法控制字符")
    return {"kind": "password", "phone": phone, "password": password, "label": "phone"}


def load_accounts() -> List[AccountSpec]:
    raw = env("NETEASE_MUSICIAN_ACCOUNTS")
    source = "NETEASE_MUSICIAN_ACCOUNTS"
    if not raw:
        cookie_raw = env("NETEASE_MUSICIAN_COOKIE")
        if cookie_raw:
            raw = cookie_raw
            source = "NETEASE_MUSICIAN_COOKIE"
        else:
            phone = env("NETEASE_MUSICIAN_PHONE")
            password = env("NETEASE_MUSICIAN_PASSWORD")
            if phone or password:
                if not phone or not password:
                    raise SafeError(
                        "单账号别名须同时提供 NETEASE_MUSICIAN_PHONE 与 "
                        "NETEASE_MUSICIAN_PASSWORD"
                    )
                return [
                    parse_account_line("{}|{}".format(phone, password))
                ]
            raise SafeError(
                "未配置凭据：请设置 NETEASE_MUSICIAN_ACCOUNTS（每行 "
                "phone|password 或完整 Cookie）"
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


def business_code(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    for key in ("code",):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
    data = payload.get("data")
    if isinstance(data, dict):
        value = data.get("code")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return None


def is_ok(payload: Any) -> bool:
    code = business_code(payload)
    return code in OK_CODES


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
    profile = nested(payload, ("profile",), ("data", "profile"), ("data", "account"))
    if isinstance(profile, dict):
        for field in ("nickname", "userName", "username", "displayName", "userId"):
            value = profile.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value).strip()
                if text and not re.fullmatch(r"1[3-9]\d{9}", text):
                    return text
    for field in ("nickname", "userName", "username", "displayName", "userId"):
        value = payload.get(field) if isinstance(payload, dict) else None
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value).strip()
            if text and not re.fullmatch(r"1[3-9]\d{9}", text):
                return text
    return None


def walk_dicts(data: Any):
    if isinstance(data, dict):
        yield data
        for child in data.values():
            yield from walk_dicts(child)
    elif isinstance(data, list):
        for child in data:
            yield from walk_dicts(child)


def mission_list(payload: Any) -> List[Dict[str, Any]]:
    candidates = nested(payload, ("data", "list"), ("data", "missions"), ("list",))
    if isinstance(candidates, list):
        return [item for item in candidates if isinstance(item, dict)]
    found: List[Dict[str, Any]] = []
    for item in walk_dicts(payload):
        if item.get("userMissionId") is not None and item.get("period") is not None:
            found.append(item)
    # 去重
    uniq: Dict[str, Dict[str, Any]] = {}
    for item in found:
        key = "{}:{}".format(item.get("userMissionId"), item.get("period"))
        uniq[key] = item
    return list(uniq.values())


def is_claimable(mission: Dict[str, Any]) -> bool:
    if mission.get("userMissionId") is None or mission.get("period") is None:
        return False
    status = mission.get("status", mission.get("missionStatus", mission.get("taskStatus")))
    if status in CLAIMABLE_STATUS:
        return True
    if mission.get("needReceive") is True or mission.get("canObtain") is True:
        return True
    # 上游硬编码领取登录/里程碑类任务；在缺少明确状态时，不盲领。
    return False


def already_claim_message(payload: Any) -> bool:
    message = str(
        nested(payload, ("message",), ("msg",), ("data", "message"), default="") or ""
    ).lower()
    return any(hint.lower() in message for hint in ALREADY_CLAIM_HINTS)


class ApiClient:
    def __init__(self, base: str, timeout: float) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.cookie_header = ""

    def set_cookie_header(self, cookie: str) -> None:
        self.cookie_header = cookie.strip()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, str]] = None,
        form: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if not path.startswith("/"):
            path = "/" + path
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = self.base + path + (("?" + query) if query else "")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SafeError("拒绝非 HTTPS 请求")
        data = None
        headers = self._headers()
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise SafeError("响应过大")
                if int(status) < 200 or int(status) >= 400:
                    raise SafeError("HTTP 状态异常")
                text = payload.decode("utf-8", errors="replace")
                try:
                    body = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise SafeError("响应不是有效 JSON") from exc
                if not isinstance(body, dict):
                    raise SafeError("响应结构异常")
                return body
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raise SafeError("HTTP 请求失败（状态 {}）".format(exc.code)) from exc
        except urllib.error.URLError:
            raise SafeError("网络请求失败或超时") from None
        except TimeoutError:
            raise SafeError("网络请求超时") from None
        except Exception:
            raise SafeError("请求过程异常") from None

    def cookie_string_from_jar(self) -> str:
        parts: List[str] = []
        for cookie in self.jar:
            parts.append("{}={}".format(cookie.name, cookie.value))
        return "; ".join(parts)


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def login_account(client: ApiClient, account: AccountSpec) -> Tuple[str, Optional[str]]:
    if account["kind"] == "cookie":
        client.set_cookie_header(account["cookie"])
        # 用音乐人云豆查询确认会话；不打印原始响应。
        payload = client.request("GET", "/musician/cloudbean")
        if not is_ok(payload):
            # 部分实现用 /login/status
            payload = client.request("GET", "/login/status")
            if not is_ok(payload):
                raise SafeError("Cookie 登录未确认（业务码未通过）")
        identity = extract_identity(payload)
        return "Cookie 会话已确认", identity

    phone = account["phone"]
    password = account["password"]
    if password_is_md5():
        if not re.fullmatch(r"[0-9a-f]{32}", password):
            raise SafeError("MD5 密码须为 32 位小写十六进制")
        params = {"phone": phone, "md5_password": password}
    else:
        # 兼容上游 md5=false：由本脚本本地 MD5 后再走 md5_password，避免明文落在查询串以外路径时仍可预测。
        params = {"phone": phone, "md5_password": md5_hex(password)}
    payload = client.request("GET", "/login/cellphone", params=params)
    if not is_ok(payload):
        raise SafeError("手机号登录未确认（业务码未通过）")
    jar_cookie = client.cookie_string_from_jar()
    body_cookie = nested(payload, ("cookie",), ("data", "cookie"), default="")
    if isinstance(body_cookie, str) and body_cookie.strip():
        client.set_cookie_header(body_cookie.strip())
    elif jar_cookie:
        client.set_cookie_header(jar_cookie)
    else:
        raise SafeError("登录成功但未获得会话 Cookie")
    identity = extract_identity(payload)
    return "手机号登录已确认", identity


def musician_sign(client: ApiClient) -> Tuple[str, str]:
    payload = client.request("GET", "/musician/sign")
    code = business_code(payload)
    if code in OK_CODES:
        return "success", "音乐人中心签到已确认"
    message = str(nested(payload, ("message",), ("msg",), default="") or "")
    if any(hint in message for hint in ("已签到", "重复", "already")):
        return "alreadyComplete", "今日已完成音乐人签到"
    raise SafeError("音乐人签到业务未确认成功")


def claim_rewards(client: ApiClient) -> Tuple[str, str]:
    payload = client.request("GET", "/musician/tasks")
    if not is_ok(payload):
        raise SafeError("获取音乐人任务列表失败")
    missions = mission_list(payload)
    claimable = [item for item in missions if is_claimable(item)]
    if not claimable:
        # 上游会固定领取若干项；若接口未给出可领状态，尝试领取描述含登录/里程碑的任务。
        fallback: List[Dict[str, Any]] = []
        for item in missions:
            desc = str(
                item.get("description")
                or item.get("name")
                or item.get("missionName")
                or item.get("title")
                or ""
            )
            if item.get("userMissionId") is None or item.get("period") is None:
                continue
            if any(token in desc for token in ("登录音乐人", "里程碑", "音乐人中心")):
                fallback.append(item)
        claimable = fallback
    if not claimable:
        return "alreadyComplete", "当前没有可领取的云豆任务"

    success = 0
    already = 0
    failed = 0
    for item in claimable:
        mid = str(item["userMissionId"])
        period = str(item["period"])
        try:
            result = client.request(
                "GET",
                "/musician/cloudbean/obtain",
                params={"id": mid, "period": period},
            )
            if is_ok(result):
                success += 1
            elif already_claim_message(result):
                already += 1
            else:
                failed += 1
        except SafeError:
            failed += 1
    detail = "可领 {}，成功 {}，已领 {}，失败 {}".format(
        len(claimable), success, already, failed
    )
    if failed:
        return "failure", detail
    if success:
        return "success", detail
    return "alreadyComplete", detail


def cloudbean_balance(client: ApiClient) -> Tuple[str, str]:
    payload = client.request("GET", "/musician/cloudbean")
    if not is_ok(payload):
        raise SafeError("云豆余额查询失败")
    balance = nested(
        payload,
        ("data", "cloudBean"),
        ("data", "cloudbean"),
        ("cloudBean",),
    )
    if balance is None:
        raise SafeError("云豆余额字段缺失")
    try:
        amount = int(balance)
    except (TypeError, ValueError) as exc:
        raise SafeError("云豆余额字段无效") from exc
    return "success", "当前云豆 {}".format(amount)


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
        "netease_musician_checkin.py",
        "candidate.py",
        "scripts/netease_musician_checkin.py",
        "netease_musician",
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


def secrets_for(account: AccountSpec) -> List[str]:
    values = []
    if account["kind"] == "cookie":
        values.append(account["cookie"])
        for part in account["cookie"].split(";"):
            if "=" in part:
                values.append(part.split("=", 1)[1].strip())
    else:
        values.extend([account["phone"], account["password"], md5_hex(account["password"])])
    return [item for item in values if item]


def run_account(
    result: AccountResult,
    account: AccountSpec,
    api_base: str,
    timeout: float,
    dry_run: bool,
) -> None:
    secrets = secrets_for(account)
    stages = [
        (1, "登录并确认会话"),
        (2, "音乐人中心签到"),
        (3, "领取可领云豆任务"),
        (4, "查询云豆余额"),
    ]
    total = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项".format(
            result.number, total
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
                client = ApiClient(api_base, timeout)
                detail, identity = login_account(client, account)
                if identity:
                    result.identity = identity
                    log("账号 {} 官方身份：{}".format(result.number, identity))
                else:
                    log(
                        "账号 {}：未返回公开身份，使用序号标识".format(
                            result.number
                        )
                    )
                result.stats["success"] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS["success"], detail, time.monotonic() - tick
                    )
                )
            elif index == 2:
                assert client is not None
                outcome, detail = musician_sign(client)
                result.stats[outcome] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS[outcome], detail, time.monotonic() - tick
                    )
                )
                if outcome == "failure":
                    raise SafeError(detail)
            elif index == 3:
                assert client is not None
                outcome, detail = claim_rewards(client)
                result.stats[outcome] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS[outcome], detail, time.monotonic() - tick
                    )
                )
                if outcome == "failure":
                    raise SafeError(detail)
            else:
                assert client is not None
                outcome, detail = cloudbean_balance(client)
                result.stats[outcome] += 1
                log(
                    "{} {}；耗时 {:.2f} 秒".format(
                        ICONS[outcome], detail, time.monotonic() - tick
                    )
                )
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
    dry_setting = env("NETEASE_MUSICIAN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[AccountSpec] = []
    timeout = float(DEFAULT_TIMEOUT)
    api_base = ""
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("NETEASE_MUSICIAN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        if not dry_run:
            api_base = resolve_api_base()
        else:
            # 预演允许未配置 API；若已配置则校验格式。
            if env("NETEASE_MUSICIAN_API_BASE"):
                api_base = resolve_api_base()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                "；API 已配置" if api_base else "；预演未要求 API",
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
            run_account(item, account, api_base, timeout, dry_run)
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
