#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NGA 论坛签到
# cron: 49 0 * * *
# SPDX-License-Identifier: MIT
# Additional compatible source: yongyeym/AutoSign_QingLong, nga_sign.py
# commit f13a88e488c2d396e24cce8e9b6e27eefcbccad6 (MIT).
# Upstream alternative schedule: 3 0 * * *; canonical default retained below.
# Maintained from nga_checkin.py in agluo/ql-script-hub (commit
# a8d39b97cb22c3ac657089014df754342b456ff6). Original and modifications MIT.
"""NGA daily check-in and optional mission actions for Qinglong.

Accounts are configured as ``access_uid|access_token`` lines in NGA_ACCOUNT.
The script never logs either value. Optional mission actions
are off by default because they mutate reward/task state beyond check-in.

参数获取：登录自己的 NGA 客户端，从授权抓包取得 access_uid、access_token。
iOS 账号同时获取签到请求的 __ngaClientChecksum，使用 NGA_ACCOUNT 单行 JSON：
字段 access_uid、access_token、client_checksum 均为字符串；不填写真实凭据示例。
每个非空行一个账号。旧版 nga_uid、nga_cookie、nga_client_checksum 在未设置
NGA_ACCOUNT 时兼容，需逐行对应。CLIENT ERROR 时更新当前 iOS 客户端校验码。
NGA_DRY_RUN=1 完全断网；正式通知遵循 QINGLONG_NOTIFY，预演只生成本地摘要。
默认定时 17:01 保持不变，原 iOS 来源的 00:03 可在青龙中按需修改。

"""

from __future__ import annotations

import importlib
import hashlib
import uuid
from datetime import datetime
import importlib.util
import json
import os
import random
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


TITLE = "NGA论坛签到"
API_URL = "https://ngabbs.com/nuke.php"
APP_ID = "1010"
MAX_RESPONSE_BYTES = 65536
DISABLED_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = DISABLED_VALUES


class ConfigError(ValueError):
    """A safe-to-display configuration error."""


class ApiError(RuntimeError):
    """A redacted transport or response error."""


@dataclass(frozen=True)
class Config:
    uids: list[str]
    tokens: list[str]
    checksums: list[str]
    user_agent: str
    dry_run: bool
    daily_missions: bool
    video_missions: bool
    share_missions: bool
    query_stats: bool
    random_delay_max: int
    action_delay: float
    video_delay: float
    timeout: float


@dataclass
class AccountResult:
    index: int
    success: bool = True
    outcomes: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"success": 0, "already": 0, "skipped": 0, "failure": 0})
    started: float = field(default_factory=time.monotonic)
    stage_started: float = field(default_factory=time.monotonic)

    def add(self, action: str, ok: bool, detail: str) -> None:
        state = "already" if ok and "已签到" in detail else "success" if ok else "failure"
        self.counts[state] += 1
        self.outcomes.append(f"{action}: {detail}")
        log(f"账号{self.index} 阶段 {len(self.outcomes)} [{action}] {'☑️' if state == 'already' else '✅' if ok else '❌'} {detail}；耗时 {time.monotonic() - self.stage_started:.2f} 秒")
        self.stage_started = time.monotonic()
        if not ok:
            self.success = False


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ConfigError(f"{name} 必须是 1/0、true/false、yes/no 或 on/off")


def env_number(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数字") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return value


def account_lines(name: str) -> dict[int, str]:
    value = os.getenv(name, "").replace("\r\n", "\n").replace("\r", "\n")
    if not value.strip():
        raise ConfigError(f"缺少必填环境变量 {name}")
    return {index: line.strip() for index, line in enumerate(value.split("\n"), 1) if line.strip()}


def load_config() -> Config:
    # JSON lines permit all same-account credentials without ambiguous delimiters.
    uids, tokens, checksums = [], [], []
    if os.getenv("NGA_ACCOUNT", "").strip():
        account_values = account_lines("NGA_ACCOUNT")
        for index, value in account_values.items():
            if value.startswith("{"):
                try:
                    item = json.loads(value)
                    uid, token = item["access_uid"], item["access_token"]
                    checksum = item.get("client_checksum", "")
                except (ValueError, TypeError, KeyError):
                    raise ConfigError(f"NGA_ACCOUNT 第 {index} 行 JSON 凭据格式无效") from None
            elif "|" in value:
                uid, token = (part.strip() for part in value.split("|", 1))
                checksum = ""
            else:
                raise ConfigError(f"NGA_ACCOUNT 第 {index} 行必须是 UID|Token 或 JSON 对象")
            if not all(isinstance(v, str) for v in (uid, token, checksum)):
                raise ConfigError(f"NGA_ACCOUNT 第 {index} 行凭据必须是文本")
            uids.append(uid.strip()); tokens.append(token.strip()); checksums.append(checksum.strip())
    else:
        # Legacy source variables remain optional compatibility inputs.
        if not any(os.getenv(name, "").strip() for name in ("nga_uid", "nga_cookie", "nga_client_checksum")):
            raise ConfigError("缺少必填环境变量 NGA_ACCOUNT")
        legacy = [account_lines(name) for name in ("nga_uid", "nga_cookie", "nga_client_checksum")]
        if not (list(legacy[0]) == list(legacy[1]) == list(legacy[2])):
            raise ConfigError("旧版凭据必须每行对应同一账号，且行数一致")
        uids, tokens, checksums = [list(values.values()) for values in legacy]
    for index, (uid, token, checksum) in enumerate(zip(uids, tokens, checksums), 1):
        if not uid or not token or any(c in uid + token + checksum for c in "\r\n\x00"):
            raise ConfigError(f"账号 {index} 凭据为空或包含控制字符")
        if checksum and any(c in uid + token for c in ";"):
            raise ConfigError(f"账号 {index} iOS 凭据包含非法 Cookie 分隔符")
    user_agent = os.getenv("NGA_UA", "Nga_Official/90409").strip()
    if not user_agent or "\r" in user_agent or "\n" in user_agent:
        raise ConfigError("NGA_UA 不能为空或包含换行")
    return Config(
        uids=uids,
        tokens=tokens,
        checksums=checksums,
        user_agent=user_agent,
        dry_run=env_bool("NGA_DRY_RUN", False),
        daily_missions=env_bool("NGA_ENABLE_DAILY_MISSIONS", False),
        video_missions=env_bool("NGA_ENABLE_VIDEO_MISSIONS", False),
        share_missions=env_bool("NGA_ENABLE_SHARE_MISSIONS", False),
        query_stats=env_bool("NGA_QUERY_STATS", True),
        random_delay_max=int(env_number("NGA_RANDOM_DELAY_MAX", 0, 0, 21600)),
        action_delay=env_number("NGA_ACTION_DELAY_SECONDS", 1, 0, 30),
        video_delay=env_number("NGA_VIDEO_DELAY_SECONDS", 30, 0, 120),
        timeout=env_number("NGA_HTTP_TIMEOUT", 20, 3, 60),
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError("拒绝接口重定向，避免凭据发送至其他地址")


class NgaClient:
    def __init__(self, uid: str, token: str, user_agent: str, timeout: float, checksum: str = ""):
        self.uid = uid
        self.token = token
        self.user_agent = user_agent
        self.timeout = timeout
        self.checksum = checksum
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect()
        )

    def request(self, lib: str, act: str, extra: Optional[dict[str, str]] = None) -> dict[str, Any]:
        form = {
            "access_uid": self.uid,
            "access_token": self.token,
            "app_id": APP_ID,
            "__act": act,
            "__lib": lib,
            "__output": "11",
        }
        if extra:
            form.update(extra)
        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }
        if self.checksum:
            ios_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NGA_skull/10.1.36"
            user_info = "%25" + uuid.uuid4().hex
            form.update({"app_id": "1100", "device": "iOS;" + hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                         "__ngaClientChecksum": self.checksum, "__inchst": "UTF-8"})
            headers.update({"User-Agent": ios_ua, "X-USER-AGENT": ios_ua,
                            "Origin": "https://ngabbs.com", "Referer": "https://ngabbs.com/misc/mission/mission.php",
                            "Cookie": f"ngacn0comInfoCheckTime={int(time.time())}; ngacn0comUserInfo={user_info}; ngacn0comUserInfoCheck={hashlib.md5(user_info.encode()).hexdigest()}; bbsmisccookies=%7B%7D; access_token={self.token}; access_uid={self.uid}"})
            # Match the upstream iOS multipart contract with correct CRLF and computed length.
            boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
            body_data = "".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n' for key, value in form.items())
            body_data = (body_data + f"--{boundary}--\r\n").encode("utf-8")
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        else:
            body_data = urllib.parse.urlencode(form).encode("utf-8")
        request = urllib.request.Request(
            API_URL,
            data=body_data,
            headers=headers,
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP 状态异常 ({exc.code})") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ApiError("网络请求失败或超时") from None
        if status < 200 or status >= 300:
            raise ApiError(f"HTTP 状态异常 ({status})")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ApiError("响应超过安全大小限制")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError("响应不是有效 JSON") from None
        if not isinstance(payload, dict):
            raise ApiError("响应结构无效")
        return payload


def error_text(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, list) and error:
        return str(error[0])
    if isinstance(error, str):
        return error
    return ""


def explicit_success(payload: dict[str, Any]) -> bool:
    if error_text(payload):
        return False
    if "data" in payload and payload["data"] not in (None, False, ""):
        return True
    if payload.get("code") in (0, "0"):
        return True
    return bool(payload.get("time"))


def pause(seconds: float, dry_run: bool) -> None:
    if not dry_run and seconds > 0:
        time.sleep(seconds)


def run_live_account(index: int, config: Config) -> AccountResult:
    result = AccountResult(index=index)
    client = NgaClient(config.uids[index - 1], config.tokens[index - 1], config.user_agent, config.timeout, config.checksums[index - 1])
    log(f"账号{index}: 开始执行（凭据已隐藏）")
    try:
        checkin = client.request("check_in", "check_in")
    except ApiError as exc:
        result.add("签到", False, str(exc))
        return result

    show_identity(checkin, index, config)
    message = error_text(checkin)
    already_done = "已经签到" in message or "今天已经签到了" in message
    data = checkin.get("data")
    data_message = str(data[0]) if isinstance(data, list) and data else ""
    already_done = already_done or "已经签到" in data_message or "今天已经签到了" in data_message
    checked_in = not message and "签到成功" in data_message
    if checked_in:
        detail = "成功"
        if len(data) > 1 and isinstance(data[1], dict):
            days = {key: data[1].get(key) for key in ("sum", "continued")}
            if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in days.values()):
                detail += f"；连续 {days['continued']} 天，累计 {days['sum']} 天"
        result.add("签到", True, detail)
    elif already_done:
        result.add("签到", True, "今日已签到")
    else:
        detail = "登录凭据失效，请更新 NGA_ACCOUNT" if "你必须先登录论坛" in message else "iOS 客户端校验码失效或不适配，请从当前 iOS 客户端抓包更新 client_checksum" if "CLIENT ERROR" in message else "服务端未确认成功"
        result.add("签到", False, detail)
        return result

    def perform(action: str, lib: str, act: str, extra: Optional[dict[str, str]] = None) -> bool:
        try:
            payload = client.request(lib, act, extra)
            ok = explicit_success(payload)
            result.add(action, ok, "成功" if ok else "服务端未确认成功")
            return ok
        except ApiError as exc:
            result.add(action, False, str(exc))
            return False

    if config.daily_missions:
        for mission_id in ("2", "131", "30"):
            perform(
                f"日常任务{mission_id}",
                "mission",
                "checkin_count_add",
                {"mid": mission_id, "get_success_repeat": "1", "no_compatible_fix": "1"},
            )
            pause(config.action_delay, False)

    if config.video_missions:
        perform("免广告任务初始化", "mission", "video_view_task_counter_add_v2_for_adfree_sp1")
        for number in range(1, 5):
            pause(config.video_delay, False)
            perform(f"免广告任务{number}/4", "mission", "video_view_task_counter_add_v2_for_adfree")
        for number in range(1, 6):
            pause(config.video_delay, False)
            perform(f"N币视频任务{number}/5", "mission", "video_view_task_counter_add_v2")

    if config.share_missions:
        topic_id = str(random.SystemRandom().randint(12345678, 24692245))
        for number in range(1, 6):
            perform(
                f"分享记录{number}/5",
                "data_query",
                "topic_share_log_v2",
                {"event": "4", "tid": topic_id},
            )
            pause(config.action_delay, False)
        perform(
            "分享奖励",
            "mission",
            "check_mission",
            {"mid": "149", "get_success_repeat": "1", "no_compatible_fix": "1"},
        )

    if config.query_stats:
        try:
            stats = client.request("check_in", "get_stat")
            show_identity(stats, index, config)
            data = stats.get("data")
            ok = not error_text(stats) and isinstance(data, list) and len(data) >= 3 and all(isinstance(item, dict) for item in data[:3])
            result.add("资产查询", ok, "成功" if ok else "响应结构未确认")
        except ApiError as exc:
            result.add("资产查询", False, str(exc))
    return result


def dry_run_account(index: int, config: Config) -> AccountResult:
    actions = ["签到"]
    if config.daily_missions:
        actions.extend(["日常任务2", "日常任务131", "日常任务30"])
    if config.video_missions:
        actions.extend(["免广告任务初始化", "免广告任务×4", "N币视频任务×5"])
    if config.share_missions:
        actions.extend(["分享记录×5", "分享奖励"])
    if config.query_stats:
        actions.append("资产查询")
    log(f"账号{index}: DRY-RUN，凭据格式已验证，未发起网络请求")
    log(f"账号{index}: 计划动作: {', '.join(actions)}")
    result = AccountResult(index=index)
    result.add("预演", True, "配置有效且无网络请求")
    return result


def notification_enabled() -> bool:
    return os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in DISABLED_VALUES


def load_notify_send() -> Optional[Callable[[str, str], Any]]:
    try:
        module = importlib.import_module("notify")
        candidate = getattr(module, "send", None)
        if callable(candidate):
            return candidate
    except Exception:
        pass
    paths: list[Path] = []
    configured = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if configured:
        paths.append(Path(configured) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            candidate = getattr(module, "send", None)
            if callable(candidate):
                return candidate
        except Exception:
            continue
    return None


def notify(summary: str, dry_run: bool = False) -> str:
    if not notification_enabled():
        log("通知: 已由 QINGLONG_NOTIFY 关闭")
        return "关闭"
    if dry_run:
        log("通知: DRY-RUN 汇总已生成，禁止调用可能联网的通知模块")
        return "预演，仅本地汇总"
    sender = load_notify_send()
    if sender is None:
        paths = [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
        if os.getenv("QINGLONG_NOTIFY_DIR", "").strip():
            paths.insert(0, Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "sendNotify.js")
        for path in paths:
            if path.is_file():
                try:
                    program = "const m=require(process.argv[1]); Promise.resolve(m.sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1));"
                    delivery = subprocess.run(["node", "-e", program, str(path.resolve()), TITLE, summary],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
                    if delivery.returncode == 0:
                        log("通知: 已通过 sendNotify.js 提交脱敏汇总")
                        return "已提交"
                except (OSError, subprocess.TimeoutExpired):
                    pass
        log("通知: 未找到可用通知器或发送失败，业务退出码不变")
        return "不可用"
    try:
        sender(TITLE, summary)
        log("通知: 已提交脱敏汇总")
        return "已提交"
    except Exception:
        log("通知: 发送失败，业务退出码不变")
        return "失败"


def make_summary(results: list[AccountResult], dry_run: bool) -> str:
    total = len(results)
    succeeded = sum(item.success for item in results)
    failed = total - succeeded
    state = "预演" if dry_run else ("成功" if failed == 0 else "部分失败" if succeeded else "失败")
    lines = [f"NGA论坛签到{state}", f"账号总数: {total}", f"成功数: {succeeded}", f"失败数: {failed}"]
    for item in results:
        status = "成功" if item.success else "失败"
        lines.append(f"账号{item.index}: {status}；" + "；".join(item.outcomes))
    return "\n".join(lines)


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def show_identity(payload: dict[str, Any], index: int, config: Config) -> None:
    # Only official, explicitly public identity fields. Never print arbitrary responses.
    secrets = config.tokens + config.checksums
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"nickname", "username", "display_name", "public_uid"} and isinstance(item, (str, int)):
                    text = str(item)
                    if not any(secret and secret in text for secret in secrets) and not any(c in text for c in "\r\n"):
                        log(f"账号{index} 官方身份 {key}: {text}")
                elif isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(payload)


def main() -> int:
    started = time.monotonic()
    log(f"========== {TITLE} ==========")
    log(f"开始时间: {datetime.now().isoformat(timespec='seconds')}")
    results = []
    dry_run = os.getenv("NGA_DRY_RUN", "").strip().lower() in TRUE_VALUES
    error = ""
    try:
        config = load_config()
        dry_run = config.dry_run
        log(f"阶段 1 配置检查；模式: {'DRY-RUN' if dry_run else '正式运行'}；账号数: {len(config.uids)}；耗时 {time.monotonic() - started:.2f} 秒")
        if config.random_delay_max and not dry_run:
            delay = random.SystemRandom().randint(0, config.random_delay_max)
            log(f"执行前随机延迟: {delay} 秒")
            pause(delay, False)
        for index in range(1, len(config.uids) + 1):
            try:
                result = dry_run_account(index, config) if dry_run else run_live_account(index, config)
            except Exception:
                result = AccountResult(index=index)
                result.add("执行", False, "执行异常，详细内容已隐藏")
            results.append(result)
            log(f"账号{index} 统计: 总任务 {len(result.outcomes)}，成功 {result.counts['success']}，已完成 {result.counts['already']}，跳过 {result.counts['skipped']}，失败 {result.counts['failure']}，耗时 {time.monotonic() - result.started:.2f} 秒")
        code = 0 if all(item.success for item in results) else 1
        summary = make_summary(results, dry_run)
    except ConfigError as exc:
        error = str(exc)
        code = 2
        log(f"阶段 1 配置检查失败；模式: {'DRY-RUN' if dry_run else '正式运行'}；账号数: 0；耗时 {time.monotonic() - started:.2f} 秒")
        summary = f"NGA论坛签到配置错误\n账号总数: 0\n成功数: 0\n失败数: 0\n原因: {error}"
    log("----------------------------------------")
    print(summary)
    notification = notify(summary, dry_run)
    counts = {key: sum(r.counts[key] for r in results) for key in ("success", "already", "skipped", "failure")}
    log(f"子任务统计: {json.dumps(counts, ensure_ascii=False)}")
    status = "configuration-error" if code == 2 else ("partial-failure" if any(r.success for r in results) else "failure") if code else "dry-run" if dry_run else "success"
    log(f"完成时间: {datetime.now().isoformat(timespec='seconds')}；总耗时: {time.monotonic() - started:.2f} 秒；通知: {notification}；最终状态: {status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry_run else "live", "status": status,
          "accounts": len(results), "success": sum(r.success for r in results), "failure": sum(not r.success for r in results),
          "tasks": counts, "notification": notification, "exitCode": code}, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
