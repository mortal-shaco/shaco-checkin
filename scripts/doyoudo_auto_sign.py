#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Doyoudo每日签到发言
# cron: 59 8 * * *
#
# 来源：xueshanlinghu/doyoudo-auto-sign doyoudo_auto_sign.py（MIT）
# https://github.com/xueshanlinghu/doyoudo-auto-sign
# 提交：f448a9efbc2e70e155a2b3942383e56226433ee1
#
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2020 雪山凌狐
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
"""Doyoudo（www.doyoudo.com）登录签到与发言 - 青龙维护版。

功能清点（相对上游 doyoudo_auto_sign.py）：
- POST /api/user/login/ 使用用户名与密码登录，校验 errno==0 并取得 token
- 本地按 CryptoJS.AES.encrypt(token, \"dyd\") 兼容算法生成 dyd-token Cookie，
  不再依赖 localhost:3002 加密服务或 Node 可执行文件
- POST /api/user/sign/ 每日签到；errno==0 为成功，识别「已签」类业务提示
- POST /api/voice/ 发言获取积分；文案优先一言 HTTPS 随机文本，失败回落本地列表
- GET /api/user/my_info/ 读取公开用户名等非凭据身份用于核对
- 移除 argv 明文传参、token/dyd-token 日志、无超时请求与写盘 log.log

DOYOUDO_ACCOUNTS：每个非空行一个账号，格式 用户名|密码；仅在首个竖线处分割。
兼容单账号别名：同时设置 DOYOUDO_USERNAME 与 DOYOUDO_PASSWORD（仅当
DOYOUDO_ACCOUNTS 为空）。
DOYOUDO_ACTIONS：逗号/分号/空白分隔，默认 sign,say,info（与上游顺序一致）。
DOYOUDO_LOCAL_TEXT：发言在一言不可用时的本地正文覆盖（最多 280 字）。
DOYOUDO_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
DOYOUDO_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
正式运行需安装公开包 pycryptodome（本地 AES）；断网预演不要求安装。
建议 Cron：30 8 * * *（对齐上游 GitHub Actions 北京时间约 08:30）。
不打印密码、Token、dyd-token、Cookie 或原始响应；官方返回的用户名直接展示。
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
        _ql_notify_identities = ('aa8ce405ac3abf85', 'scripts/doyoudo_auto_sign.py', 'doyoudo_auto_sign.py', 'doyoudo_auto_sign')
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
import http.cookiejar
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "Doyoudo每日签到发言"
CATALOG_ID = "aa8ce405ac3abf85"
HOST = "www.doyoudo.com"
HITOKOTO_HOST = "v1.hitokoto.cn"
LOGIN_URL = "https://www.doyoudo.com/api/user/login/"
SIGN_URL = "https://www.doyoudo.com/api/user/sign/"
SAY_URL = "https://www.doyoudo.com/api/voice/"
INFO_URL = "https://www.doyoudo.com/api/user/my_info/"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
DYD_AES_PASSPHRASE = "dyd"
DEFAULT_TIMEOUT = 15
MAX_BYTES = 65536
HITOKOTO_TIMEOUT = 8
HITOKOTO_LIMIT = 16384
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ALLOWED_ACTIONS = ("sign", "say", "info")
DEFAULT_ACTIONS = ("sign", "say", "info")
LOCAL_SAY_TEXTS = (
    "今天也要好好努力学习~",
    "每日学一点，我要努力学习！",
    "打卡打卡来啦！~",
    "每日签到，拿雪糕！~",
    "学如逆水行舟",
)
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
UA = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/65.0.3314.0 Safari/537.36 SE 2.X MetaSr 1.0"
)
ALREADY_MARKERS = (
    "已签到",
    "已经签到",
    "今日已签",
    "今天已签",
    "重复签到",
    "签过了",
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def compact(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:280]


def resolve_timeout() -> float:
    raw = env("DOYOUDO_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("DOYOUDO_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("DOYOUDO_TIMEOUT 须在 5 到 60 秒之间")
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
        raise SafeError("DOYOUDO_ACTIONS 含未知动作，仅允许 sign/say/info")
    # 保序去重
    ordered: List[str] = []
    for item in parts:
        if item not in ordered:
            ordered.append(item)
    return ordered


def parse_account_line(text: str) -> Dict[str, str]:
    if "|" not in text:
        raise SafeError("账号行缺少竖线分隔符；格式为 用户名|密码")
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("用户名或密码为空")
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
        raise SafeError("账号行含控制字符")
    return {"username": username, "password": password}


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    return accounts


def load_accounts() -> List[Dict[str, str]]:
    raw = env("DOYOUDO_ACCOUNTS")
    if raw:
        accounts = parse_accounts(raw)
        if not accounts:
            raise SafeError("DOYOUDO_ACCOUNTS 没有有效账号行")
        return accounts
    username = env("DOYOUDO_USERNAME")
    password = env("DOYOUDO_PASSWORD")
    if username or password:
        if not username or not password:
            raise SafeError("单账号别名须同时提供 DOYOUDO_USERNAME 与 DOYOUDO_PASSWORD")
        return [{"username": username, "password": password}]
    raise SafeError("未配置 DOYOUDO_ACCOUNTS，或单账号别名 DOYOUDO_USERNAME/DOYOUDO_PASSWORD")


def evp_bytes_to_key(password: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16) -> Tuple[bytes, bytes]:
    """OpenSSL / CryptoJS 口令派生（MD5，1 轮）。"""
    derived = b""
    block = b""
    while len(derived) < key_len + iv_len:
        block = hashlib.md5(block + password + salt).digest()
        derived += block
    return derived[:key_len], derived[key_len : key_len + iv_len]


def cryptojs_aes_encrypt(plaintext: str, passphrase: str) -> str:
    """等价于 CryptoJS.AES.encrypt(text, passphrase).toString()。"""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError as exc:
        raise SafeError(
            "缺少公开依赖 pycryptodome，请在青龙依赖管理中执行：pip install pycryptodome"
        ) from exc
    salt = os.urandom(8)
    key, iv = evp_bytes_to_key(passphrase.encode("utf-8"), salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(b"Salted__" + salt + ciphertext).decode("ascii")


def ensure_pycryptodome() -> None:
    try:
        from Crypto.Cipher import AES  # noqa: F401
        from Crypto.Util.Padding import pad  # noqa: F401
    except ImportError as exc:
        raise SafeError(
            "缺少公开依赖 pycryptodome，请在青龙依赖管理中执行：pip install pycryptodome"
        ) from exc


def http_json(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    cookies: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    limit: int = MAX_BYTES,
    dry_run: bool = False,
    allow_hosts: Optional[Tuple[str, ...]] = None,
) -> Dict[str, Any]:
    if dry_run:
        raise SafeError("断网预演禁止 HTTP 请求")
    parsed_host = urllib.parse.urlparse(url).hostname or ""
    allowed = allow_hosts or (HOST,)
    if parsed_host not in allowed:
        raise SafeError("拒绝访问非白名单主机")
    jar = http.cookiejar.CookieJar()
    if cookies:
        for name, value in cookies.items():
            jar.set_cookie(
                http.cookiejar.Cookie(
                    version=0,
                    name=str(name),
                    value=str(value),
                    port=None,
                    port_specified=False,
                    domain=parsed_host,
                    domain_specified=True,
                    domain_initial_dot=False,
                    path="/",
                    path_specified=True,
                    secure=url.startswith("https"),
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.ProxyHandler({}),
    )
    request_headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        request_headers.update(headers)
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json;charset=UTF-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            raise SafeError("不支持的请求体类型")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
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
    return {"status": status, "json": payload, "text": text}


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "errmsg", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value, 120)
    return ""


def is_already_complete(message: str) -> bool:
    text = message or ""
    return any(marker in text for marker in ALREADY_MARKERS)


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


def published_text(dry_run: bool, timeout: float) -> Tuple[str, str]:
    override = normalize_public_text(env("DOYOUDO_LOCAL_TEXT"))
    fallback = override or random.choice(LOCAL_SAY_TEXTS)
    fallback = normalize_public_text(fallback) or LOCAL_SAY_TEXTS[0]
    if dry_run:
        return fallback, "断网预演：不请求一言，使用本地文案"
    try:
        result = http_json(
            HITOKOTO_URL,
            method="GET",
            timeout=min(timeout, HITOKOTO_TIMEOUT),
            limit=HITOKOTO_LIMIT,
            dry_run=False,
            allow_hosts=(HITOKOTO_HOST,),
        )
        if result["status"] != 200 or not isinstance(result["json"], dict):
            raise SafeError("文案接口响应不可用")
        return format_hitokoto(result["json"]), "使用一言文案，保留作者和作品署名"
    except Exception:
        return fallback, "一言不可用，使用本地发言文案"


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


class DoyoudoClient:
    def __init__(self, timeout: float, dry_run: bool = False):
        self.timeout = timeout
        self.dry_run = dry_run
        self.token = ""
        self.dyd_token = ""

    def _auth_headers(self, with_json: bool = True) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Token": self.token,
        }
        if with_json:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        return headers

    def _cookies(self) -> Dict[str, str]:
        return {"dyd-token": self.dyd_token}

    def login(self, username: str, password: str) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        result = http_json(
            LOGIN_URL,
            method="POST",
            headers={"Content-Type": "application/json;charset=UTF-8"},
            body={"username": username, "password": password},
            timeout=self.timeout,
            dry_run=self.dry_run,
        )
        if result["status"] != 200:
            raise SafeError("登录请求失败（HTTP {}）".format(result["status"]))
        payload = result["json"]
        if not isinstance(payload, dict):
            raise SafeError("登录响应不是 JSON 对象")
        if payload.get("errno") != 0:
            message = business_message(payload) or "登录业务失败"
            raise SafeError("登录失败：{}".format(message))
        results = payload.get("results")
        if not isinstance(results, dict):
            raise SafeError("登录响应缺少 results")
        token = results.get("token")
        if not isinstance(token, str) or not token.strip():
            raise SafeError("登录响应缺少 token")
        self.token = token.strip()
        return "success", "登录成功，已取得会话", {"has_token": True}

    def build_dyd_token(self) -> Tuple[str, str, None]:
        if not self.token:
            raise SafeError("缺少登录 token，无法生成 dyd-token")
        self.dyd_token = cryptojs_aes_encrypt(self.token, DYD_AES_PASSPHRASE)
        if not self.dyd_token:
            raise SafeError("dyd-token 生成为空")
        return "success", "已本地生成 dyd-token（CryptoJS 兼容 AES）", None

    def sign(self) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        result = http_json(
            SIGN_URL,
            method="POST",
            headers=self._auth_headers(with_json=False),
            cookies=self._cookies(),
            timeout=self.timeout,
            dry_run=self.dry_run,
        )
        if result["status"] != 200:
            raise SafeError("签到请求失败（HTTP {}）".format(result["status"]))
        payload = result["json"]
        if not isinstance(payload, dict):
            raise SafeError("签到响应不是 JSON 对象")
        message = business_message(payload)
        if payload.get("errno") == 0:
            results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
            constant = results.get("constant", "未知")
            reward = results.get("reward", "未知")
            score = results.get("score", "未知")
            detail = "签到成功；坚持天数 {}，本次奖励 {}，雪糕 {}".format(
                constant, reward, score
            )
            return "success", detail, results
        if is_already_complete(message):
            return "alreadyComplete", "今日已签到：{}".format(message or "业务提示已签"), None
        raise SafeError("签到失败：{}".format(message or "业务码非成功"))

    def say(self, content: str) -> Tuple[str, str, None]:
        result = http_json(
            SAY_URL,
            method="POST",
            headers=self._auth_headers(with_json=True),
            cookies=self._cookies(),
            body={
                "content": content,
                "image_urls": [],
                "at_userinfo_ids": [],
                "tag_title_list": [],
            },
            timeout=self.timeout,
            dry_run=self.dry_run,
        )
        if result["status"] != 200:
            raise SafeError("发言请求失败（HTTP {}）".format(result["status"]))
        payload = result["json"]
        if not isinstance(payload, dict):
            raise SafeError("发言响应不是 JSON 对象")
        message = business_message(payload)
        if payload.get("errno") == 0:
            return "success", "发言成功", None
        if any(marker in (message or "") for marker in ("已发言", "重复", "今日已")):
            return "alreadyComplete", "发言已完成：{}".format(message or "业务提示已完成"), None
        raise SafeError("发言失败：{}".format(message or "业务码非成功"))

    def personal_info(self) -> Tuple[str, str, Optional[Dict[str, Any]]]:
        result = http_json(
            INFO_URL,
            method="GET",
            headers=self._auth_headers(with_json=False),
            cookies=self._cookies(),
            timeout=self.timeout,
            dry_run=self.dry_run,
        )
        if result["status"] != 200:
            raise SafeError("获取个人信息失败（HTTP {}）".format(result["status"]))
        payload = result["json"]
        if not isinstance(payload, dict):
            raise SafeError("个人信息响应不是 JSON 对象")
        if payload.get("errno") != 0:
            message = business_message(payload) or "业务码非成功"
            raise SafeError("获取个人信息失败：{}".format(message))
        results = payload.get("results")
        if not isinstance(results, dict):
            raise SafeError("个人信息缺少 results")
        name = results.get("name")
        identity = compact(name, 64) if isinstance(name, str) else ""
        score = results.get("score", "未知")
        money = results.get("money", "未知")
        detail = "已读取公开资料；雪糕 {}，金币 {}".format(score, money)
        if identity:
            detail = "用户名 {}；{}".format(identity, detail)
        return "success", detail, {"identity": identity, "score": score, "money": money}


def run_account(
    runner: AccountRunner,
    account: Dict[str, str],
    actions: List[str],
    timeout: float,
    dry_run: bool,
) -> None:
    def parameter_check():
        if not account["username"] or not account["password"]:
            raise SafeError("用户名或密码为空")
        if not dry_run:
            ensure_pycryptodome()
            return "success", "账号本地格式检查通过；pycryptodome 可用", None
        try:
            ensure_pycryptodome()
            note = "pycryptodome 可用（预演不加密）"
        except SafeError:
            note = "预演未强制安装 pycryptodome；正式运行前请安装"
        return "success", "账号本地格式检查通过，内容不输出；{}".format(note), None

    runner.stage(1, "参数检查", parameter_check)

    stage_no = 2
    if dry_run:
        runner.skip(stage_no, "登录", "断网预演：不请求登录接口")
        stage_no += 1
        runner.skip(stage_no, "生成 dyd-token", "断网预演：不本地加密会话")
        stage_no += 1
        for action in actions:
            label = {"sign": "执行签到", "say": "发言", "info": "读取个人信息"}[action]
            runner.skip(stage_no, label, "断网预演：不请求业务接口")
            stage_no += 1
        runner.status = "dry-run"
        log(
            "账号 {}：无网络预演通过；未验证真实凭据或业务结果".format(
                runner.display()
            )
        )
        return

    client = DoyoudoClient(timeout, dry_run=False)
    critical_failed = False

    def login_stage():
        return client.login(account["username"], account["password"])

    runner.stage(stage_no, "登录", login_stage)
    stage_no += 1

    def token_stage():
        return client.build_dyd_token()

    runner.stage(stage_no, "生成 dyd-token", token_stage)
    stage_no += 1

    for action in actions:
        if action == "sign":

            def sign_stage():
                return client.sign()

            try:
                runner.stage(stage_no, "执行签到", sign_stage)
            except SafeError:
                critical_failed = True
        elif action == "say":

            def say_stage():
                content, note = published_text(False, timeout)
                log("账号 {} · 发言文案来源：{}".format(runner.number, note))
                state, detail, result = client.say(content)
                return state, detail, result

            try:
                runner.stage(stage_no, "发言", say_stage)
            except SafeError:
                critical_failed = True
        elif action == "info":

            def info_stage():
                state, detail, result = client.personal_info()
                if isinstance(result, dict):
                    identity = str(result.get("identity") or "").strip()
                    if identity:
                        runner.identity = identity
                        log("账号 {} 公开身份：{}".format(runner.number, identity))
                return state, detail, result

            try:
                runner.stage(stage_no, "读取个人信息", info_stage)
            except SafeError:
                # 读资料失败计入阶段失败；若同时请求了签到/发言，不单独拖垮账号成功态
                if "sign" not in actions and "say" not in actions:
                    critical_failed = True
        stage_no += 1

    if critical_failed:
        runner.status = "failure"
    elif runner.stats["success"] > 0:
        runner.status = "success"
    elif runner.stats["alreadyComplete"] > 0:
        runner.status = "alreadyComplete"
    else:
        runner.status = "success"


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
        "doyoudo_auto_sign.py",
        "candidate.py",
        "scripts/doyoudo_auto_sign.py",
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
    dry_setting = env("DOYOUDO_DRY_RUN", "0").lower()
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
            raise SafeError("DOYOUDO_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        actions = parse_actions(env("DOYOUDO_ACTIONS"))
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
