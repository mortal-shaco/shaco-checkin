#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Leaflow 签到
# cron: 34 18 * * *
# SPDX-License-Identifier: MIT
# Maintained standalone version derived from agluo/ql-script-hub,
# archive/leaflow_checkin.pyleaflow_checkin.py (commit a8d39b9), MIT licensed.

"""Leaflow daily check-in with newline-delimited multi-account support.

Required environment:
  LEAFLOW_COOKIE  One complete browser Cookie header per non-empty line.

Obtain it by signing in at https://checkin.leaflow.net in a browser, opening
Developer Tools -> Network, reloading the page, selecting a request to that
site, and copying the value of the request's ``Cookie`` header. Treat it like a
password. The script never prints it.

Optional environment:
  LEAFLOW_DRY_RUN=1       Validate configuration and simulate without network.
  LEAFLOW_TIMEOUT=20      Per-request timeout in seconds (1..120).
  LEAFLOW_RETRIES=3       Attempts per account (1..5).
  LEAFLOW_RETRY_DELAY=3   Seconds between attempts (0..60).
  LEAFLOW_MAX_DELAY=0     Random per-account delay window (0..3600 seconds).
  LEAFLOW_BASE=https://checkin.leaflow.net
  QINGLONG_NOTIFY=1       青龙汇总通知开关，0/false/no/off 关闭。
  QINGLONG_NOTIFY_DIR     可选，青龙 notify.py 所在目录。

通知：正式运行结束时发现 notify.send 或青龙标准目录的 notify.py，
通知失败不改变业务退出码。预演仅在控制台生成通知内容，不加载或调用通知模块，
确保完全断网。每行一个完整 Cookie；不能用 & 或 @ 分隔账号。
兼容上游 LEAFFLOW_BASE、TIMEOUT、RETRY_TIMES、RETRY_DELAY、
RANDOM_SIGNIN、MAX_RANDOM_DELAY；维护版参数优先，默认随机窗口仍为 0。
NOTIFY_ON_ALREADY 控制已签到账号明细；任务汇总通知始终受 QINGLONG_NOTIFY 控制。
DEBUG_MODE 只显示脱敏阶段信息，不保存响应。
HTTP_PROXY/HTTPS_PROXY 由标准库读取，代理地址不会记录。
"""

from __future__ import annotations

import html
import json
import importlib.util
import contextlib
import io
from datetime import datetime
from pathlib import Path
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


DEFAULT_BASE = "https://checkin.leaflow.net"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
TRUTHY = {"1", "true", "yes", "on"}


@dataclass
class Config:
    cookies: List[str]
    dry_run: bool
    base: str
    timeout: int
    retries: int
    retry_delay: int
    max_delay: int


@dataclass
class Result:
    status: str
    message: str
    amount: float = 0.0
    identity: str = ""


class HiddenInputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "input":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        if values.get("type", "").lower() != "hidden" or not values.get("name"):
            return
        self.fields[values["name"]] = values.get("value", "")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    aliases = {"LEAFLOW_TIMEOUT": "TIMEOUT", "LEAFLOW_RETRIES": "RETRY_TIMES",
               "LEAFLOW_RETRY_DELAY": "RETRY_DELAY", "LEAFLOW_MAX_DELAY": "MAX_RANDOM_DELAY"}
    raw = os.getenv(name, os.getenv(aliases.get(name, name), str(default))).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def load_config() -> Config:
    # Newlines are the only account delimiter. Cookie values may legitimately
    # contain '&' or '@', so splitting on either would corrupt credentials.
    cookies = [line.strip() for line in os.getenv("LEAFLOW_COOKIE", "").splitlines() if line.strip()]
    if not cookies:
        raise ValueError("LEAFLOW_COOKIE is required (one account per non-empty line)")

    base = os.getenv("LEAFLOW_BASE", os.getenv("LEAFFLOW_BASE", DEFAULT_BASE)).strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("LEAFLOW_BASE must be an HTTPS origin without embedded credentials")
    if parsed.path or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("LEAFLOW_BASE must not contain a path, query, or fragment")

    max_delay = env_int("LEAFLOW_MAX_DELAY", 0, 0, 3600)
    if "LEAFLOW_MAX_DELAY" not in os.environ and "RANDOM_SIGNIN" in os.environ:
        max_delay = (env_int("MAX_RANDOM_DELAY", 3600, 0, 3600)
                     if os.getenv("RANDOM_SIGNIN", "").lower() == "true" else 0)
    return Config(
        cookies=cookies,
        dry_run=os.getenv("LEAFLOW_DRY_RUN", "").strip().lower() in TRUTHY,
        base=base,
        timeout=env_int("LEAFLOW_TIMEOUT", 20, 1, 120),
        retries=env_int("LEAFLOW_RETRIES", 3, 1, 5),
        retry_delay=env_int("LEAFLOW_RETRY_DELAY", 3, 0, 60),
        max_delay=max_delay,
    )


def hidden_fields(document: str) -> Dict[str, str]:
    parser = HiddenInputParser()
    try:
        parser.feed(document)
    except Exception:
        # A malformed page is handled later as an unverified business result.
        return {}
    return parser.fields


def visible_text(document: str) -> str:
    cleaned = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", document, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()


def extract_reward(document: str) -> float:
    # 上游明确要求排除历史记录，避免把过去的金额记作今日奖励。
    document = re.sub(r'<div\b[^>]*class=["\'][^"\']*history[^"\']*["\'][^>]*>.*?</div>',
                      " ", document, flags=re.I | re.S)
    text = visible_text(document).split("签到历史", 1)[0]
    patterns = (
        r"(?:今日|今天|本次).*?获得.*?([0-9]+(?:\.[0-9]+)?)\s*元",
        r"签到成功.*?获得.*?([0-9]+(?:\.[0-9]+)?)\s*元",
        r"今日签到.*?([0-9]+(?:\.[0-9]+)?)\s*元",
        r"成功.*?奖励.*?([0-9]+(?:\.[0-9]+)?)\s*元",
        r"恭喜.*?获得.*?([0-9]+(?:\.[0-9]+)?)\s*元",
        r"\+\s*([0-9]+(?:\.[0-9]+)?)\s*元",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            amount = float(match.group(1))
            if 0 < amount <= 10:
                return amount
    return 0.0


def parse_business_result(document: str) -> Result:
    if not document.strip():
        return Result("unknown", "empty response")
    text = visible_text(document)
    lowered = text.lower()

    if any(re.search(pattern, text, re.I) for pattern in (
        r"请登录", r"未登录", r"登录失效", r"please\s+log\s*in", r"session\s+expired"
    )):
        return Result("invalid", "login session is invalid; update LEAFLOW_COOKIE")

    amount = extract_reward(document)
    if any(re.search(pattern, text, re.I) for pattern in (
        r"今日已签到", r"已连续签到", r"明天再来", r"已签到", r"already\s+checked"
    )):
        message = "already checked in today"
        if amount:
            message += f"; today's reward={amount:g} CNY"
        return Result("already", message, amount)

    if any(re.search(pattern, text, re.I) for pattern in (
        r"签到成功", r"获得奖励", r"领取成功", r"恭喜", r"check-?in\s+success"
    )):
        message = "check-in succeeded"
        if amount:
            message += f"; reward={amount:g} CNY"
        return Result("success", message, amount)

    if "error" in lowered or "错误" in text:
        return Result("failed", "service returned an error page")
    return Result("unknown", "response did not contain a recognized business-success marker")


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlparse(req.full_url), urlparse(newurl)
        if (new.scheme, new.netloc) != (old.scheme, old.netloc):
            raise RuntimeError("cross-origin redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class IdentityParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.identity = ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for field in ("data-nickname", "data-username", "data-display-name", "data-public-uid"):
            value = values.get(field)
            if value and not self.identity:
                self.identity = value


def public_identity(document, cookie):
    parser = IdentityParser()
    parser.feed(document)
    identity = parser.identity
    if not identity:
        match = re.search(r"(?:昵称|用户名|显示名称|公开UID)\s*[:：]\s*([^<\r\n]+)", document)
        if match:
            identity = html.unescape(match.group(1)).strip()
    # Identity is displayed unchanged unless it contains a credential or phone number.
    secrets = [item.split("=", 1)[1].strip() for item in cookie.split(";") if "=" in item]
    if any(value and value in identity for value in secrets) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", identity):
        return ""
    if any(ord(char) < 32 or ord(char) == 127 for char in identity):
        return ""
    return identity


def stage(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}")


def request_text(
    opener: object,
    url: str,
    cookie: str,
    timeout: int,
    data: Optional[bytes] = None,
    referer: Optional[str] = None,
) -> Tuple[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie,
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if referer:
        headers["Referer"] = referer
    request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with opener.open(request, timeout=timeout) as response:  # type: ignore[attr-defined]
        status = getattr(response, "status", 0)
        if status != 200:
            raise RuntimeError(f"unexpected HTTP status {status}")
        final_url = response.geturl()
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise RuntimeError("response too large")
        body = raw.decode(charset, errors="replace")
    return final_url, body


def check_in_once(config: Config, cookie: str) -> Result:
    opener = build_opener(SameOriginRedirect())
    home_url = f"{config.base}/"
    try:
        request_started = time.monotonic()
        stage("阶段 2.1 获取签到页面")
        final_url, home = request_text(opener, home_url, cookie, config.timeout)
        stage(f"阶段 2.1 页面 HTTP 200，耗时 {time.monotonic() - request_started:.2f} 秒")
        identity = public_identity(home, cookie)
        if identity:
            stage(f"官方账号身份：{identity}")
        if "login" in urlparse(final_url).path.lower():
            return Result("invalid", "request redirected to login; update LEAFLOW_COOKIE")

        initial = parse_business_result(home)
        initial.identity = identity
        if initial.status in {"already", "invalid"}:
            # Avoid a needless state-changing POST when today's completion is
            # already explicitly visible on the authenticated homepage.
            return initial

        form = hidden_fields(home)
        form["checkin"] = ""
        request_started = time.monotonic()
        stage("阶段 2.2 提交签到表单")
        final_post_url, posted = request_text(
            opener,
            f"{config.base}/index.php",
            cookie,
            config.timeout,
            data=urlencode(form).encode("utf-8"),
            referer=home_url,
        )
        stage(f"阶段 2.2 表单 HTTP 200，耗时 {time.monotonic() - request_started:.2f} 秒")
        if "login" in urlparse(final_post_url).path.lower():
            return Result("invalid", "登录会话失效，请更新 Cookie", identity=identity)
        result = parse_business_result(posted)
        result.identity = public_identity(posted, cookie) or identity
        if result.status in {"success", "already", "invalid"}:
            return result

        # Some deployments only expose the resulting state on the homepage.
        request_started = time.monotonic()
        stage("阶段 2.3 核验签到状态")
        final_verify_url, verified = request_text(opener, home_url, cookie, config.timeout)
        stage(f"阶段 2.3 核验 HTTP 200，耗时 {time.monotonic() - request_started:.2f} 秒")
        if "login" in urlparse(final_verify_url).path.lower():
            return Result("invalid", "登录会话失效，请更新 Cookie", identity=identity)
        verification = parse_business_result(verified)
        verification.identity = public_identity(verified, cookie) or identity
        if verification.status in {"already", "invalid"}:
            return verification
        return result
    except HTTPError as exc:
        if exc.code == 403:
            return Result("failed", "HTTP 403; request rejected by service risk controls")
        return Result("failed", f"HTTP {exc.code}")
    except (TimeoutError, URLError) as exc:
        reason = getattr(exc, "reason", exc)
        return Result("failed", f"network error: {type(reason).__name__}")
    except Exception as exc:
        return Result("failed", f"request error: {type(exc).__name__}")


def run_account(config: Config, cookie: str, account_number: int) -> Result:
    if (any(ord(char) < 32 or ord(char) == 127 for char in cookie)
            or not all("=" in field and field.split("=", 1)[0].strip()
                       for field in cookie.split(";") if field.strip())):
        return Result("invalid", "Cookie 格式无效，请使用完整名称=值请求头")
    if config.dry_run:
        return Result("success", "DRY-RUN verified: network and check-in mutation skipped")

    last = Result("failed", "no attempt made")
    for attempt in range(1, config.retries + 1):
        last = check_in_once(config, cookie)
        if last.status in {"success", "already", "invalid"}:
            return last
        stage(f"阶段 2 账号 {account_number} 尝试 {attempt}/{config.retries}：{last.message}")
        if attempt < config.retries:
            print(
                f"ACCOUNT index={account_number} attempt={attempt} status=retrying "
                f"reason={last.message}"
            )
            if config.retry_delay:
                time.sleep(config.retry_delay)
    return Result("failed", f"{last.message}; exhausted {config.retries} attempt(s)")


def send_summary(body, dry_run):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        stage("阶段 3 通知：全局开关关闭")
        return "disabled"
    if dry_run:
        stage("阶段 3 通知：断网预演，仅生成本地汇总，未加载通知模块")
        stage(body)
        return "dry-run-local"
    try:
        # Do not expose notifier output/exception text; it may contain credentials.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                from notify import send
            except ImportError:
                paths = []
                if os.getenv("QINGLONG_NOTIFY_DIR"):
                    paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
                paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
                send = None
                for path in paths:
                    if not path.is_file():
                        continue
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    send = getattr(module, "send", None)
                    if callable(send):
                        break
                if not callable(send):
                    raise ImportError("notifier unavailable")
            delivered = send("Leaflow 每日签到", body)
            if delivered is False:
                raise RuntimeError("notification failed")
        stage("阶段 3 通知：发送完成")
        return "sent"
    except BaseException:
        stage("阶段 3 通知：不可用或发送失败，保留业务退出码")
        return "unavailable-or-failed"


def finish(started, mode, total, succeeded, already, failed, skipped, reward, code, details):
    dry_run = mode == "dry-run"
    status = ("configuration-error" if code == 2 else "partial-failure" if failed and succeeded
              else "failure" if failed else "dry-run" if dry_run else "success")
    body = (f"状态：{status}；账号总数：{total}；成功数：{succeeded}；失败数：{failed}；"
            f"已完成：{already}；预演跳过：{skipped}；奖励：{reward:g} 元")
    if details:
        body += "\n" + "\n".join(details)
    notify_started = time.monotonic()
    notification = send_summary(body, dry_run)
    stage(f"阶段 3 耗时 {time.monotonic() - notify_started:.2f} 秒")
    print("-" * 50)
    stage(f"账号统计：总数 {total}，成功 {succeeded}，失败 {failed}")
    stage(f"子任务统计：总数 {total}，成功 {succeeded - already - skipped}，已完成 {already}，跳过 {skipped}，失败 {failed}")
    elapsed = time.monotonic() - started
    stage(f"总耗时 {elapsed:.2f} 秒；完成时间 {datetime.now():%Y-%m-%d %H:%M:%S}；通知状态 {notification}；最终状态 {status}")
    # Preserve the maintained candidate's SUMMARY format and dry-run success counts.
    print(f"SUMMARY total={total} succeeded={succeeded} failed={failed} "
          f"reward_cny={reward:g} dry_run={'true' if dry_run else 'false'}")
    record = {"application": "leaflow", "mode": mode, "status": status,
              "total": total, "succeeded": succeeded, "failed": failed,
              "already": already, "skipped": skipped, "reward_cny": reward,
              "notification": notification, "elapsed_seconds": round(elapsed, 3),
              "exit_code": code}
    print("TASK_SUMMARY=" + json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    return code


def main() -> int:
    started = time.monotonic()
    mode = "dry-run" if os.getenv("LEAFLOW_DRY_RUN", "").strip().lower() in TRUTHY else "live"
    count = len([line for line in os.getenv("LEAFLOW_COOKIE", "").splitlines() if line.strip()])
    print("=" * 50)
    stage("Leaflow 每日签到（维护版）")
    stage(f"开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}；模式 {mode}；账号数量 {count}")
    stage("阶段 1 配置校验")
    try:
        config = load_config()
    except ValueError as exc:
        print(f"CONFIG status=failed reason={exc}", file=sys.stderr)
        stage(f"阶段 1 配置错误：{exc}；耗时 {time.monotonic() - started:.2f} 秒")
        return finish(started, mode, count, 0, 0, count, 0, 0.0, 2, ["配置校验失败，请检查参数"])

    stage(f"阶段 1 配置校验通过；耗时 {time.monotonic() - started:.2f} 秒")
    print(f"START application=leaflow mode={mode} accounts={len(config.cookies)}")
    if config.dry_run:
        print("DRY-RUN no network requests will be made and no check-in state will change")

    schedule = []
    for index, cookie in enumerate(config.cookies, 1):
        delay = 0 if config.dry_run else random.randint(0, config.max_delay)
        schedule.append((delay, index, cookie))
    schedule.sort(key=lambda item: (item[0], item[1]))
    succeeded = failed = already = skipped = 0
    total_reward = 0.0
    details = []
    for delay, index, cookie in schedule:
        remaining = delay - (time.monotonic() - started)
        if remaining > 0:
            print(f"ACCOUNT index={index} status=waiting delay_seconds={int(remaining + 0.999)}")
            stage(f"阶段 2 账号 {index} 等待随机窗口 {remaining:.0f} 秒")
            time.sleep(remaining)
        account_started = time.monotonic()
        stage(f"阶段 2 账号 {index} 开始")
        result = run_account(config, cookie, index)
        ok = result.status in {"success", "already"}
        if ok:
            succeeded += 1
            total_reward += result.amount
        else:
            failed += 1
        already += int(result.status == "already")
        skipped += int(config.dry_run and ok)
        print(f"ACCOUNT index={index} status={result.status} message={result.message}")
        label = result.identity or f"账号 {index}"
        stage(f"阶段 2 {label} 结果：{result.status}；{result.message}")
        stage(f"{label} 子任务总数 1，成功 {int(ok and result.status != 'already' and not config.dry_run)}，"
              f"已完成 {int(result.status == 'already')}，跳过 {int(config.dry_run and ok)}，"
              f"失败 {int(not ok)}，耗时 {time.monotonic() - account_started:.2f} 秒")
        if result.status != "already" or os.getenv("NOTIFY_ON_ALREADY", "true").lower() == "true":
            details.append(f"{label}：{result.status}；{result.message}")
    return finish(started, mode, len(config.cookies), succeeded, already, failed,
                  skipped, total_reward, 1 if failed else 0, details)


if __name__ == "__main__":
    raise SystemExit(main())
