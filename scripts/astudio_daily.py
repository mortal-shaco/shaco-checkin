#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AStudio 每日登录积分观测
# cron: 17 9 * * *
"""AStudio（科大讯飞 Astron Studio）每日登录积分观测独立维护版。

来源：L0NE-6/AStudio-Daily（MIT），原路径 astudio_daily.py。
上游事实（Agent2Providers v3.4.1，只读协议证据）：
  - 每日登录积分没有独立 claim 接口，服务端在当天账号网页会话首次活跃时发放。
  - 账号面根地址：https://agent.xfyun.cn/xingchen-studio/
  - 配置：GET membership/plan-config
  - 余额：GET points/balance
  - 活跃触发：GET membership/me、GET points/summary
  - 前后 totalBalance 增加时只报告“观察到余额增长”，不推断增长来源。

本维护版：青龙可调度、ASTUDIO_COOKIES 多账号（每行一个）、ASTUDIO_DRY_RUN 断网预演、
超时与业务成功判定、脱敏青龙通知与时间轴日志；不依赖私有仓库或桌面端文件。
不打印 Cookie、token、完整 account_id、ssoSessionId、手机号或原始响应。
官方返回的套餐名 planName 等非凭据身份直接显示，便于核对账号。

ASTUDIO_COOKIES：每个非空行一个账号。支持完整 Cookie、备注|token|account_id[|sso]、
或整段 JSON 数组。不使用 &、@ 分隔账号。
兼容 ASTUDIO_ACCOUNT_FILE 显式账号文件；未设置时不自动读取本地默认文件。
ASTUDIO_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
ASTUDIO_TASK=query 或 --query：仅查询活动配置与余额，不触发活跃接口。
ASTUDIO_WAIT_SECONDS / ASTUDIO_TIMEOUT / ASTUDIO_PROXY：等待、超时与可选代理。
通知遵守 QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS；失败不改变业务退出码。
本脚本不发布帖子、评论或分享文本。

MIT License

Copyright (c) 2026 L0NE-6

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
        _ql_notify_identities = ('56e1597cff520f65', 'scripts/astudio_daily.py', 'astudio_daily.py', 'astudio_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import datetime
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

TITLE = "AStudio 每日登录积分观测"
CATALOG_ID = "56e1597cff520f65"
VERSION = "1.1.0-maintained"
ACCOUNT_API_BASE = "https://agent.xfyun.cn/xingchen-studio/"
PLAN_CONFIG_PATH = "membership/plan-config"
POINTS_BALANCE_PATH = "points/balance"
MEMBERSHIP_ME_PATH = "membership/me"
POINTS_SUMMARY_PATH = "points/summary"
DEFAULT_TIMEOUT = 20
DEFAULT_WAIT_SECONDS = 2.5
USER_AGENT = "undici"
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?(1[3-9]\d{9})(?!\d)")
FALSE_FLAGS = {"0", "false", "no", "off", "关闭", "否"}
TRUE_FLAGS = {"1", "true", "yes", "on", "开启", "是"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
BJ = datetime.timezone(datetime.timedelta(hours=8))


class AStudioError(Exception):
    """AStudio Daily 的受控错误基类。"""


class AccountConfigError(AStudioError):
    """账号配置格式错误。"""


class SessionExpired(AStudioError):
    """网页会话失效，需要重新获取 Cookie。"""


class APIError(AStudioError):
    """HTTP、JSON 信封或业务字段错误。"""


@dataclass(frozen=True)
class Account:
    name: str
    token: str
    account_id: str
    sso_session_id: str = ""

    @property
    def label(self) -> str:
        if self.name:
            return redact_phone(self.name)
        return "AStudio-%s" % mask_secret(self.account_id, keep=3)

    @property
    def cookie_header(self) -> str:
        parts: List[str] = []
        if self.sso_session_id:
            parts.append("ssoSessionId=%s" % self.sso_session_id)
            parts.append("sso_sessionid=%s" % self.sso_session_id)
        if self.account_id:
            parts.append("account_id=%s" % self.account_id)
        if self.token:
            parts.append("token=%s" % self.token)
        return "; ".join(parts)

    @property
    def fingerprint(self) -> Tuple[str, str]:
        return (self.token, self.account_id)

    def secrets(self) -> List[str]:
        return [item for item in (self.token, self.sso_session_id, self.account_id) if item]


@dataclass
class Balance:
    total: Decimal
    activity: Optional[Decimal] = None
    activity_next_expire: Optional[str] = None
    spark_total: Optional[Decimal] = None


@dataclass
class StageStat:
    total: int = 0
    success: int = 0
    alreadyComplete: int = 0
    skipped: int = 0
    failure: int = 0


@dataclass
class AccountResult:
    index: int
    label: str
    identity: str
    status: str
    message: str
    before: Optional[Decimal] = None
    after: Optional[Decimal] = None
    delta: Optional[Decimal] = None
    plan_name: str = ""
    detail_lines: List[str] = field(default_factory=list)
    stats: StageStat = field(default_factory=StageStat)
    elapsed_seconds: float = 0.0

    @property
    def failed(self) -> bool:
        return self.status == "failure"

    @property
    def ok(self) -> bool:
        return self.status in {"success", "alreadyComplete", "skipped", "dry-run"}


def now_bj() -> datetime.datetime:
    return datetime.datetime.now(BJ)


def clock() -> str:
    return now_bj().strftime("%Y-%m-%d %H:%M:%S%z")


def print_safe(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(
            encoding, errors="replace"
        )
        print(safe_text, flush=True)


def log(message: str) -> None:
    print_safe("[%s] %s" % (time.strftime("%H:%M:%S"), message))


def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_flag(name: str, default: str = "0") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    raise AccountConfigError("%s 必须为布尔开关值" % name)


def redact_phone(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        phone = match.group(1)
        return "%s****%s" % (phone[:3], phone[-4:])

    return PHONE_PATTERN.sub(replace, str(text or ""))


def mask_secret(value: Any, keep: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if len(text) <= keep + 4:
        return "****"
    return "%s****%s" % (text[:keep], text[-4:])


def sanitize_message(message: Any, account: Optional[Account] = None) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " ").strip()
    if account is not None:
        for secret, replacement in (
            (account.token, "[redacted-token]"),
            (account.sso_session_id, "[redacted-sso]"),
            (account.account_id, mask_secret(account.account_id, keep=3)),
        ):
            if secret:
                text = text.replace(secret, replacement)
    for env_name in (
        "PUSHPLUS_TOKEN",
        "BARK_URL",
        "WECOM_WEBHOOK",
        "ASTUDIO_PROXY",
        "ASTUDIO_COOKIES",
    ):
        value = env_text(env_name)
        if value:
            text = text.replace(value, "[redacted-%s]" % env_name.lower())
    return redact_phone(text)[:800]


def decimal_value(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise APIError("%s 不是有效数字" % field_name)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise APIError("%s 不是有效数字" % field_name)
    if not number.is_finite():
        raise APIError("%s 不是有限数字" % field_name)
    return number


def optional_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value is None:
        return None
    return decimal_value(value, field_name)


def activity_enabled(value: Any) -> bool:
    """Match the upstream contract: only an explicit false value disables it."""
    if value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, str) and value.strip().lower() in FALSE_FLAGS:
        return False
    if value is True:
        return True
    if isinstance(value, (int, float)) and value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in TRUE_FLAGS:
        return True
    return True


def format_decimal(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def split_account_entries(raw: str) -> List[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise AccountConfigError("账号 JSON 格式错误：%s" % error.msg)
        if not isinstance(payload, list):
            raise AccountConfigError("账号 JSON 顶层必须是数组")
        return [json.dumps(item, ensure_ascii=False) for item in payload]
    entries: List[str] = []
    for line in re.split(r"\r?\n", text):
        entry = line.strip().strip('"').strip("'")
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def parse_cookie_header(cookie: str, name: str = "") -> Account:
    values: Dict[str, str] = {}
    for part in cookie.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        normalized = key.strip().lower()
        if normalized in {
            "token",
            "account_id",
            "accountid",
            "sso_sessionid",
            "ssosessionid",
            "sso_session_id",
        }:
            values[normalized] = value.strip()
    token = values.get("token", "")
    account_id = values.get("account_id", "") or values.get("accountid", "")
    sso_session_id = (
        values.get("sso_sessionid", "")
        or values.get("ssosessionid", "")
        or values.get("sso_session_id", "")
    )
    if not token or not account_id:
        raise AccountConfigError("Cookie 必须包含 token 和 account_id")
    return Account(
        name=name.strip(),
        token=token,
        account_id=account_id,
        sso_session_id=sso_session_id,
    )


def account_from_json_object(
    payload: Dict[str, Any], fallback_name: str = ""
) -> Account:
    session = payload.get("session")
    session_value = session if isinstance(session, dict) else {}

    def pick(*keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value is None:
                value = session_value.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    token = pick("token", "sessionToken")
    account_id = pick("accountId", "account_id")
    sso_session_id = pick("ssoSessionId", "sso_sessionid")
    name = pick("name") or fallback_name
    if not token or not account_id:
        raise AccountConfigError(
            "JSON 账号必须包含 token 与 accountId/session.accountId"
        )
    return Account(
        name=name.strip(),
        token=token,
        account_id=account_id,
        sso_session_id=sso_session_id,
    )


def parse_account_entry(entry: str, index: int) -> Account:
    text = entry.strip()
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise AccountConfigError("第 %d 个账号 JSON 错误：%s" % (index, error.msg))
        if not isinstance(payload, dict):
            raise AccountConfigError("第 %d 个账号 JSON 必须是对象" % index)
        return account_from_json_object(payload)
    if "|" in text:
        # 仅按前 3 个竖线拆分，保留 sso 字段后续原文
        parts = text.split("|", 3)
        if len(parts) < 3:
            raise AccountConfigError(
                "第 %d 个账号格式应为 备注|token|account_id|sso_session_id" % index
            )
        name = parts[0].strip()
        token = parts[1].strip()
        account_id = parts[2].strip()
        sso_session_id = parts[3].strip() if len(parts) > 3 else ""
        if not token or not account_id:
            raise AccountConfigError("第 %d 个账号缺少 token 或 account_id" % index)
        return Account(
            name=name,
            token=token,
            account_id=account_id,
            sso_session_id=sso_session_id,
        )
    return parse_cookie_header(text)


def parse_accounts(raw: str) -> List[Account]:
    accounts: List[Account] = []
    seen: Set[Tuple[str, str]] = set()
    for index, entry in enumerate(split_account_entries(raw), 1):
        account = parse_account_entry(entry, index)
        if account.fingerprint in seen:
            continue
        seen.add(account.fingerprint)
        accounts.append(account)
    return accounts


def load_accounts() -> List[Account]:
    sources: List[Tuple[str, str]] = []
    env_cookies = env_text("ASTUDIO_COOKIES")
    if env_cookies:
        sources.append(("ASTUDIO_COOKIES", env_cookies))

    configured_path = env_text("ASTUDIO_ACCOUNT_FILE")
    if configured_path:
        account_path = Path(configured_path)
        try:
            file_text = account_path.read_text(encoding="utf-8")
        except OSError as error:
            raise AccountConfigError(
                "读取账号文件失败：%s" % (error.strerror or "I/O error")
            )
        if file_text.strip():
            sources.append((account_path.name, file_text))

    if not sources:
        raise AccountConfigError(
            "未配置账号。请设置必填环境变量 ASTUDIO_COOKIES（每行一个账号），"
            "或显式设置 ASTUDIO_ACCOUNT_FILE"
        )

    accounts: List[Account] = []
    seen: Set[Tuple[str, str]] = set()
    for source_name, raw in sources:
        try:
            parsed = parse_accounts(raw)
        except AccountConfigError as error:
            raise AccountConfigError("%s：%s" % (source_name, error))
        for account in parsed:
            if account.fingerprint in seen:
                continue
            seen.add(account.fingerprint)
            accounts.append(account)
    if not accounts:
        raise AccountConfigError("账号配置中没有有效账号")
    return accounts


def parse_only(value: str, account_count: int) -> Set[int]:
    selected: Set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_text, end_text = chunk.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError:
                raise AccountConfigError("--only 格式错误：%s" % chunk)
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            try:
                selected.add(int(chunk))
            except ValueError:
                raise AccountConfigError("--only 格式错误：%s" % chunk)
    if not selected:
        raise AccountConfigError("--only 不能为空")
    invalid = sorted(
        number for number in selected if number < 1 or number > account_count
    )
    if invalid:
        raise AccountConfigError(
            "--only 超出账号范围 1..%d：%s"
            % (account_count, ",".join(str(number) for number in invalid))
        )
    return selected


class AStudioClient:
    def __init__(
        self,
        proxy: str = "",
        timeout: int = DEFAULT_TIMEOUT,
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
    ) -> None:
        if requests is None:
            raise APIError("缺少公开依赖 requests，请在青龙依赖管理中安装")
        self.timeout = timeout
        self.wait_seconds = wait_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            }
        )
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def _url(self, path: str) -> str:
        return ACCOUNT_API_BASE + path.lstrip("/")

    def get(self, account: Account, path: str) -> Any:
        url = self._url(path)
        try:
            response = self.session.get(
                url,
                headers={"Cookie": account.cookie_header},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise APIError(
                sanitize_message("%s 网络请求失败：%s" % (path, error), account)
            )

        status = response.status_code
        if status in (401, 403):
            raise SessionExpired(
                "AStudio 会话已失效（HTTP %d），请重新获取 Cookie" % status
            )

        try:
            payload = json.loads(
                response.text,
                parse_float=Decimal,
                parse_int=int,
            )
        except (json.JSONDecodeError, TypeError):
            raise APIError("%s 返回的不是 JSON（HTTP %d）" % (path, status))
        if not isinstance(payload, dict):
            raise APIError("%s 返回的 JSON 顶层不是对象（HTTP %d）" % (path, status))

        code = payload.get("code")
        desc = payload.get("desc") or payload.get("message") or payload.get("msg") or ""
        desc_text = sanitize_message(desc, account)
        code_text = str(code) if code is not None else ""
        expired = code_text == "80000" or "重新登录" in desc_text
        if expired:
            raise SessionExpired(
                "AStudio 会话已失效：%s" % (desc_text or "需要重新登录")
            )

        failed = (
            not 200 <= status < 300
            or payload.get("flag") is False
            or (code is not None and code_text != "0")
        )
        if failed:
            detail = "：%s" % desc_text if desc_text else ""
            raise APIError("%s 失败（HTTP %d）%s" % (path, status, detail))

        data = payload.get("data")
        return {} if data is None else data

    def plan_config(self, account: Account) -> Dict[str, Any]:
        data = self.get(account, PLAN_CONFIG_PATH)
        if not isinstance(data, dict):
            raise APIError("membership/plan-config 的 data 不是对象")
        return data

    def balance(self, account: Account) -> Balance:
        data = self.get(account, POINTS_BALANCE_PATH)
        if not isinstance(data, dict):
            raise APIError("points/balance 的 data 不是对象")
        if "totalBalance" not in data:
            raise APIError("points/balance 缺少 totalBalance")
        return Balance(
            total=decimal_value(data.get("totalBalance"), "totalBalance"),
            activity=optional_decimal(data.get("activityBalance"), "activityBalance"),
            activity_next_expire=(
                str(data.get("activityNextExpireTime"))
                if data.get("activityNextExpireTime") is not None
                else None
            ),
            spark_total=optional_decimal(
                data.get("sparkTotalBalance"), "sparkTotalBalance"
            ),
        )

    def membership(self, account: Account) -> Any:
        return self.get(account, MEMBERSHIP_ME_PATH)

    def points_summary(self, account: Account) -> Any:
        return self.get(account, POINTS_SUMMARY_PATH)


def balance_detail(balance: Balance) -> str:
    parts = ["通用积分=%s" % format_decimal(balance.total)]
    if balance.activity is not None:
        parts.append("活动积分=%s" % format_decimal(balance.activity))
    if balance.spark_total is not None:
        parts.append("星火积分=%s" % format_decimal(balance.spark_total))
    if balance.activity_next_expire:
        parts.append("活动积分到期=%s" % balance.activity_next_expire)
    return "；".join(parts)


def identity_from_config(config: Dict[str, Any], account: Account) -> str:
    plan_name = str(config.get("planName") or "").strip()
    if plan_name:
        return redact_phone(plan_name)
    return account.label


def mark_stage(stats: StageStat, status: str) -> None:
    stats.total += 1
    if status == "success":
        stats.success += 1
    elif status == "alreadyComplete":
        stats.alreadyComplete += 1
    elif status == "skipped":
        stats.skipped += 1
    else:
        stats.failure += 1


def run_account_dry(
    index: int, account: Account, query_only: bool
) -> AccountResult:
    started = time.monotonic()
    stats = StageStat()
    identity = account.label
    log("---------- 账号%d %s ----------" % (index, identity))
    log("阶段 1/2 校验凭据字段：开始")
    stage_begin = time.monotonic()
    if not account.token or not account.account_id:
        mark_stage(stats, "failure")
        log(
            "阶段 1/2 校验凭据字段：%s 缺少 token 或 account_id（%.2f秒）"
            % (ICONS["failure"], time.monotonic() - stage_begin)
        )
        return AccountResult(
            index=index,
            label=account.label,
            identity=identity,
            status="failure",
            message="账号凭据不完整",
            stats=stats,
            elapsed_seconds=round(time.monotonic() - started, 2),
        )
    mark_stage(stats, "success")
    log(
        "阶段 1/2 校验凭据字段：%s 通过（%.2f秒）"
        % (ICONS["success"], time.monotonic() - stage_begin)
    )
    log("阶段 2/2 断网预演动作清单：开始")
    stage_begin = time.monotonic()
    actions = ["GET membership/plan-config"]
    if query_only:
        actions.append("GET points/balance（仅查询）")
        actions.append("跳过 membership/me 与 points/summary")
    else:
        actions.extend(
            [
                "GET points/balance（签到前）",
                "GET membership/me（活跃触发）",
                "GET points/summary（活跃触发）",
                "等待 ASTUDIO_WAIT_SECONDS",
                "GET points/balance（签到后比较）",
            ]
        )
    for action in actions:
        log("  · %s" % action)
    mark_stage(stats, "skipped")
    log(
        "阶段 2/2 断网预演动作清单：%s 已列出，未发起网络请求（%.2f秒）"
        % (ICONS["skipped"], time.monotonic() - stage_begin)
    )
    elapsed = round(time.monotonic() - started, 2)
    log(
        "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
        % (
            index,
            stats.total,
            stats.success,
            stats.alreadyComplete,
            stats.skipped,
            stats.failure,
            elapsed,
        )
    )
    return AccountResult(
        index=index,
        label=account.label,
        identity=identity,
        status="dry-run",
        message="断网预演通过；未声明业务成功",
        detail_lines=actions,
        stats=stats,
        elapsed_seconds=elapsed,
    )


def run_account(
    index: int,
    account: Account,
    client: AStudioClient,
    query_only: bool = False,
    sleeper: Any = time.sleep,
) -> AccountResult:
    started = time.monotonic()
    stats = StageStat()
    label = account.label
    identity = label
    log("---------- 账号%d %s ----------" % (index, label))
    try:
        log("阶段 1/4 读取活动配置：开始")
        stage_begin = time.monotonic()
        config = client.plan_config(account)
        enabled = activity_enabled(config.get("dailyLoginEnabled"))
        identity = identity_from_config(config, account)
        plan_name = str(config.get("planName") or "")
        if plan_name:
            log("  公开套餐名：%s" % redact_phone(plan_name))
        mark_stage(stats, "success")
        log(
            "阶段 1/4 读取活动配置：%s 每日登录活动=%s（%.2f秒）"
            % (
                ICONS["success"],
                "启用" if enabled else "未启用",
                time.monotonic() - stage_begin,
            )
        )

        if query_only:
            log("阶段 2/4 查询余额：开始")
            stage_begin = time.monotonic()
            balance = client.balance(account)
            mark_stage(stats, "success")
            detail = balance_detail(balance)
            log(
                "阶段 2/4 查询余额：%s %s（%.2f秒）"
                % (ICONS["success"], detail, time.monotonic() - stage_begin)
            )
            log("阶段 3/4 活跃触发：%s 查询模式跳过" % ICONS["skipped"])
            mark_stage(stats, "skipped")
            log("阶段 4/4 余额复查：%s 查询模式跳过" % ICONS["skipped"])
            mark_stage(stats, "skipped")
            elapsed = round(time.monotonic() - started, 2)
            log(
                "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
                % (
                    index,
                    stats.total,
                    stats.success,
                    stats.alreadyComplete,
                    stats.skipped,
                    stats.failure,
                    elapsed,
                )
            )
            return AccountResult(
                index=index,
                label=label,
                identity=identity,
                status="success",
                message="查询完成；未调用 membership/me 或 points/summary",
                before=balance.total,
                plan_name=plan_name,
                detail_lines=[
                    "每日登录活动=%s" % ("启用" if enabled else "未启用"),
                    detail,
                ],
                stats=stats,
                elapsed_seconds=elapsed,
            )

        if not enabled:
            log("阶段 2/4 余额与活跃：%s 活动未启用，跳过触发" % ICONS["skipped"])
            mark_stage(stats, "skipped")
            elapsed = round(time.monotonic() - started, 2)
            log(
                "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
                % (
                    index,
                    stats.total,
                    stats.success,
                    stats.alreadyComplete,
                    stats.skipped,
                    stats.failure,
                    elapsed,
                )
            )
            return AccountResult(
                index=index,
                label=label,
                identity=identity,
                status="skipped",
                message="当前没有启用每日登录积分活动",
                plan_name=plan_name,
                stats=stats,
                elapsed_seconds=elapsed,
            )

        log("阶段 2/4 读取签到前余额：开始")
        stage_begin = time.monotonic()
        before = client.balance(account)
        mark_stage(stats, "success")
        log(
            "阶段 2/4 读取签到前余额：%s %s（%.2f秒）"
            % (ICONS["success"], balance_detail(before), time.monotonic() - stage_begin)
        )

        log("阶段 3/4 活跃触发：开始")
        stage_begin = time.monotonic()
        touch_errors: List[str] = []
        membership_data: Any = None
        try:
            membership_data = client.membership(account)
            log("  membership/me：%s" % ICONS["success"])
        except SessionExpired:
            raise
        except APIError as error:
            touch_errors.append("membership/me：%s" % sanitize_message(error, account))
            log("  membership/me：%s %s" % (ICONS["warning"], touch_errors[-1]))

        if isinstance(membership_data, dict):
            for key in ("nickname", "userName", "username", "displayName", "name"):
                value = membership_data.get(key)
                if value is not None and str(value).strip():
                    identity = redact_phone(str(value).strip())
                    log("  公开身份：%s" % identity)
                    break
            plan_from_me = str(membership_data.get("planName") or "").strip()
            if plan_from_me and not plan_name:
                plan_name = plan_from_me
                log("  公开套餐名：%s" % redact_phone(plan_name))

        try:
            client.points_summary(account)
            log("  points/summary：%s" % ICONS["success"])
        except SessionExpired:
            raise
        except APIError as error:
            touch_errors.append("points/summary：%s" % sanitize_message(error, account))
            log("  points/summary：%s %s" % (ICONS["warning"], touch_errors[-1]))

        if touch_errors and len(touch_errors) == 2:
            mark_stage(stats, "failure")
        elif touch_errors:
            mark_stage(stats, "skipped")
        else:
            mark_stage(stats, "success")
        log(
            "阶段 3/4 活跃触发：%s（%.2f秒）"
            % (
                ICONS["failure"]
                if len(touch_errors) == 2
                else (ICONS["warning"] if touch_errors else ICONS["success"]),
                time.monotonic() - stage_begin,
            )
        )

        wait_seconds = max(0.0, float(client.wait_seconds))
        sleeper(wait_seconds)

        log("阶段 4/4 读取签到后余额：开始")
        stage_begin = time.monotonic()
        after = client.balance(account)
        delta = after.total - before.total
        detail_lines = [
            "签到前：%s" % balance_detail(before),
            "签到后：%s" % balance_detail(after),
        ]
        detail_lines.extend(touch_errors)

        if delta > 0:
            mark_stage(stats, "success")
            log(
                "阶段 4/4 读取签到后余额：%s 增长 +%s（%.2f秒）"
                % (ICONS["success"], format_decimal(delta), time.monotonic() - stage_begin)
            )
            elapsed = round(time.monotonic() - started, 2)
            log(
                "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
                % (
                    index,
                    stats.total,
                    stats.success,
                    stats.alreadyComplete,
                    stats.skipped,
                    stats.failure,
                    elapsed,
                )
            )
            return AccountResult(
                index=index,
                label=label,
                identity=identity,
                status="success",
                message=(
                    "本轮余额增加 +%s；仅证明观察到余额变化，未区分发放来源"
                    % format_decimal(delta)
                ),
                before=before.total,
                after=after.total,
                delta=delta,
                plan_name=plan_name,
                detail_lines=detail_lines,
                stats=stats,
                elapsed_seconds=elapsed,
            )

        if touch_errors:
            mark_stage(stats, "failure")
            log(
                "阶段 4/4 读取签到后余额：%s 余额未增加且活跃触发不完整（%.2f秒）"
                % (ICONS["failure"], time.monotonic() - stage_begin)
            )
            elapsed = round(time.monotonic() - started, 2)
            log(
                "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
                % (
                    index,
                    stats.total,
                    stats.success,
                    stats.alreadyComplete,
                    stats.skipped,
                    stats.failure,
                    elapsed,
                )
            )
            return AccountResult(
                index=index,
                label=label,
                identity=identity,
                status="failure",
                message="余额未增加，且会员/积分汇总活跃触发不完整",
                before=before.total,
                after=after.total,
                delta=delta,
                plan_name=plan_name,
                detail_lines=detail_lines,
                stats=stats,
                elapsed_seconds=elapsed,
            )

        # 余额无增长：保持上游诚实语义，不伪造成功；计为跳过（中性）
        mark_stage(stats, "skipped")
        if delta == 0:
            message = "余额无变化；可能今日已签到或积分尚未发放，本次不确认成功"
            icon = ICONS["skipped"]
        else:
            message = "余额减少 %s；本次未观测到签到发放" % format_decimal(-delta)
            icon = ICONS["warning"]
        log(
            "阶段 4/4 读取签到后余额：%s %s（%.2f秒）"
            % (icon, message, time.monotonic() - stage_begin)
        )
        elapsed = round(time.monotonic() - started, 2)
        log(
            "账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒"
            % (
                index,
                stats.total,
                stats.success,
                stats.alreadyComplete,
                stats.skipped,
                stats.failure,
                elapsed,
            )
        )
        return AccountResult(
            index=index,
            label=label,
            identity=identity,
            status="skipped",
            message=message,
            before=before.total,
            after=after.total,
            delta=delta,
            plan_name=plan_name,
            detail_lines=detail_lines,
            stats=stats,
            elapsed_seconds=elapsed,
        )
    except SessionExpired as error:
        mark_stage(stats, "failure")
        message = sanitize_message(error, account)
        log("%s %s" % (ICONS["failure"], message))
        return AccountResult(
            index=index,
            label=label,
            identity=identity,
            status="failure",
            message=message,
            stats=stats,
            elapsed_seconds=round(time.monotonic() - started, 2),
        )
    except APIError as error:
        mark_stage(stats, "failure")
        message = sanitize_message(error, account)
        log("%s %s" % (ICONS["failure"], message))
        return AccountResult(
            index=index,
            label=label,
            identity=identity,
            status="failure",
            message=message,
            stats=stats,
            elapsed_seconds=round(time.monotonic() - started, 2),
        )


def notification_enabled(disabled: bool = False) -> Tuple[bool, str]:
    if disabled:
        return False, "本轮已关闭通知"
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch not in {"", "auto"}:
        return False, "通知开关无效，仅允许 auto 或布尔值"
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return False, "默认仅通知名单内脚本，未配置 QINGLONG_NOTIFY_SCRIPTS"
    selectors = re.split(
        r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip()
    )
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "astudio_daily.py",
        "candidate.py",
        "scripts/astudio_daily.py",
        "astudio-daily",
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


def _notify_via_qinglong(title: str, body: str, dry_run: bool) -> bool:
    if dry_run:
        raise AccountConfigError("预演禁止启动通知进程")
    paths: List[Path] = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))

    py_code = """import sys,json,importlib.util
from pathlib import Path
payload=json.load(sys.stdin)
if len(sys.argv)>1:
    path=Path(sys.argv[1])
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('qinglong_notify', path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send=module.send
else:
    from notify import send
result=send(payload['title'], payload['body'])
sys.exit(1 if result is False else 0)
"""
    js_code = """const fs=require('fs');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.body))
.then(r=>{process.exitCode=r===false?1:0;}).catch(()=>{process.exitCode=1;});
"""
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    attempts: List[Tuple[List[str], Optional[Path]]] = [([sys.executable, "-c", py_code], None)]
    for folder in paths:
        notify_py = folder / "notify.py"
        if notify_py.is_file():
            attempts.append(([sys.executable, "-c", py_code, str(notify_py)], notify_py))
    node = None
    try:
        import shutil

        node = shutil.which("node")
    except Exception:
        node = None
    if node:
        for folder in paths:
            send_js = folder / "sendNotify.js"
            if send_js.is_file():
                attempts.append(([node, "-e", js_code, str(send_js)], send_js))

    for command, _path in attempts:
        try:
            result = subprocess.run(
                command,
                input=payload,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False


def notify_summary(body: str, disabled: bool, dry_run: bool) -> str:
    enabled, reason = notification_enabled(disabled)
    if not enabled:
        log("通知：%s %s" % (ICONS["skipped"], reason))
        return "disabled"
    if dry_run:
        log("通知：%s 预演模拟：%s" % (ICONS["skipped"], body))
        return "dry-run-simulated"
    try:
        if _notify_via_qinglong(TITLE, body, dry_run=False):
            log("通知：%s 脱敏总结已交给青龙适配器" % ICONS["success"])
            return "sent"
    except Exception:
        pass
    log("通知：%s 青龙适配器不可用或投递失败；保留业务退出码" % ICONS["warning"])
    return "unavailable-or-failed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument(
        "--query",
        action="store_true",
        help="只查询活动配置与余额，不调用已识别的活跃触发接口",
    )
    parser.add_argument(
        "--only",
        metavar="N[,N|A-B]",
        help="只运行指定账号序号，例如 1、1,3、1-3",
    )
    parser.add_argument("--no-notify", action="store_true", help="关闭本轮推送")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    started = time.monotonic()
    started_at = clock()
    args = build_parser().parse_args(argv)
    dry_setting = os.environ.get("ASTUDIO_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    query_env = env_text("ASTUDIO_TASK").lower()
    query_only = bool(args.query or query_env in {"query", "credits", "balance"})
    config_error: Optional[str] = None
    accounts: List[Account] = []
    selected: Set[int] = set()
    results: List[AccountResult] = []

    log("========== %s ==========" % TITLE)
    log("版本：%s；目录编号：%s" % (VERSION, CATALOG_ID))

    try:
        if dry_setting and dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise AccountConfigError("ASTUDIO_DRY_RUN 配置无效，停止执行")
        wait_seconds = float(
            env_text("ASTUDIO_WAIT_SECONDS", str(DEFAULT_WAIT_SECONDS)) or str(DEFAULT_WAIT_SECONDS)
        )
        if not math.isfinite(wait_seconds) or wait_seconds < 0:
            raise AccountConfigError("ASTUDIO_WAIT_SECONDS 必须是非负有限数字")
        timeout_text = env_text("ASTUDIO_TIMEOUT", str(DEFAULT_TIMEOUT)) or str(
            DEFAULT_TIMEOUT
        )
        try:
            timeout = int(timeout_text)
        except ValueError:
            raise AccountConfigError("ASTUDIO_TIMEOUT 不是有效整数")
        if timeout <= 0:
            raise AccountConfigError("ASTUDIO_TIMEOUT 必须大于 0")
        accounts = load_accounts()
        selected = (
            parse_only(args.only, len(accounts))
            if args.only
            else set(range(1, len(accounts) + 1))
        )
    except AccountConfigError as error:
        config_error = str(error)
        log("%s 配置错误：%s" % (ICONS["failure"], config_error))

    mode_text = "断网预演" if dry_run else ("仅查询" if query_only else "每日登录积分观测")
    log("开始时间：%s" % started_at)
    log("运行模式：%s" % mode_text)
    log(
        "账号数：配置%d，本次%d"
        % (len(accounts), len(selected) if accounts else 0)
    )

    if not config_error:
        client: Optional[AStudioClient] = None
        if not dry_run:
            try:
                client = AStudioClient(
                    proxy=env_text("ASTUDIO_PROXY"),
                    timeout=timeout,
                    wait_seconds=wait_seconds,
                )
            except APIError as error:
                config_error = str(error)
                log("%s %s" % (ICONS["failure"], config_error))

        if not config_error:
            for index, account in enumerate(accounts, 1):
                if index not in selected:
                    continue
                if dry_run:
                    result = run_account_dry(index, account, query_only)
                else:
                    assert client is not None
                    result = run_account(
                        index, account, client, query_only=query_only
                    )
                results.append(result)
                icon = {
                    "success": ICONS["success"],
                    "alreadyComplete": ICONS["alreadyComplete"],
                    "skipped": ICONS["skipped"],
                    "dry-run": ICONS["skipped"],
                    "failure": ICONS["failure"],
                }.get(result.status, "•")
                log(
                    "%s 账号%d %s：%s"
                    % (icon, result.index, result.identity, result.message)
                )
                for detail in result.detail_lines:
                    log("   %s" % detail)

    success_count = sum(1 for item in results if item.status == "success")
    already_count = sum(1 for item in results if item.status == "alreadyComplete")
    skipped_count = sum(1 for item in results if item.status == "skipped")
    dry_count = sum(1 for item in results if item.status == "dry-run")
    failed_count = sum(1 for item in results if item.status == "failure")
    if config_error:
        failed_count = max(failed_count, 1)
    account_total = len(results)
    verified_ok = success_count + already_count
    # 上游诚实语义：余额无变化（skipped）不视为失败；任一 failure / 配置错误非零退出
    # 断网预演通过配置校验即退出 0；真实执行要求无失败，且至少有一个经核查的成功/已完成，
    # 或全部为活动未启用/中性跳过（与上游 exit 0 对齐，但不把中性写成成功）。
    if config_error:
        exit_code = 2 if not results else 1
    elif failed_count:
        exit_code = 1
    elif dry_run:
        exit_code = 0
    elif query_only:
        exit_code = 0 if results and failed_count == 0 else 1
    elif verified_ok > 0:
        exit_code = 0
    elif results and failed_count == 0:
        # 全部 skipped（未启用或余额中性）：保留上游非失败退出，但不标业务成功
        exit_code = 0
    else:
        exit_code = 1

    if config_error:
        status = "configuration-error"
    elif failed_count and (verified_ok or dry_count or skipped_count):
        status = "partial-failure"
    elif failed_count:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    elif verified_ok > 0:
        status = "success"
    else:
        status = "success" if results else "failure"

    task_totals = StageStat()
    for item in results:
        task_totals.total += item.stats.total
        task_totals.success += item.stats.success
        task_totals.alreadyComplete += item.stats.alreadyComplete
        task_totals.skipped += item.stats.skipped
        task_totals.failure += item.stats.failure

    body = (
        "状态：%s；账号总数%d，成功%d，已完成%d，跳过%d，失败%d，预演%d%s"
        % (
            status,
            account_total if not config_error else 0,
            success_count,
            already_count,
            skipped_count,
            failed_count if not config_error else failed_count,
            dry_count,
            "；配置错误" if config_error else "",
        )
    )
    log("--------------------------------------------------------")
    log(body)
    log(
        "子任务统计：总数%d，成功%d，已完成%d，跳过%d，失败%d"
        % (
            task_totals.total,
            task_totals.success,
            task_totals.alreadyComplete,
            task_totals.skipped,
            task_totals.failure,
        )
    )
    try:
        notification = notify_summary(body, args.no_notify, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：%s 适配器异常；保留业务退出码" % ICONS["warning"])

    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("通知状态：%s" % notification)
    log(
        "完成时间：%s；总耗时 %.2f秒；最终状态：%s"
        % (finished_at, elapsed, status)
    )
    summary = {
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "mode": "dry-run" if dry_run else ("query" if query_only else "live"),
        "status": status,
        "accountCount": account_total if not config_error else 0,
        "successCount": success_count,
        "alreadyCompleteCount": already_count,
        "skippedCount": skipped_count,
        "failureCount": failed_count if not config_error else failed_count,
        "dryRunCount": dry_count,
        "configurationError": bool(config_error),
        "accounts": [
            {
                "index": item.index,
                "identity": item.identity,
                "status": item.status,
                "message": item.message,
                "planName": item.plan_name,
                "delta": format_decimal(item.delta) if item.delta is not None else None,
                "stats": {
                    "total": item.stats.total,
                    "success": item.stats.success,
                    "alreadyComplete": item.stats.alreadyComplete,
                    "skipped": item.stats.skipped,
                    "failure": item.stats.failure,
                },
                "elapsedSeconds": item.elapsed_seconds,
            }
            for item in results
        ],
        "tasks": {
            "total": task_totals.total,
            "success": task_totals.success,
            "alreadyComplete": task_totals.alreadyComplete,
            "skipped": task_totals.skipped,
            "failure": task_totals.failure,
        },
        "notification": notification,
        "startTime": started_at,
        "finishTime": finished_at,
        "durationSeconds": elapsed,
        "exitCode": exit_code,
    }
    print_safe(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
