#!/usr/bin/env python3
# name: 恩山论坛签到
# cron: 39 12 * * *
#
# SPDX-License-Identifier: MIT
# Maintained standalone version of agluo/ql-script-hub/enshan_checkin.py at
# commit a8d39b97cb22c3ac657089014df754342b456ff6. Upstream copyright belongs
# to its contributors; this derivative remains distributed under the MIT License.

"""恩山论坛每日签到（多账号、失败闭合、支持完全断网预演）。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import gzip
import html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Dict, List, Optional, Sequence, Tuple


BASE_URL = "https://www.right.com.cn/forum"
SIGN_PAGE_URL = f"{BASE_URL}/erling_qd-sign_in.html"
SIGN_URL = f"{BASE_URL}/plugin.php?id=erling_qd:action&action=sign"
CREDIT_URLS = (
    f"{BASE_URL}/home.php?mod=spacecp&ac=credit",
    f"{BASE_URL}/home.php?mod=spacecp&ac=credit&showcredit=1",
    "https://www.right.com.cn/FORUM/home.php?mod=spacecp&ac=credit",
    "https://www.right.com.cn/FORUM/home.php?mod=spacecp&ac=credit&showcredit=1",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class HttpResponse:
    status: int
    text: str
    headers: object
    url: str


@dataclass
class AccountResult:
    account: int
    success: bool
    status: str
    message: str
    user: str = ""
    coin_before: Optional[int] = None
    coin_after: Optional[int] = None
    point_before: Optional[int] = None
    point_after: Optional[int] = None
    group: str = ""
    contribution: Optional[int] = None
    statistics: Optional[dict] = None


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def parse_accounts(raw: str) -> List[str]:
    """One non-empty account per line; no alternate account separators."""
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    return accounts


def validate_cookie(cookie: str, number: int) -> None:
    if "=" not in cookie or "&&" in cookie or any(ord(c) < 32 or ord(c) == 127 for c in cookie):
        raise ValueError(f"账号{number} Cookie 格式无效")
    cookie.encode("latin-1")


def clean_text(value: object, secret: str = "", limit: int = 180) -> str:
    text = html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if secret:
        text = text.replace(secret, "[REDACTED]")
        for part in secret.split(";"):
            if "=" in part:
                key, val = part.strip().split("=", 1)
                if val:
                    text = text.replace(val, f"[{key or 'COOKIE'}_REDACTED]")
    return text[:limit]


def mask_username(username: str, privacy: bool) -> str:
    # ENSHAN_PRIVACY_MODE remains accepted; public identities must be shown.
    return username


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.netloc != "www.right.com.cn":
            raise ValueError("拒绝向站外重定向发送凭据")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def first_match(text: str, patterns: Sequence[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return html.unescape(match.group(1)).strip()
    return None


def number_from(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.search(r"-?\d[\d,]*", value)
    return int(match.group(0).replace(",", "")) if match else None


class EnshanClient:
    def __init__(self, cookie: str, timeout: int, privacy: bool):
        self.cookie = cookie
        self.timeout = timeout
        self.privacy = privacy
        self.formhash: Optional[str] = None
        self.username = ""
        self.group = ""
        self.contribution = None
        self.opener = urllib.request.build_opener(SameOriginRedirect())

    def _merge_set_cookie(self, headers: object) -> None:
        values = getattr(headers, "get_all", lambda _name: [])("Set-Cookie") or []
        for header in values:
            parsed = SimpleCookie()
            try:
                parsed.load(header)
            except Exception:
                continue
            for key, morsel in parsed.items():
                self.cookie = self._upsert_cookie(self.cookie, f"{key}={morsel.value}")

    def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Cookie": self.cookie,
        }
        if extra_headers:
            headers.update(extra_headers)
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        raw = response.read(2 * 1024 * 1024 + 1)
        response.close()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("响应超过大小限制")
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                raw = compressed.read(8 * 1024 * 1024 + 1)
        elif encoding == "deflate":
            raw = zlib.decompressobj().decompress(raw, 8 * 1024 * 1024 + 1)
        charset = response.headers.get_content_charset() or "utf-8"
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("解压响应超过大小限制")
        text = raw.decode(charset, errors="replace")
        self._merge_set_cookie(response.headers)
        return HttpResponse(int(response.status), text, response.headers, response.geturl())

    @staticmethod
    def _upsert_cookie(base: str, new_pair: str) -> str:
        if "=" not in new_pair:
            return base
        new_key, new_value = new_pair.split("=", 1)
        entries: List[Tuple[str, str]] = []
        replaced = False
        for raw in base.split(";"):
            if "=" not in raw:
                continue
            key, value = raw.strip().split("=", 1)
            if key == new_key:
                entries.append((new_key, new_value))
                replaced = True
            else:
                entries.append((key, value))
        if not replaced:
            entries.append((new_key, new_value))
        return "; ".join(f"{key}={value}" for key, value in entries)

    @staticmethod
    def _extract_formhash(page: str) -> Optional[str]:
        return first_match(
            page,
            (
                r'name=["\']formhash["\'][^>]*value=["\']([0-9a-f]+)',
                r"action=logout(?:&amp;|&)formhash=([0-9a-f]+)",
            ),
        )

    @staticmethod
    def _rotl8(value: int, count: int) -> int:
        count &= 7
        return ((value << count) & 0xFF) | (value >> (8 - count))

    @staticmethod
    def _rotr8(value: int, count: int) -> int:
        count &= 7
        return (value >> count) | ((value << (8 - count)) & 0xFF)

    @classmethod
    def _decode_waf_cookie(cls, page: str) -> Optional[str]:
        array_match = re.search(r"oo\s*=\s*\[([^\]]+)\]", page)
        wi_match = re.search(r'setTimeout\("\w+\((\d+)\)"', page)
        if not wi_match:
            wi_match = re.search(r"\b\w+\((\d+)\)", page)
        loop1 = re.search(
            r"qo\s*=\s*(\d+);\s*do\{.*?oo\[qo\]=\(-oo\[qo\]\)&0xff;.*?"
            r"oo\[qo\]=\(\(\(oo\[qo\]>>(\d+)\)\|\(\(oo\[qo\]<<(\d+)\)&0xff\)\)\-(\d+)\)&0xff;.*?"
            r"\}\s*while\(--qo>=2\);",
            page,
            re.S,
        )
        loop2 = re.search(
            r"qo\s*=\s*(\d+);\s*do\s*\{[^}]*oo\[qo\]\s*=\s*\(oo\[qo\]\s*-\s*oo\[qo\s*-\s*1\]\)\s*&\s*0xff;[^}]*\}\s*while\s*\(\s*--\s*qo\s*>=\s*3\s*\)",
            page,
            re.S,
        )
        block = re.search(r"qo\s*=\s*1;\s*for\s*\(.*?\)\s*\{(.*?)\}\s*po\s*=", page, re.S)
        if not all((array_match, wi_match, loop1, loop2, block)):
            return None
        upper_match = re.search(r"qo\s*>\s*(\d+)\)\s*break", block.group(1))
        assign = re.search(r"oo\[qo\]\s*=\s*(.+?);", block.group(1), re.S)
        if not upper_match or not assign:
            return None
        adds = [int(x) for x in re.findall(r"\+\s*(\d+)", assign.group(1))]
        shifts = [int(a or b) for a, b in re.findall(r"<<\s*(\d+)|>>\s*(\d+)", assign.group(1))]
        if len(adds) < 2 or len(shifts) < 2:
            return None
        tokens = re.findall(r"0x[0-9a-fA-F]+|\d+", array_match.group(1))
        values = [
            (int(token, 16) if token.lower().startswith("0x") else int(token, 10)) & 0xFF
            for token in tokens
        ]
        if len(values) < 6:
            return None
        last = len(values) - 1
        start1, shift_r, shift_l, subtract = (int(x) for x in loop1.groups())
        index = min(start1, last - 1)
        while index >= 2:
            values[index] = (-values[index]) & 0xFF
            if shift_r + shift_l == 8:
                values[index] = (cls._rotr8(values[index], shift_r) - subtract) & 0xFF
            else:
                values[index] = (
                    (values[index] >> shift_r) | ((values[index] << shift_l) & 0xFF)
                )
                values[index] = (values[index] - subtract) & 0xFF
            index -= 1
        index = min(int(loop2.group(1)), last - 2)
        while index >= 3:
            values[index] = (values[index] - values[index - 1]) & 0xFF
            index -= 1
        upper = min(int(upper_match.group(1)), last - 1)
        for index in range(1, upper + 1):
            values[index] = cls._rotl8((values[index] + adds[0] + adds[1]) & 0xFF, shifts[0])
        mod_match = re.search(r"qo\s*%\s*(\d+)", page)
        modulus = int(mod_match.group(1)) if mod_match else 7
        wi = int(wi_match.group(1)) & 0xFF
        decoded = "".join(chr((values[i] ^ wi) & 0xFF) for i in range(1, last) if i % modulus)
        cookie_match = re.search(r"document\.cookie=['\"]([^'\"]+)['\"]", decoded)
        return cookie_match.group(1).split(";", 1)[0].strip() if cookie_match else None

    def login(self) -> Tuple[bool, str]:
        response = self.request("GET", SIGN_PAGE_URL, extra_headers={"Referer": f"{BASE_URL}/forum.php"})
        page = response.text if response.status == 200 else ""
        if re.search(r"oo\s*=\s*\[", page):
            waf_cookie = self._decode_waf_cookie(page)
            if waf_cookie:
                self.cookie = self._upsert_cookie(self.cookie, waf_cookie)
                response = self.request("GET", SIGN_PAGE_URL, extra_headers={"Referer": SIGN_PAGE_URL})
                page = response.text if response.status == 200 else ""
            else:
                page = ""
        self.formhash = self._extract_formhash(page)
        if not self.formhash:
            fallback = self.request("GET", f"{BASE_URL}/forum.php")
            if fallback.status != 200:
                return False, f"forum page returned HTTP {fallback.status}"
            page = fallback.text
            self.formhash = self._extract_formhash(page)
        if not self.formhash:
            return False, "login was not verified (formhash missing; Cookie may be expired)"
        # A logout action or non-zero Discuz UID is a positive authentication signal.
        authenticated = "action=logout" in page or bool(re.search(r"discuz_uid\s*=\s*['\"]?[1-9]\d*", page))
        return (True, "login verified") if authenticated else (False, "Cookie was not authenticated")

    def profile(self) -> Tuple[bool, Dict[str, Optional[object]], str]:
        last_status = 0
        for url in CREDIT_URLS:
            for attempt in range(3):
                response = self.request("GET", url, extra_headers={"Referer": f"{BASE_URL}/forum.php"})
                last_status = response.status
                if response.status == 200 and response.text:
                    username = first_match(
                        response.text,
                        (
                            r'访问我的空间["\']?[^>]*>([^<]+)</a>',
                            r'class=["\']vwmy["\'][^>]*>([^<]+)</a>',
                            r"欢迎您回来\s*[,，]\s*([^<\n]+)",
                            r"用户名[：:]\s*([^<\n]+)",
                        ),
                    )
                    coin = first_match(
                        response.text,
                        (r"恩山币\s*[:：]\s*</em>\s*([^<&\s]+)", r"恩山币\s*[:：]\s*([^<\s]+)"),
                    )
                    points = first_match(
                        response.text,
                        (r"积分\s*[:：]\s*</em>\s*([^<&\s]+)", r"积分\s*[:：]\s*([^<\s]+)"),
                    )
                    if username:
                        self.username = clean_text(username, self.cookie, len(username))
                    group = first_match(response.text, (r"用户组\s*[:：]\s*([^<\n]+)",))
                    self.group = clean_text(group, self.cookie, 60)
                    self.contribution = number_from(first_match(response.text, (
                        r"贡献\s*[:：]\s*</em>\s*([^<\s]+)", r"贡献\s*[:：]\s*(\d+)",
                    )))
                    parsed = {"coin": number_from(coin), "points": number_from(points)}
                    if parsed["coin"] is None and parsed["points"] is None:
                        continue
                    return True, parsed, "profile read"
                if response.status not in {429, 521, 500, 502, 503, 504}:
                    break
                if attempt < 2:
                    time.sleep(1 + attempt)
        return False, {"coin": None, "points": None}, f"credit page returned HTTP {last_status}"

    def checkin(self) -> Tuple[bool, str, str]:
        if not self.formhash:
            return False, "failed", "formhash is unavailable"
        response = self.request(
            "POST",
            SIGN_URL,
            {"formhash": self.formhash},
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://www.right.com.cn",
                "Referer": SIGN_PAGE_URL,
            },
        )
        if response.status != 200:
            return False, "failed", f"check-in returned HTTP {response.status}"
        message = ""
        status: object = None
        success: object = None
        try:
            payload = json.loads(response.text)
            if isinstance(payload, dict):
                message = clean_text(payload.get("message") or payload.get("msg"), self.cookie)
                status = payload.get("status")
                success = payload.get("success")
        except (ValueError, TypeError):
            message = clean_text(response.text, self.cookie)
        # Classify recognized business signals only; never print server messages or HTML.
        rejected = success is False or (status is not None and status not in (1, "1", "success", "ok"))
        negative = any(marker in message for marker in ("失败", "未签到", "尚未签到", "不能", "错误", "无效"))
        already = any(marker in message for marker in ("已签到", "已经签到", "今日已签"))
        explicit = success is True or status in (1, "1", "success", "ok")
        stated = any(marker in message for marker in ("签到成功", "打卡成功"))
        if already and not negative:
            return True, "already_checked_in", "今日已签到"
        if (explicit or stated) and not rejected and not negative:
            return True, "checked_in", "签到成功"
        return False, "failed", "响应未确认签到成功，请检查登录状态或接口变化"


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}")


def run_account(index: int, cookie: str, timeout: int, privacy: bool) -> AccountResult:
    client = EnshanClient(cookie, timeout, privacy)
    started = time.monotonic()
    stats = {"total": 4, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}

    def stage(number, title, action):
        begin = time.monotonic()
        log(f"账号{index} · 阶段{number}/4 {title} 开始")
        value = action()
        ok = value[0]
        if number == 3 and ok and value[1] == "already_checked_in":
            stats["alreadyComplete"] += 1
        else:
            stats["success" if ok else "failed"] += 1
        log(f"账号{index} · 阶段{number}/4 {title} {'✅ 完成' if ok else '❌ 失败'}，耗时{time.monotonic()-begin:.2f}秒")
        return value

    try:
        validate_cookie(cookie, index)
        login_ok, login_message = stage(1, "验证登录", client.login)
        if not login_ok:
            stats["skipped"] = 3
            result = AccountResult(index, False, "login_failed", "登录验证失败，请更新 Cookie")
        else:
            before_ok, before, _ = stage(2, "读取签到前余额", client.profile)
            if client.username:
                log(f"账号{index} · 用户：{client.username}")
            log(f"账号{index} · 恩山币 {before['coin']}，积分 {before['points']}，用户组 {client.group or '未知'}，贡献 {client.contribution}")
            success, status, message = stage(3, "每日签到", client.checkin)
            after_ok, after, _ = stage(4, "读取签到后余额", client.profile)
            log(f"账号{index} · 恩山币 {before['coin']} → {after['coin']}，积分 {before['points']} → {after['points']}")
            details = message
            if not before_ok or not after_ok:
                details += "；部分余额未能读取"
            result = AccountResult(index, success, status, details, client.username,
                                   before['coin'], after['coin'], before['points'], after['points'],
                                   client.group, client.contribution)
    except Exception:
        # Exception text may contain URL parameters, Cookie, or response contents.
        stats['failed'] += 1
        stats['skipped'] = max(0, 4 - sum(stats[k] for k in ('success', 'alreadyComplete', 'failed')))
        result = AccountResult(index, False, "request_error", "请求或解析失败；请检查网络、Cookie 或接口变化")
    stats['elapsedSeconds'] = round(time.monotonic() - started, 2)
    result.statistics = stats
    log(f"账号{index} · {result.message}；总任务4，成功{stats['success']}，已完成{stats['alreadyComplete']}，跳过{stats['skipped']}，失败{stats['failed']}，耗时{stats['elapsedSeconds']}秒")
    return result


def notify_summary(body: str, dry_run: bool) -> str:
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        return "全局关闭"
    if dry_run:
        log("通知预演：" + body.replace("\n", "；"))
        return "断网预演已生成通知，未调用通知网络"
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    send = None
    # Suppress untrusted notifier logs, which can contain delivery credentials.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            from notify import send
        except Exception:
            pass
        if not callable(send):
            for path in paths:
                if not path.is_file():
                    continue
                try:
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if callable(getattr(module, "send", None)):
                        send = module.send
                        break
                except Exception:
                    continue
        if not callable(send):
            return "通知模块不可用（保留业务退出码）"
        try:
            send("恩山论坛每日签到", body)
            return "通知已发送"
        except Exception:
            return "通知发送失败（保留业务退出码）"


def finish(results, dry_run, started, code, config_error=""):
    payload = {
        "application": "enshan", "dryRun": dry_run, "total": len(results),
        "succeeded": sum(r.success for r in results), "failed": sum(not r.success for r in results),
        "accounts": [asdict(r) for r in results],
        "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "configuration_error" if config_error else ("dry_run" if dry_run and code == 0 else ("success" if code == 0 else "partial_failure" if any(r.success for r in results) else "failure")),
        "exitCode": code, "elapsedSeconds": round(time.monotonic()-started, 2),
    }
    body = f"账号总数{payload['total']}，成功{payload['succeeded']}，失败{payload['failed']}；状态{payload['status']}"
    if config_error:
        body += "；" + config_error
    payload['notification'] = notify_summary(body, dry_run)
    log("----------------------------------------")
    log(body)
    totals = {k: sum((r.statistics or {}).get(k, 0) for r in results) for k in ('total','success','alreadyComplete','skipped','failed')}
    payload['taskStatistics'] = totals
    log(f"子任务统计：总数{totals['total']}，成功{totals['success']}，已完成{totals['alreadyComplete']}，跳过{totals['skipped']}，失败{totals['failed']}")
    log(f"完成时间 {payload['finishedAt']}；耗时{payload['elapsedSeconds']}秒；最终状态 {payload['status']}；{payload['notification']}")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print("SUMMARY_JSON=" + encoded)
    print("TASK_SUMMARY=" + encoded)
    return code


def main() -> int:
    started = time.monotonic()
    dry_run = env_bool("ENSHAN_DRY_RUN")
    log("==== 恩山论坛每日签到 ====")
    log(f"开始时间 {datetime.now().astimezone().isoformat(timespec='seconds')}；模式 {'断网预演' if dry_run else '正式签到'}")
    privacy = env_bool("ENSHAN_PRIVACY_MODE", env_bool("PRIVACY_MODE", True))
    accounts = []
    try:
        timeout = bounded_int("ENSHAN_HTTP_TIMEOUT", 20, 5, 120)
        delay_name = "ENSHAN_MAX_RANDOM_DELAY" if "ENSHAN_MAX_RANDOM_DELAY" in os.environ else "MAX_RANDOM_DELAY"
        max_delay = bounded_int(delay_name, 0, 0, 3600)
        accounts = parse_accounts(os.getenv("ENSHAN_COOKIE", os.getenv("enshan_cookie", "")))
        if not accounts:
            raise ValueError("ENSHAN_COOKIE 未配置，请每行填写一个完整 Cookie")
    except ValueError:
        log(f"账号数 {len(accounts)}；❌ 配置错误，请检查 Cookie 格式、超时和延迟范围")
        return finish([], dry_run, started, 2, "配置错误，请按契约检查环境变量")
    log(f"账号数 {len(accounts)}；凭据已隐藏；官方公开昵称直接展示")
    if dry_run:
        results = []
        for i in range(1, len(accounts)+1):
            for n, title in enumerate(("登录验证", "读取签到前余额", "每日签到", "读取签到后余额"), 1):
                log(f"账号{i} · 阶段{n}/4 {title} ⏭️ 断网预演跳过，耗时0秒")
            stats = dict(total=4, success=0, alreadyComplete=0, skipped=4, failed=0, elapsedSeconds=0)
            try:
                validate_cookie(accounts[i-1], i)
                results.append(AccountResult(i, True, "dry_run", "仅验证配置，未验证真实业务", statistics=stats))
            except (ValueError, UnicodeError):
                results.append(AccountResult(i, False, "configuration_error", "Cookie 格式无效", statistics=stats))
            log(f"账号{i} · 总任务4，成功0，已完成0，跳过4，失败0，耗时0秒")
        ok = all(r.success for r in results)
        if ok:
            print(f"DRY_RUN_OK: validated {len(accounts)} account(s); no network requests or state changes were made")
        return finish(results, True, started, 0 if ok else 2)
    if max_delay and env_bool("RANDOM_SIGNIN", True):
        delay = random.randint(0, max_delay)
        log(f"随机启动延迟 {delay}秒")
        time.sleep(delay)
    results = [run_account(i, cookie, timeout, privacy) for i, cookie in enumerate(accounts, 1)]
    return finish(results, False, started, 0 if all(r.success for r in results) else 1)


def handler(event, context):
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
