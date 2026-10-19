#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 69云签到
# cron: 20 0 * * *
# SPDX-License-Identifier: MIT
"""
69yun_multi_checkin.py

这是很早以前保存下来的通用机场签到脚本，原出处已经找不到了。
后来为了放进自己的青龙，改了网络请求、代理、重试、多账号和通知。

维护版保留 Cookie 会话、重试、代理、多机场、多账号、用户信息查询和通知，
并增加逐行 JSON 账号配置、断网预演、严格业务成功判断及结构化汇总。

推荐变量 AIRPORT_ACCOUNTS：每个非空行是一个 JSON 对象，例如字段为
url、user、password。password 字段由 JSON 解析，内容中的分隔符不会被拆分。
仍兼容 AIRPORT1_URL、AIRPORT1_USER1、AIRPORT1_PASS1 等旧变量，其通用写法为
AIRPORT{n}_URL、AIRPORT{n}_USER{m}、AIRPORT{n}_PASS{m}。
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
        _ql_notify_identities = ('1e0938cba7889cb3', 'scripts/69yun_checkin.py', '69yun_checkin.py', '69yun_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import importlib
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


TASK_NAME = "69云签到"
CATALOG_ID = "1e0938cba7889cb3"
ACCOUNT_ENV = "AIRPORT_ACCOUNTS"
DRY_RUN_ENV = "AIRPORT_CHECKIN_DRY_RUN"
CONNECT_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_RETRIES = 3
RETRY_STATUS = {500, 502, 503, 504}
ALREADY_DONE_WORDS = ("已经签到", "已签到", "重复签到", "already checked", "already signed")


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}", flush=True)


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f} 秒"


def safe_message(value: Any, fallback: str = "未提供说明", secrets: Tuple[str, ...] = ()) -> str:
    """压缩服务端业务说明；不记录原始响应或明显凭据。"""
    if not isinstance(value, str):
        return fallback
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return fallback
    text = re.sub(r"(?i)(cookie|token|session|passwd|password|authorization)\s*[:=]\s*\S+", r"\1=[已隐藏]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", text)
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[手机号已隐藏]", text)
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        text = text.replace(secret, "[敏感值已隐藏]")
    return text[:240]


def normalize_base_url(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("url 必须是非空字符串")
    value = raw.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("url 必须是有效的 HTTPS 地址")
    if parsed.username or parsed.password:
        raise ValueError("url 不得包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("url 不得包含查询参数或片段")
    return value


@dataclass
class Account:
    url: str
    user: str
    password: str


@dataclass
class AccountStats:
    index: int
    total: int = 0
    succeeded: int = 0
    already_complete: int = 0
    skipped: int = 0
    failed: int = 0
    identity: str = ""
    detail: str = ""
    duration: float = 0.0
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


def parse_accounts() -> Tuple[List[Account], str]:
    raw = os.getenv(ACCOUNT_ENV, "")
    accounts: List[Account] = []
    if raw.strip():
        for line_number, raw_line in enumerate(raw.splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{ACCOUNT_ENV} 第 {line_number} 行不是有效 JSON：第 {exc.colno} 列格式错误") from None
            if not isinstance(item, dict):
                raise ValueError(f"{ACCOUNT_ENV} 第 {line_number} 行必须是 JSON 对象")
            url = normalize_base_url(item.get("url"))
            user = item.get("user")
            password = item.get("password")
            if not isinstance(user, str) or not user.strip():
                raise ValueError(f"{ACCOUNT_ENV} 第 {line_number} 行缺少非空 user")
            if not isinstance(password, str) or not password:
                raise ValueError(f"{ACCOUNT_ENV} 第 {line_number} 行缺少非空 password")
            accounts.append(Account(url=url, user=user.strip(), password=password))
        if not accounts:
            raise ValueError(f"{ACCOUNT_ENV} 没有非空账号行")
        return accounts, ACCOUNT_ENV

    airport_index = 1
    while True:
        url_value = os.getenv(f"AIRPORT{airport_index}_URL", "").strip()
        if not url_value:
            break
        url = normalize_base_url(url_value)
        account_index = 1
        found_for_airport = False
        while True:
            user = os.getenv(f"AIRPORT{airport_index}_USER{account_index}")
            password = os.getenv(f"AIRPORT{airport_index}_PASS{account_index}")
            if not user and not password:
                break
            if not user or not password:
                raise ValueError(
                    f"旧格式机场 {airport_index} 的账号 {account_index} 必须同时设置 USER 与 PASS"
                )
            accounts.append(Account(url=url, user=user.strip(), password=password))
            found_for_airport = True
            account_index += 1
        if not found_for_airport:
            raise ValueError(f"旧格式机场 {airport_index} 未配置任何完整账号")
        airport_index += 1

    if not accounts:
        raise ValueError(
            f"缺少必填变量 {ACCOUNT_ENV}；请按每行一个 JSON 对象配置 url、user、password"
        )
    return accounts, "legacy"


class HttpSession:
    def __init__(self) -> None:
        handlers: List[Any] = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
        proxy = os.getenv("PROXY_URL", "").strip()
        if proxy:
            parsed = urllib.parse.urlsplit(proxy)
            if parsed.scheme.lower() not in {"http", "https", "socks5"} or not parsed.netloc:
                raise ValueError("PROXY_URL 必须是有效的 http、https 或 socks5 代理地址")
            if parsed.scheme.lower() == "socks5":
                raise ValueError("标准库运行模式不支持 socks5 代理，请使用 http 或 https 代理")
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = urllib.request.build_opener(*handlers)

    def request_json(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        accept_json: bool = True,
    ) -> Tuple[int, Any]:
        body = None
        headers = {
            "User-Agent": "Mozilla/5.0 (Qinglong 69yun maintained script)",
            "Accept": "application/json" if accept_json else "text/html,application/xhtml+xml",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        last_error: Optional[BaseException] = None
        for attempt in range(1, MAX_RETRIES + 1):
            request = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with self.opener.open(request, timeout=CONNECT_TIMEOUT_SECONDS) as response:
                    status = int(response.getcode())
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("响应超过安全大小限制")
                    charset = response.headers.get_content_charset() or "utf-8"
                    text = raw.decode(charset, errors="replace")
                    if accept_json:
                        try:
                            return status, json.loads(text)
                        except json.JSONDecodeError:
                            raise RuntimeError(f"接口返回非 JSON（HTTP {status}）") from None
                    return status, text
            except urllib.error.HTTPError as exc:
                last_error = RuntimeError(f"HTTP {exc.code}")
                if exc.code not in RETRY_STATUS or attempt == MAX_RETRIES:
                    break
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
                last_error = exc
                if attempt == MAX_RETRIES:
                    break
            time.sleep(float(2 ** (attempt - 1)))
        raise RuntimeError(safe_message(str(last_error), "网络请求失败"))


def business_success(data: Dict[str, Any]) -> bool:
    for key in ("ret", "code", "success", "status"):
        if key not in data:
            continue
        value = data[key]
        if value is True or value == 1:
            return True
        if isinstance(value, str) and value.strip().lower() in {"1", "true", "success", "ok", "200"}:
            return True
        if key == "code" and value == 200:
            return True
    return False


def response_message(data: Dict[str, Any], secrets: Tuple[str, ...] = ()) -> str:
    for key in ("msg", "message", "detail"):
        if key in data:
            return safe_message(data[key], secrets=secrets)
    return "服务端未提供业务说明"


def already_complete(message: str) -> bool:
    lowered = message.lower()
    return any(word.lower() in lowered for word in ALREADY_DONE_WORDS)


def find_identity(value: Any, forbidden: Tuple[str, ...] = ()) -> str:
    """仅提取官方结构中的非秘密身份字段，邮箱和手机号不输出。"""
    wanted = {"nickname", "nick_name", "display_name", "displayname", "username", "uid", "user_id"}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in wanted and isinstance(item, (str, int)):
                candidate = re.sub(r"\s+", " ", str(item)).strip()
                if (
                    not candidate
                    or candidate in forbidden
                    or "@" in candidate
                    or re.fullmatch(r"1\d{10}", candidate)
                ):
                    continue
                return candidate[:80]
        for item in value.values():
            found = find_identity(item, forbidden)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_identity(item, forbidden)
            if found:
                return found
    return ""


def extract_user_info(html: str) -> Dict[str, str]:
    result = {"到期时间": "未知", "剩余流量": "未知"}
    patterns = {
        "到期时间": r"['\"]Class_Expire['\"]\s*:\s*['\"]([^'\"]*)['\"]",
        "剩余流量": r"['\"]Unused_Traffic['\"]\s*:\s*['\"]([^'\"]*)['\"]",
    }
    for label, pattern in patterns.items():
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            result[label] = safe_message(match.group(1), "未知")[:100]
    return result


def stage(index: int, name: str, action: Callable[[], Any]) -> Tuple[bool, Any, float]:
    started = time.monotonic()
    log(f"阶段 {index}/3：{name} 开始")
    try:
        value = action()
        duration = time.monotonic() - started
        log(f"阶段 {index}/3：{name} 完成，耗时 {duration:.2f} 秒")
        return True, value, duration
    except Exception as exc:
        duration = time.monotonic() - started
        log(f"❌ 阶段 {index}/3：{name} 失败：{safe_message(str(exc))}，耗时 {duration:.2f} 秒")
        return False, None, duration


def run_account(account: Account, index: int, dry_run: bool) -> AccountStats:
    started = time.monotonic()
    stats = AccountStats(index=index)
    print("-" * 60)
    log(f"账号 {index} 开始（凭据已隐藏）")

    if dry_run:
        for stage_index, name in ((1, "校验登录配置"), (2, "模拟签到请求"), (3, "模拟用户信息查询")):
            stats.total += 1
            stage_started = time.monotonic()
            log(f"阶段 {stage_index}/3：{name} 开始")
            log(f"⏭️ 阶段 {stage_index}/3：断网预演已跳过网络请求，耗时 {elapsed_text(stage_started)}")
            stats.skipped += 1
        stats.duration = time.monotonic() - started
        stats.detail = "配置有效；断网预演未执行真实登录、签到或查询"
        log(
            f"账号 {index} 统计：总任务 {stats.total}，成功 {stats.succeeded}，"
            f"已完成 {stats.already_complete}，跳过 {stats.skipped}，失败 {stats.failed}，耗时 {stats.duration:.2f} 秒"
        )
        return stats

    try:
        session = HttpSession()
    except Exception as exc:
        stats.total = 3
        stats.failed = 1
        stats.skipped = 2
        stats.detail = safe_message(str(exc), "会话初始化失败")
        stats.duration = time.monotonic() - started
        log(f"❌ 账号 {index} 无法初始化会话：{stats.detail}")
        return stats

    login_payload: Dict[str, Any] = {}

    def login() -> Dict[str, Any]:
        status, data = session.request_json(
            "POST",
            f"{account.url}/auth/login",
            {"email": account.user, "passwd": account.password, "remember_me": "on"},
        )
        if status < 200 or status >= 300 or not isinstance(data, dict):
            raise RuntimeError(f"登录接口未成功（HTTP {status}）")
        message = response_message(data, (account.user, account.password))
        if not business_success(data):
            raise RuntimeError(f"登录业务失败：{message}")
        return data

    stats.total += 1
    ok, login_payload, _ = stage(1, "登录并建立 Cookie 会话", login)
    if not ok:
        stats.failed += 1
        stats.detail = "登录失败，后续阶段未执行"
        stats.skipped += 2
        stats.total += 2
        stats.duration = time.monotonic() - started
        log(f"⏭️ 账号 {index} 的签到与用户信息查询已跳过")
        log(
            f"账号 {index} 统计：总任务 {stats.total}，成功 {stats.succeeded}，"
            f"已完成 {stats.already_complete}，跳过 {stats.skipped}，失败 {stats.failed}，耗时 {stats.duration:.2f} 秒"
        )
        return stats
    stats.succeeded += 1
    stats.identity = find_identity(login_payload, (account.user, account.password))
    if stats.identity:
        log(f"✅ 账号 {index} 官方身份：{stats.identity}")
    else:
        log(f"✅ 账号 {index} 登录成功（官方响应未提供可公开身份）")

    checkin_result: Dict[str, Any] = {}

    def checkin() -> Dict[str, Any]:
        status, data = session.request_json("POST", f"{account.url}/user/checkin")
        if status < 200 or status >= 300 or not isinstance(data, dict):
            raise RuntimeError(f"签到接口未成功（HTTP {status}）")
        message = response_message(data, (account.user, account.password))
        if not business_success(data) and not already_complete(message):
            raise RuntimeError(f"签到业务失败：{message}")
        return data

    stats.total += 1
    ok, checkin_result, _ = stage(2, "执行签到", checkin)
    if ok:
        checkin_message = response_message(checkin_result, (account.user, account.password))
        if business_success(checkin_result):
            stats.succeeded += 1
            log(f"✅ 账号 {index} 签到成功：{checkin_message}")
        else:
            stats.already_complete += 1
            log(f"☑️ 账号 {index} 今日已完成签到：{checkin_message}")
        stats.detail = checkin_message
    else:
        stats.failed += 1
        stats.detail = "签到未获得明确业务成功结果"

    def user_info() -> Dict[str, str]:
        status, html = session.request_json("GET", f"{account.url}/user", accept_json=False)
        if status < 200 or status >= 300 or not isinstance(html, str):
            raise RuntimeError(f"用户信息页面未成功（HTTP {status}）")
        return extract_user_info(html)

    stats.total += 1
    info_ok, info, _ = stage(3, "查询到期时间与剩余流量", user_info)
    if info_ok:
        stats.succeeded += 1
        log(f"✅ 账号 {index} 到期时间：{info['到期时间']}；剩余流量：{info['剩余流量']}")
    else:
        stats.failed += 1
        stats.warnings.append("用户信息查询失败，不改变已验证的签到结果")
        log(f"⚠️ 账号 {index} 用户信息查询失败；签到本身仍按阶段 2 判定，但账号任务记为失败")

    stats.duration = time.monotonic() - started
    log(
        f"账号 {index} 统计：总任务 {stats.total}，成功 {stats.succeeded}，"
        f"已完成 {stats.already_complete}，跳过 {stats.skipped}，失败 {stats.failed}，耗时 {stats.duration:.2f} 秒"
    )
    return stats


def notification_selected() -> Tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in {"0", "false", "no", "off"}:
        return False, "全局开关已关闭"
    if switch not in {"", "auto", "1", "true", "yes", "on"}:
        return False, "QINGLONG_NOTIFY 值无效，按安全策略关闭"

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "默认启用"
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False, "脚本选择列表为空"
    selectors = [item for item in re.split(r"[,;\s]+", raw.strip()) if item]
    filename = Path(__file__).name
    candidates = {CATALOG_ID, filename, "69yun_checkin.py", f"checkin/{filename}", "checkin/69yun_checkin.py"}
    if any(selector == "*" or any(fnmatch.fnmatch(value, selector) for value in candidates) for selector in selectors):
        return True, "已被脚本选择列表选中"
    return False, "未被脚本选择列表选中"


def load_notify_send() -> Tuple[Optional[Callable[[str, str], Any]], str]:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            return sender, "Python 模块 notify"
    except Exception:
        pass

    candidates: List[Path] = []
    custom_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify_runtime", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                return sender, str(path)
        except Exception:
            continue
    return None, "未找到可用 notify.py"


def send_notification(body: str, dry_run: bool = False) -> str:
    # 断网预演不得因通知模块而产生任何外部请求；仍生成并记录脱敏通知摘要。
    if dry_run:
        log("⏭️ 通知已生成但未发送：断网预演禁止外部请求")
        return "dry-run-skipped"
    enabled, reason = notification_selected()
    if not enabled:
        log(f"⏭️ 通知未发送：{reason}")
        return "disabled"
    sender, source = load_notify_send()
    if sender is None:
        log(f"⚠️ 通知不可用：{source}；业务退出码保持不变")
        return "unavailable"
    try:
        sender(TASK_NAME, body)
        log(f"✅ 通知已通过 {source} 发送")
        return "sent"
    except Exception as exc:
        log(f"⚠️ 通知发送失败：{safe_message(str(exc))}；业务退出码保持不变")
        return "failed"


def make_summary(
    status: str,
    dry_run: bool,
    results: List[AccountStats],
    started_at: str,
    finished_at: str,
    duration: float,
    notification: str,
    configuration_error: str = "",
) -> Dict[str, Any]:
    account_success = sum(1 for item in results if item.ok)
    account_failed = sum(1 for item in results if not item.ok)
    return {
        "task": TASK_NAME,
        "catalogId": CATALOG_ID,
        "status": status,
        "dryRun": dry_run,
        "verifiedBusinessSuccess": bool(not dry_run and results and account_failed == 0 and not configuration_error),
        "accounts": {"total": len(results), "success": account_success, "failed": account_failed},
        "subtasks": {
            "total": sum(item.total for item in results),
            "success": sum(item.succeeded for item in results),
            "alreadyComplete": sum(item.already_complete for item in results),
            "skipped": sum(item.skipped for item in results),
            "failed": sum(item.failed for item in results),
        },
        "configurationError": bool(configuration_error),
        "notification": notification,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationSeconds": round(duration, 3),
    }


def main() -> int:
    monotonic_start = time.monotonic()
    started_at = now_text()
    dry_run = env_enabled(DRY_RUN_ENV)
    print("=" * 60)
    print(f"{TASK_NAME}｜独立维护版")
    print("=" * 60)
    log(f"开始时间：{started_at}")
    log(f"运行模式：{'断网预演' if dry_run else '正式运行'}")

    configuration_error = ""
    try:
        accounts, source = parse_accounts()
        log(f"账号数量：{len(accounts)}；配置来源：{source}")
        if source == ACCOUNT_ENV and os.getenv("AIRPORT1_URL", "").strip():
            log("⚠️ 同时检测到新旧配置；为避免重复签到，本次仅使用 AIRPORT_ACCOUNTS")
    except Exception as exc:
        accounts = []
        configuration_error = safe_message(str(exc), "账号配置无效")
        log("账号数量：0")
        log(f"❌ 配置错误：{configuration_error}")

    results: List[AccountStats] = []
    if not configuration_error:
        for index, account in enumerate(accounts, 1):
            results.append(run_account(account, index, dry_run))
            if not dry_run and index < len(accounts):
                delay = 2 + (index % 4)
                log(f"账号间隔：等待 {delay} 秒后继续")
                time.sleep(delay)

    business_exit = 2 if configuration_error else (1 if any(not item.ok for item in results) else 0)
    if configuration_error:
        final_status = "configuration-error"
    elif dry_run:
        final_status = "dry-run"
    elif business_exit == 0:
        final_status = "success"
    elif any(item.ok for item in results):
        final_status = "partial-failure"
    else:
        final_status = "failure"

    success_count = sum(1 for item in results if item.ok)
    failed_count = sum(1 for item in results if not item.ok)
    notification_body = (
        f"状态：{final_status}\n账号总数：{len(results)}\n成功账号：{success_count}\n"
        f"失败账号：{failed_count}\n模式：{'断网预演' if dry_run else '正式运行'}"
    )
    if configuration_error:
        notification_body += "\n配置：无效（详情请查看任务日志）"
    notification = send_notification(notification_body, dry_run=dry_run)

    finished_at = now_text()
    duration = time.monotonic() - monotonic_start
    print("=" * 60)
    log(
        f"任务统计：账号总数 {len(results)}，成功 {success_count}，失败 {failed_count}；"
        f"子任务总数 {sum(item.total for item in results)}，成功 {sum(item.succeeded for item in results)}，"
        f"已完成 {sum(item.already_complete for item in results)}，跳过 {sum(item.skipped for item in results)}，"
        f"失败 {sum(item.failed for item in results)}"
    )
    log(f"总耗时：{duration:.2f} 秒；完成时间：{finished_at}；通知状态：{notification}")
    log(f"最终状态：{final_status}")
    summary = make_summary(
        final_status,
        dry_run,
        results,
        started_at,
        finished_at,
        duration,
        notification,
        configuration_error,
    )
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return business_exit


if __name__ == "__main__":
    raise SystemExit(main())
