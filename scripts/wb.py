#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 微博超话关注批量签到
# cron: 20 8 * * *
# SPDX-License-Identifier: MIT
"""微博超话关注批量签到（青龙维护版）。

作者: emper0r
仓库: https://github.com/imhuimie/WeiBo
原路径: wb.py
协议: MIT
维护版有效许可证: MIT（依据导入任务 effectiveLicense）

保留上游网页版契约：
  超话列表 GET https://weibo.com/ajax/profile/topicContent
  超话签到 GET https://weibo.com/p/aj/general/button
             （api=http://i.huati.weibo.com/aj/super/checkin）
  登录体检 GET https://weibo.com/ajax/setting/getPrivacy
  账号身份 GET https://weibo.com/ajax/profile/info

与已发布「微博超话签到」(api.weibo.cn / gsid) 凭据模型不同；
与「微博超话网页签到评论」同为网页 Cookie，但本脚本自动分页拉取全部
关注超话并签到，无需预先填写超话名称，也不默认开启评论。

环境变量：
  WEIBO_COOKIE   必填，每行一个账号的完整浏览器 Cookie；可选「备注|Cookie」
  WEIBO_COOKIES  可选兼容别名，同样按换行分隔账号（不再支持 @ / ----）
  WEIBO_FOLLOW_DRY_RUN=1  完全断网预演（亦接受 WEIBO_DRY_RUN=1）
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
        _ql_notify_identities = ('74a9aa8b41b5634c', 'scripts/wb.py', 'wb.py', 'wb')
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
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

CATALOG_ID = "74a9aa8b41b5634c"
TASK_NAME = "微博超话关注批量签到"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    "candidate.py",
    "output/candidate.py",
    "wb.py",
    "scripts/wb.py",
    "weibo_follow_checkin.py",
    "scripts/weibo_follow_checkin.py",
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TOPIC_LIST_URL = "https://weibo.com/ajax/profile/topicContent"
CHECKIN_URL = "https://weibo.com/p/aj/general/button"
CHECKIN_API = "http://i.huati.weibo.com/aj/super/checkin"
PRIVACY_URL = "https://weibo.com/ajax/setting/getPrivacy"
PROFILE_INFO_URL = "https://weibo.com/ajax/profile/info"

MAX_RESPONSE_BYTES = 1_048_576
MAX_TOPIC_PAGES = 100
HTTP_TIMEOUT_DEFAULT = 15.0
SIGN_INTERVAL_DEFAULT = 1.5
ACCOUNT_INTERVAL_DEFAULT = 10.0

SUCCESS_CODES = {"100000", "382004", "382010"}
ALREADY_CODE = "382004"

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


# ---------------------------------------------------------------------------
# logging helpers
# ---------------------------------------------------------------------------


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}", flush=True)


def env_flag(*names: str, default: bool = False) -> bool:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        return raw.strip().lower() in TRUE_VALUES
    return default


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


def safe_identity(value: Any, secrets: list[str]) -> Optional[str]:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or len(text) > 120 or re.search(r"[\r\n\x00-\x1f]|1[3-9]\d{9}", text):
        return None
    if any(secret and secret in text for secret in secrets):
        return None
    return text


def redact_message(message: str, secrets: list[str]) -> str:
    text = message
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "***")
    return text


# ---------------------------------------------------------------------------
# config / accounts
# ---------------------------------------------------------------------------


@dataclass
class Account:
    index: int
    label: str
    cookie: str


@dataclass
class Settings:
    dry_run: bool
    timeout: float
    sign_interval: float
    account_interval: float


def cookie_field(cookie: str, name: str) -> str:
    for part in cookie.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""


def clean_cookie(cookie: str) -> str:
    text = cookie.strip().replace("\n", "").replace("\r", "")
    if isinstance(text, bytes):  # pragma: no cover - defensive
        text = text.decode("utf-8", errors="ignore")
    return "".join(ch for ch in text if ord(ch) < 128)


def parse_account_line(index: int, line: str) -> Account:
    if "|" in line:
        label, cookie = line.split("|", 1)
        label = label.strip() or f"账号{index}"
        cookie = cookie.strip()
    else:
        label = f"账号{index}"
        cookie = line.strip()
    cookie = clean_cookie(cookie)
    if not cookie or len(cookie) < 20:
        raise ValueError(f"账号 {index} Cookie 无效或过短")
    if "=" not in cookie:
        raise ValueError(f"账号 {index} Cookie 应为浏览器请求头中的完整 key=value 内容")
    if any(ord(ch) < 32 for ch in cookie):
        raise ValueError(f"账号 {index} Cookie 不得包含控制字符")
    return Account(index=index, label=label, cookie=cookie)


def load_accounts() -> list[Account]:
    raw = os.getenv("WEIBO_COOKIE", "")
    if not raw.strip():
        raw = os.getenv("WEIBO_COOKIES", "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError(
            "未配置 WEIBO_COOKIE（兼容 WEIBO_COOKIES）；每行一个账号 Cookie，"
            "不要使用 @、& 或 ---- 分隔账号"
        )
    return [parse_account_line(i, line) for i, line in enumerate(lines, start=1)]


def load_settings() -> Settings:
    return Settings(
        dry_run=env_flag("WEIBO_FOLLOW_DRY_RUN", "WEIBO_DRY_RUN"),
        timeout=bounded_float("WEIBO_TIMEOUT", HTTP_TIMEOUT_DEFAULT, 5.0, 60.0),
        sign_interval=bounded_float(
            "WEIBO_SIGN_INTERVAL", SIGN_INTERVAL_DEFAULT, 0.0, 60.0
        ),
        account_interval=bounded_float(
            "WEIBO_ACCOUNT_INTERVAL", ACCOUNT_INTERVAL_DEFAULT, 0.0, 300.0
        ),
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def read_limited(response: Any, limit: int) -> bytes:
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise RuntimeError("响应体超过安全大小限制")
    return payload


def http_get(
    url: str,
    *,
    cookie: str,
    params: Optional[dict[str, Any]] = None,
    referer: str = "https://weibo.com/",
    timeout: float,
) -> tuple[int, str]:
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    xsrf = cookie_field(cookie, "XSRF-TOKEN")
    headers = {
        "User-Agent": UA,
        "Cookie": cookie,
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    if xsrf:
        headers["X-XSRF-TOKEN"] = xsrf
        headers["X-Xsrf-Token"] = xsrf
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=ssl.create_default_context()
        ) as resp:
            raw = read_limited(resp, MAX_RESPONSE_BYTES)
            return int(getattr(resp, "status", 200)), raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = read_limited(exc, MAX_RESPONSE_BYTES)
        except Exception:
            pass
        return int(exc.code), raw.decode("utf-8", "replace")


def parse_json_body(body: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise RuntimeError("响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("响应 JSON 根节点不是对象")
    return data


# ---------------------------------------------------------------------------
# Weibo API
# ---------------------------------------------------------------------------


def check_login(cookie: str, timeout: float) -> bool:
    status, body = http_get(PRIVACY_URL, cookie=cookie, timeout=timeout)
    try:
        data = parse_json_body(body)
    except RuntimeError:
        return False
    if status == 200 and data.get("ok") == -100:
        return False
    return status == 200 and (data.get("data") or {}).get("privacy") is not None


def fetch_profile_identity(cookie: str, timeout: float) -> Optional[str]:
    status, body = http_get(PROFILE_INFO_URL, cookie=cookie, timeout=timeout)
    if status != 200:
        return None
    try:
        data = parse_json_body(body)
    except RuntimeError:
        return None
    user = (data.get("data") or {}).get("user") or {}
    if not isinstance(user, dict):
        return None
    for key in ("screen_name", "name", "idstr", "id"):
        ident = safe_identity(user.get(key), [cookie])
        if ident:
            return ident
    return None


def fetch_chaohua_page(
    cookie: str, page: int, timeout: float
) -> tuple[list[dict[str, str]], int]:
    status, body = http_get(
        TOPIC_LIST_URL,
        cookie=cookie,
        params={"tabid": "231093_-_chaohua", "page": page},
        timeout=timeout,
    )
    if status != 200:
        raise RuntimeError(f"超话列表 HTTP {status}")
    data = parse_json_body(body)
    if data.get("ok") != 1:
        msg = str(data.get("msg") or "未知错误")
        lowered = msg.lower()
        if "login" in lowered or "cookie" in lowered:
            raise RuntimeError("登录状态失效，请更新 Cookie")
        raise RuntimeError(f"超话列表接口返回错误：{msg}")
    api_data = data.get("data") or {}
    if not isinstance(api_data, dict):
        raise RuntimeError("超话列表 data 字段无效")
    items = api_data.get("list") or []
    collected: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("oid") or "")
            if not oid.startswith("1022:"):
                continue
            chaohua_id = oid[5:]
            chaohua_name = str(item.get("topic_name") or "").strip()
            if chaohua_id and chaohua_name:
                collected.append({"id": chaohua_id, "name": chaohua_name})
    try:
        max_page = int(api_data.get("max_page") or 1)
    except (TypeError, ValueError):
        max_page = 1
    return collected, max(1, max_page)


def fetch_all_chaohua(cookie: str, timeout: float) -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []
    seen: set[str] = set()
    max_page = 1
    page = 1
    while page <= max_page and page <= MAX_TOPIC_PAGES:
        batch, max_page = fetch_chaohua_page(cookie, page, timeout)
        for item in batch:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            collected.append(item)
        if page >= max_page:
            break
        page += 1
        time.sleep(0.8)
    return collected


def sign_chaohua(
    cookie: str, chaohua_id: str, timeout: float
) -> tuple[str, str]:
    """Return (status, detail) where status in success|already|failed."""
    params = {
        "api": CHECKIN_API,
        "id": chaohua_id,
        "location": "page_100808_super_index",
        "__rnd": int(time.time() * 1000),
    }
    status, body = http_get(
        CHECKIN_URL,
        cookie=cookie,
        params=params,
        referer=f"https://weibo.com/p/{chaohua_id}/super_index",
        timeout=timeout,
    )
    if status != 200:
        return "failed", f"HTTP 错误 {status}"
    try:
        data = parse_json_body(body)
    except RuntimeError:
        return "failed", "签到响应非 JSON"
    code = str(data.get("code", ""))
    msg = str(data.get("msg") or "未知错误")
    if code == ALREADY_CODE:
        return "already", msg or "今日已签到"
    if code in SUCCESS_CODES:
        return "success", msg or "签到成功"
    return "failed", f"签到失败 code={code} msg={msg}"


# ---------------------------------------------------------------------------
# account runner
# ---------------------------------------------------------------------------


@dataclass
class AccountStats:
    total: int = 0
    success: int = 0
    already: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class AccountResult:
    index: int
    label: str
    identity: Optional[str]
    ok: bool
    detail: str
    duration: float
    stats: AccountStats = field(default_factory=AccountStats)


def run_account(account: Account, settings: Settings) -> AccountResult:
    started = time.monotonic()
    stats = AccountStats()
    identity: Optional[str] = None
    display = account.label
    secrets = [account.cookie]

    log(f"账号 {account.index}（{display}）｜阶段 1/4：校验 Cookie 参数")
    stage1 = time.monotonic()
    if not cookie_field(account.cookie, "SUB") and not cookie_field(
        account.cookie, "XSRF-TOKEN"
    ):
        log(f"账号 {account.index}｜⚠️ Cookie 中未检出 SUB/XSRF-TOKEN，仍继续尝试")
    else:
        log(f"账号 {account.index}｜✅ Cookie 格式有效，未输出凭据")
    log(f"账号 {account.index}｜阶段耗时 {time.monotonic() - stage1:.2f} 秒")

    log(f"账号 {account.index}｜阶段 2/4：{'预演登录体检' if settings.dry_run else '登录态体检'}")
    stage2 = time.monotonic()
    if settings.dry_run:
        log(
            f"账号 {account.index}｜⏭️ dry-run 跳过真实登录与身份请求｜"
            f"阶段耗时 {time.monotonic() - stage2:.2f} 秒"
        )
    else:
        if not check_login(account.cookie, settings.timeout):
            stats.total += 1
            stats.failed += 1
            duration = time.monotonic() - started
            log(f"账号 {account.index}｜❌ Cookie 登录态无效")
            log(
                f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
                f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜"
                f"耗时 {duration:.2f} 秒"
            )
            return AccountResult(
                account.index, display, None, False, "登录态无效", duration, stats
            )
        identity = fetch_profile_identity(account.cookie, settings.timeout)
        if identity:
            display = identity
            log(f"账号 {account.index}｜官方账号身份：{identity}")
        log(f"账号 {account.index}｜✅ 登录态有效｜阶段耗时 {time.monotonic() - stage2:.2f} 秒")

    log(
        f"账号 {account.index}｜阶段 3/4："
        f"{'预演拉取' if settings.dry_run else '拉取'}关注超话列表"
    )
    stage3 = time.monotonic()
    if settings.dry_run:
        topics = [{"id": "dry-run-topic", "name": "预演超话"}]
        log(
            f"账号 {account.index}｜⏭️ dry-run 模拟关注超话 1 个｜"
            f"阶段耗时 {time.monotonic() - stage3:.2f} 秒"
        )
    else:
        try:
            topics = fetch_all_chaohua(account.cookie, settings.timeout)
        except Exception as exc:  # noqa: BLE001
            stats.total += 1
            stats.failed += 1
            duration = time.monotonic() - started
            detail = redact_message(str(exc), secrets)
            log(f"账号 {account.index}｜❌ 获取超话列表失败：{detail}")
            log(
                f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
                f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜"
                f"耗时 {duration:.2f} 秒"
            )
            return AccountResult(
                account.index, display, identity, False, detail, duration, stats
            )
        log(
            f"账号 {account.index}｜✅ 获取到 {len(topics)} 个关注超话｜"
            f"阶段耗时 {time.monotonic() - stage3:.2f} 秒"
        )

    log(
        f"账号 {account.index}｜阶段 4/4："
        f"{'预演' if settings.dry_run else '执行'}超话签到"
    )
    stage4 = time.monotonic()
    if not topics:
        stats.total += 1
        stats.skipped += 1
        log(f"账号 {account.index}｜⏭️ 当前账号无关注超话，跳过签到")
    else:
        for i, topic in enumerate(topics, 1):
            name = topic["name"]
            tid = topic["id"]
            stats.total += 1
            log(f"账号 {account.index}｜▶ ({i}/{len(topics)}) 超话「{name}」")
            if settings.dry_run:
                stats.skipped += 1
                log(f"账号 {account.index}｜⏭️ 预演：将签到「{name}」（未请求网络）")
            else:
                status, detail = sign_chaohua(account.cookie, tid, settings.timeout)
                detail = redact_message(detail, secrets)
                if status == "success":
                    stats.success += 1
                    log(f"账号 {account.index}｜✅ [{name}] {detail}")
                elif status == "already":
                    stats.already += 1
                    log(f"账号 {account.index}｜☑️ [{name}] {detail}")
                else:
                    stats.failed += 1
                    log(f"账号 {account.index}｜❌ [{name}] {detail}")
            if i < len(topics) and not settings.dry_run:
                delay = settings.sign_interval + random.uniform(0.5, 1.0)
                time.sleep(delay)
    log(f"账号 {account.index}｜阶段耗时 {time.monotonic() - stage4:.2f} 秒")

    duration = time.monotonic() - started
    ok = stats.failed == 0
    if settings.dry_run:
        detail = "dry-run 预演完成"
    elif ok and (stats.success or stats.already or stats.skipped):
        detail = "签到完成"
    elif ok:
        detail = "无待签超话"
    else:
        detail = "存在签到失败"
    log(
        f"账号 {account.index} 统计｜总任务 {stats.total}｜成功 {stats.success}｜"
        f"已完成 {stats.already}｜跳过 {stats.skipped}｜失败 {stats.failed}｜"
        f"耗时 {duration:.2f} 秒"
    )
    log(f"账号 {account.index}｜{'✅' if ok else '❌'} {detail}")
    return AccountResult(account.index, display, identity, ok, detail, duration, stats)


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def notification_selected() -> tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch in TRUE_VALUES:
        return True, "全局开关已启用"
    if switch != "auto":
        return False, "QINGLONG_NOTIFY 值无效，已安全跳过"
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "auto 默认对本维护任务启用"
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False, "脚本选择列表为空"
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    for selector in selectors:
        if selector == "*" or any(
            fnmatch.fnmatch(ident, selector) for ident in SCRIPT_IDENTITIES
        ):
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


def send_notification(body: str, *, dry_run: bool) -> str:
    selected, reason = notification_selected()
    if not selected:
        log(f"通知｜⏭️ {reason}")
        return "skipped"
    if dry_run:
        log("通知｜⏭️ dry-run 仅生成摘要，不调用可能联网的通知模块")
        return "dry-run-simulated"
    sender = load_notify_sender()
    if sender is None:
        log("通知｜⚠️ 未找到青龙 notify.py；业务退出码保持不变")
        return "unavailable"
    try:
        sender(TASK_NAME, body)
        log("通知｜✅ 已发送脱敏任务总结")
        return "sent"
    except Exception as exc:  # noqa: BLE001
        log(f"通知｜⚠️ 发送失败：{type(exc).__name__}；业务退出码保持不变")
        return "failed"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def emit_final(
    *,
    started_wall: str,
    started_mono: float,
    mode: str,
    results: list[AccountResult],
    configuration_error: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    total = len(results)
    success = sum(1 for item in results if item.ok)
    failed = sum(1 for item in results if not item.ok)
    task_total = sum(item.stats.total for item in results)
    task_success = sum(item.stats.success for item in results)
    task_already = sum(item.stats.already for item in results)
    task_skipped = sum(item.stats.skipped for item in results)
    task_failed = sum(item.stats.failed for item in results)

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
    notify_status = send_notification(notification_body, dry_run=dry_run)
    finished = now_text()
    duration = time.monotonic() - started_mono

    print("=" * 56)
    log(f"任务统计｜账号总数 {total}｜成功账号 {success}｜失败账号 {failed}")
    log(
        "子任务统计｜"
        f"总任务 {task_total}｜成功 {task_success}｜已完成 {task_already}｜"
        f"跳过 {task_skipped}｜失败 {task_failed}"
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
            "total": task_total,
            "success": task_success,
            "alreadyComplete": task_already,
            "skipped": task_skipped,
            "failed": task_failed,
        },
        "status": final_status,
        "notification": notify_status,
        "startedAt": started_wall,
        "finishedAt": finished,
        "durationSeconds": round(duration, 3),
        "exitCode": business_exit,
    }
    print(
        "TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    if business_exit == 0 and mode == "dry-run":
        print("DRY_RUN_OK", flush=True)
    return business_exit


def main() -> int:
    started_mono = time.monotonic()
    started_wall = now_text()
    print("=" * 56)
    print(f"{TASK_NAME}｜维护版", flush=True)
    print("=" * 56)
    log(f"开始时间｜{started_wall}")

    try:
        settings = load_settings()
        accounts = load_accounts()
    except ValueError as exc:
        mode = (
            "dry-run"
            if env_flag("WEIBO_FOLLOW_DRY_RUN", "WEIBO_DRY_RUN")
            else "live"
        )
        log(f"运行模式｜{mode}")
        log("账号数量｜0")
        log(f"❌ 配置错误：{exc}")
        return emit_final(
            started_wall=started_wall,
            started_mono=started_mono,
            mode=mode,
            results=[],
            configuration_error=str(exc),
            dry_run=mode == "dry-run",
        )

    mode = "dry-run" if settings.dry_run else "live"
    log(f"运行模式｜{mode}")
    log(f"账号数量｜{len(accounts)}")
    log(
        f"超时｜{settings.timeout:g}s；签到间隔｜{settings.sign_interval:g}s；"
        f"账号间隔｜{settings.account_interval:g}s"
    )

    results: list[AccountResult] = []
    for idx, account in enumerate(accounts):
        print("-" * 56)
        try:
            results.append(run_account(account, settings))
        except Exception as exc:  # noqa: BLE001
            duration = time.monotonic() - started_mono
            log(f"账号 {account.index}｜❌ 未处理异常：{type(exc).__name__}")
            log(
                f"账号 {account.index} 统计｜总任务 1｜成功 0｜已完成 0｜跳过 0｜失败 1｜"
                f"耗时 {duration:.2f} 秒"
            )
            results.append(
                AccountResult(
                    account.index,
                    account.label,
                    None,
                    False,
                    type(exc).__name__,
                    duration,
                    AccountStats(total=1, failed=1),
                )
            )
        if (
            idx < len(accounts) - 1
            and settings.account_interval > 0
            and not settings.dry_run
        ):
            log(f"⏱️ 等待 {settings.account_interval:g} 秒后处理下一账号")
            time.sleep(settings.account_interval)

    return emit_final(
        started_wall=started_wall,
        started_mono=started_mono,
        mode=mode,
        results=results,
        dry_run=settings.dry_run,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已由用户中断。", file=sys.stderr)
        raise SystemExit(130)
