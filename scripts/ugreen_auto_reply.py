#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 绿联社区自动回复
# cron: 2 10 * * *
#
# 来源：silence9527/ugreen_auto_reply ugreen_auto_reply.py（MIT）
# https://github.com/silence9527/ugreen_auto_reply
# 提交：b5b3e986f9d11b60c194a8d4ad85b350f75d1b6d
# 上游署名：By:Matata
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2024 Matata / silence9527
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
"""绿联社区（club.ugnas.com）自动回复（青龙独立维护版）。

功能清点（相对上游 ugreen_auto_reply.py）：
- 使用 Cookie 登录绿联社区 Discuz 论坛
- 从「功能讨论 / 玩法攻略 / 用户互助」三个板块抓取帖子
- 提取 formhash 后对随机帖子提交回复
- 公开回复文案优先使用一言 HTTPS，失败回退本地语料；dry-run 不请求一言
- 保留上游多风格本地语料作为回退文案
- 移除 ugreen_log.txt 文件写入、QYWX_AM 第三方推送与 30–600 秒默认长等待
- 默认每次仅回复 3 帖（可用 UGREEN_REPLY_COUNT 调高至最多 20），动作间隔默认 2 秒
- 多账号：UGREEN_COOKIE 每行一个 Cookie
- UGREEN_DRY_RUN=1 完全断网预演；青龙通知与 TASK_SUMMARY
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
            "a941733da99ecdb7",
            "scripts/ugreen_auto_reply.py",
            "ugreen_auto_reply.py",
            "candidate.py",
            "output/candidate.py",
            "ugreen",
            "绿联社区自动回复",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import html
import importlib.util
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "a941733da99ecdb7"
SCRIPT_NAME = "绿联社区自动回复"
SCRIPT_FILENAME = "ugreen_auto_reply.py"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    SCRIPT_FILENAME,
    "scripts/ugreen_auto_reply.py",
    "candidate.py",
    "output/candidate.py",
    "ugreen",
    SCRIPT_NAME,
)

COOKIE_ENV = "UGREEN_COOKIE"
DRY_RUN_ENV = "UGREEN_DRY_RUN"
TIMEOUT_ENV = "UGREEN_TIMEOUT"
REPLY_COUNT_ENV = "UGREEN_REPLY_COUNT"
ACTION_DELAY_ENV = "UGREEN_ACTION_DELAY_SEC"
LOCAL_TEXT_ENV = "UGREEN_LOCAL_TEXT"

BASE_HOST = "club.ugnas.com"
BASE_URL = "https://club.ugnas.com"
HOME_URL = BASE_URL + "/"
FORMHASH_URL = BASE_URL + "/forum.php?mod=post&action=newthread&fid=10"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_HOST = "v1.hitokoto.cn"
HITOKOTO_TIMEOUT = 8
HITOKOTO_MAX_BYTES = 16384
HTTP_TIMEOUT = 30
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_REPLY_COUNT = 3
MAX_REPLY_COUNT = 20
DEFAULT_ACTION_DELAY = 2.0
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

FORUM_URLS = {
    "功能讨论": f"{BASE_URL}/forum.php?mod=forumdisplay&fid=10",
    "玩法攻略": f"{BASE_URL}/forum.php?mod=forumdisplay&fid=9",
    "用户互助": f"{BASE_URL}/forum.php?mod=forumdisplay&fid=13",
}

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

STATUS_ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}

# 上游多风格语料，仅作一言失败时的本地回退
LOCAL_REPLY_POOL = [
    "这个功能确实值得优化",
    "建议加个远程端口配置选项",
    "我也遇到类似情况，建议官方看看",
    "这个问题我用 Docker 解决了",
    "这个玩法太赞了",
    "学习了新技巧，感谢分享",
    "我也试过这个方法，确实有效",
    "适合新手参考",
    "我也遇到过类似问题",
    "建议检查网络设置",
    "可以试试重启设备",
    "这个方法值得一试",
    "太棒了这个建议！",
    "支持楼主！",
    "功能细节讲得很清楚",
    "希望官方采纳！",
    "感谢分享！我马上试试",
    "这个教程太实用了",
    "赞一个！",
    "我来打卡学习了",
    "大家都好热心！",
    "楼主的问题解决了吗？",
    "欢迎交流",
    "希望你能顺利解决",
    "这个功能让我头秃了",
    "官方快来救命！",
    "我也踩过这个坑",
    "功能不够用，脑洞来凑",
    "这招太骚了！",
    "我抄作业来了",
    "这波操作我给满分",
    "高手在民间啊",
    "我来围观学习了",
    "这个问题我也翻车过",
    "大家都是技术人！",
    "互助区就是温暖",
]

THREAD_HREF_RE = re.compile(
    r'href=["\']([^"\']*thread-(\d+)-\d+-\d+[^"\']*)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
THREAD_TID_RE = re.compile(r"[?&]tid=(\d+)", re.IGNORECASE)
FORMHASH_RE = re.compile(
    r'name=["\']formhash["\']\s+value=["\']([a-fA-F0-9]+)["\']'
    r'|value=["\']([a-fA-F0-9]+)["\']\s+name=["\']formhash["\']'
    r'|formhash=([a-fA-F0-9]+)',
    re.IGNORECASE,
)
USERNAME_PATTERNS = [
    re.compile(r'id=["\']um["\'][^>]*>.*?<strong[^>]*>(.*?)</strong>', re.I | re.S),
    re.compile(r'id=["\']space_nickname["\'][^>]*>(.*?)<', re.I | re.S),
    re.compile(r'class=["\']vwmy["\'][^>]*>.*?<a[^>]*>(.*?)</a>', re.I | re.S),
    re.compile(r'title=["\']访问我的空间["\'][^>]*>(.*?)<', re.I | re.S),
]
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


def _now() -> datetime:
    return datetime.now().astimezone()


def _clock() -> str:
    return _now().strftime("%H:%M:%S")


def _full_ts() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str = "") -> None:
    if msg:
        print(f"[{_clock()}] {msg}", flush=True)
    else:
        print(flush=True)


def env_raw(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def compact(text: str, limit: int = 160) -> str:
    cleaned = WS_RE.sub(" ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)] + "…"


def strip_html(text: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub(" ", html.unescape(text or ""))).strip()


def normalize_public_text(text: Any) -> str:
    return WS_RE.sub(" ", str(text or "")).strip()


def parse_accounts(raw: str) -> List[str]:
    """每个非空行一个 Cookie；账号之间只用换行分隔。"""
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if any(ord(ch) < 32 for ch in text):
            raise SafeError(f"第 {line_no} 行 Cookie 含非法控制字符")
        accounts.append(text)
    return accounts


def bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = env_raw(name).strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError(f"{name} 须为数字") from exc
    if value < minimum or value > maximum:
        raise SafeError(f"{name} 须在 {minimum} 到 {maximum} 之间")
    return value


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env_raw(name).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{name} 须为整数") from exc
    if value < minimum or value > maximum:
        raise SafeError(f"{name} 须在 {minimum} 到 {maximum} 之间")
    return value


def extract_formhash(page: str) -> Optional[str]:
    match = FORMHASH_RE.search(page or "")
    if not match:
        return None
    for group in match.groups():
        if group:
            return group
    return None


def extract_username(page: str) -> str:
    for pattern in USERNAME_PATTERNS:
        match = pattern.search(page or "")
        if not match:
            continue
        name = strip_html(match.group(1))
        if name and name.lower() not in {"登录", "注册", "login"}:
            return name
    return ""


def look_logged_in(page: str) -> bool:
    text = page or ""
    if extract_formhash(text):
        return True
    lowered = text.lower()
    markers = ("退出", "logout", "uid=", "space.php?uid=")
    negative = ("您尚未登录", "请先登录", "需要先登录", "member.php?mod=logging")
    if any(n in text for n in negative) and "退出" not in text:
        return False
    return any(m.lower() in lowered or m in text for m in markers)


def parse_threads(forum_name: str, page: str) -> List[Tuple[str, str, str]]:
    found: Dict[str, Tuple[str, str, str]] = {}
    for match in THREAD_HREF_RE.finditer(page or ""):
        href, tid, title_html = match.group(1), match.group(2), match.group(3)
        title = strip_html(title_html)
        if not tid or not title:
            continue
        if "javascript" in (href or "").lower():
            continue
        found[tid] = (forum_name, tid, title)
    if not found:
        for match in THREAD_TID_RE.finditer(page or ""):
            tid = match.group(1)
            found.setdefault(tid, (forum_name, tid, f"帖子{tid}"))
    return list(found.values())


def reply_success(body: str, status: int) -> Tuple[bool, str]:
    text = body or ""
    lowered = text.lower()
    fail_markers = (
        "errorhandle",
        "您尚未登录",
        "请先登录",
        "需要先登录",
        "抱歉，您没有权限",
        "没有权限进行此操作",
        "验证码",
        "发表受限",
        "两次发表间隔",
        "内容包含敏感词",
        "不能为空",
    )
    for marker in fail_markers:
        if marker.lower() in lowered or marker in text:
            return False, compact(f"业务失败：{marker}", 120)
    success_markers = (
        "succeedhandle_fastpost",
        "succeedhandle",
        "回复发布成功",
        "非常感谢",
        "帖子发布成功",
        "post_reply_succeed",
    )
    for marker in success_markers:
        if marker.lower() in lowered or marker in text:
            return True, "回复成功"
    if status == 200 and ("tid=" in text or "viewthread" in lowered or "pid=" in lowered):
        # Discuz 部分主题返回帖子页且无明确错误文案，视为成功
        if "message_error" not in lowered and "alert_error" not in lowered:
            return True, "回复成功（页面回跳）"
    if 200 <= status < 400:
        return False, f"未识别到明确成功标记（HTTP {status}）"
    return False, f"HTTP {status}"


def format_hitokoto(payload: Any) -> str:
    text = normalize_public_text(payload.get("hitokoto") if isinstance(payload, dict) else "")
    if not text:
        raise SafeError("missing-text")
    author = normalize_public_text(payload.get("from_who") if isinstance(payload, dict) else "")
    source = normalize_public_text(payload.get("from") if isinstance(payload, dict) else "")
    if author and source:
        text = f"{text} —— {author}《{source}》"
    elif source:
        text = f"{text} ——《{source}》"
    elif author:
        text = f"{text} —— {author}"
    text = normalize_public_text(text)
    if not text:
        raise SafeError("missing-text")
    if len(text) > 280:
        raise SafeError("overlong-text")
    return text


def local_public_text() -> str:
    override = normalize_public_text(env_raw(LOCAL_TEXT_ENV))
    if override:
        return override[:280]
    return random.choice(LOCAL_REPLY_POOL)


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout: float = HTTP_TIMEOUT,
    dry_run: bool = False,
    allow_hosts: Tuple[str, ...] = (BASE_HOST,),
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Dict[str, Any]:
    if dry_run:
        raise SafeError("dry-run 禁止发起网络请求")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise SafeError("仅允许 HTTPS 请求")
    host = parsed.hostname or ""
    if host not in allow_hosts:
        raise SafeError(f"不允许的主机：{host}")
    request = urllib.request.Request(url, data=data, method=method.upper())
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            status = int(response.getcode())
            raw = response.read(max_bytes + 1)
            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        status = int(error.code)
        try:
            raw = error.read(max_bytes + 1)
        except Exception:
            raw = b""
        finally:
            try:
                error.close()
            except Exception:
                pass
        final_url = url
    except Exception as exc:
        raise SafeError(f"网络请求失败：{exc.__class__.__name__}") from None
    if len(raw) > max_bytes:
        raise SafeError("响应过大，已中止解析")
    text = raw.decode("utf-8", errors="replace")
    return {"status": status, "text": text, "url": final_url}


def fetch_public_text(*, dry_run: bool, timeout: float) -> Tuple[str, str]:
    if dry_run:
        return local_public_text(), "dry-run-local"
    try:
        result = http_request(
            HITOKOTO_URL,
            method="GET",
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=min(timeout, HITOKOTO_TIMEOUT),
            dry_run=False,
            allow_hosts=(HITOKOTO_HOST,),
            max_bytes=HITOKOTO_MAX_BYTES,
        )
        if result["status"] != 200:
            raise SafeError("http-error")
        try:
            payload = json.loads(result["text"])
        except json.JSONDecodeError as exc:
            raise SafeError("invalid-json") from exc
        return format_hitokoto(payload), "一言"
    except SafeError:
        return local_public_text(), "local-fallback"
    except Exception:
        return local_public_text(), "local-fallback"


def _notify_global_mode() -> str:
    raw = env_raw("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in TRUE_VALUES:
        return "enabled"
    if raw in FALSE_VALUES:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if raw is None:
        return None
    if raw.strip() == "":
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _selector_match(selector: str) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if sel == "*":
        return True
    candidates = {c.lower() for c in SCRIPT_IDENTITIES}
    sel_l = sel.lower()
    if sel_l in candidates:
        return True
    for identity in SCRIPT_IDENTITIES:
        if _ql_notify_fnmatch.fnmatch(identity.lower(), sel_l):
            return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    if mode == "enabled":
        return True
    selectors = _script_selectors()
    if selectors is None:
        return True
    if not selectors:
        return False
    return any(_selector_match(s) for s in selectors)


def _load_notify_send():
    try:
        from notify import send as notify_send  # type: ignore

        return notify_send
    except Exception:
        pass
    candidates: List[str] = []
    custom = env_raw("QINGLONG_NOTIFY_DIR").strip()
    if custom:
        candidates.append(os.path.join(custom, "notify.py"))
    candidates.extend(
        [
            "/ql/data/scripts/notify.py",
            "/ql/scripts/notify.py",
        ]
    )
    for path in candidates:
        try:
            if not os.path.isfile(path):
                continue
            spec = importlib.util.spec_from_file_location("ql_notify_mod", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = getattr(module, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, content: str) -> str:
    if not _should_notify():
        return "skipped"
    send = _load_notify_send()
    if send is None:
        log(f"{STATUS_ICONS['warning']} 未找到可用 notify.py，跳过通知并保留业务退出码")
        return "unavailable"
    try:
        send(title, content)
        return "sent"
    except Exception:
        log(f"{STATUS_ICONS['warning']} 通知发送失败，已忽略并保留业务退出码")
        return "failed"


class UgreenClient:
    def __init__(self, cookie: str, timeout: float, dry_run: bool = False):
        self.cookie = cookie
        self.timeout = timeout
        self.dry_run = dry_run
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": cookie,
            "Referer": HOME_URL,
        }

    def get(self, url: str) -> Dict[str, Any]:
        return http_request(
            url,
            method="GET",
            headers=self.headers,
            timeout=self.timeout,
            dry_run=self.dry_run,
            allow_hosts=(BASE_HOST,),
        )

    def post_form(self, url: str, form: Dict[str, str]) -> Dict[str, Any]:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers = dict(self.headers)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = BASE_URL
        return http_request(
            url,
            method="POST",
            headers=headers,
            data=body,
            timeout=self.timeout,
            dry_run=self.dry_run,
            allow_hosts=(BASE_HOST,),
        )

    def fetch_identity_and_formhash(self) -> Tuple[str, str]:
        home = self.get(HOME_URL)
        username = extract_username(home["text"])
        if not look_logged_in(home["text"]):
            raise SafeError("Cookie 无效或未登录绿联社区")
        formhash = extract_formhash(home["text"])
        if not formhash:
            page = self.get(FORMHASH_URL)
            formhash = extract_formhash(page["text"])
            if not username:
                username = extract_username(page["text"])
        if not formhash:
            raise SafeError("未能提取 formhash")
        return username, formhash

    def list_threads(self) -> List[Tuple[str, str, str]]:
        threads: List[Tuple[str, str, str]] = []
        seen = set()
        for name, url in FORUM_URLS.items():
            page = self.get(url)
            if page["status"] >= 400:
                raise SafeError(f"获取板块【{name}】失败 HTTP {page['status']}")
            batch = parse_threads(name, page["text"])
            for item in batch:
                if item[1] in seen:
                    continue
                seen.add(item[1])
                threads.append(item)
        return threads

    def reply(self, tid: str, message: str, formhash: str) -> Tuple[bool, str]:
        url = (
            f"{BASE_URL}/forum.php?mod=post&action=reply&tid={urllib.parse.quote(tid)}"
            "&replysubmit=yes&infloat=yes&handlekey=fastpost"
        )
        form = {
            "message": message,
            "formhash": formhash,
            "posttime": str(int(time.time())),
        }
        result = self.post_form(url, form)
        return reply_success(result["text"], result["status"])


def action_delay(seconds: float, dry_run: bool) -> None:
    if dry_run or seconds <= 0:
        return
    time.sleep(seconds)


def empty_stats() -> Dict[str, int]:
    return {
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }


def run_account(
    index: int,
    total: int,
    cookie: str,
    *,
    dry_run: bool,
    timeout: float,
    reply_count: int,
    delay_sec: float,
) -> Dict[str, Any]:
    started = time.monotonic()
    identity = f"账号{index}"
    stats = empty_stats()
    messages: List[str] = []

    def mark(state: str) -> None:
        if state in stats:
            stats[state] += 1
        else:
            stats["failed"] += 1

    def stage(num: int, title: str, state: str, detail: str) -> None:
        icon = STATUS_ICONS.get(state, STATUS_ICONS["failure"])
        log(f"阶段{num} {title}：{icon} {detail}")
        mark(state)
        messages.append(f"{title}:{detail}")

    log(f"—— 账号 {index}/{total}（{identity}）——")

    if not cookie:
        stage(1, "校验Cookie", "failure", "Cookie 为空")
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": "Cookie 为空",
            "stats": stats,
            "replies_ok": 0,
            "replies_fail": 0,
        }

    if dry_run:
        stage(1, "校验Cookie", "success", "dry-run 跳过真实登录校验")
        stage(2, "提取formhash", "success", "dry-run 跳过 formhash 提取")
        stage(3, "抓取帖子列表", "success", f"dry-run 模拟抓取 {len(FORUM_URLS)} 个板块")
        planned = reply_count
        reply_ok = 0
        for i in range(planned):
            text, source = fetch_public_text(dry_run=True, timeout=timeout)
            stage(
                4 + i,
                f"回复帖子({i + 1}/{planned})",
                "success",
                f"dry-run 使用{source}文案（{compact(text, 40)}）",
            )
            reply_ok += 1
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": True,
            "identity": identity,
            "status": "dry-run-success",
            "message": "断网预演通过",
            "stats": stats,
            "replies_ok": reply_ok,
            "replies_fail": 0,
        }

    client = UgreenClient(cookie, timeout=timeout, dry_run=False)
    try:
        t0 = time.monotonic()
        username, formhash = client.fetch_identity_and_formhash()
        if username:
            identity = username
            log(f"公开身份: {username}")
        stage(
            1,
            "校验登录",
            "success",
            f"已登录（耗时 {time.monotonic() - t0:.2f}秒）",
        )
        stage(2, "提取formhash", "success", "已获取 formhash")
    except SafeError as exc:
        stage(1, "校验登录", "failure", str(exc))
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": str(exc),
            "stats": stats,
            "replies_ok": 0,
            "replies_fail": 0,
        }

    try:
        t0 = time.monotonic()
        threads = client.list_threads()
        stage(
            3,
            "抓取帖子列表",
            "success",
            f"共 {len(threads)} 个候选帖（耗时 {time.monotonic() - t0:.2f}秒）",
        )
    except SafeError as exc:
        stage(3, "抓取帖子列表", "failure", str(exc))
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": str(exc),
            "stats": stats,
            "replies_ok": 0,
            "replies_fail": 0,
        }

    if not threads:
        stage(4, "回复帖子", "failure", "未获取到任何帖子")
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": "未获取到任何帖子",
            "stats": stats,
            "replies_ok": 0,
            "replies_fail": 0,
        }

    planned = min(reply_count, len(threads))
    selected = random.sample(threads, planned) if planned < len(threads) else list(threads)
    reply_ok = 0
    reply_fail = 0
    for i, (forum_name, tid, title) in enumerate(selected):
        stage_num = 4 + i
        text, source = fetch_public_text(dry_run=False, timeout=timeout)
        try:
            t0 = time.monotonic()
            ok, detail = client.reply(tid, text, formhash)
            cost = time.monotonic() - t0
            title_brief = compact(title, 24) or tid
            if ok:
                reply_ok += 1
                stage(
                    stage_num,
                    f"回复帖子({i + 1}/{planned})",
                    "success",
                    f"【{forum_name}】{title_brief} / {source} / {detail}（{cost:.2f}秒）",
                )
            else:
                reply_fail += 1
                stage(
                    stage_num,
                    f"回复帖子({i + 1}/{planned})",
                    "failure",
                    f"【{forum_name}】{title_brief} / {detail}（{cost:.2f}秒）",
                )
        except SafeError as exc:
            reply_fail += 1
            stage(
                stage_num,
                f"回复帖子({i + 1}/{planned})",
                "failure",
                str(exc),
            )
        if i + 1 < planned:
            action_delay(delay_sec, dry_run=False)

    elapsed = time.monotonic() - started
    account_ok = reply_ok > 0 and reply_fail == 0
    if reply_ok > 0 and reply_fail > 0:
        status = "partial-failure"
        message = f"部分回复成功 {reply_ok}/{planned}"
        account_ok = False
    elif account_ok:
        status = "success"
        message = f"全部回复成功 {reply_ok}/{planned}"
    else:
        status = "failure"
        message = f"回复失败 {reply_fail}/{planned}"

    log(
        f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
    )
    return {
        "ok": account_ok,
        "identity": identity,
        "status": status,
        "message": message,
        "stats": stats,
        "replies_ok": reply_ok,
        "replies_fail": reply_fail,
    }


def print_task_summary(payload: Dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    started_at = _full_ts()
    mono_start = time.monotonic()
    dry_run = env_truthy(DRY_RUN_ENV, False)
    notify_status = "skipped"

    log("=" * 62)
    log(f"任务：{SCRIPT_NAME}")
    log(f"开始时间：{started_at}")
    log(f"运行模式：{'dry-run（完全断网预演）' if dry_run else 'live'}")
    log("=" * 62)

    try:
        timeout = bounded_float(TIMEOUT_ENV, float(HTTP_TIMEOUT), 5.0, 120.0)
        reply_count = bounded_int(REPLY_COUNT_ENV, DEFAULT_REPLY_COUNT, 1, MAX_REPLY_COUNT)
        delay_sec = bounded_float(ACTION_DELAY_ENV, DEFAULT_ACTION_DELAY, 0.0, 60.0)
        accounts = parse_accounts(env_raw(COOKIE_ENV))
    except SafeError as exc:
        log(f"{STATUS_ICONS['failure']} 配置错误：{exc}")
        notify_status = send_notification(
            SCRIPT_NAME,
            f"配置错误\n原因：{exc}\n模式：{'dry-run' if dry_run else 'live'}",
        )
        summary = {
            "catalogId": CATALOG_ID,
            "script": SCRIPT_FILENAME,
            "status": "configuration-error",
            "exitCode": 2,
            "accountTotal": 0,
            "accountSuccess": 0,
            "accountFailed": 0,
            "dryRun": dry_run,
            "notifyStatus": notify_status,
            "message": str(exc),
            "finishedAt": _full_ts(),
        }
        print_task_summary(summary)
        log(f"结束时间：{_full_ts()}")
        log(f"最终状态：{STATUS_ICONS['failure']} 配置错误")
        return 2

    if not accounts:
        msg = f"未配置必填环境变量 {COOKIE_ENV}"
        log(f"{STATUS_ICONS['failure']} {msg}")
        notify_status = send_notification(
            SCRIPT_NAME,
            f"配置错误\n原因：{msg}\n模式：{'dry-run' if dry_run else 'live'}",
        )
        summary = {
            "catalogId": CATALOG_ID,
            "script": SCRIPT_FILENAME,
            "status": "configuration-error",
            "exitCode": 2,
            "accountTotal": 0,
            "accountSuccess": 0,
            "accountFailed": 0,
            "dryRun": dry_run,
            "notifyStatus": notify_status,
            "message": msg,
            "finishedAt": _full_ts(),
        }
        print_task_summary(summary)
        log(f"结束时间：{_full_ts()}")
        log(f"最终状态：{STATUS_ICONS['failure']} 配置错误")
        return 2

    log(f"账号数量：{len(accounts)}")
    log(f"计划每账号回复数：{reply_count}（上限 {MAX_REPLY_COUNT}）")
    if not dry_run:
        log(f"动作间隔：{delay_sec} 秒")

    results: List[Dict[str, Any]] = []
    for idx, cookie in enumerate(accounts, start=1):
        result = run_account(
            idx,
            len(accounts),
            cookie,
            dry_run=dry_run,
            timeout=timeout,
            reply_count=reply_count,
            delay_sec=delay_sec,
        )
        results.append(result)

    success_count = sum(1 for item in results if item.get("ok"))
    failed_count = len(results) - success_count
    reply_ok_total = sum(int(item.get("replies_ok") or 0) for item in results)
    reply_fail_total = sum(int(item.get("replies_fail") or 0) for item in results)
    elapsed = time.monotonic() - mono_start
    finished_at = _full_ts()

    if dry_run and failed_count == 0:
        final_status = "dry-run"
        exit_code = 0
        final_icon = STATUS_ICONS["success"]
        final_text = "dry-run 预演成功"
    elif failed_count == 0:
        final_status = "success"
        exit_code = 0
        final_icon = STATUS_ICONS["success"]
        final_text = "全部账号成功"
    elif success_count == 0:
        final_status = "failure"
        exit_code = 1
        final_icon = STATUS_ICONS["failure"]
        final_text = "全部账号失败"
    else:
        final_status = "partial-failure"
        exit_code = 1
        final_icon = STATUS_ICONS["warning"]
        final_text = "部分账号失败"

    log("-" * 62)
    log(
        f"任务统计：账号成功 {success_count}/{len(accounts)}，失败 {failed_count}；"
        f"回复成功 {reply_ok_total}，回复失败 {reply_fail_total}；"
        f"总耗时 {elapsed:.2f}秒"
    )
    for item in results:
        icon = STATUS_ICONS["success"] if item.get("ok") else STATUS_ICONS["failure"]
        log(f"  {icon} {item.get('identity')}: {item.get('message')}")
    log(f"完成时间：{finished_at}")

    body_lines = [
        f"模式：{'dry-run' if dry_run else 'live'}",
        f"账号总数：{len(accounts)}",
        f"成功：{success_count}",
        f"失败：{failed_count}",
        f"回复成功：{reply_ok_total}",
        f"回复失败：{reply_fail_total}",
        f"结果：{final_text}",
    ]
    for item in results:
        body_lines.append(f"- {item.get('identity')}: {item.get('message')}")
    notify_status = send_notification(SCRIPT_NAME, "\n".join(body_lines))
    log(f"通知状态：{notify_status}")
    log(f"最终状态：{final_icon} {final_text}")

    summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "status": "dry-run" if dry_run and exit_code == 0 else final_status,
        "exitCode": exit_code,
        "accountTotal": len(accounts),
        "accountSuccess": success_count,
        "accountFailed": failed_count,
        "replySuccess": reply_ok_total,
        "replyFailed": reply_fail_total,
        "dryRun": dry_run,
        "notifyStatus": notify_status,
        "elapsedSeconds": round(elapsed, 2),
        "finishedAt": finished_at,
    }
    print_task_summary(summary)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
