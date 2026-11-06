#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: T00ls每日签到
# cron: 21 1 * * *
#
# 来源：strivewu0813/t00ls-auto-sign t00ls_sign.py（MIT）
# https://github.com/strivewu0813/t00ls-auto-sign
# 分支：main
# 提交：69845b654f18d11125389a5eeb291acd171d5de2
# 原路径：t00ls_sign.py
# SPDX-License-Identifier: MIT
#
# Copyright (c) strivewu0813 / t00ls-auto-sign contributors
# 本维护版沿用上游 MIT 许可，保留原作者版权与归属声明。
#
"""T00ls（www.t00ls.com）每日签到（青龙维护版）。

功能清点（相对上游 t00ls_sign.py）：
- 用户名 + 密码(MD5) + 可选安全提问登录，或 Cookie 登录
- 查询会员资料（sign_today / sign_times / TuBi / TCV / username）
- 提交每日签到（formhash + ajax-sign），幂等识别今日已签
- 可选零点换日残留检测与重试（不默认长时间阻塞时可通过环境变量关闭）
- 可选补签（ajax-busign，每次约扣 20 TuBi）：默认关闭，需显式开启
- 多账号：T00LS_ACCOUNTS 每个非空行一个账号
- T00LS_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 标准库 urllib 实现 HTTP；超时与业务成功核验；任一账号失败非零退出

官方接口参考：https://www.t00ls.com/api.html
  POST /login.json
  GET  /members-profile.json
  POST /ajax-sign.json
  POST /ajax-busign.json（可选补签）

建议 Cron：10 0 * * *（北京时间零点后）。不打印密码、Cookie、Token 或原始响应。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_identities = ('06364e72aec0863e', 'scripts/t00ls_sign.py', 't00ls_sign.py', 't00ls_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPSHandler
from http.cookiejar import CookieJar

SCRIPT_NAME = "T00ls每日签到"
CATALOG_ID = "06364e72aec0863e"
SCRIPT_FILENAME = "candidate.py"
DEFAULT_BASE_URL = "https://www.t00ls.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 20
MAX_RESPONSE_BYTES = 256 * 1024
DRY_RUN_ENV = "T00LS_DRY_RUN"
ACCOUNTS_ENV = "T00LS_ACCOUNTS"
TIMEOUT_ENV = "T00LS_TIMEOUT"
BASE_URL_ENV = "T00LS_BASE_URL"
AUTO_BU_SIGN_ENV = "T00LS_AUTO_BU_SIGN"
FORCE_BU_SIGN_ENV = "T00LS_FORCE_BU_SIGN"
BU_WITHIN_ENV = "T00LS_BU_SIGN_WITHIN_DAYS"
STALE_RETRIES_ENV = "T00LS_STALE_RETRIES"
STALE_WAIT_ENV = "T00LS_STALE_WAIT"
STATE_FILE_ENV = "T00LS_STATE_FILE"

CST = timezone(timedelta(hours=8))

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

LOGIN_HINTS = {
    "1": "密码为空",
    "2": "用户名为空",
    "3": "用户名或密码不对，或安全提问不匹配",
    "4": "用户名、密码或安全提问不正确",
    "5": "同一 IP 连续登录失败过多，请约 15 分钟后再试",
    "login_invalid": "用户名或密码（MD5）不对",
    "login_question_invalid": "安全提问编号或答案不匹配",
    "login_answer_invalid": "安全提问答案错误",
    "login_strike": "密码错误次数过多，账号被临时锁定",
    "login_seccheck": "站点要求验证码，请改用 Cookie 登录",
    "login_nonexistence": "账号不存在",
    "wrongaction": "接口未收到 action=login，请确认 base_url 为 https://www.t00ls.com",
}


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


class AccountAuth:
    """单个账号的登录材料（不打印敏感字段）。"""

    def __init__(
        self,
        kind: str,
        username: str = "",
        password: str = "",
        password_md5: str = "",
        question_id: int = 0,
        question_answer: str = "",
        cookie: str = "",
        label: str = "",
    ) -> None:
        self.kind = kind  # "password" | "cookie"
        self.username = username
        self.password = password
        self.password_md5 = password_md5
        self.question_id = question_id
        self.question_answer = question_answer
        self.cookie = cookie
        self.label = label or username or "cookie账号"

    def resolved_password_md5(self) -> str:
        if self.password_md5.strip():
            return self.password_md5.strip().lower()
        if self.password:
            text = self.password
            if re.fullmatch(r"[0-9a-fA-F]{32}", text):
                return text.lower()
            return hashlib.md5(text.encode("utf-8")).hexdigest()
        return ""


def _now() -> datetime:
    return datetime.now()


def _now_cst() -> datetime:
    return datetime.now(CST)


def _ts(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%H:%M:%S")


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def today_cst() -> str:
    return _now_cst().strftime("%Y-%m-%d")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def log_stage(index: int, title: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    log(f"阶段{index} {title}{suffix}")


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_dry_run() -> bool:
    return _env_truthy(DRY_RUN_ENV)


def _http_timeout() -> int:
    raw = os.getenv(TIMEOUT_ENV, "").strip()
    if not raw:
        return HTTP_TIMEOUT
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{TIMEOUT_ENV} 须为整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError(f"{TIMEOUT_ENV} 须在 5 到 120 秒之间")
    return value


def _base_url() -> str:
    return (os.getenv(BASE_URL_ENV, "") or DEFAULT_BASE_URL).strip().rstrip("/") or DEFAULT_BASE_URL


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _previous_day(day: str) -> str:
    try:
        return (datetime.strptime(day, "%Y-%m-%d").date() - timedelta(days=1)).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def days_between(earlier: Optional[str], later: str) -> Optional[int]:
    try:
        start = datetime.strptime(str(earlier), "%Y-%m-%d").date()
        end = datetime.strptime(str(later), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (end - start).days


def normalize_cookie(raw: str) -> str:
    cookie = (raw or "").strip()
    if not cookie:
        return ""
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    cookie = " ".join(line.strip() for line in cookie.splitlines() if line.strip())
    parts: List[str] = []
    for chunk in cookie.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        if chunk not in parts:
            parts.append(chunk)
    return "; ".join(parts)


def _looks_like_cookie(line: str) -> bool:
    text = line.strip()
    if text.lower().startswith("cookie:"):
        return True
    if "|" in text and not (("=" in text) and (";" in text or text.count("=") >= 2)):
        # username|password 形态优先按密码登录解析
        first = text.split("|", 1)[0].strip()
        if first and "=" not in first:
            return False
    if "=" in text and (";" in text or text.count("=") >= 1):
        # 单段 name=value 也允许作为 Cookie
        if "|" not in text:
            return True
        # 含竖线但仍像 Cookie（少见）时：首段含 =
        return "=" in text.split("|", 1)[0]
    return False


def parse_account_line(line: str, line_no: int) -> AccountAuth:
    text = line.strip()
    if not text:
        raise ValueError(f"第 {line_no} 行为空")

    if _looks_like_cookie(text):
        cookie = normalize_cookie(text)
        if not cookie:
            raise ValueError(f"第 {line_no} 行 Cookie 无效")
        return AccountAuth(kind="cookie", cookie=cookie, label=f"账号{line_no}")

    # 用户名|密码 或 用户名|密码|提问编号|答案
    # 默认仅在首个竖线处分割，密码原文完整保留；
    # 若末两段可明确解析为 questionid(0-7)+answer，则从右侧拆出提问。
    if "|" not in text:
        raise ValueError(
            f"第 {line_no} 行无法识别：请使用「用户名|密码」或完整 Cookie"
        )
    parts = text.split("|")
    username = parts[0].strip()
    if not username:
        raise ValueError(f"第 {line_no} 行用户名为空")

    question_id = 0
    question_answer = ""
    if (
        len(parts) >= 4
        and parts[-2].strip().isdigit()
        and int(parts[-2].strip()) in range(0, 8)
    ):
        question_id = int(parts[-2].strip())
        question_answer = parts[-1]
        password = "|".join(parts[1:-2]).strip()
    else:
        password = text.split("|", 1)[1].strip()

    if not password:
        raise ValueError(f"第 {line_no} 行密码为空")

    password_md5 = ""
    if re.fullmatch(r"[0-9a-fA-F]{32}", password):
        password_md5 = password.lower()
        password = ""

    return AccountAuth(
        kind="password",
        username=username,
        password=password,
        password_md5=password_md5,
        question_id=question_id,
        question_answer=question_answer,
        label=username,
    )


def parse_accounts(raw: str) -> List[AccountAuth]:
    accounts: List[AccountAuth] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text, line_no))
    return accounts


def _read_accounts_raw() -> Tuple[str, str]:
    primary = os.getenv(ACCOUNTS_ENV)
    if primary is not None and primary.strip() != "":
        return primary, ACCOUNTS_ENV

    # 兼容：整段 Cookie 多行
    cookie = os.getenv("T00LS_COOKIE")
    if cookie is not None and cookie.strip() != "":
        return cookie, "T00LS_COOKIE"

    # 兼容单账号：用户名 + 密码 / MD5
    username = (os.getenv("T00LS_USERNAME") or "").strip()
    password = os.getenv("T00LS_PASSWORD")
    password_md5 = os.getenv("T00LS_PASSWORD_MD5")
    if username and (
        (password is not None and str(password).strip() != "")
        or (password_md5 is not None and str(password_md5).strip() != "")
    ):
        qid = (os.getenv("T00LS_QUESTION_ID") or "0").strip() or "0"
        answer = os.getenv("T00LS_QUESTION_ANSWER") or ""
        secret = (password_md5 if password_md5 and str(password_md5).strip() else password) or ""
        if qid != "0" or str(answer).strip():
            line = f"{username}|{secret}|{qid}|{answer}"
        else:
            line = f"{username}|{secret}"
        return line, "T00LS_USERNAME"

    return "", ""


def collect_strings(obj: Any, out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []
    if isinstance(obj, dict):
        for value in obj.values():
            collect_strings(value, out)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            collect_strings(value, out)
    elif obj is not None:
        out.append(str(obj))
    return out


def _login_hint(message: str) -> str:
    if message in LOGIN_HINTS:
        return LOGIN_HINTS[message]
    lowered = message.lower()
    for pattern, hint in (
        ("failedlogin", LOGIN_HINTS["5"]),
        ("plswait", "站点要求稍后再试"),
        ("seccheck", LOGIN_HINTS["login_seccheck"]),
    ):
        if pattern in lowered:
            return hint
    return ""


# --------------------------------------------------------------------------- #
# 本地状态（可选，仅用于漏签判断与补签限频；默认不启用自动补签）
# --------------------------------------------------------------------------- #
class State:
    VERSION = 1

    def __init__(self, path: str, account_key: str) -> None:
        self.path = path
        self.account_key = account_key
        self.root: Dict[str, Any] = {"version": self.VERSION, "accounts": {}}

    def load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self.root = data
                if "accounts" not in self.root or not isinstance(self.root["accounts"], dict):
                    # 兼容上游单账号扁平结构
                    if "last_sign_date" in self.root:
                        self.root = {
                            "version": self.VERSION,
                            "accounts": {"default": {
                                k: self.root.get(k)
                                for k in (
                                    "last_sign_date",
                                    "last_sign_times",
                                    "last_tubi",
                                    "bu_sign_dates",
                                )
                                if k in self.root
                            }},
                        }
                    else:
                        self.root.setdefault("accounts", {})
        except (OSError, ValueError) as exc:
            log(f"{ICON_WARN} 状态文件读取失败（按首次运行处理）：{type(exc).__name__}")

    def _bucket(self) -> Dict[str, Any]:
        accounts = self.root.setdefault("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
            self.root["accounts"] = accounts
        bucket = accounts.setdefault(self.account_key, {})
        if not isinstance(bucket, dict):
            bucket = {}
            accounts[self.account_key] = bucket
        return bucket

    def get(self, key: str, default: Any = None) -> Any:
        return self._bucket().get(key, default)

    def save(self) -> None:
        if not self.path:
            return
        try:
            directory = os.path.dirname(os.path.abspath(self.path))
            if directory and not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            self.root["version"] = self.VERSION
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(self.root, handle, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(temp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as exc:
            log(f"{ICON_WARN} 状态文件写入失败：{type(exc).__name__}")

    def record_signed(self, today: str, sign_times: Optional[int], tubi: Optional[int]) -> None:
        bucket = self._bucket()
        bucket["last_sign_date"] = today
        if sign_times is not None:
            bucket["last_sign_times"] = sign_times
        if tubi is not None:
            bucket["last_tubi"] = tubi

    def bu_sign_dates(self) -> List[str]:
        dates = self._bucket().get("bu_sign_dates")
        return list(dates) if isinstance(dates, list) else []

    def bu_sign_done_today(self, today: str) -> bool:
        return today in self.bu_sign_dates()

    def mark_bu_sign(self, today: str) -> None:
        dates = [d for d in self.bu_sign_dates() if d != today]
        dates.append(today)
        self._bucket()["bu_sign_dates"] = dates[-30:]

    def detect_missed_days(self, today: str, sign_times: Optional[int]) -> Tuple[Optional[int], str]:
        last_sign = self.get("last_sign_date")
        last_times = _as_int(self.get("last_sign_times"))
        if not last_sign:
            return None, "首次运行，没有基线"
        elapsed = days_between(str(last_sign), today)
        if elapsed is None:
            return None, "状态日期无法解析"
        if elapsed <= 0:
            return 0, "今天已经记过账"
        gap_days = elapsed - 1
        if sign_times is None or last_times is None:
            return None, "站点未返回累计签到次数，无法安全判断漏签"
        delta = sign_times - last_times
        if delta < 0:
            return None, "累计签到次数异常变小"
        counter_missed = elapsed - delta
        missed = max(0, min(counter_missed, gap_days))
        detail = (
            f"相隔 {elapsed} 天，期间累计签到 +{delta}"
            f"（counter 漏 {max(0, counter_missed)}，记录漏 {gap_days}）"
        )
        return missed, detail


# --------------------------------------------------------------------------- #
# HTTP 客户端
# --------------------------------------------------------------------------- #
class T00lsClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar), HTTPSHandler())
        self.formhash: Optional[str] = None
        self.username: str = ""
        self._extra_cookie = ""

    def _headers(self, form: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.base_url + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "close",
        }
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        if self._extra_cookie:
            headers["Cookie"] = self._extra_cookie
        return headers

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, str]] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        url = self.base_url + path
        body = urlencode(data or {}).encode("utf-8") if data is not None else None
        last_error: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                req = Request(
                    url,
                    data=body,
                    headers=self._headers(form=data is not None),
                    method=method.upper(),
                )
                with self.opener.open(req, timeout=self.timeout) as resp:
                    raw = resp.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("响应过大，已中止读取")
                    charset = resp.headers.get_content_charset() or "utf-8"
                    text = raw.decode(charset, errors="replace")
                    # 跟随跳转后的最终域名
                    final_url = getattr(resp, "geturl", lambda: url)()
                    if final_url and final_url.startswith("http"):
                        try:
                            from urllib.parse import urlsplit

                            parts = urlsplit(final_url)
                            new_origin = f"{parts.scheme}://{parts.netloc}"
                            if new_origin.rstrip("/") != self.base_url:
                                log(
                                    f"{ICON_WARN} 接口域名跳转到 {new_origin}，已自动改用新域名"
                                )
                                self.base_url = new_origin.rstrip("/")
                        except Exception:
                            pass
                    try:
                        payload = json.loads(text) if text.strip() else {}
                    except Exception as exc:
                        raise RuntimeError("接口未返回 JSON（可能被 CDN/WAF 拦截）") from exc
                    if not isinstance(payload, dict):
                        raise RuntimeError("接口返回结构异常")
                    return payload
            except HTTPError as exc:
                last_error = exc
                if exc.code >= 500 and attempt < retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError(f"HTTP {exc.code}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                reason = getattr(exc, "reason", None)
                name = type(reason).__name__ if reason is not None else type(exc).__name__
                raise RuntimeError(f"网络错误: {name}") from exc
            except TimeoutError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError("请求超时") from exc
            except Exception as exc:
                if isinstance(exc, RuntimeError):
                    raise
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError(f"请求失败: {type(exc).__name__}") from exc
        raise RuntimeError(f"请求连续失败: {type(last_error).__name__ if last_error else 'unknown'}")

    def login_with_password(self, auth: AccountAuth) -> None:
        password_md5 = auth.resolved_password_md5()
        if not auth.username.strip():
            raise SafeError("用户名为空")
        if not password_md5:
            raise SafeError("未配置密码或 password_md5")
        payload = self._request(
            "POST",
            "/login.json",
            data={
                "action": "login",
                "username": auth.username,
                "password": password_md5,
                "questionid": str(auth.question_id),
                "answer": auth.question_answer,
            },
        )
        if str(payload.get("status")) != "success":
            message = str(payload.get("message") or "login_failed")
            hint = _login_hint(message)
            raise RuntimeError(
                f"登录失败：{message}" + (f"（{hint}）" if hint else "")
            )
        self.formhash = (str(payload.get("formhash") or "")).strip() or None
        self.username = auth.username

    def login_with_cookie(self, raw_cookie: str) -> None:
        cookie = normalize_cookie(raw_cookie)
        if not cookie:
            raise SafeError("Cookie 为空")
        self._extra_cookie = cookie
        info = self.profile()
        self.username = str(info.get("username") or self.username or "cookie用户")

    def profile(self) -> Dict[str, Any]:
        payload = self._request("GET", "/members-profile.json")
        if str(payload.get("status")) != "success":
            message = str(payload.get("message") or "profile_failed")
            if message == "loginfirst":
                raise RuntimeError("Cookie 已失效或未登录（loginfirst），请重新获取 Cookie")
            raise RuntimeError(f"获取用户信息失败：{message}")
        info = payload.get("memberinfo") or {}
        if not isinstance(info, dict):
            raise RuntimeError("用户信息字段异常")
        if not self.formhash:
            self.formhash = (str(info.get("formhash") or "")).strip() or None
        if not self.username:
            self.username = str(info.get("username") or "")
        return info

    @staticmethod
    def is_signed_today(info: Dict[str, Any]) -> bool:
        return str(info.get("sign_today", "0")).strip() in ("1", "true", "True")

    def _submit_sign(self) -> Tuple[bool, bool, str]:
        """返回 (ok, already, message)。"""
        if not self.formhash:
            self.profile()
        if not self.formhash:
            raise RuntimeError("无法获取 formhash，签到中止")
        payload = self._request(
            "POST",
            "/ajax-sign.json",
            data={"formhash": self.formhash, "signsubmit": "true"},
        )
        strings = " ".join(collect_strings(payload)).lower()
        if "alreadysign" in strings:
            return True, True, "今日已签到"
        if str(payload.get("status")).lower() == "success":
            return True, False, "签到成功"
        return False, False, str(payload.get("message") or "sign_failed")

    def sign(self) -> Tuple[bool, bool, str]:
        ok, already, message = self._submit_sign()
        if ok:
            return ok, already, message
        if "wrongsubmit" in message.lower() or "formhash" in message.lower():
            log(f"{ICON_WARN} formhash 可能失效，刷新后重试一次")
            self.formhash = None
            self.profile()
            ok, already, message = self._submit_sign()
            if ok:
                return ok, already, message
        raise RuntimeError(f"签到失败：{message}")

    def bu_sign(self) -> Tuple[bool, bool, str]:
        if not self.formhash:
            self.profile()
        if not self.formhash:
            raise RuntimeError("无法获取 formhash，补签中止")
        payload = self._request(
            "POST",
            "/ajax-busign.json",
            data={"formhash": self.formhash, "signsubmit": "true"},
        )
        strings = " ".join(collect_strings(payload)).lower()
        if "alreadysign" in strings:
            return True, True, "今日已签到"
        if "wrongbusubmit" in strings:
            return False, False, "没有可补签的日期"
        if str(payload.get("status")).lower() == "success":
            return True, False, "补签请求已提交"
        return False, False, str(payload.get("message") or "bu_sign_failed")


def looks_like_stale_sign_today(state: State, info: Dict[str, Any], today: str) -> bool:
    if state.get("last_sign_date") != _previous_day(today):
        return False
    last_times = _as_int(state.get("last_sign_times"))
    now_times = _as_int(info.get("sign_times"))
    if last_times is None or now_times is None:
        return False
    return now_times == last_times


def resolve_stale_sign_today(
    client: T00lsClient,
    retries: int,
    wait: float,
) -> Dict[str, Any]:
    log(
        f"{ICON_WARN} sign_today=1 但累计次数与昨天相同，站点可能尚未换日；"
        f"将等待 {wait:g} 秒后重试签到，最多 {retries} 次"
    )
    for attempt in range(1, retries + 1):
        if wait > 0:
            time.sleep(wait)
        ok, already, message = client.sign()
        if ok and not already:
            log(f"{ICON_OK} 站点已换日：第 {attempt} 次尝试签到成功")
            time.sleep(1.0)
            refreshed = client.profile()
            if not T00lsClient.is_signed_today(refreshed):
                raise RuntimeError("签到接口返回成功，但 sign_today 仍为 0")
            return refreshed
        log(f"  第 {attempt}/{retries} 次仍返回已签（{message}）")
    raise RuntimeError("站点似乎尚未换日，本次未能签到")


def try_bu_sign(
    client: T00lsClient,
    state: State,
    today: str,
    info: Dict[str, Any],
    within_days: int,
    force: bool,
) -> Optional[str]:
    if state.bu_sign_done_today(today) and not force:
        log(f"{ICON_SKIP} 今日已尝试过补签，跳过（避免重复消耗 TuBi）")
        return None

    sign_times = _as_int(info.get("sign_times"))
    if force:
        log(f"{ICON_WARN} 强制补签：不检查是否漏签，每次约消耗 20 TuBi")
    else:
        missed, detail = state.detect_missed_days(today, sign_times)
        if missed is None:
            log(f"{ICON_SKIP} 本次不补签：{detail}")
            return None
        if missed < 1:
            log(f"{ICON_SKIP} 未检测到漏签，无需补签（{detail}）")
            return None
        if missed > within_days:
            log(
                f"{ICON_WARN} 检测到漏签 {missed} 天，超过上限 {within_days}，跳过补签"
            )
            return None
        log(f"检测到漏签 {missed} 天（{detail}），尝试补签（约消耗 20 TuBi）")

    # 先落盘再请求，避免同一天重复扣费
    state.mark_bu_sign(today)
    state.save()

    tubi_before = _as_int(info.get("extcredits2"))
    try:
        ok, already, message = client.bu_sign()
    except Exception as exc:
        line = f"补签失败：{exc}"
        log(f"{ICON_WARN} {line}")
        return line

    time.sleep(1.0)
    try:
        refreshed = client.profile()
        info.update(refreshed)
    except Exception as exc:
        log(f"{ICON_WARN} 补签后复核失败：{type(exc).__name__}")
        refreshed = {}
    tubi_after = _as_int(refreshed.get("extcredits2")) if refreshed else None
    cost = ""
    if tubi_before is not None and tubi_after is not None:
        cost = f"，TuBi {tubi_before} -> {tubi_after}"

    if ok and not already:
        line = f"补签已提交（{message}{cost}）"
        log(f"{ICON_OK} {line}")
        return line
    line = f"补签未成功：{message}{cost}"
    log(f"{ICON_WARN} {line}")
    return line


# --------------------------------------------------------------------------- #
# 通知
# --------------------------------------------------------------------------- #
def _notify_global_mode() -> str:
    raw = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in {"1", "true", "yes", "on"}:
        return "enabled"
    if raw in {"0", "false", "no", "off"}:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
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
    candidates = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        f"scripts/{SCRIPT_FILENAME}",
        "scripts/t00ls_sign.py",
        "t00ls_sign.py",
        SCRIPT_NAME,
        "t00ls",
    }
    sel_l = sel.lower()
    if sel in candidates or sel_l in {c.lower() for c in candidates}:
        return True
    if sel.endswith("*") and SCRIPT_FILENAME.startswith(sel[:-1]):
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
    search_dirs = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, body: str) -> str:
    if not _should_notify():
        log("通知: 已跳过（全局开关或脚本选择未启用）")
        return "skipped"
    sender = _load_notify_send()
    if sender is None:
        log(f"{ICON_WARN} 通知: 未找到 notify.py，已跳过发送")
        return "unavailable"
    try:
        sender(title, body)
        log(f"{ICON_OK} 通知: 已发送")
        return "sent"
    except Exception as exc:
        log(f"{ICON_WARN} 通知发送失败: {type(exc).__name__}")
        return "failed"


def emit_machine(out: Dict[str, Any]) -> None:
    safe = {
        k: v
        for k, v in out.items()
        if k not in {"cookie", "password", "password_md5", "raw", "formhash"}
    }
    print(json.dumps(safe, ensure_ascii=False, default=str), flush=True)


def _state_path() -> str:
    custom = os.getenv(STATE_FILE_ENV, "").strip()
    if custom:
        return custom
    # 默认写在脚本同目录旁的缓存名，避免无路径时跳过漏签判断；用户可显式关闭补签
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "t00ls-state.json")


def _account_state_key(auth: AccountAuth) -> str:
    if auth.kind == "cookie":
        digest = hashlib.sha256(auth.cookie.encode("utf-8")).hexdigest()[:16]
        return f"cookie:{digest}"
    return f"user:{auth.username}"


def run_account_dry(index: int, total: int, auth: AccountAuth) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    identity = auth.label or label
    log(f"—— {label}/{total} 开始（预演）——")
    stats = {
        "total": 4,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": identity,
        "ok": True,
        "status": "success",
        "message": "预演通过",
        "resultCode": "DRY_RUN",
        "elapsedMs": 0,
    }

    log_stage(1, "校验账号凭据")
    if auth.kind == "cookie":
        if not auth.cookie:
            stats["failed"] += 1
            result.update(ok=False, status="failure", message="Cookie 为空", resultCode="NO_AUTH")
            log(f"  {ICON_FAIL} Cookie 为空")
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} Cookie 登录材料已提供（不输出值）")
    else:
        if not auth.username or not auth.resolved_password_md5():
            stats["failed"] += 1
            result.update(
                ok=False,
                status="failure",
                message="用户名或密码缺失",
                resultCode="NO_AUTH",
            )
            log(f"  {ICON_FAIL} 用户名或密码缺失")
        else:
            stats["success"] += 1
            q = f"，安全提问编号={auth.question_id}" if auth.question_id else ""
            log(f"  {ICON_OK} 密码登录材料已提供（用户名将在正式运行时展示）{q}")

    if result["ok"]:
        log_stage(2, "预演登录", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 POST {_base_url()}/login.json 或使用 Cookie")

        log_stage(3, "预演查询资料", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 GET {_base_url()}/members-profile.json")

        log_stage(4, "预演提交签到", "跳过真实网络请求")
        stats["skipped"] += 1
        log(f"  {ICON_SKIP} 断网预演：将 POST {_base_url()}/ajax-sign.json")
        if _env_truthy(AUTO_BU_SIGN_ENV) or _env_truthy(FORCE_BU_SIGN_ENV):
            log(f"  {ICON_SKIP} 断网预演：补签开关已开，正式运行才会调用 /ajax-busign.json")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats
    emit_machine(
        {
            "result": result["resultCode"],
            "report": result["message"],
            "account": index,
            "dry_run": True,
        }
    )
    log(
        f"{result['identity']} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(
    index: int,
    total: int,
    auth: AccountAuth,
    timeout: int,
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始 ——")
    stats = {
        "total": 4,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": auth.label or label,
        "ok": False,
        "status": "failure",
        "message": "",
        "resultCode": "ERROR",
        "elapsedMs": 0,
        "stats": stats,
    }
    machine: Dict[str, Any] = {"result": "ERROR", "report": "", "account": index}
    today = today_cst()
    state = State(_state_path(), _account_state_key(auth))
    state.load()
    client = T00lsClient(_base_url(), timeout)
    info: Dict[str, Any] = {}

    try:
        log_stage(1, "登录")
        t1 = _now()
        if auth.kind == "cookie":
            client.login_with_cookie(auth.cookie)
        else:
            client.login_with_password(auth)
        info = client.profile()
        identity = str(info.get("username") or client.username or label)
        result["identity"] = identity
        stage_ms = int((_now() - t1).total_seconds() * 1000)
        stats["success"] += 1
        log(f"  {ICON_OK} 登录成功，用户：{identity}（耗时 {stage_ms}ms）")

        log_stage(2, "查询签到状态")
        t2 = _now()
        signed = T00lsClient.is_signed_today(info)
        sign_times = info.get("sign_times")
        tubi = info.get("extcredits2")
        tcv = info.get("extcredits1")
        stage_ms = int((_now() - t2).total_seconds() * 1000)
        stats["success"] += 1
        bits = [f"今日已签={'是' if signed else '否'}"]
        if sign_times is not None:
            bits.append(f"累计={sign_times}")
        if tubi is not None:
            bits.append(f"TuBi={tubi}")
        if tcv is not None:
            bits.append(f"TCV={tcv}")
        log(f"  {ICON_OK} {'，'.join(bits)}（耗时 {stage_ms}ms）")

        log_stage(3, "提交每日签到")
        t3 = _now()
        already = False
        action = ""
        if signed:
            stale_retries = _as_int(os.getenv(STALE_RETRIES_ENV, "3")) or 0
            stale_wait = float(os.getenv(STALE_WAIT_ENV, "30") or 30)
            if stale_retries > 0 and looks_like_stale_sign_today(state, info, today):
                info = resolve_stale_sign_today(client, stale_retries, stale_wait)
                already = False
                action = "签到成功（换日重试）"
                stats["success"] += 1
                log(f"  {ICON_OK} {action}")
            else:
                already = True
                action = "今日已签到"
                stats["alreadyComplete"] += 1
                log(f"  {ICON_DONE} {action}")
        else:
            ok, already, message = client.sign()
            time.sleep(1.0)
            try:
                refreshed = client.profile()
                if refreshed:
                    info = refreshed
            except Exception as exc:
                log(f"  {ICON_WARN} 签到后复核失败（不影响结论）：{type(exc).__name__}")
            if not already and not T00lsClient.is_signed_today(info):
                raise RuntimeError("接口返回成功，但 sign_today 仍为 0，请手动确认")
            if already:
                action = "今日已签到"
                stats["alreadyComplete"] += 1
                log(f"  {ICON_DONE} {action}（接口 alreadysign）")
            else:
                action = "签到成功" if ok else message
                stats["success"] += 1
                log(f"  {ICON_OK} {action}")

        stage_ms = int((_now() - t3).total_seconds() * 1000)
        log(f"  签到阶段耗时 {stage_ms}ms")

        log_stage(4, "可选补签")
        t4 = _now()
        auto_bu = _env_truthy(AUTO_BU_SIGN_ENV)
        force_bu = _env_truthy(FORCE_BU_SIGN_ENV)
        bu_line = None
        if (auto_bu or force_bu) and T00lsClient.is_signed_today(info):
            within = _as_int(os.getenv(BU_WITHIN_ENV, "3")) or 3
            bu_line = try_bu_sign(
                client, state, today, info, within_days=within, force=force_bu
            )
            if bu_line and "失败" in bu_line:
                stats["failed"] += 1
            elif bu_line and "已提交" in bu_line:
                stats["success"] += 1
            else:
                stats["skipped"] += 1
        else:
            stats["skipped"] += 1
            log(f"  {ICON_SKIP} 补签未启用（默认关闭，避免消耗 TuBi）")
        stage_ms = int((_now() - t4).total_seconds() * 1000)
        log(f"  补签阶段耗时 {stage_ms}ms")

        if T00lsClient.is_signed_today(info):
            state.record_signed(
                today, _as_int(info.get("sign_times")), _as_int(info.get("extcredits2"))
            )
            state.save()

        msg_bits = [action]
        if bu_line:
            msg_bits.append(bu_line)
        if info.get("extcredits2") is not None:
            msg_bits.append(f"TuBi={info.get('extcredits2')}")
        result["ok"] = True
        result["status"] = "success"
        result["message"] = "；".join(msg_bits)
        result["resultCode"] = "ALREADY" if already and not bu_line else "SIGNED"
        machine = {
            "result": result["resultCode"],
            "report": result["message"],
            "account": index,
            "username": result["identity"],
            "sign_times": info.get("sign_times"),
            "tubi": info.get("extcredits2"),
        }
    except SafeError as exc:
        stats["failed"] += 1
        result["message"] = str(exc)[:200]
        result["resultCode"] = "NO_AUTH"
        machine = {"result": "NO_AUTH", "report": result["message"], "account": index}
        log(f"  {ICON_FAIL} {result['message']}")
    except Exception as exc:
        stats["failed"] += 1
        result["message"] = str(exc)[:200]
        result["resultCode"] = "ERROR"
        machine = {"result": "ERROR", "report": result["message"], "account": index}
        log(f"  {ICON_FAIL} {result['message']}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    emit_machine(machine)
    log(
        f"{result['identity']} 统计: 总任务={stats['total']} "
        f"成功={stats['success']} 已完成={stats['alreadyComplete']} "
        f"跳过={stats['skipped']} 失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def main() -> int:
    task_start = _now()
    dry = _is_dry_run()
    mode = "dry-run" if dry else "live"

    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")
    log(f"签到日期（北京时间）: {today_cst()}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        timeout = _http_timeout()
        raw, source_name = _read_accounts_raw()
        if not raw:
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{ICON_FAIL} 未配置必填环境变量 {ACCOUNTS_ENV}")
            log(
                "获取方式: 在 https://www.t00ls.com 注册并登录本人账号。"
                f"密码登录行格式「用户名|密码」或「用户名|密码|提问编号|答案」；"
                "也可整行粘贴浏览器 Cookie。"
                f"写入青龙环境变量 {ACCOUNTS_ENV}，每个非空行一个账号。"
            )
            log("账号数量: 0")
            emit_machine({"result": "NO_AUTH", "report": f"未配置必填环境变量 {ACCOUNTS_ENV}"})
        else:
            log(f"凭据来源: {source_name}（内容已脱敏）")
            try:
                accounts = parse_accounts(raw)
            except ValueError as exc:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 账号解析失败: {exc}")
                accounts = []
                emit_machine({"result": "ERROR", "report": str(exc)})

            log(f"账号数量: {len(accounts)}")
            if not config_error and not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 未解析到任何有效账号")
                emit_machine({"result": "NO_AUTH", "report": "未解析到任何有效账号"})

            if not config_error:
                total = len(accounts)
                for idx, auth in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, auth)
                    else:
                        ar = run_account_live(idx, total, auth, timeout=timeout)
                    account_results.append(ar)

                failed = [a for a in account_results if not a.get("ok")]
                succeeded = [a for a in account_results if a.get("ok")]
                if failed and succeeded:
                    summary_status = "partial-failure"
                    exit_code = 1
                elif failed:
                    summary_status = "failure"
                    exit_code = 1
                else:
                    summary_status = "dry-run" if dry else "success"
                    exit_code = 0
    except SafeError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 配置错误: {exc}")
        emit_machine({"result": "ERROR", "report": str(exc)})
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 未处理异常: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        emit_machine({"result": "ERROR", "report": f"脚本运行异常（{type(exc).__name__}）"})

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(int((a.get("stats") or {}).get("success") or 0) for a in account_results)
    sub_fail = sum(int((a.get("stats") or {}).get("failed") or 0) for a in account_results)
    sub_skip = sum(int((a.get("stats") or {}).get("skipped") or 0) for a in account_results)
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0) for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {_iso(task_end)}")

    if dry and not config_error:
        event = "dry-run"
    elif config_error:
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        f"任务: {SCRIPT_NAME}",
        f"模式: {mode}",
        f"事件: {event}",
        f"账号总数: {total_accounts if not config_error else 0}",
        f"成功: {ok_count}",
        f"失败: {fail_count}",
        f"状态: {summary_status}",
    ]
    for a in account_results:
        lines.append(
            f"- {a.get('identity')}: {a.get('status')} / {str(a.get('message', ''))[:120]}"
        )
    body = "\n".join(lines)
    notify_status = send_notification(SCRIPT_NAME, body)
    log(f"通知状态: {notify_status}")

    final_status = summary_status
    if exit_code == 0 and dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        log(f"{ICON_OK} 最终状态：预演完成")
        final_status = "dry-run-success"
    elif exit_code == 0:
        log(f"{ICON_OK} 最终状态：成功")
    elif config_error:
        log(f"{ICON_FAIL} 最终状态：配置错误")
    else:
        log(f"{ICON_FAIL} 最终状态：失败")

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "task": SCRIPT_NAME,
        "mode": mode,
        "status": final_status if exit_code == 0 else summary_status,
        "exitCode": exit_code,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSucceeded": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notifyStatus": notify_status,
        "finishedAt": _iso(task_end),
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
