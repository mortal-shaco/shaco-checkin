#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: STC国芯论坛签到
# cron: 36 8 * * *
#
# 来源：klxf/stc-auto-check-in zqlj_sign.py（GPL-3.0）
# https://github.com/klxf/stc-auto-check-in
# 提交：85cdd8b81bbc1e3d9526ff55395cc82d0282c98a
# SPDX-License-Identifier: GPL-3.0-only
#
# 本维护版沿用上游 GPL-3.0 许可。Copyright (C) klxf / stc-auto-check-in contributors。
# 你可以通过自由软件基金会发布的 GNU 通用公共许可证第 3 版（或你选择的任何后续版本）
# 重新分发和/或修改本程序。本程序的分发希望它有用，但不提供任何担保。
# 完整许可证文本见上游仓库 LICENSE。
#
"""STC 国芯论坛（www.stcaimcu.com）Discuz zqlj_sign 每日打卡 - 青龙维护版。

功能清点（相对上游 zqlj_sign.py）：
- 使用已登录 Cookie 访问 plugin.php?id=zqlj_sign 打卡页
- 解析「点击打卡 / 今日已打卡」链接并请求打卡 URL
- 根据页面消息核验打卡成功或今日已打卡
- 展示 Discuz 公开昵称（若页面返回）以便核对账号
- 移除写入本地 HTML 缓存文件、原始响应打印与无超时请求
- 增加逐行多账号、STCAIMCU_DRY_RUN 断网预演、请求超时、时间轴日志、青龙通知与 TASK_SUMMARY

STCAIMCU_COOKIE：每个非空行一个已登录 Cookie（保留分号分隔的键值对）。
兼容上游别名 STCAIMCU_COOKIES / STCAIMCU_Cookies（仅当规范变量为空时生效）。
STCAIMCU_TIMEOUT：单次 HTTPS 请求超时秒数，默认 15，范围 5..60。
STCAIMCU_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求，不声明业务成功。
建议 Cron：30 8 * * *。不打印 Cookie、Token、会话值或原始响应。
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
        _ql_notify_identities = ('aeb184ef4b033ac4', 'scripts/zqlj_sign.py', 'zqlj_sign.py', 'zqlj_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "STC国芯论坛签到"
CATALOG_ID = "aeb184ef4b033ac4"
HOST = "www.stcaimcu.com"
BASE = "https://www.stcaimcu.com/"
PAGE = BASE + "plugin.php?id=zqlj_sign"
DEFAULT_TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
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
SUCCESS_HINTS = (
    "恭喜您，打卡成功",
    "打卡成功",
    "签到成功",
)
ALREADY_HINTS = (
    "您今天已经打过卡了",
    "请勿重复操作",
    "今日已打卡",
    "已经打过卡",
    "已签到",
    "请勿重复签到",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


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
    raw = env("STCAIMCU_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("STCAIMCU_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("STCAIMCU_TIMEOUT 须在 5 到 60 秒之间")
    return value


def validate_cookie(cookie: str) -> str:
    text = cookie.strip()
    if not text:
        raise SafeError("Cookie 为空")
    if "=" not in text:
        raise SafeError("Cookie 格式错误：缺少键值对")
    if any(ord(ch) < 32 or ord(ch) > 255 for ch in text):
        raise SafeError("Cookie 含非法控制字符或非 Latin-1 字节")
    return text


def load_accounts() -> List[str]:
    raw = env("STCAIMCU_COOKIE")
    source = "STCAIMCU_COOKIE"
    if not raw:
        for alias in ("STCAIMCU_COOKIES", "STCAIMCU_Cookies"):
            raw = env(alias)
            if raw:
                source = alias
                break
    if not raw:
        raise SafeError(
            "未配置凭据：请设置 STCAIMCU_COOKIE（每行一个 Cookie）；"
            "兼容别名 STCAIMCU_COOKIES / STCAIMCU_Cookies"
        )
    accounts: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(validate_cookie(text))
    if not accounts:
        raise SafeError("{} 中没有有效账号行".format(source))
    return accounts


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: List[Tuple[str, str, str]] = []
        self._active: Optional[List[Any]] = None
        self.message_chunks: List[str] = []
        self._in_message = False
        self._message_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        mapping = {k: (v or "") for k, v in attrs}
        if tag == "a":
            self._active = [mapping.get("href", ""), mapping.get("class", ""), ""]
        if tag == "div" and mapping.get("id") == "messagetext":
            self._in_message = True
            self._message_depth = 1
        elif self._in_message:
            self._message_depth += 1

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active[2] += data
        if self._in_message and data:
            self.message_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active is not None:
            self.anchors.append(
                (self._active[0], self._active[1], self._active[2])
            )
            self._active = None
        if self._in_message:
            self._message_depth -= 1
            if self._message_depth <= 0:
                self._in_message = False
                self._message_depth = 0


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.netloc.lower() != HOST:
            raise SafeError("拒绝跨站或不安全重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, cookie: str, timeout: float) -> None:
        self.cookie = cookie
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            SameHostRedirect(),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )

    def get(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() != HOST:
            raise SafeError("拒绝访问非目标站点地址")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Referer": PAGE,
                "Cookie": self.cookie,
            },
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                if int(status) != 200:
                    raise SafeError("HTTP 状态异常")
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise SafeError("响应过大")
                charset = response.headers.get_content_charset() or "utf-8"
                return data.decode(charset, errors="replace")
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            raise SafeError("HTTP 请求失败（状态 {}）".format(exc.code)) from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络请求失败") from exc
        except Exception as exc:
            raise SafeError("请求过程异常") from exc


def extract_identity(page: str, cookie: str) -> Optional[str]:
    match = re.search(r'<div\b[^>]*\bid=["\']um["\'][^>]*>(.*?)</div>', page, re.S | re.I)
    if not match:
        match = re.search(
            r'<a\b[^>]*class=["\'][^"\']*\bvwmy\b[^"\']*["\'][^>]*>(.*?)</a>',
            page,
            re.S | re.I,
        )
        if match:
            name = plain(match.group(1))
            if (
                name
                and not re.search(r"\d{11}|cookie|token|session", name, re.I)
                and name not in cookie
            ):
                return name
            return None
        return None
    parser = AnchorParser()
    parser.feed(match.group(1))
    for href, _cls, label in parser.anchors:
        if "mod=space" in href and "uid=" in href:
            name = plain(label)
            if (
                name
                and not re.search(r"\d{11}|cookie|token|session", name, re.I)
                and name not in cookie
            ):
                return name
    return None


def extract_message(page: str) -> str:
    parser = AnchorParser()
    parser.feed(page)
    text = plain("".join(parser.message_chunks))
    if text:
        return text
    match = re.search(
        r'<div\b[^>]*\bid=["\']messagetext["\'][^>]*>(.*?)</div>',
        page,
        re.S | re.I,
    )
    if match:
        return plain(match.group(1))
    return ""


def find_sign_action(page: str) -> Tuple[Optional[str], bool]:
    parser = AnchorParser()
    parser.feed(page)
    for href, cls, label in parser.anchors:
        text = plain(label)
        classes = set(cls.split())
        if text not in {"点击打卡", "今日已打卡"} and "btna" not in classes:
            continue
        if not href:
            continue
        url = urllib.parse.urljoin(BASE, href)
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != HOST
            or parsed.path != "/plugin.php"
            or query.get("id") != ["zqlj_sign"]
        ):
            continue
        already = text == "今日已打卡" or "已经打过卡" in text
        token = query.get("sign", [""])[0]
        if token and not re.fullmatch(r"[0-9a-fA-F]+", token):
            raise SafeError("打卡链接签名格式异常")
        if already:
            return None, True
        if not token:
            # 上游仅要求找到 a.btna 的 href；无 sign 参数时仍允许同源插件链接
            if "sign" not in query and text == "点击打卡":
                return url, False
            continue
        return url, False
    # 兼容上游：div.bm.signbtn.cl 内 a.btna
    block = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bbm\b[^"\']*\bsignbtn\b[^"\']*["\'][^>]*>(.*?)</div>',
        page,
        re.S | re.I,
    )
    if block:
        inner = AnchorParser()
        inner.feed(block.group(1))
        for href, cls, label in inner.anchors:
            text = plain(label)
            if "btna" not in cls.split() and text not in {"点击打卡", "今日已打卡"}:
                continue
            url = urllib.parse.urljoin(BASE, href)
            parsed = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qs(parsed.query)
            if (
                parsed.scheme == "https"
                and parsed.netloc.lower() == HOST
                and parsed.path == "/plugin.php"
                and query.get("id") == ["zqlj_sign"]
            ):
                if text == "今日已打卡":
                    return None, True
                return url, False
    raise SafeError("未找到有效打卡链接，请检查登录状态或页面是否已更新")


def classify_result(message: str, page: str) -> str:
    haystack = "{} {}".format(message, plain(page[:2000]))
    for hint in ALREADY_HINTS:
        if hint in haystack:
            return "alreadyComplete"
    for hint in SUCCESS_HINTS:
        if hint in haystack:
            return "success"
    if message:
        # 有官方消息但无法归类时视为失败，避免把未知文案当成功
        raise SafeError("打卡结果消息无法确认成功：" + message[:80])
    raise SafeError("响应未包含可核验的打卡成功或已打卡消息")


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
        "zqlj_sign.py",
        "candidate.py",
        "scripts/zqlj_sign.py",
        "stcaimcu_zqlj_sign",
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
    result: AccountResult, cookie: str, timeout: float, dry_run: bool
) -> None:
    stages = [
        (1, "读取打卡页及账号身份"),
        (2, "执行打卡"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项".format(
            result.number, total_stages
        )
    )
    sign_url: Optional[str] = None
    already = False
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
                client = Client(cookie, timeout)
                page = client.get(PAGE)
                nickname = extract_identity(page, cookie)
                if nickname:
                    result.identity = nickname
                    log("账号 {} 官方昵称：{}".format(result.number, nickname))
                else:
                    log("账号 {}：页面未返回公开昵称，使用序号标识".format(result.number))
                sign_url, already = find_sign_action(page)
                result.stats["success"] += 1
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                client = Client(cookie, timeout)
                if already:
                    result.stats["alreadyComplete"] += 1
                    result.message = "今日已打卡"
                    result.status = "alreadyComplete"
                    log("{} 页面确认今日已打卡".format(ICONS["alreadyComplete"]))
                    log(
                        "{} 阶段完成；耗时 {:.2f} 秒".format(
                            ICONS["alreadyComplete"], time.monotonic() - tick
                        )
                    )
                    continue
                if not sign_url:
                    raise SafeError("缺少打卡链接")
                response = client.get(sign_url)
                message = extract_message(response)
                outcome = classify_result(message, response)
                result.message = message or (
                    "打卡成功" if outcome == "success" else "今日已打卡"
                )
                if outcome == "alreadyComplete":
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    log(
                        "{} {}".format(
                            ICONS["alreadyComplete"], result.message[:120]
                        )
                    )
                else:
                    result.stats["success"] += 1
                    result.status = "success"
                    log("{} {}".format(ICONS["success"], result.message[:120]))
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
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    str(error),
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
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
        # 两阶段都成功但未在阶段 2 写入终态时，视为成功
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
    dry_setting = env("STCAIMCU_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[str] = []
    timeout = float(DEFAULT_TIMEOUT)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("STCAIMCU_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, cookie in enumerate(accounts_data, 1):
            account = AccountResult(number)
            results.append(account)
            run_account(account, cookie, timeout, dry_run)
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
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
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
