#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: FF14石之家签到
# cron: 47 2 * * *
# SPDX-License-Identifier: MIT
#
# MIT License
# Copyright (c) 2023 StarHeartHunt
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
#
"""FF14 石之家（Rising Stones）独立签到维护版。

上游：StarHeartHunt/ff14risingstone_sign_task，src/client.py 及同仓签到入口（MIT）。
https://github.com/StarHeartHunt/ff14risingstone_sign_task

参数获取：
1. 浏览器登录 https://ff14risingstones.web.sdo.com/
2. 打开开发者工具「网络」，选中发往石之家 API 的已登录请求
3. 复制 Cookie 中的 ff14risingstones=...（可为完整 Cookie，脚本会保留）
4. 复制与登录时一致的 User-Agent（石之家会校验 UA）
5. 写入 FF14_RS_ACCOUNT，每行一个账号，格式：Cookie|User-Agent
   仅在首个竖线处拆分，后续 UA 原文保留；不要用 & 或 @ 分隔账号。

兼容别名（与规范变量二选一）：
- FF14_RS_COOKIE 与 FF14_RS_USER_AGENT 按行一一对应
- 上游风格 INPUT_COOKIE / INPUT_USER_AGENT 同样按行配对

可选开关（默认与上游正式入口一致）：
- FF14_RS_GET_SIGN_REWARD=1 领取当月可领签到奖励（默认开启）
- FF14_RS_CHECK_HOUSE=0 检查房屋拆除倒计时（默认关闭；发现倒计时则本账号失败）
- FF14_RS_DO_LIKE=0 / FF14_RS_DO_COMMENT=0 点赞/评论（上游正式入口已注释，默认关闭）
- FF14_RS_DO_SEAL=0 完成对应活跃印记（默认关闭）
- FF14_RS_LIKE_POST_ID / FF14_RS_COMMENT_POST_ID 目标帖子 ID（默认 8）
- FF14_RS_LOCAL_TEXT 评论本地回退文案；正式评论优先一言 HTTPS 文案
- FF14_RS_BASE_URL / FF14_RS_IMPERSONATE / FF14_RS_TIMEOUT
- FF14_RS_DRY_RUN=1 完全断网预演

依赖：公开 PyPI 包 curl_cffi（浏览器 TLS 指纹）。不依赖私有仓库或本机预装应用。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "a4b5c4930f657b54",
            "scripts/ff14_risingstone_sign.py",
            "ff14_risingstone_sign.py",
            "candidate.py",
            "ff14_risingstone_sign",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

CATALOG_ID = "a4b5c4930f657b54"
TASK_NAME = "FF14石之家签到"
DEFAULT_BASE_URL = "https://apiff14risingstones.web.sdo.com"
DEFAULT_REFERER = "https://ff14risingstones.web.sdo.com/"
DEFAULT_IMPERSONATE = "chrome124"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
LOCAL_FALLBACK_TEXTS = (
    "今日签到打卡",
    "石之家日常报到",
    "保持热爱，继续冒险",
    "艾欧泽亚今天也加油",
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SECRETS: List[str] = []


class SafeError(Exception):
    """脱敏业务错误，可安全写入日志。"""


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default).strip().lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    raise SafeError("{} 必须是开关值 1/0（true/false/yes/no/on/off）".format(name))


def env_flag(name: str, default: str = "0") -> bool:
    try:
        return truthy(name, default)
    except SafeError:
        raise


def current_month() -> str:
    shanghai = timezone(timedelta(hours=8))
    return datetime.now(timezone.utc).astimezone(shanghai).strftime("%Y-%m")


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if value:
        SECRETS.append(value)


def redact(text: Any, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret and secret in value:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    if len(value) > limit:
        value = value[: limit - 1] + "…"
    return value


def clean_identity(value: Any) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if any(secret and secret in text for secret in SECRETS):
        return ""
    if re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text):
        return ""
    if re.search(r"(?i)(cookie|token|session|authorization|ff14risingstones\s*=)", text):
        return ""
    return "".join(ch if ch.isprintable() else " " for ch in text).strip()


def parse_timeout() -> float:
    raw = os.getenv("FF14_RS_TIMEOUT", "30").strip() or "30"
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("FF14_RS_TIMEOUT 必须是数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("FF14_RS_TIMEOUT 必须在 5 到 120 秒之间")
    return value


def parse_positive_int(name: str, default: str) -> int:
    raw = os.getenv(name, default).strip() or default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("{} 必须是整数".format(name)) from exc
    if value <= 0:
        raise SafeError("{} 必须是正整数".format(name))
    return value


def normalize_cookie(raw: str) -> str:
    cookie = raw.strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie):
        raise SafeError("Cookie 含控制字符，请重新复制")
    if not cookie:
        raise SafeError("Cookie 为空")
    lowered = cookie.lower()
    if "ff14risingstones=" in lowered:
        return cookie
    if "=" not in cookie and ";" not in cookie:
        return "ff14risingstones=" + cookie
    raise SafeError("Cookie 需包含 ff14risingstones 键；可只填 ff14risingstones=编码值")


def normalize_user_agent(raw: str) -> str:
    ua = raw.strip()
    if not ua or any(ord(ch) < 32 or ord(ch) == 127 for ch in ua):
        raise SafeError("User-Agent 无效或含控制字符")
    if len(ua) < 20:
        raise SafeError("User-Agent 过短，请使用登录时的完整浏览器标识")
    return ua


def credential_lines(name: str) -> List[str]:
    return [line.strip() for line in os.getenv(name, "").splitlines() if line.strip()]


def load_accounts() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    combined = credential_lines("FF14_RS_ACCOUNT")
    if combined:
        for line in combined:
            cookie, sep, user_agent = line.partition("|")
            if not sep or not cookie.strip() or not user_agent.strip():
                raise SafeError(
                    "FF14_RS_ACCOUNT 每行格式为 Cookie|User-Agent，仅在首个竖线处拆分"
                )
            accounts.append(
                {
                    "cookie": normalize_cookie(cookie),
                    "user_agent": normalize_user_agent(user_agent),
                }
            )
    else:
        cookie_names = ("FF14_RS_COOKIE", "INPUT_COOKIE")
        ua_names = ("FF14_RS_USER_AGENT", "INPUT_USER_AGENT")
        cookies: List[str] = []
        agents: List[str] = []
        for cname, uname in zip(cookie_names, ua_names):
            cookies = credential_lines(cname)
            agents = credential_lines(uname)
            if cookies or agents:
                if not cookies or not agents or len(cookies) != len(agents):
                    raise SafeError(
                        "{} 与 {} 必须逐行配对且数量相同；建议改用 FF14_RS_ACCOUNT".format(
                            cname, uname
                        )
                    )
                accounts = [
                    {
                        "cookie": normalize_cookie(cookie),
                        "user_agent": normalize_user_agent(ua),
                    }
                    for cookie, ua in zip(cookies, agents)
                ]
                break
    if not accounts:
        raise SafeError(
            "未配置账号：请设置 FF14_RS_ACCOUNT（每行 Cookie|User-Agent），"
            "或配对填写 FF14_RS_COOKIE 与 FF14_RS_USER_AGENT"
        )
    for item in accounts:
        remember_secret(item["cookie"])
        for part in item["cookie"].split(";"):
            _key, sep, value = part.strip().partition("=")
            if sep and value.strip():
                remember_secret(value.strip())
        # UA 本身不是密钥，但不作为身份输出即可
    return accounts


def api_ok(code: Any) -> bool:
    if not isinstance(code, int) or isinstance(code, bool):
        return False
    return code <= 10000 or code == 10001


def already_done_message(msg: Any, code: Any) -> bool:
    text = str(msg or "")
    if code == 10001:
        return True
    return any(token in text for token in ("已签", "已领取", "已完成", "重复", "已经"))


def extract_identity(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    sources: List[Any] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        sources.append(data)
        for key in ("userInfo", "user", "character", "profile"):
            nested = data.get(key)
            if isinstance(nested, dict):
                sources.append(nested)
        details = data.get("characterDetail")
        if isinstance(details, list):
            for item in details[:3]:
                if isinstance(item, dict):
                    sources.append(item)
    fields = (
        "character_name",
        "characterName",
        "CharName",
        "nickname",
        "nickName",
        "username",
        "userName",
        "displayName",
        "name",
        "uid",
        "userId",
        "id",
    )
    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in fields:
            identity = clean_identity(source.get(field))
            if identity and field == "id" and identity.isdigit() and len(identity) > 12:
                continue
            if identity:
                return identity
    return ""


class HttpClient:
    def __init__(
        self,
        base_url: str,
        cookie: str,
        user_agent: str,
        timeout: float,
        impersonate: str,
        dry_run: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie = cookie
        self.user_agent = user_agent
        self.timeout = timeout
        self.impersonate = impersonate
        self.dry_run = dry_run
        self._session = None

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        try:
            from curl_cffi import requests as curl_requests
        except ImportError as exc:
            raise SafeError("缺少公开依赖 curl_cffi，请通过青龙依赖管理从 PyPI 安装") from exc
        self._session = curl_requests
        return self._session

    def headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "Referer": DEFAULT_REFERER,
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "User-Agent": self.user_agent,
            "Cookie": self.cookie,
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        with_credential: bool = True,
        absolute_url: Optional[str] = None,
        timeout: Optional[float] = None,
        limit: int = 1024 * 1024,
    ) -> Tuple[int, Dict[str, Any], str]:
        if self.dry_run:
            raise SafeError("断网预演禁止 HTTP 请求")
        url = absolute_url or (self.base_url + path)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise SafeError("仅允许 HTTPS 业务或文案地址")
        if with_credential:
            host = parsed.netloc.lower()
            base_host = urlsplit(self.base_url).netloc.lower()
            if host != base_host:
                raise SafeError("拒绝向非石之家 API 域名发送凭据")
        session = self._ensure_session()
        headers = self.headers() if with_credential else {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Qinglong-FF14RisingStone/1.0",
        }
        try:
            kwargs = {
                "method": method.upper(),
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout or self.timeout,
                "allow_redirects": False,
            }
            if with_credential:
                kwargs["impersonate"] = self.impersonate
            if data is not None:
                kwargs["data"] = data
            response = session.request(**kwargs)
        except SafeError:
            raise
        except Exception as exc:
            raise SafeError("网络、超时或 TLS 校验失败") from exc
        raw = response.content or b""
        if len(raw) > limit:
            raise SafeError("响应超过大小限制")
        text = ""
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        payload: Dict[str, Any]
        try:
            loaded = response.json()
            payload = loaded if isinstance(loaded, dict) else {"data": loaded}
        except Exception:
            payload = {}
        return int(getattr(response, "status_code", 0) or 0), payload, text


def fetch_public_comment_text(dry_run: bool) -> Tuple[str, str]:
    fallback = " ".join(os.getenv("FF14_RS_LOCAL_TEXT", "").split())
    if not fallback or len(fallback) > 280:
        fallback = random.choice(LOCAL_FALLBACK_TEXTS)
    if dry_run:
        return fallback, "断网预演使用本地评论文案，未访问一言"
    try:
        request = urllib.request.Request(
            HITOKOTO_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Qinglong-FF14RisingStone/1.0",
            },
            method="GET",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=8) as response:
            raw = response.read(16385)
            status = getattr(response, "status", 200)
        if status != 200 or len(raw) > 16384:
            raise SafeError("一言 HTTP 失败或响应过大")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise SafeError("一言 JSON 无效")
        text = payload.get("hitokoto")
        if not isinstance(text, str) or not text.strip():
            raise SafeError("一言缺少正文")
        text = " ".join(text.split()).strip()
        author = payload.get("from_who")
        source = payload.get("from")
        author = " ".join(author.split()).strip() if isinstance(author, str) else ""
        source = " ".join(source.split()).strip() if isinstance(source, str) else ""
        if author and source:
            text = "{} —— {}《{}》".format(text, author, source)
        elif source:
            text = "{} ——《{}》".format(text, source)
        elif author:
            text = "{} —— {}".format(text, author)
        if len(text) > 280:
            raise SafeError("一言文案过长")
        return text, "使用一言文案并保留署名"
    except Exception:
        return fallback, "一言不可用，已回退本地文案"


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {
        CATALOG_ID,
        Path(__file__).name,
        "candidate.py",
        "ff14_risingstone_sign.py",
        "scripts/ff14_risingstone_sign.py",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    if value not in {"", "auto"}:
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演仅生成脱敏摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    py_paths: List[Optional[Path]] = [None]
    if notify_dir:
        py_paths.append(Path(notify_dir) / "notify.py")
    py_paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in py_paths:
        if path is not None and not path.is_file():
            continue
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    python_runner,
                    str(path) if path else "",
                    str(Path(__file__).resolve().parent),
                ],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                log("通知状态：{} 已调用".format("notify.py" if path else "notify.send"))
                return "sent"
        except Exception:
            continue

    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        js_paths: List[Path] = []
        if notify_dir:
            js_paths.append(Path(notify_dir) / "sendNotify.js")
        js_paths.extend(
            [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
        )
        for path in js_paths:
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue

    log("{} 通知状态：未找到可用通知器或发送失败，不改变业务退出码".format(ICONS["warning"]))
    return "unavailable"


class AccountRun:
    def __init__(self, index: int) -> None:
        self.index = index
        self.started = time.monotonic()
        self.identity = "账号{}".format(index)
        self.stats = {
            "total": 0,
            "success": 0,
            "alreadyComplete": 0,
            "skipped": 0,
            "failed": 0,
        }
        self.ok = False
        self.errors: List[str] = []

    def mark(self, state: str) -> None:
        self.stats["total"] += 1
        self.stats[state] += 1

    def stage(self, number: int, name: str, fn):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.index, number, name))
        state = "failure"
        detail = "操作未完成"
        try:
            state, detail = fn()
            if state not in self.stats:
                state = "failure"
            return state, detail
        except SafeError as exc:
            state, detail = "failure", str(exc)
            self.errors.append(detail)
            raise
        except Exception:
            state, detail = "failure", "内部处理失败，已抑制异常详情"
            self.errors.append(detail)
            raise SafeError(detail) from None
        finally:
            self.mark(state)
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.index,
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    redact(detail),
                    time.monotonic() - started,
                )
            )


def run_account(
    index: int,
    account: Dict[str, str],
    *,
    base_url: str,
    timeout: float,
    impersonate: str,
    dry_run: bool,
    get_reward: bool,
    check_house: bool,
    do_like: bool,
    do_comment: bool,
    do_seal: bool,
    like_post_id: int,
    comment_post_id: int,
) -> Dict[str, Any]:
    run = AccountRun(index)
    client = HttpClient(
        base_url,
        account["cookie"],
        account["user_agent"],
        timeout,
        impersonate,
        dry_run,
    )

    def stage_config():
        normalize_cookie(account["cookie"])
        normalize_user_agent(account["user_agent"])
        return "success", "本地凭据格式检查通过（内容不输出）"

    try:
        run.stage(1, "配置检查", stage_config)
    except SafeError:
        run.ok = False
        elapsed = time.monotonic() - run.started
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 FAILED".format(
                index,
                run.stats["total"],
                run.stats["success"],
                run.stats["alreadyComplete"],
                run.stats["skipped"],
                run.stats["failed"],
                elapsed,
            )
        )
        return {
            "index": index,
            "identity": run.identity,
            "ok": False,
            "stats": run.stats,
            "elapsed": elapsed,
            "errors": run.errors,
        }

    if dry_run:
        plan = ["每日签到"]
        if get_reward:
            plan.append("领取当月签到奖励")
        if check_house:
            plan.append("房屋拆除倒计时检查")
        if do_like:
            plan.append("点赞")
        if do_comment:
            plan.append("评论")
        if do_seal:
            plan.append("活跃印记")

        def stage_dry():
            return "skipped", "DRY_RUN_OK：计划执行 {}；未发送请求或产生副作用".format(
                "、".join(plan)
            )

        try:
            run.stage(2, "断网预演", stage_dry)
            run.ok = True
        except SafeError:
            run.ok = False
        elapsed = time.monotonic() - run.started
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                index,
                run.stats["total"],
                run.stats["success"],
                run.stats["alreadyComplete"],
                run.stats["skipped"],
                run.stats["failed"],
                elapsed,
                "DRY_RUN" if run.ok else "FAILED",
            )
        )
        return {
            "index": index,
            "identity": run.identity,
            "ok": run.ok,
            "stats": run.stats,
            "elapsed": elapsed,
            "errors": run.errors,
        }

    stage_no = 2

    def stage_signin():
        status, payload, _text = client.request(
            "POST",
            "/api/home/sign/signIn",
            params={"tempsuid": str(uuid.uuid4())},
            data={"tempsuid": str(uuid.uuid4())},
        )
        if status != 200:
            raise SafeError("签到 HTTP {}".format(status))
        code = payload.get("code")
        msg = payload.get("msg") or payload.get("message") or ""
        if not api_ok(code):
            raise SafeError("签到业务失败：{}".format(redact(msg) or "未返回成功码"))
        if already_done_message(msg, code):
            return "alreadyComplete", "今日已签到（code={}）".format(code)
        return "success", "签到成功（code={}）".format(code)

    try:
        run.stage(stage_no, "每日签到", stage_signin)
    except SafeError:
        pass
    stage_no += 1

    def stage_profile():
        status, payload, _text = client.request(
            "GET",
            "/api/home/userInfo/getUserInfo",
            params={"page": 1},
        )
        if status != 200:
            raise SafeError("用户信息 HTTP {}".format(status))
        code = payload.get("code")
        if code is not None and not api_ok(code):
            raise SafeError("用户信息业务失败")
        identity = extract_identity(payload)
        if identity:
            run.identity = identity
            log("账号 {} 身份：{}".format(index, identity))
        if check_house:
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            details = data.get("characterDetail") if isinstance(data, dict) else None
            house_remain = None
            if isinstance(details, list) and details:
                first = details[0] if isinstance(details[0], dict) else {}
                house_remain = first.get("house_remain_day")
            if house_remain:
                raise SafeError("房屋拆除倒计时：{}".format(redact(house_remain)))
            return "success", "用户信息已读取；未发现房屋拆除倒计时"
        return "success", "用户信息已读取" + ("；已显示公开身份" if identity else "")

    try:
        run.stage(stage_no, "读取身份" + ("/房屋检查" if check_house else ""), stage_profile)
    except SafeError:
        pass
    stage_no += 1

    if get_reward:

        def stage_rewards():
            month = current_month()
            status, payload, _text = client.request(
                "GET",
                "/api/home/sign/signRewardList",
                params={"month": month, "tempsuid": str(uuid.uuid4())},
            )
            if status != 200:
                raise SafeError("奖励列表 HTTP {}".format(status))
            code = payload.get("code")
            if code is not None and not api_ok(code):
                raise SafeError("奖励列表业务失败")
            items = payload.get("data")
            if not isinstance(items, list):
                raise SafeError("奖励列表结构无效")
            claimed = 0
            available = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("is_get") != 0:
                    continue
                available += 1
                reward_id = item.get("id")
                name = redact(item.get("item_name") or reward_id)
                if not isinstance(reward_id, int):
                    raise SafeError("奖励项缺少有效 id")
                r_status, r_payload, _r_text = client.request(
                    "POST",
                    "/api/home/sign/getSignReward",
                    params={"tempsuid": str(uuid.uuid4())},
                    data={
                        "id": reward_id,
                        "month": month,
                        "tempsuid": str(uuid.uuid4()),
                    },
                )
                if r_status != 200:
                    raise SafeError("领取奖励 HTTP {}".format(r_status))
                r_code = r_payload.get("code")
                if not api_ok(r_code):
                    raise SafeError("领取奖励失败：{}".format(name))
                claimed += 1
                log("账号 {} 领取奖励：{}".format(index, name))
            if available == 0:
                return "alreadyComplete", "本月无可领签到奖励"
            return "success", "领取签到奖励 {}/{} 项".format(claimed, available)

        try:
            run.stage(stage_no, "领取签到奖励", stage_rewards)
        except SafeError:
            pass
        stage_no += 1
    else:

        def stage_skip_reward():
            return "skipped", "已按配置跳过领取签到奖励"

        try:
            run.stage(stage_no, "领取签到奖励", stage_skip_reward)
        except SafeError:
            pass
        stage_no += 1

    if do_like:

        def stage_like():
            success_count = 0
            for _ in range(10):
                status, payload, _text = client.request(
                    "POST",
                    "/api/home/posts/like",
                    params={"tempsuid": str(uuid.uuid4())},
                    data={"id": like_post_id, "type": 1},
                )
                if status != 200:
                    raise SafeError("点赞 HTTP {}".format(status))
                code = payload.get("code")
                if not api_ok(code):
                    raise SafeError("点赞业务失败")
                if payload.get("data") == 1:
                    success_count += 1
                time.sleep(1)
            if success_count <= 0:
                raise SafeError("点赞未确认成功次数")
            if do_seal:
                seal_status, seal_payload, _seal_text = client.request(
                    "POST",
                    "/api/home/active/online2312/doSeal",
                    data={"type": 2},
                )
                if seal_status != 200 or not api_ok(seal_payload.get("code")):
                    raise SafeError("点赞印记提交失败")
            return "success", "点赞成功 {} 次".format(success_count)

        try:
            run.stage(stage_no, "点赞", stage_like)
        except SafeError:
            pass
        stage_no += 1
    else:

        def stage_skip_like():
            return "skipped", "上游正式入口已停用点赞；保持默认关闭"

        try:
            run.stage(stage_no, "点赞", stage_skip_like)
        except SafeError:
            pass
        stage_no += 1

    if do_comment:
        comment_text, comment_source = fetch_public_comment_text(dry_run=False)

        def stage_comment():
            content = "<p>{}</p>".format(comment_text)
            status, payload, _text = client.request(
                "POST",
                "/api/home/posts/comment",
                params={"tempsuid": str(uuid.uuid4())},
                data={
                    "content": content,
                    "posts_id": comment_post_id,
                    "parent_id": "0",
                    "root_parent": "0",
                    "comment_pic": "",
                },
            )
            if status != 200:
                raise SafeError("评论 HTTP {}".format(status))
            code = payload.get("code")
            if not api_ok(code):
                raise SafeError("评论业务失败")
            if do_seal:
                seal_status, seal_payload, _seal_text = client.request(
                    "POST",
                    "/api/home/active/online2312/doSeal",
                    data={"type": 3},
                )
                if seal_status != 200 or not api_ok(seal_payload.get("code")):
                    raise SafeError("评论印记提交失败")
            return "success", "评论成功（{}）".format(comment_source)

        try:
            run.stage(stage_no, "评论", stage_comment)
        except SafeError:
            pass
        stage_no += 1
    else:

        def stage_skip_comment():
            return "skipped", "上游正式入口已停用评论；保持默认关闭"

        try:
            run.stage(stage_no, "评论", stage_skip_comment)
        except SafeError:
            pass
        stage_no += 1

    if do_seal:

        def stage_sign_seal():
            status, payload, _text = client.request(
                "POST",
                "/api/home/active/online2312/doSeal",
                data={"type": 1},
            )
            if status != 200:
                raise SafeError("签到印记 HTTP {}".format(status))
            code = payload.get("code")
            msg = payload.get("msg") or ""
            if not api_ok(code):
                raise SafeError("签到印记业务失败")
            if already_done_message(msg, code):
                return "alreadyComplete", "签到印记已完成"
            return "success", "签到印记已提交"

        try:
            run.stage(stage_no, "签到印记", stage_sign_seal)
        except SafeError:
            pass

    run.ok = run.stats["failed"] == 0
    elapsed = time.monotonic() - run.started
    log(
        "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
            index,
            run.stats["total"],
            run.stats["success"],
            run.stats["alreadyComplete"],
            run.stats["skipped"],
            run.stats["failed"],
            elapsed,
            "SUCCESS" if run.ok else "FAILED",
        )
    )
    return {
        "index": index,
        "identity": run.identity,
        "ok": run.ok,
        "stats": run.stats,
        "elapsed": elapsed,
        "errors": run.errors,
    }


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = False
    mode_printed = False
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))

    try:
        dry_run = truthy("FF14_RS_DRY_RUN", "0")
        print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
        print("=" * 56, flush=True)
        mode_printed = True
        timeout = parse_timeout()
        base_url = os.getenv("FF14_RS_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise SafeError("FF14_RS_BASE_URL 必须是 HTTPS 根地址")
        if parsed.netloc.lower() not in {
            "apiff14risingstones.web.sdo.com",
            "ff14risingstones.web.sdo.com",
        }:
            raise SafeError("FF14_RS_BASE_URL 仅允许石之家官方域名")
        base_url = "{}://{}".format(parsed.scheme, parsed.netloc)
        impersonate = (
            os.getenv("FF14_RS_IMPERSONATE", DEFAULT_IMPERSONATE).strip() or DEFAULT_IMPERSONATE
        )
        get_reward = env_flag("FF14_RS_GET_SIGN_REWARD", "1")
        check_house = env_flag("FF14_RS_CHECK_HOUSE", "0")
        do_like = env_flag("FF14_RS_DO_LIKE", "0")
        do_comment = env_flag("FF14_RS_DO_COMMENT", "0")
        do_seal = env_flag("FF14_RS_DO_SEAL", "0")
        like_post_id = parse_positive_int("FF14_RS_LIKE_POST_ID", "8")
        comment_post_id = parse_positive_int("FF14_RS_COMMENT_POST_ID", "8")
        accounts = load_accounts()
    except SafeError as exc:
        if not mode_printed:
            print("运行模式：配置检查失败")
            print("=" * 56, flush=True)
        log("账号数量：0")
        log("[0/0] ❌ 配置错误：{}".format(redact(exc)))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误"
        notify_state = send_notification(TASK_NAME, body, dry_run)
        finished_at = now_text()
        print("-" * 56)
        print("账号结果：总数 0，成功 0，失败 1")
        print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0")
        print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
        print("完成时间：{}".format(finished_at))
        print("通知状态：{}".format(notify_state))
        print("最终状态：CONFIG_ERROR")
        print(
            "TASK_SUMMARY="
            + json.dumps(
                {
                    "status": "configuration-error",
                    "mode": "dry-run" if dry_run else "live",
                    "accounts": {"total": 0, "success": 0, "failed": 1},
                    "tasks": {
                        "total": 0,
                        "success": 0,
                        "alreadyComplete": 0,
                        "skipped": 0,
                        "failed": 0,
                    },
                    "notification": notify_state,
                    "startedAt": started_at,
                    "finishedAt": finished_at,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 2

    log("账号数量：{}".format(len(accounts)))
    results = [
        run_account(
            index,
            account,
            base_url=base_url,
            timeout=timeout,
            impersonate=impersonate,
            dry_run=dry_run,
            get_reward=get_reward,
            check_house=check_house,
            do_like=do_like,
            do_comment=do_comment,
            do_seal=do_seal,
            like_post_id=like_post_id,
            comment_post_id=comment_post_id,
        )
        for index, account in enumerate(accounts, 1)
    ]

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "alreadyComplete", "skipped", "failed")
    }
    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
    elif account_failed == 0:
        status = "success"
        exit_code = 0
    elif account_success:
        status = "partial-failure"
        exit_code = 1
    else:
        status = "failure"
        exit_code = 1

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), account_success, account_failed, status
    )
    notify_state = send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    print("\n" + "-" * 56)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), account_success, account_failed
        )
    )
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failed}".format(
            **task_stats
        )
    )
    print("总耗时：{:.2f}秒".format(elapsed))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：{}".format(status.upper()))
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "status": status,
                "mode": "dry-run" if dry_run else "live",
                "accounts": {
                    "total": len(results),
                    "success": account_success,
                    "failed": account_failed,
                },
                "tasks": task_stats,
                "notification": notify_state,
                "elapsedSeconds": round(elapsed, 3),
                "startedAt": started_at,
                "finishedAt": finished_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
