#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: TJUPT每日签到
# cron: 13 9 * * *
#
# 来源：Kevin-Beta/TjuptAutoAttendance main.py（GPL-3.0）
# https://github.com/Kevin-Beta/TjuptAutoAttendance
# 提交：b0d81cb652dcfceacc0c594f620535b30d2082e1
# SPDX-License-Identifier: GPL-3.0-only
#
# Copyright (C) Kevin-Beta / TjuptAutoAttendance contributors
# 本维护版沿用上游 GPL-3.0 许可。
# 你可以通过自由软件基金会发布的 GNU 通用公共许可证第 3 版
# （或你选择的任何后续版本）重新分发和/或修改本程序。
# 本程序的分发希望它有用，但不提供任何担保。
# 完整许可证文本见上游仓库 LICENSE.md。
#
"""TJUPT（天津大学 PT / 北洋园）每日签到 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用站点账号密码登录 https://www.tjupt.org/（可改镜像根地址）
- 访问 attendance.php；识别「今日已签到」或提交验证码答案完成签到
- 通过豆瓣电影 suggest 接口，将验证码海报与选项片名匹配后提交
- 展示页面公开用户名（若返回）以便核对账号
- 移除 cookies.pkl / douban.json 默认落盘、pickle 反序列化、无超时请求与原始响应打印
- 增加逐行多账号、TJUPT_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

TJUPT_ACCOUNTS：每个非空行一个账号，格式 username|password；仅按第一个 | 分割，
密码中后续 | 原样保留。兼容单账号别名 TJUPT_USERNAME + TJUPT_PASSWORD
（仅当规范变量为空时生效）。
TJUPT_BASE_URL：可选站点根地址，默认 https://www.tjupt.org/
TJUPT_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
TJUPT_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：5 9 * * *。不打印密码、Cookie、Token、会话值或原始响应。
本脚本不发布帖子、评论或分享文字。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "b80894cbf3aaac9f",
            "scripts/tjupt_attendance.py",
            "tjupt_attendance.py",
            "candidate.py",
            "main.py",
            "tjupt",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import html
import http.cookiejar
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TITLE = "TJUPT每日签到"
CATALOG_ID = "b80894cbf3aaac9f"
DEFAULT_BASE = "https://www.tjupt.org/"
DEFAULT_TIMEOUT = 20
MAX_BYTES = 1024 * 1024
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
STATES = ("success", "alreadyComplete", "skipped", "failure")
LOGIN_OK_HINT = "logout.php"
ALREADY_HINT = "今日已签到"
SUCCESS_HINT = "签到成功"
DOUBAN_SUGGEST = "https://movie.douban.com/j/subject_suggest"


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def resolve_timeout() -> float:
    raw = env("TJUPT_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("TJUPT_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("TJUPT_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_base_url() -> str:
    raw = env("TJUPT_BASE_URL", DEFAULT_BASE) or DEFAULT_BASE
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SafeError("TJUPT_BASE_URL 必须是不含凭据的 HTTPS 根地址")
    if parsed.username or parsed.password:
        raise SafeError("TJUPT_BASE_URL 不得包含用户名或密码")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise SafeError("TJUPT_BASE_URL 端口无效") from exc
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc.lower(), path, "", "")
    )


def redact(text: str, secrets: List[str]) -> str:
    out = str(text).replace("\r", " ").replace("\n", " ")
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        if len(secret) >= 2:
            out = out.replace(secret, "[敏感值]")
    out = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]", out)
    return "".join(ch for ch in out if ch.isprintable())[:200]


def parse_account_line(line: str) -> Tuple[str, str]:
    text = line.strip()
    if not text:
        raise SafeError("账号行为空")
    if "|" not in text:
        raise SafeError("账号行须为 username|password，且至少包含一个 |")
    username, password = text.split("|", 1)
    username = username.strip()
    password = password.strip()
    if not username or not password:
        raise SafeError("用户名与密码均不能为空")
    if any(ord(ch) < 32 for ch in username) or any(ord(ch) < 32 for ch in password):
        raise SafeError("凭据含非法控制字符")
    return username, password


def load_accounts() -> List[Tuple[str, str]]:
    raw = env("TJUPT_ACCOUNTS")
    source = "TJUPT_ACCOUNTS"
    if not raw:
        username = env("TJUPT_USERNAME")
        password = env("TJUPT_PASSWORD")
        if username or password:
            if not username or not password:
                raise SafeError(
                    "单账号别名须同时提供 TJUPT_USERNAME 与 TJUPT_PASSWORD"
                )
            return [(username, password)]
        raise SafeError(
            "未配置凭据：请设置 TJUPT_ACCOUNTS（每行 username|password）；"
            "兼容别名 TJUPT_USERNAME + TJUPT_PASSWORD"
        )
    accounts: List[Tuple[str, str]] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(parse_account_line(text))
    if not accounts:
        raise SafeError("{} 中没有有效账号行".format(source))
    return accounts


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set) -> None:
        super().__init__()
        self.allowed_hosts = {h.lower() for h in allowed_hosts}

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.hostname is None:
            raise SafeError("拒绝跨站或不安全重定向")
        host = target.hostname.lower()
        if host not in self.allowed_hosts and not any(
            host.endswith("." + allowed) for allowed in self.allowed_hosts
        ):
            # 允许同站 www / 非 www，以及豆瓣主机单独走另一客户端
            raise SafeError("拒绝跨站或不安全重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url
        self.timeout = timeout
        host = urllib.parse.urlsplit(base_url).hostname or ""
        hosts = {host.lower()}
        if host.lower().startswith("www."):
            hosts.add(host.lower()[4:])
        else:
            hosts.add("www." + host.lower())
        self.hosts = hosts
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            SameHostRedirect(hosts),
            urllib.request.HTTPCookieProcessor(self.jar),
        )

    def url(self, path: str) -> str:
        return urllib.parse.urljoin(self.base_url, path.lstrip("/"))

    def _headers(
        self, *, referer: Optional[str] = None, form: bool = False
    ) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close",
        }
        if referer:
            headers["Referer"] = referer
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return headers

    def request(
        self,
        url: str,
        *,
        data: Optional[bytes] = None,
        referer: Optional[str] = None,
        allow_hosts: Optional[set] = None,
        as_json: bool = False,
    ):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SafeError("拒绝访问非 HTTPS 地址")
        host = parsed.hostname.lower()
        allowed = allow_hosts or self.hosts
        if host not in allowed and not any(
            host.endswith("." + item) for item in allowed
        ):
            raise SafeError("拒绝访问非目标站点地址")
        method = "POST" if data is not None else "GET"
        request = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(referer=referer, form=data is not None),
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                final_url = response.geturl()
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise SafeError("响应过大")
                charset = response.headers.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if as_json:
                    try:
                        return status, final_url, json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise SafeError("豆瓣响应不是有效 JSON") from exc
                if int(status) < 200 or int(status) >= 400:
                    raise SafeError("HTTP 状态异常")
                return status, final_url, text
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raise SafeError("HTTP 请求失败（状态 {}）".format(exc.code)) from exc
        except urllib.error.URLError:
            raise SafeError("网络请求失败或超时") from None
        except TimeoutError:
            raise SafeError("网络请求超时") from None
        except Exception:
            raise SafeError("请求过程异常") from None


def extract_identity(page: str, secrets: List[str]) -> Optional[str]:
    patterns = (
        r'欢迎[您你]，?\s*<a[^>]*>([^<>]{1,40})</a>',
        r'欢迎[您你]，?\s*([^<>\r\n]{1,40})',
        r'class=["\'][^"\']*username[^"\']*["\'][^>]*>([^<>]{1,40})<',
        r'<a\b[^>]*href=["\'][^"\']*userdetails\.php\?id=\d+["\'][^>]*>([^<>]{1,40})</a>',
    )
    phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    for pattern in patterns:
        match = re.search(pattern, page, re.I | re.S)
        if not match:
            continue
        name = plain(match.group(1))
        if not name or len(name) > 40:
            continue
        if any(secret and secret in name for secret in secrets):
            continue
        if phone.search(name):
            continue
        if re.search(r"cookie|token|session|password|登录|簽到|签到", name, re.I):
            continue
        return name
    return None


def looks_logged_in(page: str) -> bool:
    return LOGIN_OK_HINT in page


def looks_logged_out(page: str, final_url: str) -> bool:
    if "login.php" in final_url.lower():
        return True
    if looks_logged_in(page):
        return False
    return "takelogin.php" in page.lower() or 'name="username"' in page.lower()


def extract_poster_id(url_or_html: str) -> Optional[str]:
    match = re.search(r"/(p\d+)\.", url_or_html)
    return match.group(1) if match else None


def extract_captcha(page: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    image_match = re.search(
        r'(?:class=["\'][^"\']*captcha[^"\']*["\'][\s\S]{0,800}?|attendance[\s\S]{0,400}?)'
        r'<img[^>]+src=["\']([^"\']+)["\']',
        page,
        re.I,
    )
    if not image_match:
        image_match = re.search(r'<img[^>]+src=["\']([^"\']*?/p\d+\.[^"\']+)["\']', page, re.I)
    if not image_match:
        raise SafeError("未找到签到验证码图片，页面结构可能已变更")
    captcha_image = html.unescape(image_match.group(1))
    captcha_image_id = extract_poster_id(captcha_image)
    if not captcha_image_id:
        raise SafeError("验证码图片标识解析失败")

    options: List[Tuple[str, str, str]] = []
    for match in re.finditer(
        r'<input[^>]*name=["\']answer["\'][^>]*value=["\']([^"\']+)["\'][^>]*/?>'
        r'\s*([^<>]+)',
        page,
        re.I,
    ):
        value = html.unescape(match.group(1))
        title = plain(match.group(2))
        id_match = re.search(r"&(\d+)$", value) or re.search(r"&amp;(\d+)$", match.group(1))
        option_id = id_match.group(1) if id_match else ""
        if title:
            options.append((value, option_id, title))
    if not options:
        # 兼容 value 含 &amp; 且标签后紧跟片名
        for match in re.finditer(
            r'name=["\']answer["\'][^>]*value=["\']([^"\']+)["\'][^>]*>\s*([^<]+)',
            page,
            re.I,
        ):
            value = html.unescape(match.group(1))
            title = plain(match.group(2))
            id_match = re.search(r"&(\d+)$", value)
            option_id = id_match.group(1) if id_match else ""
            if title:
                options.append((value, option_id, title))
    if not options:
        raise SafeError("未找到验证码选项，页面结构可能已变更")
    return captcha_image_id, options


def douban_poster_id(client: Client, title: str, cache: Dict[str, Optional[str]]) -> Optional[str]:
    if title in cache:
        return cache[title]
    time.sleep(random.random() * 2)
    query = urllib.parse.urlencode({"q": title})
    url = "{}?{}".format(DOUBAN_SUGGEST, query)
    # 豆瓣使用独立 opener，避免站点 Cookie 外泄
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://movie.douban.com/",
            "Connection": "close",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=client.timeout) as response:
            payload = response.read(16384 + 1)
            if len(payload) > 16384:
                raise SafeError("豆瓣响应过大")
            data = json.loads(payload.decode("utf-8", errors="replace"))
    except SafeError:
        cache[title] = None
        raise
    except Exception:
        cache[title] = None
        raise SafeError("豆瓣查询失败或超时") from None
    if not isinstance(data, list) or not data:
        cache[title] = None
        return None
    first = data[0]
    if not isinstance(first, dict):
        cache[title] = None
        return None
    img = first.get("img")
    if not isinstance(img, str):
        cache[title] = None
        return None
    poster = extract_poster_id(img)
    cache[title] = poster
    return poster


def login(client: Client, username: str, password: str) -> None:
    client.request(client.url("login.php"))
    body = urllib.parse.urlencode(
        {"username": username, "password": password}
    ).encode("utf-8")
    _, _, text = client.request(
        client.url("takelogin.php"),
        data=body,
        referer=client.url("login.php"),
    )
    if not looks_logged_in(text):
        raise SafeError("登录失败：未检测到有效登录态")


def attend_once(
    client: Client,
    username: str,
    password: str,
    secrets: List[str],
    douban_cache: Dict[str, Optional[str]],
) -> Tuple[str, Optional[str], str]:
    status, final_url, text = client.request(client.url("attendance.php"))
    if looks_logged_out(text, final_url):
        log("需要重新登录")
        login(client, username, password)
        status, final_url, text = client.request(client.url("attendance.php"))
        if looks_logged_out(text, final_url):
            raise SafeError("登录后仍无法访问签到页")

    identity = extract_identity(text, secrets)
    if ALREADY_HINT in text:
        return "alreadyComplete", identity, "今日已签到"

    captcha_image_id, options = extract_captcha(text)
    matches: List[Tuple[str, str, str]] = []
    for value, option_id, title in options:
        poster_id = douban_poster_id(client, title, douban_cache)
        if poster_id and poster_id == captcha_image_id:
            matches.append((value, option_id, title))
            log("匹配到验证码选项：片名已脱敏统计，海报标识一致")

    if len(matches) == 0:
        raise SafeError("未能匹配到唯一验证码选项")
    if len(matches) > 1:
        raise SafeError("匹配到多个验证码选项，拒绝盲提交")

    form = urllib.parse.urlencode(
        {"answer": matches[0][0], "submit": "提交"}
    ).encode("utf-8")
    _, _, result = client.request(
        client.url("attendance.php"),
        data=form,
        referer=client.url("attendance.php"),
    )
    identity = extract_identity(result, secrets) or identity
    if SUCCESS_HINT in result:
        return "success", identity, "签到成功"
    if ALREADY_HINT in result:
        return "alreadyComplete", identity, "今日已签到"
    raise SafeError("响应未包含可核验的签到成功或已签到消息")


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
        "main.py",
        "tjupt_attendance.py",
        "candidate.py",
        "scripts/tjupt_attendance.py",
        "tjupt",
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
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


class AccountResult:
    def __init__(self, number: int) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""


def run_account(
    result: AccountResult,
    username: str,
    password: str,
    base_url: str,
    timeout: float,
    dry_run: bool,
    douban_cache: Dict[str, Optional[str]],
) -> None:
    secrets = [username, password]
    stages = [
        (1, "登录站点"),
        (2, "执行签到（含验证码匹配）"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项".format(
            result.number, total_stages
        )
    )
    client: Optional[Client] = None
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total_stages, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                client = Client(base_url, timeout)
                login(client, username, password)
                result.stats["success"] += 1
                log(
                    "{} 登录态已核验；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                assert client is not None
                # 有限重试，与上游 5 次意图一致，但不打印原始响应
                last_error = "签到未确认"
                outcome = None
                identity = None
                message = ""
                for attempt in range(1, 6):
                    try:
                        outcome, identity, message = attend_once(
                            client, username, password, secrets, douban_cache
                        )
                        break
                    except SafeError as error:
                        last_error = str(error)
                        if attempt < 5:
                            log(
                                "{} 第 {} 次尝试未成功，准备重试".format(
                                    ICONS["warning"], attempt
                                )
                            )
                            time.sleep(random.random() * 2)
                        else:
                            raise SafeError(last_error) from error
                if outcome is None:
                    raise SafeError(last_error)
                if identity:
                    result.identity = identity
                    log("账号 {} 官方身份：{}".format(result.number, identity))
                else:
                    log(
                        "账号 {}：页面未返回公开身份，使用序号标识".format(
                            result.number
                        )
                    )
                if outcome == "alreadyComplete":
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    result.message = message
                    log("{} {}".format(ICONS["alreadyComplete"], message))
                else:
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = message
                    log("{} {}".format(ICONS["success"], message))
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total_stages
                    )
                )
            result.status = "failure"
            result.message = redact(str(error), secrets)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    result.message,
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
            result.message = "未预期本地错误"
            log(
                "{} 账号 {} 阶段 {} 失败：未预期本地错误，详情已抑制；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    time.monotonic() - tick,
                )
            )
            return
    if dry_run:
        result.status = "dry-run"
        result.stats["success"] = 0
    elif result.status not in {"success", "alreadyComplete"}:
        if result.stats["failure"] == 0 and result.stats["alreadyComplete"] == 0:
            result.status = "success"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total_stages,
            result.stats["success"],
            result.stats["alreadyComplete"],
            result.stats["skipped"],
            result.stats["failure"],
            elapsed,
        )
    )


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("TJUPT_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Tuple[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    base_url = DEFAULT_BASE
    config_error: Optional[str] = None
    douban_cache: Dict[str, Optional[str]] = {}

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("TJUPT_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        base_url = resolve_base_url()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；站点根：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                base_url,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, (username, password) in enumerate(accounts_data, 1):
            account = AccountResult(number)
            results.append(account)
            run_account(
                account,
                username,
                password,
                base_url,
                timeout,
                dry_run,
                douban_cache,
            )
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in results if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in results if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in results if item.status == "failure"),
        "dry-run": sum(1 for item in results if item.status == "dry-run"),
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(item.stats[key] for item in results) for key in STATES}
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
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态：{}".format(
            finished_at, elapsed, notification, final_label
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
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
