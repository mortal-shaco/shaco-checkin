# -*- coding: utf-8 -*-
# name: EUserv 自动续期
# cron: 56 10 */7 * *
# SPDX-License-Identifier: MIT
# Effective license supplied by the source catalog: MIT.
# Upstream notices retained verbatim:
# SPDX-FileCopyrightText: (c) 2020-2021 CokeMine & Its repository contributors
# SPDX-FileCopyrightText: (c) 2021 A beam of light
# Original file declared: SPDX-License-Identifier: GPL-3.0-or-later
"""EUserv 自动续期（独立青龙脚本）。

上游作者：@ZetaoYang

环境变量 ``EUSERV_ACCOUNTS`` 每个非空行是一个 JSON 对象，例如字段结构为：
``username``、``password``、``mailparser_dl_url_id``、``userid``、``apikey``。
其中 userid/apikey 是 TrueCaptcha 凭据，mailparser_dl_url_id 是 Mailparser
解析结果下载地址末尾的 ID。脚本不会输出这些值。

设置 ``EUSERV_DRY_RUN=1`` 可进行完全断网的配置预演。兼容旧变量
``EUSERV``，它可以是同样的逐行 JSON，也可以是 JSON 数组或包含 EUSERV
数组的 JSON 对象。
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
        _ql_notify_identities = ('9b86f9dc679c7816', 'scripts/ck_euserv.py', 'ck_euserv.py', 'ck_euserv')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import http.cookiejar
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable


TASK_NAME = "EUserv 自动续期"
CATALOG_ID = "9b86f9dc679c7816"
SCRIPT_NAMES = {CATALOG_ID, "candidate.py", "ck_euserv.py", "EUserv 自动续期"}
BASE_URL = "https://support.euserv.com/index.iphp"
CAPTCHA_IMAGE_URL = "https://support.euserv.com/securimage_show.php"
CAPTCHA_SOLVE_URL = "https://api.apitruecaptcha.org/one/gettext"
CAPTCHA_USAGE_URL = "https://api.apitruecaptcha.org/one/getusage"
MAILPARSER_BASE_URL = "https://files.mailparser.io/d/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
)
DEFAULT_TIMEOUT = 20.0
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数字") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return value


class ConfigError(Exception):
    """安全、可直接展示的配置错误。"""


class TaskError(Exception):
    """已脱敏、可直接展示的账号任务错误。"""


@dataclass(frozen=True)
class Account:
    username: str
    password: str
    mailparser_dl_url_id: str
    captcha_userid: str
    captcha_apikey: str


@dataclass
class Stats:
    total: int = 0
    success: int = 0
    already: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, other: "Stats") -> None:
        self.total += other.total
        self.success += other.success
        self.already += other.already
        self.skipped += other.skipped
        self.failed += other.failed

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "success": self.success,
            "already_complete": self.already,
            "skipped": self.skipped,
            "failed": self.failed,
        }


@dataclass
class AccountResult:
    ok: bool
    stats: Stats = field(default_factory=Stats)
    message: str = ""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Any
    body: bytes

    def text(self) -> str:
        content_type = self.headers.get_content_charset() if self.headers else None
        return self.body.decode(content_type or "utf-8", errors="replace")

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TaskError("服务返回了无效 JSON") from exc


class HttpClient:
    """带 Cookie、超时及响应大小限制的标准库 HTTP 客户端。"""

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        form: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        max_bytes: int = MAX_HTML_BYTES,
        label: str = "请求",
    ) -> HttpResponse:
        data: bytes | None = None
        request_headers = dict(headers or {})
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            request_headers.setdefault(
                "Content-Type", "application/x-www-form-urlencoded; charset=UTF-8"
            )
        elif json_body is not None:
            data = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request_headers.setdefault("User-Agent", USER_AGENT)
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method.upper()
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise TaskError(f"{label}响应过大")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise TaskError(f"{label}响应过大")
                return HttpResponse(
                    status=getattr(response, "status", 200),
                    headers=response.headers,
                    body=body,
                )
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError(f"{label}失败（HTTP {exc.code}）") from None
        except urllib.error.URLError:
            raise TaskError(f"{label}网络失败或超时") from None
        except TimeoutError:
            raise TaskError(f"{label}超时") from None


class OrdersParser(HTMLParser):
    """提取上游页面中订单号与续期状态，不保存或输出整页内容。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.saw_orders_marker = False
        self.server_depth = 0
        self.action_depth = 0
        self.server_parts: list[str] = []
        self.action_parts: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = set(attr.get("class", "").split())
        if attr.get("id") == "kc2_order_customer_orders_tab_content_1" or (
            "kc2_order_table" in classes
        ):
            self.saw_orders_marker = True
        if tag == "tr":
            self.in_row = True
            self.server_parts = []
            self.action_parts = []
            self.server_depth = 0
            self.action_depth = 0
            return
        if not self.in_row:
            return
        if self.server_depth:
            self.server_depth += 1
        elif "td-z1-sp1-kc" in classes:
            self.server_depth = 1
        if self.action_depth:
            self.action_depth += 1
        elif "kc2_order_action_container" in classes:
            self.action_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self.in_row:
            return
        if tag == "tr":
            server = " ".join("".join(self.server_parts).split())
            action = " ".join("".join(self.action_parts).split())
            if server:
                self.rows.append((server, action))
            self.in_row = False
            self.server_depth = 0
            self.action_depth = 0
            return
        if self.server_depth:
            self.server_depth -= 1
        if self.action_depth:
            self.action_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.server_depth:
            self.server_parts.append(data)
        if self.action_depth:
            self.action_parts.append(data)


def parse_account_object(value: Any, position: int) -> Account:
    if not isinstance(value, dict):
        raise ConfigError(f"第 {position} 个账号必须是 JSON 对象")

    def pick(*names: str) -> str:
        for name in names:
            candidate = value.get(name)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    account = Account(
        username=pick("username", "user", "email"),
        password=pick("password", "pass"),
        mailparser_dl_url_id=pick("mailparser_dl_url_id", "mailparser_id"),
        captcha_userid=pick("userid", "captcha_userid"),
        captcha_apikey=pick("apikey", "captcha_apikey"),
    )
    missing = [
        label
        for label, value_text in (
            ("username", account.username),
            ("password", account.password),
            ("mailparser_dl_url_id", account.mailparser_dl_url_id),
            ("userid", account.captcha_userid),
            ("apikey", account.captcha_apikey),
        )
        if not value_text
    ]
    if missing:
        raise ConfigError(f"第 {position} 个账号缺少字段：{', '.join(missing)}")
    return account


def load_accounts() -> tuple[list[Account], list[str], str]:
    canonical = os.getenv("EUSERV_ACCOUNTS")
    legacy = os.getenv("EUSERV")
    raw = canonical if canonical is not None else legacy
    source = "EUSERV_ACCOUNTS" if canonical is not None else "EUSERV"
    if raw is None or not raw.strip():
        return [], ["未配置必需环境变量 EUSERV_ACCOUNTS"], source

    entries: list[Any] = []
    stripped = raw.strip()
    if source == "EUSERV" and stripped.startswith(("[", "{")):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            entries = decoded
        elif isinstance(decoded, dict) and isinstance(decoded.get("EUSERV"), list):
            entries = decoded["EUSERV"]
        elif isinstance(decoded, dict):
            entries = [decoded]
    if not entries:
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append(ConfigError(f"第 {line_number} 行不是有效 JSON"))

    accounts: list[Account] = []
    errors: list[str] = []
    for position, entry in enumerate(entries, start=1):
        if isinstance(entry, ConfigError):
            errors.append(str(entry))
            continue
        try:
            accounts.append(parse_account_object(entry, position))
        except ConfigError as exc:
            errors.append(str(exc))
    if not entries and not errors:
        errors.append(f"{source} 中没有非空账号")
    return accounts, errors, source


def parse_captcha_answer(result: Any) -> str:
    if not isinstance(result, str) or not result.strip():
        raise TaskError("验证码服务未返回识别结果")
    text = result.strip()
    demo_match = re.search(r"RESULT\s+IS\s*.\s*(.*?)\s*.", text, re.IGNORECASE)
    if demo_match:
        text = demo_match.group(1).strip()
    arithmetic = re.fullmatch(r"\s*(\d+)\s*([xX+\-])\s*(\d+)\s*", text)
    if not arithmetic:
        return text
    left, operator, right = arithmetic.groups()
    left_number, right_number = int(left), int(right)
    if operator in {"x", "X"}:
        return str(left_number * right_number)
    if operator == "+":
        return str(left_number + right_number)
    return str(left_number - right_number)


class EUservRunner:
    def __init__(self, account: Account, timeout: float, pin_wait: float):
        self.account = account
        self.timeout = timeout
        self.pin_wait = pin_wait
        self.client = HttpClient(timeout)
        self.headers = {"Origin": "https://www.euserv.com", "User-Agent": USER_AGENT}

    def _session_id(self, response: HttpResponse) -> str:
        for cookie in self.client.cookies:
            if cookie.name == "PHPSESSID" and cookie.value:
                return cookie.value
        cookie_header = response.headers.get("Set-Cookie", "")
        match = re.search(r"PHPSESSID=([A-Za-z0-9]{10,128})", cookie_header)
        if not match:
            raise TaskError("登录页未建立有效会话")
        return match.group(1)

    def _solve_captcha(self) -> str:
        image = self.client.request(
            "GET",
            CAPTCHA_IMAGE_URL,
            headers=self.headers,
            max_bytes=MAX_IMAGE_BYTES,
            label="验证码图片请求",
        )
        solver = HttpClient(self.timeout)
        solved = solver.request(
            "POST",
            CAPTCHA_SOLVE_URL,
            json_body={
                "userid": self.account.captcha_userid,
                "apikey": self.account.captcha_apikey,
                "case": "lower",
                "mode": "default",
                "data": base64.b64encode(image.body).decode("ascii"),
            },
            max_bytes=MAX_JSON_BYTES,
            label="验证码识别请求",
        ).json()
        if not isinstance(solved, dict):
            raise TaskError("验证码服务响应结构异常")
        answer = parse_captcha_answer(solved.get("result"))
        if len(answer) > 64:
            raise TaskError("验证码识别结果长度异常")

        query = urllib.parse.urlencode(
            {
                "username": self.account.captcha_userid,
                "apikey": self.account.captcha_apikey,
            }
        )
        usage = solver.request(
            "GET",
            f"{CAPTCHA_USAGE_URL}?{query}",
            max_bytes=MAX_JSON_BYTES,
            label="验证码用量查询",
        ).json()
        if isinstance(usage, list) and usage and isinstance(usage[0], dict):
            date = str(usage[0].get("date", "未知"))[:32]
            count = str(usage[0].get("count", "未知"))[:16]
            log(f"验证码服务用量：日期 {date}，次数 {count}")
        else:
            log("⚠️ 验证码用量响应结构异常，不影响本次识别")
        return answer

    def login(self) -> tuple[str, str]:
        initial = self.client.request(
            "GET", BASE_URL, headers=self.headers, label="EUserv 登录页请求"
        )
        session_id = self._session_id(initial)
        response = self.client.request(
            "POST",
            BASE_URL,
            headers=self.headers,
            form={
                "email": self.account.username,
                "password": self.account.password,
                "form_selected_language": "en",
                "Submit": "Login",
                "subaction": "login",
                "sess_id": session_id,
            },
            label="EUserv 登录请求",
        )
        page = response.text()
        success_markers = ("Hello", "Confirm or change your customer data here")
        if any(marker in page for marker in success_markers):
            return session_id, page
        captcha_prompt = "To finish the login process please solve the following captcha."
        if captcha_prompt not in page:
            raise TaskError("登录失败，请检查账号信息或页面是否已变更")
        log("需要验证码，正在调用 TrueCaptcha")
        answer = self._solve_captcha()
        verified = self.client.request(
            "POST",
            BASE_URL,
            headers=self.headers,
            form={
                "subaction": "login",
                "sess_id": session_id,
                "captcha_code": answer,
            },
            label="验证码提交请求",
        ).text()
        if captcha_prompt in verified or not any(
            marker in verified for marker in success_markers
        ):
            raise TaskError("验证码校验或登录失败")
        return session_id, verified

    def get_servers(self, session_id: str, page: str | None = None) -> dict[str, bool]:
        if page is None:
            page = self.client.request(
                "GET",
                f"{BASE_URL}?{urllib.parse.urlencode({'sess_id': session_id})}",
                headers=self.headers,
                label="服务器列表请求",
            ).text()
        parser = OrdersParser()
        parser.feed(page)
        parser.close()
        if not parser.saw_orders_marker and not parser.rows:
            raise TaskError("服务器列表页面结构异常或登录状态已失效")
        return {
            order_id: "Contract extension possible from" not in action
            for order_id, action in parser.rows
        }

    def _mailparser_pin(self) -> str:
        response = HttpClient(self.timeout).request(
            "GET",
            MAILPARSER_BASE_URL
            + urllib.parse.quote(self.account.mailparser_dl_url_id, safe=""),
            max_bytes=MAX_JSON_BYTES,
            label="Mailparser PIN 请求",
        ).json()
        try:
            pin = str(response[0]["pin"]).strip()
        except (KeyError, IndexError, TypeError):
            raise TaskError("Mailparser 未返回 PIN") from None
        if not re.fullmatch(r"\d{6}", pin):
            raise TaskError("Mailparser 返回的 PIN 格式无效")
        return pin

    def renew(self, session_id: str, order_id: str) -> None:
        headers = {
            "Origin": "https://support.euserv.com",
            "Referer": BASE_URL,
            "User-Agent": USER_AGENT,
        }
        self.client.request(
            "POST",
            BASE_URL,
            headers=headers,
            form={
                "Submit": "Extend contract",
                "sess_id": session_id,
                "ord_no": order_id,
                "subaction": "choose_order",
                "choose_order_subaction": "show_contract_details",
            },
            label="续期详情请求",
        )
        self.client.request(
            "POST",
            BASE_URL,
            headers=headers,
            form={
                "sess_id": session_id,
                "subaction": "show_kc2_security_password_dialog",
                "prefix": "kc2_customer_contract_details_extend_contract_",
                "type": "1",
            },
            label="续期 PIN 触发请求",
        )
        log(f"PIN 已触发，等待 {self.pin_wait:g} 秒后读取 Mailparser")
        time.sleep(self.pin_wait)
        pin = self._mailparser_pin()
        log("已取得并校验 6 位 PIN（内容已隐藏）")
        token_response = self.client.request(
            "POST",
            BASE_URL,
            headers=headers,
            form={
                "auth": pin,
                "sess_id": session_id,
                "subaction": "kc2_security_password_get_token",
                "prefix": "kc2_customer_contract_details_extend_contract_",
                "type": "1",
                "ident": f"kc2_customer_contract_details_extend_contract_{order_id}",
            },
            max_bytes=MAX_JSON_BYTES,
            label="续期令牌请求",
        ).json()
        try:
            if token_response["rs"] != "success":
                raise TaskError("续期令牌业务状态失败")
            token = str(token_response["token"]["value"])
        except (KeyError, TypeError):
            raise TaskError("续期令牌响应结构异常") from None
        if not token:
            raise TaskError("续期令牌为空")
        self.client.request(
            "POST",
            BASE_URL,
            headers=headers,
            form={
                "sess_id": session_id,
                "ord_id": order_id,
                "subaction": "kc2_customer_contract_details_extend_contract_term",
                "token": token,
            },
            label="续期提交请求",
        )
        time.sleep(5)
        current = self.get_servers(session_id)
        if current.get(order_id, False):
            raise TaskError("续期提交后复查仍显示可续期")

    def run(self, account_index: int) -> AccountResult:
        started = time.monotonic()
        stats = Stats()
        try:
            stage_started = time.monotonic()
            log(f"账号 {account_index}｜阶段 1/3 登录")
            session_id, page = self.login()
            log(f"✅ 阶段 1 完成，耗时 {time.monotonic() - stage_started:.2f} 秒")

            stage_started = time.monotonic()
            log(f"账号 {account_index}｜阶段 2/3 获取服务器列表")
            servers = self.get_servers(session_id, page)
            stats.total = len(servers)
            log(
                f"✅ 阶段 2 完成，检测到 {len(servers)} 台服务器，"
                f"耗时 {time.monotonic() - stage_started:.2f} 秒"
            )

            stage_started = time.monotonic()
            log(f"账号 {account_index}｜阶段 3/3 检查并续期")
            for server_index, (order_id, eligible) in enumerate(servers.items(), start=1):
                if not eligible:
                    stats.already += 1
                    log(f"☑️ 服务器 {server_index} 当前无需续期")
                    continue
                try:
                    self.renew(session_id, order_id)
                    stats.success += 1
                    log(f"✅ 服务器 {server_index} 续期成功并通过复查")
                except TaskError as exc:
                    stats.failed += 1
                    log(f"❌ 服务器 {server_index} 续期失败：{exc}")
            log(f"阶段 3 完成，耗时 {time.monotonic() - stage_started:.2f} 秒")
            ok = stats.failed == 0
            message = "全部服务器检查完成" if ok else "存在续期失败的服务器"
        except TaskError as exc:
            stats.failed += 1
            ok = False
            message = str(exc)
            log(f"❌ 账号 {account_index} 失败：{message}")
        except Exception:
            # 不展示可能包含 URL、表单或响应内容的底层异常，且不阻断后续账号。
            stats.failed += 1
            ok = False
            message = "发生未预期的内部错误，已安全终止本账号"
            log(f"❌ 账号 {account_index} 失败：{message}")
        stats.total = max(
            stats.total,
            stats.success + stats.already + stats.skipped + stats.failed,
        )
        elapsed = time.monotonic() - started
        log(
            f"账号 {account_index} 统计：总任务 {stats.total}，成功 {stats.success}，"
            f"已完成 {stats.already}，跳过 {stats.skipped}，失败 {stats.failed}，"
            f"耗时 {elapsed:.2f} 秒"
        )
        return AccountResult(ok=ok, stats=stats, message=message)


def selector_allows_notification() -> bool:
    selectors = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selectors is None:
        return True
    if not selectors.strip():
        return False
    patterns = [part for part in re.split(r"[,;\s]+", selectors.strip()) if part]
    for pattern in patterns:
        if pattern == "*":
            return True
        if any(fnmatch.fnmatch(name, pattern) for name in SCRIPT_NAMES):
            return True
    return False


def notification_enabled() -> bool:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    return selector_allows_notification()


def notification_candidates() -> Iterable[Path]:
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        yield Path(notify_dir) / "notify.py"
    yield Path("/ql/data/scripts/notify.py")
    yield Path("/ql/scripts/notify.py")


def load_notify_send(path: Path) -> Callable[[str, str], Any] | None:
    try:
        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        send = getattr(module, "send", None)
        return send if callable(send) else None
    except Exception:
        return None


def send_notification(body: str, dry_run: bool) -> str:
    if not notification_enabled():
        return "disabled"
    if dry_run:
        log("⏭️ dry-run 为保证完全断网，通知仅生成摘要而不投递")
        return "dry-run-skipped"
    try:
        import notify  # type: ignore

        send = getattr(notify, "send", None)
        if callable(send):
            send(TASK_NAME, body)
            return "sent-python-module"
    except Exception:
        pass
    for path in notification_candidates():
        if not path.is_file():
            continue
        send = load_notify_send(path)
        if send is None:
            continue
        try:
            send(TASK_NAME, body)
            return "sent-python-file"
        except Exception:
            return "failed"
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    js_candidates = []
    if notify_dir:
        js_candidates.append(Path(notify_dir) / "sendNotify.js")
    js_candidates.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )
    node = shutil.which("node")
    if node:
        for path in js_candidates:
            if not path.is_file():
                continue
            try:
                completed = subprocess.run(
                    [node, str(path), TASK_NAME, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                return "sent-javascript" if completed.returncode == 0 else "failed"
            except (OSError, subprocess.TimeoutExpired):
                return "failed"
    return "unavailable"


def main() -> int:
    start_wall = now_text()
    start_monotonic = time.monotonic()
    dry_run = env_flag("EUSERV_DRY_RUN")
    print("=" * 64)
    print(f"{TASK_NAME}｜任务开始")
    print("=" * 64)
    log(f"开始时间：{start_wall}")
    log(f"运行模式：{'DRY-RUN（完全断网）' if dry_run else 'LIVE'}")

    accounts, config_errors, source = load_accounts()
    configured_account_total = len(accounts) + len(config_errors)
    log(f"账号来源：{source}；有效账号数：{len(accounts)}；配置错误数：{len(config_errors)}")
    for error in config_errors:
        log(f"❌ 配置错误：{error}")

    account_success = 0
    account_failed = len(config_errors)
    total_stats = Stats(total=len(config_errors), failed=len(config_errors))
    if dry_run:
        for index, _account in enumerate(accounts, start=1):
            log(f"账号 {index}｜阶段 1/3 配置字段检查：✅ 完整")
            log(f"账号 {index}｜阶段 2/3 网络请求计划：⏭️ 已禁止")
            log(f"账号 {index}｜阶段 3/3 续期副作用：⏭️ 已禁止")
            log(
                f"账号 {index} 统计：总任务 1，成功 1，已完成 0，跳过 0，失败 0，耗时 0.00 秒"
            )
            account_success += 1
            total_stats.total += 1
            total_stats.success += 1
    else:
        try:
            timeout = bounded_float_env(
                "EUSERV_HTTP_TIMEOUT", DEFAULT_TIMEOUT, 3.0, 120.0
            )
            pin_wait = bounded_float_env(
                "EUSERV_PIN_WAIT_SECONDS", 15.0, 0.0, 300.0
            )
        except ConfigError as exc:
            config_errors.append(str(exc))
            failed_due_global_config = len(accounts) or 1
            account_failed += failed_due_global_config
            total_stats.total += failed_due_global_config
            total_stats.failed += failed_due_global_config
            log(f"❌ 配置错误：{exc}")
            accounts = []
        for index, account in enumerate(accounts, start=1):
            print("-" * 64)
            log(f"开始处理账号 {index}/{len(accounts)}")
            result = EUservRunner(account, timeout, pin_wait).run(index)
            total_stats.add(result.stats)
            if result.ok:
                account_success += 1
            else:
                account_failed += 1

    accounts_total = configured_account_total
    if accounts_total == 0:
        account_failed = 1
        accounts_total = 1
        total_stats.total += 1
        total_stats.failed += 1
        config_errors.append("没有可处理的账号")
    business_ok = account_failed == 0 and bool(accounts)
    status = "success" if business_ok else "failure"
    elapsed = time.monotonic() - start_monotonic
    finish_wall = now_text()
    print("=" * 64)
    log(
        f"任务统计：账号总数 {accounts_total}，成功 {account_success}，失败 {account_failed}；"
        f"子任务总数 {total_stats.total}，成功 {total_stats.success}，"
        f"已完成 {total_stats.already}，跳过 {total_stats.skipped}，失败 {total_stats.failed}"
    )
    log(f"总耗时：{elapsed:.2f} 秒")
    log(f"完成时间：{finish_wall}")
    log(f"最终状态：{'成功' if business_ok else '失败'}")

    body = (
        f"模式：{'dry-run' if dry_run else 'live'}\n"
        f"账号总数：{accounts_total}\n成功：{account_success}\n失败：{account_failed}\n"
        f"子任务成功：{total_stats.success}\n子任务失败：{total_stats.failed}\n"
        f"最终状态：{'成功' if business_ok else '失败'}"
    )
    notification = send_notification(body, dry_run)
    log(f"通知状态：{notification}")
    summary = {
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": {
            "total": accounts_total,
            "success": account_success,
            "failed": account_failed,
        },
        "tasks": total_stats.as_dict(),
        "notification": notification,
        "started_at": start_wall,
        "finished_at": finish_wall,
        "elapsed_seconds": round(elapsed, 3),
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0 if business_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("❌ 用户中断任务")
        raise SystemExit(130)

