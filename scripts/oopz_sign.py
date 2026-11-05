#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Oopz每日签到与星辉任务
# cron: 25 9 * * *
#
# 来源：Nth2Miss/oopz-auto-task oopz_sign.py（MIT）
# https://github.com/Nth2Miss/oopz-auto-task
# 提交：c6e76876ee4cd5ae9d479f7060777c4a9f1e43f7
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2026 oopz-auto-task contributors
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
"""Oopz 每日签到与社区星辉任务（青龙独立维护版）。

功能清点（相对上游 oopz_sign.py）：
- Web 端 RSA 签名后调用 gateway.oopz.cn：每日星辉签到、浏览/点赞/评论/分享/发布笔记、领取奖励
- 凭据改为环境变量多账号；手机号|密码可自动登录并在 token 失效时重登；不写盘、不落明文配置
- 评论与发布正文优先一言 HTTPS 随机文本（署名格式按公开内容策略），失败或断网预演回落本地短句
- 发布配图优先必应每日一图，失败时用 1x1 占位 PNG；断网预演不请求一言/必应/业务接口
- 移除交互登录、微信扫码、Node 浏览器助手、常驻 loop、原始响应探测与脚本内硬编码账号密码

OOPZ_ACCOUNTS：每个非空行一个账号。
  · token|uid —— 已有登录态（仅在首个竖线处分割）
  · 11 位手机号|密码 —— 密码登录并自动续期
兼容单账号别名：OOPZ_TOKEN+OOPZ_UID，或 OOPZ_PHONE+OOPZ_PASSWORD（仅当 OOPZ_ACCOUNTS 为空）。
OOPZ_ACTIONS：默认 sign,tasks（与上游 cron「签到 + 全部每日任务」一致）。
OOPZ_LOCAL_TEXT：评论/发布在一言不可用时的本地正文覆盖（最多 280 字）。
OOPZ_TIMEOUT：单次 HTTPS 超时秒数，默认 25，范围 5..120。
OOPZ_DRY_RUN=1：完全断网预演。
建议 Cron：30 8 * * *。
不打印 Token、密码、手机号、设备标识或原始响应；官方返回的昵称/uid 直接展示。
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
            "2d0eeee40adf7820",
            "scripts/oopz_sign.py",
            "oopz_sign.py",
            "oopz_sign",
            "candidate.py",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import hashlib
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "Oopz每日签到与星辉任务"
CATALOG_ID = "2d0eeee40adf7820"
GATEWAY_HOST = "gateway.oopz.cn"
GATEWAY = "https://gateway.oopz.cn"
HITOKOTO_HOST = "v1.hitokoto.cn"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
BING_HOST = "cn.bing.com"
PLATFORM = "windows"
CHANNEL = "Web"
APP_VER = "88053"
CLIENT_VERSION = "0.88.53"
LOGIN_API = "/client/v1/login/v2/login"
DEFAULT_TIMEOUT = 25
HITOKOTO_TIMEOUT = 8
HITOKOTO_LIMIT = 16384
MAX_BYTES = 262144
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ALLOWED_ACTIONS = ("sign", "tasks")
DEFAULT_ACTIONS = ("sign", "tasks")
PHONE_RE = re.compile(r"^\d{11}$")
ALREADY_HINTS = ("已签到", "已经签到", "重复签到", "已领取", "今日已", "请勿重复")
PUBLISH_TITLES = ("今日份的游戏日常", "随手记录一下", "开黑碎片时间", "今天的对局感受", "水一发社区")
LOCAL_TEXTS = (
    "打卡打卡，内容不错，支持一下！",
    "今天也是元气满满的一天呢",
    "今日打卡，顺便记录一下游戏日常！",
    "开黑愉快，把把超神，社区见。",
    "随手打卡一下，祝大家游戏愉快。",
)
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
ERROR_HINTS = {
    401: "签名不正确",
    403: "缺少请求头",
    405: "请求方法不正确",
    428: "需要登录或登录态失效",
    502: "服务端错误",
}
LOGIN_ERR_HINTS = {
    "ERROR_PASSWORD": "密码错误",
    "ERROR_SMSCODE": "验证码错误或已过期",
    "ERROR_RETRY_LIMIT": "尝试过于频繁，请稍后再试",
    "ERROR_USER_NOT_FOUND": "用户不存在",
    "ERROR_USER_DISABLE": "账号已被禁用",
}
PASSWORD_PUB_N_B64URL = (
    "wf935Evk12yBMDq5u-2WGXG7rI80-WTu5BQXVnMm2HRZWKmOEdjW5XG4WhsbidDF2hhxO4emVqRlEE-"
    "EAZ8Ro936fk-oDvuYcLGbe_AUhgkb_uCldl32inF7dYXuONb-eigNSlGjapv8Ef__rFi0srg1dJg7_j8I"
    "QBm2RC5Hgd98-7QKokpjZHQmi-WpYAyaW7rZk1s6Ac6vZiAAq8HEa-eaEFTeQBcxrgYMwL65FfNFomh3"
    "Xvd1tMMtTx-dp4dfARfJB8UHhC8_xsUlHp14KYg4YRq9eRelnM_pV1ZXEAjPCbl6hwEsGrxWz40m-OeVs"
    "EZy-XGcoeeZfZ5dbTsicQ"
)
PRIV_B64 = (
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC/dbSx0kagPRmhBdaExF7PPTr4CEc0wNE/pZQXjZwIIiaGruKg"
    "w4fPS/steNZLmLo/223cUcW17Vza/hhvhY9byP4spq9aEGdUjDYHHyBynlUYTdkbcYm2IeCQnQ99uZOPvL/Z6bJIVUXfCp2I+8hz"
    "slK7aIjNgf15YfHXdi6MPic+6lFCYk38RK+OKXlq4jZxHvM4igVxJcCwU+dP1D0Y9D/ne4WIijSIz9HTx9ANc3YeR4cxN98loo9z"
    "c11cR677midk3Z6Qn0BsHeQ48wtz8l1LgYUFiaQKUS7LbtbkfYOHBDDRMi4HQxTZmxh357jaeBNRep4Fij2dUqtkc1lRAgMBAAEC"
    "ggEAUQEsAlBFMWaogUhHCsVKl8QAPxDBj8BEx/j2P0Da01YflrxHhl00CLDNBOArSrDDnGDqilzOmbpjnwQCsqx/iwXvBFVBu4lV"
    "LqBj+39f6x6yQiYtxT60VSrgKE9LTpZFqHrjcP8/PvtVJJkJLfvZQ5ofBsujlc95vvGBsPd/mjW2LPc0+qYGMvSuySQuCmsy5jHA"
    "9zLn6TNgAuC6dDhjfD8ovNkPUt7BQn6LyvBj+Zu3mYzVSDO6aZcyzPe4hakwnFHQ/BDpgLuv+JKKHhdKbJcsgX+00oVGDThqivKq"
    "Y7MiyQIOEvO/AZIVTVIyXwYfsYZUg4noghpOoq2AEJi/QQKBgQDpQu59XGfN3cbW6n/lOTtkXLL8JSUapjY+5esir150JMxEDEnM"
    "uAwpdIxVT0OJdtjHCgMO//3vR57Af3PBCqjO9QDXhrXvwh4yDmaI8RYRZQibc1HbVsFFE5xP2c2bZcVjU9QIowt03gYSUakmxNtC"
    "M0vutKymejDvgp57PQGAJwKBgQDSH5vKkydAhCuyjCW+5e7u31jX0vPFdI/+jpNWFgUAv9aw/6omUCQLEU+dhP6/CT0Ej5LFsv1Y"
    "6+LAlfNyY+wTO+dVWl7hBDn+9rtR9+7ri7js5htd4aczzmSWO/WIGnCRr2BlcCpl8fsQIHirE+AC6sXdUey6uGCvL0XQvntNxwKB"
    "gD63nVIdh1eF2tGsSWkDg2GPvxwmjJxmtk0hGqC/0ECgKD/fofQmRDbdPGIvprQOPWj+2yWsVMWCVz/gxOnRiOPkYi6Q7NgjNGU3"
    "FACb+dgBd1f8oLS91cdR54RcxniS24jCYE9WL11j2PQR+s4OvflFu5PaBlXYotGzKBNwqrefAoGBAICKzaeTdgPF12WWztCFoTGI"
    "eLUvW+mDcUNsvT2AovbeZNxKyzA8/o+2u1nFroH3iNhtbIB9CveG9mSSVye3cQgjMVXJvxkwmLoc/mMapZJ7G1nxOvSnwr2ymV4+"
    "t+nXIt48x1/GymkrK0emVatysSuXrAvEvmlLufnxlWgp3wypAoGAGWO0G5EC/Ub7eMutFTuKM3OqZe1QfsA0czqSmRm6BxJScsZ1"
    "FUxaTfhgt/gukhcI8VSOLB9V45zOz9ZDurh5OCDhNYaGJWgvkSUQyywAM0S/ZM6xQ4RdUa3ul7iIFitxwZHBPJvIF1zlc5pD+rje"
    "+rlKfKY1WLUGaXs5QRXfEr4="
)
SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:280]


def resolve_timeout() -> float:
    raw = env("OOPZ_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("OOPZ_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 120:
        raise SafeError("OOPZ_TIMEOUT 须在 5 到 120 秒之间")
    return value


def parse_actions(raw: str) -> List[str]:
    text = raw.strip() if raw else ""
    if not text:
        return list(DEFAULT_ACTIONS)
    parts = [item.lower() for item in re.split(r"[,;\s]+", text) if item]
    if not parts:
        return list(DEFAULT_ACTIONS)
    unknown = [item for item in parts if item not in ALLOWED_ACTIONS]
    if unknown:
        raise SafeError("OOPZ_ACTIONS 含未知动作，仅允许 sign/tasks")
    ordered: List[str] = []
    for item in parts:
        if item not in ordered:
            ordered.append(item)
    return ordered


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少竖线分隔符；格式为 token|uid 或 手机号|密码")
    left, right = text.split("|", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        raise SafeError("账号行左右字段不能为空")
    if any(ord(ch) < 32 for ch in left) or any(ord(ch) < 32 for ch in right):
        raise SafeError("账号行含控制字符")
    if PHONE_RE.match(left):
        return {"kind": "password", "phone": left, "password": right, "token": "", "uid": ""}
    return {"kind": "token", "token": left, "uid": right, "phone": "", "password": ""}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("OOPZ_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("OOPZ_ACCOUNTS 没有有效账号行")
        return accounts
    token = env("OOPZ_TOKEN")
    uid = env("OOPZ_UID")
    phone = env("OOPZ_PHONE")
    password = env("OOPZ_PASSWORD")
    if token or uid:
        if not token or not uid:
            raise SafeError("单账号别名须同时提供 OOPZ_TOKEN 与 OOPZ_UID")
        return [{"kind": "token", "token": token, "uid": uid, "phone": "", "password": ""}]
    if phone or password:
        if not phone or not password:
            raise SafeError("单账号别名须同时提供 OOPZ_PHONE 与 OOPZ_PASSWORD")
        if not PHONE_RE.match(phone):
            raise SafeError("OOPZ_PHONE 须为 11 位数字手机号")
        return [{"kind": "password", "phone": phone, "password": password, "token": "", "uid": ""}]
    raise SafeError(
        "未配置 OOPZ_ACCOUNTS，或单账号别名 OOPZ_TOKEN/OOPZ_UID、OOPZ_PHONE/OOPZ_PASSWORD"
    )


def _der_walk(buf: bytes, off: int, out: List[bytes]) -> List[bytes]:
    while off < len(buf):
        tag = buf[off]
        ln = buf[off + 1]
        off += 2
        if ln & 0x80:
            nbytes = ln & 0x7F
            ln = int.from_bytes(buf[off : off + nbytes], "big")
            off += nbytes
        val = buf[off : off + ln]
        if tag == 0x30:
            _der_walk(val, 0, out)
        elif tag == 0x04:
            _der_walk(val, 0, out)
        elif tag == 0x02:
            out.append(val)
        off += ln
    return out


def _load_key() -> Tuple[int, int, int]:
    der = base64.b64decode(PRIV_B64)
    ints = _der_walk(der, 0, [])
    if len(ints) < 5:
        raise SafeError("内置签名私钥解析失败")
    n = int.from_bytes(ints[2], "big")
    d = int.from_bytes(ints[4], "big")
    k = (n.bit_length() + 7) // 8
    return n, d, k


N_PRIV, D_PRIV, K_PRIV = _load_key()


def make_sign(path_with_query: str, body_str: str, ts_ms: str) -> str:
    md5_hex = hashlib.md5((path_with_query + body_str).encode("utf-8")).hexdigest()
    payload = (md5_hex + ts_ms).encode("utf-8")
    digest_info = SHA256_DIGESTINFO_PREFIX + hashlib.sha256(payload).digest()
    em = b"\x00\x01" + b"\xff" * (K_PRIV - len(digest_info) - 3) + b"\x00" + digest_info
    sig = pow(int.from_bytes(em, "big"), D_PRIV, N_PRIV).to_bytes(K_PRIV, "big")
    return base64.b64encode(sig).decode("ascii")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _mgf1_sha256(seed: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_password(password: str) -> str:
    n_pub = int.from_bytes(_b64url_decode(PASSWORD_PUB_N_B64URL), "big")
    k = (n_pub.bit_length() + 7) // 8
    hlen = 32
    msg = password.encode("utf-8")
    if len(msg) > k - 2 * hlen - 2:
        raise SafeError("密码过长，无法按客户端算法加密")
    lhash = hashlib.sha256(b"").digest()
    ps = b"\x00" * (k - len(msg) - 2 * hlen - 2)
    db = lhash + ps + b"\x01" + msg
    seed = os.urandom(hlen)
    masked_db = bytes(a ^ b for a, b in zip(db, _mgf1_sha256(seed, len(db))))
    masked_seed = bytes(a ^ b for a, b in zip(seed, _mgf1_sha256(masked_db, hlen)))
    em = b"\x00" + masked_seed + masked_db
    cipher = pow(int.from_bytes(em, "big"), 65537, n_pub).to_bytes(k, "big")
    return base64.b64encode(cipher).decode("ascii")


def placeholder_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        block = tag + data
        return struct.pack(">I", len(data)) + block + struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
        + chunk(b"IEND", b"")
    )


def business_ok(status: Optional[int], payload: Any) -> bool:
    if status != 200 or not isinstance(payload, dict):
        return False
    return payload.get("status") is True


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "error", "errmsg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value, 120)
    return ""


def format_hitokoto(payload: Any) -> str:
    text = normalize_public_text(payload.get("hitokoto") if isinstance(payload, dict) else "")
    if not text:
        raise SafeError("文案缺失")
    author = normalize_public_text(payload.get("from_who") if isinstance(payload, dict) else "")
    source = normalize_public_text(payload.get("from") if isinstance(payload, dict) else "")
    if author and source:
        text = "{} —— {}《{}》".format(text, author, source)
    elif source:
        text = "{} ——《{}》".format(text, source)
    elif author:
        text = "{} —— {}".format(text, author)
    text = normalize_public_text(text)
    if not text:
        raise SafeError("文案缺失")
    if len(text) > 280:
        raise SafeError("署名后的文案过长")
    return text


def local_public_text(min_len: int = 1) -> str:
    override = normalize_public_text(env("OOPZ_LOCAL_TEXT"))
    base = override or random.choice(LOCAL_TEXTS)
    base = normalize_public_text(base) or LOCAL_TEXTS[0]
    while len(base) < min_len:
        extra = normalize_public_text(random.choice(LOCAL_TEXTS))
        base = normalize_public_text((base + " " + extra).strip())
        if len(base) >= 280:
            break
    return base[:280]


def http_exchange(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    limit: int = MAX_BYTES,
    dry_run: bool = False,
    allow_hosts: Optional[Tuple[str, ...]] = None,
    raw_body: Optional[bytes] = None,
) -> Dict[str, Any]:
    if dry_run:
        raise SafeError("断网预演禁止 HTTP 请求")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    allowed = allow_hosts or (GATEWAY_HOST,)
    if host not in allowed:
        raise SafeError("拒绝访问非白名单主机")
    request_headers = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    data = raw_body
    if data is None and body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json;charset=utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            raise SafeError("不支持的请求体类型")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            status = int(response.getcode())
            raw = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        status = int(error.code)
        try:
            raw = error.read(limit + 1)
        except Exception:
            raw = b""
        finally:
            error.close()
    except Exception as exc:
        raise SafeError("网络请求失败：{}".format(type(exc).__name__)) from None
    if len(raw) > limit:
        raise SafeError("响应过大，已中止解析")
    text = raw.decode("utf-8", errors="replace")
    payload: Any = None
    if text.strip():
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
    return {"status": status, "json": payload, "text": text, "raw": raw}


class AccountRunner:
    def __init__(self, number: int, hint: str = ""):
        self.number = number
        self.hint = hint
        self.identity = ""
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"

    def display(self) -> str:
        return self.identity or self.hint or "账号{}".format(self.number)

    def stage(self, number: int, name: str, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        state, detail = "failure", "操作未完成"
        try:
            state, detail, result = operation()
            return result
        except SafeError as error:
            detail = str(error)
            raise
        except Exception:
            detail = "内部处理失败，已抑制异常详情"
            raise SafeError(detail) from None
        finally:
            self.stats[state] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number: int, name: str, reason: str) -> None:
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self) -> None:
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                self.display(),
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


class OopzClient:
    def __init__(self, timeout: float, dry_run: bool = False, token: str = "", uid: str = ""):
        self.timeout = timeout
        self.dry_run = dry_run
        self.token = token
        self.uid = str(uid or "")
        self.display_name = ""

    def request(
        self,
        path: str,
        method: str = "POST",
        body: Any = None,
        with_auth: bool = True,
        limit: int = MAX_BYTES,
    ) -> Dict[str, Any]:
        ts = str(int(time.time() * 1000))
        body_str = "" if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = {
            "accept": "*/*",
            "content-type": "application/json;charset=utf-8",
            "oopz-app-version-number": APP_VER,
            "oopz-channel": CHANNEL,
            "oopz-device-id": str(uuid.uuid4()),
            "oopz-platform": PLATFORM,
            "oopz-request-id": str(uuid.uuid4()),
            "oopz-time": ts,
            "oopz-web": "true",
            "oopz-sign": make_sign(path, body_str, ts),
            "origin": "https://web.oopz.cn",
            "referer": "https://web.oopz.cn/",
            "user-agent": UA,
        }
        if with_auth:
            if not self.token:
                raise SafeError("缺少登录 token")
            headers["oopz-signature"] = self.token
            headers["oopz-person"] = self.uid
        return http_exchange(
            GATEWAY + path,
            method=method,
            headers=headers,
            body=body_str if body_str else None,
            timeout=self.timeout,
            limit=limit,
            dry_run=self.dry_run,
            allow_hosts=(GATEWAY_HOST,),
        )

    def describe_status(self, status: Optional[int]) -> str:
        if status is None:
            return "网络错误"
        hint = ERROR_HINTS.get(status, "")
        return "HTTP {}".format(status) + ("（{}）".format(hint) if hint else "")

    def verify_session(self) -> Tuple[str, str, None]:
        result = self.request(
            "/general/v3/settings?oopzChannel=Web&versionNo={}".format(APP_VER),
            method="GET",
            body=None,
        )
        status = result["status"]
        if status == 428:
            raise SafeError("登录态失效（HTTP 428）")
        if not business_ok(status, result["json"]):
            raise SafeError("凭证校验失败：{}".format(self.describe_status(status)))
        return "success", "凭证有效", None

    def login_password(self, phone: str, password: str) -> Tuple[str, str, Dict[str, str]]:
        device_id = str(uuid.uuid4())
        body = {
            "auto": True,
            "code": encrypt_password(password),
            "loginType": "PASSWORD",
            "phone": phone,
            "autoRegister": False,
            "yunhaiToken": "",
            "deviceId": device_id,
            "deviceRam": "TBD",
            "deviceProcessor": "0",
            "loggedIn": device_id,
            "osEdition": "web",
            "osVersion": "web/_BrowserName.chrome",
            "resolution": "TBD",
            "graphics": "TBD",
            "clientVersion": CLIENT_VERSION,
        }
        result = self.request(LOGIN_API, method="POST", body=body, with_auth=False)
        payload = result["json"] if isinstance(result["json"], dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        token = data.get("signature") or data.get("token")
        uid = data.get("uid")
        name = data.get("name") or data.get("nickname") or ""
        if isinstance(token, str) and token and uid is not None:
            self.token = str(token)
            self.uid = str(uid)
            if isinstance(name, str) and name.strip():
                self.display_name = compact(name, 64)
            detail = "密码登录成功"
            if self.display_name:
                detail = "密码登录成功；昵称 {}；uid {}".format(self.display_name, self.uid)
            else:
                detail = "密码登录成功；uid {}".format(self.uid)
            return "success", detail, {"token": self.token, "uid": self.uid, "name": self.display_name}
        dtype = data.get("type") if isinstance(data, dict) else None
        if dtype in LOGIN_ERR_HINTS:
            raise SafeError("登录失败：{}".format(LOGIN_ERR_HINTS[dtype]))
        message = business_message(payload) or self.describe_status(result["status"])
        raise SafeError("登录失败：{}".format(message))

    def sign_in(self) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        result = self.request("/task/v1/signIn", method="POST", body={})
        status = result["status"]
        payload = result["json"] if isinstance(result["json"], dict) else {}
        raw_compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload else ""
        message = business_message(payload)
        if status == 428:
            raise SafeError("签到失败：登录态失效")
        if status == 200 and any(hint in (message or raw_compact) for hint in ALREADY_HINTS):
            return "alreadyComplete", "今日已签到", None
        data = payload.get("data")
        if business_ok(status, payload) and data is not None:
            award = ""
            if isinstance(data, dict):
                award_type = data.get("awardType")
                award_num = data.get("awardNum")
                if award_type is not None and award_num is not None:
                    award = "；奖励 {}×{}".format(award_type, award_num)
            confirmed = self._signin_state()
            if confirmed is not None:
                days, today = confirmed
                if not today:
                    raise SafeError("签到接口返回成功但服务端日历未更新")
                return "success", "签到成功；连续 {} 天{}".format(days, award), {"days": days}
            return "success", "签到成功{}".format(award), None
        raise SafeError("签到失败：{}".format(message or self.describe_status(status)))

    def _signin_state(self) -> Optional[Tuple[int, bool]]:
        result = self.request("/task/v1/detail", method="GET", body=None)
        if not business_ok(result["status"], result["json"]):
            return None
        payload = result["json"] if isinstance(result["json"], dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        sign = data.get("signInEveryDay") if isinstance(data.get("signInEveryDay"), dict) else {}
        if not sign:
            return None
        return int(sign.get("signInNum") or 0), bool(sign.get("isTodaySignIn"))

    def _task_status(self) -> Dict[int, Tuple[str, str, int]]:
        result = self.request("/task/v1/detail", method="GET", body=None)
        if not business_ok(result["status"], result["json"]):
            return {}
        payload = result["json"] if isinstance(result["json"], dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        everyday = data.get("taskEveryDay") if isinstance(data.get("taskEveryDay"), dict) else {}
        items = everyday.get("list") if isinstance(everyday.get("list"), list) else []
        out: Dict[int, Tuple[str, str, int]] = {}
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                continue
            try:
                tid = int(item["id"])
            except (TypeError, ValueError):
                continue
            out[tid] = (
                str(item.get("title") or ""),
                str(item.get("progress") or ""),
                int(item.get("state") or 0),
            )
        return out

    def _fetch_feed(self, n: int = 12) -> List[Dict[str, Any]]:
        result = self.request("/community/v1/feed?pageSize={}".format(n), method="GET", body=None)
        if not business_ok(result["status"], result["json"]):
            return []
        payload = result["json"] if isinstance(result["json"], dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        items = data.get("list") if isinstance(data.get("list"), list) else []
        return [item for item in items if isinstance(item, dict) and item.get("momentId")]

    def published_text(self, min_len: int = 20) -> Tuple[str, str]:
        fallback = local_public_text(min_len)
        if self.dry_run:
            return fallback, "断网预演：不请求一言，使用本地文案"
        try:
            result = http_exchange(
                HITOKOTO_URL,
                method="GET",
                timeout=min(self.timeout, HITOKOTO_TIMEOUT),
                limit=HITOKOTO_LIMIT,
                dry_run=False,
                allow_hosts=(HITOKOTO_HOST,),
            )
            if result["status"] != 200 or not isinstance(result["json"], dict):
                raise SafeError("文案接口响应不可用")
            text = format_hitokoto(result["json"])
            if len(text) < min_len:
                text = normalize_public_text(text + " " + fallback)[:280]
            return text, "使用一言文案，保留作者和作品署名"
        except Exception:
            return fallback, "一言不可用，使用本地发言文案"

    def _bing_daily_image(self) -> Optional[Tuple[bytes, int, int, Dict[str, Any]]]:
        try:
            meta = http_exchange(
                "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1",
                method="GET",
                timeout=min(self.timeout, 20),
                limit=65536,
                dry_run=self.dry_run,
                allow_hosts=(BING_HOST,),
            )
            if meta["status"] != 200 or not isinstance(meta["json"], dict):
                return None
            images = meta["json"].get("images")
            if not isinstance(images, list) or not images:
                return None
            img = images[0] if isinstance(images[0], dict) else None
            if not img:
                return None
            path = str(img.get("url") or "")
            if not path:
                return None
            image = http_exchange(
                "https://cn.bing.com" + path,
                method="GET",
                timeout=min(self.timeout, 30),
                limit=5 * 1024 * 1024,
                dry_run=self.dry_run,
                allow_hosts=(BING_HOST,),
            )
            if image["status"] != 200 or not image.get("raw"):
                return None
            return image["raw"], 0, 0, img
        except Exception:
            return None

    def _upload_image(
        self,
        data: Optional[bytes] = None,
        filename: str = "a.png",
        content_type: str = "image/png",
    ) -> Optional[str]:
        blob = data if data is not None else placeholder_png()
        for _ in range(2):
            result = self.request(
                "/v1/upload/getCommunityImagePreSignUrl",
                method="POST",
                body={"fileName": filename, "contentType": content_type},
            )
            if not business_ok(result["status"], result["json"]):
                return None
            payload = result["json"] if isinstance(result["json"], dict) else {}
            up = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            put_url = up.get("url")
            if not isinstance(put_url, str) or not put_url:
                return None
            put_host = urllib.parse.urlparse(put_url).hostname or ""
            uploaded = False
            for _retry in range(3):
                try:
                    http_exchange(
                        put_url,
                        method="PUT",
                        headers={"Content-Type": content_type, "User-Agent": UA},
                        timeout=min(max(self.timeout, 30), 120),
                        limit=4096,
                        dry_run=self.dry_run,
                        allow_hosts=(put_host,),
                        raw_body=blob,
                    )
                    uploaded = True
                    break
                except Exception:
                    time.sleep(1.0)
            if not uploaded:
                continue
            host_url = up.get("hostUrl")
            if isinstance(host_url, str) and host_url:
                return host_url
            path = up.get("path") or urllib.parse.unquote(urllib.parse.urlparse(put_url).path)
            origin = urllib.parse.urlparse(put_url)
            if not str(path).startswith("/"):
                path = "/" + str(path)
            return "{}://{}{}".format(origin.scheme, origin.netloc, path)
        return None

    def _publish_note(self, title: str, content: str, bing_info=None) -> Tuple[str, str, None]:
        width = height = 1
        if bing_info:
            data, width, height, _meta = bing_info
            res = self._upload_image(data=data, filename="bing.jpg", content_type="image/jpeg")
            if not res:
                res = self._upload_image()
                width = height = 1
        else:
            res = self._upload_image()
        if not res:
            raise SafeError("图片上传失败，无法发布笔记")
        body = {
            "groupType": "article",
            "title": title,
            "content": content,
            "imageList": [
                {
                    "cover": res,
                    "resource": res,
                    "resourceType": "IMAGE",
                    "sourceResource": "",
                    "height": height or 1,
                    "width": width or 1,
                }
            ],
        }
        result = self.request("/community/v1/publish", method="POST", body=body)
        if business_ok(result["status"], result["json"]):
            return "success", "笔记发布成功", None
        message = business_message(result["json"]) or self.describe_status(result["status"])
        raise SafeError("笔记发布失败：{}".format(message))

    def run_daily_tasks(self) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        before = self._task_status()
        feed = self._fetch_feed(12)
        if not feed:
            raise SafeError("社区 feed 为空，无法执行每日任务")
        viewed = 0
        for item in feed:
            if viewed >= 10:
                break
            mid = item.get("momentId")
            result = self.request(
                "/community/v1/detail?momentId={}".format(mid),
                method="GET",
                body=None,
            )
            if business_ok(result["status"], result["json"]):
                viewed += 1
            time.sleep(0.25)
        liked = 0
        for item in feed:
            if liked >= 3:
                break
            result = self.request(
                "/community/v1/like",
                method="POST",
                body={"momentId": item.get("momentId"), "author": item.get("author"), "like": 1},
            )
            if business_ok(result["status"], result["json"]):
                liked += 1
            time.sleep(0.3)
        target = feed[0]
        comment_text, comment_note = self.published_text(min_len=8)
        comment = self.request(
            "/community/v1/moment/comment_commit",
            method="POST",
            body={"momentId": target.get("momentId"), "content": comment_text},
        )
        comment_ok = business_ok(comment["status"], comment["json"])
        share = self.request(
            "/community/v1/share",
            method="POST",
            body={"momentId": target.get("momentId"), "author": target.get("author")},
        )
        share_ok = business_ok(share["status"], share["json"])
        pub_done = (before.get(9) or ("", "", 0))[2] != 0
        publish_ok = pub_done
        publish_note = "今日发布任务已完成，跳过"
        if not pub_done:
            title = random.choice(PUBLISH_TITLES)
            note_content, text_note = self.published_text(min_len=20)
            bing = self._bing_daily_image()
            if bing:
                bing_title = compact((bing[3].get("title") or ""), 40)
                if bing_title and bing_title not in title:
                    title = "{}｜{}".format(title, bing_title)
                copyright_text = compact((bing[3].get("copyright") or ""), 60)
                if copyright_text:
                    note_content = normalize_public_text(
                        note_content + " 配图：今日必应每日一图 · " + copyright_text
                    )
            try:
                self._publish_note(title, note_content, bing_info=bing)
                publish_ok = True
                publish_note = "发布成功（{}）".format(text_note)
            except SafeError:
                time.sleep(2)
                note_content2 = normalize_public_text(note_content + " 补充：祝大家游戏愉快！")
                self._publish_note(title, note_content2, bing_info=bing)
                publish_ok = True
                publish_note = "发布重试成功（{}）".format(text_note)
        time.sleep(1.5)
        after = self._task_status()
        claimed = 0
        for tid, (title2, _prog, _state) in after.items():
            result = self.request("/task/v1/receive", method="POST", body={"taskId": tid})
            if business_ok(result["status"], result["json"]):
                claimed += 1
            time.sleep(0.2)
        if viewed < 1 and liked < 1 and not comment_ok and not share_ok and not publish_ok:
            raise SafeError("每日任务均未成功")
        detail = (
            "浏览 {}；点赞 {}；评论 {}；分享 {}；发布 {}；领取 {}；文案：{}".format(
                viewed,
                liked,
                "成功" if comment_ok else "失败",
                "成功" if share_ok else "失败",
                publish_note if publish_ok else "失败",
                claimed,
                comment_note,
            )
        )
        return "success", detail, {
            "viewed": viewed,
            "liked": liked,
            "comment": comment_ok,
            "share": share_ok,
            "publish": publish_ok,
            "claimed": claimed,
        }


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    actions: List[str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if account["kind"] == "password":
            if not PHONE_RE.match(account["phone"]) or not account["password"]:
                raise SafeError("手机号或密码格式无效")
            return "success", "账号本地格式检查通过（密码登录，不输出号码）", None
        if not account["token"] or not account["uid"]:
            raise SafeError("token 或 uid 为空")
        return "success", "账号本地格式检查通过（token 登录态）", None

    runner.stage(1, "参数检查", parameter_check)
    stage_no = 2

    if dry_run:
        runner.skip(stage_no, "准备会话", "断网预演：不登录、不校验凭证")
        stage_no += 1
        for action in actions:
            label = {"sign": "执行签到", "tasks": "每日星辉任务"}[action]
            runner.skip(stage_no, label, "断网预演：不请求业务接口")
            stage_no += 1
        runner.status = "dry-run"
        log("账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(runner.number))
        return

    client = OopzClient(timeout=timeout, dry_run=False)

    def prepare_session():
        if account["kind"] == "password":
            state, detail, meta = client.login_password(account["phone"], account["password"])
            if meta.get("name"):
                runner.identity = meta["name"]
            elif client.uid:
                runner.identity = "uid:{}".format(client.uid)
            return state, detail, meta
        client.token = account["token"]
        client.uid = account["uid"]
        runner.identity = "uid:{}".format(client.uid)
        try:
            return client.verify_session()
        except SafeError as error:
            raise SafeError("token 会话不可用：{}".format(error)) from error

    try:
        runner.stage(stage_no, "准备会话", prepare_session)
    except SafeError:
        runner.status = "failure"
        return
    stage_no += 1
    if runner.identity:
        log("账号 {} 公开身份：{}".format(runner.number, runner.identity))

    critical_failed = False
    for action in actions:
        if action == "sign":

            def sign_stage():
                try:
                    return client.sign_in()
                except SafeError as error:
                    if account["kind"] == "password" and "登录态失效" in str(error):
                        client.login_password(account["phone"], account["password"])
                        return client.sign_in()
                    raise

            try:
                runner.stage(stage_no, "执行签到", sign_stage)
            except SafeError:
                critical_failed = True
        elif action == "tasks":

            def tasks_stage():
                try:
                    return client.run_daily_tasks()
                except SafeError as error:
                    if account["kind"] == "password" and "登录态失效" in str(error):
                        client.login_password(account["phone"], account["password"])
                        return client.run_daily_tasks()
                    raise

            try:
                runner.stage(stage_no, "每日星辉任务", tasks_stage)
            except SafeError:
                critical_failed = True
        stage_no += 1

    if critical_failed:
        runner.status = "failure"
    elif runner.stats["success"] > 0 or runner.stats["alreadyComplete"] > 0:
        runner.status = "success" if runner.stats["success"] > 0 else "alreadyComplete"
    else:
        runner.status = "failure"


PY_NOTIFY_RUNNER = r'''
import importlib.util
import json
import os
import socket
import sys
specification = json.load(sys.stdin)
if specification.get("dry_run"):
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    socket.socket = denied  # type: ignore
    socket.create_connection = denied  # type: ignore
    for name in ("system", "popen", "execv", "execve", "spawnv", "spawnve"):
        if hasattr(os, name):
            setattr(os, name, denied)
sys.path.insert(0, specification["directory"])
module = None
if specification["path"] is None:
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as error:
        sys.exit(3 if error.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", specification["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
sender = getattr(module, "send", None)
if not callable(sender):
    sys.exit(3)
result = sender(specification["title"], specification["body"])
sys.exit(1 if result is False else 0)
'''

JS_NOTIFY_RUNNER = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (input.dry_run) {
  const denied = () => { throw new Error('dry-run forbids network and external processes'); };
  require('net').Socket.prototype.connect = denied;
  require('dgram').createSocket = denied;
  for (const name of ['http', 'https']) {
    require(name).request = denied;
    require(name).get = denied;
  }
  require('tls').connect = denied;
  require('http2').connect = denied;
  const dns = require('dns');
  for (const key of Object.keys(dns)) if (typeof dns[key] === 'function') dns[key] = denied;
  for (const key of Object.keys(dns.promises)) if (typeof dns.promises[key] === 'function') dns.promises[key] = denied;
  const cp = require('child_process');
  for (const key of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) cp[key] = denied;
  require('worker_threads').Worker = denied;
  globalThis.fetch = denied;
}
Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
  .then(result => process.exit(result === false ? 1 : 0))
  .catch(() => process.exit(1));
'''


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
        "oopz_sign.py",
        "candidate.py",
        "scripts/oopz_sign.py",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    if dry_run:
        log("通知：⏭️ 断网预演仅生成脱敏摘要，不投递外部通知")
        log("通知摘要：" + body)
        return "dry-run-skipped"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": False,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(
        ("python", directory / "notify.py")
        for directory in paths
        if (directory / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", directory / "sendNotify.js")
            for directory in paths
            if (directory / "sendNotify.js").is_file()
        )
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = (
            [sys.executable, "-c", PY_NOTIFY_RUNNER]
            if kind == "python"
            else [node, "-e", JS_NOTIFY_RUNNER]
        )
        try:
            result = subprocess.run(
                command,
                input=json.dumps(specification, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                log("通知：✅ 脱敏总结已交给青龙适配器")
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用或投递失败；保留业务退出码")
    return "unavailable-or-failed"


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("OOPZ_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    actions = list(DEFAULT_ACTIONS)
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
            raise SafeError("OOPZ_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        actions = parse_actions(env("OOPZ_ACTIONS"))
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；动作：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                ",".join(actions),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, account in enumerate(accounts_data, 1):
            runner = AccountRunner(number, hint="账号{}".format(number))
            accounts.append(runner)
            try:
                run_account(runner, account, actions, timeout, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        state: sum(a.status == state for a in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
        final_label = "配置错误"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
        final_label = "部分失败"
    elif failed:
        status = "failure"
        final_label = "失败"
    elif dry_run:
        status = "dry-run"
        final_label = "预演完成"
    else:
        status = "success"
        final_label = "成功"
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
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
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
        print("无网络预演通过", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
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
