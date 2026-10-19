#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Fa米家每日签到
# cron: 52 0 * * *
# SPDX-License-Identifier: MIT
#
# 基于 yuxian158/check 的 dailycheckin_scripts/ck_fmapp.py 维护；原项目按 MIT 许可发布。
"""Fa米家签到、账号信息与发米粒余额查询（独立青龙任务）。"""

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
        _ql_notify_identities = ('4bf795804a91086f', 'scripts/yuxian158_check_fmapp.py', 'yuxian158_check_fmapp.py', 'yuxian158_check_fmapp')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


TASK_NAME = "Fa米家每日签到"
CATALOG_ID = "4bf795804a91086f"
# 发布器应采用这个产品专属路径，避免与其他应用的 ck_fmapp.py 冲突。
PUBLISHED_SCRIPT_PATH = "scripts/famijia_daily.py"
BASE_URL = "https://fmapp.chinafamilymart.com.cn"
DRY_RUN_ENV = "FMAPP_DRY_RUN"
ACCOUNT_ENV = "FMAPP_ACCOUNTS"
DEFAULT_TIMEOUT = 10.0
MAX_RESPONSE_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"[{clock_text()}] {message}", flush=True)


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f}秒"


def env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def safe_timeout() -> float:
    raw = os.getenv("FMAPP_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if 1 <= value <= 60 else DEFAULT_TIMEOUT


def one_line(value: Any, limit: int = 160) -> str:
    """只展示明确允许的响应字段，并阻断控制字符与超长输出。"""
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    return text[:limit]


def public_identity(value: Any) -> str:
    """昵称按官方返回展示，但手机号形态仍按凭据安全规则隐藏。"""
    text = one_line(value, 120)
    if re.fullmatch(r"(?:\+?86[- ]?)?1[3-9]\d{9}", text):
        return "[疑似手机号，已隐藏]"
    return text or "未返回昵称"


@dataclass(frozen=True)
class Account:
    token: str
    cookie: str
    blackbox: str
    device_id: str
    fmversion: str = "2.2.3"
    os_name: str = "ios"
    useragent: str = "Fa"

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Account":
        normalized = {
            "token": value.get("token"),
            "cookie": value.get("cookie"),
            "blackbox": value.get("blackbox", value.get("blackBox")),
            "device_id": value.get("device_id", value.get("deviceId")),
        }
        missing = [key for key, item in normalized.items() if not isinstance(item, str) or not item.strip()]
        if missing:
            raise ValueError("缺少必填字段：" + "、".join(missing))
        return cls(
            token=normalized["token"].strip(),
            cookie=normalized["cookie"].strip(),
            blackbox=normalized["blackbox"].strip(),
            device_id=normalized["device_id"].strip(),
            fmversion=str(value.get("fmversion", value.get("fmVersion", "2.2.3"))).strip() or "2.2.3",
            os_name=str(value.get("os", "ios")).strip() or "ios",
            useragent=str(value.get("useragent", value.get("userAgent", "Fa"))).strip() or "Fa",
        )

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": "zh-Hans;q=1.0",
            # urllib 不依赖额外解压库，明确请求原始响应，避免把压缩体误判为无效 JSON。
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "loginChannel": "app",
            "token": self.token,
            "fmVersion": self.fmversion,
            "deviceId": self.device_id,
            "User-Agent": self.useragent,
            "os": self.os_name,
            "Cookie": self.cookie,
            "blackBox": self.blackbox,
        }


@dataclass
class AccountEntry:
    number: int
    account: Account | None
    error: str | None = None


@dataclass
class StageResult:
    ok: bool
    detail: str
    identity: str | None = None


def load_accounts() -> list[AccountEntry]:
    raw = os.getenv(ACCOUNT_ENV, "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    entries: list[AccountEntry] = []
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("每行必须是 JSON 对象")
            entries.append(AccountEntry(number, Account.from_mapping(value)))
        except json.JSONDecodeError:
            entries.append(AccountEntry(number, None, "不是有效的 JSON 对象"))
        except (TypeError, ValueError) as exc:
            entries.append(AccountEntry(number, None, one_line(exc)))
    return entries


def request_json(path: str, headers: dict[str, str], payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    body = b"" if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("响应超过安全大小限制")
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP 状态异常：{exc.code}") from None
    except urllib.error.URLError as exc:
        reason = "网络连接失败"
        if isinstance(exc.reason, TimeoutError):
            reason = "请求超时"
        raise RuntimeError(reason) from None
    except TimeoutError:
        raise RuntimeError("请求超时") from None

    try:
        value = json.loads(raw.decode(charset))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("响应不是有效 JSON") from None
    if not isinstance(value, dict):
        raise RuntimeError("响应结构无效")
    return value


def business_data(response: dict[str, Any]) -> dict[str, Any]:
    code = response.get("code")
    if str(code) != "200":
        safe_code = one_line(code, 32) or "缺失"
        raise RuntimeError(f"业务失败（code={safe_code}）")
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def sign(account: Account, timeout: float) -> StageResult:
    data = business_data(
        request_json("/api/app/market/member/signin/sign", account.headers(), None, timeout)
    )
    progress = []
    if data.get("nextDay") is not None and data.get("nextNumber") is not None:
        progress.append(f"再坚持{one_line(data['nextDay'], 20)}天可获得{one_line(data['nextNumber'], 20)}个发米粒")
    if data.get("lastDay") is not None and data.get("lastNumber") is not None:
        progress.append(f"签到{one_line(data['lastDay'], 20)}天可获得{one_line(data['lastNumber'], 20)}个发米粒")
    return StageResult(True, "；".join(progress) if progress else "签到接口返回成功")


def user_info(account: Account, timeout: float) -> StageResult:
    data = business_data(request_json("/api/app/member/info", account.headers(), None, timeout))
    nickname = public_identity(data.get("nickName"))
    return StageResult(True, f"账号身份：{nickname}", nickname)


def mili_count(account: Account, timeout: float) -> StageResult:
    data = business_data(
        request_json(
            "/api/app/member/v1/mili/service/detail",
            account.headers(),
            {"pageSize": 10, "pageNo": 1},
            timeout,
        )
    )
    amount = data.get("miliNum")
    detail = "米粒数量：未返回" if amount is None else f"米粒数量：{one_line(amount, 40)}"
    return StageResult(True, detail)


def notification_selected() -> tuple[bool, str]:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "已由 QINGLONG_NOTIFY 关闭"
    if switch not in TRUE_VALUES and switch not in {"", "auto"}:
        return False, "QINGLONG_NOTIFY 值无效，按关闭处理"

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "自动"
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    selectors = [item for item in re.split(r"[,;\s]+", raw.strip()) if item]
    if not selectors:
        return False, "脚本选择器为空"
    relative = os.path.relpath(__file__, os.getcwd())
    identities = {
        CATALOG_ID,
        Path(__file__).name,
        relative,
        Path(PUBLISHED_SCRIPT_PATH).name,
        PUBLISHED_SCRIPT_PATH,
    }
    selected = any(selector == "*" or any(fnmatch.fnmatch(identity, selector) for identity in identities) for selector in selectors)
    return (True, "已匹配脚本选择器") if selected else (False, "未匹配脚本选择器")


def find_notify_send() -> Callable[[str, str], Any] | None:
    try:
        from notify import send  # type: ignore

        if callable(send):
            return send
    except Exception:
        pass

    candidates: list[Path] = []
    configured = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if configured:
        candidates.append(Path(configured) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("fmapp_ql_notify", path)
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
        return "跳过（" + reason + "）"
    sender = find_notify_send()
    if sender is None:
        return "不可用（未发现 notify.py）"
    try:
        sender(TASK_NAME, body)
        return "发送成功"
    except Exception as exc:
        return f"发送失败（{type(exc).__name__}）"


def main() -> int:
    task_started = time.monotonic()
    started_at = now_text()
    dry_run = env_enabled(DRY_RUN_ENV)
    entries = load_accounts()
    configured_lines = len(entries)
    valid_accounts = sum(1 for entry in entries if entry.account is not None)

    print("=" * 60)
    print(f"{TASK_NAME} | 安全维护版")
    print("=" * 60)
    print(f"开始时间：{started_at}")
    print(f"运行模式：{'DRY-RUN（完全断网）' if dry_run else 'LIVE'}")
    print(f"账号数量：{configured_lines}（有效 {valid_accounts}）")

    account_success = 0
    account_failed = 0
    total_success = 0
    total_skipped = 0
    total_failed = 0
    total_tasks = 0

    if configured_lines == 0:
        log(f"❌ 配置错误：未设置 {ACCOUNT_ENV}，或变量中没有非空行")
        total_failed = 1
        total_tasks = 1

    stages: list[tuple[str, Callable[[Account, float], StageResult]]] = [
        ("签到", sign),
        ("查询账号信息", user_info),
        ("查询米粒数量", mili_count),
    ]
    timeout = safe_timeout()

    for entry in entries:
        account_started = time.monotonic()
        print("-" * 60)
        log(f"账号 {entry.number} 开始")
        if entry.account is None:
            log(f"❌ 账号 {entry.number} 配置无效：{entry.error}")
            log(f"账号 {entry.number} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 {elapsed_text(account_started)}")
            account_failed += 1
            total_failed += 1
            total_tasks += 1
            continue

        account_ok = True
        account_stage_success = 0
        account_stage_skipped = 0
        account_stage_failed = 0
        for stage_number, (stage_name, action) in enumerate(stages, 1):
            stage_started = time.monotonic()
            log(f"[{stage_number}/{len(stages)}] {stage_name}")
            total_tasks += 1
            if dry_run:
                log(f"⏭️ 账号 {entry.number}：已验证配置，断网预演不调用接口 | 耗时 {elapsed_text(stage_started)}")
                total_skipped += 1
                account_stage_skipped += 1
                continue
            try:
                result = action(entry.account, timeout)
                if not result.ok:
                    raise RuntimeError(result.detail)
                log(f"✅ 账号 {entry.number}：{result.detail} | 耗时 {elapsed_text(stage_started)}")
                total_success += 1
                account_stage_success += 1
            except Exception as exc:
                log(f"❌ 账号 {entry.number}：{one_line(exc) or type(exc).__name__} | 耗时 {elapsed_text(stage_started)}")
                total_failed += 1
                account_stage_failed += 1
                account_ok = False

        if account_ok:
            account_success += 1
        else:
            account_failed += 1
        log(
            f"账号 {entry.number} 统计：总任务 {len(stages)}，成功 {account_stage_success}，"
            f"已完成 0，跳过 {account_stage_skipped}，失败 {account_stage_failed}，耗时 {elapsed_text(account_started)}"
        )

    business_exit = 0 if account_failed == 0 and configured_lines > 0 else 1
    if dry_run and business_exit == 0:
        status = "dry-run"
        final_status = "预演完成"
    elif business_exit == 0:
        status = "success"
        final_status = "成功"
    elif account_success > 0:
        status = "partial-failure"
        final_status = "部分失败"
    elif configured_lines == 0 or valid_accounts == 0:
        status = "configuration-error"
        final_status = "配置错误"
    else:
        status = "failure"
        final_status = "失败"

    notify_body = (
        f"状态：{final_status}\n账号总数：{configured_lines}\n"
        f"成功账号：{account_success}\n失败账号：{account_failed}\n"
        f"子任务成功：{total_success}\n子任务跳过：{total_skipped}\n子任务失败：{total_failed}"
    )
    notification_status = send_notification(notify_body)
    finished_at = now_text()

    print("=" * 60)
    print("任务统计")
    print(f"账号结果：总数 {configured_lines}，成功 {account_success}，失败 {account_failed}")
    print(f"子任务结果：总数 {total_tasks}，成功 {total_success}，已完成 0，跳过 {total_skipped}，失败 {total_failed}")
    print(f"总耗时：{elapsed_text(task_started)}")
    print(f"完成时间：{finished_at}")
    print(f"通知状态：{notification_status}")
    print(f"最终状态：{final_status}")
    summary = {
        "accountFailed": account_failed,
        "accountSuccess": account_success,
        "accounts": configured_lines,
        "dryRun": dry_run,
        "exitCode": business_exit,
        "finishedAt": finished_at,
        "notification": notification_status,
        "publishedPath": PUBLISHED_SCRIPT_PATH,
        "startedAt": started_at,
        "status": status,
        "taskFailed": total_failed,
        "taskSkipped": total_skipped,
        "taskSuccess": total_success,
        "tasks": total_tasks,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return business_exit


if __name__ == "__main__":
    sys.exit(main())
