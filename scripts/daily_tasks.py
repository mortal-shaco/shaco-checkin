#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 二重螺旋皎皎角每日任务
# cron: 3 8 * * *
"""二重螺旋（Duet Night Abyss）皎皎角社区每日任务 — 青龙独立维护版。

MIT License
Copyright (c) 2026 abyss-stars

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Derived from abyss-stars/dna-sign src/daily_tasks.py（及同仓签名算法实现），
commit 9c33ca7dd0bb92b177563e0d6c1274f9ff0d61b5，MIT。
Catalog 3b82fe4eb92e84d2 / SHA256
fce874e6b7510418d86d7ab6130458029c08f0b176ce977e26b7767a210728ca.

用户可见能力（与上游 daily_tasks 一致）：
1. 浏览社区帖子（viewCommunity / viewCount）
2. 点赞帖子（forum/like）
3. 分享任务（encourage/level/shareTask）
4. 回复评论区（forum/comment/createComment，正式运行优先一言文案）
5. 社区签到（user/signIn）

参数获取：
1. 在 Android 模拟器安装并登录「皎皎角」App（勿用网页 token，否则易 403）。
2. 从 App 数据提取：
   - token：user_data.xml 登录会话
   - devCode：g_hu_sp.xml 的 dv_id / androidIdSysKey 等设备码
   - 可选 refreshToken：login_data.refreshToken（access token 约 14 天到期时可自动续期）
3. 写入 DNA_ACCOUNTS，每行一个账号：token|devCode 或 token|devCode|refreshToken
   仅按竖线拆分字段；不要用 & 或 @ 分隔账号。

兼容别名：未设置 DNA_ACCOUNTS 时可用 DNA_TOKEN + DNA_DEVICE_CODE（多行一一对应），
可选 DNA_REFRESH_TOKEN。

可选：
- DNA_SIGN_MODE=h5|app（默认有设备码则 app）
- DNA_LOCAL_TEXT 评论本地回退文案（多行或逗号分隔）
- DNA_DRY_RUN=1 完全断网预演
- DNA_HTTP_TIMEOUT 请求超时秒（默认 15）

依赖：公开 PyPI 包 requests、cryptography。不依赖私有仓库或本机预装应用。
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
            "3b82fe4eb92e84d2",
            "scripts/dna_bbs_daily_tasks.py",
            "dna_bbs_daily_tasks.py",
            "candidate.py",
            "output/candidate.py",
            "daily_tasks.py",
        )
        if not _ql_notify_selectors or (
            len(_ql_notify_selectors) == 1 and _ql_notify_selectors[0] == ""
        ):
            _ql_notify_enabled = False
        elif "*" in _ql_notify_selectors:
            _ql_notify_enabled = True
        else:
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
import importlib.util
import json
import os
import random
import re
import string
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

TASK_NAME = "二重螺旋皎皎角每日任务"
CATALOG_ID = "3b82fe4eb92e84d2"
NOTIFY_IDENTITIES = (
    CATALOG_ID,
    "scripts/dna_bbs_daily_tasks.py",
    "dna_bbs_daily_tasks.py",
    "candidate.py",
    "output/candidate.py",
    "daily_tasks.py",
)
DRY_RUN_ENV = "DNA_DRY_RUN"
BASE_URL = "https://dnabbs-api.yingxiong.com/"
GAME_ID = 268
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_TIMEOUT = 8
HITOKOTO_MAX_BYTES = 16384
PUBLIC_TEXT_MAX = 280

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}

LOCAL_FALLBACK_TEXTS = (
    "签到打卡",
    "水水水",
    "每日一签",
    "支持一下",
    "好帖顶一个",
    "感谢分享",
    "路过看看",
    "加油加油",
    "来了来了",
)

SECRETS: list[str] = []
_DIGIT_ALPHABET = "01234567890123456789012345678901234567890123456789010123456789"


@dataclass
class Account:
    index: int
    token: str
    device_code: str
    refresh_token: str = ""


@dataclass
class StageResult:
    name: str
    status: str
    detail: str
    elapsed: float


@dataclass
class AccountResult:
    index: int
    identity: str
    ok: bool
    message: str
    stages: list[StageResult] = field(default_factory=list)
    elapsed: float = 0.0
    stats: dict[str, int] = field(default_factory=dict)


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str, icon: str = "") -> None:
    prefix = f"{icon} " if icon else ""
    print(f"[{clock()}] {prefix}{message}", flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(name: str, default: str = "0") -> bool:
    raw = env(name, default).lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES or raw == "":
        return False
    raise ValueError(f"{name} 必须是开关值 1/0（true/false/yes/no/on/off）")


def dry_run_enabled() -> bool:
    return truthy(DRY_RUN_ENV, "0")


def remember_secret(value: str) -> None:
    value = (value or "").strip()
    if value and value not in SECRETS:
        SECRETS.append(value)


def redact(text: Any, limit: int = 200) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted(SECRETS, key=len, reverse=True):
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
    if re.search(r"(?i)(cookie|token|session|authorization|refresh)", text):
        return ""
    return "".join(ch if ch.isprintable() else " " for ch in text).strip()


def http_timeout() -> float:
    raw = env("DNA_HTTP_TIMEOUT", "15") or "15"
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("DNA_HTTP_TIMEOUT 必须是数字") from exc
    if value <= 0:
        raise ValueError("DNA_HTTP_TIMEOUT 必须大于 0")
    return value


def parse_accounts() -> list[Account]:
    accounts: list[Account] = []
    raw = env("DNA_ACCOUNTS")
    if raw:
        for index, line in enumerate(raw.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise ValueError(
                    f"第 {index} 行账号格式无效：需要 token|devCode 或 token|devCode|refreshToken"
                )
            token, rest = line.split("|", 1)
            token = token.strip()
            if "|" in rest:
                device_code, refresh_token = rest.split("|", 1)
                device_code = device_code.strip()
                refresh_token = refresh_token.strip()
            else:
                device_code = rest.strip()
                refresh_token = ""
            if not token or not device_code:
                raise ValueError(f"第 {index} 行缺少 token 或设备码")
            remember_secret(token)
            remember_secret(device_code)
            remember_secret(refresh_token)
            accounts.append(
                Account(
                    index=len(accounts) + 1,
                    token=token,
                    device_code=device_code,
                    refresh_token=refresh_token,
                )
            )
        if not accounts:
            raise ValueError("DNA_ACCOUNTS 没有有效账号行")
        return accounts

    tokens = [ln.strip() for ln in env("DNA_TOKEN").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    devices = [
        ln.strip()
        for ln in env("DNA_DEVICE_CODE").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    refreshes = [
        ln.strip()
        for ln in env("DNA_REFRESH_TOKEN").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not tokens:
        raise ValueError(
            "未配置凭据：请设置 DNA_ACCOUNTS（推荐），或兼容别名 DNA_TOKEN + DNA_DEVICE_CODE"
        )
    if not devices:
        raise ValueError("兼容模式下必须同时设置 DNA_DEVICE_CODE（与 DNA_TOKEN 按行对应）")
    if len(devices) not in (1, len(tokens)):
        raise ValueError("DNA_DEVICE_CODE 行数须为 1 或与 DNA_TOKEN 相同")
    if refreshes and len(refreshes) not in (1, len(tokens)):
        raise ValueError("DNA_REFRESH_TOKEN 行数须为 1 或与 DNA_TOKEN 相同")
    for i, token in enumerate(tokens):
        device = devices[0] if len(devices) == 1 else devices[i]
        refresh = ""
        if refreshes:
            refresh = refreshes[0] if len(refreshes) == 1 else refreshes[i]
        remember_secret(token)
        remember_secret(device)
        remember_secret(refresh)
        accounts.append(Account(index=i + 1, token=token, device_code=device, refresh_token=refresh))
    return accounts


# ─── 签名算法（源自上游 dna_sign.py，H5 + App）──────────────────────────────


def rand_str(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def rand_str2(length: int = 16) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def md5_upper(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest().upper()


def shuffle_md5(md5_hex: str) -> str:
    if len(md5_hex) <= 23:
        return md5_hex
    chars = list(md5_hex)
    for a, b in ((1, 13), (5, 17), (7, 23)):
        chars[a], chars[b] = chars[b], chars[a]
    return "".join(chars)


def swap_positions(s: str, swaps: list[tuple[int, int]]) -> str:
    chars = list(s)
    for a, b in swaps:
        if 0 <= a < len(chars) and 0 <= b < len(chars):
            chars[a], chars[b] = chars[b], chars[a]
    return "".join(chars)


def rsa_encrypt(text: str, public_key_b64: str) -> str:
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    key_bytes = [public_key_b64[i : i + 64] for i in range(0, len(public_key_b64), 64)]
    pem = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(key_bytes) + "\n-----END PUBLIC KEY-----"
    public_key = load_pem_public_key(pem.encode("ascii"))
    data = text.encode("utf-8")
    max_chunk = public_key.key_size // 8 - 11
    result = b""
    for i in range(0, len(data), max_chunk):
        result += public_key.encrypt(data[i : i + max_chunk], padding.PKCS1v15())
    return base64.b64encode(result).decode("ascii")


def generate_sa_h5() -> tuple[str, str]:
    ts = str(int(time.time() * 1000))
    raw = [random.choice("0123456789") for _ in range(30)]
    ti = 0
    for pos, n in ((3, 5), (18, 6), (27, 2)):
        for j in range(n):
            raw[pos + j] = ts[ti] if ti < len(ts) else "0"
            ti += 1
    raw_sa = "".join(raw)
    shuffled = swap_positions(raw_sa, [(5, 19), (11, 22), (17, 28)])
    return raw_sa, shuffled


class _JavaRandom:
    multiplier = 0x5DEECE66D
    addend = 0xB
    mask = (1 << 48) - 1

    def __init__(self, seed: int) -> None:
        self.seed = (seed ^ self.multiplier) & self.mask

    def next(self, bits: int) -> int:
        self.seed = (self.seed * self.multiplier + self.addend) & self.mask
        return self.seed >> (48 - bits)

    def next_int(self, bound: int) -> int:
        if (bound & -bound) == bound:
            return (bound * self.next(31)) >> 31
        n = self.next(31)
        t = n % bound
        while n - t + (bound - 1) < 0:
            n = self.next(31)
            t = n % bound
        return t


def generate_sa_app() -> tuple[str, str]:
    jr = _JavaRandom(int(time.time() * 1000))
    raw_sa = "".join(_DIGIT_ALPHABET[jr.next_int(62)] for _ in range(30))
    t = swap_positions(raw_sa, [(1, 17), (9, 20), (15, 16), (22, 27)])
    ts = str(int(time.time() * 1000))
    if len(t) != 30 or len(ts) < 13:
        return raw_sa, t
    ti = 0
    out: list[str] = []
    for a in range(len(t)):
        if a in (8, 16):
            out.append(ts[ti : ti + 5])
            ti += 5
        elif a == 22:
            out.append(ts[ti : ti + 3])
            ti += 3
        out.append(t[a])
    return raw_sa, "".join(out)


def build_sign_string(params: dict, key: str, truthy_only: bool) -> str:
    pairs = []
    for k in sorted(params.keys()):
        v = params[k]
        if truthy_only:
            if v:
                pairs.append(f"{k}={v}")
        elif v is not None and v != "":
            pairs.append(f"{k}={v}")
    pairs.append(key)
    return "&".join(pairs)


def xor_encode(text: str, key: str) -> str:
    text_bytes = text.encode("utf-8")
    key_bytes = key.encode("utf-8")
    return "".join(
        f"@{(tb & 0xFF) + (key_bytes[i % len(key_bytes)] & 0xFF)}"
        for i, tb in enumerate(text_bytes)
    )


def build_signature(public_key_b64: str, payload: dict, token: str, mode: str) -> dict:
    rk = rand_str(16)
    if mode == "app":
        raw_sa, shuffled_sa = generate_sa_app()
    else:
        raw_sa, shuffled_sa = generate_sa_h5()
    augmented = {k: str(v) for k, v in payload.items()}
    if token:
        augmented["token"] = token
    augmented["sa"] = raw_sa
    if mode == "app":
        sign_str = build_sign_string(augmented, rk, truthy_only=False)
        o = shuffle_md5(md5_upper(sign_str))
    else:
        sign_str = build_sign_string(augmented, rk, truthy_only=True)
        o = shuffle_md5(md5_upper(sign_str))
    u = xor_encode(o, rk)
    tn = f"{rsa_encrypt(rk, public_key_b64)},{u}"
    return {"rk": rk, "tn": tn, "sa": shuffled_sa}


def resolve_sign_mode(device_code: str) -> str:
    mode = env("DNA_SIGN_MODE").lower()
    if mode in ("h5", "app"):
        return mode
    return "app" if device_code else "h5"


def base_headers(token: str, device_code: str, mode: str) -> dict[str, str]:
    if mode == "app":
        headers = {
            "countrycode": "CN",
            "version": "1.4.0",
            "versioncode": "10",
            "source": "android",
            "lang": "zh-Hans",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/3.10.0",
        }
        if device_code:
            headers["devCode"] = device_code
    else:
        headers = {
            "version": "3.11.1",
            "source": "h5",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            "origin": "https://dnabbs.yingxiong.com",
            "refer": "https://dnabbs.yingxiong.com/",
            "devCode": "2" + rand_str2(32),
        }
    if token:
        headers["token"] = token
    return headers


def code_of(resp: Any) -> Optional[int]:
    if not isinstance(resp, dict):
        return None
    try:
        return int(resp.get("code"))
    except (TypeError, ValueError):
        return None


class DnaClient:
    def __init__(self, account: Account, dry_run: bool) -> None:
        self.account = account
        self.token = account.token
        self.device_code = account.device_code
        self.refresh_token = account.refresh_token
        self.dry_run = dry_run
        self.mode = resolve_sign_mode(account.device_code)
        self.timeout = http_timeout()
        self.pub_key: Optional[str] = None
        self.identity = f"账号{account.index}"
        self._session = None

    def _requests(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def fetch_rsa_public_key(self) -> Optional[str]:
        if self.dry_run:
            return None
        url = urllib.parse.urljoin(BASE_URL, "config/getRsaPublicKey")
        headers = base_headers(self.token, self.device_code, self.mode)
        try:
            resp = self._requests().post(url, headers=headers, timeout=self.timeout)
            data = resp.json()
        except Exception as exc:
            log(f"获取 RSA 公钥失败：{type(exc).__name__}", ICONS["warning"])
            return None
        if code_of(data) in (0, 200):
            key = (data.get("data") or {}).get("key") if isinstance(data.get("data"), dict) else None
            if isinstance(key, str) and key.strip():
                return key.strip()
        log("获取 RSA 公钥被拒绝或响应异常", ICONS["warning"])
        return None

    def ensure_key(self) -> str:
        if not self.pub_key:
            self.pub_key = self.fetch_rsa_public_key()
        if not self.pub_key:
            raise RuntimeError("缺少 RSA 公钥，无法签名")
        return self.pub_key

    def signed_post(self, path: str, data: dict, extra_params: Optional[dict] = None) -> dict:
        if self.dry_run:
            raise RuntimeError("断网预演禁止 HTTP 请求")
        pub_key = self.ensure_key()
        sig = build_signature(pub_key, data, self.token, self.mode)
        headers = base_headers(self.token, self.device_code, self.mode)
        headers["tn"] = sig["tn"]
        headers["sa"] = sig["sa"]
        body = urllib.parse.urlencode({k: str(v) for k, v in data.items()})
        if extra_params:
            parsed = urllib.parse.parse_qs(body)
            for k, v in extra_params.items():
                parsed[k] = [str(v)]
            body = urllib.parse.urlencode(parsed, doseq=True)
        url = urllib.parse.urljoin(BASE_URL, path)
        try:
            resp = self._requests().post(url, headers=headers, data=body, timeout=self.timeout)
            payload = resp.json()
            return payload if isinstance(payload, dict) else {"code": -1, "msg": "非对象响应"}
        except Exception as exc:
            return {"code": -1, "msg": type(exc).__name__}

    def refresh_access_token(self) -> bool:
        refresh = self.refresh_token or ""
        if not refresh:
            return False
        result = self.signed_post(
            "user/refreshToken",
            {"gameId": GAME_ID, "refreshToken": refresh, "source": "android"},
        )
        data = result.get("data") if isinstance(result.get("data"), dict) else None
        new_token = data.get("token") if data else None
        if code_of(result) == 200 and isinstance(new_token, str) and new_token.strip():
            remember_secret(new_token.strip())
            self.token = new_token.strip()
            log("access token 已用 refreshToken 自动续期", ICONS["success"])
            return True
        log("refreshToken 续期失败", ICONS["warning"])
        return False

    def fetch_identity(self) -> str:
        result = self.signed_post("user/mineV2", {"type": "1"})
        data = result.get("data") if isinstance(result.get("data"), dict) else None
        mine = data.get("mine") if isinstance(data, dict) else None
        if not isinstance(mine, dict):
            return self.identity
        nickname = clean_identity(mine.get("nickName") or mine.get("nickname") or mine.get("userName"))
        user_id = clean_identity(mine.get("userId") or mine.get("uid"))
        parts = [p for p in (nickname, f"uid:{user_id}" if user_id else "") if p]
        if parts:
            self.identity = " / ".join(parts)
        return self.identity


def local_fallback_texts() -> list[str]:
    raw = env("DNA_LOCAL_TEXT")
    items: list[str] = []
    if raw:
        for part in re.split(r"[\n,]+", raw):
            text = " ".join(part.split()).strip()
            if text and len(text) <= PUBLIC_TEXT_MAX:
                items.append(text)
    return items or list(LOCAL_FALLBACK_TEXTS)


def fetch_public_comment_text(dry_run: bool) -> tuple[str, str]:
    fallback = random.choice(local_fallback_texts())
    if dry_run:
        return fallback, "断网预演使用本地评论文案，未访问一言"
    try:
        request = urllib.request.Request(
            HITOKOTO_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Qinglong-DnaBbsDaily/1.0",
            },
            method="GET",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=HITOKOTO_TIMEOUT) as response:
            raw = response.read(HITOKOTO_MAX_BYTES + 1)
            status = getattr(response, "status", 200)
        if status != 200 or len(raw) > HITOKOTO_MAX_BYTES:
            raise RuntimeError("http-error")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("invalid-json")
        text = payload.get("hitokoto")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("missing-text")
        text = " ".join(text.split()).strip()
        author = payload.get("from_who")
        source = payload.get("from")
        author = " ".join(author.split()).strip() if isinstance(author, str) else ""
        source = " ".join(source.split()).strip() if isinstance(source, str) else ""
        if author and source:
            text = f"{text} —— {author}《{source}》"
        elif source:
            text = f"{text} ——《{source}》"
        elif author:
            text = f"{text} —— {author}"
        if len(text) > PUBLIC_TEXT_MAX:
            raise RuntimeError("overlong-text")
        return text, "使用一言文案并保留署名"
    except Exception:
        return fallback, "一言不可用，已回退本地文案"


def parse_task_map(task_data: dict) -> dict[str, dict[str, int]]:
    daily_tasks = (task_data.get("data") or {}).get("dailyTask") if isinstance(task_data.get("data"), dict) else None
    task_map: dict[str, dict[str, int]] = {}
    if not isinstance(daily_tasks, list):
        return task_map
    for item in daily_tasks:
        if not isinstance(item, dict):
            continue
        remark = str(item.get("remark") or "")
        if not remark:
            continue
        task_map[remark] = {
            "progress": int(item.get("process") or 0),
            "complete": int(item.get("completeTimes") or 0),
            "total": int(item.get("times") or 1),
        }
    return task_map


def is_task_done(task_map: dict[str, dict[str, int]], keyword: str) -> bool:
    for remark, info in task_map.items():
        if keyword in remark:
            return info["complete"] >= info["total"]
    return False


def remaining_count(task_map: dict[str, dict[str, int]], keyword: str) -> int:
    for remark, info in task_map.items():
        if keyword in remark:
            return max(0, info["total"] - info["complete"])
    return 0


def notification_enabled() -> bool:
    value = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    if value != "auto":
        log("QINGLONG_NOTIFY 值无效，按 auto 处理", ICONS["warning"])
    selectors_raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selectors_raw is None:
        return True
    selectors = [item.lower() for item in re.split(r"[,;\s]+", selectors_raw.strip()) if item]
    if not selectors:
        return False
    if "*" in selectors:
        return True
    return any(
        fnmatch.fnmatch(identity.lower(), selector)
        for selector in selectors
        for identity in NOTIFY_IDENTITIES
    )


def send_notify(title: str, content: str, dry_run: bool) -> str:
    if not notification_enabled():
        return f"{ICONS['skipped']} 已关闭"
    if dry_run:
        log(f"断网预演通知汇总：{content}", ICONS["skipped"])
        return f"{ICONS['skipped']} 断网预演：已生成通知汇总，未加载通知组件"
    sender = None
    try:
        from notify import send as sender  # type: ignore
    except Exception:
        roots = [env("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts"]
        for root in filter(None, roots):
            path = Path(root) / "notify.py"
            if path.is_file():
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                if spec and spec.loader:
                    try:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        candidate = getattr(module, "send", None)
                        if callable(candidate):
                            sender = candidate
                            break
                    except Exception:
                        continue
            js_path = Path(root) / "sendNotify.js"
            if js_path.is_file():
                try:
                    import subprocess

                    subprocess.run(
                        ["node", str(js_path), title, content],
                        check=False,
                        timeout=30,
                        capture_output=True,
                        text=True,
                    )
                    return f"{ICONS['success']} 已推送"
                except Exception:
                    return f"{ICONS['warning']} 推送失败"
    if not callable(sender):
        log("未找到青龙 notify.py，已跳过任务总结推送", ICONS["warning"])
        return f"{ICONS['warning']} 未找到通知组件"
    try:
        sender(title, content)
        return f"{ICONS['success']} 已推送"
    except Exception:
        log("通知发送失败", ICONS["warning"])
        return f"{ICONS['warning']} 推送失败"


def run_stage(number: int, name: str, fn) -> StageResult:
    started = time.monotonic()
    log(f"[阶段{number}] {name}：开始")
    try:
        status, detail = fn()
        if status not in ICONS:
            status = "failure"
        icon = ICONS.get(status, ICONS["failure"])
        log(f"[阶段{number}] {name}：{detail}", icon)
        return StageResult(name=name, status=status, detail=detail, elapsed=round(time.monotonic() - started, 3))
    except Exception as exc:
        detail = redact(str(exc)) or type(exc).__name__
        log(f"[阶段{number}] {name}：{detail}", ICONS["failure"])
        return StageResult(
            name=name,
            status="failure",
            detail=detail,
            elapsed=round(time.monotonic() - started, 3),
        )


def run_account_dry(account: Account) -> AccountResult:
    started = time.monotonic()
    stages: list[StageResult] = []
    identity = f"账号{account.index}"

    def stage_config() -> tuple[str, str]:
        if not account.token or not account.device_code:
            raise RuntimeError("账号凭据不完整")
        mode = resolve_sign_mode(account.device_code)
        return "success", f"模式={mode}，已配置设备码，refresh={'是' if account.refresh_token else '否'}"

    def stage_plan(name: str) -> tuple[str, str]:
        return "success", f"预演将执行{name}（不发起真实请求）"

    def stage_comment() -> tuple[str, str]:
        _, note = fetch_public_comment_text(True)
        return "success", note

    stages.append(run_stage(1, "校验配置", stage_config))
    stages.append(run_stage(2, "查询任务进度", lambda: stage_plan("任务进度查询")))
    stages.append(run_stage(3, "浏览帖子", lambda: stage_plan("浏览")))
    stages.append(run_stage(4, "点赞帖子", lambda: stage_plan("点赞")))
    stages.append(run_stage(5, "分享任务", lambda: stage_plan("分享")))
    stages.append(run_stage(6, "回复评论", stage_comment))
    stages.append(run_stage(7, "社区签到", lambda: stage_plan("签到")))
    log("DRY_RUN_OK", ICONS["success"])
    ok = all(item.status == "success" for item in stages)
    stats = summarize_stages(stages)
    return AccountResult(
        index=account.index,
        identity=identity,
        ok=ok,
        message="预演通过" if ok else "预演失败",
        stages=stages,
        elapsed=round(time.monotonic() - started, 3),
        stats=stats,
    )


def summarize_stages(stages: list[StageResult]) -> dict[str, int]:
    stats = {"total": len(stages), "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    for item in stages:
        if item.status == "success":
            stats["success"] += 1
        elif item.status == "alreadyComplete":
            stats["alreadyComplete"] += 1
        elif item.status == "skipped":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
    return stats


def run_account_live(account: Account) -> AccountResult:
    started = time.monotonic()
    client = DnaClient(account, dry_run=False)
    stages: list[StageResult] = []
    task_map: dict[str, dict[str, int]] = {}
    posts: list[dict] = []

    def stage_auth() -> tuple[str, str]:
        client.ensure_key()
        identity = client.fetch_identity()
        # 用签到状态探测鉴权
        status = client.signed_post("user/haveSignInNew", {"gameId": GAME_ID})
        auth = code_of(status)
        if auth in (220, 101):
            if client.refresh_access_token():
                status = client.signed_post("user/haveSignInNew", {"gameId": GAME_ID})
                auth = code_of(status)
                identity = client.fetch_identity()
        if auth in (220, 101, 10000):
            if auth == 220:
                raise RuntimeError("Token 已失效（220），请更新 DNA_ACCOUNTS 中的 token/refreshToken")
            if auth == 101:
                raise RuntimeError("身份验证失败（101），Token 可能已过期")
            raise RuntimeError("参数或签名错误（10000），请检查设备码与签名模式")
        if identity:
            log(f"账号身份 {identity}", ICONS["success"])
        return "success", f"鉴权通过 · {identity}"

    def stage_progress() -> tuple[str, str]:
        nonlocal task_map
        result = client.signed_post("encourage/level/getTaskProcess", {"gameId": GAME_ID})
        if code_of(result) != 200:
            raise RuntimeError(f"获取任务进度失败：{redact(result.get('msg'))}")
        task_map = parse_task_map(result)
        if not task_map:
            raise RuntimeError("未找到每日任务数据")
        summary = ", ".join(f"{k}={v['complete']}/{v['total']}" for k, v in task_map.items())
        return "success", redact(summary)

    def stage_browse() -> tuple[str, str]:
        nonlocal posts
        posts = []
        list_resp = client.signed_post(
            "forum/recommend/list",
            {
                "gameId": GAME_ID,
                "recIndex": 0,
                "newIndex": 0,
                "size": 20,
                "history": "",
            },
        )
        data = list_resp.get("data") if isinstance(list_resp.get("data"), dict) else {}
        posts = data.get("postVoList") if isinstance(data, dict) else []
        if not isinstance(posts, list):
            posts = []
        if is_task_done(task_map, "浏览"):
            return "alreadyComplete", "浏览任务：今日已完成"
        remaining = remaining_count(task_map, "浏览")
        client.signed_post("encourage/level/viewCommunity", {"gameId": GAME_ID})
        success_count = 0
        for post in posts:
            if success_count >= remaining:
                break
            if not isinstance(post, dict):
                continue
            post_id = post.get("postId", "")
            result = client.signed_post("forum/viewCount", {"gameId": GAME_ID, "postId": post_id})
            if code_of(result) == 200:
                success_count += 1
        if success_count > 0:
            return "success", f"浏览任务：完成 {success_count} 次浏览"
        if remaining == 0:
            return "alreadyComplete", "浏览任务：无需额外浏览"
        raise RuntimeError("浏览任务失败")

    def stage_like() -> tuple[str, str]:
        if is_task_done(task_map, "点赞"):
            return "alreadyComplete", "点赞任务：今日已完成"
        if not posts:
            raise RuntimeError("无法获取推荐帖子，跳过点赞")
        remaining = remaining_count(task_map, "点赞")
        unliked = [p for p in posts if isinstance(p, dict) and p.get("isLike") == 0]
        like_count = 0
        for post in unliked:
            if like_count >= remaining:
                break
            result = client.signed_post(
                "forum/like",
                {
                    "forumId": post.get("gameForumId", ""),
                    "gameId": GAME_ID,
                    "likeType": "1",
                    "operateType": "1",
                    "postCommentId": "",
                    "postCommentReplyId": "",
                    "postId": post.get("postId", ""),
                    "postType": str(post.get("postType", "1")),
                    "toUserId": post.get("userId", ""),
                },
            )
            if code_of(result) == 200:
                like_count += 1
        if like_count > 0:
            return "success", f"点赞任务：完成 {like_count} 次点赞"
        raise RuntimeError("点赞任务失败")

    def stage_share() -> tuple[str, str]:
        if is_task_done(task_map, "分享"):
            return "alreadyComplete", "分享任务：今日已完成"
        result = client.signed_post("encourage/level/shareTask", {"gameId": GAME_ID})
        if code_of(result) == 200:
            return "success", "分享任务：完成 1 次分享"
        raise RuntimeError(f"分享任务失败：{redact(result.get('msg'))}")

    def stage_reply() -> tuple[str, str]:
        if is_task_done(task_map, "回复"):
            return "alreadyComplete", "回复任务：今日已完成"
        if not posts:
            raise RuntimeError("无法获取推荐帖子，跳过回复")

        def server_reply_progress() -> tuple[int, int]:
            verify = client.signed_post("encourage/level/getTaskProcess", {"gameId": GAME_ID})
            for item in ((verify.get("data") or {}).get("dailyTask") or []):
                if isinstance(item, dict) and "回复" in str(item.get("remark") or ""):
                    return int(item.get("completeTimes") or 0), int(item.get("times") or 5)
            return 0, 5

        server_count, reply_total = server_reply_progress()
        replied: set[str] = set()
        local_ok = 0
        for round_num in range(1, 6):
            if server_count >= reply_total:
                break
            candidate_posts = posts
            if round_num > 1:
                list_resp = client.signed_post(
                    "forum/recommend/list",
                    {
                        "gameId": GAME_ID,
                        "recIndex": 0,
                        "newIndex": 0,
                        "size": 20,
                        "history": "",
                    },
                )
                data = list_resp.get("data") if isinstance(list_resp.get("data"), dict) else {}
                candidate_posts = data.get("postVoList") if isinstance(data, dict) else []
                if not isinstance(candidate_posts, list):
                    candidate_posts = []
            new_attempts = 0
            for post in candidate_posts:
                if server_count >= reply_total:
                    break
                if not isinstance(post, dict):
                    continue
                post_id = str(post.get("postId") or "")
                if not post_id or post_id in replied:
                    continue
                new_attempts += 1
                content, note = fetch_public_comment_text(False)
                if round_num == 1 and local_ok == 0:
                    log(f"评论文案来源：{note}", ICONS["skipped"])
                content_json = json.dumps(
                    [{"content": content, "contentType": "1"}],
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                result = client.signed_post(
                    "forum/comment/createComment",
                    {
                        "postId": post_id,
                        "forumId": post.get("gameForumId", ""),
                        "postType": "1",
                        "content": content_json,
                    },
                    extra_params={"toUserId": post.get("userId", "")},
                )
                replied.add(post_id)
                code = code_of(result)
                if code == 200:
                    local_ok += 1
                elif code == 302:
                    log("回复触发频率限制，等待 30 秒", ICONS["warning"])
                    time.sleep(30)
                server_count, _ = server_reply_progress()
            if server_count < reply_total and new_attempts == 0:
                break
        if server_count >= reply_total:
            return "success", f"回复任务：完成（服务器确认 {server_count}/{reply_total}）"
        if server_count > 0:
            return "warning", f"回复任务：部分完成（服务器 {server_count}/{reply_total}）"
        raise RuntimeError("回复任务失败")

    def stage_signin() -> tuple[str, str]:
        if is_task_done(task_map, "签到"):
            return "alreadyComplete", "签到任务：今日已完成"
        result = client.signed_post("user/signIn", {"gameId": GAME_ID})
        if code_of(result) in (0, 200):
            return "success", "签到任务：完成"
        raise RuntimeError(f"签到任务失败：{redact(result.get('msg'))}")

    stages.append(run_stage(1, "鉴权与身份", stage_auth))
    if stages[-1].status == "failure":
        stats = summarize_stages(stages)
        return AccountResult(
            index=account.index,
            identity=client.identity,
            ok=False,
            message=stages[-1].detail,
            stages=stages,
            elapsed=round(time.monotonic() - started, 3),
            stats=stats,
        )
    stages.append(run_stage(2, "查询任务进度", stage_progress))
    stages.append(run_stage(3, "浏览帖子", stage_browse))
    stages.append(run_stage(4, "点赞帖子", stage_like))
    stages.append(run_stage(5, "分享任务", stage_share))
    stages.append(run_stage(6, "回复评论", stage_reply))
    stages.append(run_stage(7, "社区签到", stage_signin))

    stats = summarize_stages(stages)
    # warning 计为部分失败；alreadyComplete/success 均算完成
    hard_fail = stats["failed"] > 0
    soft_fail = any(item.status == "warning" for item in stages)
    ok = not hard_fail and not soft_fail
    if hard_fail:
        message = "存在失败阶段"
    elif soft_fail:
        message = "部分任务未完全达成"
    else:
        message = "全部阶段完成"
    return AccountResult(
        index=account.index,
        identity=client.identity,
        ok=ok,
        message=message,
        stages=stages,
        elapsed=round(time.monotonic() - started, 3),
        stats=stats,
    )


def print_banner(mode: str, total: int) -> None:
    print(TASK_NAME, flush=True)
    print("═" * 62, flush=True)
    print(f"开始时间  {now_text()}", flush=True)
    print(f"运行模式  {mode}", flush=True)
    print(f"账号数量  {total}", flush=True)
    print("═" * 62, flush=True)


def print_account_stats(result: AccountResult) -> None:
    s = result.stats or summarize_stages(result.stages)
    log(
        f"账号统计 {result.identity}：总任务 {s.get('total', 0)}，成功 {s.get('success', 0)}，"
        f"已完成 {s.get('alreadyComplete', 0)}，跳过 {s.get('skipped', 0)}，"
        f"失败 {s.get('failed', 0)}，耗时 {result.elapsed}s"
    )


def build_notify_body(results: list[AccountResult], final_status: str) -> str:
    success = sum(1 for item in results if item.ok)
    failed = len(results) - success
    lines = [
        f"状态：{final_status}",
        f"账号总数：{len(results)}",
        f"成功：{success}",
        f"失败：{failed}",
    ]
    for item in results:
        icon = ICONS["success"] if item.ok else ICONS["failure"]
        lines.append(f"{icon} {item.identity}：{item.message}")
    return "\n".join(lines)


def emit_task_summary(payload: dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> int:
    dry_run = False
    config_error = False
    results: list[AccountResult] = []
    notify_status = f"{ICONS['skipped']} 未发送"
    exit_code = 0
    try:
        dry_run = dry_run_enabled()
        accounts = parse_accounts()
        mode = "dry-run" if dry_run else "live"
        print_banner(mode, len(accounts))
        for account in accounts:
            log(f"开始处理账号 {account.index}")
            if dry_run:
                result = run_account_dry(account)
            else:
                result = run_account_live(account)
            results.append(result)
            print_account_stats(result)
            icon = ICONS["success"] if result.ok else ICONS["failure"]
            log(f"账号结果 {result.identity}：{result.message}", icon)
        success = sum(1 for item in results if item.ok)
        failed = len(results) - success
        if failed == 0:
            final_status = "dry_run" if dry_run else "success"
            final_label = "预演通过" if dry_run else "全部成功"
            exit_code = 0
        else:
            final_status = "partial_failure" if success else "failure"
            final_label = "部分失败" if success else "全部失败"
            exit_code = 1
        print("─" * 62, flush=True)
        log(f"任务统计：账号成功 {success}/{len(results)}，失败 {failed}")
        log(f"完成时间  {now_text()}")
        log(f"最终状态  {final_label}", ICONS["success"] if exit_code == 0 else ICONS["failure"])
        notify_body = build_notify_body(results, final_label)
        notify_status = send_notify(TASK_NAME, notify_body, dry_run)
        log(f"通知状态：{notify_status}")
        emit_task_summary(
            {
                "catalogId": CATALOG_ID,
                "task": TASK_NAME,
                "status": final_status,
                "dryRun": dry_run,
                "accounts": len(results),
                "success": success,
                "failed": failed,
                "notify": notify_status,
                "finishedAt": now_text(),
            }
        )
        if dry_run and exit_code == 0:
            print("预演通过", flush=True)
        return exit_code
    except ValueError as exc:
        config_error = True
        message = redact(str(exc))
        log(message, ICONS["failure"])
        notify_status = send_notify(TASK_NAME, f"配置错误：{message}", dry_run)
        emit_task_summary(
            {
                "catalogId": CATALOG_ID,
                "task": TASK_NAME,
                "status": "configuration_error",
                "dryRun": dry_run,
                "accounts": 0,
                "success": 0,
                "failed": 0,
                "notify": notify_status,
                "finishedAt": now_text(),
                "error": message,
            }
        )
        return 2
    except Exception as exc:
        message = redact(str(exc)) or type(exc).__name__
        log(message, ICONS["failure"])
        notify_status = send_notify(TASK_NAME, f"任务异常：{message}", dry_run)
        emit_task_summary(
            {
                "catalogId": CATALOG_ID,
                "task": TASK_NAME,
                "status": "failure",
                "dryRun": dry_run,
                "accounts": len(results),
                "success": sum(1 for item in results if item.ok),
                "failed": max(1, len(results) - sum(1 for item in results if item.ok)),
                "notify": notify_status,
                "finishedAt": now_text(),
                "error": message,
            }
        )
        return 1 if not config_error else 2


if __name__ == "__main__":
    sys.exit(main())
