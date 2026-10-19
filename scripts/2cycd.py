#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 2cycd 论坛自动签到
# cron: 0 0 * * *
# SPDX-License-Identifier: MIT
"""
2cycd 论坛自动签到维护版。

维护版有效许可证：MIT（依据导入任务的 effectiveLicense）。

保留的上游原始声明：
name: 2cycd 论坛自动签到
Author: Ripple
Author URI: https://hiripple.com/
Version: 1.0.0
License: GNU General Public License v3.0
License URI: https://www.gnu.org/licenses/gpl-3.0.html
description:
论坛官网：http://www.2cycd.com
每天签到领贡献～

参数说明：
1. 浏览器登录 https://www.2cycd.com/。
2. 打开开发者工具的“网络”面板，刷新页面。
3. 从发往 2cycd.com 的 home.php 或 plugin.php 请求头中复制 Cookie 值。
4. 将每个账号的完整 Cookie 单独写在 CYCD_COOKIE 的一行中。
   兼容旧变量 cycd_cookie；不再使用 & 或 @ 分隔账号，因为它们可能是 Cookie 内容。

可选变量：
- CYCD_DRY_RUN=1：只验证配置和执行流程，完全不访问网络。
- CYCD_FALLBACK_TEXT：一言服务不可用时使用的本地签到文字。
- CYCD_TIMEOUT：单次请求超时秒数，默认 10。
- CYCD_RETRIES：每个账号最多尝试次数，默认 3。
- CYCD_BASE_URL：站点地址，默认 https://www.2cycd.com，仅允许 HTTPS。

cron: 0 0 * * *
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
        _ql_notify_identities = ('00e71cec355af1fb', 'scripts/2cycd.py', '2cycd.py', '2cycd')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


CATALOG_ID = "00e71cec355af1fb"
TASK_NAME = "2cycd 自动签到"
DEFAULT_BASE_URL = "https://www.2cycd.com"
DEFAULT_FALLBACK_TEXT = "记上一笔，hold住我的快乐！"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_TIMEOUT = 8.0
HITOKOTO_MAX_BYTES = 16_384
MAX_SITE_RESPONSE_BYTES = 1_048_576
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}", flush=True)


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f} 秒"


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return value


def load_accounts() -> list[str]:
    raw = os.getenv("CYCD_COOKIE")
    if raw is None or not raw.strip():
        raw = os.getenv("cycd_cookie", "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    for cookie in accounts:
        if "\r" in cookie or "\n" in cookie or any(ord(char) < 32 for char in cookie):
            raise ValueError("Cookie 不得包含控制字符")
        if "=" not in cookie:
            raise ValueError("每行 Cookie 应为浏览器请求头中的完整 key=value 内容")
    return accounts


def validate_base_url() -> str:
    raw = os.getenv("CYCD_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("CYCD_BASE_URL 必须是不含凭据的 HTTPS 地址")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname != "2cycd.com" and not hostname.endswith(".2cycd.com"):
        raise ValueError("CYCD_BASE_URL 必须属于 2cycd.com，避免 Cookie 被发送到其他站点")
    if parsed.query or parsed.fragment:
        raise ValueError("CYCD_BASE_URL 不得包含查询参数或片段")
    return raw


class FormhashParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.value: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if self.value is not None or tag.lower() != "input":
            return
        values = {key.lower(): value for key, value in attrs}
        if values.get("name") == "formhash" and values.get("value"):
            self.value = values["value"]


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise HTTPError(req.full_url, code, "为防止 Cookie 泄漏，已拒绝重定向", headers, fp)


OPENER = build_opener(NoRedirects())


def read_limited(response: Any, limit: int) -> bytes:
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("响应体超过安全大小限制")
    return payload


def decode_response(payload: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w.-]+)", content_type or "", re.IGNORECASE)
    candidates = [match.group(1)] if match else []
    candidates.extend(["utf-8", "gb18030"])
    for charset in candidates:
        try:
            return payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    raise ValueError("响应字符编码无法识别")


def request_text(
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    headers: Optional[dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> str:
    request = Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with OPENER.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError(f"HTTP 状态异常：{status}")
            payload = read_limited(response, max_bytes)
            return decode_response(payload, response.headers.get("Content-Type", ""))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP 请求失败：状态 {exc.code}") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        kind = type(reason).__name__ if reason is not None else "网络错误"
        raise RuntimeError(f"网络请求失败：{kind}") from exc
    except TimeoutError as exc:
        raise RuntimeError("网络请求超时") from exc


def normalize_public_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def local_fallback_text() -> str:
    text = normalize_public_text(os.getenv("CYCD_FALLBACK_TEXT", DEFAULT_FALLBACK_TEXT))
    if not text or len(text) > 280:
        return DEFAULT_FALLBACK_TEXT
    return text


def fetch_public_text(timeout: float) -> tuple[str, str]:
    """Return publishable text and its safe source label; never sends account data."""
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    try:
        raw = request_text(
            HITOKOTO_URL,
            timeout=min(timeout, HITOKOTO_TIMEOUT),
            max_bytes=HITOKOTO_MAX_BYTES,
            headers=headers,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("一言返回了无效 JSON") from exc
        text = normalize_public_text(data.get("hitokoto"))
        author = normalize_public_text(data.get("from_who"))
        source = normalize_public_text(data.get("from"))
        if not text:
            raise ValueError("一言响应缺少正文")
        if author and source:
            result = f"{text} —— {author}《{source}》"
        elif source:
            result = f"{text} ——《{source}》"
        elif author:
            result = f"{text} —— {author}"
        else:
            result = text
        result = normalize_public_text(result)
        if len(result) > 280:
            raise ValueError("一言格式化内容超过 280 字")
        return result, "一言"
    except Exception as exc:
        return local_fallback_text(), f"本地回退（{type(exc).__name__}）"


def parse_formhash(page: str) -> str:
    parser = FormhashParser()
    parser.feed(page)
    value = (parser.value or "").strip()
    if not value or len(value) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise RuntimeError("页面未提供有效 formhash，Cookie 可能已失效")
    return value


def site_headers(base_url: str, cookie: str, *, form: bool = False) -> dict[str, str]:
    parsed = urlparse(base_url)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Cookie": cookie,
        "Host": parsed.netloc,
        "Pragma": "no-cache",
        "Referer": urljoin(base_url + "/", "plugin.php?id=dc_signin"),
        "User-Agent": USER_AGENT,
    }
    if form:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = base_url
    return headers


def perform_signin(cookie: str, base_url: str, timeout: float, content: str) -> tuple[str, str]:
    page_url = urljoin(base_url + "/", "plugin.php?id=dc_signin")
    page = request_text(
        page_url,
        timeout=timeout,
        max_bytes=MAX_SITE_RESPONSE_BYTES,
        headers=site_headers(base_url, cookie),
    )
    formhash = parse_formhash(page)
    payload = urlencode(
        {
            "formhash": formhash,
            "signsubmit": "yes",
            "handlekey": "signin",
            "emotid": "11",
            "referer": page_url,
            "content": content,
        }
    ).encode("utf-8")
    sign_url = urljoin(base_url + "/", "plugin.php?id=dc_signin:sign&inajax=1")
    result = request_text(
        sign_url,
        timeout=timeout,
        max_bytes=MAX_SITE_RESPONSE_BYTES,
        headers=site_headers(base_url, cookie, form=True),
        data=payload,
    )
    if any(marker in result for marker in ("您今日已经签过到", "今日已签到", "已经签到")):
        return "already", "今日已经完成签到"
    if any(marker in result for marker in ("签到成功", "恭喜，签到成功", "恭喜您，签到成功")):
        return "success", "签到成功"
    raise RuntimeError("接口未返回明确的签到成功或已签到标志")


@dataclass
class AccountResult:
    index: int
    status: str
    detail: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.status in {"success", "already", "dry-run"}


def run_account(
    index: int,
    cookie: str,
    *,
    dry_run: bool,
    base_url: str,
    timeout: float,
    retries: int,
) -> AccountResult:
    started = time.monotonic()
    log(f"账号 {index}｜阶段 1/3：校验账号参数")
    log(f"账号 {index}｜✅ Cookie 格式有效，未输出凭据")

    log(f"账号 {index}｜阶段 2/3：准备签到公开内容")
    if dry_run:
        content_source = "本地预演（未访问一言）"
        content = local_fallback_text()
    else:
        content, content_source = fetch_public_text(timeout)
    log(f"账号 {index}｜✅ 内容已准备，来源：{content_source}，长度：{len(content)} 字")

    log(f"账号 {index}｜阶段 3/3：{'预演签到流程' if dry_run else '执行签到'}")
    if dry_run:
        log(f"账号 {index}｜⏭️ dry-run 已跳过全部网络请求和签到副作用")
        duration = time.monotonic() - started
        log(
            f"账号 {index} 统计｜总任务 1｜成功 0｜已完成 0｜跳过 1｜失败 0｜耗时 {duration:.2f} 秒"
        )
        return AccountResult(index, "dry-run", "断网预演通过", duration)

    last_error = "未知错误"
    for attempt in range(1, retries + 1):
        attempt_started = time.monotonic()
        try:
            status, detail = perform_signin(cookie, base_url, timeout, content)
            icon = "☑️" if status == "already" else "✅"
            log(
                f"账号 {index}｜{icon} 第 {attempt}/{retries} 次请求：{detail}｜阶段耗时 {elapsed_text(attempt_started)}"
            )
            duration = time.monotonic() - started
            success = 1 if status == "success" else 0
            already = 1 if status == "already" else 0
            log(
                f"账号 {index} 统计｜总任务 1｜成功 {success}｜已完成 {already}｜跳过 0｜失败 0｜耗时 {duration:.2f} 秒"
            )
            return AccountResult(index, status, detail, duration)
        except Exception as exc:
            last_error = str(exc) or type(exc).__name__
            log(
                f"账号 {index}｜⚠️ 第 {attempt}/{retries} 次请求失败：{last_error}｜阶段耗时 {elapsed_text(attempt_started)}"
            )
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))

    duration = time.monotonic() - started
    log(f"账号 {index}｜❌ 签到失败：{last_error}")
    log(f"账号 {index} 统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 {duration:.2f} 秒")
    return AccountResult(index, "failed", last_error, duration)


def notification_selected() -> tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch not in TRUE_VALUES and switch != "auto":
        return False, "QINGLONG_NOTIFY 值无效，已安全跳过"
    if switch in TRUE_VALUES:
        return True, "全局开关已启用"

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False, "auto 模式下未配置脚本选择列表"
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False, "脚本选择列表为空"
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    candidates = {CATALOG_ID, "candidate.py", "output/candidate.py"}
    for selector in selectors:
        if selector == "*" or any(fnmatch.fnmatch(candidate, selector) for candidate in candidates):
            return True, f"脚本选择器 {selector} 已匹配"
    return False, "当前脚本未被选择"


def load_notify_sender() -> Optional[Callable[[str, str], Any]]:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            return sender
    except Exception:
        pass

    paths: list[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in paths:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_local_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                return sender
        except Exception:
            continue
    return None


def send_notification(body: str) -> str:
    selected, reason = notification_selected()
    if not selected:
        log(f"通知｜⏭️ {reason}")
        return "skipped"
    sender = load_notify_sender()
    if sender is None:
        log("通知｜⚠️ 未找到青龙 notify.py；业务退出码保持不变")
        return "unavailable"
    try:
        sender(TASK_NAME, body)
        log("通知｜✅ 已发送脱敏任务总结")
        return "sent"
    except Exception as exc:
        log(f"通知｜⚠️ 发送失败：{type(exc).__name__}；业务退出码保持不变")
        return "failed"


def emit_final(
    *,
    started_wall: str,
    started_mono: float,
    mode: str,
    results: list[AccountResult],
    configuration_error: Optional[str] = None,
) -> int:
    total = len(results)
    success = sum(item.ok for item in results)
    failed = sum(not item.ok for item in results)
    succeeded_tasks = sum(item.status == "success" for item in results)
    already_tasks = sum(item.status == "already" for item in results)
    skipped_tasks = sum(item.status == "dry-run" for item in results)
    failed_tasks = sum(item.status == "failed" for item in results)
    if configuration_error:
        business_exit = 2
        final_status = "configuration-error"
    elif failed:
        business_exit = 1
        final_status = "partial-failure" if success else "failure"
    else:
        business_exit = 0
        final_status = "dry-run" if mode == "dry-run" else "success"

    notification_body = (
        f"模式：{mode}\n账号总数：{total}\n成功账号：{success}\n失败账号：{failed}\n"
        f"最终状态：{final_status}"
    )
    if configuration_error:
        notification_body += "\n配置检查：失败"
    notify_status = send_notification(notification_body)
    finished = now_text()
    duration = time.monotonic() - started_mono

    print("=" * 56)
    log(f"任务统计｜账号总数 {total}｜成功账号 {success}｜失败账号 {failed}")
    log(
        "子任务统计｜"
        f"成功 {succeeded_tasks}｜已完成 {already_tasks}｜跳过 {skipped_tasks}｜失败 {failed_tasks}"
    )
    log(f"总耗时｜{duration:.2f} 秒")
    log(f"开始时间｜{started_wall}")
    log(f"完成时间｜{finished}")
    log(f"通知状态｜{notify_status}")
    log(f"最终状态｜{'✅' if business_exit == 0 else '❌'} {final_status}")
    print("=" * 56)
    summary = {
        "task": CATALOG_ID,
        "name": TASK_NAME,
        "mode": mode,
        "accounts": {"total": total, "success": success, "failed": failed},
        "tasks": {
            "total": total,
            "success": succeeded_tasks,
            "alreadyComplete": already_tasks,
            "skipped": skipped_tasks,
            "failed": failed_tasks,
        },
        "status": final_status,
        "notification": notify_status,
        "startedAt": started_wall,
        "finishedAt": finished,
        "durationSeconds": round(duration, 3),
        "exitCode": business_exit,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return business_exit


def main() -> int:
    started_mono = time.monotonic()
    started_wall = now_text()
    dry_run = env_flag("CYCD_DRY_RUN")
    mode = "dry-run" if dry_run else "live"
    print("=" * 56)
    print(f"{TASK_NAME}｜维护版", flush=True)
    print("=" * 56)
    log(f"开始时间｜{started_wall}")
    log(f"运行模式｜{mode}")

    try:
        accounts = load_accounts()
        if not accounts:
            raise ValueError("未配置 CYCD_COOKIE；兼容旧变量 cycd_cookie")
        base_url = validate_base_url()
        timeout = bounded_float("CYCD_TIMEOUT", 10.0, 1.0, 60.0)
        retries = bounded_int("CYCD_RETRIES", 3, 1, 5)
    except ValueError as exc:
        log(f"账号数量｜0")
        log(f"❌ 配置错误：{exc}")
        return emit_final(
            started_wall=started_wall,
            started_mono=started_mono,
            mode=mode,
            results=[],
            configuration_error=str(exc),
        )

    log(f"账号数量｜{len(accounts)}")
    log(f"请求策略｜HTTPS、超时 {timeout:g} 秒、最多 {retries} 次尝试、禁止重定向")
    results: list[AccountResult] = []
    for index, cookie in enumerate(accounts, start=1):
        print("-" * 56)
        try:
            result = run_account(
                index,
                cookie,
                dry_run=dry_run,
                base_url=base_url,
                timeout=timeout,
                retries=retries,
            )
        except Exception as exc:
            # No credential or raw response is included in this fallback log.
            duration = time.monotonic() - started_mono
            log(f"账号 {index}｜❌ 未处理异常：{type(exc).__name__}")
            log(f"账号 {index} 统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜耗时 {duration:.2f} 秒")
            result = AccountResult(index, "failed", type(exc).__name__, duration)
        results.append(result)

    return emit_final(
        started_wall=started_wall,
        started_mono=started_mono,
        mode=mode,
        results=results,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已由用户中断。", file=sys.stderr)
        raise SystemExit(130)
