#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: LeetCode 中文站每日一题自动打卡
# cron: 30 0 * * *
# SPDX-License-Identifier: MIT
"""LeetCode 中文站（leetcode.cn）每日一题自动打卡。

来源：JadenSailing/leetcode-check，leetcode_daily.py；MIT License。
Copyright (c) 2026 jadensailing@126.com

上游能力：
  1. 查询今日每日一题（dailyQuestionRecords，回退 todayRecord）；
  2. 检查当天是否已 AC 该题；
  3. 未完成时抓取题解中合法 C++ 代码并提交，轮询判题结果。

本维护版转为青龙可调度独立任务：环境变量多账号、完全断网预演、标准库 HTTP、
超时与业务成功判定、时间轴日志、TASK_SUMMARY 与青龙通知。
移除上游进程内守护、本地 config.json / PID / 日志文件副作用。

LEETCODE_COOKIE：每个非空行一个账号。推荐直接粘贴浏览器 Cookie 片段，须含
LEETCODE_SESSION，建议同时含 csrftoken。也支持「LEETCODE_SESSION值#csrftoken值」，
仅在第一个 # 处拆分。不要把 Cookie 发给他人或写入公开仓库。
兼容别名：当 LEETCODE_COOKIE 为空时，可读 LEETCODE_SESSION + LEETCODE_CSRFTOKEN
（或 csrftoken）组成单账号。
LEETCODE_LANG：提交语言，默认 cpp（题解抓取亦针对 C++）。
LEETCODE_CHECK_ONLY=1：仅查询今日题目与完成状态，不提交代码。
LEETCODE_TIMEOUT：单次请求超时秒数，默认 30，范围 5..120。
LEETCODE_POLL_TIMEOUT：判题轮询最长秒数，默认 60，范围 10..300。
LEETCODE_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
上游 README 建议每天 00:10 / 23:50；青龙主定时采用 10 0 * * *，可另建 50 23 * * *
指向同一脚本。本脚本不发布帖子、评论或分享文本。

MIT License

Copyright (c) 2026 jadensailing@126.com

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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "afb968077b55cdf8",
            "scripts/leetcode_daily.py",
            "leetcode_daily.py",
            "candidate.py",
            "leetcode_daily",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path

TITLE = "LeetCode 中文站每日一题自动打卡"
CATALOG_ID = "afb968077b55cdf8"
BASE = "https://leetcode.cn"
GRAPHQL = BASE + "/graphql/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
MAX_RESPONSE_BYTES = 1024 * 1024


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def truthy(name):
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def redact_text(value, secrets):
    text = str(value)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def clean_identity(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if not text or any(secret and secret in text for secret in secrets):
        return ""
    if re.fullmatch(r"(?i)bearer\s+\S+", text):
        return ""
    return redact_text(text, secrets)


def parse_timeout(name, default, lo, hi):
    raw = os.environ.get(name, str(default)).strip() or str(default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("{} 必须是整数秒".format(name)) from exc
    if value < lo or value > hi:
        raise SafeError("{} 允许范围 {}..{}".format(name, lo, hi))
    return value


def parse_cookie_jar(text):
    jar = {}
    for item in text.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        jar[key.strip()] = value.strip()
    return jar


def parse_account_line(line, index):
    text = line.strip()
    if not text:
        raise SafeError("账号 {} 为空行".format(index))
    session = ""
    csrf = ""
    extra_parts = []
    secrets = []

    if "LEETCODE_SESSION=" in text or "leetcode_session=" in text.lower():
        jar = parse_cookie_jar(text)
        for key, value in jar.items():
            lower = key.lower()
            if lower == "leetcode_session":
                session = value
            elif lower == "csrftoken":
                csrf = value
            else:
                if value:
                    extra_parts.append("{}={}".format(key, value))
                    secrets.append(value)
    elif "#" in text:
        session, csrf = text.split("#", 1)
        session = session.strip()
        csrf = csrf.strip()
    else:
        # 整行仅会话值（无 csrftoken 时提交可能失败，仍允许查询）
        session = text

    if not session or len(session) < 8:
        raise SafeError("账号 {} 缺少有效的 LEETCODE_SESSION".format(index))
    secrets.append(session)
    if csrf:
        secrets.append(csrf)
    return {
        "session": session,
        "csrf": csrf,
        "extra": "; ".join(extra_parts),
        "secrets": [item for item in secrets if item],
    }


def load_accounts():
    raw = os.environ.get("LEETCODE_COOKIE", "")
    lines = [line for line in raw.splitlines() if line.strip()]
    if lines:
        return [parse_account_line(line, index) for index, line in enumerate(lines, 1)]
    session = os.environ.get("LEETCODE_SESSION", "").strip()
    csrf = (
        os.environ.get("LEETCODE_CSRFTOKEN", "").strip()
        or os.environ.get("csrftoken", "").strip()
    )
    if session or csrf:
        if not session:
            raise SafeError("兼容别名需提供 LEETCODE_SESSION")
        line = "LEETCODE_SESSION={}".format(session)
        if csrf:
            line += "; csrftoken={}".format(csrf)
        return [parse_account_line(line, 1)]
    raise SafeError("未配置 LEETCODE_COOKIE（或兼容别名 LEETCODE_SESSION）")


def parse_lang():
    lang = os.environ.get("LEETCODE_LANG", "cpp").strip() or "cpp"
    if not re.fullmatch(r"[A-Za-z0-9+#_-]{1,32}", lang):
        raise SafeError("LEETCODE_LANG 格式无效")
    return lang


class OfflineHTTPError(SafeError):
    pass


class HttpClient:
    def __init__(self, timeout, dry_run):
        self.timeout = timeout
        self.dry_run = dry_run

    def request(self, method, url, headers=None, body=None):
        if self.dry_run:
            raise OfflineHTTPError("断网预演禁止发起网络请求")
        data = None
        req_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            url, data=data, headers=req_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise SafeError("响应体过大，已中止解析")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                status = response.getcode()
        except OfflineHTTPError:
            raise
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1) if exc.fp else b""
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SafeError("HTTP {} 响应体过大".format(exc.code)) from exc
            charset = "utf-8"
            if exc.headers:
                charset = exc.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            status = exc.code
            try:
                payload = json.loads(text) if text else {}
            except ValueError:
                payload = {}
            if status >= 400:
                raise SafeError("HTTP {}".format(status)) from exc
            return status, payload if isinstance(payload, dict) else {}
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            raise SafeError("网络请求失败或超时") from exc
        try:
            payload = json.loads(text) if text else {}
        except ValueError as exc:
            raise SafeError("响应不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise SafeError("响应 JSON 结构异常")
        return status, payload


def build_headers(account, referer=None):
    cookie = "LEETCODE_SESSION={}".format(account["session"])
    if account["csrf"]:
        cookie += "; csrftoken={}".format(account["csrf"])
    if account.get("extra"):
        cookie += "; {}".format(account["extra"])
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": referer or (BASE + "/"),
        "x-csrftoken": account["csrf"],
        "x-requested-with": "XMLHttpRequest",
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
    }
    return headers


class LeetCodeClient:
    def __init__(self, http, account, lang, poll_timeout):
        self.http = http
        self.account = account
        self.lang = lang
        self.poll_timeout = poll_timeout
        self.secrets = list(account["secrets"])

    def gql(self, operation, query, variables=None):
        payload = {
            "query": query,
            "operationName": operation,
            "variables": variables or {},
        }
        _status, body = self.http.request(
            "POST", GRAPHQL, headers=build_headers(self.account), body=payload
        )
        if body.get("errors"):
            raise SafeError(
                "GraphQL {} 业务报错".format(operation)
            )
        data = body.get("data")
        if data is None:
            raise SafeError("GraphQL {} 无数据".format(operation))
        return data

    def user_identity(self):
        q = """
        query globalData {
          userStatus {
            userId
            username
            realName
            isSignedIn
          }
        }
        """
        data = self.gql("globalData", q)
        status = (data or {}).get("userStatus") or {}
        if status.get("isSignedIn") is False:
            raise SafeError("Cookie 未登录或已失效")
        for field in ("username", "realName", "userId"):
            identity = clean_identity(status.get(field), self.secrets)
            if identity:
                return identity
        return ""

    def today_question(self):
        now = datetime.datetime.now()
        q = """
        query dailyQuestionRecords($year: Int!, $month: Int!) {
          dailyQuestionRecords(year: $year, month: $month) {
            date
            userStatus
            question {
              questionId
              questionFrontendId
              titleSlug
              translatedTitle
              title
            }
          }
        }
        """
        try:
            data = self.gql(
                "dailyQuestionRecords",
                q,
                {"year": now.year, "month": now.month},
            )
            recs = (data or {}).get("dailyQuestionRecords") or []
            for item in recs:
                date_text = str(item.get("date", ""))
                if date_text.endswith(
                    "-{:02d}-{:02d}".format(now.month, now.day)
                ) or date_text.endswith("-{}-{}".format(now.month, now.day)):
                    question = item["question"]
                    return {
                        "slug": question["titleSlug"],
                        "question_id": question["questionId"],
                        "frontend_id": question["questionFrontendId"],
                        "title": question.get("translatedTitle")
                        or question.get("title"),
                    }
        except SafeError:
            pass

        q2 = """
        query queryQuestionOfToday {
          todayRecord {
            date
            userStatus
            question {
              questionId
              questionFrontendId
              titleSlug
              translatedTitle
              title
            }
          }
        }
        """
        data = self.gql("queryQuestionOfToday", q2)
        rec = (data or {}).get("todayRecord") or []
        if not rec:
            raise SafeError("无法获取今日每日一题")
        question = rec[0]["question"]
        return {
            "slug": question["titleSlug"],
            "question_id": question["questionId"],
            "frontend_id": question["questionFrontendId"],
            "title": question.get("translatedTitle") or question.get("title"),
        }

    def is_done(self, slug):
        q = """
        query submissionList($questionSlug: String!, $offset: Int!, $limit: Int!) {
          submissionList(questionSlug: $questionSlug, offset: $offset, limit: $limit) {
            submissions { id status statusDisplay lang timestamp }
            lastKey
          }
        }
        """
        data = self.gql(
            "submissionList",
            q,
            {"questionSlug": slug, "offset": 0, "limit": 30},
        )
        subs = (((data or {}).get("submissionList")) or {}).get("submissions") or []
        now = datetime.datetime.now()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_epoch = int(today_midnight.timestamp())
        for item in subs:
            status = item.get("status")
            disp = str(item.get("statusDisplay") or "")
            ts = item.get("timestamp")
            is_today = False
            if ts is not None and str(ts).isdigit():
                is_today = int(ts) >= today_start_epoch
            if not is_today:
                continue
            du = disp.upper()
            if str(status) == "10" or du in ("AC", "ACCEPTED") or "通过" in disp:
                return True
        return False

    def get_cpp_solutions(self, slug):
        q = """
        query questionSolutionList($questionSlug: String!, $first: Int!, $skip: Int!) {
          questionSolutionArticles(questionSlug: $questionSlug, first: $first, skip: $skip) {
            totalNum
            edges { node { title slug summary content } }
          }
        }
        """
        data = self.gql(
            "questionSolutionList",
            q,
            {"questionSlug": slug, "first": 10, "skip": 0},
        )
        edges = (((data or {}).get("questionSolutionArticles")) or {}).get("edges") or []
        nodes = [edge.get("node") for edge in edges if edge.get("node")]
        for node in nodes:
            if not node.get("content"):
                try:
                    node["content"] = self._article_detail(node["slug"])
                except SafeError:
                    continue
        if not nodes:
            raise SafeError("未找到任何题解文章")

        cpp_patterns = [
            re.compile(r"```(?:cpp|c\+\+|cxx)\b(.*?)```", re.S),
            re.compile(
                r'<pre[^>]*>\s*<code[^>]*class="[^"]*(?:cpp|c\+\+|cxx)[^"]*"[^>]*>(.*?)</code>',
                re.S,
            ),
        ]
        any_md_re = re.compile(r"```(?:[a-zA-Z0-9+#]+)?\b(.*?)```", re.S)
        any_html_re = re.compile(r"<pre[^>]*>\s*<code[^>]*>(.*?)</code>", re.S)
        candidates = []
        seen = set()

        def add(code):
            if not code:
                return
            key = code.strip()
            if key in seen or not self._is_valid_cpp(code):
                return
            seen.add(key)
            candidates.append(code)

        for node in nodes:
            content = node.get("content") or ""
            if not content:
                continue
            for pattern in cpp_patterns:
                for match in pattern.finditer(content):
                    add(_clean_code(match.group(1)))
        if not candidates:
            for node in nodes:
                content = node.get("content") or ""
                for pattern in (any_md_re, any_html_re):
                    for match in pattern.finditer(content):
                        add(_clean_code(match.group(1)))
        if not candidates:
            raise SafeError("未能从题解中找到包含 class Solution 的完整 C++ 代码")
        return candidates

    @staticmethod
    def _is_valid_cpp(code):
        return bool(re.search(r"class\s+Solution\b", code))

    def _article_detail(self, article_slug):
        q = """
        query solutionDetail($slug: String!) {
          solutionArticle(slug: $slug) {
            title
            content
          }
        }
        """
        data = self.gql("solutionDetail", q, {"slug": article_slug})
        article = (data or {}).get("solutionArticle") or {}
        return article.get("content") or ""

    def submit(self, slug, question_id, code):
        url = "{}/problems/{}/submit/".format(BASE, slug)
        headers = build_headers(self.account, referer="{}/problems/{}/".format(BASE, slug))
        payload = {
            "lang": self.lang,
            "question_id": int(question_id)
            if str(question_id).isdigit()
            else question_id,
            "test_judger": "",
            "test_mode": False,
            "typed_code": code,
        }
        _status, body = self.http.request("POST", url, headers=headers, body=payload)
        sid = body.get("submission_id") or body.get("submissionId")
        if not sid:
            raise SafeError("提交失败，未返回 submission_id")
        return self._poll(sid)

    def _poll(self, submission_id):
        url = "{}/submissions/detail/{}/check/".format(BASE, submission_id)
        headers = build_headers(self.account)
        start = time.time()
        while time.time() - start < self.poll_timeout:
            _status, body = self.http.request("GET", url, headers=headers)
            state = str(body.get("state") or body.get("status") or "")
            if state in ("STARTED", "PENDING", ""):
                time.sleep(2)
                continue
            if state in ("SUCCESS", "FAILED", "CHECKED"):
                status_code = body.get("status_code")
                total_correct = body.get("total_correct") or 0
                total_cases = body.get("total_testcases") or 0
                ok = (str(status_code) == "10") or (
                    total_cases
                    and total_correct == total_cases
                    and total_correct > 0
                )
                return bool(ok)
            time.sleep(2)
        raise SafeError("判题超时（{}s）".format(self.poll_timeout))


def _clean_code(raw):
    if not raw:
        return ""
    txt = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    txt = unescape(txt)
    lines = txt.splitlines()
    lines = [ln for ln in lines if not re.match(r"\s*\[sol-[\w+#]+\]\s*$", ln)]
    lines = [ln for ln in lines if ln.strip() != "```"]
    lines = [ln.rstrip() for ln in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


class AccountRunner:
    def __init__(self, number):
        self.number = number
        self.identity = ""
        self.status = "failure"
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()

    def stage(self, number, name, func):
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        started = time.monotonic()
        try:
            state, detail, extra = func()
        except SafeError as error:
            self.stats["failure"] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS["failure"],
                    str(error),
                    time.monotonic() - started,
                )
            )
            raise
        icon = ICONS.get(state, ICONS["success"])
        self.stats[state] = self.stats.get(state, 0) + 1
        log(
            "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                self.number,
                number,
                name,
                icon,
                detail,
                time.monotonic() - started,
            )
        )
        return extra

    def skip(self, number, name, reason):
        self.stats["skipped"] += 1
        log(
            "账号 {} · 阶段 {} {}：{} {}".format(
                self.number, number, name, ICONS["skipped"], reason
            )
        )

    def finish(self):
        elapsed = round(time.monotonic() - self.started, 2)
        label = self.identity or ("账号{}".format(self.number))
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                elapsed,
                self.status,
            )
        )


def run_account(runner, account, http, dry_run, lang, poll_timeout, check_only):
    def validate():
        return "success", "凭据字段齐全（已检测到 LEETCODE_SESSION）", None

    runner.stage(1, "校验账号配置", validate)

    if dry_run:
        runner.skip(2, "查询公开身份", "断网预演：不请求用户接口")
        runner.skip(3, "查询今日每日一题", "断网预演：不请求题目接口")
        runner.skip(4, "检查今日 AC 状态", "断网预演：不请求提交记录")
        if check_only:
            runner.skip(5, "抓取并提交题解", "断网预演且仅检查模式")
        else:
            runner.skip(5, "抓取并提交题解", "断网预演：不抓取题解、不提交")
        runner.status = "dry-run"
        log(
            "账号 {}：断网预演通过；未验证真实身份、凭据或业务结果".format(
                runner.number
            )
        )
        return

    client = LeetCodeClient(http, account, lang, poll_timeout)

    def identity_stage():
        identity = client.user_identity()
        if identity:
            return "success", "公开身份：" + identity, identity
        return "success", "未返回可显示用户名，将使用账号序号", ""

    display = runner.stage(2, "查询公开身份", identity_stage)
    if display:
        runner.identity = display

    def question_stage():
        info = client.today_question()
        title = clean_identity(info.get("title"), account["secrets"]) or "?"
        frontend = clean_identity(info.get("frontend_id"), account["secrets"]) or "?"
        return (
            "success",
            "今日每日一题：#{} {}".format(frontend, title),
            info,
        )

    info = runner.stage(3, "查询今日每日一题", question_stage)

    def done_stage():
        done = client.is_done(info["slug"])
        if done:
            return "alreadyComplete", "今日已 AC，无需提交", True
        return "success", "今日尚未 AC", False

    already = runner.stage(4, "检查今日 AC 状态", done_stage)
    if already:
        runner.status = "alreadyComplete"
        log(
            "账号 {}（{}）：今日已完成".format(
                runner.number, runner.identity or ("账号{}".format(runner.number))
            )
        )
        return

    if check_only:
        runner.skip(5, "抓取并提交题解", "已开启 LEETCODE_CHECK_ONLY，跳过提交")
        runner.status = "success"
        log(
            "账号 {}（{}）：仅检查模式，今日未完成".format(
                runner.number, runner.identity or ("账号{}".format(runner.number))
            )
        )
        return

    def submit_stage():
        candidates = client.get_cpp_solutions(info["slug"])
        limit = min(5, len(candidates))
        for idx, code in enumerate(candidates[:limit]):
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full = "//auto submit by script {}\n".format(stamp) + code
            try:
                ok = client.submit(info["slug"], info["question_id"], full)
            except SafeError:
                ok = False
            if ok:
                return (
                    "success",
                    "自动提交 AC（候选 {}/{}）".format(idx + 1, limit),
                    True,
                )
            time.sleep(3)
        raise SafeError("所有候选题解均未通过判题")

    runner.stage(5, "抓取并提交题解", submit_stage)
    if runner.stats["failure"]:
        runner.status = "failure"
    else:
        runner.status = "success"
    log(
        "账号 {}（{}）：{}".format(
            runner.number,
            runner.identity or ("账号{}".format(runner.number)),
            {
                "success": "打卡成功",
                "alreadyComplete": "今日已完成",
                "failure": "存在失败子任务",
            }.get(runner.status, runner.status),
        )
    )


PY_NOTIFY_RUNNER = r"""
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
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
"""

JS_NOTIFY_RUNNER = r"""
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
"""


def notification_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(
        r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip()
    )
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "leetcode_daily.py",
        "candidate.py",
        "scripts/leetcode_daily.py",
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
    return enabled, (
        "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"
    )


def notify(body, dry_run):
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
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
                log(
                    "通知：✅ 脱敏总结已交给青龙适配器"
                    + ("（断网保护启用）" if dry_run else "")
                )
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    started_at = clock()
    dry_setting = os.environ.get("LEETCODE_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    check_only = truthy("LEETCODE_CHECK_ONLY")
    accounts = []
    parsed = []
    lang = "cpp"
    poll_timeout = 60
    config_error = None
    log("========== {} ==========".format(TITLE))
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES and dry_setting != "":
            raise SafeError("LEETCODE_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout("LEETCODE_TIMEOUT", 30, 5, 120)
        poll_timeout = parse_timeout("LEETCODE_POLL_TIMEOUT", 60, 10, 300)
        lang = parse_lang()
        parsed = load_accounts()
        http = HttpClient(timeout=timeout, dry_run=dry_run)
    except SafeError as error:
        config_error = str(error)
        log(
            "开始时间：{}；运行模式：{}；账号数：0".format(
                started_at, "断网预演" if dry_run else "真实执行"
            )
        )
        log("阶段 0 参数配置：❌ " + config_error)
    else:
        mode = (
            "断网预演"
            if dry_run
            else ("仅检查" if check_only else "真实打卡")
        )
        log(
            "开始时间：{}；运行模式：{}；账号数：{}；语言：{}".format(
                started_at, mode, len(parsed), lang
            )
        )
        for number, account in enumerate(parsed, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    account,
                    http,
                    dry_run,
                    lang,
                    poll_timeout,
                    check_only,
                )
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(parsed):
                time.sleep(1)

    counts = {
        state: sum(item.status == state for item in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    account_total = len(parsed) if not config_error else 0
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    if config_error and not parsed:
        failed = max(failed, 1)
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and (succeeded or counts["dry-run"])
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status,
        account_total if not config_error else 0,
        succeeded,
        failed,
        counts["dry-run"],
        "是" if config_error else "否",
    )
    log("阶段 N 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log(
        "阶段 N 通知：结束（{:.2f}秒）".format(
            time.monotonic() - notification_started
        )
    )
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total if not config_error else 0,
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
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    if dry_run and not config_error and failed == 0:
        log("断网预演通过")
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total if not config_error else 0,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "checkOnly": check_only,
                "lang": lang,
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
