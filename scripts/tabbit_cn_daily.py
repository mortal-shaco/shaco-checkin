#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Tabbit 国内版每日签到
# cron: 18 9 * * *
# SPDX-License-Identifier: MIT
# Based on L0NE-6/Tabbit-Daily, tabbit_cn_daily.py (MIT).
# Copyright (c) L0NE-6 and contributors.
#
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Tabbit 国内版每日签到 - 青龙单文件维护脚本。

区域固定为 https://web.tabbit.com 。只读取 TABBIT_CN_ACCOUNTS，不会回退到国际版
账号变量。登录态是约 7 天有效的 JWT，上游没有 refresh 接口。

账号：每个非空行一个账号；不以 &、@ 或 && 分隔账号。
推荐格式：
  1) 整行 Cookie（须含 token=...，建议含 user_id=...）
  2) 备注|Cookie或JWT整段（只在第一个 | 处分割，后续凭据原文保留）
  3) 备注|token|uid 或 备注|token|uid|client_version
  4) 单行 JSON 对象，或整体 JSON 数组 / {"accounts":[...]}

可选：TABBIT_UNLOCK_PRO（默认关闭，避免默认伪装 Pro/默认浏览器指纹）、
TABBIT_CLIENT_VERSION、TABBIT_CN_DRY_RUN=1 完全断网预演。
命令：python candidate.py [--query] [--only N] [--no-notify]
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
        _ql_notify_identities = ('138727873cd50b7e', 'scripts/tabbit_cn_daily.py', 'tabbit_cn_daily.py', 'tabbit_cn_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import base64
import fnmatch
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlencode

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


SCRIPT_VERSION = "1.1.0"
CATALOG_ID = "138727873cd50b7e"
TITLE = "Tabbit 国内版每日签到"
REALM = "cn"
REALM_LABEL = "国内版"
BASE_URL = "https://web.tabbit.com"
ACCOUNT_ENV = "TABBIT_CN_ACCOUNTS"
DRY_RUN_ENV = "TABBIT_CN_DRY_RUN"
TIME_ZONE = "Asia/Shanghai"

SIGN_KEY_PATH = "/chat/sign-key"
STATUS_PATH = (
    "/api/commerce/activity/v1/sign-in/status"
    "?scene_codes=daily_sign_in&scene_codes=desktop_pet"
)
SIGN_IN_PATH = "/api/commerce/activity/v1/sign-in"
USAGE_PATH = "/api/commerce/quota/v1/usage"

DEFAULT_CLIENT_VERSION = "1.17.16(10117016)"
DEFAULT_CLIENT_ID = "2dd8eb4c1ed9c344d173"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
SEC_CH_UA = '"Tabbit Browser";v="149", "Chromium";v="149", "Not)A;Brand";v="24"'
WANTED_COOKIE_NAMES = ("token", "user_id", "managed", "NEXT_LOCALE", "SAPISID")
REQUEST_TIMEOUT = 20
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

TRUE_TEXT = {"1", "true", "yes", "on", "开启", "是"}
FALSE_TEXT = {"0", "false", "no", "off", "关闭", "否"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class TabbitError(RuntimeError):
    """Base error for a single account operation."""


class ConfigError(TabbitError):
    """Account configuration is missing or malformed."""


class CredentialError(TabbitError):
    """Cookie/JWT credentials are incomplete."""


class AuthError(TabbitError):
    """The site rejected the account login state."""


class ContractError(TabbitError):
    """The response does not match the observed sign-in contract."""


class ApiError(TabbitError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Account:
    index: int
    name: str
    token: str
    uid: str
    cookie: str
    unlock_pro: bool
    client_version: str


def dry_run_enabled() -> bool:
    return parse_bool(env_value(DRY_RUN_ENV), False)


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[%s] %s" % (stamp(), message), flush=True)


def elapsed(start: float) -> str:
    return "%.2f秒" % (time.monotonic() - start)


def env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_TEXT:
            return True
        if text in FALSE_TEXT:
            return False
    return default


def compact_text(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:limit]


def strip_bearer(value: str) -> str:
    text = str(value or "").strip()
    return text[7:].strip() if text.lower().startswith("bearer ") else text


def mask_secret(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return text[:2] + "***"
    return text[:4] + "***" + text[-2:]


def display_name(account: Account) -> str:
    name = compact_text(account.name or "", 40)
    if name:
        return name
    return "账号%d" % account.index


def sanitize_message(text: str, account: Optional[Account] = None) -> str:
    value = compact_text(str(text or ""), 300)
    secrets: List[str] = []
    if account:
        secrets.extend([account.token, account.cookie])
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        value = value.replace(secret, "<redacted>")
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", value)
    value = re.sub(r"(?i)(token|authorization)=([^;\s]+)", r"\1=<redacted>", value)
    return value


def decode_jwt_claims(token: str) -> Dict[str, Any]:
    try:
        pieces = token.split(".")
        if len(pieces) < 2:
            return {}
        payload = pieces[1] + "=" * (-len(pieces[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


def jwt_user_id(token: str) -> str:
    claims = decode_jwt_claims(token)
    for key in ("user_id", "uid", "sub", "userId"):
        value = claims.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    data = claims.get("data")
    if isinstance(data, dict):
        for key in ("user_id", "uid", "sub", "userId"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def extract_cookie(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lower = text.lower()
    marker = lower.find("cookie:")
    if marker >= 0:
        rest = text[marker + len("cookie:") :].strip()
        end = len(rest)
        for char in ('"', "'", "\r", "\n"):
            found = rest.find(char)
            if found >= 0:
                end = min(end, found)
        candidate = rest[:end].strip()
        if "=" in candidate:
            return candidate
    marker = lower.find(" -b ")
    if marker >= 0:
        rest = text[marker + 4 :].strip()
        if rest:
            quote = rest[0] if rest[0] in ("'", '"') else ""
            if quote:
                candidate = rest[1:].split(quote, 1)[0].strip()
            else:
                candidate = rest.split(None, 1)[0].strip()
            if "=" in candidate:
                return candidate
    return text


def cookie_map(cookie: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in extract_cookie(cookie).split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name and value:
            result[name] = value
    return result


def build_cookie(token: str, uid: str, raw_cookie: str = "") -> str:
    values = cookie_map(raw_cookie)
    values["token"] = token
    if uid:
        values.setdefault("user_id", uid)
        values.setdefault("SAPISID", uid)
    values.setdefault("managed", "tab_browser")
    values.setdefault("NEXT_LOCALE", "zh")
    return "; ".join(
        "%s=%s" % (name, values[name])
        for name in WANTED_COOKIE_NAMES
        if values.get(name)
    )


def account_from_payload(
    payload: Mapping[str, Any],
    index: int,
    default_unlock_pro: bool,
    default_client_version: str,
) -> Account:
    raw_cookie = payload.get("cookie") or ""
    raw_token = (
        payload.get("token")
        or payload.get("accessToken")
        or payload.get("access_token")
        or ""
    )
    uid = payload.get("uid") or payload.get("user_id") or payload.get("userId") or ""
    token = strip_bearer(str(raw_token or ""))
    cookie = extract_cookie(str(raw_cookie or ""))
    parsed_cookie = cookie_map(cookie)
    cookie_token = parsed_cookie.get("token", "").strip()
    if token and cookie_token and token != cookie_token:
        raise CredentialError("显式 token 与 Cookie 中的 token 不一致")
    if cookie_token:
        token = cookie_token
    if not token and cookie and "=" not in cookie:
        token = strip_bearer(cookie)
    if not token:
        raise CredentialError("缺少 Cookie 或 JWT（Cookie 中应有 token=...）")
    token = strip_bearer(token)
    if len(token) > 32768 or "\r" in token or "\n" in token:
        raise CredentialError("JWT 格式无效")
    explicit_uid = str(uid or "").strip()
    cookie_uid = parsed_cookie.get("user_id", "").strip()
    token_uid = jwt_user_id(token)
    uid_candidates = {
        value for value in (explicit_uid, cookie_uid, token_uid) if value
    }
    if len(uid_candidates) > 1:
        raise CredentialError("账号配置中的 user_id 与 JWT/Cookie 不一致")
    uid = next(iter(uid_candidates), "")
    if not uid:
        raise CredentialError("缺少 user_id，且 JWT 中没有可识别的用户标识")
    unlock_pro = parse_bool(
        payload.get("unlock_pro", payload.get("unlockPro")),
        default_unlock_pro,
    )
    client_version = str(
        payload.get("client_version")
        or payload.get("clientVersion")
        or default_client_version
    ).strip()
    if not client_version:
        client_version = DEFAULT_CLIENT_VERSION
    if len(client_version) > 80 or "\r" in client_version or "\n" in client_version:
        raise ConfigError("client_version 格式无效")
    cookie = build_cookie(token, uid, cookie)
    if len(cookie) > 32768 or "\r" in cookie or "\n" in cookie:
        raise CredentialError("Cookie 格式无效")
    name = compact_text(str(payload.get("name") or payload.get("note") or ""), 100)
    return Account(
        index, name or "账号%d" % index, token, uid, cookie, unlock_pro, client_version
    )


def account_from_text(
    raw: str,
    index: int,
    default_unlock_pro: bool,
    default_client_version: str,
) -> Account:
    text = str(raw or "").strip()
    if not text:
        raise CredentialError("账号内容为空")
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise ConfigError("JSON 账号格式错误: %s" % error) from error
        if not isinstance(value, dict):
            raise ConfigError("JSON 账号必须是对象")
        return account_from_payload(
            value, index, default_unlock_pro, default_client_version
        )
    # 只在第一个 | 处分割备注与凭据；凭据内可再按契约解析 token|uid。
    if "|" in text:
        name, rest = text.split("|", 1)
        name = name.strip()
        rest = rest.strip()
        if not rest:
            raise ConfigError("账号行在 | 后缺少凭据")
        if rest.startswith("{"):
            try:
                value = json.loads(rest)
            except json.JSONDecodeError as error:
                raise ConfigError("JSON 账号格式错误: %s" % error) from error
            if not isinstance(value, dict):
                raise ConfigError("JSON 账号必须是对象")
            if name and not value.get("name") and not value.get("note"):
                value = dict(value)
                value["name"] = name
            return account_from_payload(
                value, index, default_unlock_pro, default_client_version
            )
        if "=" in rest:
            return account_from_payload(
                {"name": name, "cookie": rest},
                index,
                default_unlock_pro,
                default_client_version,
            )
        if "|" in rest:
            parts = [item.strip() for item in rest.split("|")]
            if len(parts) == 2:
                token, uid = parts
                return account_from_payload(
                    {"name": name, "token": token, "uid": uid},
                    index,
                    default_unlock_pro,
                    default_client_version,
                )
            if len(parts) == 3:
                token, uid, client_version = parts
                return account_from_payload(
                    {
                        "name": name,
                        "token": token,
                        "uid": uid,
                        "client_version": client_version,
                    },
                    index,
                    default_unlock_pro,
                    default_client_version,
                )
            raise ConfigError(
                "账号行应使用 备注|Cookie、备注|token|uid 或 备注|token|uid|client_version"
            )
        return account_from_payload(
            {"name": name, "token": rest},
            index,
            default_unlock_pro,
            default_client_version,
        )
    payload = {"cookie": text} if "=" in text else {"token": text}
    return account_from_payload(
        payload, index, default_unlock_pro, default_client_version
    )


def load_accounts(
    raw: Optional[str] = None,
    default_unlock_pro: Optional[bool] = None,
    default_client_version: Optional[str] = None,
) -> List[Account]:
    source = env_value(ACCOUNT_ENV) if raw is None else str(raw)
    if not source.strip():
        raise ConfigError("未配置 %s" % ACCOUNT_ENV)
    # 默认关闭 unlock_pro，避免默认伪装 Pro/默认浏览器指纹。
    if default_unlock_pro is None:
        default_unlock_pro = parse_bool(env_value("TABBIT_UNLOCK_PRO", "0"), False)
    if default_client_version is None:
        default_client_version = env_value(
            "TABBIT_CLIENT_VERSION", DEFAULT_CLIENT_VERSION
        ) or DEFAULT_CLIENT_VERSION
    items: List[Any]
    text = source.strip()
    if text.startswith("[") or text.startswith("{"):
        try:
            value = json.loads(text)
            if isinstance(value, list):
                items = value
            elif isinstance(value, dict) and isinstance(value.get("accounts"), list):
                items = value["accounts"]
            elif isinstance(value, dict):
                items = [value]
            else:
                raise ConfigError("账号 JSON 必须是对象或数组")
        except json.JSONDecodeError:
            items = [
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
    else:
        items = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    accounts: List[Account] = []
    errors: List[str] = []
    for index, item in enumerate(items, 1):
        try:
            if isinstance(item, dict):
                account = account_from_payload(
                    item, index, default_unlock_pro, default_client_version
                )
            else:
                account = account_from_text(
                    str(item), index, default_unlock_pro, default_client_version
                )
            accounts.append(account)
        except TabbitError as error:
            errors.append("第 %d 条: %s" % (index, error))
    if errors:
        raise ConfigError("账号配置有误: %s" % "; ".join(errors[:3]))
    if not accounts:
        raise ConfigError("没有可用账号")
    return accounts


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signature_headers(
    sign_key: str,
    body: bytes,
    now_ms: Optional[int] = None,
    request_uuid: Optional[str] = None,
) -> Dict[str, str]:
    timestamp = str(int(time.time() * 1000) if now_ms is None else int(now_ms))
    nonce_uuid = request_uuid or str(uuid.uuid4())
    message = "%s.%s.%s" % (timestamp, nonce_uuid, sha256_hex(body))
    nonce = hmac.new(
        sign_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "x-timestamp": timestamp,
        "x-signature": nonce_uuid,
        "x-nonce": nonce,
    }


def unique_uuid(
    default_browser: bool,
    now_ms: Optional[int] = None,
    random_value: Optional[bytes] = None,
) -> str:
    raw = random_value if random_value is not None else os.urandom(32)
    if len(raw) != 32:
        raise ValueError("random_value must contain 32 bytes")
    seconds = max(0, int(time.time() * 1000) if now_ms is None else int(now_ms)) // 1000
    timestamp = format(seconds, "08x")[-8:]
    positions = (2, 7, 11, 14, 18, 21, 25, 28)
    digits = "0123456789abcdef"
    non_one = "023456789abcdef"
    chars: List[str] = []
    for index in range(32):
        if index in positions:
            chars.append(timestamp[positions.index(index)])
        elif index == 5:
            chars.append("1" if default_browser else non_one[raw[index] % len(non_one)])
        else:
            chars.append(digits[raw[index] % len(digits)])
    text = "".join(chars)
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


def device_id(uid: str) -> str:
    digest = bytearray(
        hashlib.sha256(("tabbit-device:%s" % uid).encode("utf-8")).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    text = digest.hex()
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


def chrome_consistency(uid: str) -> str:
    return (
        "version=1,client_id=%s,device_id=%s,sync_account_id=%s,"
        "signin_mode=all_accounts,signout_mode=show_confirmation"
        % (DEFAULT_CLIENT_ID, device_id(uid), uid)
    )


def base_headers(account: Account, referer_path: str) -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
        "x-chrome-id-consistency-request": chrome_consistency(account.uid),
        "referer": BASE_URL + referer_path,
        "Origin": BASE_URL,
        "x-req-ctx": base64.b64encode(account.client_version.encode("utf-8")).decode(
            "ascii"
        ),
        "unique-uuid": unique_uuid(account.unlock_pro),
    }


def make_sign_in_body(
    usage_percentage: str, request_no: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "request_no": request_no or str(uuid.uuid4()),
        "scene_codes": ["daily_sign_in"],
        "usage_percentage": usage_percentage,
    }


def json_body_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def format_usage_percentage(value: Any) -> str:
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError, OverflowError):
        number = 0.0
    return "%.2f%%" % max(0.0, min(100.0, number))


def find_daily_entry(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("响应不是 JSON 对象")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ContractError("响应缺少 results 数组")
    for entry in results:
        if isinstance(entry, dict) and entry.get("scene_code") == "daily_sign_in":
            return entry
    raise ContractError("响应缺少 daily_sign_in 场景")


def interpret_status(payload: Any) -> Dict[str, Any]:
    entry = find_daily_entry(payload)
    activity_open = parse_bool(entry.get("activity_open"), True)
    signed_today = parse_bool(entry.get("signed_today"), False)
    if not activity_open:
        state = "activity_closed"
        message = "今日签到活动未开启"
    elif signed_today:
        state = "already_signed"
        message = "今日已签到"
    else:
        state = "ready"
        message = "今日尚未签到"
    return {
        "state": state,
        "activity_open": activity_open,
        "signed_today": signed_today,
        "message": message,
        "entry": entry,
    }


def interpret_sign_in(payload: Any) -> Dict[str, Any]:
    entry = find_daily_entry(payload)
    result = str(entry.get("sign_in_result") or "").strip()
    reward = compact_text(str(entry.get("usage_reward_result") or ""), 120)
    if reward.lower() == "skipped":
        reward = ""
    if result == "success":
        return {
            "outcome": "success",
            "ok": True,
            "neutral": False,
            "succeeded": True,
            "reward": reward,
            "message": "签到成功",
        }
    if result == "already_signed":
        return {
            "outcome": "already_signed",
            "ok": True,
            "neutral": True,
            "succeeded": False,
            "reward": "",
            "message": "今日已签到",
        }
    if not result:
        return {
            "outcome": "unknown",
            "ok": False,
            "neutral": False,
            "succeeded": False,
            "reward": "",
            "message": "上游没有给出明确的签到结论",
        }
    return {
        "outcome": "failed",
        "ok": False,
        "neutral": False,
        "succeeded": False,
        "reward": "",
        "message": "签到未成功: %s" % compact_text(result, 120),
    }


def extract_usage_percentage(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ContractError("额度响应不是 JSON 对象")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload
    value = data.get("usage_percentage")
    if value is None:
        value = data.get("usage")
    if value is None:
        raise ContractError("额度响应缺少 usage_percentage")
    return format_usage_percentage(value)


@dataclass
class HttpResponse:
    status_code: int
    content: bytes

    def json(self) -> Dict[str, Any]:
        try:
            payload = json.loads(self.content.decode("utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


class NoRedirect(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError(code, "拒绝跟随 HTTP 重定向")


def http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> HttpResponse:
    if dry_run_enabled():
        raise ApiError(0, "无网络预演禁止 HTTP 请求")
    if not str(url).lower().startswith("https://"):
        raise ApiError(0, "请求必须使用 HTTPS")
    req = urlrequest.Request(
        url,
        data=body,
        headers=dict(headers or {}),
        method=method.upper(),
    )
    opener = urlrequest.build_opener(NoRedirect(), urlrequest.ProxyHandler())
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = int(getattr(response, "status", 200) or 200)
    except urlerror.HTTPError as error:
        raw = error.read(MAX_RESPONSE_BYTES + 1) if hasattr(error, "read") else b""
        status = int(error.code)
    except ApiError:
        raise
    except (urlerror.URLError, TimeoutError, OSError) as error:
        raise ApiError(0, "网络请求失败：%s" % error.__class__.__name__) from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ContractError("响应超过 4 MiB 上限")
    return HttpResponse(status, raw)


def error_text(payload: Mapping[str, Any]) -> str:
    for key in ("message", "msg", "detail", "error_message", "displayTips", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact_text(value)
        if isinstance(value, dict):
            nested = value.get("message")
            if isinstance(nested, str) and nested.strip():
                return compact_text(nested)
    return ""


def raise_for_status(status: int, payload: Mapping[str, Any], account: Account) -> None:
    if 200 <= status < 300:
        return
    upstream = error_text(payload)
    if status in (401, 403):
        detail = upstream or "登录状态失效，可能使用了另一地区的令牌"
        raise AuthError(sanitize_message(detail, account))
    if status == 409:
        raise ApiError(status, "上游会话冲突，请稍后重试")
    if status == 429:
        raise ApiError(status, "请求过于频繁，请稍后重试")
    if status == 492:
        raise ApiError(status, "账号额度或会员权限不足")
    if status >= 500:
        raise ApiError(status, "上游服务异常（HTTP %d）" % status)
    raise ApiError(status, upstream or "请求失败（HTTP %d）" % status)


class TabbitClient:
    def __init__(
        self,
        account: Account,
        session: Optional[Any] = None,
        timeout: int = REQUEST_TIMEOUT,
    ):
        self.account = account
        self.timeout = timeout
        # session 仅保留给测试替身注入；正式路径使用标准库 HTTPS。
        self.session = session
        self._sign_key = ""

    def close(self) -> None:
        close = getattr(self.session, "close", None) if self.session is not None else None
        if callable(close):
            close()

    def _transport(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Optional[bytes] = None,
    ) -> HttpResponse:
        if self.session is not None:
            if dry_run_enabled():
                raise ApiError(0, "无网络预演禁止 HTTP 请求")
            kwargs: Dict[str, Any] = {
                "headers": dict(headers),
                "timeout": self.timeout,
                "allow_redirects": False,
            }
            if body is not None:
                kwargs["data"] = body
            response = self.session.request(method.upper(), url, **kwargs)
            content = getattr(response, "content", None)
            if not isinstance(content, bytes):
                text = getattr(response, "text", "")
                content = text.encode("utf-8") if isinstance(text, str) else b""
            if len(content) > MAX_RESPONSE_BYTES:
                raise ContractError("响应超过 4 MiB 上限")
            return HttpResponse(int(response.status_code), content)
        return http_request(
            method, url, headers=headers, body=body, timeout=self.timeout
        )

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Mapping[str, Any]] = None,
        referer_path: str = "/member/usage",
        headers: Optional[Mapping[str, str]] = None,
        signed: bool = True,
    ) -> Tuple[int, Any]:
        request_headers = dict(headers or {})
        if signed:
            request_headers.update(base_headers(self.account, referer_path))
            request_headers["trace-id"] = str(uuid.uuid4())
            request_headers["Cookie"] = self.account.cookie
            request_headers["Authorization"] = "Bearer " + self.account.token
            body_bytes = b"" if body is None else json_body_bytes(body)
            request_headers.update(signature_headers(self.sign_key(), body_bytes))
        else:
            body_bytes = b"" if body is None else json_body_bytes(body)
        request_headers.setdefault("Accept", "application/json")
        if method.upper() == "POST":
            request_headers.setdefault("Content-Type", "application/json")
        response = self._transport(
            method,
            BASE_URL + path,
            request_headers,
            body_bytes if body is not None else None,
        )
        payload = response.json()
        raise_for_status(int(response.status_code), payload, self.account)
        return int(response.status_code), payload

    def sign_key(self, refresh: bool = False) -> str:
        if self._sign_key and not refresh:
            return self._sign_key
        headers = base_headers(self.account, "/")
        headers.update(
            {
                "Accept": "text/plain",
                "Cookie": self.account.cookie,
            }
        )
        response = self._transport("GET", BASE_URL + SIGN_KEY_PATH, headers)
        status = int(response.status_code)
        text = response.content.decode("utf-8", errors="replace").strip()
        if status in (401, 403):
            raise AuthError("登录状态失效，可能使用了另一地区的令牌")
        if status != 200:
            raise ApiError(status, "签名 key 获取失败（HTTP %d）" % status)
        if (
            not text
            or len(text) > 512
            or any(char in text for char in '<> \n\r{}"')
        ):
            raise ContractError("签名 key 格式无效")
        self._sign_key = text
        return text

    def query_status(self) -> Dict[str, Any]:
        _, payload = self._request("GET", STATUS_PATH, referer_path="/member/usage")
        return payload

    def query_usage_percentage(self) -> str:
        query = urlencode({"user_id": self.account.uid, "timezone": TIME_ZONE})
        _, payload = self._request(
            "GET", USAGE_PATH + "?" + query, referer_path="/"
        )
        return extract_usage_percentage(payload)

    def claim(self, usage_percentage: str) -> Dict[str, Any]:
        body = make_sign_in_body(usage_percentage)
        _, payload = self._request(
            "POST", SIGN_IN_PATH, body=body, referer_path="/member/usage"
        )
        return payload


def empty_stats() -> Dict[str, int]:
    return {
        "total": 0,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }


def process_account(
    account: Account,
    query_only: bool = False,
    stage_logger: Optional[Any] = None,
) -> Dict[str, Any]:
    stats = empty_stats()
    label = display_name(account)
    base_result: Dict[str, Any] = {
        "index": account.index,
        "name": label,
        "identity": label,
        "ok": False,
        "outcome": "failed",
        "neutral": False,
        "succeeded": False,
        "reward": "",
        "message": "",
        "stats": stats,
    }

    def stage(number: int, name: str, result: str, detail: str = "") -> None:
        if stage_logger:
            stage_logger(number, name, result, detail)

    if dry_run_enabled():
        stats["total"] = 3
        stats["skipped"] = 3
        stage(1, "凭据格式检查", "skipped", "已提供 Cookie/JWT 与 user_id")
        stage(2, "查询签到状态", "skipped", "无网络预演，未请求")
        stage(3, "执行每日签到" if not query_only else "额度查询", "skipped", "无网络预演，未请求")
        base_result.update(
            {
                "ok": True,
                "outcome": "dry_run",
                "neutral": True,
                "message": "无网络预演通过",
            }
        )
        return base_result

    client = TabbitClient(account)
    try:
        stats["total"] += 1
        stage(1, "查询签到状态", "开始")
        started = time.monotonic()
        try:
            status_payload = client.query_status()
            status = interpret_status(status_payload)
            stats["success"] += 1
            stage(
                1,
                "查询签到状态",
                "success",
                "%s；耗时%s" % (status["message"], elapsed(started)),
            )
        except Exception as error:
            stats["failed"] += 1
            raise

        # 公开 UID 来自账号契约（JWT/Cookie），官方状态接口不返回昵称；直接展示便于核对。
        base_result["identity"] = account.uid
        stage(1, "账号公开 UID", "success", account.uid)

        base_result["status"] = status["state"]
        base_result["message"] = status["message"]
        if query_only:
            if status["state"] == "ready":
                stats["total"] += 1
                started = time.monotonic()
                try:
                    usage = client.query_usage_percentage()
                    base_result["usage_percentage"] = usage
                    stats["success"] += 1
                    stage(
                        2,
                        "查询额度用量",
                        "success",
                        "%s；耗时%s" % (usage, elapsed(started)),
                    )
                except TabbitError as error:
                    stats["skipped"] += 1
                    stage(
                        2,
                        "查询额度用量",
                        "skipped",
                        "%s；耗时%s"
                        % (sanitize_message(str(error), account), elapsed(started)),
                    )
            else:
                stats["total"] += 1
                stats["skipped"] += 1
                stage(2, "查询额度用量", "skipped", "当前状态无需查询额度")
            base_result.update({"ok": True, "outcome": "query"})
            return base_result

        if status["state"] == "activity_closed":
            stats["total"] += 1
            stats["alreadyComplete"] += 1
            stage(2, "执行每日签到", "alreadyComplete", "活动未开启，跳过领取")
            base_result.update(
                {"ok": True, "outcome": "activity_closed", "neutral": True}
            )
            return base_result
        if status["state"] == "already_signed":
            stats["total"] += 1
            stats["alreadyComplete"] += 1
            stage(2, "执行每日签到", "alreadyComplete", "今日已签到")
            base_result.update(
                {"ok": True, "outcome": "already_signed", "neutral": True}
            )
            return base_result

        stats["total"] += 1
        started = time.monotonic()
        try:
            usage_percentage = client.query_usage_percentage()
            stats["success"] += 1
            stage(
                2,
                "查询额度用量",
                "success",
                "%s；耗时%s" % (usage_percentage, elapsed(started)),
            )
        except TabbitError as error:
            usage_percentage = "0.00%"
            stats["skipped"] += 1
            stage(
                2,
                "查询额度用量",
                "skipped",
                "按契约回退 0.00%%：%s；耗时%s"
                % (sanitize_message(str(error), account), elapsed(started)),
            )
        base_result["usage_percentage"] = usage_percentage

        stats["total"] += 1
        started = time.monotonic()
        claim_payload = client.claim(usage_percentage)
        outcome = interpret_sign_in(claim_payload)
        outcome["message"] = sanitize_message(outcome["message"], account)
        outcome["reward"] = sanitize_message(outcome["reward"], account)
        if outcome["ok"]:
            if outcome.get("neutral"):
                stats["alreadyComplete"] += 1
                stage(
                    3,
                    "执行每日签到",
                    "alreadyComplete",
                    "%s；耗时%s" % (outcome["message"], elapsed(started)),
                )
            else:
                stats["success"] += 1
                reward = ("；奖励 %s" % outcome["reward"]) if outcome.get("reward") else ""
                stage(
                    3,
                    "执行每日签到",
                    "success",
                    "%s%s；耗时%s" % (outcome["message"], reward, elapsed(started)),
                )
        else:
            stats["failed"] += 1
            stage(
                3,
                "执行每日签到",
                "failure",
                "%s；耗时%s" % (outcome["message"], elapsed(started)),
            )
        base_result.update(outcome)
        base_result["status"] = outcome["outcome"]
        return base_result
    except AuthError as error:
        stats["failed"] = max(stats["failed"], 1)
        if stats["total"] == 0:
            stats["total"] = 1
        base_result.update(
            {
                "ok": False,
                "outcome": "auth_failed",
                "message": sanitize_message(str(error), account),
            }
        )
        stage(1, "查询签到状态", "failure", base_result["message"])
        return base_result
    except TabbitError as error:
        if stats["failed"] == 0:
            stats["failed"] = 1
        if stats["total"] == 0:
            stats["total"] = 1
        base_result.update(
            {
                "ok": False,
                "outcome": "failed",
                "message": sanitize_message(str(error), account),
            }
        )
        return base_result
    finally:
        client.close()
        base_result["stats"] = stats


def notification_selected(no_notify: bool = False) -> bool:
    if no_notify or parse_bool(env_value("TABBIT_CN_NO_NOTIFY"), False):
        return False
    switch = env_value("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE_TEXT:
        return False
    if switch in TRUE_TEXT:
        return True
    selected = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selected is None:
        return False
    if not selected.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", selected.strip()) if part]
    script = Path(__file__)
    choices = (
        CATALOG_ID,
        script.name,
        script.as_posix(),
        "output/candidate.py",
        "tabbit_cn_daily.py",
        "scripts/tabbit_cn_daily.py",
    )
    if "*" in selectors:
        return True
    return any(
        fnmatch.fnmatchcase(choice, pattern)
        for pattern in selectors
        for choice in choices
    )


def qinglong_notify(title: str, body: str) -> bool:
    if dry_run_enabled():
        return False
    worker = r"""
import importlib, importlib.util, json, sys
from pathlib import Path
payload = json.load(sys.stdin)
paths = payload["paths"]
try:
    module = importlib.import_module("notify")
    send = getattr(module, "send", None)
    if callable(send):
        result = send(payload["title"], payload["body"])
        if result is not False:
            sys.exit(0)
except Exception:
    pass
for filename in paths:
    try:
        if not Path(filename).is_file():
            continue
        spec = importlib.util.spec_from_file_location("qinglong_task_notify", filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        send = getattr(module, "send", None)
        if callable(send) and send(payload["title"], payload["body"]) is not False:
            sys.exit(0)
    except Exception:
        continue
sys.exit(1)
"""
    dirs: List[Path] = []
    custom = env_value("QINGLONG_NOTIFY_DIR")
    if custom:
        dirs.append(Path(custom))
    dirs.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    payload = {
        "title": title,
        "body": body,
        "paths": [str(directory / "notify.py") for directory in dirs],
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", worker],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    node = shutil.which("node")
    if node:
        js_worker = (
            "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));"
            "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body))"
            ".then(r=>process.exit(r===false?1:0)).catch(()=>process.exit(1));"
        )
        for directory in dirs:
            path = directory / "sendNotify.js"
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_worker, str(path.resolve())],
                    input=json.dumps(payload, ensure_ascii=False),
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue
    return False


def legacy_notify(title: str, content: str) -> int:
    if dry_run_enabled():
        return 0
    destinations: List[Tuple[str, Dict[str, Any]]] = []
    token = env_value("PUSHPLUS_TOKEN")
    if token:
        destinations.append(
            (
                "https://www.pushplus.plus/send",
                {
                    "token": token,
                    "title": title,
                    "content": content[:18000],
                    "template": "markdown",
                },
            )
        )
    bark = env_value("BARK_URL").rstrip("/")
    if bark.startswith("https://"):
        destinations.append(
            (bark, {"title": title, "body": content[:12000], "group": "Tabbit"})
        )
    hook = env_value("WECOM_WEBHOOK")
    if hook:
        if not hook.startswith(("http://", "https://")):
            hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
        if hook.startswith("https://"):
            destinations.append(
                (
                    hook,
                    {
                        "msgtype": "text",
                        "text": {"content": ("%s\n%s" % (title, content))[:3900]},
                    },
                )
            )
    sent = 0
    for url, payload in destinations:
        try:
            response = http_request(
                "POST",
                url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=15,
            )
            data = response.json()
            code = data.get("code")
            if data.get("errcode") == 0 or str(code) in ("0", "200"):
                sent += 1
        except Exception:
            pass
    return sent


def build_notify_body(
    results: Sequence[Mapping[str, Any]],
    *,
    query_only: bool,
    dry: bool,
    status: str,
    config_error: str = "",
) -> str:
    total = len(results)
    success = sum(1 for item in results if item.get("ok"))
    failed = total - success
    lines = [
        "账号总数%d，成功%d，失败%d；状态：%s"
        % (total, success, failed, status)
    ]
    if config_error:
        lines.append("配置错误：" + compact_text(config_error, 200))
    for item in results:
        suffix = ""
        if item.get("reward"):
            suffix += " · 奖励 %s" % item["reward"]
        if item.get("usage_percentage"):
            suffix += " · 用量 %s" % item["usage_percentage"]
        identity = item.get("identity") or item.get("name") or ("账号%s" % item.get("index"))
        lines.append(
            "- %s: %s%s"
            % (identity, item.get("message") or item.get("outcome"), suffix)
        )
    if dry:
        lines.append("模式：无网络预演（未调用业务接口与通知通道）")
    elif query_only:
        lines.append("模式：仅查询状态")
    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--query", action="store_true", help="只查询状态，不发送签到请求")
    parser.add_argument(
        "--only", type=int, metavar="N", help="只处理第 N 个账号（从 1 开始）"
    )
    parser.add_argument("--no-notify", action="store_true", help="不发送通知")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    start_at = datetime.now().astimezone().isoformat(timespec="seconds")
    dry = dry_run_enabled()
    config_error = ""
    accounts: List[Account] = []

    log("===== %s =====" % TITLE)
    log("开始时间：%s" % start_at)
    log("运行模式：%s" % ("无网络预演" if dry else ("仅查询" if args.query else "正式签到")))
    log("脚本版本：v%s · 区域：%s" % (SCRIPT_VERSION, BASE_URL))

    try:
        accounts = load_accounts()
        if args.only is not None:
            if args.only < 1 or args.only > len(accounts):
                raise ConfigError("--only 超出范围: 1..%d" % len(accounts))
            accounts = [accounts[args.only - 1]]
    except ConfigError as error:
        config_error = sanitize_message(str(error))

    log("账号数量：%d" % len(accounts))
    results: List[Dict[str, Any]] = []
    substats = empty_stats()

    if config_error:
        log("%s [阶段1] 配置检查：%s；耗时%s" % (ICONS["failure"], config_error, elapsed(started)))
    else:
        for account in accounts:
            account_start = time.monotonic()
            label = display_name(account)
            log("----- 账号 %d/%d：%s -----" % (account.index, len(accounts), label))

            def stage_logger(number: int, name: str, result: str, detail: str = "") -> None:
                icon = {
                    "开始": "·",
                    "success": ICONS["success"],
                    "alreadyComplete": ICONS["alreadyComplete"],
                    "skipped": ICONS["skipped"],
                    "failure": ICONS["failure"],
                    "warning": ICONS["warning"],
                }.get(result, "·")
                status_text = {
                    "开始": "开始",
                    "success": "成功",
                    "alreadyComplete": "已完成",
                    "skipped": "跳过",
                    "failure": "失败",
                    "warning": "警告",
                }.get(result, result)
                log(
                    "[阶段%d] %s %s：%s%s"
                    % (number, icon, name, status_text, ("；" + detail) if detail else "")
                )

            result = process_account(
                account, query_only=args.query, stage_logger=stage_logger
            )
            results.append(result)
            stats = result.get("stats") or empty_stats()
            for key in substats:
                substats[key] += int(stats.get(key, 0))
            identity = result.get("identity") or label
            icon = ICONS["success"] if result.get("ok") else ICONS["failure"]
            reward = (" · 奖励 %s" % result["reward"]) if result.get("reward") else ""
            log(
                "%s 账号结果：%s · %s%s"
                % (icon, identity, result.get("message") or result.get("outcome"), reward)
            )
            log(
                "账号%d统计：总任务%d，成功%d，已完成%d，跳过%d，失败%d，耗时%s"
                % (
                    account.index,
                    stats.get("total", 0),
                    stats.get("success", 0),
                    stats.get("alreadyComplete", 0),
                    stats.get("skipped", 0),
                    stats.get("failed", 0),
                    elapsed(account_start),
                )
            )

    success_count = sum(1 for item in results if item.get("ok"))
    failed_count = (0 if config_error else len(results) - success_count) + (
        1 if config_error else 0
    )
    if config_error:
        status = "配置错误"
        business_exit = 1
    elif dry:
        status = (
            "预演完成"
            if failed_count == 0
            else ("预演部分失败" if success_count else "预演失败")
        )
        business_exit = 0 if failed_count == 0 else 1
    else:
        status = (
            "成功"
            if failed_count == 0
            else ("部分失败" if success_count else "失败")
        )
        business_exit = 0 if failed_count == 0 and results else 1

    notify_body = build_notify_body(
        results,
        query_only=args.query,
        dry=dry,
        status=status,
        config_error=config_error,
    )
    notify_status = "已关闭或未列入通知清单"
    if notification_selected(args.no_notify):
        if dry:
            notify_status = "预演通知摘要已生成（无网络，不调用通知模块）"
        else:
            ql_ok = qinglong_notify(TITLE, notify_body[:1800])
            legacy_count = legacy_notify(TITLE, notify_body[:1800])
            notify_status = "青龙已发送" if ql_ok else "青龙不可用或发送失败"
            if legacy_count:
                notify_status += "；兼容渠道发送%d个" % legacy_count

    log("===== 任务汇总 =====")
    log("账号结果：总数%d，成功%d，失败%d" % (len(results), success_count, failed_count if not config_error else failed_count))
    if config_error:
        log("配置错误：%s" % config_error)
    log(
        "子任务结果：总数%d，成功%d，已完成%d，跳过%d，失败%d"
        % (
            substats["total"],
            substats["success"],
            substats["alreadyComplete"],
            substats["skipped"],
            substats["failed"],
        )
    )
    finish_at = datetime.now().astimezone().isoformat(timespec="seconds")
    log("总耗时：%s；通知状态：%s" % (elapsed(started), notify_status))
    log("完成时间：%s；最终状态：%s" % (finish_at, status))

    summary = {
        "task": "tabbit_cn_daily",
        "catalogId": CATALOG_ID,
        "realm": REALM,
        "mode": "dry-run" if dry else ("query" if args.query else "live"),
        "status": status,
        "accounts": {
            "total": len(accounts) if not config_error else 0,
            "success": success_count,
            "failed": failed_count if not config_error else 1,
        },
        "subtasks": substats,
        "notification": notify_status,
        "exitCode": business_exit,
        "configurationError": bool(config_error),
        "startedAt": start_at,
        "finishedAt": finish_at,
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return business_exit


if __name__ == "__main__":
    sys.exit(main())
