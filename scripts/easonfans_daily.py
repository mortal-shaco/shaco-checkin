#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 神经研究所每日任务
# cron: 0 20 * * *
"""神经研究所（easonfans）每日签到、转盘、答题与可选留言维护版。

上游来源：https://github.com/OneGuoZexin/easonfans-daily-automation
上游文件：easonfans_daily.py、quiz_tools.py
上游提交：75c0e63af5dbad6e886e9c69fa9e16600775c07b
许可证：MIT

本维护版移除 Playwright/Chromium、本机浏览器资料目录、交互式登录等待与
题库文件安装依赖，改为纯 HTTPS + Cookie 实现；公开默认仍关闭留言。

必填：
  EASONFANS_COOKIE：浏览器登录 https://www.easonfans.com/forum/ 后，从开发者
  工具网络面板本站请求头复制完整 Cookie；每个非空行一个账号。

可选：
  EASONFANS_BASE_URL：论坛根地址，默认 https://www.easonfans.com/forum/
  EASONFANS_QUIZ_BANK：题库 JSON（[{"question","answer"},...]）或题库纯文本
  EASONFANS_MESSAGE_COUNT：留言条数，默认 0（关闭）；正整数才开启
  EASONFANS_MESSAGE_DELAY：留言间隔秒数，默认 25
  EASONFANS_EMOJI_INDEX：签到心情/表情序号，默认 0
  EASONFANS_LOCAL_TEXT：留言本地兜底文字；未设置时使用论坛表情码
  EASONFANS_TIMEOUT：单次请求超时秒数，默认 20
  EASONFANS_DRY_RUN=1：完全断网预演

MIT License

Copyright (c) 2026 OneGuoZexin

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
"""
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
        _ql_notify_identities = ('99686155ae0324e2', 'scripts/easonfans_daily.py', 'easonfans_daily.py', 'easonfans_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import html
import http.cookiejar
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TITLE = "神经研究所每日任务"
CATALOG_ID = "99686155ae0324e2"
DEFAULT_BASE = "https://www.easonfans.com/forum/"
DRY_RUN_ENV = "EASONFANS_DRY_RUN"
COOKIE_ENV = "EASONFANS_COOKIE"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
MOOD_IDS = ["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
BEIJING = timezone(timedelta(hours=8))
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
MAX_BYTES = 2 * 1024 * 1024


class TaskError(Exception):
    pass


def now_clock() -> str:
    return datetime.now(BEIJING).strftime("%H:%M:%S")


def now_full() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, icon: str = "") -> None:
    prefix = f"{icon} " if icon else ""
    print(f"[{now_clock()}] {prefix}{message}", flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUE:
        return True
    if value in FALSE:
        return False
    return default


def env_int(name: str, default: int, minimum: int = 0, maximum: int = 10**6) -> int:
    raw = env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise TaskError(f"{name} 必须是整数") from exc
    if value < minimum or value > maximum:
        raise TaskError(f"{name} 必须在 {minimum} 至 {maximum} 之间")
    return value


def compact(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def strip_tags(source: str) -> str:
    source = re.sub(r"(?is)<script\b.*?</script>", " ", source)
    source = re.sub(r"(?is)<style\b.*?</style>", " ", source)
    return compact(html.unescape(re.sub(r"(?s)<[^>]+>", " ", source)), 50000)


def timeout_seconds() -> float:
    raw = env("EASONFANS_TIMEOUT")
    if not raw:
        return 20.0
    try:
        return min(60.0, max(3.0, float(raw)))
    except ValueError:
        return 20.0


def normalize_base(url: str) -> str:
    text = (url or DEFAULT_BASE).strip() or DEFAULT_BASE
    if not text.endswith("/"):
        text += "/"
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme != "https" or not parsed.hostname:
        raise TaskError("EASONFANS_BASE_URL 必须是 HTTPS 论坛根地址")
    host = parsed.hostname.lower()
    if host not in {"www.easonfans.com", "easonfans.com"}:
        raise TaskError("EASONFANS_BASE_URL 仅允许 easonfans.com 域名")
    return urllib.parse.urlunsplit(("https", host, parsed.path or "/forum/", "", ""))


def allowed_host(base: str) -> str:
    return urllib.parse.urlsplit(base).hostname or "www.easonfans.com"


# ---- quiz matching (from upstream quiz_tools.py, MIT) ----

def _number(match: re.Match) -> str:
    digits = dict(zip("零〇一二两三四五六七八九", [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
    s = match.group()
    if not any(c in s for c in "十百千"):
        return "".join(str(digits[c]) for c in s)
    total = current = 0
    for c in s:
        if c in digits:
            current = digits[c]
        else:
            total += (current or 1) * {"十": 10, "百": 100, "千": 1000}[c]
            current = 0
    return str(total + current)


def quiz_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[零〇一二两三四五六七八九十百千]+(?=[个届年月日号场首次张岁人])", _number, text)
    if re.fullmatch(r"[零〇一二两三四五六七八九十百千]+", text):
        text = _number(re.match(r".+", text))
    return "".join(c for c in text if c.isalnum())


def parse_bank_text(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    pending = None
    for line_no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip().lstrip("\ufeff")
        if not s or re.match(r"^[一二三四五六七八九十]+、", s):
            continue
        s = re.sub(r"^(?:\d+|[a-z])[.、．]\s*", "", s).strip()
        if not s:
            continue
        if pending and re.match(r"^答(?:案)?[：:]", s):
            s = "—" + re.sub(r"^答(?:案)?[：:]\s*", "", s)
        pair = re.split(r"\s*[—–]+\s*", s, maxsplit=1)
        if len(pair) == 2 and not pair[0] and pending:
            question, answer = pending[1], pair[1]
            pending = None
        elif len(pair) == 2 and pair[0] and pair[1]:
            question, answer = pair
        else:
            boundary = max(s.rfind("？"), s.rfind("?"))
            pair = [s[:boundary], s[boundary + 1 :].strip()] if boundary >= 0 else [s]
            if (
                len(pair) == 2
                and quiz_normalize(pair[1])
                and not re.search(r"错啦|已收录|啊喂|讲真", pair[1])
                and not pair[1].startswith(("（", "("))
            ):
                question, answer = pair[0] + "？", pair[1]
            else:
                if pending:
                    issues.append({"kind": "unparsed", "line": pending[0], "text": pending[1]})
                pending = (line_no, s)
                continue
        if pending:
            issues.append({"kind": "unparsed", "line": pending[0], "text": pending[1]})
            pending = None
        corrected = re.search(r"正确答案[是为：:]\s*(.+)", answer)
        if corrected:
            answer = corrected.group(1).rstrip("!！。 ")
        if re.search(r"错啦|是错的|不确定|待确认", answer):
            issues.append({"kind": "uncertain", "line": line_no, "text": s})
            continue
        rows.append({"question": question.strip(), "answer": answer.strip(), "line": line_no})
    if pending:
        issues.append({"kind": "unparsed", "line": pending[0], "text": pending[1]})
    unique: List[Dict[str, Any]] = []
    seen = set()
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = (quiz_normalize(row["question"]), quiz_normalize(row["answer"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        groups.setdefault(key[0], []).append(row)
    for entries in groups.values():
        if len(entries) > 1:
            issues.append({"kind": "conflict", "entries": entries})
    return unique, issues


def question_score(question: str, candidate: str) -> float:
    a, b = quiz_normalize(question), quiz_normalize(candidate)
    if a == b:
        return 1.0
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return 0.0
    if ("不" in a or "没" in a) != ("不" in b or "没" in b):
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def answer_matches(answer: str, option: str) -> bool:
    option = re.sub(r"^[A-Da-d][.、:：)）]\s*", "", option.strip())
    target = quiz_normalize(option)
    if not target:
        return False
    variants = [answer, re.sub(r"[（(].*?[）)]", "", answer)]
    variants += re.split(r"\s*/\s*", variants[1])
    for variant in variants:
        value = quiz_normalize(variant)
        if value == target:
            return True
        if value.isdigit() and re.fullmatch(re.escape(value) + r"(?:年|个|场|首|次|张|人|岁|号|届)", target):
            return True
    return False


def choose_option(question: str, options: Sequence[str], bank: Sequence[Dict[str, Any]]) -> Optional[int]:
    scored = [
        (question_score(question, variant), row)
        for row in bank
        for variant in [row["question"]] + row["question"].split("/")
    ]
    if not scored:
        return None
    best = max(s for s, _ in scored)
    if best < 0.88:
        return None
    top = [r for s, r in scored if s >= best - 0.025]
    if len({quiz_normalize(r["answer"]) for r in top}) != 1:
        return None
    matches = [i for i, option in enumerate(options) if answer_matches(top[0]["answer"], option)]
    return matches[0] if len(matches) == 1 else None


def load_quiz_bank() -> List[Dict[str, Any]]:
    raw = os.environ.get("EASONFANS_QUIZ_BANK", "")
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TaskError("EASONFANS_QUIZ_BANK JSON 无法解析") from exc
        if not isinstance(data, list):
            raise TaskError("EASONFANS_QUIZ_BANK JSON 必须是数组")
        bank = []
        for item in data:
            if not isinstance(item, dict):
                continue
            q = compact(item.get("question"), 500)
            a = compact(item.get("answer"), 200)
            if q and a:
                bank.append({"question": q, "answer": a})
        return bank
    bank, _issues = parse_bank_text(text)
    return [{"question": row["question"], "answer": row["answer"]} for row in bank]


def signed_today(text: str) -> bool:
    if "【今天未签到】" in text:
        return False
    return any(s in text for s in ("【今天已签到】", "您今天已经签到", "您今日已经签到", "今日已经签到", "今天已经签到"))


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: List[Dict[str, Any]] = []
        self.links: List[Tuple[Dict[str, str], str]] = []
        self.identity: Optional[str] = None
        self.uid: Optional[str] = None
        self._form: Optional[Dict[str, Any]] = None
        self._option: Optional[Dict[str, Any]] = None
        self._anchor: Optional[List[Any]] = None
        self._capture_identity = False
        self._text_buf = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "form":
            self._form = {
                "id": a.get("id", ""),
                "action": a.get("action", ""),
                "method": (a.get("method") or "get").lower(),
                "inputs": {},
                "options": [],
                "text": "",
            }
            self.forms.append(self._form)
        if tag == "input" and self._form is not None:
            name = a.get("name", "")
            itype = (a.get("type") or "text").lower()
            value = a.get("value", "")
            if name:
                if itype == "radio":
                    radios = self._form["inputs"].setdefault(name, [])
                    if not isinstance(radios, list):
                        radios = [radios]
                        self._form["inputs"][name] = radios
                    radios.append(value)
                elif itype not in {"submit", "button", "image", "file"}:
                    self._form["inputs"][name] = value
            if self._option is not None and itype == "radio":
                self._option["value"] = value
                self._option["name"] = name
        if tag in {"label", "div", "li", "span"} and self._form is not None:
            if "qs_option" in classes or a.get("class", "").find("qs_option") >= 0:
                self._option = {"text": "", "value": "", "name": "answer"}
                self._form["options"].append(self._option)
                self._text_buf = "option"
        if tag == "textarea" and self._form is not None and a.get("name"):
            self._form["inputs"][a["name"]] = a.get("value", "")
            self._text_buf = f"textarea:{a['name']}"
        if tag == "a":
            self._anchor = [a, ""]
            href = a.get("href", "")
            if "mod=space" in href and "uid=" in href and ("vwmy" in classes or a.get("title") == ""):
                if "vwmy" in classes:
                    self._capture_identity = True
            if "action=logout" in href:
                pass
            uid_match = re.search(r"[?&]uid=(\d+)", html.unescape(href))
            if uid_match and ("vwmy" in classes or "space" in href):
                if "vwmy" in classes:
                    self.uid = uid_match.group(1)
        if tag == "strong" and "vwmy" in classes:
            self._capture_identity = True

    def handle_data(self, data: str) -> None:
        if self._form is not None:
            self._form["text"] += data
        if self._option is not None and self._text_buf == "option":
            self._option["text"] += data
        if self._text_buf.startswith("textarea:") and self._form is not None:
            name = self._text_buf.split(":", 1)[1]
            self._form["inputs"][name] = self._form["inputs"].get(name, "") + data
        if self._anchor is not None:
            self._anchor[1] += data
        if self._capture_identity:
            piece = data.strip()
            if piece:
                self.identity = ((self.identity or "") + piece).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None
        if tag in {"label", "div", "li", "span"} and self._text_buf == "option":
            self._option = None
            self._text_buf = ""
        if tag == "textarea" and self._text_buf.startswith("textarea:"):
            self._text_buf = ""
        if tag == "a" and self._anchor is not None:
            self.links.append((self._anchor[0], self._anchor[1]))
            attrs, text = self._anchor
            if self._capture_identity or "vwmy" in attrs.get("class", "").split():
                name = text.strip()
                if name:
                    self.identity = name
                href = attrs.get("href", "")
                uid_match = re.search(r"[?&]uid=(\d+)", html.unescape(href))
                if uid_match:
                    self.uid = uid_match.group(1)
            self._anchor = None
            self._capture_identity = False
        if tag == "strong":
            self._capture_identity = False


def parse_page(text: str) -> FormParser:
    parser = FormParser()
    try:
        parser.feed(text)
    except Exception as exc:
        raise TaskError("页面结构解析失败") from exc
    return parser


class Client:
    def __init__(self, cookie: str, base: str, dry_run: bool = False) -> None:
        self.cookie = cookie
        self.base = base
        self.host = allowed_host(base)
        self.dry_run = dry_run
        self.timeout = timeout_seconds()
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar),
            RestrictedRedirect(self.host),
        )

    def url(self, path: str) -> str:
        joined = urllib.parse.urljoin(self.base, path)
        parsed = urllib.parse.urlsplit(joined)
        if parsed.scheme != "https" or parsed.hostname not in {self.host, "www.easonfans.com", "easonfans.com"}:
            raise TaskError("拒绝非本站 HTTPS 地址，防止凭据外发")
        if parsed.username or parsed.password:
            raise TaskError("拒绝带用户信息的 URL")
        return urllib.parse.urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))

    def request(self, path: str, data: Optional[Dict[str, str]] = None, referer: Optional[str] = None) -> str:
        if self.dry_run:
            raise TaskError("断网预演禁止业务 HTTP")
        url = self.url(path)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; QinglongEasonFans/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": self.cookie,
            "Referer": referer or self.base,
        }
        body = None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = f"https://{self.host}"
            body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
        except TaskError:
            raise
        except Exception as exc:
            raise TaskError("业务网络请求失败或超时") from exc
        if len(raw) > MAX_BYTES:
            raise TaskError("业务响应超过大小限制")
        return raw.decode("utf-8", errors="replace")


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host: str) -> None:
        super().__init__()
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urljoin(req.full_url, newurl)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {self.host, "www.easonfans.com", "easonfans.com"}:
            raise TaskError("拒绝向外站或非 HTTPS 地址转发请求")
        return super().redirect_request(req, fp, code, msg, headers, url)


def extract_formhash(text: str, page: Optional[FormParser] = None) -> str:
    if page is not None:
        for form in page.forms:
            value = form["inputs"].get("formhash")
            if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9]{6,32}", value):
                return value
    for match in re.finditer(r'name=["\']formhash["\']\s+value=["\']([a-zA-Z0-9]{6,32})["\']', text):
        return match.group(1)
    for match in re.finditer(r'value=["\']([a-zA-Z0-9]{6,32})["\']\s+name=["\']formhash["\']', text):
        return match.group(1)
    for match in re.finditer(r"formhash=([a-zA-Z0-9]{6,32})", text):
        return match.group(1)
    raise TaskError("未取得有效 formhash，请更新 Cookie")


def is_logged_in(text: str) -> bool:
    return "action=logout" in text or "member.php?mod=logging&action=logout" in text


def public_identity(page: FormParser, index: int) -> str:
    if page.identity:
        name = compact(page.identity, 80)
        if name and not re.search(r"1[3-9]\d{9}", name) and not any(ord(c) < 32 for c in name):
            log(f"账号 {index} 官方昵称：{name}")
            return name
    if page.uid:
        log(f"账号 {index} 官方公开 UID：{page.uid}")
        return f"UID:{page.uid}"
    return f"账号{index}"


def free_wheel_count(text: str) -> Optional[int]:
    match = re.search(r"今日剩余免费次数[：:]\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def discover_wheel_action(text: str) -> Optional[str]:
    patterns = [
        r"""(?:ajaxget|showWindow|location\.href|window\.open)\(\s*['"]([^'"]*gplayconstellation[^'"]+)['"]""",
        r"""['"]([^'"]*plugin\.php\?id=gplayconstellation:[^'"]+)['"]""",
        r"""href=["']([^"']*gplayconstellation[^"']*)["']""",
        r"""id=["']pointlevel["'][^>]*(?:href|data-url|onclick)=["']([^"']+)["']""",
        r"""(?:href|data-url)=["']([^"']+)["'][^>]*id=["']pointlevel["']""",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            candidate = html.unescape(match.group(1)).strip()
            if "gplayconstellation" in candidate or "pointlevel" in candidate.lower() or "lottery" in candidate.lower() or "draw" in candidate.lower():
                if candidate.startswith("javascript:"):
                    continue
                return candidate
    # onclick handlers that embed plugin URLs
    for match in re.finditer(r"id=[\"']pointlevel[\"'][^>]*onclick=[\"']([^\"']+)[\"']", text, re.I):
        inner = match.group(1)
        url_match = re.search(r"['\"]([^'\"]*plugin\.php[^'\"]+)['\"]", inner)
        if url_match:
            return html.unescape(url_match.group(1))
    return None


def extract_quiz_question(form_text: str) -> str:
    text = form_text.replace("\xa0", " ")
    match = re.search(r"【题目】\s*(.+?)(?:\n|$)", text)
    if match:
        line = match.group(1).strip()
    else:
        line = next((x.strip() for x in text.splitlines() if "？" in x or "?" in x), "")
    return re.split(r"\s{2,}", line)[0].strip()


def fetch_public_text(dry_run: bool) -> str:
    fallback = compact(env("EASONFANS_LOCAL_TEXT", "[em:1:]"), 280) or "[em:1:]"
    if len(fallback) > 280 or any(ord(c) < 32 for c in fallback):
        fallback = "[em:1:]"
    if dry_run:
        log("留言正文：断网预演使用本地兜底，不请求一言", ICONS["skipped"])
        return fallback
    try:
        req = urllib.request.Request(
            HITOKOTO_URL,
            headers={"User-Agent": "Qinglong-EasonFans", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError("oversized")
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        text = compact(obj.get("hitokoto"))
        author = compact(obj.get("from_who"))
        source = compact(obj.get("from"))
        if not text:
            raise ValueError("missing-text")
        if author and source:
            text = f"{text} —— {author}《{source}》"
        elif source:
            text = f"{text} ——《{source}》"
        elif author:
            text = f"{text} —— {author}"
        if len(text) > 280:
            raise ValueError("overlong-text")
        log("留言正文：一言内容及出处已取得（不输出正文）", ICONS["success"])
        return text
    except Exception:
        log("留言正文：一言不可用，使用本地兜底", ICONS["warning"])
        return fallback


def validate_cookie(cookie: str) -> str:
    text = cookie.strip()
    if not text:
        raise TaskError("Cookie 为空")
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise TaskError("Cookie 含控制字符")
    if ":" in text.split("=", 1)[0] and text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    parts = [p.strip() for p in text.split(";") if p.strip()]
    if not parts:
        raise TaskError("Cookie 格式无效")
    for part in parts:
        if "=" not in part:
            raise TaskError("Cookie 字段缺少名称")
    return text


def parse_accounts() -> List[str]:
    raw = os.environ.get(COOKIE_ENV, "")
    accounts = [validate_cookie(line) for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise TaskError(
            f"请设置 {COOKIE_ENV}：浏览器登录论坛后复制完整 Cookie，每个非空行一个账号"
        )
    return accounts


def stage_result(kind: str) -> str:
    return {
        "success": "success",
        "already": "already",
        "alreadyComplete": "already",
        "skipped": "skipped",
        "failed": "failed",
    }[kind]


def run_sign(client: Client, mood: str) -> str:
    path = "plugin.php?id=dsu_paulsign:sign"
    page_text = client.request(path)
    if not is_logged_in(page_text):
        raise TaskError("登录已失效，请更新 Cookie")
    if signed_today(page_text):
        return "already"
    formhash = extract_formhash(page_text)
    result = client.request(
        "plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1",
        {
            "formhash": formhash,
            "qdxq": mood,
            "qdmode": "3",
            "todaysay": "",
            "fastreply": "0",
        },
        referer=client.url(path),
    )
    visible = strip_tags(result)
    if signed_today(result) or any(s in visible for s in ("签到成功", "签到了", "签到完成", "恭喜你签到")):
        return "success"
    # re-check page
    after = client.request(path)
    if signed_today(after):
        return "success"
    if any(s in visible for s in ("已经签到", "已签到", "今日已签", "今天已经签到")):
        return "already"
    raise TaskError("签到未返回明确成功标志")


def run_wheel(client: Client) -> str:
    path = "plugin.php?id=gplayconstellation:front"
    text = client.request(path)
    remaining = free_wheel_count(text)
    if remaining == 0:
        return "already"
    action = discover_wheel_action(text)
    if not action:
        if remaining is None and "gplayconstellation" not in text and "pointlevel" not in text:
            raise TaskError("转盘页面结构无法确认")
        raise TaskError("转盘控件未暴露可复现的 HTTPS 动作，无法安全点击")
    if action.startswith("http"):
        parsed = urllib.parse.urlsplit(action)
        action_path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    else:
        action_path = action
    client.request(action_path, referer=client.url(path))
    after = client.request(path)
    after_remaining = free_wheel_count(after)
    if after_remaining == 0:
        return "success"
    if remaining is not None and after_remaining is not None and after_remaining < remaining:
        return "success"
    visible = strip_tags(after)
    if any(s in visible for s in ("抽奖成功", "恭喜", "获得", "已抽奖")):
        return "success"
    raise TaskError("转盘请求后未确认次数变化或成功标志")


def run_quiz(client: Client, bank: Sequence[Dict[str, Any]]) -> str:
    if not bank:
        log("题库未配置，跳过答题（设置 EASONFANS_QUIZ_BANK 可启用）", ICONS["skipped"])
        return "skipped"
    path = "plugin.php?id=ahome_dayquestion:index"
    answered = 0
    for round_no in range(1, 4):
        text = client.request(path)
        page = parse_page(text)
        form = next((f for f in page.forms if f.get("id") == "myform"), None)
        if form is None:
            if answered:
                return "success"
            if any(s in text for s in ("已经答过", "今日已答", "没有题目", "已完成", "明天再来")):
                return "already"
            log("未找到答题表单，可能今日已完成", ICONS["alreadyComplete"])
            return "already"
        question = extract_quiz_question(form.get("text", "") or strip_tags(text))
        if not question:
            log(f"第 {round_no} 题未解析到题干，结束答题", ICONS["warning"])
            return "success" if answered else "skipped"
        options = []
        values = []
        for opt in form.get("options") or []:
            options.append(compact(opt.get("text"), 200))
            values.append(str(opt.get("value") or ""))
        if not options:
            # fallback: radios named answer
            radios = form["inputs"].get("answer")
            if isinstance(radios, list):
                values = [str(v) for v in radios]
                options = values[:]
        log(f"题目 {round_no}：已取得题干与 {len(options)} 个选项（不输出原文）")
        selected = choose_option(question, options, bank)
        if selected is None:
            log("题目或选项无法唯一匹配，未提交答案；结束本次答题", ICONS["warning"])
            return "success" if answered else "skipped"
        formhash = form["inputs"].get("formhash")
        if not isinstance(formhash, str) or not formhash:
            formhash = extract_formhash(text, page)
        payload: Dict[str, str] = {}
        for key, value in form["inputs"].items():
            if isinstance(value, list):
                continue
            payload[str(key)] = str(value)
        answer_name = "answer"
        if form.get("options") and form["options"][selected].get("name"):
            answer_name = form["options"][selected]["name"]
        answer_value = values[selected] if selected < len(values) and values[selected] else str(selected + 1)
        payload[answer_name] = answer_value
        payload["formhash"] = formhash
        action = form.get("action") or path
        client.request(action, payload, referer=client.url(path))
        answered += 1
        time.sleep(1)
    return "success"


def collect_uids(client: Client, self_uid: str, needed: int) -> List[str]:
    found: List[str] = []
    for page_no in range(1, 31):
        path = f"home.php?mod=space&uid={self_uid}&do=wall&page={page_no}"
        text = client.request(path)
        for match in re.finditer(r"[?&]uid=(\d+)", text):
            uid = match.group(1)
            if uid != self_uid and uid not in found:
                found.append(uid)
        if len(found) >= needed:
            break
    return found[:needed]


def leave_one_message(client: Client, uid: str, message: str) -> bool:
    path = f"home.php?mod=space&uid={uid}&do=wall"
    text = client.request(path)
    if "comment_message" not in text and "留言" not in text:
        return False
    page = parse_page(text)
    form = None
    for item in page.forms:
        inputs = item.get("inputs") or {}
        if "message" in inputs or "commentsubmit" in str(inputs) or item.get("id", "").startswith("commentform"):
            form = item
            break
        if "comment_message" in item.get("text", ""):
            form = item
            break
    formhash = extract_formhash(text, page)
    payload: Dict[str, str] = {
        "message": message,
        "formhash": formhash,
        "commentsubmit": "true",
        "handlekey": f"qcwall_{uid}",
        "id": uid,
        "idtype": "uid",
    }
    action = "home.php?mod=spacecp&ac=comment"
    if form is not None:
        for key, value in (form.get("inputs") or {}).items():
            if isinstance(value, list):
                continue
            payload[str(key)] = str(value)
        payload["message"] = message
        payload["formhash"] = formhash
        if form.get("action"):
            action = form["action"]
    result = client.request(action, payload, referer=client.url(path))
    visible = strip_tags(result)
    box = re.search(rf"return_qcwall_{uid}[^>]*>([^<]+)", result)
    if box:
        visible = compact(html.unescape(box.group(1)), 200) + " " + visible
    if "操作成功" in visible or "留言成功" in visible:
        return True
    if "操作太快" in visible:
        return False
    # some Discuz installs return empty AJAX but still succeed; re-open wall is expensive — require clear success
    return False


def run_wall(client: Client, self_uid: str, count: int, delay: int, dry_run: bool) -> str:
    if count <= 0:
        log("留言已关闭（EASONFANS_MESSAGE_COUNT=0）", ICONS["skipped"])
        return "skipped"
    if not self_uid:
        raise TaskError("未能从页面识别自身 UID，无法安全留言")
    targets = collect_uids(client, self_uid, count)
    if not targets:
        raise TaskError("留言墙未收集到目标 UID")
    message = fetch_public_text(dry_run)
    ok = 0
    for index, uid in enumerate(targets):
        if leave_one_message(client, uid, message):
            ok += 1
            log(f"留言目标 {index + 1}/{len(targets)}：成功", ICONS["success"])
        else:
            log(f"留言目标 {index + 1}/{len(targets)}：未确认成功", ICONS["failure"])
        if index < len(targets) - 1:
            time.sleep(max(1, delay))
    if ok == 0:
        raise TaskError("全部留言均未确认成功")
    if ok < len(targets):
        raise TaskError(f"仅确认 {ok}/{len(targets)} 条留言成功")
    return "success"


def run_account(
    index: int,
    cookie: str,
    base: str,
    dry_run: bool,
    bank: Sequence[Dict[str, Any]],
    message_count: int,
    message_delay: int,
    mood: str,
) -> Dict[str, Any]:
    stats = {"total": 0, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    started = time.monotonic()
    identity = f"账号{index}"
    account_failed = False

    def stage(number: int, name: str, action) -> None:
        nonlocal account_failed
        before = time.monotonic()
        stats["total"] += 1
        log(f"账号 {index} 阶段 {number}：{name}")
        try:
            result = action()
            key = stage_result(result)
            stats[key] += 1
            label = {
                "success": f"{ICONS['success']} 成功",
                "already": f"{ICONS['alreadyComplete']} 已完成",
                "skipped": f"{ICONS['skipped']} 跳过",
            }[key]
            log(f"账号 {index} 阶段 {number}：{label}，耗时 {time.monotonic() - before:.2f} 秒")
        except Exception as exc:
            stats["failed"] += 1
            account_failed = True
            message = compact(exc) if isinstance(exc, TaskError) else "响应解析或本地处理失败"
            log(f"账号 {index} 阶段 {number}：{ICONS['failure']} {message}，耗时 {time.monotonic() - before:.2f} 秒")

    if dry_run:
        stage(1, "模拟登录校验（无网络）", lambda: "skipped")
        stage(2, "模拟每日签到（无状态变更）", lambda: "skipped")
        stage(3, "模拟幸运转盘（无状态变更）", lambda: "skipped")
        stage(4, "模拟每日答题（无状态变更）", lambda: "skipped")
        stage(
            5,
            "模拟留言墙" if message_count > 0 else "留言未开启",
            lambda: "skipped",
        )
    else:
        client = Client(cookie, base, dry_run=False)
        state: Dict[str, Any] = {"uid": ""}

        def login() -> str:
            nonlocal identity
            text = client.request("")
            if not is_logged_in(text):
                # try sign page which often contains logout link
                text = client.request("plugin.php?id=dsu_paulsign:sign")
            if not is_logged_in(text):
                raise TaskError("登录已失效，请更新 Cookie")
            page = parse_page(text)
            identity = public_identity(page, index)
            state["uid"] = page.uid or ""
            if not state["uid"]:
                uid_match = re.search(r"[?&]uid=(\d+)", text)
                if uid_match:
                    state["uid"] = uid_match.group(1)
            return "success"

        if not account_failed:
            stage(1, "校验登录与公开身份", login)
        if not account_failed:
            stage(2, "每日签到", lambda: run_sign(client, mood))
        if not account_failed:
            stage(3, "幸运转盘", lambda: run_wheel(client))
        if not account_failed:
            stage(4, "每日答题", lambda: run_quiz(client, bank))
        if not account_failed:
            stage(
                5,
                "留言墙" if message_count > 0 else "留言未开启",
                lambda: run_wall(client, state.get("uid") or "", message_count, message_delay, dry_run),
            )

    log(
        "账号 {index} 统计：总任务 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}；耗时 {elapsed:.2f} 秒".format(
            index=index, elapsed=time.monotonic() - started, **stats
        )
    )
    return {
        "ok": not account_failed,
        "identity": identity,
        "stats": stats,
        "failed": account_failed,
    }


def notify_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE:
        return False, "已关闭"
    if switch in TRUE:
        return True, "已开启"
    if switch != "auto":
        log("QINGLONG_NOTIFY 值无效，按 auto 处理", ICONS["warning"])
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False, "默认仅通知名单内脚本，未配置 QINGLONG_NOTIFY_SCRIPTS"
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", ""))
        if item
    ]
    if not selectors:
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空，已禁用全部通知"
    identities = {
        CATALOG_ID.lower(),
        "scripts/easonfans_daily.py",
        "easonfans_daily.py",
        "easonfans_daily",
        "candidate.py",
        Path(__file__).name.lower(),
    }
    if "*" in selectors or any(
        _ql_notify_fnmatch.fnmatch(identity, selector)
        for selector in selectors
        for identity in identities
    ):
        return True, "名单匹配"
    return False, "未匹配通知名单"


def send_notify(body: str, dry_run: bool) -> str:
    enabled, reason = notify_enabled()
    if not enabled:
        return reason
    if dry_run:
        log("断网预演通知：" + body, ICONS["skipped"])
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
        p = pathlib.Path(root) / 'notify.py'
        if p.is_file():
            spec = importlib.util.spec_from_file_location('notify', p)
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
            check=False,
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
                        ".catch(()=>process.exit(1))"
                    )
                    node = subprocess.run(
                        ["node", "-e", js, str(path), TITLE, body],
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    return "已发送" if node.returncode == 0 else "发送失败"
        return "不可用或发送失败"
    except Exception:
        return "不可用或发送失败"


def main() -> int:
    started = time.monotonic()
    started_at = now_full()
    dry_run = env_bool(DRY_RUN_ENV)
    config_error = ""
    accounts: List[str] = []
    bank: List[Dict[str, Any]] = []
    base = DEFAULT_BASE
    message_count = 0
    message_delay = 25
    mood = MOOD_IDS[0]

    log("=" * 56)
    log(f"{TITLE} | 维护版")
    log(f"开始时间：{started_at}")
    log(f"运行模式：{'断网预演' if dry_run else '正式执行'}")

    try:
        base = normalize_base(env("EASONFANS_BASE_URL", DEFAULT_BASE))
        accounts = parse_accounts()
        bank = load_quiz_bank()
        message_count = env_int("EASONFANS_MESSAGE_COUNT", 0, 0, 50)
        message_delay = env_int("EASONFANS_MESSAGE_DELAY", 25, 1, 600)
        emoji_index = env_int("EASONFANS_EMOJI_INDEX", 0, 0, len(MOOD_IDS) - 1)
        mood = MOOD_IDS[emoji_index]
    except Exception as exc:
        config_error = compact(exc) if isinstance(exc, TaskError) else "配置解析失败"
        accounts = []

    log(f"账号数量：{len(accounts)}")
    if bank:
        log(f"题库条目：{len(bank)}")
    else:
        log("题库条目：0（答题阶段将跳过）", ICONS["warning"])

    results: List[Dict[str, Any]] = []
    if config_error:
        log(f"配置错误：{config_error}", ICONS["failure"])
    else:
        for index, cookie in enumerate(accounts, 1):
            log(f"----- 账号 {index}/{len(accounts)} -----")
            results.append(
                run_account(
                    index,
                    cookie,
                    base,
                    dry_run,
                    bank,
                    message_count,
                    message_delay,
                    mood,
                )
            )

    failed_accounts = (max(1, len(accounts)) if config_error else sum(1 for item in results if item.get("failed")))
    success_accounts = 0 if config_error else len(results) - failed_accounts
    if config_error:
        status = "configuration-error"
    elif dry_run and not failed_accounts:
        status = "dry-run"
    elif failed_accounts and success_accounts:
        status = "partial-failure"
    elif failed_accounts:
        status = "failure"
    else:
        status = "success"

    totals = {key: sum(item["stats"][key] for item in results) for key in ("total", "success", "already", "skipped", "failed")}
    body = (
        f"状态：{status}；账号总数：{len(accounts)}；成功数：{success_accounts}；失败数：{failed_accounts}"
        + ("；预演未验证业务" if dry_run else "")
        + (f"；原因：{config_error}" if config_error else "")
    )
    notification = send_notify(body, dry_run)

    log("-" * 40)
    log(body)
    log(
        "子任务统计：总任务 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(
            **totals
        )
    )
    finished_at = now_full()
    log(f"总耗时：{time.monotonic() - started:.2f} 秒；通知：{notification}")
    log(f"完成时间：{finished_at}；最终状态：{status}")
    summary = {
        "task": "easonfans_daily",
        "catalogId": CATALOG_ID,
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": len(accounts),
        "successfulAccounts": success_accounts,
        "failedAccounts": failed_accounts,
        "tasks": totals,
        "notification": notification,
        "finishedAt": finished_at,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    if not config_error and not failed_accounts:
        print("DRY_RUN_OK" if dry_run else "EASONFANS_TASK_OK", flush=True)
    return 1 if config_error or failed_accounts else 0


if __name__ == "__main__":
    raise SystemExit(main())
