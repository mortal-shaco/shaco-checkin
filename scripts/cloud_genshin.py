#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 云原神每日签到
# cron: 30 9 * * *
#
# 来源：gbxh/AutoMiyoushe cloud_genshin.py（MIT；上游 fork 自 Womsxd/AutoMihoyoBBS）
# https://github.com/gbxh/AutoMiyoushe
# 提交：c984a9f9e5108b1341cf542b1d4d986a3a335311
#
# MIT License
#
# Copyright (c) 2021-2022 Womsxd
# Copyright (c) gbxh / AutoMiyoushe contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""云原神每日签到 - 青龙独立维护版。

功能清点（相对上游 cloud_genshin.py）：
- 使用云原神 App 抓包得到的 combo_token 请求钱包接口领取每日免费时长
- 识别当日已领或达到免费时长上限（retcode=0 且 send_freetime=0）
- 查询剩余免费时长、畅玩卡状态、米云币数量
- 识别 token 失效 / 防沉迷（retcode=-100）

维护改动：
- 去掉 tools/config/setting/request/loghelper 私有依赖，标准库 HTTPS 实现
- 移除上游写回清空本地配置 token 的副作用与原始 JSON 打印
- 多账号改为 CLOUD_GENSHIN_TOKEN 每行一个 combo_token；任一账号失败整体非零退出
- 增加 CLOUD_GENSHIN_DRY_RUN 断网预演、时间轴日志、青龙通知与 TASK_SUMMARY

环境变量：
  CLOUD_GENSHIN_TOKEN       必填。每行一个账号的 x-rpc-combo_token
  CLOUD_GENSHIN_DEVICE_ID   可选。覆盖自动生成的设备 ID；多账号时每行对应一个，行数不足则回退自动生成
  CLOUD_GENSHIN_TIMEOUT     可选。单次 HTTPS 超时秒数，默认 15，范围 5..60
  CLOUD_GENSHIN_ACCOUNT_GAP 可选。账号间隔秒数，默认 2（断网预演不睡眠）
  CLOUD_GENSHIN_DRY_RUN     1/true/yes/on 开启完全断网预演
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR 见通知策略
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
        _ql_notify_identities = ('0b3d91e14d17bbc2', 'scripts/cloud_genshin.py', 'cloud_genshin.py', 'cloud_genshin')
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
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "云原神每日签到"
CATALOG_ID = "0b3d91e14d17bbc2"
SCRIPT_FILENAME = "cloud_genshin_checkin.py"
API_URL = "https://api-cloudgame.mihoyo.com/hk4e_cg_cn/wallet/wallet/get"
APP_VERSION = "3.0.0"
CLIENT_TYPE = "2"
APP_ID = "1953439974"
DEFAULT_TIMEOUT = 15
DEFAULT_ACCOUNT_GAP = 2
MAX_BYTES = 256 * 1024
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


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_timeout() -> float:
    raw = env("CLOUD_GENSHIN_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("CLOUD_GENSHIN_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("CLOUD_GENSHIN_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_account_gap() -> float:
    raw = env("CLOUD_GENSHIN_ACCOUNT_GAP")
    if not raw:
        return float(DEFAULT_ACCOUNT_GAP)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("CLOUD_GENSHIN_ACCOUNT_GAP 须为数字秒数") from exc
    if value < 0 or value > 120:
        raise SafeError("CLOUD_GENSHIN_ACCOUNT_GAP 须在 0 到 120 秒之间")
    return value


def time_conversion(minute: int) -> str:
    hours = minute // 60
    remain = minute % 60
    return "{}小时{}分钟".format(hours, remain)


def device_id_for(token: str, override: str = "") -> str:
    if override:
        return override
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "cloud-genshin:" + token))


def load_accounts() -> List[Dict[str, str]]:
    raw = os.environ.get("CLOUD_GENSHIN_TOKEN", "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise SafeError("未配置 CLOUD_GENSHIN_TOKEN，无法执行云原神签到")
    device_raw = os.environ.get("CLOUD_GENSHIN_DEVICE_ID", "")
    device_lines = [line.strip() for line in device_raw.splitlines() if line.strip()]
    accounts: List[Dict[str, str]] = []
    for index, token in enumerate(lines):
        if len(token) < 8:
            raise SafeError("第 {} 个账号的 combo_token 过短或无效".format(index + 1))
        override = device_lines[index] if index < len(device_lines) else (
            device_lines[0] if len(device_lines) == 1 else ""
        )
        accounts.append(
            {
                "token": token,
                "device_id": device_id_for(token, override),
            }
        )
    return accounts


def build_headers(token: str, device_id: str) -> Dict[str, str]:
    return {
        "x-rpc-combo_token": token,
        "x-rpc-client_type": CLIENT_TYPE,
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "mihoyo",
        "x-rpc-device_id": device_id,
        "x-rpc-device_name": "Xiaomi M2012K11AC",
        "x-rpc-device_model": "M2012K11AC",
        "x-rpc-app_id": APP_ID,
        "Referer": "https://app.mihoyo.com",
        "Host": "api-cloudgame.mihoyo.com",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "User-Agent": "okhttp/4.9.0",
    }


def http_get_json(url: str, headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise SafeError("接口响应过大，已中止解析")
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise SafeError("HTTP 状态码 {}".format(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise SafeError("网络请求失败") from exc
    except TimeoutError as exc:
        raise SafeError("请求超时") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SafeError("接口返回非 JSON") from exc
    if not isinstance(data, dict):
        raise SafeError("接口返回结构异常")
    return data


class AccountRunner:
    def __init__(self, number: int) -> None:
        self.number = number
        self.label = "账号{}".format(number)
        self.status = "failure"
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.messages: List[str] = []

    def note(self, message: str) -> None:
        self.messages.append(message)

    def finish(self) -> None:
        elapsed = time.monotonic() - self.started
        log(
            "账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                elapsed,
                self.status,
            )
        )


def stage(runner: AccountRunner, index: int, name: str) -> float:
    log("账号 {}｜阶段 {} {}：开始".format(runner.label, index, name))
    return time.monotonic()


def end_stage(runner: AccountRunner, index: int, name: str, started: float, icon: str, detail: str) -> None:
    log(
        "账号 {}｜阶段 {} {}：{} {}（{:.2f}秒）".format(
            runner.label,
            index,
            name,
            icon,
            detail,
            time.monotonic() - started,
        )
    )


def parse_wallet(data: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    retcode = data.get("retcode")
    if retcode == -100:
        return "failure", "token 失效或触发防沉迷", {}
    if retcode != 0:
        return "failure", "业务返回码异常", {}
    payload = data.get("data")
    if not isinstance(payload, dict):
        return "failure", "缺少钱包数据", {}
    free_time = payload.get("free_time") if isinstance(payload.get("free_time"), dict) else {}
    play_card = payload.get("play_card") if isinstance(payload.get("play_card"), dict) else {}
    coin = payload.get("coin") if isinstance(payload.get("coin"), dict) else {}
    try:
        send_free = int(free_time.get("send_freetime") or 0)
        remain_free = int(free_time.get("free_time") or 0)
    except (TypeError, ValueError):
        return "failure", "免费时长字段无效", {}
    coin_num = coin.get("coin_num", "未知")
    card_msg = str(play_card.get("short_msg") or "未知")
    summary = {
        "send_freetime": send_free,
        "free_time": remain_free,
        "play_card": card_msg,
        "coin_num": coin_num,
    }
    if send_free > 0:
        return (
            "success",
            "签到成功，已获得{}分钟免费时长；剩余 {}；畅玩卡 {}；米云币 {}".format(
                send_free,
                time_conversion(remain_free),
                card_msg,
                coin_num,
            ),
            summary,
        )
    return (
        "alreadyComplete",
        "今日未再获得免费时长（可能已签到或达上限）；剩余 {}；畅玩卡 {}；米云币 {}".format(
            time_conversion(remain_free),
            card_msg,
            coin_num,
        ),
        summary,
    )


def run_account(
    runner: AccountRunner,
    token: str,
    device_id: str,
    timeout: float,
    dry_run: bool,
) -> None:
    log("---------- 账号 {} / {} ----------".format(runner.number, runner.label))
    started = stage(runner, 1, "参数校验")
    if not token:
        end_stage(runner, 1, "参数校验", started, ICONS["failure"], "缺少 combo_token")
        runner.stats["failure"] += 1
        runner.status = "failure"
        return
    end_stage(runner, 1, "参数校验", started, ICONS["success"], "combo_token 已配置")
    runner.stats["success"] += 1

    started = stage(runner, 2, "云原神签到")
    if dry_run:
        end_stage(
            runner,
            2,
            "云原神签到",
            started,
            ICONS["skipped"],
            "断网预演，跳过真实请求",
        )
        runner.stats["skipped"] += 1
        runner.status = "dry-run"
        runner.note("DRY_RUN")
        return

    try:
        payload = http_get_json(API_URL, build_headers(token, device_id), timeout)
        status, detail, _summary = parse_wallet(payload)
    except SafeError as error:
        end_stage(runner, 2, "云原神签到", started, ICONS["failure"], str(error))
        runner.stats["failure"] += 1
        runner.status = "failure"
        runner.note(str(error))
        return
    except Exception:
        end_stage(runner, 2, "云原神签到", started, ICONS["failure"], "未预期的本地错误")
        runner.stats["failure"] += 1
        runner.status = "failure"
        return

    icon = ICONS.get(status, ICONS["failure"])
    end_stage(runner, 2, "云原神签到", started, icon, detail)
    runner.stats[status] = runner.stats.get(status, 0) + 1
    runner.status = status
    runner.note(detail)
    # 官方本接口通常不返回昵称；仅账号序号用于核对


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE_VALUES:
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch in TRUE_VALUES:
        return True, "QINGLONG_NOTIFY 已启用"
    selection = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selection is None:
        return False, "未设置 QINGLONG_NOTIFY_SCRIPTS，默认不通知"
    if selection.strip() == "":
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空，已禁用全部名单通知"
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", selection.strip())
        if item
    ]
    if "*" in selectors:
        return True, "通知选择列表包含 *"
    identities = {
        CATALOG_ID.lower(),
        SCRIPT_FILENAME.lower(),
        "scripts/{}".format(SCRIPT_FILENAME).lower(),
        "candidate.py",
        "cloud_genshin.py",
        "cloud_genshin",
    }
    script = Path(__file__).resolve()
    identities.add(script.name.lower())
    try:
        identities.add(script.as_posix().lower())
    except Exception:
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


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("CLOUD_GENSHIN_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[Dict[str, str]] = []
    timeout = float(DEFAULT_TIMEOUT)
    account_gap = float(DEFAULT_ACCOUNT_GAP)
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("CLOUD_GENSHIN_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        account_gap = resolve_account_gap()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；账号间隔：{}秒".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                int(account_gap) if float(account_gap).is_integer() else account_gap,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts: List[AccountRunner] = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(
                    runner,
                    item["token"],
                    item["device_id"],
                    timeout,
                    dry_run,
                )
            except SafeError as error:
                runner.status = "failure"
                log("账号 {}：❌ {}".format(number, error))
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(accounts_data) and account_gap > 0:
                time.sleep(account_gap)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in accounts if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in accounts if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in accounts if item.status == "failure"),
        "dry-run": sum(1 for item in accounts if item.status == "dry-run"),
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
    tasks = {key: sum(item.stats[key] for item in accounts) for key in STATES}
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
    final_label = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIG_ERROR",
        "dry-run": "DRY-RUN",
    }.get(status, status.upper())
    log("最终状态：{}".format(final_label))
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
