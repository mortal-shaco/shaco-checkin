#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 米游社游戏签到
# cron: 11 8 * * *
#
# 来源：zyhqwq/sign-myself mihoyo/miyoushe_sign.py（MIT）
# 参考同仓 miyoushe_debug.py（只读诊断，不并入定时任务）
# 与 miyoushe_qr_login.py（本地扫码取 Cookie，非定时任务；仅用于参数获取说明）
#
# MIT License
#
# Copyright (c) zyhqwq / sign-myself contributors
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
"""
米游社游戏签到（青龙独立维护版）

功能清点（相对上游 miyoushe_sign.py）：
- 使用 Cookie / stoken 刷新 cookie_token
- 查询绑定角色，仅为已绑定角色签到
- 原神 / 崩坏:星穹铁道 / 绝区零 月卡签到福利
- 可选 MIYOUSHE_ONLY 按 game_biz 过滤
- 明确不做社区米游币签到（上游已说明第三方接口被封禁）

未合并（非同一时机的定时账号任务）：
- miyoushe_qr_login.py：本地扫码登录写文件
- miyoushe_debug.py：本地只读诊断

维护改动：
- 去掉私有 notify 依赖与仓库相对路径；标准库 HTTP 实现
- 多账号改为每行一个 Cookie；任一账号失败整体非零退出
- MIYOUSHE_DRY_RUN 完全断网预演、青龙通知、时间轴日志与 TASK_SUMMARY

环境变量：
  MIYOUSHE_COOKIE      必填。每行一个账号 Cookie（可含 stoken 或网页 cookie_token）
  MIYOUSHE_DEVICE_ID   可选。Cookie 未含 device_id 时的设备 ID 回退
  MIYOUSHE_ONLY        可选。仅签指定 game_biz，逗号分隔，如 hk4e_cn,hkrpg_cn,nap_cn
  MIYOUSHE_TIMEOUT     可选。单次 HTTP 超时秒数，默认 15
  MIYOUSHE_GAME_GAP    可选。同账号游戏间间隔秒数，默认 3（断网预演不睡眠）
  MIYOUSHE_ACCOUNT_GAP 可选。账号间隔秒数，默认 2
  MIYOUSHE_DRY_RUN     1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略
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
        _ql_notify_identities = ('132658a551b47b61', 'scripts/miyoushe_sign.py', 'miyoushe_sign.py', 'miyoushe_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "132658a551b47b61"
TASK_NAME = "米游社游戏签到"
SCRIPT_FILENAME = "miyoushe_sign.py"

PASSPORT_API = "https://passport-api.mihoyo.com"
TAKUMI_API = "https://api-takumi.mihoyo.com"
NAP_API = "https://act-nap-api.mihoyo.com"
BINDING_URL = TAKUMI_API + "/binding/api/getUserGameRolesByCookie"

GAMES = [
    {
        "biz": "hk4e_cn",
        "name": "原神",
        "act_id": "e202311201442471",
        "signgame": "hk4e",
        "base": TAKUMI_API,
        "sub": "",
    },
    {
        "biz": "hkrpg_cn",
        "name": "崩坏:星穹铁道",
        "act_id": "e202304121516551",
        "signgame": "",
        "base": TAKUMI_API,
        "sub": "",
    },
    {
        "biz": "nap_cn",
        "name": "绝区零",
        "act_id": "e202406242138391",
        "signgame": "zzz",
        "base": NAP_API,
        "sub": "/zzz",
    },
]

DS_SALT_WEB = "G1ktdwFL4IyGkHuuWSmz0wUe9Db9scyK"
LOGIN_INVALID = frozenset((-100, -101, 10001, 1008, 10103, 10104))
ALREADY_SIGNED = -5003
CAPTCHA = 1034
MAX_RESPONSE_BYTES = 512 * 1024
DEFAULT_TIMEOUT = 15
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
BEIJING = timezone(timedelta(hours=8), "Asia/Shanghai")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SECRETS: List[str] = []
_DEVICE: Optional[str] = None


def now_beijing() -> datetime:
    return datetime.now(BEIJING)


def now_text() -> str:
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return now_beijing().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def parse_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip() or str(default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("{} 必须是 {} 到 {} 的整数".format(name, minimum, maximum)) from exc
    if value < minimum or value > maximum:
        raise ValueError("{} 必须是 {} 到 {} 的整数".format(name, minimum, maximum))
    return value


def redact(text: Any, limit: int = 200) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for secret in sorted({item for item in SECRETS if item}, key=len, reverse=True):
        if secret and secret in value:
            value = value.replace(secret, "[已隐藏]")
    value = re.sub(
        r"(?i)(cookie|token|stoken|ltoken|authorization|session|signature|"
        r"device[_-]?id|cookie_token(?:_v2)?)\s*[:=]\s*[^\s,;]+",
        "[敏感字段已隐藏]",
        value,
    )
    value = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", value)
    return value[:limit] if value else "未提供业务消息"


def remember_secret(value: str) -> None:
    text = (value or "").strip()
    if text and text not in SECRETS:
        SECRETS.append(text)


def random_string(n: int) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def set_device(device_id: Optional[str]) -> None:
    global _DEVICE
    _DEVICE = (device_id or "").strip() or None


def gen_ds() -> str:
    t = str(int(time.time()))
    r = random_string(6)
    c = hashlib.md5("salt={}&t={}&r={}".format(DS_SALT_WEB, t, r).encode()).hexdigest()
    return "{},{},{}".format(t, r, c)


def parse_cookie(cookie_str: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for item in cookie_str.replace("\n", "").split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value
            if value and key.lower() in {
                "stoken",
                "ltoken",
                "ltoken_v2",
                "cookie_token",
                "cookie_token_v2",
                "device_id",
                "devicefp",
            }:
                remember_secret(value)
    return cookies


def validate_cookie_fields(cookies: Dict[str, str]) -> str:
    """返回将使用的凭证形态说明；字段不足时抛错。"""
    if cookies.get("account_id") and cookies.get("cookie_token"):
        return "v1(cookie_token)"
    if cookies.get("account_id") and cookies.get("cookie_token_v2"):
        return "v2(cookie_token_v2)"
    if cookies.get("stoken"):
        return "stoken"
    raise ValueError("Cookie 缺少有效字段(account_id+cookie_token[_v2] 或 stoken)")


def load_accounts() -> List[str]:
    raw = os.getenv("MIYOUSHE_COOKIE", "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not accounts:
        raise ValueError(
            "未配置 MIYOUSHE_COOKIE；请每行填写一个账号 Cookie"
            "（可用本地扫码工具获取，详见参数说明）"
        )
    for cookie in accounts:
        remember_secret(cookie)
        cookies = parse_cookie(cookie)
        validate_cookie_fields(cookies)
    return accounts


def passport_headers(device_id: Optional[str] = None) -> Dict[str, str]:
    return {
        "User-Agent": "HYPContainer/1.3.3.182",
        "x-rpc-app_id": "ddxf5dufpuyo",
        "x-rpc-client_type": "3",
        "x-rpc-device_id": device_id or _DEVICE or random_string(16),
        "Accept": "application/json, text/plain, */*",
    }


def web_headers(cookie_str: str) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile "
            "Safari/537.36 miHoYoBBS/2.109.0"
        ),
        "x-rpc-app_version": "2.109.0",
        "x-rpc-client_type": "5",
        "Origin": "https://act.mihoyo.com",
        "Referer": "https://act.mihoyo.com/",
        "x-rpc-channel": "miyousheluodi",
        "X-Requested-With": "com.mihoyo.hyperion",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,en-US;q=0.8",
        "Connection": "keep-alive",
        "x-rpc-device_id": _DEVICE or random_string(32),
        "Cookie": cookie_str,
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("接口重定向已阻止，未转发凭据")


def http_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    timeout: float,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    full_url = url
    data = None
    req_headers = dict(headers)
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        full_url = url + ("&" if "?" in url else "?") + query
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = urllib.request.Request(full_url, data=data, headers=req_headers, method=method.upper())
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("接口返回 HTTP {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        reason_name = type(reason).__name__ if reason is not None else "网络错误"
        raise RuntimeError("网络请求失败（{}）".format(reason_name)) from exc
    except TimeoutError as exc:
        raise RuntimeError("网络请求超时") from exc
    if status < 200 or status >= 300:
        raise RuntimeError("接口返回 HTTP {}".format(status))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("接口响应超过安全上限")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("接口未返回有效 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("接口 JSON 顶层结构无效")
    return payload


def refresh_cookie_token(cookies: Dict[str, str], timeout: float) -> str:
    stoken = cookies.get("stoken") or ""
    if cookies.get("device_id"):
        set_device(cookies["device_id"])
    uid = cookies.get("stuid") or cookies.get("ltuid") or ""
    mid = cookies.get("mid", "")
    if not stoken:
        raise RuntimeError("Cookie 缺少 stoken 字段")
    remember_secret(stoken)
    cookie_header = "stoken={};stuid={};mid={}".format(stoken, uid, mid)
    remember_secret(cookie_header)
    data = http_json(
        "GET",
        PASSPORT_API + "/account/auth/api/getCookieAccountInfoBySToken",
        {**passport_headers(), "Cookie": cookie_header},
        timeout,
        params={"stoken": stoken, "uid": uid, "mid": mid},
    )
    if data.get("retcode") != 0:
        raise RuntimeError(
            "stoken 已失效（{}），请重新扫码获取".format(redact(data.get("message"), 40))
        )
    token = ((data.get("data") or {}) if isinstance(data.get("data"), dict) else {}).get("cookie_token")
    if not token:
        raise RuntimeError("刷新 cookie_token 失败：返回为空")
    remember_secret(str(token))
    cookies["cookie_token"] = str(token)
    return "account_id={};cookie_token={}".format(uid, token)


def build_web_cookie(cookies: Dict[str, str], timeout: float) -> str:
    if cookies.get("account_id") and cookies.get("cookie_token"):
        built = "account_id={};cookie_token={}".format(
            cookies["account_id"], cookies["cookie_token"]
        )
        remember_secret(built)
        return built
    if cookies.get("account_id") and cookies.get("cookie_token_v2"):
        keys = [
            "account_id",
            "account_mid_v2",
            "cookie_token_v2",
            "ltoken_v2",
            "ltmid_v2",
            "mid",
            "devicefp",
        ]
        parts = ["{}={}".format(k, cookies[k]) for k in keys if cookies.get(k)]
        built = ";".join(parts)
        remember_secret(built)
        return built
    if cookies.get("stoken"):
        return refresh_cookie_token(cookies, timeout)
    raise RuntimeError("Cookie 缺少有效字段(account_id+cookie_token[_v2] 或 stoken)")


def get_roles(cookie_str: str, timeout: float) -> List[Dict[str, Any]]:
    roles: List[Dict[str, Any]] = []
    for biz in sorted({game["biz"] for game in GAMES}):
        try:
            data = http_json(
                "GET",
                BINDING_URL,
                web_headers(cookie_str),
                timeout,
                params={"game_biz": biz},
            )
        except Exception as exc:
            log(
                "{} 查询 {} 角色失败：{}".format(
                    ICONS["warning"], biz, redact(exc, 60)
                )
            )
            continue
        if data.get("retcode") != 0:
            log(
                "{} 查询 {} 角色业务失败：{}".format(
                    ICONS["warning"],
                    biz,
                    redact(data.get("message"), 40),
                )
            )
            continue
        payload = data.get("data") or {}
        items = payload.get("list") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            continue
        for role in items:
            if isinstance(role, dict):
                roles.append(role)
    return roles


def luna_request(
    method: str,
    path: str,
    game: Dict[str, str],
    cookie_str: str,
    timeout: float,
    **params: Any,
) -> Dict[str, Any]:
    url = "{}/event/luna{}/{}".format(game["base"], game["sub"], path)
    headers = web_headers(cookie_str)
    if game["signgame"]:
        headers["x-rpc-signgame"] = game["signgame"]
    headers["DS"] = gen_ds()
    payload = {"lang": "zh-cn", "act_id": game["act_id"]}
    payload.update(params)
    if method.lower() == "get":
        return http_json("GET", url, headers, timeout, params=payload)
    return http_json("POST", url, headers, timeout, body=payload)


def get_awards(game: Dict[str, str], cookie_str: str, timeout: float) -> List[Dict[str, Any]]:
    try:
        data = luna_request("get", "home", game, cookie_str, timeout)
    except Exception:
        return []
    if data.get("retcode") != 0:
        return []
    awards = ((data.get("data") or {}) if isinstance(data.get("data"), dict) else {}).get("awards")
    return awards if isinstance(awards, list) else []


def award_of(awards: List[Dict[str, Any]], day_1based: int) -> str:
    if awards and 1 <= day_1based <= len(awards):
        item = awards[day_1based - 1]
        if isinstance(item, dict) and item.get("name"):
            return "「{}」x{}".format(item.get("name"), item.get("cnt", 1))
    return ""


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def sign_game(
    game: Dict[str, str],
    role: Dict[str, Any],
    cookie_str: str,
    timeout: float,
) -> Tuple[str, str]:
    """返回 (outcome, message)；outcome in success|already|failed。"""
    nickname = str(role.get("nickname") or "").strip() or "角色"
    level = role.get("level")
    role_label = "{} Lv{}".format(nickname, level) if level is not None else nickname
    uid = str(role.get("game_uid") or "")
    region = str(role.get("region") or "")
    try:
        info = luna_request(
            "get", "info", game, cookie_str, timeout, uid=uid, region=region
        )
    except Exception as exc:
        return "failed", "{} {} 请求异常 - {}".format(game["name"], role_label, redact(exc, 60))

    retcode = info.get("retcode")
    try:
        retcode_int = int(retcode) if retcode is not None else None
    except (TypeError, ValueError):
        retcode_int = None

    if retcode_int in LOGIN_INVALID:
        return "failed", "{} {} Cookie 已失效，请重新扫码获取".format(game["name"], role_label)
    if retcode_int == CAPTCHA:
        return "failed", "{} {} 触发风控验证(1034)，今日未能签到".format(game["name"], role_label)
    if retcode_int != 0:
        return (
            "failed",
            "{} {} 查询签到状态失败 - {} ({})".format(
                game["name"], role_label, redact(info.get("message"), 40), retcode
            ),
        )

    data = info.get("data") if isinstance(info.get("data"), dict) else {}
    if data.get("first_bind"):
        return (
            "failed",
            "{} {} 首次绑定，请先在米游社 App 手动签到一次".format(game["name"], role_label),
        )

    total_days = int(data.get("total_sign_day") or 0)
    if boolish(data.get("is_sign")):
        return "already", "{} {} 今天已签到（本月累计{}天）".format(
            game["name"], role_label, total_days
        )

    result = luna_request(
        "post", "sign", game, cookie_str, timeout, uid=uid, region=region
    )
    try:
        rc2 = int(result.get("retcode")) if result.get("retcode") is not None else None
    except (TypeError, ValueError):
        rc2 = None

    if rc2 == 0:
        sign_data = result.get("data") if isinstance(result.get("data"), dict) else {}
        award = sign_data.get("award") if isinstance(sign_data.get("award"), dict) else {}
        if award.get("name"):
            award_text = "「{}」x{}".format(award.get("name"), award.get("cnt", 1))
        else:
            award_text = award_of(get_awards(game, cookie_str, timeout), total_days + 1)
        suffix = "，奖励{}".format(award_text) if award_text else ""
        return "success", "{} {} 签到成功{}".format(game["name"], role_label, suffix)
    if rc2 == ALREADY_SIGNED:
        return "already", "{} {} 今天已签到".format(game["name"], role_label)
    if rc2 == CAPTCHA:
        return "failed", "{} {} 触发风控验证(1034)，今日未能签到".format(game["name"], role_label)
    if rc2 in LOGIN_INVALID:
        return "failed", "{} {} Cookie 已失效，请重新扫码获取".format(game["name"], role_label)
    return (
        "failed",
        "{} {} 签到失败 - {} (retcode={})".format(
            game["name"], role_label, redact(result.get("message"), 40), rc2
        ),
    )


def account_identity_from_roles(roles: List[Dict[str, Any]], index: int) -> str:
    nicknames = []
    for role in roles:
        nick = str(role.get("nickname") or "").strip()
        if nick and nick not in nicknames:
            nicknames.append(nick)
    if nicknames:
        return "/".join(nicknames[:3])
    return "账号{}".format(index)


def run_account(
    index: int,
    cookie_raw: str,
    dry_run: bool,
    timeout: float,
    game_gap: float,
    only_biz: set,
) -> Dict[str, Any]:
    started = time.monotonic()
    stats = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    errors: List[str] = []
    identity = "账号{}".format(index)
    print("\n========== {} ==========".format(identity), flush=True)

    cookies = parse_cookie(cookie_raw)
    set_device(cookies.get("device_id") or os.environ.get("MIYOUSHE_DEVICE_ID") or os.environ.get("DEVICE_ID"))

    # 阶段 1：凭证准备
    stage_no = 1
    stage_started = time.monotonic()
    stats["total"] += 1
    prefix = "[账号{}][{}/?]".format(index, stage_no)
    log("{} 凭证准备开始".format(prefix))
    web_cookie = ""
    try:
        fmt = validate_cookie_fields(cookies)
        if dry_run:
            stats["skipped"] += 1
            log(
                "{} {} 凭证准备：已校验 {}，未发起网络请求（{:.2f}秒）".format(
                    prefix, ICONS["skipped"], fmt, time.monotonic() - stage_started
                )
            )
        else:
            web_cookie = build_web_cookie(cookies, timeout)
            stats["success"] += 1
            log(
                "{} {} 凭证准备完成（形态={}，{:.2f}秒）".format(
                    prefix, ICONS["success"], fmt, time.monotonic() - stage_started
                )
            )
    except Exception as exc:
        stats["failed"] += 1
        message = redact(exc, 80)
        errors.append(message)
        log(
            "{} {} 凭证准备失败：{}（{:.2f}秒）".format(
                prefix, ICONS["failure"], message, time.monotonic() - stage_started
            )
        )
        elapsed = time.monotonic() - started
        log(
            "[账号{}] 结果=FAILED；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
                index,
                identity,
                stats["total"],
                stats["success"],
                stats["already"],
                stats["skipped"],
                stats["failed"],
                elapsed,
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": False,
            "stats": stats,
            "elapsed": elapsed,
            "errors": errors,
        }

    # 阶段 2：角色查询
    stage_no = 2
    stage_started = time.monotonic()
    stats["total"] += 1
    prefix = "[账号{}][{}/?]".format(index, stage_no)
    log("{} 角色查询开始".format(prefix))
    roles: List[Dict[str, Any]] = []
    if dry_run:
        stats["skipped"] += 1
        log(
            "{} {} 角色查询：断网预演跳过（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
    else:
        try:
            roles = get_roles(web_cookie, timeout)
            identity = account_identity_from_roles(roles, index)
            if identity != "账号{}".format(index):
                log("{} 公开身份：{}".format(prefix, identity))
            stats["success"] += 1
            log(
                "{} {} 绑定角色数 {}（{:.2f}秒）".format(
                    prefix, ICONS["success"], len(roles), time.monotonic() - stage_started
                )
            )
        except Exception as exc:
            stats["failed"] += 1
            message = redact(exc, 80)
            errors.append(message)
            log(
                "{} {} 角色查询失败：{}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], message, time.monotonic() - stage_started
                )
            )
            elapsed = time.monotonic() - started
            log(
                "[账号{}] 结果=FAILED；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
                    index,
                    identity,
                    stats["total"],
                    stats["success"],
                    stats["already"],
                    stats["skipped"],
                    stats["failed"],
                    elapsed,
                )
            )
            return {
                "index": index,
                "identity": identity,
                "ok": False,
                "stats": stats,
                "elapsed": elapsed,
                "errors": errors,
            }

    if dry_run:
        stage_no = 3
        stage_started = time.monotonic()
        stats["total"] += 1
        prefix = "[账号{}][{}/3]".format(index, stage_no)
        log("{} 游戏签到开始".format(prefix))
        stats["skipped"] += 1
        log(
            "{} {} 游戏签到：断网预演跳过（{:.2f}秒）".format(
                prefix, ICONS["skipped"], time.monotonic() - stage_started
            )
        )
        elapsed = time.monotonic() - started
        log(
            "[账号{}] 结果=DRY_RUN；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
                index,
                identity,
                stats["total"],
                stats["success"],
                stats["already"],
                stats["skipped"],
                stats["failed"],
                elapsed,
            )
        )
        log("DRY_RUN_OK")
        return {
            "index": index,
            "identity": identity,
            "ok": True,
            "stats": stats,
            "elapsed": elapsed,
            "errors": errors,
        }

    if only_biz:
        roles = [role for role in roles if role.get("game_biz") in only_biz]

    if not roles:
        stage_no = 3
        stage_started = time.monotonic()
        stats["total"] += 1
        prefix = "[账号{}][{}/3]".format(index, stage_no)
        log("{} 游戏签到开始".format(prefix))
        stats["skipped"] += 1
        reason = "所选游戏未绑定角色，跳过" if only_biz else "未绑定任何游戏角色，无需签到"
        log(
            "{} {} {}（{:.2f}秒）".format(
                prefix, ICONS["skipped"], reason, time.monotonic() - stage_started
            )
        )
        elapsed = time.monotonic() - started
        log(
            "[账号{}] 结果=SUCCESS；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
                index,
                identity,
                stats["total"],
                stats["success"],
                stats["already"],
                stats["skipped"],
                stats["failed"],
                elapsed,
            )
        )
        return {
            "index": index,
            "identity": identity,
            "ok": True,
            "stats": stats,
            "elapsed": elapsed,
            "errors": errors,
        }

    signable = []
    for role in roles:
        game = next((item for item in GAMES if item["biz"] == role.get("game_biz")), None)
        if game:
            signable.append((game, role))

    total_stages = 2 + len(signable)
    for offset, (game, role) in enumerate(signable, 1):
        stage_no = 2 + offset
        stage_started = time.monotonic()
        stats["total"] += 1
        prefix = "[账号{}][{}/{}]".format(index, stage_no, total_stages)
        stage_name = "{}签到".format(game["name"])
        log("{} {}开始".format(prefix, stage_name))
        try:
            outcome, message = sign_game(game, role, web_cookie, timeout)
            if outcome == "success":
                stats["success"] += 1
                icon = ICONS["success"]
            elif outcome == "already":
                stats["already"] += 1
                icon = ICONS["alreadyComplete"]
            else:
                stats["failed"] += 1
                icon = ICONS["failure"]
                errors.append(message)
            log(
                "{} {} {}（{:.2f}秒）".format(
                    prefix, icon, message, time.monotonic() - stage_started
                )
            )
        except Exception as exc:
            stats["failed"] += 1
            message = redact(exc, 80)
            errors.append(message)
            log(
                "{} {} {}失败：{}（{:.2f}秒）".format(
                    prefix, ICONS["failure"], stage_name, message, time.monotonic() - stage_started
                )
            )
        if offset < len(signable) and game_gap > 0:
            time.sleep(game_gap)

    elapsed = time.monotonic() - started
    ok = stats["failed"] == 0
    result_label = "SUCCESS" if ok else "FAILED"
    log(
        "[账号{}] 结果={}；身份={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            index,
            result_label,
            identity,
            stats["total"],
            stats["success"],
            stats["already"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return {
        "index": index,
        "identity": identity,
        "ok": ok,
        "stats": stats,
        "elapsed": elapsed,
        "errors": errors,
    }


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
        SCRIPT_FILENAME,
        "candidate.py",
        "scripts/miyoushe_sign.py",
        "miyoushe",
        script_path,
    }
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled(no_notify: bool = False) -> bool:
    if no_notify:
        return False
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value not in TRUE_VALUES and value != "auto":
        log("{} QINGLONG_NOTIFY 值无效，按 auto 处理".format(ICONS["warning"]))
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    paths.append(Path(__file__).resolve().parent / "notify.py")
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    return paths


def send_notification(title: str, body: str, dry_run: bool, no_notify: bool = False) -> str:
    if not notification_enabled(no_notify=no_notify):
        log("通知状态：已按 QINGLONG_NOTIFY、脚本选择规则或 --no-notify 关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
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
    paths = [None] + [path for path in python_notifier_paths() if path.is_file()]
    for path in paths:
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
        for path in js_notifier_paths():
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

    log("{} 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码".format(ICONS["warning"]))
    return "unavailable"


def print_summary(summary: Dict[str, Any]) -> None:
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def finish_config_error(
    started_at: str, overall_started: float, dry_run: bool, message: str, no_notify: bool
) -> int:
    log("账号数量：0")
    log("[0/0] {} 配置错误：{}".format(ICONS["failure"], message))
    body = "账号总数：0；成功：0；失败：1；状态：配置错误"
    notify_state = send_notification(TASK_NAME, body, dry_run, no_notify=no_notify)
    finished_at = now_text()
    print("-" * 56)
    print("账号结果：总数 0，成功 0，失败 1")
    print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0")
    print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：CONFIG_ERROR")
    print_summary(
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
        }
    )
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    no_notify = "--no-notify" in argv
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("MIYOUSHE_DRY_RUN")
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        timeout = float(parse_int_env("MIYOUSHE_TIMEOUT", DEFAULT_TIMEOUT, 3, 120))
        game_gap = float(parse_int_env("MIYOUSHE_GAME_GAP", 3, 0, 30))
        account_gap = float(parse_int_env("MIYOUSHE_ACCOUNT_GAP", 2, 0, 60))
        only_biz = {
            item.strip()
            for item in os.getenv("MIYOUSHE_ONLY", "").split(",")
            if item.strip()
        }
        accounts = load_accounts()
    except ValueError as exc:
        return finish_config_error(
            started_at, overall_started, dry_run, redact(exc), no_notify
        )

    log("账号数量：{}".format(len(accounts)))
    if only_biz:
        log("仅签到游戏：{}".format(",".join(sorted(only_biz))))

    results: List[Dict[str, Any]] = []
    for index, cookie in enumerate(accounts, 1):
        results.append(
            run_account(index, cookie, dry_run, timeout, game_gap, only_biz)
        )
        if not dry_run and index < len(accounts) and account_gap > 0:
            time.sleep(account_gap)

    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
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

    identity_bits = []
    for item in results:
        identity_bits.append("{}:{}".format(item["index"], item["identity"]))
    body = "账号总数：{}；成功：{}；失败：{}；状态：{}；身份摘要：{}".format(
        len(results),
        account_success,
        account_failed,
        status,
        "；".join(identity_bits) if identity_bits else "无",
    )
    notify_state = send_notification(TASK_NAME, body, dry_run, no_notify=no_notify)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    print("\n" + "-" * 56)
    print(
        "账号结果：总数 {}，成功 {}，失败 {}".format(
            len(results), account_success, account_failed
        )
    )
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(
            **task_stats
        )
    )
    print("总耗时：{:.2f}秒".format(elapsed))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    final_status = {
        "dry-run": "DRY_RUN_SUCCESS",
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
    }.get(status, status.upper())
    print("最终状态：{}".format(final_status))
    print_summary(
        {
            "status": status,
            "mode": "dry-run" if dry_run else "live",
            "accounts": {
                "total": len(results),
                "success": account_success,
                "failed": account_failed,
            },
            "tasks": {
                "total": task_stats["total"],
                "success": task_stats["success"],
                "alreadyComplete": task_stats["already"],
                "skipped": task_stats["skipped"],
                "failed": task_stats["failed"],
            },
            "notification": notify_state,
            "elapsedSeconds": round(elapsed, 3),
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
