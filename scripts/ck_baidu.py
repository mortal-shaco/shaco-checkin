#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 百度站点提交
# cron: 6 0 * * *
# SPDX-License-Identifier: MIT
# Upstream: yuxian158/check dailycheckin_scripts/ck_baidu.py

"""百度搜索资源平台普通收录提交任务。

环境变量 BAIDU_SUBMIT_ACCOUNTS 每个非空行是一组 JSON 账号，例如：
{"site":"https://example.com","token":"请填推送准入密钥","data_url":"https://example.com/urls.txt"}

脚本不会打印 token、数据地址、原始响应或 URL 列表。设置 BAIDU_DRY_RUN=1
时仅校验配置和执行计划，不发起业务 HTTP 请求。
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
        _ql_notify_identities = ('0acdab575fbc0e9e', 'scripts/ck_baidu.py', 'ck_baidu.py', 'ck_baidu')
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
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import error, parse, request


TASK_NAME = "百度站点提交"
CATALOG_ID = "0acdab575fbc0e9e"
SOURCE_FILENAME = "ck_baidu.py"
ACCOUNTS_ENV = "BAIDU_SUBMIT_ACCOUNTS"
DRY_RUN_ENV = "BAIDU_DRY_RUN"
DEFAULT_TIMEOUT = 15
DEFAULT_TIMES = 1
MAX_TIMES = 100
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
MAX_URLS = 10000
BATCH_SIZE = 2000
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """可安全展示的配置错误。"""


class TaskError(RuntimeError):
    """不包含凭据、URL 或原始响应的任务错误。"""


@dataclass(frozen=True)
class Account:
    number: int
    site: str
    token: str
    data_url: str
    times: int


@dataclass
class AccountResult:
    number: int
    status: str
    total: int
    success: int
    already_complete: int
    skipped: int
    failed: int
    duration_seconds: float
    submitted_urls: int = 0


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def elapsed_text(started: float) -> str:
    return f"{time.monotonic() - started:.2f} 秒"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES or not normalized:
        return False
    raise ConfigError(f"{name} 只能填写 1/true/yes/on 或 0/false/no/off")


def parse_int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def validate_http_url(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} 不能为空")
    clean = value.strip()
    parts = parse.urlsplit(clean)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ConfigError(f"{field_name} 必须是完整的 HTTP 或 HTTPS 地址")
    if parts.username or parts.password:
        raise ConfigError(f"{field_name} 不得在地址中包含用户名或密码")
    return clean


def validate_site(value: Any, field_name: str) -> str:
    site = validate_http_url(value, field_name)
    parts = parse.urlsplit(site)
    if parts.query or parts.fragment:
        raise ConfigError(f"{field_name} 不得包含查询参数或片段")
    return site


def parse_account(line: str, number: int, default_times: int) -> Account:
    try:
        item = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"账号 {number} 不是有效的单行 JSON 对象") from exc
    if not isinstance(item, dict):
        raise ConfigError(f"账号 {number} 必须是 JSON 对象")

    site = validate_site(item.get("site"), f"账号 {number} 的 site")
    data_url = validate_http_url(item.get("data_url"), f"账号 {number} 的 data_url")
    token = item.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ConfigError(f"账号 {number} 的 token 不能为空")
    if any(character.isspace() for character in token):
        raise ConfigError(f"账号 {number} 的 token 不得包含空白字符")
    if len(token) > 512:
        raise ConfigError(f"账号 {number} 的 token 长度异常")

    times_value = item.get("times", default_times)
    if isinstance(times_value, bool):
        raise ConfigError(f"账号 {number} 的 times 必须是整数")
    try:
        times = int(times_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"账号 {number} 的 times 必须是整数") from exc
    if not 1 <= times <= MAX_TIMES:
        raise ConfigError(f"账号 {number} 的 times 必须在 1 到 {MAX_TIMES} 之间")

    return Account(
        number=number,
        site=site,
        token=token.strip(),
        data_url=data_url,
        times=times,
    )


def parse_accounts() -> Tuple[List[Account], Dict[int, str]]:
    raw = os.environ.get(ACCOUNTS_ENV, "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ConfigError(f"缺少必填环境变量 {ACCOUNTS_ENV}")

    default_times = parse_int_setting(
        "BAIDU_SUBMIT_TIMES", DEFAULT_TIMES, 1, MAX_TIMES
    )
    accounts: List[Account] = []
    account_errors: Dict[int, str] = {}
    for number, line in enumerate(lines, start=1):
        try:
            accounts.append(parse_account(line, number, default_times))
        except ConfigError as exc:
            account_errors[number] = str(exc)
    return accounts, account_errors


def safe_http_error(exc: BaseException) -> str:
    if isinstance(exc, error.HTTPError):
        return f"HTTP 状态码 {exc.code}"
    if isinstance(exc, error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return "请求超时"
        return "网络连接失败"
    if isinstance(exc, TimeoutError):
        return "请求超时"
    return f"请求失败（{type(exc).__name__}）"


def read_limited(response: Any, limit: int) -> bytes:
    content = response.read(limit + 1)
    if len(content) > limit:
        raise TaskError("响应内容超过安全大小限制")
    return content


def fetch_urls(account: Account, timeout: int) -> List[str]:
    req = request.Request(
        account.data_url,
        headers={
            "Accept": "text/plain, text/*;q=0.9, */*;q=0.1",
            "User-Agent": "Qinglong-BaiduSubmit/1.0",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise TaskError(f"URL 列表请求返回 HTTP 状态码 {status}")
            content = read_limited(response, MAX_SOURCE_BYTES)
    except TaskError:
        raise
    except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
        raise TaskError(f"获取 URL 列表失败：{safe_http_error(exc)}") from exc

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TaskError("URL 列表不是有效的 UTF-8 文本") from exc

    urls: List[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        candidate = line.strip()
        if not candidate:
            continue
        parts = parse.urlsplit(candidate)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise TaskError(f"URL 列表第 {line_number} 行不是完整的 HTTP 或 HTTPS 地址")
        if parts.username or parts.password:
            raise TaskError(f"URL 列表第 {line_number} 行包含不允许的用户信息")
        urls.append(candidate)
        if len(urls) > MAX_URLS:
            raise TaskError(f"URL 列表超过单次运行上限 {MAX_URLS} 条")
    if not urls:
        raise TaskError("URL 列表中没有可提交的有效地址")
    return urls


def chunks(values: Sequence[str], size: int) -> Sequence[Sequence[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def submit_batch(account: Account, urls: Sequence[str], timeout: int) -> Tuple[int, int]:
    query = parse.urlencode({"site": account.site, "token": account.token})
    endpoint = f"https://data.zz.baidu.com/urls?{query}"
    body = "\n".join(urls).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "text/plain; charset=utf-8",
            "User-Agent": "Qinglong-BaiduSubmit/1.0",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            content = read_limited(response, MAX_RESPONSE_BYTES)
    except TaskError:
        raise
    except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
        raise TaskError(f"提交请求失败：{safe_http_error(exc)}") from exc
    if not 200 <= status < 300:
        raise TaskError(f"提交请求返回 HTTP 状态码 {status}")

    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TaskError("提交接口没有返回有效的 JSON") from exc
    if not isinstance(payload, dict):
        raise TaskError("提交接口返回的数据结构不正确")

    error_code = payload.get("error")
    if error_code not in (None, 0, "0", ""):
        if isinstance(error_code, int) and not isinstance(error_code, bool):
            raise TaskError(f"百度接口返回业务错误码 {error_code}")
        if isinstance(error_code, str) and re.fullmatch(r"\d{1,8}", error_code):
            raise TaskError(f"百度接口返回业务错误码 {error_code}")
        raise TaskError("百度接口返回业务错误")
    accepted = payload.get("success")
    remain = payload.get("remain")
    if isinstance(accepted, bool) or not isinstance(accepted, int):
        raise TaskError("提交接口缺少有效的 success 数量")
    if isinstance(remain, bool) or not isinstance(remain, int) or remain < 0:
        raise TaskError("提交接口缺少有效的 remain 数量")
    invalid_count = 0
    for key in ("not_same_site", "not_valid"):
        value = payload.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise TaskError(f"提交接口的 {key} 字段格式不正确")
        invalid_count += len(value)
    if invalid_count:
        raise TaskError(f"百度接口拒绝了 {invalid_count} 条 URL")
    if accepted != len(urls):
        raise TaskError(f"百度接口确认 {accepted} 条，预期确认 {len(urls)} 条")
    return accepted, remain


def stage(account_number: int, current: int, total: int, name: str) -> float:
    started = time.monotonic()
    print(f"[{clock_text()}] [账号 {account_number}] [阶段 {current}/{total}] {name}")
    return started


def run_account(account: Account, dry_run: bool, timeout: int) -> AccountResult:
    started = time.monotonic()
    total = 3
    success = 0
    skipped = 0
    failed = 0

    step_started = stage(account.number, 1, total, "校验账号配置")
    print(
        f"[{clock_text()}] ✅ 账号 {account.number} 配置有效；目标站点：{account.site}；"
        f"重复次数：{account.times}；耗时：{elapsed_text(step_started)}"
    )
    success += 1

    if dry_run:
        for current, name in ((2, "读取 URL 列表"), (3, "提交 URL")):
            step_started = stage(account.number, current, total, name)
            print(
                f"[{clock_text()}] ⏭️ dry-run 已跳过网络请求；耗时："
                f"{elapsed_text(step_started)}"
            )
            skipped += 1
        duration = time.monotonic() - started
        print(
            f"[{clock_text()}] [账号 {account.number} 统计] 总任务 {total}，成功 {success}，"
            f"已完成 0，跳过 {skipped}，失败 0，耗时 {duration:.2f} 秒"
        )
        return AccountResult(
            account.number, "dry-run", total, success, 0, skipped, 0, duration
        )

    step_started = stage(account.number, 2, total, "读取并校验 URL 列表")
    try:
        urls = fetch_urls(account, timeout)
    except TaskError as exc:
        failed += 1
        print(f"[{clock_text()}] ❌ {exc}；耗时：{elapsed_text(step_started)}")
        skipped_started = stage(account.number, 3, total, "提交 URL")
        print(
            f"[{clock_text()}] ⏭️ 因 URL 列表读取失败跳过；耗时："
            f"{elapsed_text(skipped_started)}"
        )
        duration = time.monotonic() - started
        print(
            f"[{clock_text()}] [账号 {account.number} 统计] 总任务 {total}，成功 {success}，"
            f"已完成 0，跳过 1，失败 {failed}，耗时 {duration:.2f} 秒"
        )
        return AccountResult(account.number, "failed", total, success, 0, 1, failed, duration)
    success += 1
    print(
        f"[{clock_text()}] ✅ 已读取并校验 {len(urls)} 条 URL；耗时："
        f"{elapsed_text(step_started)}"
    )

    step_started = stage(account.number, 3, total, "向百度提交 URL")
    submitted = 0
    batches = chunks(urls, BATCH_SIZE)
    try:
        for repeat in range(1, account.times + 1):
            for batch_number, batch in enumerate(batches, start=1):
                accepted, remain = submit_batch(account, batch, timeout)
                submitted += accepted
                print(
                    f"[{clock_text()}] ✅ 第 {repeat}/{account.times} 轮、第 "
                    f"{batch_number}/{len(batches)} 批确认 {accepted} 条，剩余额度 {remain}"
                )
    except TaskError as exc:
        failed += 1
        print(f"[{clock_text()}] ❌ {exc}；耗时：{elapsed_text(step_started)}")
        duration = time.monotonic() - started
        print(
            f"[{clock_text()}] [账号 {account.number} 统计] 总任务 {total}，成功 {success}，"
            f"已完成 0，跳过 0，失败 {failed}，耗时 {duration:.2f} 秒"
        )
        return AccountResult(
            account.number, "failed", total, success, 0, 0, failed, duration, submitted
        )
    success += 1
    print(
        f"[{clock_text()}] ✅ 共确认提交 {submitted} 条次 URL；耗时："
        f"{elapsed_text(step_started)}"
    )
    duration = time.monotonic() - started
    print(
        f"[{clock_text()}] [账号 {account.number} 统计] 总任务 {total}，成功 {success}，"
        f"已完成 0，跳过 0，失败 0，耗时 {duration:.2f} 秒"
    )
    return AccountResult(account.number, "success", total, success, 0, 0, 0, duration, submitted)


def record_account_config_error(number: int, message: str) -> AccountResult:
    started = time.monotonic()
    print(f"[{clock_text()}] ---------- 账号 {number} 开始 ----------")
    step_started = stage(number, 1, 3, "校验账号配置")
    print(f"[{clock_text()}] ❌ {message}；耗时：{elapsed_text(step_started)}")
    for current, name in ((2, "读取 URL 列表"), (3, "提交 URL")):
        step_started = stage(number, current, 3, name)
        print(
            f"[{clock_text()}] ⏭️ 因账号配置错误跳过；耗时："
            f"{elapsed_text(step_started)}"
        )
    duration = time.monotonic() - started
    print(
        f"[{clock_text()}] [账号 {number} 统计] 总任务 3，成功 0，"
        f"已完成 0，跳过 2，失败 1，耗时 {duration:.2f} 秒"
    )
    return AccountResult(number, "config-error", 3, 0, 0, 2, 1, duration)


def notification_selected() -> Tuple[bool, str]:
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "已由 QINGLONG_NOTIFY 关闭"
    if switch not in TRUE_VALUES and switch != "auto":
        return False, "QINGLONG_NOTIFY 值无效"

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "自动模式"
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False, "脚本选择列表为空"
    selectors = [value for value in re.split(r"[,;\s]+", raw) if value]
    candidates = {
        CATALOG_ID,
        SOURCE_FILENAME,
        "candidate.py",
        "output/candidate.py",
        Path(__file__).name,
        str(Path(__file__)),
    }
    matched = any(
        selector == "*"
        or any(fnmatch.fnmatch(candidate, selector) for candidate in candidates)
        for selector in selectors
    )
    return matched, "脚本选择列表匹配" if matched else "脚本选择列表未匹配"


def load_notify_module(path: Path) -> Optional[Any]:
    try:
        spec = importlib.util.spec_from_file_location("qinglong_notify", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except (Exception, SystemExit):
        return None


def send_notification(body: str) -> str:
    selected, reason = notification_selected()
    if not selected:
        print(f"[{clock_text()}] ⚠️ 通知未发送：{reason}")
        return "disabled"

    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(TASK_NAME, body)
            print(f"[{clock_text()}] ✅ 已通过 notify.py 发送脱敏摘要")
            return "sent"
    except (Exception, SystemExit):
        pass

    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    python_paths: List[Path] = []
    javascript_paths: List[Path] = []
    if notify_dir:
        python_paths.append(Path(notify_dir) / "notify.py")
        javascript_paths.append(Path(notify_dir) / "sendNotify.js")
    python_paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    javascript_paths.extend(
        [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    )

    for path in python_paths:
        if not path.is_file():
            continue
        module = load_notify_module(path)
        sender = getattr(module, "send", None) if module is not None else None
        if callable(sender):
            try:
                sender(TASK_NAME, body)
                print(f"[{clock_text()}] ✅ 已通过 notify.py 发送脱敏摘要")
                return "sent"
            except (Exception, SystemExit):
                continue

    node_program = (
        "const [p,t,b]=process.argv.slice(1);"
        "Promise.resolve(require(p)(t,b)).then(()=>process.exit(0))"
        ".catch(()=>process.exit(1));"
    )
    for path in javascript_paths:
        if not path.is_file():
            continue
        try:
            completed = subprocess.run(
                ["node", "-e", node_program, str(path), TASK_NAME, body],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            print(f"[{clock_text()}] ✅ 已通过 sendNotify.js 发送脱敏摘要")
            return "sent"

    print(f"[{clock_text()}] ⚠️ 未找到可用通知组件或通知发送失败；业务退出码保持不变")
    return "unavailable"


def print_banner(start_time: str, dry_run: bool, account_count: int) -> None:
    print("=" * 60)
    print(f"{TASK_NAME} | 安全维护版")
    print(f"开始时间: {start_time}")
    print(f"运行模式: {'DRY_RUN（完全断网预演）' if dry_run else 'LIVE（真实提交）'}")
    print(f"账号数量: {account_count}")
    print("=" * 60)


def finish(
    *,
    started: float,
    start_time: str,
    dry_run: bool,
    results: Sequence[AccountResult],
    configuration_error: bool = False,
) -> int:
    account_total = len(results)
    account_success = sum(result.failed == 0 for result in results)
    account_failed = sum(result.failed > 0 for result in results)
    subtask_total = sum(result.total for result in results)
    subtask_success = sum(result.success for result in results)
    subtask_already = sum(result.already_complete for result in results)
    subtask_skipped = sum(result.skipped for result in results)
    subtask_failed = sum(result.failed for result in results)

    if configuration_error:
        status = "CONFIG_ERROR"
        business_exit_code = 2
    elif account_failed:
        if account_success:
            status = "PARTIAL_FAILURE"
        elif results and all(result.status == "config-error" for result in results):
            status = "CONFIG_ERROR"
        else:
            status = "FAILURE"
        business_exit_code = 1
    elif dry_run:
        status = "DRY_RUN"
        business_exit_code = 0
    else:
        status = "SUCCESS"
        business_exit_code = 0

    body = (
        f"状态：{status}\n账号总数：{account_total}\n"
        f"成功账号：{account_success}\n失败账号：{account_failed}\n"
        f"子任务失败：{subtask_failed}"
    )
    notification = send_notification(body)
    finished_at = now_text()
    duration = time.monotonic() - started

    print("-" * 60)
    print("任务统计")
    print(f"账号结果: 总数 {account_total}，成功 {account_success}，失败 {account_failed}")
    print(
        f"子任务结果: 总数 {subtask_total}，成功 {subtask_success}，已完成 "
        f"{subtask_already}，跳过 {subtask_skipped}，失败 {subtask_failed}"
    )
    print(f"总耗时: {duration:.2f} 秒")
    print(f"开始时间: {start_time}")
    print(f"完成时间: {finished_at}")
    print(f"通知状态: {notification}")
    print(f"最终状态: {status}")
    print("-" * 60)

    summary: Dict[str, Any] = {
        "status": status.lower().replace("_", "-"),
        "mode": "dry-run" if dry_run else "live",
        "accounts": {
            "total": account_total,
            "success": account_success,
            "failed": account_failed,
        },
        "subtasks": {
            "total": subtask_total,
            "success": subtask_success,
            "alreadyComplete": subtask_already,
            "skipped": subtask_skipped,
            "failed": subtask_failed,
        },
        "notification": notification,
        "durationSeconds": round(duration, 3),
        "finishedAt": finished_at,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return business_exit_code


def main() -> int:
    started = time.monotonic()
    start_time = now_text()
    raw_count = len(
        [line for line in os.environ.get(ACCOUNTS_ENV, "").splitlines() if line.strip()]
    )
    try:
        dry_run = env_flag(DRY_RUN_ENV)
    except ConfigError as exc:
        dry_run = False
        print_banner(start_time, dry_run, raw_count)
        print(f"[{clock_text()}] [阶段 1/1] 配置检查")
        print(f"[{clock_text()}] ❌ {exc}")
        return finish(
            started=started,
            start_time=start_time,
            dry_run=dry_run,
            results=[],
            configuration_error=True,
        )

    try:
        timeout = parse_int_setting("BAIDU_HTTP_TIMEOUT", DEFAULT_TIMEOUT, 3, 60)
        accounts, account_errors = parse_accounts()
    except ConfigError as exc:
        print_banner(start_time, dry_run, raw_count)
        print(f"[{clock_text()}] [阶段 1/1] 配置检查")
        print(f"[{clock_text()}] ❌ {exc}")
        return finish(
            started=started,
            start_time=start_time,
            dry_run=dry_run,
            results=[],
            configuration_error=True,
        )

    print_banner(start_time, dry_run, len(accounts) + len(account_errors))
    results: List[AccountResult] = []
    account_map = {account.number: account for account in accounts}
    for number in range(1, len(accounts) + len(account_errors) + 1):
        if number in account_errors:
            results.append(record_account_config_error(number, account_errors[number]))
            continue
        account = account_map[number]
        print(f"[{clock_text()}] ---------- 账号 {account.number} 开始 ----------")
        try:
            results.append(run_account(account, dry_run, timeout))
        except Exception as exc:
            print(
                f"[{clock_text()}] ❌ 账号 {account.number} 发生未预期错误"
                f"（{type(exc).__name__}），已安全结束该账号"
            )
            print(
                f"[{clock_text()}] [账号 {account.number} 统计] 总任务 3，成功 0，"
                "已完成 0，跳过 2，失败 1，耗时 0.00 秒"
            )
            results.append(
                AccountResult(account.number, "failed", 3, 0, 0, 2, 1, 0.0)
            )
    return finish(
        started=started,
        start_time=start_time,
        dry_run=dry_run,
        results=results,
    )


if __name__ == "__main__":
    sys.exit(main())
