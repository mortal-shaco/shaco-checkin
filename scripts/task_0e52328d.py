#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 掘金好好生活计划打卡
# cron: 2 1 * * *
# SPDX-License-Identifier: MIT
"""掘金 JUEJIN FRIENDS 好好生活计划沸点打卡（青龙维护版）。

Upstream: https://github.com/XiaoMiku01/JUEJIN-FRIENDS-21days
Original path: main.py
Commit: d83ff297b457a1408e30b824c2ff501a16b343a8
License: MIT

Copyright (c) XiaoMiku01 and contributors.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

功能概览（相对上游）：
- Cookie 改为环境变量，一行一个账号；去掉脚本内硬编码凭据与常驻 schedule 循环
- 由青龙 cron 调度；断网 dry-run、超时、业务成功判定、脱敏通知与 TASK_SUMMARY
- 公开文案遵循一言策略；图片上传默认保留但可关闭；失败时允许无图发布
- 与已发布「稀土掘金每日签到」不同：本脚本发布活动主题沸点，不替代签到/抽奖

JUEJIN_FRIENDS_DRY_RUN=1：完全断网预演，不发起网络请求。
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
        _ql_notify_identities = ('0e52328dae82c7d9', 'scripts/task_0e52328d.py', 'task_0e52328d.py', 'task_0e52328d')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import hmac
import importlib
import importlib.util
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

CATALOG_ID = "0e52328dae82c7d9"
SCRIPT_NAME = "掘金好好生活计划打卡"
SCRIPT_FILENAME = "candidate.py"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    SCRIPT_FILENAME,
    "output/candidate.py",
    "juejin_friends_21days.py",
    "scripts/juejin_friends_21days.py",
)

COOKIE_ENV = "JUEJIN_FRIENDS_COOKIE"
DRY_RUN_ENV = "JUEJIN_FRIENDS_DRY_RUN"
LOCAL_TEXT_ENV = "JUEJIN_FRIENDS_LOCAL_TEXT"
DAY_ENV = "JUEJIN_FRIENDS_DAY"
THEME_ID_ENV = "JUEJIN_FRIENDS_THEME_ID"
THEME_TAG_ENV = "JUEJIN_FRIENDS_THEME_TAG"
UPLOAD_IMAGE_ENV = "JUEJIN_FRIENDS_UPLOAD_IMAGE"
NOTIFY_SWITCH = "QINGLONG_NOTIFY"
NOTIFY_SCRIPTS = "QINGLONG_NOTIFY_SCRIPTS"

DEFAULT_THEME_ID = "7163537723910225960"
DEFAULT_THEME_TAG = "JUEJIN FRIENDS 好好生活计划"
DEFAULT_LOCAL_TEXT = "每日打卡，好好生活。"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_TIMEOUT = 8
HITOKOTO_MAX_BYTES = 16384
HTTP_TIMEOUT = 25
MAX_RESPONSE_BYTES = 2_000_000
IMAGE_MAX_BYTES = 5_000_000
IMAGEX_SERVICE_ID = "k3u1fbpfcp"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

STATUS_ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------


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


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in TRUE_VALUES


def env_text(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip()


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------


def parse_accounts(raw: str) -> List[str]:
    """一行一个 Cookie；保留整行，不在行内按 &/@ 拆账号。"""
    accounts: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(text)
    return accounts


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib)
# ---------------------------------------------------------------------------


class HttpError(RuntimeError):
    pass


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    json_body: Optional[Any] = None,
    timeout: float = HTTP_TIMEOUT,
    max_bytes: int = MAX_RESPONSE_BYTES,
    expect_binary: bool = False,
) -> Tuple[int, Any]:
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    body = data
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise HttpError(f"响应过大（>{max_bytes} 字节）")
            status = int(resp.status)
            if expect_binary:
                return status, raw
            return status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read(max_bytes + 1) if hasattr(exc, "read") else b""
        if len(raw) > max_bytes:
            raise HttpError(f"错误响应过大（>{max_bytes} 字节）") from exc
        text = raw.decode("utf-8", errors="replace") if raw else ""
        if expect_binary:
            return int(exc.code), raw
        return int(exc.code), text
    except urllib.error.URLError as exc:
        raise HttpError(f"网络请求失败: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HttpError("网络请求超时") from exc


def read_json(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise HttpError("响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise HttpError("响应 JSON 不是对象")
    return data


def juejin_ok(payload: Dict[str, Any]) -> bool:
    if payload.get("err_msg") == "success":
        return True
    if payload.get("err_no") == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# public text (一言)
# ---------------------------------------------------------------------------


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def format_hitokoto(data: Dict[str, Any]) -> str:
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


def fetch_public_text(*, fallback: str, dry_run: bool) -> Tuple[str, str]:
    if dry_run:
        return fallback, "本地预演（未访问一言）"
    try:
        status, body = http_request(
            "GET",
            HITOKOTO_URL,
            headers={"Accept": "application/json"},
            timeout=HITOKOTO_TIMEOUT,
            max_bytes=HITOKOTO_MAX_BYTES,
        )
        if status != 200:
            raise HttpError(f"一言 HTTP {status}")
        data = read_json(body if isinstance(body, str) else body.decode("utf-8", "replace"))
        return format_hitokoto(data), "一言"
    except Exception as exc:  # noqa: BLE001 — policy fallback
        return fallback, f"本地回退（{type(exc).__name__}）"


# ---------------------------------------------------------------------------
# ImageX signing / upload (from upstream)
# ---------------------------------------------------------------------------


def random_str(n: int) -> str:
    alphabet = "zyxwvutsrqponmlkjihgfedcba0123456789"
    return "".join(random.choice(alphabet) for _ in range(n))


def hash256(msg: str) -> str:
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def hmac_hash256(key: Any, msg: str) -> hmac.HMAC:
    if isinstance(key, str):
        return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256)
    return hmac.new(key.digest(), msg.encode("utf-8"), hashlib.sha256)


def file_crc32(file_buffer: bytes) -> str:
    return hex(zlib.crc32(file_buffer) & 0xFFFFFFFF)[2:]


def sorted_query(params: Dict[str, str]) -> str:
    items = sorted(params.items(), key=lambda x: x[0])
    return "&".join(f"{k}={v}" for k, v in items)


class JJRequest:
    def __init__(self, token: Dict[str, Any], amz_date: str, params: Dict[str, str]):
        self.token = token
        self.amz_date = amz_date
        self.params = params
        self.method = "GET"

    def get_authorization(self) -> str:
        return (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.token['AccessKeyId']}/{self.amz_date[0:8]}/cn-north-1/imagex/aws4_request, "
            "SignedHeaders=x-amz-date;x-amz-security-token, "
            f"Signature={self.signature()}"
        )

    def signature(self) -> str:
        return hmac_hash256(self.get_signing_key(), self.string_to_sign()).hexdigest()

    def get_signing_key(self) -> hmac.HMAC:
        o = hmac_hash256("AWS4" + self.token["SecretAccessKey"], self.amz_date[0:8])
        i = hmac_hash256(o, "cn-north-1")
        s = hmac_hash256(i, "imagex")
        return hmac_hash256(s, "aws4_request")

    def string_to_sign(self) -> str:
        return "\n".join(
            [
                "AWS4-HMAC-SHA256",
                self.amz_date,
                f"{self.amz_date[0:8]}/cn-north-1/imagex/aws4_request",
                hash256(self.canonical_string()),
            ]
        )

    def canonical_string(self) -> str:
        return "\n".join(
            [
                self.method,
                "/",
                sorted_query(self.params),
                (
                    f"x-amz-date:{self.amz_date}\n"
                    f"x-amz-security-token:{self.token['SessionToken']}\n"
                ),
                "x-amz-date;x-amz-security-token",
                hash256(""),
            ]
        )


def get_upload_token(cookie: str) -> Dict[str, Any]:
    status, body = http_request(
        "GET",
        "https://api.juejin.cn/imagex/gen_token?client=web",
        headers={"cookie": cookie},
    )
    payload = read_json(body if isinstance(body, str) else "")
    if status != 200 or not juejin_ok(payload):
        raise HttpError("获取 ImageX token 失败")
    token = (payload.get("data") or {}).get("token")
    if not isinstance(token, dict):
        raise HttpError("ImageX token 结构无效")
    for key in ("AccessKeyId", "SecretAccessKey", "SessionToken"):
        if key not in token:
            raise HttpError(f"ImageX token 缺少 {key}")
    return token


def get_img_url(uri: str) -> List[str]:
    qs = urllib.parse.urlencode({"uri": uri})
    status, body = http_request(
        "GET",
        f"https://api.juejin.cn/imagex/get_img_url?{qs}",
    )
    payload = read_json(body if isinstance(body, str) else "")
    if status != 200 or not juejin_ok(payload):
        raise HttpError("获取图片地址失败")
    main_url = (payload.get("data") or {}).get("main_url")
    if not main_url:
        return []
    return [str(main_url)]


def fetch_asoul_image() -> bytes:
    qs = urllib.parse.urlencode(
        {
            "nocache": str(int(time.time())),
            "page": "1",
            "tag_id": "0",
            "sort": "3",
            "part": "0",
            "rank": "0",
            "ctime": "0",
            "type": "1",
        }
    )
    status, body = http_request(
        "GET",
        f"https://api.asoulfanart.com:9000/getPic?{qs}",
        timeout=HTTP_TIMEOUT,
        max_bytes=MAX_RESPONSE_BYTES,
    )
    if status != 200:
        raise HttpError(f"获取图片列表失败 HTTP {status}")
    try:
        items = json.loads(body if isinstance(body, str) else "")
    except ValueError as exc:
        raise HttpError("图片列表 JSON 无效") from exc
    if not isinstance(items, list) or not items:
        raise HttpError("图片列表为空")
    chosen = random.choice(items)
    pic_list = chosen.get("pic_url") if isinstance(chosen, dict) else None
    if not isinstance(pic_list, list) or not pic_list:
        raise HttpError("图片条目缺少 pic_url")
    first = pic_list[0]
    img_src = first.get("img_src") if isinstance(first, dict) else None
    if not img_src or not str(img_src).startswith("https://"):
        raise HttpError("图片地址无效")
    status2, raw = http_request(
        "GET",
        str(img_src),
        timeout=HTTP_TIMEOUT,
        max_bytes=IMAGE_MAX_BYTES,
        expect_binary=True,
    )
    if status2 != 200 or not isinstance(raw, (bytes, bytearray)) or not raw:
        raise HttpError("下载图片失败")
    return bytes(raw)


def upload_image(cookie: str) -> List[str]:
    token = get_upload_token(cookie)
    amz_date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    params = {
        "Action": "ApplyImageUpload",
        "Version": "2018-08-01",
        "ServiceId": IMAGEX_SERVICE_ID,
        "s": random_str(11),
    }
    signer = JJRequest(token, amz_date, params)
    headers = {
        "authorization": signer.get_authorization(),
        "x-amz-date": amz_date,
        "x-amz-security-token": token["SessionToken"],
    }
    qs = sorted_query(params)
    status, body = http_request(
        "GET",
        f"https://imagex.bytedanceapi.com/?{qs}",
        headers=headers,
    )
    resp = read_json(body if isinstance(body, str) else "")
    if "Result" not in resp:
        raise HttpError("申请图片上传失败")
    store = resp["Result"]["UploadAddress"]["StoreInfos"][0]
    host = resp["Result"]["UploadAddress"]["UploadHosts"][0]
    store_uri = store["StoreUri"]
    upload_url = f"https://{host}/{store_uri}"
    authorization = store["Auth"]

    status_u, body_u = http_request(
        "POST",
        upload_url + "?uploads",
        headers={"Authorization": authorization},
    )
    # upstream accepts either HTTP 200 or nested error.code == 200
    if status_u != 200:
        try:
            err = read_json(body_u if isinstance(body_u, str) else "")
            if (err.get("error") or {}).get("code") != 200:
                raise HttpError("初始化分片上传失败")
        except HttpError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HttpError("初始化分片上传失败") from exc

    image = fetch_asoul_image()
    status_p, body_p = http_request(
        "PUT",
        upload_url,
        headers={
            "authorization": authorization,
            "content-length": str(len(image)),
            "content-Type": "application/octet-stream",
            "content-crc32": file_crc32(image),
        },
        data=image,
        expect_binary=False,
    )
    if status_p != 200:
        try:
            err = read_json(body_p if isinstance(body_p, str) else "")
            if (err.get("error") or {}).get("code") != 200:
                raise HttpError("上传图片失败")
        except HttpError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HttpError("上传图片失败") from exc
    return get_img_url(store_uri)


# ---------------------------------------------------------------------------
# Juejin business APIs
# ---------------------------------------------------------------------------


def fetch_user_identity(cookie: str) -> Optional[str]:
    status, body = http_request(
        "GET",
        "https://api.juejin.cn/user_api/v1/user/get",
        headers={"cookie": cookie, "User-Agent": UA},
    )
    payload = read_json(body if isinstance(body, str) else "")
    if status != 200 or not juejin_ok(payload):
        return None
    data = payload.get("data") or {}
    for key in ("user_name", "user_id", "user_id_str"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and key != "user_name":
            return str(value)
    return None


def publish_short_msg(
    cookie: str,
    *,
    content: str,
    pic_list: List[str],
    theme_id: str,
) -> None:
    status, body = http_request(
        "POST",
        "https://api.juejin.cn/content_api/v1/short_msg/publish",
        headers={
            "cookie": cookie,
            "content-type": "application/json",
            "User-Agent": UA,
        },
        json_body={
            "content": content,
            "pic_list": pic_list,
            "sync_to_org": False,
            "theme_id": theme_id,
        },
    )
    payload = read_json(body if isinstance(body, str) else "")
    if status != 200 or not juejin_ok(payload):
        err = payload.get("err_msg") or payload.get("err_no") or f"HTTP {status}"
        raise HttpError(f"沸点发布失败: {err}")


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def _split_selectors(raw: str) -> List[str]:
    parts: List[str] = []
    for chunk in raw.replace(";", ",").replace("\n", ",").split(","):
        for piece in chunk.split():
            text = piece.strip()
            if text:
                parts.append(text)
    return parts


def notify_enabled() -> bool:
    raw = os.environ.get(NOTIFY_SWITCH, "auto").strip().lower()
    if raw in FALSE_VALUES:
        return False
    if raw in TRUE_VALUES:
        return True
    # auto / empty → listed-only via QINGLONG_NOTIFY_SCRIPTS
    listed = os.environ.get(NOTIFY_SCRIPTS)
    if listed is None:
        return True
    if listed.strip() == "":
        return False
    selectors = _split_selectors(listed)
    if "*" in selectors:
        return True
    for sel in selectors:
        for ident in SCRIPT_IDENTITIES:
            if sel == ident or fnmatch.fnmatch(ident, sel) or fnmatch.fnmatch(SCRIPT_FILENAME, sel):
                return True
    return False


def send_notify(title: str, content: str) -> str:
    if not notify_enabled():
        return "disabled"
    try:
        notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
        candidates: List[str] = []
        if notify_dir:
            candidates.append(os.path.join(notify_dir, "notify.py"))
        candidates.extend(
            [
                "/ql/data/scripts/notify.py",
                "/ql/scripts/notify.py",
            ]
        )
        for path in candidates:
            if not path or not os.path.isfile(path):
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify_module", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = getattr(module, "send", None)
            if callable(send):
                send(title, content)
                return "sent"
        try:
            module = importlib.import_module("notify")
            send = getattr(module, "send", None)
            if callable(send):
                send(title, content)
                return "sent"
        except Exception:  # noqa: BLE001
            pass
        return "unavailable"
    except Exception as exc:  # noqa: BLE001
        log(f"{STATUS_ICONS['warning']} 通知发送失败（不影响业务退出码）: {type(exc).__name__}")
        return "failed"


# ---------------------------------------------------------------------------
# account / task runners
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
    identity: str
    ok: bool
    detail: str
    duration: float
    stats: AccountStats = field(default_factory=AccountStats)


@dataclass
class Settings:
    dry_run: bool
    cookies: List[str]
    local_text: str
    day_label: str
    theme_id: str
    theme_tag: str
    upload_image: bool


def load_settings() -> Settings:
    raw = os.environ.get(COOKIE_ENV, "")
    cookies = parse_accounts(raw)
    if not cookies:
        raise ValueError(
            f"缺少必填凭据环境变量 {COOKIE_ENV}：请配置掘金 Web Cookie，一行一个账号"
        )
    day_raw = env_text(DAY_ENV)
    if day_raw:
        day_label = day_raw
    else:
        day_label = _now().strftime("%Y%m%d")
    theme_id = env_text(THEME_ID_ENV, DEFAULT_THEME_ID) or DEFAULT_THEME_ID
    theme_tag = env_text(THEME_TAG_ENV, DEFAULT_THEME_TAG) or DEFAULT_THEME_TAG
    local_text = env_text(LOCAL_TEXT_ENV, DEFAULT_LOCAL_TEXT) or DEFAULT_LOCAL_TEXT
    # 默认开启配图以保留上游能力；显式 0/false 关闭
    upload_image = env_truthy(UPLOAD_IMAGE_ENV, default=True)
    return Settings(
        dry_run=env_truthy(DRY_RUN_ENV),
        cookies=cookies,
        local_text=local_text,
        day_label=day_label,
        theme_id=theme_id,
        theme_tag=theme_tag,
        upload_image=upload_image,
    )


def build_content(theme_id: str, theme_tag: str, body: str, day_label: str) -> str:
    prefix = f"[{theme_id}#{theme_tag}#] "
    return f"{prefix}{body} day{day_label}"


def run_account(index: int, cookie: str, settings: Settings) -> AccountResult:
    started = time.monotonic()
    stats = AccountStats()
    identity = f"账号{index}"
    log(f"—— 账号 {index}/{len(settings.cookies)} ——")

    # stage 1: validate cookie shape
    stage = time.monotonic()
    log(f"阶段1 校验 Cookie {STATUS_ICONS['success']}")
    if len(cookie) < 8:
        stats.total += 1
        stats.failed += 1
        duration = time.monotonic() - started
        log(f"阶段1 失败 {STATUS_ICONS['failure']}: Cookie 过短｜耗时 {time.monotonic() - stage:.2f}s")
        log(
            f"账号统计｜总任务 {stats.total}｜成功 {stats.success}｜已完成 {stats.already}｜"
            f"跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f}s"
        )
        return AccountResult(index, identity, False, "Cookie 无效", duration, stats)
    log(f"阶段1 完成：已读取 Cookie（长度已隐藏）｜耗时 {time.monotonic() - stage:.2f}s")

    # stage 2: identity
    stage = time.monotonic()
    log("阶段2 获取账号身份")
    if settings.dry_run:
        stats.total += 1
        stats.skipped += 1
        log(f"阶段2 {STATUS_ICONS['skipped']} dry-run 跳过用户信息请求｜耗时 {time.monotonic() - stage:.2f}s")
    else:
        stats.total += 1
        try:
            name = fetch_user_identity(cookie)
            if name:
                identity = name
                stats.success += 1
                log(f"阶段2 {STATUS_ICONS['success']} 账号身份：{identity}｜耗时 {time.monotonic() - stage:.2f}s")
            else:
                stats.skipped += 1
                log(
                    f"阶段2 {STATUS_ICONS['warning']} 未返回可展示身份，继续打卡｜"
                    f"耗时 {time.monotonic() - stage:.2f}s"
                )
        except Exception as exc:  # noqa: BLE001
            stats.skipped += 1
            log(
                f"阶段2 {STATUS_ICONS['warning']} 身份查询失败（{type(exc).__name__}），继续打卡｜"
                f"耗时 {time.monotonic() - stage:.2f}s"
            )

    # stage 3: public text
    stage = time.monotonic()
    log("阶段3 准备公开文案")
    body, source = fetch_public_text(fallback=settings.local_text, dry_run=settings.dry_run)
    content = build_content(settings.theme_id, settings.theme_tag, body, settings.day_label)
    stats.total += 1
    stats.success += 1
    log(
        f"阶段3 {STATUS_ICONS['success']} 文案来源：{source}，长度 {len(content)}（不输出正文）｜"
        f"耗时 {time.monotonic() - stage:.2f}s"
    )

    # stage 4: optional image
    stage = time.monotonic()
    pic_list: List[str] = []
    log("阶段4 配图上传")
    if not settings.upload_image:
        stats.total += 1
        stats.skipped += 1
        log(f"阶段4 {STATUS_ICONS['skipped']} 已关闭配图｜耗时 {time.monotonic() - stage:.2f}s")
    elif settings.dry_run:
        stats.total += 1
        stats.skipped += 1
        log(f"阶段4 {STATUS_ICONS['skipped']} dry-run 跳过图片下载与上传｜耗时 {time.monotonic() - stage:.2f}s")
    else:
        stats.total += 1
        try:
            pic_list = upload_image(cookie)
            if pic_list:
                stats.success += 1
                log(
                    f"阶段4 {STATUS_ICONS['success']} 已上传 {len(pic_list)} 张配图（不输出 URL）｜"
                    f"耗时 {time.monotonic() - stage:.2f}s"
                )
            else:
                stats.skipped += 1
                log(
                    f"阶段4 {STATUS_ICONS['warning']} 未获得配图地址，将无图发布｜"
                    f"耗时 {time.monotonic() - stage:.2f}s"
                )
        except Exception as exc:  # noqa: BLE001
            stats.skipped += 1
            log(
                f"阶段4 {STATUS_ICONS['warning']} 配图失败（{type(exc).__name__}），将无图发布｜"
                f"耗时 {time.monotonic() - stage:.2f}s"
            )

    # stage 5: publish
    stage = time.monotonic()
    log("阶段5 发布沸点打卡")
    stats.total += 1
    if settings.dry_run:
        stats.skipped += 1
        duration = time.monotonic() - started
        log(
            f"阶段5 {STATUS_ICONS['skipped']} dry-run 跳过真实发布 theme_id={settings.theme_id}｜"
            f"耗时 {time.monotonic() - stage:.2f}s"
        )
        log(
            f"账号统计｜总任务 {stats.total}｜成功 {stats.success}｜已完成 {stats.already}｜"
            f"跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f}s"
        )
        return AccountResult(index, identity, True, "dry-run 预演通过", duration, stats)

    last_error = ""
    for attempt in range(1, 6):
        try:
            publish_short_msg(
                cookie,
                content=content,
                pic_list=pic_list,
                theme_id=settings.theme_id,
            )
            stats.success += 1
            duration = time.monotonic() - started
            log(
                f"阶段5 {STATUS_ICONS['success']} 打卡发布成功｜"
                f"耗时 {time.monotonic() - stage:.2f}s（尝试 {attempt}/5）"
            )
            log(
                f"账号统计｜总任务 {stats.total}｜成功 {stats.success}｜已完成 {stats.already}｜"
                f"跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f}s"
            )
            return AccountResult(index, identity, True, "打卡发布成功", duration, stats)
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
            log(f"阶段5 {STATUS_ICONS['warning']} 发布失败 {last_error}，重试 {attempt}/5")
            if attempt < 5:
                time.sleep(5)

    stats.failed += 1
    duration = time.monotonic() - started
    log(f"阶段5 {STATUS_ICONS['failure']} 打卡发布失败（{last_error}）｜耗时 {time.monotonic() - stage:.2f}s")
    log(
        f"账号统计｜总任务 {stats.total}｜成功 {stats.success}｜已完成 {stats.already}｜"
        f"跳过 {stats.skipped}｜失败 {stats.failed}｜耗时 {duration:.2f}s"
    )
    return AccountResult(index, identity, False, f"打卡发布失败（{last_error}）", duration, stats)


def main() -> int:
    task_started = time.monotonic()
    start_ts = _full_ts()
    print("=" * 60, flush=True)
    log(f"任务｜{SCRIPT_NAME}")
    log(f"开始时间｜{start_ts}")
    notify_status = "not-run"
    exit_code = 1

    try:
        settings = load_settings()
    except ValueError as exc:
        mode = "dry-run" if env_truthy(DRY_RUN_ENV) else "live"
        log(f"运行模式｜{mode}")
        log(f"账号数量｜0")
        log(f"{STATUS_ICONS['failure']} 配置错误: {exc}")
        body = (
            f"任务: {SCRIPT_NAME}\n"
            f"模式: {mode}\n"
            f"结果: 配置错误\n"
            f"账号总数: 0\n成功: 0\n失败: 0\n"
            f"说明: 缺少或无效的必填凭据"
        )
        notify_status = send_notify(SCRIPT_NAME, body)
        summary = {
            "catalogId": CATALOG_ID,
            "script": SCRIPT_NAME,
            "status": "configuration-error",
            "mode": mode,
            "accounts": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "notify": notify_status,
            "durationSeconds": round(time.monotonic() - task_started, 3),
            "finishTime": _full_ts(),
        }
        log(f"通知｜{notify_status}")
        log(f"结束时间｜{summary['finishTime']}")
        log(f"最终状态: failure")
        print(f"TASK_SUMMARY={json.dumps(summary, ensure_ascii=False)}", flush=True)
        return 1

    mode = "dry-run" if settings.dry_run else "live"
    log(f"运行模式｜{mode}")
    log(f"账号数量｜{len(settings.cookies)}")
    log(f"主题｜{settings.theme_tag} ({settings.theme_id})")
    log(f"配图｜{'开启' if settings.upload_image else '关闭'}")

    results: List[AccountResult] = []
    for idx, cookie in enumerate(settings.cookies, 1):
        try:
            results.append(run_account(idx, cookie, settings))
        except Exception as exc:  # noqa: BLE001
            log(f"{STATUS_ICONS['failure']} 账号 {idx} 未捕获异常: {type(exc).__name__}")
            results.append(
                AccountResult(
                    idx,
                    f"账号{idx}",
                    False,
                    f"未捕获异常: {type(exc).__name__}",
                    0.0,
                    AccountStats(total=1, failed=1),
                )
            )
        if idx < len(settings.cookies) and not settings.dry_run:
            time.sleep(5)

    success_accounts = sum(1 for r in results if r.ok)
    failed_accounts = sum(1 for r in results if not r.ok)
    sub_total = sum(r.stats.total for r in results)
    sub_success = sum(r.stats.success for r in results)
    sub_already = sum(r.stats.already for r in results)
    sub_skipped = sum(r.stats.skipped for r in results)
    sub_failed = sum(r.stats.failed for r in results)
    duration = round(time.monotonic() - task_started, 3)
    finish_ts = _full_ts()

    if failed_accounts == 0:
        if settings.dry_run:
            final_status = "success"
            event = "dry-run"
            human = "dry-run 预演通过"
        else:
            final_status = "success"
            event = "success"
            human = "全部账号打卡成功"
        exit_code = 0
    elif success_accounts == 0:
        final_status = "failure"
        event = "failure"
        human = "全部账号失败"
        exit_code = 1
    else:
        final_status = "partial-failure"
        event = "partial-failure"
        human = "部分账号失败"
        exit_code = 1

    print("-" * 60, flush=True)
    log("任务统计")
    log(f"账号结果｜成功 {success_accounts} / 失败 {failed_accounts} / 总计 {len(results)}")
    log(
        f"子任务｜总 {sub_total}｜成功 {sub_success}｜已完成 {sub_already}｜"
        f"跳过 {sub_skipped}｜失败 {sub_failed}"
    )
    log(f"总耗时｜{duration:.2f}s")
    log(f"完成时间｜{finish_ts}")

    lines = [
        f"任务: {SCRIPT_NAME}",
        f"模式: {mode}",
        f"结果: {human}",
        f"账号总数: {len(results)}",
        f"成功: {success_accounts}",
        f"失败: {failed_accounts}",
    ]
    for r in results:
        mark = STATUS_ICONS["success"] if r.ok else STATUS_ICONS["failure"]
        lines.append(f"{mark} {r.identity}: {r.detail}")
    notify_status = send_notify(SCRIPT_NAME, "\n".join(lines))
    log(f"通知｜{notify_status}")

    icon = STATUS_ICONS["success"] if exit_code == 0 else STATUS_ICONS["failure"]
    log(f"最终状态: {final_status} {icon}")
    summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_NAME,
        "status": event,
        "finalStatus": final_status,
        "mode": mode,
        "accounts": len(results),
        "success": success_accounts,
        "failed": failed_accounts,
        "skipped": sub_skipped,
        "notify": notify_status,
        "durationSeconds": duration,
        "finishTime": finish_ts,
    }
    print(f"TASK_SUMMARY={json.dumps(summary, ensure_ascii=False)}", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
