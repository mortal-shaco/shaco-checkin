#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Bailanjo 自动签到
# cron: 31 2 * * *
"""Bailanjo 自动签到维护版。

上游来源：https://github.com/LinVireo/bailanjo-auto-check-in
上游文件：bailanjo_checkin.py、ql_bailanjo.sh
许可证：MIT（保留上游项目归属与许可声明）

本文件不使用 Playwright、Chromium 或安装脚本。它通过 HTTPS 获取页面、保留
Cookie 和隐藏表单字段，并提交账号查询与签到表单。若站点改为仅能由 JavaScript
执行且页面不再暴露表单、链接或 fetch 端点，本脚本会明确失败，不会把未知响应
误报为签到成功。

账号配置：
  BAILANJO_ACCOUNTS（必填）：每个非空行一个账号，格式为“账号|密码”。只在第一
  个竖线处分割，因此密码中后续的竖线会被保留。不要用 & 或 @ 分隔账号。

兼容配置：
  BAILANJO_ACCOUNT 与 BAILANJO_PASSWORD 可继续提供单账号；命令行
  --account/--password 也保留。新配置应优先使用 BAILANJO_ACCOUNTS。

离线预演：
  BAILANJO_DRY_RUN=1。预演不会访问业务站点、推送服务或青龙通知脚本。
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
        _ql_notify_identities = ('e052c233e8ebcd95', 'scripts/bailanjo_checkin.py', 'bailanjo_checkin.py', 'bailanjo_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
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
from datetime import datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


TASK_NAME = "Bailanjo 自动签到"
CATALOG_ID = "e052c233e8ebcd95"
USER_URL = "https://bailanjo.top/user"
DEFAULT_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 512 * 1024
DRY_RUN_ENV = "BAILANJO_DRY_RUN"
ACCOUNT_ENV = "BAILANJO_ACCOUNTS"
BEIJING = timezone(timedelta(hours=8))

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
FAILURE_WORDS = (
    "账号或密码错误",
    "密码错误",
    "账号不存在",
    "登录失败",
    "查询失败",
    "签到失败",
    "操作失败",
)
SIGN_SUCCESS_WORDS = ("签到成功", "余额增加", "签到完成")
SIGN_ALREADY_WORDS = ("已签到", "已经签到", "重复签到", "今日签过")


def now_text() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def clock_text() -> str:
    return datetime.now(BEIJING).strftime("%H:%M:%S")


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f}s"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return default


def safe_timeout() -> float:
    raw = os.getenv("BAILANJO_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        return min(60.0, max(3.0, float(raw)))
    except ValueError:
        return DEFAULT_TIMEOUT


def compact_text(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def redact_text(value: Any, secrets: Sequence[str] = ()) -> str:
    text = compact_text(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    text = re.sub(
        r"(?i)\b(cookie|token|session|authorization|device[_ -]?id)\s*[:=]\s*[^\s,，;；]+",
        lambda match: f"{match.group(1)}=[凭据已隐藏]",
        text,
    )
    return text


def safe_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        return f"网络错误（{type(reason).__name__ if reason else '连接失败'}）"
    if isinstance(exc, TimeoutError):
        return "请求超时"
    return compact_text(type(exc).__name__, 80)


def strip_html(source: str) -> str:
    source = re.sub(r"(?is)<script\b.*?</script>", " ", source)
    source = re.sub(r"(?is)<style\b.*?</style>", " ", source)
    return compact_text(unescape(re.sub(r"(?s)<[^>]+>", " ", source)), 20000)


def first_mapping_value(data: Any, keys: Iterable[str]) -> str:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, (str, int, float)) and str(value).strip():
                return compact_text(value)
        for value in data.values():
            found = first_mapping_value(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = first_mapping_value(value, keys)
            if found:
                return found
    return ""


@dataclass(frozen=True)
class Account:
    username: str
    password: str


@dataclass
class FormControl:
    name: str
    value: str = ""
    kind: str = "text"
    placeholder: str = ""


@dataclass
class FormInfo:
    action: str
    method: str
    controls: List[FormControl] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    @property
    def description(self) -> str:
        return " ".join(self.labels + [item.placeholder for item in self.controls])


@dataclass
class LinkInfo:
    href: str
    text: str


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: List[FormInfo] = []
        self.links: List[LinkInfo] = []
        self.loose_controls: List[FormControl] = []
        self._form: Optional[FormInfo] = None
        self._button_text: Optional[List[str]] = None
        self._link_href: Optional[str] = None
        self._link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "form":
            self._form = FormInfo(values.get("action", ""), values.get("method", "get").lower())
            self.forms.append(self._form)
        elif tag == "input":
            control = FormControl(
                name=values.get("name", ""),
                value=values.get("value", ""),
                kind=values.get("type", "text").lower(),
                placeholder=values.get("placeholder", ""),
            )
            if self._form is not None:
                self._form.controls.append(control)
            else:
                self.loose_controls.append(control)
        elif tag == "button":
            self._button_text = []
            if self._form is not None and values.get("value"):
                self._form.labels.append(values["value"])
        elif tag == "a":
            self._link_href = values.get("href", "")
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._button_text is not None:
            self._button_text.append(data)
        if self._link_href is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "button" and self._button_text is not None:
            label = compact_text(" ".join(self._button_text), 100)
            if label and self._form is not None:
                self._form.labels.append(label)
            self._button_text = None
        elif tag == "a" and self._link_href is not None:
            self.links.append(LinkInfo(self._link_href, compact_text(" ".join(self._link_text), 100)))
            self._link_href = None
            self._link_text = []
        elif tag == "form":
            self._form = None


@dataclass
class HttpResult:
    status: int
    url: str
    body: str
    content_type: str


class HttpClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(
        self,
        url: str,
        method: str = "GET",
        fields: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_bytes: int = MAX_RESPONSE_BYTES,
    ) -> HttpResult:
        if urllib.parse.urlsplit(url).scheme.lower() != "https":
            raise RuntimeError("拒绝非 HTTPS 请求")
        request_headers = {
            "User-Agent": "Mozilla/5.0 (Qinglong Bailanjo Maintained Script)",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        }
        request_headers.update(headers or {})
        payload: Optional[bytes] = None
        method = method.upper()
        if json_body is not None:
            payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        elif fields is not None:
            encoded = urllib.parse.urlencode(fields).encode("utf-8")
            if method == "GET":
                separator = "&" if urllib.parse.urlsplit(url).query else "?"
                url = url + separator + encoded.decode("ascii")
            else:
                payload = encoded
                request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                final_url = response.geturl()
                if urllib.parse.urlsplit(final_url).scheme.lower() != "https":
                    raise RuntimeError("服务器重定向到非 HTTPS 地址")
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise RuntimeError("响应内容超过安全上限")
                charset = response.headers.get_content_charset() or "utf-8"
                body = raw.decode(charset, errors="replace")
                return HttpResult(
                    status=int(getattr(response, "status", 200)),
                    url=final_url,
                    body=body,
                    content_type=response.headers.get("Content-Type", ""),
                )
        except urllib.error.HTTPError:
            raise


def parse_page(source: str) -> PageParser:
    parser = PageParser()
    parser.feed(source)
    parser.close()
    return parser


def choose_control(controls: Sequence[FormControl], password: bool) -> Optional[FormControl]:
    if password:
        for item in controls:
            marker = f"{item.name} {item.placeholder}".lower()
            if item.kind == "password" or any(word in marker for word in ("password", "passwd", "pwd", "密码")):
                return item
        return None
    for item in controls:
        marker = f"{item.name} {item.placeholder}".lower()
        if item.kind in {"text", "email", "tel"} and any(
            word in marker for word in ("account", "username", "user", "email", "账号", "用户")
        ):
            return item
    for item in controls:
        if item.kind in {"text", "email", "tel"}:
            return item
    return None


def form_payload(form: FormInfo) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for item in form.controls:
        if item.name and item.kind not in {"submit", "button", "reset", "file"}:
            payload[item.name] = item.value
    return payload


def find_query_form(page: PageParser, base_url: str) -> Tuple[FormInfo, FormControl, FormControl]:
    candidates = list(page.forms)
    if page.loose_controls:
        candidates.append(FormInfo(base_url, "post", page.loose_controls, ["查询"]))
    ranked: List[Tuple[int, FormInfo, FormControl, FormControl]] = []
    for form in candidates:
        password = choose_control(form.controls, password=True)
        account = choose_control(form.controls, password=False)
        if not account or not password or not account.name or not password.name:
            continue
        desc = form.description.lower()
        score = 10 + (4 if "查询" in desc else 0) + (2 if "登录" in desc else 0)
        ranked.append((score, form, account, password))
    if not ranked:
        raise RuntimeError("页面未暴露可提交的账号密码表单")
    _, form, account, password = max(ranked, key=lambda item: item[0])
    return form, account, password


def submit_form(
    client: HttpClient,
    base_url: str,
    form: FormInfo,
    updates: Dict[str, str],
    require_post: bool = False,
) -> HttpResult:
    payload = form_payload(form)
    payload.update(updates)
    target = urllib.parse.urljoin(base_url, form.action or base_url)
    method = form.method.upper()
    if method not in {"GET", "POST"}:
        raise RuntimeError(f"不支持的表单方法 {method}")
    if require_post and method != "POST":
        raise RuntimeError("账号密码表单不是 POST，已拒绝把凭据放入 URL")
    return client.request(target, method=method, fields=payload, headers={"Referer": base_url})


def response_json(result: HttpResult) -> Any:
    body = result.body.lstrip()
    if "json" not in result.content_type.lower() and not body.startswith(("{", "[")):
        return None
    try:
        return json.loads(result.body)
    except (TypeError, ValueError):
        return None


def response_message(result: HttpResult) -> str:
    data = response_json(result)
    if data is not None:
        message = first_mapping_value(data, ("message", "msg", "detail", "notice", "toast"))
        if message:
            return message
    alert = re.search(r"(?is)alert\s*\(\s*['\"](.{1,240}?)['\"]\s*\)", result.body)
    if alert:
        return compact_text(unescape(alert.group(1)))
    return strip_html(result.body)


def extract_user_info(result: HttpResult) -> Dict[str, str]:
    data = response_json(result)
    text = strip_html(result.body)
    info = {"uid": "", "balance": "", "diamonds": ""}
    if data is not None:
        info["uid"] = first_mapping_value(data, ("uid", "userId", "user_id", "publicUid"))
        info["balance"] = first_mapping_value(data, ("balance", "money", "amount"))
        info["diamonds"] = first_mapping_value(data, ("diamonds", "diamond", "diamondCount"))
    patterns = {
        "uid": r"(?i)\bUID\s*[:：]\s*([^\s<,，;；]{1,80})",
        "balance": r"余额\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
        "diamonds": r"(?:累计获得的)?钻石(?:数量)?\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
    }
    for key, pattern in patterns.items():
        if not info[key]:
            match = re.search(pattern, text)
            if match:
                info[key] = compact_text(match.group(1), 80)
    return info


def parse_added_amount(message: str) -> str:
    match = re.search(r"余额(?:增加|加)[^\d]*([0-9]+(?:\.[0-9]+)?)元", message or "")
    return match.group(1) if match else ""


def query_is_verified(result: HttpResult, info: Dict[str, str]) -> bool:
    message = response_message(result)
    if any(word in message for word in FAILURE_WORDS):
        return False
    if any(info.values()):
        return True
    data = response_json(result)
    if isinstance(data, dict):
        code = data.get("code", data.get("status"))
        return code in (0, 200, "0", "200", True, "success")
    return False


def discover_sign_action(result: HttpResult) -> Tuple[str, str, Optional[FormInfo]]:
    page = parse_page(result.body)
    for form in page.forms:
        if "签到" in form.description:
            return "form", result.url, form
    for link in page.links:
        if "签到" in link.text and link.href and not link.href.lower().startswith("javascript:"):
            return "get", urllib.parse.urljoin(result.url, link.href), None

    # 兼容页面通过简单 fetch('/path', {method: 'POST'}) 触发签到的情况；只接受
    # 页面自身公开、同源、HTTPS 的固定字符串端点，不执行或解释任意 JavaScript。
    for match in re.finditer(r"(?is)fetch\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*\{(.{0,600}?)\})?\s*\)", result.body):
        before = result.body[max(0, match.start() - 400) : match.end() + 200]
        if "签到" not in before:
            continue
        url = urllib.parse.urljoin(result.url, match.group(1))
        if urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(result.url).netloc:
            continue
        options = match.group(2) or ""
        method_match = re.search(r"(?i)method\s*:\s*['\"](GET|POST)['\"]", options)
        return (method_match.group(1).lower() if method_match else "get"), url, None
    raise RuntimeError("查询成功，但页面未暴露可验证的签到表单或端点")


def sign_is_verified(result: HttpResult) -> Tuple[bool, bool, str]:
    message = response_message(result)
    if any(word in message for word in FAILURE_WORDS):
        return False, False, compact_text(message)
    if any(word in message for word in SIGN_ALREADY_WORDS):
        return True, True, compact_text(message)
    if any(word in message for word in SIGN_SUCCESS_WORDS):
        return True, False, compact_text(message)
    data = response_json(result)
    if isinstance(data, dict):
        code = data.get("code", data.get("status"))
        explicit = first_mapping_value(data, ("signed", "checkin", "checkedIn", "success"))
        if code in (0, 200, "0", "200", True, "success") and str(explicit).lower() in TRUE_VALUES:
            return True, False, "接口明确返回签到成功"
    return False, False, "响应未包含可验证的签到成功状态"


def execute_account(account: Account, timeout: float) -> Dict[str, Any]:
    client = HttpClient(timeout)
    initial = client.request(USER_URL)
    if initial.status < 200 or initial.status >= 300:
        raise RuntimeError(f"用户页返回 HTTP {initial.status}")
    page = parse_page(initial.body)
    form, account_control, password_control = find_query_form(page, initial.url)
    queried = submit_form(
        client,
        initial.url,
        form,
        {account_control.name: account.username, password_control.name: account.password},
        require_post=True,
    )
    info_before = extract_user_info(queried)
    if not query_is_verified(queried, info_before):
        raise RuntimeError("账号查询响应未通过业务成功校验")
    action, target, sign_form = discover_sign_action(queried)
    if action == "form" and sign_form is not None:
        signed = submit_form(client, queried.url, sign_form, {})
    else:
        signed = client.request(target, method=action.upper(), headers={"Referer": queried.url})
    ok, already, message = sign_is_verified(signed)
    message = redact_text(message, (account.username, account.password))
    if not ok:
        raise RuntimeError(message)
    info_after = extract_user_info(signed)
    info = {key: info_after.get(key) or info_before.get(key) or "" for key in ("uid", "balance", "diamonds")}
    return {
        "ok": True,
        "already": already,
        "signed": not already,
        "message": message,
        "added": parse_added_amount(message),
        **info,
    }


def parse_accounts(args: argparse.Namespace) -> List[Account]:
    canonical = os.getenv(ACCOUNT_ENV, "")
    accounts: List[Account] = []
    errors: List[str] = []
    if canonical.strip():
        for number, raw_line in enumerate(canonical.splitlines(), start=1):
            if not raw_line.strip():
                continue
            if "|" not in raw_line:
                errors.append(f"第 {number} 个非空行缺少字段分隔符 |")
                continue
            username, password = raw_line.split("|", 1)
            if not username.strip() or not password:
                errors.append(f"第 {number} 个非空行的账号或密码为空")
                continue
            accounts.append(Account(username.strip(), password))
    else:
        username = args.account or os.getenv("BAILANJO_ACCOUNT", "")
        password = args.password or os.getenv("BAILANJO_PASSWORD", "")
        if username or password:
            if not username or not password:
                errors.append("兼容变量 BAILANJO_ACCOUNT 与 BAILANJO_PASSWORD 必须同时提供")
            else:
                accounts.append(Account(username, password))
    if errors:
        raise ValueError("；".join(errors))
    if not accounts:
        raise ValueError(f"未配置 {ACCOUNT_ENV}，每行应为 账号|密码")
    return accounts


def public_identity(result: Dict[str, Any], index: int) -> str:
    uid = compact_text(result.get("uid"), 80)
    return f"UID {uid}" if uid else f"账号 {index}"


def machine_account_record(index: int, result: Dict[str, Any]) -> Dict[str, Any]:
    # 延续上游逐账号 JSON 输出，但只保留非凭据字段。
    return {
        "index": index,
        "ok": bool(result.get("ok")),
        "message": redact_text(result.get("message")),
        "balance": compact_text(result.get("balance"), 80),
        "uid": compact_text(result.get("uid"), 80),
        "diamonds": compact_text(result.get("diamonds"), 80),
        "added": compact_text(result.get("added"), 80),
        "signed": bool(result.get("signed")),
        "already": bool(result.get("already")),
    }


def notification_selected() -> bool:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch not in TRUE_VALUES | {"auto", ""}:
        print(f"[{clock_text()}] ⚠️ QINGLONG_NOTIFY 值无法识别，按关闭处理")
        return False
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    identities = (
        CATALOG_ID,
        "candidate.py",
        "bailanjo_checkin.py",
        "checkin/bailanjo_checkin.py",
    )
    return any(selector == "*" or any(fnmatch.fnmatch(identity, selector) for identity in identities) for selector in selectors)


def discover_notify_python() -> List[Path]:
    candidates: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        candidates.append(Path(custom) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    return candidates


def send_qinglong_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_selected():
        return "已关闭"
    if dry_run:
        # no-network dry-run 的优先级高于所有通知配置。
        return "预演模式离线跳过"
    try:
        import notify  # type: ignore

        sender = getattr(notify, "send", None)
        if callable(sender):
            sender(title, body)
            return "notify.py 已调用"
    except (ImportError, AttributeError):
        pass
    except Exception as exc:
        return f"notify.py 失败（{safe_error(exc)}）"

    for path in discover_notify_python():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("bailanjo_ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                return f"{path.name} 已调用"
        except Exception as exc:
            return f"notify.py 失败（{safe_error(exc)}）"

    js_candidates: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        js_candidates.append(Path(custom) / "sendNotify.js")
    js_candidates.extend((Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")))
    node = shutil.which("node")
    if node:
        for path in js_candidates:
            if not path.is_file():
                continue
            try:
                completed = subprocess.run(
                    [node, str(path), title, body],
                    check=False,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return "sendNotify.js 已调用" if completed.returncode == 0 else "sendNotify.js 调用失败"
            except Exception as exc:
                return f"sendNotify.js 失败（{safe_error(exc)}）"
    return "未发现青龙通知组件"


def push_response_ok(channel: str, result: HttpResult) -> bool:
    if channel == "Discord":
        return result.status in (200, 204)
    data = response_json(result)
    if channel == "Telegram":
        return isinstance(data, dict) and data.get("ok") is True
    if channel == "Server酱":
        return result.status == 200 and (not isinstance(data, dict) or data.get("code", 0) in (0, "0"))
    if channel == "PushPlus":
        return isinstance(data, dict) and data.get("code") in (200, "200")
    if channel == "Bark":
        return result.status == 200 and (not isinstance(data, dict) or data.get("code", 200) in (200, "200"))
    if channel == "飞书":
        return isinstance(data, dict) and data.get("code", data.get("StatusCode")) in (0, "0")
    if channel in {"钉钉", "企业微信"}:
        return isinstance(data, dict) and data.get("errcode") in (0, "0")
    return False


def send_legacy_pushes(title: str, body: str, timeout: float, dry_run: bool) -> Tuple[int, int]:
    if dry_run:
        return 0, 0
    configs: List[Tuple[str, str, str, Optional[Dict[str, str]], Optional[Dict[str, Any]]]] = []
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TG_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("TG_USER_ID", "") or os.getenv("TG_CHAT_ID", "")
    if tg_token and tg_chat:
        configs.append(("Telegram", f"https://api.telegram.org/bot{tg_token}/sendMessage", "POST", {"chat_id": tg_chat, "text": body}, None))
    server_key = os.getenv("SERVERCHAN_SENDKEY", "")
    if server_key:
        configs.append(("Server酱", f"https://sctapi.ftqq.com/{server_key}.send", "POST", {"title": title, "desp": body}, None))
    pushplus = os.getenv("PUSHPLUS_TOKEN", "")
    if pushplus:
        configs.append(("PushPlus", "https://www.pushplus.plus/send", "POST", {"token": pushplus, "title": title, "content": body, "template": "markdown"}, None))
    bark = os.getenv("BARK_URL", "").rstrip("/")
    if bark:
        configs.append(("Bark", f"{bark}/{urllib.parse.quote(title, safe='')}/{urllib.parse.quote(body, safe='')}", "GET", None, None))
    webhook_payloads = (
        ("Discord", "DISCORD_WEBHOOK_URL", {"content": body}),
        ("飞书", "FEISHU_WEBHOOK_URL", {"msg_type": "text", "content": {"text": body}}),
        ("钉钉", "DINGTALK_WEBHOOK_URL", {"msgtype": "markdown", "markdown": {"title": title, "text": body}}),
        ("企业微信", "WECHAT_WORK_WEBHOOK_URL", {"msgtype": "markdown", "markdown": {"content": body}}),
    )
    for name, env_name, payload in webhook_payloads:
        url = os.getenv(env_name, "")
        if url:
            configs.append((name, url, "POST", None, payload))
    succeeded = 0
    for name, url, method, fields, payload in configs:
        try:
            client = HttpClient(timeout)
            result = client.request(url, method=method, fields=fields, json_body=payload, max_bytes=64 * 1024)
            ok = push_response_ok(name, result)
        except Exception:
            ok = False
        succeeded += int(ok)
        icon = "✅" if ok else "❌"
        print(f"[{clock_text()}] {icon} {name} 通知{'成功' if ok else '失败'}")
    return succeeded, len(configs)


def build_notification(results: Sequence[Dict[str, Any]], dry_run: bool) -> str:
    success = sum(1 for item in results if item.get("ok"))
    failed = len(results) - success
    already = sum(1 for item in results if item.get("already"))
    mode = "离线预演" if dry_run else "正式执行"
    details: List[str] = []
    for index, item in enumerate(results, start=1):
        identity = public_identity(item, index)
        state = "已签到" if item.get("already") else ("成功" if item.get("ok") else "失败")
        fields = [f"{identity}={state}"]
        if item.get("balance"):
            fields.append(f"余额 {compact_text(item['balance'], 80)}")
        if item.get("added"):
            fields.append(f"增加 {compact_text(item['added'], 80)} 元")
        details.append("、".join(fields))
    suffix = f"；明细：{'；'.join(details)}" if details else ""
    return f"模式：{mode}；账号总数：{len(results)}；成功：{success}；已签到：{already}；失败：{failed}{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bailanjo 自动签到（纯 HTTP 维护版）")
    parser.add_argument("--account", default="", help="兼容单账号输入，推荐改用 BAILANJO_ACCOUNTS")
    parser.add_argument("--password", default="", help="兼容单账号密码输入，推荐改用 BAILANJO_ACCOUNTS")
    parser.add_argument("--headless", action="store_true", help="兼容旧参数；纯 HTTP 版本无需浏览器")
    parser.add_argument("--headed", action="store_true", help="兼容旧参数；纯 HTTP 版本无需浏览器")
    args = parser.parse_args()

    task_started = time.monotonic()
    started_at = now_text()
    dry_run = env_bool(DRY_RUN_ENV)
    timeout = safe_timeout()
    print("=" * 64)
    print(f"{TASK_NAME} | 维护版")
    print(f"开始时间：{started_at}")
    print(f"运行模式：{'离线预演' if dry_run else '正式执行'}")
    print("=" * 64)

    config_error = ""
    try:
        accounts = parse_accounts(args)
    except ValueError as exc:
        accounts = []
        config_error = compact_text(exc)
    print(f"账号数量：{len(accounts)}")

    results: List[Dict[str, Any]] = []
    if config_error:
        print(f"[{clock_text()}] ❌ 配置错误：{config_error}")
    else:
        for index, account in enumerate(accounts, start=1):
            account_started = time.monotonic()
            stats = {"total": 2, "success": 0, "already": 0, "skipped": 0, "failed": 0}
            print(f"\n--- 账号 {index}/{len(accounts)} ---")
            stage = time.monotonic()
            print(f"[{clock_text()}] [1/2] 校验配置与建立会话")
            if dry_run:
                print(f"[{clock_text()}] ✅ 配置格式有效；离线预演不建立网络会话（耗时 {elapsed_text(stage)}）")
                stats["success"] += 1
                stage = time.monotonic()
                print(f"[{clock_text()}] [2/2] 模拟账号查询与签到")
                result = {
                    "ok": True,
                    "already": False,
                    "signed": False,
                    "message": "DRY_RUN_OK：已验证参数和执行路径，未发出网络请求",
                    "balance": "",
                    "uid": "",
                    "diamonds": "",
                    "added": "",
                }
                stats["skipped"] += 1
                print(f"[{clock_text()}] ⏭️ DRY_RUN_OK：业务请求与所有通知均已离线跳过（耗时 {elapsed_text(stage)}）")
            else:
                print(f"[{clock_text()}] ✅ 配置格式有效，准备访问 Bailanjo（耗时 {elapsed_text(stage)}）")
                stats["success"] += 1
                stage = time.monotonic()
                print(f"[{clock_text()}] [2/2] 查询账号并执行签到")
                try:
                    result = execute_account(account, timeout)
                    identity = public_identity(result, index)
                    state = "今日已经签到" if result.get("already") else "签到成功"
                    print(f"[{clock_text()}] {'☑️' if result.get('already') else '✅'} {identity}：{state}（耗时 {elapsed_text(stage)}）")
                    details = []
                    for label, key in (("余额", "balance"), ("累计钻石", "diamonds"), ("本次增加", "added")):
                        if result.get(key):
                            details.append(f"{label}={compact_text(result[key], 80)}")
                    if details:
                        print(f"[{clock_text()}] 结果明细：{'；'.join(details)}")
                    stats["already" if result.get("already") else "success"] += 1
                except Exception as exc:
                    result = {
                        "ok": False,
                        "already": False,
                        "signed": False,
                        "message": safe_error(exc) if not isinstance(exc, RuntimeError) else compact_text(exc),
                        "balance": "",
                        "uid": "",
                        "diamonds": "",
                        "added": "",
                    }
                    stats["failed"] += 1
                    print(f"[{clock_text()}] ❌ 账号 {index} 签到失败：{result['message']}（耗时 {elapsed_text(stage)}）")
            results.append(result)
            print(json.dumps(machine_account_record(index, result), ensure_ascii=False, separators=(",", ":")))
            print(
                f"[{clock_text()}] 账号统计：总任务={stats['total']} 成功={stats['success']} "
                f"已完成={stats['already']} 跳过={stats['skipped']} 失败={stats['failed']} "
                f"耗时={elapsed_text(account_started)}"
            )

    succeeded = sum(1 for item in results if item.get("ok"))
    failed = len(results) - succeeded
    if config_error:
        failed = 1
    body = build_notification(results, dry_run) if not config_error else f"配置错误；账号总数：0；成功：0；失败：1；原因：{config_error}"
    legacy_ok, legacy_total = send_legacy_pushes(TASK_NAME, body, timeout, dry_run)
    notify_status = send_qinglong_notification(TASK_NAME, body, dry_run)
    business_ok = not config_error and bool(results) and failed == 0
    final_status = "DRY_RUN" if dry_run and business_ok else ("SUCCESS" if business_ok else "FAILURE")
    exit_code = 0 if business_ok else (2 if config_error else 1)
    finished_at = now_text()

    print("\n" + "=" * 64)
    print(f"任务统计：账号总数={len(results)} 成功={succeeded} 失败={failed}")
    print(f"子任务统计：签到处理={len(results)} 自定义通知={legacy_ok}/{legacy_total}")
    print(f"总耗时：{elapsed_text(task_started)}")
    print(f"完成时间：{finished_at}")
    print(f"通知状态：{notify_status}")
    print(f"最终状态：{final_status}")
    print("=" * 64)
    summary = {
        "task": "bailanjo_checkin",
        "status": final_status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": len(results),
        "success": succeeded,
        "failed": failed,
        "notification": notify_status,
        "exitCode": exit_code,
        "finishedAt": finished_at,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
