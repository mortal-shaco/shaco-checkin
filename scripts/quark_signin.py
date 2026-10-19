#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 夸克网盘每日签到
# cron: 15 0 * * *
# SPDX-License-Identifier: GPL-3.0-only
# Original maintained source license notice: SPDX-License-Identifier: MIT
# Maintained standalone adaptation of quark_signin.py from agluo/ql-script-hub.
# Original source commit: a8d39b97cb22c3ac657089014df754342b456ff6
# Compatible mobile signing adaptation: Cp0204/quark-auto-save, GPL-3.0-only.
# Repo: https://github.com/Cp0204/quark_auto_save
# Modify: 2026-02-04
# ConfigFile: quark_config.json (upstream attribution; this script needs no file)
# Upstream commit: 1c35e969332e03980f60c34fc15b2467370bafb2

"""夸克网盘每日存储空间签到（青龙独立版）。

必填环境变量：
  QUARK_COOKIE  每个非空行为一个账号的完整 Cookie。登录 https://pan.quark.cn/
                后打开浏览器开发者工具的“网络”面板，选择夸克请求，
                复制请求头 Cookie 的完整值。

可选环境变量：
  QUARK_DRY_RUN=1                   完全断网预演。
  QUARK_TIMEOUT_SECONDS=15          单次请求超时，范围 3..60 秒。
  QUARK_RANDOM_DELAY_MAX_SECONDS=0  每个实时账号执行前的随机延迟上限，范围 0..3600。
  QINGLONG_NOTIFY=1                 设为 0/false/no/off 可关闭通知。
  QINGLONG_NOTIFY_DIR               可选，青龙 notify.py 所在目录。

账号只使用换行分隔；脚本绝不输出 Cookie 或原始响应。
默认保持原有网页 Cookie 接口和每日 18:13 定时。可混合配置：
  pc|完整网页 Cookie       （pc| 前缀可省略，原参数无需修改）
  mobile|移动端凭据文本    （文本需包含同账号的 kps、sign、vcode，分号分隔）
移动端凭据：登录夸克手机应用，用自己的抓包工具查看 growth/info 或
 growth/sign 请求的查询参数，将 kps、sign、vcode 的原始编码值组合到同一行。
不要使用他人凭据；不要复制请求 URL、设备标识或手机号。
前缀只按首个 | 切分，后续文本原样保留；绝不使用 & 或 @ 分隔账号。
移动端模式按上游 fr=android 和三项签名参数请求，网页模式不会自动切换接口。
两种模式都先查询明确的签到布尔状态，再决定是否领取奖励。
兼容展示官方返回的会员类型、总容量、签到累计容量（字段有效时）。
本版本只优化同周期的签到能力。上游追更任务定时为 0 8,18,20 * * *，
涉及转存、创建目录、重命名、可选删除及插件；其风险和调度不同，未合入。
不读取 quark_config.json、TASKLIST、PUSH_CONFIG，不安装插件或下载配置。
QUARK_TEST 的转存测试及删除回收站逻辑不适用于本签到任务。
青龙通知在实时运行时发送；完全断网预演仅生成通知摘要，不调用通知模块。
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
        _ql_notify_identities = ('18c47e12eda9864c', 'scripts/quark_signin.py', 'quark_signin.py', 'quark_signin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import importlib
import importlib.util
import json
import os
import random
import re
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler


TASK_NAME = "夸克网盘每日签到"
DRY_RUN_ENV = "QUARK_DRY_RUN"
COOKIE_ENV = "QUARK_COOKIE"
DISABLED_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
MAX_RESPONSE_BYTES = 65536
API_QUERY = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}


class TaskError(Exception):
    """仅包含可安全展示信息的任务异常。"""


@dataclass
class Stats:
    total: int = 0
    success: int = 0
    already: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, status: str) -> None:
        self.total += 1
        if status == "success":
            self.success += 1
        elif status == "already":
            self.already += 1
        elif status == "skipped":
            self.skipped += 1
        else:
            self.failed += 1

    def merge(self, other: "Stats") -> None:
        for key in ("total", "success", "already", "skipped", "failed"):
            setattr(self, key, getattr(self, key) + getattr(other, key))

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "success": self.success,
            "alreadyComplete": self.already,
            "skipped": self.skipped,
            "failed": self.failed,
        }


@dataclass
class AccountResult:
    ok: bool
    stats: Stats = field(default_factory=Stats)
    outcome: str = "failed"


def iso_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clock_time() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise TaskError(f"{name} 必须是整数") from exc
    if not minimum <= value <= maximum:
        raise TaskError(f"{name} 必须在 {minimum}..{maximum} 之间")
    return value


def load_accounts() -> list[str]:
    raw = os.getenv(COOKIE_ENV, "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    if not accounts:
        raise TaskError(f"未配置 {COOKIE_ENV}；每个账号使用一个非空行")
    return accounts


def business_data(payload: dict[str, Any], operation: str) -> Any:
    """兼容夸克已知的 code、status、success 和仅 data 响应包装。

    上游账号接口以 data 为成功依据，部分响应不返回 code。如果响应中
    出现业务标记，它必须是显式成功值；无论响应包装如何，data 都必须
    存在且非空，各调用方还会继续校验所需字段。
    """
    if "code" in payload:
        code = payload.get("code")
        if type(code) not in (int, str) or code not in (0, "0"):
            shown = safe_code(code)
            raise TaskError(f"{operation}失败（业务码 {shown}；{response_shape(payload)}）")
    if "status" in payload:
        status = payload.get("status")
        if type(status) not in (int, str) or status not in (200, "200"):
            shown = safe_code(status)
            raise TaskError(f"{operation}失败（业务状态 {shown}；{response_shape(payload)}）")
    if "success" in payload and payload.get("success") is not True:
        raise TaskError(f"{operation}失败（业务成功标记为否；{response_shape(payload)}）")
    if "data" not in payload or payload["data"] is None:
        raise TaskError(f"{operation}失败（成功响应缺少 data；{response_shape(payload)}）")
    return payload["data"]


def field_shape(data: dict[str, Any], key: str) -> str:
    """仅报告固定字段的类型，不回显字段内容或未知字段名。"""
    if key not in data:
        return "缺失"
    value = data[key]
    if value is None:
        return "空值"
    return {dict: "对象", list: "数组", str: "文本", bool: "布尔",
            int: "整数", float: "小数"}.get(type(value), "其他")


def response_shape(payload: dict[str, Any]) -> str:
    fields = []
    for key in ("code", "status"):
        fields.append(f"{key}={safe_code(payload[key])}" if key in payload
                      else f"{key}=缺失")
    fields.extend(f"{key}类型={field_shape(payload, key)}" for key in ("success", "data"))
    return "，".join(fields)


def safe_code(value: Any) -> str:
    """业务码仅输出有限长度的整数，禁止把任意响应字符串写入日志。"""
    if type(value) is int and abs(value) <= 10**12:
        return str(value)
    if isinstance(value, str) and value.lstrip("-").isascii() and value.lstrip("-").isdigit() and len(value) <= 13:
        return value
    return "非数字或缺失"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把 Cookie 随跳转发送至其他地址；接口迁移需要人工核对。
        return None


class QuarkClient:
    def __init__(self, cookie: str, timeout: int):
        self.cookie = cookie
        self.timeout = timeout
        self.ssl_context = ssl.create_default_context()
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=self.ssl_context))

    def request_json(
        self, method: str, base_url: str, query: dict[str, str], body: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(query)}"
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        request = Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Cookie": self.cookie,
                "User-Agent": "Mozilla/5.0 Qinglong-Quark-Signin/1.1",
            },
        )
        if not self.cookie:
            request.remove_header("Cookie")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise TaskError(f"HTTP 请求失败（状态 {exc.code}）") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TaskError(f"网络请求失败（{type(exc).__name__}）") from exc
        except UnicodeEncodeError as exc:
            raise TaskError("Cookie 请求头无法编码，请复制浏览器网络面板的完整原始 Cookie 值，不要添加中文备注") from exc
        except ValueError as exc:
            raise TaskError("请求头格式无效，请重新复制 Cookie 值，不要包含请求头名称或控制字符") from exc
        if not 200 <= status < 300:
            raise TaskError(f"HTTP 请求失败（状态 {status}）")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TaskError("接口响应超过安全大小限制")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TaskError("接口返回的 JSON 无效") from exc
        if not isinstance(payload, dict):
            raise TaskError("接口返回格式无效")
        return payload

    def account_info(self) -> dict[str, Any]:
        payload = self.request_json(
            "GET", "https://pan.quark.cn/account/info", {"fr": "pc", "platform": "pc"}
        )
        data = business_data(payload, "账号验证")
        if not isinstance(data, dict) or not data:
            raise TaskError(f"账号验证失败（data 为空或格式无效；{response_shape(payload)}）")
        return data

    def growth_info(self) -> dict[str, Any]:
        payload = self.request_json(
            "GET", "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info", API_QUERY
        )
        data = business_data(payload, "签到状态查询")
        if not isinstance(data, dict) or not isinstance(data.get("cap_sign"), dict):
            shape = field_shape(data, "cap_sign") if isinstance(data, dict) else "不可读取"
            raise TaskError(f"签到状态查询失败（cap_sign 类型={shape}；{response_shape(payload)}）")
        return data

    def sign(self) -> dict[str, Any]:
        payload = self.request_json(
            "POST",
            "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign",
            API_QUERY,
            {"sign_cyclic": True},
        )
        data = business_data(payload, "签到")
        if not isinstance(data, dict) or not valid_number(data.get("sign_daily_reward")):
            shape = field_shape(data, "sign_daily_reward") if isinstance(data, dict) else "不可读取"
            raise TaskError(f"签到失败（奖励字段缺失或无效；sign_daily_reward 类型={shape}；{response_shape(payload)}；请先查询签到状态再重试）")
        return data


def account_credential(value: str) -> tuple[str, str]:
    """仅解析明确的模式前缀，保留后续全部凭据内容。"""
    mode, credential = "pc", value
    if value.startswith(("pc|", "mobile|")):
        mode, credential = value.split("|", 1)
    if not credential.strip():
        raise TaskError("账号凭据为空")
    if any(ord(char) < 32 or ord(char) == 127 for char in credential):
        raise TaskError("账号凭据包含非法控制字符")
    return mode, credential


def mobile_parameters(credential: str) -> dict[str, str]:
    params = {}
    # 上游支持原始编码值，并仅把二次编码的 %25 还原一次。
    for key in ("kps", "sign", "vcode"):
        matches = re.findall(r"(?:^|[;\s])" + key + r"=([a-zA-Z0-9%+/=]+)(?=;|\s|$)", credential)
        if len(matches) != 1:
            raise TaskError(f"移动端凭据必须包含且仅包含一个 {key}；请使用分号分隔同账号的三项参数")
        params[key] = matches[0].replace("%25", "%")
    return params


class MobileQuarkClient(QuarkClient):
    """采用上游已给出的移动端签到契约；不改变网页默认接口。"""

    def __init__(self, credential: str, timeout: int):
        self.mobile_query = {"pr": "ucpro", "fr": "android", **mobile_parameters(credential)}
        super().__init__("", timeout)
        self.cached_growth: Optional[dict[str, Any]] = None

    def account_info(self) -> dict[str, Any]:
        # 纯移动端凭据不能验证网页 Cookie；通过签名的只读容量接口认证。
        self.cached_growth = self.growth_info()
        identity = {key: self.cached_growth[key]
                    for key in ("nickname", "username", "display_name", "uid")
                    if key in self.cached_growth}
        return identity or {"authenticated": True}

    def growth_info(self) -> dict[str, Any]:
        if self.cached_growth is not None:
            return self.cached_growth
        payload = self.request_json(
            "GET", "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info", self.mobile_query
        )
        data = business_data(payload, "移动端签到状态查询")
        if not isinstance(data, dict) or not isinstance(data.get("cap_sign"), dict):
            raise TaskError(f"移动端签到状态查询失败（{response_shape(payload)}）")
        return data

    def sign(self) -> dict[str, Any]:
        payload = self.request_json(
            "POST", "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign",
            self.mobile_query, {"sign_cyclic": True}
        )
        data = business_data(payload, "移动端签到")
        if not isinstance(data, dict) or not valid_number(data.get("sign_daily_reward")):
            raise TaskError(f"移动端签到失败（奖励字段无效；{response_shape(payload)}；请先查询签到状态再重试）")
        return data


def make_client(value: str, timeout: int) -> QuarkClient:
    mode, credential = account_credential(value)
    return MobileQuarkClient(credential, timeout) if mode == "mobile" else QuarkClient(credential, timeout)


def capacity_detail(growth: dict[str, Any]) -> str:
    details = []
    memberships = {"NORMAL": "普通用户", "EXP_SVIP": "88VIP", "SUPER_VIP": "SVIP", "Z_VIP": "SVIP+"}
    member = growth.get("member_type")
    if isinstance(member, str) and member in memberships:
        details.append("会员类型：" + memberships[member])
    if valid_number(growth.get("total_capacity")):
        details.append(f"总空间：{reward_mb(growth['total_capacity'])} MB")
    composition = growth.get("cap_composition")
    if isinstance(composition, dict) and valid_number(composition.get("sign_reward")):
        details.append(f"签到累计获得：{reward_mb(composition['sign_reward'])} MB")
    return "，" + "，".join(details) if details else ""


def valid_number(value: Any) -> bool:
    import math
    return type(value) in (int, float) and value >= 0 and math.isfinite(value)


def reward_mb(value: Any) -> int:
    return int(value / 1024 / 1024) if valid_number(value) else 0


def stage(number: int, title: str, status: str, detail: str, stats: Stats, started: float) -> None:
    icons = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failure": "❌"}
    stats.add(status)
    elapsed = time.monotonic() - started
    print(f"  [{clock_time()}] [{number}/3] {title}: {icons[status]} {detail}（{elapsed:.2f}s）")


def run_account(index: int, cookie: str, timeout: int, dry_run: bool, delay_max: int) -> AccountResult:
    account_started = time.monotonic()
    stats = Stats()
    print(f"\n[{clock_time()}] 账号 {index}")
    if dry_run:
        step_started = time.monotonic()
        try:
            mode, credential = account_credential(cookie)
            if mode == "mobile":
                mobile_parameters(credential)
        except TaskError as exc:
            stage(1, "账号配置", "failure", str(exc), stats, step_started)
            for number in (2, 3):
                stage(number, "后续任务", "skipped", "配置错误，未访问网络", stats, time.monotonic())
            print(f"  账号统计: 总任务={stats.total} 成功={stats.success} 已完成={stats.already} 跳过={stats.skipped} 失败={stats.failed} 耗时={time.monotonic() - account_started:.2f}s")
            return AccountResult(False, stats, "failed")
        stage(1, "账号配置", "success", f"已检测到非空凭据（内容已隐藏），模式={mode}", stats, step_started)
        step_started = time.monotonic()
        stage(2, "签到状态", "success", "离线预演：将查询今日签到状态", stats, step_started)
        step_started = time.monotonic()
        stage(3, "领取奖励", "skipped", "离线预演：不会发送签到请求", stats, step_started)
        elapsed = time.monotonic() - account_started
        print(f"  账号统计: 总任务={stats.total} 成功={stats.success} 已完成={stats.already} 跳过={stats.skipped} 失败={stats.failed} 耗时={elapsed:.2f}s")
        return AccountResult(True, stats, "dry-run")

    if delay_max:
        delay = random.randint(0, delay_max)
        if delay:
            print(f"  [{clock_time()}] 执行前随机等待 {delay}s")
            time.sleep(delay)
    step_started = time.monotonic()
    try:
        if any(ord(char) < 32 or ord(char) == 127 for char in cookie):
            raise TaskError("Cookie 包含非法控制字符，请重新复制请求头")
        client = make_client(cookie, timeout)
        step_started = time.monotonic()
        account = client.account_info()
        identity = next((account[key] for key in ("nickname", "username", "display_name", "uid")
                         if isinstance(account.get(key), (str, int)) and account[key]), None)
        identity_text = f"，昵称：{identity}" if isinstance(identity, (str, int)) and identity else ""
        stage(1, "账号验证", "success", f"{'移动端凭据有效' if isinstance(client, MobileQuarkClient) else 'Cookie 有效'}{identity_text}", stats, step_started)
        step_started = time.monotonic()
        growth = client.growth_info()
        cap_sign = growth["cap_sign"]
        if type(cap_sign.get("sign_daily")) is not bool:
            raise TaskError(f"签到状态查询失败（cap_sign.sign_daily 类型={field_shape(cap_sign, 'sign_daily')}；要求布尔值，未执行签到）")
        stage(2, "签到状态", "success", "已获取签到状态" + capacity_detail(growth), stats, step_started)
        step_started = time.monotonic()
        if cap_sign.get("sign_daily") is True:
            reward = reward_mb(cap_sign.get("sign_daily_reward"))
            progress = cap_sign.get("sign_progress")
            target = cap_sign.get("sign_target")
            suffix = f"，连签进度 {progress}/{target}" if isinstance(progress, int) and isinstance(target, int) else ""
            stage(3, "领取奖励", "already", f"今日已签到，奖励 {reward} MB{suffix}", stats, step_started)
            outcome = "already-complete"
        else:
            signed = client.sign()
            reward = reward_mb(signed["sign_daily_reward"])
            progress, target = cap_sign.get("sign_progress"), cap_sign.get("sign_target")
            suffix = f"，连签进度 {progress + 1}/{target}" if type(progress) is int and type(target) is int else ""
            stage(3, "领取奖励", "success", f"签到成功，奖励 {reward} MB{suffix}", stats, step_started)
            outcome = "success"
        ok = True
    except TaskError as exc:
        step_number = min(stats.total + 1, 3)
        stage(step_number, ("账号验证", "签到状态", "领取奖励")[step_number - 1], "failure", str(exc), stats, step_started)
        ok, outcome = False, "failed"
    except Exception as exc:
        step_number = min(stats.total + 1, 3)
        stage(step_number, ("账号验证", "签到状态", "领取奖励")[step_number - 1], "failure",
              f"执行异常（{type(exc).__name__}；详情已隐藏）", stats, step_started)
        ok, outcome = False, "failed"
    if not ok:
        while stats.total < 3:
            stage(stats.total + 1, "后续任务", "skipped", "前置步骤失败", stats, time.monotonic())
    elapsed = time.monotonic() - account_started
    print(f"  账号统计: 总任务={stats.total} 成功={stats.success} 已完成={stats.already} 跳过={stats.skipped} 失败={stats.failed} 耗时={elapsed:.2f}s")
    return AccountResult(ok, stats, outcome)


def notification_enabled() -> bool:
    return os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in DISABLED_VALUES


def find_notifier() -> Optional[Callable[[str, str], Any]]:
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
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in paths:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, "send", None)
                if callable(sender):
                    return sender
        except Exception:
            continue
    return None


def notify(summary: str, dry_run: bool) -> str:
    if not notification_enabled():
        print("通知状态: 已关闭（QINGLONG_NOTIFY）")
        return "disabled"
    if dry_run:
        print("通知状态: 离线预演已生成通知摘要，未调用通知模块")
        return "dry-run-simulated"
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        sender = find_notifier()
    if sender is None:
        print("通知状态: ⚠️ 未找到青龙 notify.py，业务退出码不变")
        return "unavailable"
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            sender(TASK_NAME, summary)
        print("通知状态: ✅ 已发送")
        return "sent"
    except Exception as exc:
        print(f"通知状态: ⚠️ 发送失败（{type(exc).__name__}），业务退出码不变")
        return "failed"


def main() -> int:
    task_started = time.monotonic()
    start_time = iso_time()
    dry_run = env_flag(DRY_RUN_ENV)
    print(f"========== {TASK_NAME} ==========")
    print(f"开始时间: {start_time}")
    print(f"运行模式: {'DRY-RUN（完全离线）' if dry_run else 'LIVE'}")
    accounts: list[str] = []
    config_error: Optional[str] = None
    try:
        accounts = load_accounts()
        timeout = bounded_int("QUARK_TIMEOUT_SECONDS", 15, 3, 60)
        delay_max = bounded_int("QUARK_RANDOM_DELAY_MAX_SECONDS", 0, 0, 3600)
    except TaskError as exc:
        config_error = str(exc)
        timeout, delay_max = 15, 0
    print(f"账号数量: {len(accounts)}")

    results: list[AccountResult] = []
    all_stats = Stats()
    if config_error:
        print(f"\n[{clock_time()}] [配置检查] ❌ {config_error}")
    else:
        for index, cookie in enumerate(accounts, 1):
            result = run_account(index, cookie, timeout, dry_run, delay_max)
            results.append(result)
            all_stats.merge(result.stats)

    account_success = sum(1 for item in results if item.ok)
    account_failure = len(accounts) - account_success
    business_ok = config_error is None and account_failure == 0
    if config_error:
        final_status = "configuration-error"
    elif dry_run and account_failure == 0:
        final_status = "dry-run"
    elif account_failure == 0:
        final_status = "success"
    elif account_success:
        final_status = "partial-failure"
    else:
        final_status = "failure"

    notice_body = f"账号总数: {len(accounts)}，成功: {account_success}，失败: {account_failure}，状态: {final_status}"
    notice_status = notify(notice_body, dry_run)
    elapsed = time.monotonic() - task_started
    finish_time = iso_time()
    print("\n----------------------------------------")
    print("任务统计:")
    print(f"  账号结果: 总数={len(accounts)} 成功={account_success} 失败={account_failure}")
    print(f"  子任务结果: 总数={all_stats.total} 成功={all_stats.success} 已完成={all_stats.already} 跳过={all_stats.skipped} 失败={all_stats.failed}")
    print(f"  总耗时: {elapsed:.2f}s")
    print(f"  完成时间: {finish_time}")
    print(f"  通知状态: {notice_status}")
    print(f"最终状态: {'✅' if business_ok else '❌'} {final_status}")
    summary = {
        "task": TASK_NAME,
        "mode": "dry-run" if dry_run else "live",
        "status": final_status,
        "accounts": {"total": len(accounts), "success": account_success, "failed": account_failure},
        "steps": all_stats.as_dict(),
        "notification": notice_status,
        "durationSeconds": round(elapsed, 3),
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0 if business_ok else 1


if __name__ == "__main__":
    sys.exit(main())
