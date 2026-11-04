#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 微博超话网页签到评论
# cron: 28 8 * * *
# SPDX-License-Identifier: MIT
"""微博超话网页签到 + 可选评论（青龙维护版）。

作者：88lin
仓库：https://github.com/88lin/weibo-checkin
协议：MIT
维护版有效许可证：MIT（依据导入任务 effectiveLicense）

保留上游接口契约（weibo.com 网页版，需登录态 Cookie）：
  签到  POST https://weibo.com/ajax_proxy/chaohua/page/checkin
  评论  POST https://weibo.com/ajax/comments/create
  评论列表 GET https://weibo.com/ajax/statuses/buildComments
  超话解析 GET https://s.weibo.com/weibo?q=<名字>超话
  最新帖  GET https://weibo.com/ajax_proxy/chaohua/page?flowId=<超话id>
  登录体检 GET https://weibo.com/ajax/setting/getPrivacy

与已发布「微博超话签到」(api.weibo.cn / gsid 抓包) 凭据模型与评论副作用不同，
本脚本面向网页 Cookie 账号，默认仅签到；评论需显式开启。

环境变量见契约；WEIBO_WEB_DRY_RUN=1 完全断网预演。
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('8484f065335f8ea3', 'scripts/weibo_checkin.py', 'weibo_checkin.py', 'weibo_checkin')
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
import platform
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

CATALOG_ID = "8484f065335f8ea3"
TASK_NAME = "微博超话网页签到评论"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    "candidate.py",
    "output/candidate.py",
    "weibo_web_checkin.py",
    "scripts/weibo_web_checkin.py",
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_TIMEOUT = 8.0
HITOKOTO_MAX_BYTES = 16_384
DEFAULT_FALLBACK_TEXT = "今日超话打卡，继续加油。"
MAX_RESPONSE_BYTES = 1_048_576
HTTP_TIMEOUT_DEFAULT = 25.0

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

CHECKIN_OK = 100000
CHECKIN_ALREADY = 382004


# ---------------------------------------------------------------------------
# logging helpers
# ---------------------------------------------------------------------------


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}", flush=True)


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return value


def safe_identity(value: Any, secrets: list[str]) -> Optional[str]:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or len(text) > 120 or re.search(r"[\r\n\x00-\x1f]|1[3-9]\d{9}", text):
        return None
    if any(secret and secret in text for secret in secrets):
        return None
    return text


# ---------------------------------------------------------------------------
# config / accounts
# ---------------------------------------------------------------------------


@dataclass
class Account:
    index: int
    label: str
    cookie: str


@dataclass
class Settings:
    dry_run: bool
    topics: list[str]
    enable_comment: bool
    comment_count: int
    reply_mode: str
    delay_min: float
    delay_max: float
    jitter_minutes: float
    retries: int
    retry_backoff: float
    timeout: float
    fallback_text: str


def parse_account_line(index: int, line: str) -> Account:
    if "|" in line:
        label, cookie = line.split("|", 1)
        label = label.strip() or f"账号{index}"
        cookie = cookie.strip()
    else:
        label = f"账号{index}"
        cookie = line.strip()
    if not cookie or "粘贴" in cookie:
        raise ValueError(f"账号 {index} Cookie 无效")
    if "=" not in cookie:
        raise ValueError(f"账号 {index} Cookie 应为浏览器请求头中的完整 key=value 内容")
    if any(ord(ch) < 32 for ch in cookie):
        raise ValueError(f"账号 {index} Cookie 不得包含控制字符")
    return Account(index=index, label=label, cookie=cookie)


def load_accounts() -> list[Account]:
    raw = os.getenv("WEIBO_COOKIE", "")
    if not raw.strip():
        raw = os.getenv("WEIBO_WEB_COOKIE", "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError("未配置 WEIBO_COOKIE（兼容 WEIBO_WEB_COOKIE）；每行一个账号 Cookie")
    return [parse_account_line(i, line) for i, line in enumerate(lines, start=1)]


def load_topics() -> list[str]:
    raw = os.getenv("WEIBO_SUPERTOPICS", "").strip()
    if not raw:
        raise ValueError("未配置 WEIBO_SUPERTOPICS；填写要签到的超话名称，逗号或换行分隔")
    parts = re.split(r"[,，\n]+", raw)
    topics = [item.strip() for item in parts if item.strip()]
    if not topics:
        raise ValueError("WEIBO_SUPERTOPICS 解析后为空")
    return topics


def load_settings() -> Settings:
    reply_mode = os.getenv("WEIBO_REPLY_MODE", "new").strip().lower() or "new"
    if reply_mode not in ("new", "reply", "mixed"):
        raise ValueError("WEIBO_REPLY_MODE 只能是 new/reply/mixed")
    fallback = " ".join(os.getenv("WEIBO_FALLBACK_TEXT", DEFAULT_FALLBACK_TEXT).split()).strip()
    if not fallback or len(fallback) > 280:
        fallback = DEFAULT_FALLBACK_TEXT
    delay_min = bounded_float("WEIBO_DELAY_MIN", 5.0, 0.0, 120.0)
    delay_max = bounded_float("WEIBO_DELAY_MAX", 15.0, 0.0, 300.0)
    if delay_min > delay_max:
        raise ValueError("WEIBO_DELAY_MIN 不能大于 WEIBO_DELAY_MAX")
    return Settings(
        dry_run=env_flag("WEIBO_WEB_DRY_RUN") or env_flag("WEIBO_DRY_RUN"),
        topics=load_topics(),
        enable_comment=env_flag("WEIBO_ENABLE_COMMENT", False),
        comment_count=bounded_int("WEIBO_COMMENT_COUNT", 1, 1, 5),
        reply_mode=reply_mode,
        delay_min=delay_min,
        delay_max=delay_max,
        jitter_minutes=bounded_float("WEIBO_JITTER_MINUTES", 0.0, 0.0, 60.0),
        retries=bounded_int("WEIBO_RETRIES", 3, 1, 5),
        retry_backoff=bounded_float("WEIBO_RETRY_BACKOFF", 4.0, 1.0, 60.0),
        timeout=bounded_float("WEIBO_TIMEOUT", HTTP_TIMEOUT_DEFAULT, 5.0, 60.0),
        fallback_text=fallback,
    )


def cookie_field(cookie: str, name: str) -> str:
    for part in cookie.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""


def cookie_expiry(cookie: str) -> Optional[datetime]:
    raw = cookie_field(cookie, "ALF")
    match = re.search(r"(\d{10})", raw)
    if match and int(match.group(1)) > 10**9:
        return datetime.fromtimestamp(int(match.group(1)))
    return None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def read_limited(response: Any, limit: int) -> bytes:
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise RuntimeError("响应体超过安全大小限制")
    return payload


def http_request(
    url: str,
    *,
    cookie: str,
    data: Optional[dict[str, str]] = None,
    referer: str = "https://weibo.com/",
    timeout: float,
    retries: int,
    backoff: float,
) -> tuple[int, str]:
    xsrf = cookie_field(cookie, "XSRF-TOKEN")
    headers = {
        "User-Agent": UA,
        "Cookie": cookie,
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }
    if xsrf:
        headers["X-Xsrf-Token"] = xsrf
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    last_err: Optional[BaseException] = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout, context=ssl.create_default_context()
            ) as resp:
                raw = read_limited(resp, MAX_RESPONSE_BYTES)
                return int(getattr(resp, "status", 200)), raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raw = b""
            try:
                raw = read_limited(exc, MAX_RESPONSE_BYTES)
            except Exception:
                pass
            return int(exc.code), raw.decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 — network layer retries
            last_err = exc
            if attempt < retries - 1:
                wait = backoff * (2**attempt)
                log(f"  网络错误（{type(exc).__name__}），{wait:.0f}s 后重试 {attempt + 2}/{retries}")
                time.sleep(wait)
    raise RuntimeError(f"网络请求连续失败 {retries} 次（{type(last_err).__name__}）")


def sleep_jitter(seconds: float, *, dry_run: bool) -> None:
    if dry_run or seconds <= 0:
        return
    log(f"… 随机间隔 {seconds:.0f}s（防风控）")
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# public text (一言)
# ---------------------------------------------------------------------------


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def format_hitokoto(data: dict[str, Any]) -> str:
    text = normalize_public_text(data.get("hitokoto"))
    author = normalize_public_text(data.get("from_who"))
    source = normalize_public_text(data.get("from"))
    if not text:
        raise ValueError("一言响应缺少正文")
    if author and source:
        result = f"{text} —— {author}《{source}》"
    elif source:
        result = f"{text} ——《{source}》"
    elif author:
        result = f"{text} —— {author}"
    else:
        result = text
    result = normalize_public_text(result)
    if len(result) > 280:
        raise ValueError("一言格式化内容超过 280 字")
    return result


def fetch_public_texts(
    count: int,
    *,
    fallback: str,
    timeout: float,
    dry_run: bool,
) -> tuple[list[str], str]:
    if dry_run:
        return [fallback] * count, "本地预演（未访问一言）"
    texts: list[str] = []
    source_label = "一言"
    for _ in range(count):
        try:
            req = urllib.request.Request(
                HITOKOTO_URL,
                headers={"Accept": "application/json", "User-Agent": UA},
            )
            with urllib.request.urlopen(
                req,
                timeout=min(timeout, HITOKOTO_TIMEOUT),
                context=ssl.create_default_context(),
            ) as resp:
                raw = read_limited(resp, HITOKOTO_MAX_BYTES)
            data = json.loads(raw.decode("utf-8", "replace"))
            if not isinstance(data, dict):
                raise ValueError("一言返回了无效 JSON")
            texts.append(format_hitokoto(data))
        except Exception as exc:  # noqa: BLE001 — policy: fall back locally
            texts.append(fallback)
            source_label = f"本地回退（{type(exc).__name__}）"
    return texts, source_label


# ---------------------------------------------------------------------------
# Weibo API
# ---------------------------------------------------------------------------


def check_cookie(cookie: str, settings: Settings) -> bool:
    status, body = http_request(
        "https://weibo.com/ajax/setting/getPrivacy",
        cookie=cookie,
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    try:
        data = json.loads(body)
    except ValueError:
        return False
    if status == 200 and data.get("ok") == -100:
        return False
    return status == 200 and (data.get("data") or {}).get("privacy") is not None


def search_topic(name: str, cookie: str, settings: Settings, cache: dict[str, str]) -> Optional[str]:
    if name in cache:
        return cache[name]
    query = urllib.parse.quote(f"{name}超话")
    status, body = http_request(
        f"https://s.weibo.com/weibo?q={query}",
        cookie=cookie,
        referer="https://s.weibo.com/",
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    if status != 200:
        log(f"  搜索页 HTTP {status}，可能触发风控")
        return None
    if "login.sina.com.cn" in body or "retcode=6102" in body:
        log("  搜索被重定向到登录页 → Cookie 已失效")
        return None
    ids = list(dict.fromkeys(re.findall(r"100808[0-9a-f]{28,}", body)))
    if not ids:
        return None
    for cid in ids:
        idx = body.find(cid)
        ctx = re.sub(r"<[^>]+>", "", body[max(0, idx - 300) : idx])
        if f"{name}超话" in ctx or f"#{name}#" in ctx:
            cache[name] = cid
            return cid
    log(f"  上下文未精确匹配「{name}超话」，使用首个候选 id")
    cache[name] = ids[0]
    return ids[0]


def do_checkin(page_id: str, cookie: str, settings: Settings) -> tuple[str, str]:
    """Return (status, detail) where status in success|already|failed."""
    _, body = http_request(
        "https://weibo.com/ajax_proxy/chaohua/page/checkin",
        cookie=cookie,
        data={
            "scene_id": "pc_checkin",
            "page_id": page_id,
            "timezone": "Asia/Shanghai",
            "lang": "zh-cn",
            "plat": platform.platform(),
            "ua": UA,
        },
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    try:
        data = json.loads(body)
    except ValueError:
        return "failed", "签到响应非 JSON"
    code = data.get("code")
    if code == CHECKIN_OK:
        title = str(data.get("title") or "")
        sub = str(data.get("sub_title") or "")
        detail = "签到成功"
        extra = "，".join(part for part in (title, sub) if part)
        if extra:
            detail = f"{detail}（{extra}）"
        return "success", detail
    if code == CHECKIN_ALREADY:
        return "already", "今日已签"
    return "failed", f"签到失败 code={code}"


def latest_post(page_id: str, cookie: str, settings: Settings) -> Optional[tuple[str, str, str]]:
    _, body = http_request(
        f"https://weibo.com/ajax_proxy/chaohua/page?flowId={page_id}",
        cookie=cookie,
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    try:
        data = json.loads(body)
    except ValueError:
        return None
    items = data.get("items") or (data.get("data") or {}).get("items") or []
    for item in items:
        feed = item.get("data") or {}
        mid = feed.get("mid") or feed.get("id")
        if mid and str(mid).isdigit() and len(str(mid)) >= 15:
            text = re.sub(r"\s+", " ", feed.get("text_raw") or feed.get("text") or "")[:40]
            uid = str((feed.get("user") or {}).get("id") or "")
            return str(mid), text, uid
    return None


def list_comments(mid: str, cookie: str, settings: Settings, count: int = 20) -> list[dict[str, str]]:
    status, body = http_request(
        "https://weibo.com/ajax/statuses/buildComments?is_reload=1"
        f"&id={mid}&is_show_bulletin=3&is_mix=0&count={count}&fetch_level=0&locale=en-US",
        cookie=cookie,
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if status >= 400 and data.get("ok") == 0:
        return []
    out: list[dict[str, str]] = []
    for item in data.get("data") or []:
        if item.get("id"):
            out.append(
                {
                    "id": str(item["id"]),
                    "user_id": str((item.get("user") or {}).get("id") or ""),
                }
            )
    return out


def do_comment(
    mid: str,
    text: str,
    cookie: str,
    settings: Settings,
    *,
    reply_to: Optional[str] = None,
    author_uid: str = "",
    my_uid_box: dict[str, str],
) -> tuple[str, str]:
    payload = {
        "id": mid,
        "comment": text,
        "pic_id": "",
        "is_repost": "0",
        "comment_ori": "0",
        "is_comment": "0",
        "fp": "",
    }
    if reply_to:
        payload["rootid"] = reply_to
    if author_uid:
        payload["uid"] = author_uid
    status, body = http_request(
        "https://weibo.com/ajax/comments/create",
        cookie=cookie,
        data=payload,
        timeout=settings.timeout,
        retries=settings.retries,
        backoff=settings.retry_backoff,
    )
    try:
        data = json.loads(body)
    except ValueError:
        return "failed", f"评论响应非 JSON（HTTP {status}）"
    if data.get("ok") == 1:
        user = (data.get("data") or {}).get("user") or {}
        my = str(user.get("id") or "")
        if my:
            my_uid_box["uid"] = my
        for key in ("screen_name", "name", "idstr", "id"):
            ident = safe_identity(user.get(key), [cookie])
            if ident:
                my_uid_box["identity"] = ident
                break
        where = "楼中楼" if reply_to else "主楼"
        return "success", f"评论成功[{where}]"
    if data.get("ok") == -100:
        return "failed", "评论失败：登录态失效"
    return "failed", f"评论失败 ok={data.get('ok')}"


# ---------------------------------------------------------------------------
# account runner
# ---------------------------------------------------------------------------


@dataclass
class AccountStats:
    total: int = 0
    success: int = 0
    already: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class AccountResult:
    index: int
    label: str
    identity: Optional[str]
    ok: bool
    detail: str
    duration: float
    stats: AccountStats = field(default_factory=AccountStats)


def run_account(account: Account, settings: Settings) -> AccountResult:
    started = time.monotonic()
    stats = AccountStats()
    identity: Optional[str] = None
    cache: dict[str, str] = {}
    my_uid_box: dict[str, str] = {}
    display = account.label

    log(f"账号 {account.index}（{display}）｜阶段 1/4：校验 Cookie 参数")
    expiry = cookie_expiry(account.cookie)
    if expiry:
        days = (expiry - datetime.now()).days
        if days < 0 and not settings.dry_run:
            stats.failed += 1
            stats.total += 1
            duration = time.monotonic() - started
            log(f"账号 {account.index}｜❌ Cookie 已过期（ALF）")
            log(
                f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
                f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f} 秒"
            )
            return AccountResult(account.index, display, None, False, "Cookie 已过期", duration, stats)
        if days <= 7:
            log(f"账号 {account.index}｜⚠️ Cookie 将于 {expiry:%m-%d} 过期（约 {days} 天）")
    log(f"账号 {account.index}｜✅ Cookie 格式有效，未输出凭据")

    if settings.jitter_minutes > 0 and not settings.dry_run:
        wait = random.uniform(0, settings.jitter_minutes * 60)
        log(f"账号 {account.index}｜启动抖动 {wait / 60:.1f} 分钟…")
        time.sleep(wait)

    log(f"账号 {account.index}｜阶段 2/4：{'预演登录体检' if settings.dry_run else '登录态体检'}")
    stage2 = time.monotonic()
    if settings.dry_run:
        log(f"账号 {account.index}｜⏭️ dry-run 跳过真实登录请求｜阶段耗时 {time.monotonic() - stage2:.2f} 秒")
    else:
        if not check_cookie(account.cookie, settings):
            stats.failed += 1
            stats.total += 1
            duration = time.monotonic() - started
            log(f"账号 {account.index}｜❌ Cookie 登录态无效")
            log(
                f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
                f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f} 秒"
            )
            return AccountResult(account.index, display, None, False, "登录态无效", duration, stats)
        log(f"账号 {account.index}｜✅ 登录态有效｜阶段耗时 {time.monotonic() - stage2:.2f} 秒")

    log(f"账号 {account.index}｜阶段 3/4：准备评论公开内容")
    comment_texts: list[str] = []
    content_source = "未启用评论"
    if settings.enable_comment:
        comment_texts, content_source = fetch_public_texts(
            settings.comment_count,
            fallback=settings.fallback_text,
            timeout=settings.timeout,
            dry_run=settings.dry_run,
        )
        log(
            f"账号 {account.index}｜✅ 评论内容已准备，来源：{content_source}，"
            f"条数：{len(comment_texts)}"
        )
    else:
        log(f"账号 {account.index}｜⏭️ 未开启 WEIBO_ENABLE_COMMENT，仅签到")

    log(f"账号 {account.index}｜阶段 4/4：{'预演' if settings.dry_run else '执行'}超话签到"
        f"{'与评论' if settings.enable_comment else ''}")
    topics = list(settings.topics)
    if not settings.dry_run:
        random.shuffle(topics)

    for idx, name in enumerate(topics):
        if idx:
            sleep_jitter(random.uniform(settings.delay_min, settings.delay_max), dry_run=settings.dry_run)
        log(f"账号 {account.index}｜▶ 超话「{name}」")
        stats.total += 1
        try:
            if settings.dry_run:
                stats.skipped += 1
                log(f"账号 {account.index}｜⏭️ 预演：将解析并签到「{name}」（未执行）")
                if settings.enable_comment:
                    stats.total += 1
                    stats.skipped += 1
                    log(f"账号 {account.index}｜⏭️ 预演：将发表评论（未执行，未访问一言）")
                continue

            cid = search_topic(name, account.cookie, settings, cache)
            if not cid:
                stats.failed += 1
                log(f"账号 {account.index}｜❌ 未解析到超话「{name}」")
                continue
            status, detail = do_checkin(cid, account.cookie, settings)
            if status == "success":
                stats.success += 1
                log(f"账号 {account.index}｜✅ {detail}")
            elif status == "already":
                stats.already += 1
                log(f"账号 {account.index}｜☑️ {detail}")
            else:
                stats.failed += 1
                log(f"账号 {account.index}｜❌ {detail}")

            if not settings.enable_comment:
                continue

            sleep_jitter(
                random.uniform(max(settings.delay_min, 3), max(settings.delay_max, 8)),
                dry_run=False,
            )
            post = latest_post(cid, account.cookie, settings)
            if not post:
                stats.total += 1
                stats.skipped += 1
                log(f"账号 {account.index}｜⏭️ 未取到最新帖，跳过评论")
                continue
            mid, preview, author_uid = post
            log(f"账号 {account.index}｜最新帖摘要：{preview}…")
            targets: Optional[list[dict[str, str]]] = None
            if settings.reply_mode in ("reply", "mixed"):
                my_uid = my_uid_box.get("uid", "")
                all_c = list_comments(mid, account.cookie, settings, 20)
                targets = [c for c in all_c if not my_uid or c["user_id"] != my_uid]
                if not targets and all_c:
                    log(f"账号 {account.index}｜⚠️ 无法排除自身评论，回退主楼")

            for i, text in enumerate(comment_texts):
                stats.total += 1
                reply_to = None
                if settings.reply_mode == "reply" or (settings.reply_mode == "mixed" and i % 2 == 1):
                    if targets:
                        chosen = random.choice(targets)
                        targets.remove(chosen)
                        reply_to = chosen["id"]
                c_status, c_detail = do_comment(
                    mid,
                    text,
                    account.cookie,
                    settings,
                    reply_to=reply_to,
                    author_uid=author_uid,
                    my_uid_box=my_uid_box,
                )
                if c_status == "success":
                    stats.success += 1
                    if my_uid_box.get("identity") and not identity:
                        identity = my_uid_box["identity"]
                        display = identity
                        log(f"账号 {account.index}｜官方账号身份：{identity}")
                    log(f"账号 {account.index}｜✅ {c_detail}")
                else:
                    stats.failed += 1
                    log(f"账号 {account.index}｜❌ {c_detail}")
                if i < len(comment_texts) - 1:
                    sleep_jitter(
                        random.uniform(max(settings.delay_min, 8), max(settings.delay_max, 20)),
                        dry_run=False,
                    )
        except Exception as exc:  # noqa: BLE001 — isolate per topic
            stats.failed += 1
            log(f"账号 {account.index}｜❌ 超话异常：{type(exc).__name__}")

    duration = time.monotonic() - started
    ok = stats.failed == 0
    detail = (
        f"超话 {len(topics)}；成功 {stats.success}；已完成 {stats.already}；"
        f"跳过 {stats.skipped}；失败 {stats.failed}"
    )
    log(
        f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
        f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f} 秒"
    )
    return AccountResult(account.index, display, identity, ok, detail, duration, stats)


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def notification_selected() -> tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch in TRUE_VALUES:
        return True, "全局开关已启用"
    if switch != "auto":
        return False, "QINGLONG_NOTIFY 值无效，已安全跳过"
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "auto 默认对本维护任务启用"
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False, "脚本选择列表为空"
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    for selector in selectors:
        if selector == "*" or any(fnmatch.fnmatch(ident, selector) for ident in SCRIPT_IDENTITIES):
            return True, f"脚本选择器 {selector} 已匹配"
    return False, "当前脚本未被选择"


def load_notify_sender() -> Optional[Callable[[str, str], Any]]:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            return sender
    except Exception:
        pass
    paths: list[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in paths:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_local_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                return sender
        except Exception:
            continue
    return None


def send_notification(body: str, *, dry_run: bool) -> str:
    selected, reason = notification_selected()
    if not selected:
        log(f"通知｜⏭️ {reason}")
        return "skipped"
    if dry_run:
        log("通知｜⏭️ dry-run 仅生成摘要，不调用可能联网的通知模块")
        return "dry-run-simulated"
    sender = load_notify_sender()
    if sender is None:
        log("通知｜⚠️ 未找到青龙 notify.py；业务退出码保持不变")
        return "unavailable"
    try:
        sender(TASK_NAME, body)
        log("通知｜✅ 已发送脱敏任务总结")
        return "sent"
    except Exception as exc:  # noqa: BLE001
        log(f"通知｜⚠️ 发送失败：{type(exc).__name__}；业务退出码保持不变")
        return "failed"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def emit_final(
    *,
    started_wall: str,
    started_mono: float,
    mode: str,
    results: list[AccountResult],
    configuration_error: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    total = len(results)
    success = sum(1 for item in results if item.ok)
    failed = sum(1 for item in results if not item.ok)
    task_total = sum(item.stats.total for item in results)
    task_success = sum(item.stats.success for item in results)
    task_already = sum(item.stats.already for item in results)
    task_skipped = sum(item.stats.skipped for item in results)
    task_failed = sum(item.stats.failed for item in results)

    if configuration_error:
        business_exit = 2
        final_status = "configuration-error"
    elif failed:
        business_exit = 1
        final_status = "partial-failure" if success else "failure"
    else:
        business_exit = 0
        final_status = "dry-run" if mode == "dry-run" else "success"

    notification_body = (
        f"模式：{mode}\n账号总数：{total}\n成功账号：{success}\n失败账号：{failed}\n"
        f"最终状态：{final_status}"
    )
    if configuration_error:
        notification_body += "\n配置检查：失败"
    notify_status = send_notification(notification_body, dry_run=dry_run)
    finished = now_text()
    duration = time.monotonic() - started_mono

    print("=" * 56)
    log(f"任务统计｜账号总数 {total}｜成功账号 {success}｜失败账号 {failed}")
    log(
        "子任务统计｜"
        f"总任务 {task_total}｜成功 {task_success}｜已完成 {task_already}｜"
        f"跳过 {task_skipped}｜失败 {task_failed}"
    )
    log(f"总耗时｜{duration:.2f} 秒")
    log(f"开始时间｜{started_wall}")
    log(f"完成时间｜{finished}")
    log(f"通知状态｜{notify_status}")
    log(f"最终状态｜{'✅' if business_exit == 0 else '❌'} {final_status}")
    print("=" * 56)
    summary = {
        "task": CATALOG_ID,
        "name": TASK_NAME,
        "mode": mode,
        "accounts": {"total": total, "success": success, "failed": failed},
        "tasks": {
            "total": task_total,
            "success": task_success,
            "alreadyComplete": task_already,
            "skipped": task_skipped,
            "failed": task_failed,
        },
        "status": final_status,
        "notification": notify_status,
        "startedAt": started_wall,
        "finishedAt": finished,
        "durationSeconds": round(duration, 3),
        "exitCode": business_exit,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    if business_exit == 0 and mode == "dry-run":
        print("DRY_RUN_OK", flush=True)
    return business_exit


def main() -> int:
    started_mono = time.monotonic()
    started_wall = now_text()
    print("=" * 56)
    print(f"{TASK_NAME}｜维护版", flush=True)
    print("=" * 56)
    log(f"开始时间｜{started_wall}")

    try:
        settings = load_settings()
        accounts = load_accounts()
    except ValueError as exc:
        mode = "dry-run" if (env_flag("WEIBO_WEB_DRY_RUN") or env_flag("WEIBO_DRY_RUN")) else "live"
        log(f"运行模式｜{mode}")
        log("账号数量｜0")
        log(f"❌ 配置错误：{exc}")
        return emit_final(
            started_wall=started_wall,
            started_mono=started_mono,
            mode=mode,
            results=[],
            configuration_error=str(exc),
            dry_run=mode == "dry-run",
        )

    mode = "dry-run" if settings.dry_run else "live"
    log(f"运行模式｜{mode}")
    log(f"账号数量｜{len(accounts)}")
    log(
        f"超话数量｜{len(settings.topics)}；评论｜"
        f"{'开启/' + settings.reply_mode + '/' + str(settings.comment_count) if settings.enable_comment else '关闭'}"
    )

    results: list[AccountResult] = []
    for account in accounts:
        print("-" * 56)
        try:
            results.append(run_account(account, settings))
        except Exception as exc:  # noqa: BLE001
            duration = time.monotonic() - started_mono
            log(f"账号 {account.index}｜❌ 未处理异常：{type(exc).__name__}")
            log(
                f"账号 {account.index} 统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 {duration:.2f} 秒"
            )
            results.append(
                AccountResult(
                    account.index,
                    account.label,
                    None,
                    False,
                    type(exc).__name__,
                    duration,
                    AccountStats(total=1, failed=1),
                )
            )

    return emit_final(
        started_wall=started_wall,
        started_mono=started_mono,
        mode=mode,
        results=results,
        dry_run=settings.dry_run,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已由用户中断。", file=sys.stderr)
        raise SystemExit(130)
