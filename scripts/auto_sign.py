#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 天使动漫签到打工
# cron: 31 9 * * *
#
# 来源：Mashiro-Sorata/TSDM-Automatic_SIGN dist/V1.0/Auto_Sign.py（MIT）
# https://github.com/Mashiro-Sorata/TSDM-Automatic_SIGN
# 提交：78403f4904f78b08d8945db9e2cbc9134bda2b32
# 相关：dist/V1.0/_data_init.py、source/V1.0/_data_init.py（端点与请求头内联）
# SPDX-License-Identifier: MIT
#
# MIT License
#
# Copyright (c) 2017 SO_RA
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
"""天使动漫（TSDM）每日签到与打工（青龙维护版）。

功能清点（相对上游 Auto_Sign.py + _data_init.py）：
- 校验登录态并展示公开昵称
- 每日 dsu_paulsign 签到（含已签到判断；默认发言模式 qdmode=1）
- 可选 np_cliworkdz 打工：点击广告满 6 次后领取天使币（默认开启，对齐上游 mission=True）
- 移除硬编码账号密码、交互验证码、pickle/_data 私有文件、QQ pgv 探测与落盘 Cookie
- 改为环境变量 Cookie 认证；端点与请求头内联，默认站点 https://www.tsdm39.net
- 增加换行多账号、TSDM_DRY_RUN 断网预演、超时、业务成功核验、
  时间轴日志、TASK_SUMMARY、青龙脱敏通知与任一账号失败非零退出

TSDM_COOKIE（必填）：浏览器登录天使动漫后，从开发者工具网络面板本站请求头复制
完整 Cookie；每个非空行一个账号；可选 备注|Cookie（仅按第一个 | 分割）。
TSDM_BASE_URL：论坛根地址，默认 https://www.tsdm39.net
TSDM_ENABLE_WORK：是否执行打工，默认 1（开启）；0/false/off 关闭
TSDM_SIGN_MODE：签到模式，默认 1（发言，使用 todaysay）；3 为不发言
TSDM_MOOD：签到心情代码，默认 kx
TSDM_LOCAL_TEXT：签到发言本地兜底文字；未设置时使用内置短句
TSDM_WORK_DELAY：打工点击间隔秒数，默认 2，范围 1..8
TSDM_TIMEOUT：单次请求超时秒数，默认 20，范围 5..60
TSDM_DRY_RUN=1：完全断网预演，不发起网络请求，也不调用一言。
建议 Cron：30 9 * * *。不打印 Cookie、Token、会话值或原始响应。
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
        _ql_notify_identities = ('ba4842f946bbd44b', 'scripts/auto_sign.py', 'auto_sign.py', 'auto_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import gzip
import http.cookiejar
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "天使动漫签到打工"
CATALOG_ID = "ba4842f946bbd44b"
DEFAULT_BASE = "https://www.tsdm39.net"
DRY_RUN_ENV = "TSDM_DRY_RUN"
COOKIE_ENV = "TSDM_COOKIE"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
HITOKOTO_MAX = 16384
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
STATES = ("success", "alreadyComplete", "skipped", "failure")
LOCAL_SAY_FALLBACK = [
    "Happy day again",
    "Working hard, and make it!",
    "Another peaceful day on TSDM",
]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
)


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), message), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def redact(text: str, secrets: List[str]) -> str:
    out = clean_text(text)
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 4:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", out)
    out = re.sub(
        r"(?i)(cookie|token|authorization|session|password|auth)=([^;\s&]+)",
        r"\1=[敏感值]",
        out,
    )
    return "".join(ch for ch in out if ch.isprintable())[:240]


def resolve_bool(name: str, default: bool) -> bool:
    raw = env(name)
    if not raw:
        return default
    low = raw.lower()
    if low in TRUE_VALUES:
        return True
    if low in FALSE_VALUES:
        return False
    raise SafeError("{} 须为开关值（1/0、true/false）".format(name))


def resolve_timeout() -> float:
    raw = env("TSDM_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("TSDM_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("TSDM_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_work_delay() -> float:
    raw = env("TSDM_WORK_DELAY")
    if not raw:
        return 2.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("TSDM_WORK_DELAY 须为数字秒数") from exc
    if value < 1 or value > 8:
        raise SafeError("TSDM_WORK_DELAY 须在 1 到 8 秒之间")
    return value


def resolve_base_url() -> str:
    raw = env("TSDM_BASE_URL", DEFAULT_BASE) or DEFAULT_BASE
    parts = urllib.parse.urlsplit(raw)
    if parts.scheme != "https" or not parts.netloc:
        raise SafeError("TSDM_BASE_URL 须为 https:// 开头的论坛根地址")
    return raw.rstrip("/")


def resolve_sign_mode() -> str:
    raw = env("TSDM_SIGN_MODE", "1") or "1"
    if raw not in {"1", "3"}:
        raise SafeError("TSDM_SIGN_MODE 仅支持 1（发言）或 3（不发言）")
    return raw


def resolve_mood() -> str:
    raw = env("TSDM_MOOD", "kx") or "kx"
    if not re.fullmatch(r"[A-Za-z]{1,16}", raw):
        raise SafeError("TSDM_MOOD 须为字母心情代码，例如 kx")
    return raw


def load_accounts() -> List[Dict[str, str]]:
    raw = env(COOKIE_ENV)
    if not raw:
        alias = env("TSDM_COOKIES")
        if alias:
            raw = alias
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        label = ""
        cookie = text
        if "|" in text:
            label, cookie = text.split("|", 1)
            label = label.strip()
            cookie = cookie.strip()
        if not cookie or any(ord(ch) < 32 for ch in cookie):
            raise SafeError("第 {} 行 Cookie 无效或含控制字符".format(line_no))
        if "=" not in cookie:
            raise SafeError("第 {} 行不像有效 Cookie（缺少 name=value）".format(line_no))
        accounts.append(
            {
                "label": label or "账号{}".format(len(accounts) + 1),
                "cookie": cookie,
            }
        )
    if not accounts:
        raise SafeError(
            "请设置 {}，每个非空行一个账号 Cookie；可选 备注|Cookie".format(COOKIE_ENV)
        )
    return accounts


def join_url(base: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return "{}/{}".format(base.rstrip("/"), path.lstrip("/"))


class Client:
    def __init__(self, cookie: str, base: str, timeout: float) -> None:
        self.cookie = cookie
        self.base = base
        self.timeout = timeout
        self.host = urllib.parse.urlsplit(base).netloc.lower()
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def _headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.8",
            "User-Agent": UA,
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "Host": self.host,
            "Referer": referer or (self.base + "/"),
        }
        return headers

    def _decode(self, response: Any) -> str:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise SafeError("业务响应超过大小限制")
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                raw = zlib.decompress(raw, zlib.MAX_WBITS | 16)
        elif encoding == "deflate":
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                raw = zlib.decompress(raw)
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")

    def request(
        self,
        path: str,
        data: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        content_type_form: bool = False,
    ) -> str:
        url = join_url(self.base, path)
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.netloc.lower() != self.host:
            raise SafeError("拒绝非本站或非 HTTPS 业务请求")
        headers = self._headers(referer=referer)
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            if content_type_form:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return self._decode(response)
        except SafeError:
            raise
        except Exception as exc:
            raise SafeError("业务网络请求失败或超时") from exc


def extract_formhash(html: str) -> str:
    patterns = [
        r'name=["\']formhash["\']\s+value=["\']([^"\']+)["\']',
        r'value=["\']([^"\']+)["\']\s+name=["\']formhash["\']',
        r"formhash=([a-zA-Z0-9]{6,32})",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if match and re.fullmatch(r"[a-zA-Z0-9]{6,32}", match.group(1)):
            return match.group(1)
    raise SafeError("未取得有效表单令牌，请更新登录 Cookie")


def extract_nickname(html: str) -> Optional[str]:
    patterns = [
        r'title=["\']访问我的空间["\']>([^<]+)</a>',
        r'class=["\'][^"\']*vwmy[^"\']*["\'][^>]*>([^<]+)<',
        r"<strong[^>]*class=[\"'][^\"']*vwmy[^\"']*[\"'][^>]*>([^<]+)</strong>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if match:
            name = clean_text(re.sub(r"<[^>]+>", "", match.group(1)))
            if name and len(name) <= 64 and "http" not in name.lower():
                return name
    return None


def visible_text(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return clean_text(text)


def fetch_sign_say(dry_run: bool) -> str:
    """签到发言属于公开内容：先一言，失败再用本地文字。Dry-run 不请求一言。"""
    local = clean_text(env("TSDM_LOCAL_TEXT"))
    if not local:
        local = random.choice(LOCAL_SAY_FALLBACK)
    if len(local) > 280:
        local = LOCAL_SAY_FALLBACK[0]
    if dry_run:
        return local
    try:
        req = urllib.request.Request(
            HITOKOTO_URL,
            headers={"User-Agent": "Qinglong-TSDM", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(HITOKOTO_MAX + 1)
        if len(raw) > HITOKOTO_MAX:
            raise ValueError("oversized")
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        text = clean_text(obj.get("hitokoto"))
        author = clean_text(obj.get("from_who"))
        source = clean_text(obj.get("from"))
        if not text:
            raise ValueError("missing-text")
        if author and source:
            composed = "{} —— {}《{}》".format(text, author, source)
        elif source:
            composed = "{} ——《{}》".format(text, source)
        elif author:
            composed = "{} —— {}".format(text, author)
        else:
            composed = text
        if len(composed) > 280:
            raise ValueError("overlong-text")
        log("签到发言：一言内容及出处已取得（不输出正文）")
        return composed
    except Exception:
        log("{} 签到发言：一言不可用或内容不合规，使用本地文字".format(ICONS["warning"]))
        return local


def parse_sign_result(html: str) -> str:
    text = visible_text(html)
    if any(token in text for token in ("您今日已经签到", "今天已签到", "已经签到过")):
        return "alreadyComplete"
    if "恭喜你签到成功" in text or "签到成功" in text:
        return "success"
    if any(token in text for token in ("已经过了签到时间段", "签到时间还没有到", "不在签到时间")):
        raise SafeError("当前不在签到时间段")
    if "未定义操作" in text:
        raise SafeError("签到失败：表单令牌可能失效，请更新 Cookie")
    raise SafeError("签到未返回明确成功标志，请检查登录状态")


def parse_work_click(html: str) -> Tuple[str, Optional[int]]:
    text = clean_text(html)
    if "请先登录" in text:
        raise SafeError("打工失败：Cookie 已失效")
    wait = re.search(r"您需要等待(.+?)后即可进行", text)
    if wait or "必须与上一次间隔" in text or "刚刚完成过" in text:
        return "alreadyComplete", None
    if "不要作弊" in text or "作弊" in text:
        raise SafeError("打工失败：触发防作弊判定")
    if "服务器负荷较重" in text:
        raise SafeError("打工失败：服务器负荷较重")
    digits = re.fullmatch(r"\d+", text)
    if digits:
        value = int(digits.group(0))
        if value > 1_000_000_000:
            raise SafeError("打工失败：检测到异常时间戳判定")
        return "progress", value
    raise SafeError("打工点击响应无法确认")


def parse_work_reward(html: str) -> str:
    text = visible_text(html)
    if "成功领取了奖励天使币" in text or "恭喜，您已经成功领取了奖励" in text:
        return "success"
    if "不要作弊" in text or "作弊" in text:
        raise SafeError("领取奖励失败：防作弊判定")
    if "请先登录" in text:
        raise SafeError("领取奖励失败：Cookie 已失效")
    if "已经领取" in text or "已经成功领取" in text:
        return "alreadyComplete"
    raise SafeError("领取奖励未返回明确成功标志")


def empty_stats() -> Dict[str, int]:
    return {key: 0 for key in ("total",) + STATES}


def run_account(
    account: Dict[str, str],
    index: int,
    *,
    dry_run: bool,
    base: str,
    timeout: float,
    enable_work: bool,
    sign_mode: str,
    mood: str,
    work_delay: float,
) -> Dict[str, Any]:
    stats = empty_stats()
    started = time.monotonic()
    display = account["label"]
    secrets = [account["cookie"]]

    def stage(number: int, name: str, action) -> str:
        before = time.monotonic()
        stats["total"] += 1
        log("账号 {}（{}）阶段 {}：{}".format(index, display, number, name))
        try:
            result = action()
            if result not in STATES:
                raise SafeError("内部状态异常")
            stats[result] += 1
            icon = ICONS[result]
            label = {
                "success": "成功",
                "alreadyComplete": "已完成",
                "skipped": "跳过",
                "failure": "失败",
            }[result]
            log(
                "账号 {} 阶段 {}：{} {}，耗时 {:.2f} 秒".format(
                    index, number, icon, label, time.monotonic() - before
                )
            )
            return result
        except Exception as exc:
            stats["failure"] += 1
            message = str(exc) if isinstance(exc, SafeError) else "响应解析或本地处理失败"
            log(
                "账号 {} 阶段 {}：{} {}，耗时 {:.2f} 秒".format(
                    index,
                    number,
                    ICONS["failure"],
                    redact(message, secrets),
                    time.monotonic() - before,
                )
            )
            return "failure"

    if dry_run:
        stage(1, "模拟登录态校验（无网络）", lambda: "skipped")
        stage(2, "模拟每日签到（无状态变更）", lambda: "skipped")
        if enable_work:
            stage(3, "模拟打工点击与领奖（无状态变更）", lambda: "skipped")
        else:
            stage(3, "打工未开启", lambda: "skipped")
    else:
        client = Client(account["cookie"], base, timeout)
        state: Dict[str, Any] = {}

        def check_login() -> str:
            html = client.request("forum.php")
            nick = extract_nickname(html)
            logged_in = bool(nick) or ("action=logout" in html)
            if not logged_in:
                raise SafeError("登录态无效，请更新 Cookie")
            if nick:
                # 直接展示官方昵称，便于核对账号
                log("账号 {} 官方昵称：{}".format(index, nick))
                account["label"] = nick
            state["logged_in"] = True
            return "success"

        login_result = stage(1, "校验登录态并读取公开昵称", check_login)
        if login_result == "success":

            def do_sign() -> str:
                page = client.request(
                    "plugin.php?id=dsu_paulsign:sign",
                    referer=join_url(base, "forum.php"),
                )
                formhash = extract_formhash(page)
                todaysay = ""
                if sign_mode == "1":
                    todaysay = fetch_sign_say(False)
                payload = {
                    "formhash": formhash,
                    "qdxq": mood,
                    "qdmode": sign_mode,
                    "todaysay": todaysay,
                    "fastreply": "1",
                }
                result_html = client.request(
                    "plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1",
                    data=payload,
                    referer=join_url(base, "plugin.php?id=dsu_paulsign:sign"),
                    content_type_form=True,
                )
                outcome = parse_sign_result(result_html)
                if outcome == "success":
                    reward = re.search(r"恭喜你签到成功[!！]?([^<\n]{0,80})", visible_text(result_html))
                    if reward:
                        log("账号 {} 签到奖励摘要：{}".format(index, clean_text(reward.group(1))[:80]))
                return outcome

            stage(2, "每日签到", do_sign)

            if enable_work:

                def do_work() -> str:
                    # 上游先访问任务帖，再请求打工插件
                    client.request(
                        "forum.php?mod=viewthread&tid=321479",
                        referer=join_url(base, "forum.php"),
                    )
                    work_path = "plugin.php?id=np_cliworkdz:work"
                    client.request(work_path, referer=join_url(base, "forum.php"))
                    click_count = 0
                    for round_idx in range(8):
                        html = client.request(
                            work_path,
                            data={"act": "clickad"},
                            referer=join_url(base, work_path),
                            content_type_form=True,
                        )
                        status, value = parse_work_click(html)
                        if status == "alreadyComplete":
                            log("账号 {} 打工：今日已完成或仍在冷却".format(index))
                            return "alreadyComplete"
                        if value is not None:
                            click_count = value
                            log("账号 {} 打工点击进度：{}/6".format(index, min(click_count, 6)))
                            if click_count >= 6:
                                break
                        time.sleep(work_delay + random.uniform(0, 0.5))
                        if round_idx >= 7 and click_count < 6:
                            raise SafeError("打工点击未达到 6 次")
                    reward_html = client.request(
                        work_path,
                        data={"act": "getcre"},
                        referer=join_url(base, work_path),
                        content_type_form=True,
                    )
                    return parse_work_reward(reward_html)

                stage(3, "广告打工并领取天使币", do_work)
            else:
                stage(3, "打工未开启", lambda: "skipped")
        else:
            stage(2, "每日签到", lambda: "skipped")
            stage(3, "打工" if enable_work else "打工未开启", lambda: "skipped")

    elapsed = time.monotonic() - started
    log(
        "账号 {} 统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，"
        "跳过 {skipped}，失败 {failure}；耗时 {elapsed:.2f} 秒".format(
            index, elapsed=elapsed, **stats
        )
    )
    account_ok = stats["failure"] == 0
    return {
        "ok": account_ok,
        "stats": stats,
        "label": account.get("label") or display,
        "elapsed": elapsed,
    }


def notify_enabled() -> bool:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    return switch == "auto" and env("QINGLONG_NOTIFY") != ""


def send_notification(body: str, dry_run: bool) -> str:
    if env("QINGLONG_NOTIFY", "auto").lower() in FALSE_VALUES:
        return "已关闭"
    if dry_run:
        log("{} 断网预演通知：{}".format(ICONS["skipped"], body))
        return "已模拟（无网络）"
    code = """import importlib.util, os, pathlib, sys
try:
    import notify
except ImportError:
    notify = None
if notify is None:
    roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for root in roots:
        if not root:
            continue
        path = pathlib.Path(root) / 'notify.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('notify', path)
            notify = importlib.util.module_from_spec(spec)
            sys.path.insert(0, root)
            spec.loader.exec_module(notify)
            break
if notify is None:
    sys.exit(3)
notify.send(sys.argv[1], sys.argv[2])
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code, TITLE, body],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return "已发送"
        if result.returncode == 3:
            for root in [env("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts"]:
                path = Path(root) / "sendNotify.js" if root else None
                if path and path.is_file():
                    js = (
                        "Promise.resolve(require(process.argv[1])"
                        ".sendNotify(process.argv[2], process.argv[3]))"
                        ".catch(() => process.exit(1))"
                    )
                    js_result = subprocess.run(
                        ["node", "-e", js, str(path), TITLE, body],
                        capture_output=True,
                        timeout=30,
                    )
                    return "已发送" if js_result.returncode == 0 else "发送失败"
        return "不可用或发送失败"
    except Exception:
        return "不可用或发送失败"


def main() -> int:
    started = time.monotonic()
    log("========== {} ==========".format(TITLE))
    log("开始时间：{}".format(clock()))
    config_error = False
    dry_run = False
    accounts: List[Dict[str, str]] = []
    results: List[Dict[str, Any]] = []
    try:
        dry_run = resolve_bool(DRY_RUN_ENV, False)
        accounts = load_accounts()
        base = resolve_base_url()
        timeout = resolve_timeout()
        enable_work = resolve_bool("TSDM_ENABLE_WORK", True)
        sign_mode = resolve_sign_mode()
        mood = resolve_mood()
        work_delay = resolve_work_delay()
    except SafeError as exc:
        config_error = True
        log("{} 配置错误：{}".format(ICONS["failure"], exc))
        base = DEFAULT_BASE
        timeout = float(DEFAULT_TIMEOUT)
        enable_work = True
        sign_mode = "1"
        mood = "kx"
        work_delay = 2.0

    mode_text = "断网预演" if dry_run else "正式"
    log("运行模式：{}；账号数：{}".format(mode_text, len(accounts)))
    if not config_error:
        log(
            "站点：{}；打工：{}；签到模式：{}".format(
                base, "开启" if enable_work else "关闭", sign_mode
            )
        )
        for index, account in enumerate(accounts, 1):
            results.append(
                run_account(
                    account,
                    index,
                    dry_run=dry_run,
                    base=base,
                    timeout=timeout,
                    enable_work=enable_work,
                    sign_mode=sign_mode,
                    mood=mood,
                    work_delay=work_delay,
                )
            )

    failed_accounts = len(accounts) if config_error else sum(1 for item in results if not item["ok"])
    passed_accounts = 0 if config_error else len(results) - failed_accounts
    if config_error:
        status = "configuration-error"
        final_status = "CONFIG-ERROR"
    elif dry_run and failed_accounts == 0:
        status = "dry-run"
        final_status = "DRY-RUN"
    elif failed_accounts == 0:
        status = "success"
        final_status = "SUCCESS"
    elif passed_accounts == 0:
        status = "failure"
        final_status = "FAILURE"
    else:
        status = "partial-failure"
        final_status = "PARTIAL-FAILURE"

    totals = empty_stats()
    for item in results:
        for key in totals:
            totals[key] += item["stats"][key]

    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}{}".format(
        status,
        len(accounts),
        passed_accounts,
        failed_accounts,
        "；预演未验证业务" if dry_run and not config_error else "",
    )
    notification = send_notification(body, dry_run=dry_run or config_error)

    log("----------------------------------------")
    log(body)
    log(
        "子任务统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，"
        "跳过 {skipped}，失败 {failure}".format(**totals)
    )
    log("总耗时：{:.2f} 秒；通知：{}".format(time.monotonic() - started, notification))
    log("完成时间：{}；最终状态：{}".format(clock(), final_status))
    summary = {
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": len(accounts),
        "successfulAccounts": passed_accounts,
        "failedAccounts": failed_accounts,
        "tasks": totals,
        "notification": notification,
        "catalogId": CATALOG_ID,
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    if not config_error and failed_accounts == 0:
        print("DRY_RUN_OK" if dry_run else "天使动漫签到打工成功", flush=True)
    return 1 if config_error or failed_accounts else 0


if __name__ == "__main__":
    sys.exit(main())
