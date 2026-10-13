#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 阿里云盘签到
# cron: 3 11 * * *
# dependencies: ecdsa (仅启用设备签名时需要)
"""Aliyun Drive daily check-in.

Maintained standalone repair of ``aliyunpan_checkin.py`` from
https://github.com/agluo/ql-script-hub (commit
a8d39b97cb22c3ac657089014df754342b456ff6).

Copyright (c) agluo/ql-script-hub contributors.
Released under the upstream MIT License.

Required environment:
  ALIYUN_REFRESH_TOKEN  One non-empty refresh token per line.

Optional environment:
  ALIYUN_CLAIM_REWARD=1             Claim today's reward; 0 means check-in only.
  ALIYUN_CLAIM_ALL_REWARDS=1         Opt in to all unclaimed signed-day rewards.
  refreshToken                     Legacy alias; one account per non-empty line.
  ALIYUN_DRIVE_DRY_RUN=1             Simulate all HTTP operations.
  ALIYUN_MAX_DELAY_SECONDS=0          Random delay before live execution.
  ALIYUN_PERSIST_ROTATED_TOKENS=1     Opt in to the file adapter below.
  ALIYUN_TOKEN_OUTPUT_FILE=/path      Destination for rotated tokens.

获取参数：登录阿里云盘网页版，打开开发者工具 Application → Local Storage，
查看当前站点的 token 项，复制 refresh_token 字段（不要复制整段 JSON）。
ALIYUN_REFRESH_TOKEN 每个非空行放一个账号，不使用 & 或 @ 分隔。
默认签到后领取当日奖励；ALIYUN_CLAIM_REWARD=0 只签到。
ALIYUN_CLAIM_ALL_REWARDS=1 显式补领本月所有已签到且未领奖的奖励；
仅在 ALIYUN_CLAIM_REWARD=1 时生效，默认 0 保留当日领奖语义。
refreshToken 为旧变量别名；ALIYUN_REFRESH_TOKEN 设置时优先，别名也按行分账号。
每天输出签到明细及已领、待领奖天数；不会自动改写青龙环境变量。
合并 TangTang0812/aliyun autoSignin.js（MIT），提交
fb6c6aa9c49c315f2e5c32949eef06689aa2ea7e；保留该来源署名。
原来源定时为 0 9 * * *，与每日签到兼容；规范脚本保留 3 11 * * *。
预演模拟 HTTP、通知及领奖，不联网、不等待、不写入凭据文件。
QINGLONG_NOTIFY 默认 1；设为 0/false/no/off 可关闭。QINGLONG_NOTIFY_DIR
可指定青龙 notify.py 所在目录，通知故障不改变业务退出码。
安全持久化默认关闭，只在显式开启且令牌轮换时原子写入权限 0600 的文件。
该文件每行对应原账号顺序的当前刷新令牌，应安全更新青龙环境变量，勿公开。

合并来源：Sitoi/dailycheckin dailycheckin/aliyun/main.py，MIT；
agluo/ql-script-hub aliyunpan_checkin.py 的领奖参考，MIT。
保留规范目标的令牌轮换、多账号、通知、延迟和持久化能力及原定时。
不采用参考脚本的默认数据库/环境改写或令牌片段输出。
新增来源：lizhixu/ql-script-hub aliyunpan_checkin.py，MIT，
提交 ac591a320092dcaeaf236b7c2b6acfd28981e589；保留原有 MIT 声明。
新增只读身份与容量查询；查询失败仍继续签到和领奖，最终非零退出。
ENABLE_DEVICE_SESSION=1 可显式启用上游设备签名及注册会话，默认关闭，
仅启用时需要公共 PyPI 的 ecdsa 包；预演不导入该依赖、不注册设备。
MAX_RANDOM_DELAY 和 RANDOM_SIGNIN 接受显式旧配置；新延迟变量优先。
AUTO_UPDATE_TOKEN、PRIVACY_MODE、SHOW_TOKEN_IN_NOTIFICATION 不再用于
改写面板或放宽凭据保护；请使用原有显式安全文件持久化配置。

MIT License
Copyright (c) agluo/ql-script-hub contributors.

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

The script never prints refresh/access tokens. It does not read Qinglong auth
files, databases, or invoke Qinglong executables.
"""

from __future__ import annotations

import json
import hashlib
import uuid
import importlib.util
import os
import random
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


TOKEN_URL = "https://auth.aliyundrive.com/v2/account/token"
REWARD_URL = "https://member.aliyundrive.com/v1/activity/sign_in_reward"
SIGN_URL = "https://member.aliyundrive.com/v1/activity/sign_in_list"
USER_INFO_URL = "https://user.aliyundrive.com/v2/user/get"
STORAGE_URL = "https://api.aliyundrive.com/v2/user/get"
SESSION_URL = "https://api.aliyundrive.com/users/v1/users/device/create_session"
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "qinglong-aliyun-drive-checkin/2.0"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
NOTIFY_TITLE = "阿里云盘签到"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an account's authorization or JSON credentials.
        return None


def read_response(response, operation):
    body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise CheckinError(f"{operation} 响应过大")
    return decode_json(body, operation)


class CheckinError(RuntimeError):
    """An expected account or service failure safe to display."""


def enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def notification_enabled() -> bool:
    return os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in FALSE_VALUES


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except Exception:
        pass
    candidates: list[Path] = []
    custom_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, "send", None)
                if callable(sender):
                    return sender
        except Exception:
            continue
    return None


def notify_summary(body: str, dry_run: bool) -> str:
    if not notification_enabled():
        return "⏭️ 已关闭"
    if dry_run:
        timeline("通知阶段：预演模拟发送脱敏总结（不调用网络）", "└─")
        return "✅ 预演通知已模拟"
    sender = load_notify_sender()
    if sender is None:
        print("WARNING: Qinglong notify.py was not found; task status is unchanged", file=sys.stderr)
        return "⚠️ 未找到通知组件"
    try:
        sender(NOTIFY_TITLE, body)
        return "✅ 青龙任务总结已推送"
    except Exception:
        print("WARNING: notification delivery failed; task status is unchanged", file=sys.stderr)
        return "⚠️ 推送失败"


def log_banner(mode: str, account_count: int) -> None:
    print("阿里云盘签到")
    print("═" * 62)
    print(f"运行模式  {mode}")
    print(f"账号数量  {account_count}")
    print(f"开始时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def log_task_summary(payload: dict[str, Any], notification: str, started: float) -> None:
    elapsed = round(time.monotonic() - started, 1)
    payload = {**payload, "elapsed_seconds": elapsed, "notification": notification}
    timeline("生成任务总结")
    timeline(f"通知状态：{notification}", "└─")
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"最终状态  {payload['status_label']}")
    print(f"账号统计  总数 {payload['accounts_total']} │ 成功 {payload['accounts_success']} │ 失败 {payload['accounts_failed']}")
    stats = payload["task_stats"]
    print(f"任务统计  总数 {sum(stats.values())} │ 成功 {stats['success']} │ 已完成 {stats['already']} │ 跳过 {stats['skipped']} │ 失败 {stats['failed']}")
    print(f"凭据轮换  {payload.get('tokens_rotated', 0)}")
    print(f"通知状态  {notification}")
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def summary_text(event: str, total: int, succeeded: int, failed: int, rotated: int = 0) -> str:
    payload = {
        "event": event,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "rotated": rotated,
    }
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print(f"ALIYUN_DRIVE_SUMMARY={line}")
    return f"状态：{event}；账号总数 {total}；成功 {succeeded}；失败 {failed}；令牌轮换 {rotated}"


def parse_nonnegative_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise CheckinError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise CheckinError(f"{name} must be a non-negative integer")
    return value


def parse_tokens() -> list[str]:
    raw = os.environ.get("ALIYUN_REFRESH_TOKEN", os.getenv("refreshToken", ""))
    tokens = [line.strip() for line in raw.splitlines() if line.strip()]
    if not tokens:
        raise CheckinError(
            "ALIYUN_REFRESH_TOKEN is required; provide one non-empty account per line"
        )
    return tokens


def decode_json(body: bytes, operation: str) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckinError(f"{operation} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CheckinError(f"{operation} returned an unexpected response")
    return payload


def post_json(
    url: str, payload: dict[str, Any], operation: str, bearer_token: str = "",
    extra_headers: Optional[dict[str, str]] = None
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if extra_headers:
        headers.update(extra_headers)
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, read_response(response, operation)
    except HTTPError as exc:
        with exc:
            return exc.code, read_response(exc, operation)
    except (URLError, TimeoutError, OSError) as exc:
        raise CheckinError(f"{operation} request failed: {type(exc).__name__}") from exc


@dataclass
class AccountResult:
    success: bool
    refresh_token: str
    rotated: bool = False
    sign_days: Optional[int] = None
    error: str = ""


class AliyunDriveClient:
    def __init__(self, refresh_token: str, dry_run: bool) -> None:
        self.refresh_token = refresh_token
        self.dry_run = dry_run
        self.sign_result = {}
        self.identity = ""
        self.secrets = [refresh_token]
        self.user_id = ""
        self.device_headers = {}
        self.device_session = enabled("ENABLE_DEVICE_SESSION")

    def refresh_access_token(self) -> tuple[str, str, bool]:
        if self.dry_run:
            self.identity = "预演账号"
            return "dry-run-access-token", self.refresh_token, False

        status, payload = post_json(
            TOKEN_URL,
            {
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
            },
            "token refresh",
        )
        if status != 200 or payload.get("code") or payload.get("success") is False:
            raise CheckinError(f"token refresh rejected (HTTP {status})")

        access_token = payload.get("access_token")
        next_refresh_token = payload.get("refresh_token", self.refresh_token)
        if not isinstance(access_token, str) or not access_token:
            raise CheckinError("token refresh response did not contain an access token")
        if not isinstance(next_refresh_token, str) or not next_refresh_token:
            raise CheckinError("token refresh response contained an invalid refresh token")
        self.secrets.extend([access_token, next_refresh_token])
        self.user_id = payload.get("user_id", "")
        for field in ("nick_name", "display_name", "user_name", "user_id"):
            value = payload.get(field)
            if isinstance(value, str) and value and not any(secret in value for secret in self.secrets):
                # Explicit public identity fields only; do not read phone/device/session fields.
                self.identity = value
                break
        return access_token, next_refresh_token, next_refresh_token != self.refresh_token

    def account_information(self, access_token):
        """Read only the reference-supported identity and storage fields."""
        if self.dry_run:
            self.identity = "预演账号"
            return "账号身份：预演账号；存储空间 1.00GB / 10.00GB（10.0%）"
        details = []
        for url, operation in ((USER_INFO_URL, "查询账号身份"), (STORAGE_URL, "查询存储容量")):
            status, payload = post_json(url, {}, operation, access_token)
            if status != 200 or payload.get("code") or payload.get("success") is False:
                raise CheckinError(f"{operation}未获接口确认（HTTP {status}）")
            if url == USER_INFO_URL:
                for field in ("nick_name", "display_name", "user_name", "user_id"):
                    value = payload.get(field)
                    if isinstance(value, str) and value and not any(s in value for s in self.secrets):
                        self.identity = value
                        details.append("官方账号身份：" + json.dumps(value, ensure_ascii=False))
                        break
                else:
                    raise CheckinError("账号接口未返回可验证的公开身份")
            else:
                space = payload.get("personal_space_info")
                if not isinstance(space, dict):
                    raise CheckinError("容量接口缺少存储信息")
                used, total = space.get("used_size"), space.get("total_size")
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0
                       for v in (used, total)) or total <= 0:
                    raise CheckinError("容量接口未返回有效空间数值")
                details.append(f"存储空间 {used / 1024**3:.2f}GB / {total / 1024**3:.2f}GB（{used / total * 100:.1f}%）")
        return "；".join(details)

    def prepare_device_session(self, access_token):
        if not self.device_session:
            return
        if self.dry_run:
            return
        if not isinstance(self.user_id, str) or not self.user_id:
            raise CheckinError("设备签名需要官方返回的用户标识")
        try:
            from ecdsa import SigningKey, SECP256k1
        except ImportError as exc:
            raise CheckinError("ENABLE_DEVICE_SESSION=1 需要通过公共包仓库安装 ecdsa") from exc
        private_key = SigningKey.generate(curve=SECP256k1)
        device_id = uuid.uuid4().hex + uuid.uuid4().hex
        self.secrets.append(device_id)
        signing_text = f"25dzX3vbYqktVxyX:{device_id}:{self.user_id}:0".encode("utf-8")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aDrive/7.1.2 Chrome/130.0.6723.59 Electron/32.0.1 Safari/537.36",
            "x-canary": "client=windows,app=adrive,version=v7.1.2",
            "x-device-id": device_id,
            "x-signature": private_key.sign(signing_text, hashfunc=hashlib.sha256).hex() + "01",
            "x-signature-v2": hashlib.sha1(signing_text).hexdigest(),
        }
        status, payload = post_json(SESSION_URL, {
            "deviceName": "Python Script", "modelName": "Windows 客户端",
            "pubKey": private_key.get_verifying_key().to_string("uncompressed").hex(),
        }, "注册可选设备会话", access_token, headers)
        # Do not treat arbitrary nonempty result objects as verified success.
        if status != 200 or payload.get("success") is not True:
            raise CheckinError(f"设备会话未获明确成功确认（HTTP {status}）")
        self.device_headers = headers

    def sign_in(self, access_token: str) -> int:
        if self.dry_run:
            self.sign_result = {"signInCount": 1, "signInLogs": [{"day": 1, "status": "normal", "isReward": False, "reward": {"name": "预演奖励"}}]}
            return 1

        status, payload = post_json(SIGN_URL, {}, "check-in", access_token)
        if status != 200:
            raise CheckinError(f"check-in rejected (HTTP {status})")
        if payload.get("success") is not True:
            raise CheckinError("check-in was not accepted by the service")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise CheckinError("check-in response did not contain a result")
        sign_days = result.get("signInCount")
        if isinstance(sign_days, bool) or not isinstance(sign_days, int) or sign_days < 0:
            raise CheckinError("check-in response did not contain a valid sign-in count")
        self.sign_result = result
        return sign_days

    def reward_description(self, reward):
        if not isinstance(reward, dict):
            return ""
        # Only display allowlisted reward text, never raw service responses.
        values = [reward.get(k) for k in ("name", "description", "notice")]
        text = " ".join(v for v in values if isinstance(v, str))
        for secret in self.secrets:
            text = text.replace(secret, "[已隐藏]")
        text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
        return text.replace("\n", " ").replace("\r", " ")[:500]

    def log_reward_description(self, log):
        text = self.reward_description(log.get("reward"))
        if text:
            return text
        kind, amount = log.get("type"), log.get("rewardAmount")
        if kind not in {"postpone", "backupSpaceMb"}:
            return ""
        label = "延期卡" if kind == "postpone" else "备份空间"
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount > 0:
            label += f" {amount}" + ("MB" if kind == "backupSpaceMb" else "张")
        return label

    def sign_details(self):
        _, rows = self.sign_details_for_claim()
        pending = []
        claimed = []
        for day, entry in rows:
            if entry.get("status") != "normal":
                label = "未签到或未开放"
            elif entry.get("isReward") is True:
                label = "已领奖"
                claimed.append(day)
            elif entry.get("isReward") is False:
                label = "待领奖"
                pending.append(day)
            else:
                raise CheckinError("已签到记录缺少明确的领奖状态")
            description = self.log_reward_description(entry)
            timeline(f"第 {day} 天：{label}" + ("；" + description if description else ""), "└─")
        return pending, f"签到明细 {len(rows)} 天；已领奖 {len(claimed)} 天；待领奖 {len(pending)} 天"

    def claim_all_rewards(self, access_token):
        pending, _ = self.sign_details_for_claim()
        if not pending:
            return "already", "全部已签到奖励均已领取或暂无可领奖励"
        # Each eligible day is independent: a failed claim must not stop later days.
        self.prepare_device_session(access_token)
        successes, failures = 0, 0
        for day in pending:
            try:
                outcome, detail = self.claim_reward(access_token, day, prepare=False)
                timeline(f"第 {day} 天：{detail}", "└─")
                successes += 1
            except Exception as exc:
                failures += 1
                detail = str(exc) if isinstance(exc, CheckinError) else "处理异常，详情已隐藏"
                timeline(f"❌ 第 {day} 天奖励领取失败：{detail}", "└─")
        self.reward_stats = {"total": len(pending), "success": successes, "failed": failures}
        if failures:
            raise CheckinError(f"全量领奖：成功 {successes} 天，失败 {failures} 天")
        return "success", f"全量领奖成功，共领取 {successes} 天奖励"

    def sign_details_for_claim(self):
        # Validate the same response fields as the displayed detail without logging twice.
        logs = self.sign_result.get("signInLogs")
        if not isinstance(logs, list):
            raise CheckinError("签到接口缺少签到明细列表")
        pending = []
        seen = set()
        rows = []
        for entry in logs:
            if not isinstance(entry, dict):
                raise CheckinError("签到明细记录格式异常")
            day = entry.get("day")
            if isinstance(day, str) and day.isdecimal():
                day = int(day)
            if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 31 or day in seen:
                raise CheckinError("签到明细日期无效或重复")
            seen.add(day)
            rows.append((day, entry))
            if entry.get("status") == "normal":
                if not isinstance(entry.get("isReward"), bool):
                    raise CheckinError("已签到记录缺少明确的领奖状态")
                if entry["isReward"] is False:
                    pending.append(day)
        return pending, rows

    def claim_reward(self, access_token, sign_days, prepare=True):
        if sign_days < 1:
            return "skipped", "签到累计为零，无当日奖励可领取"
        logs = self.sign_result.get("signInLogs", [])
        if not isinstance(logs, list):
            raise CheckinError("签到奖励记录格式异常")
        today = next((log for log in logs if isinstance(log, dict)
                      and str(log.get("day")) == str(sign_days)
                      and log.get("status") == "normal"), None)
        if today and today.get("isReward") is True:
            return "already", "当日奖励已领取 " + self.log_reward_description(today)
        if self.dry_run:
            return "success", "领奖成功（预演奖励）"
        if prepare:
            self.prepare_device_session(access_token)
        status, payload = post_json(REWARD_URL, {"signInDay": sign_days}, f"领取第 {sign_days} 天奖励", access_token, self.device_headers)
        if status != 200 or payload.get("success") is not True:
            # A vague error string or a failed claim must never become success.
            raise CheckinError(f"领奖未获接口确认（HTTP {status}），请核对该日奖励状态")
        info = self.reward_description(payload.get("result"))
        if not info and today:
            info = self.log_reward_description(today)
        return "success", "领奖成功" + ("：" + info if info else "")

    def run(self, index=1, claim=True, claim_all=False) -> AccountResult:
        next_token, rotated, days = self.refresh_token, False, None
        self.stats = {"success": 0, "already": 0, "skipped": 0, "failed": 0}
        operations = [("刷新登录凭据", None), ("查询身份与容量", None), ("执行签到", None), ("显示签到明细", None), ("领取全部未领奖励" if claim_all else "领取当日奖励", None)]
        access_token = ""
        error = ""
        for number, (name, _) in enumerate(operations, 1):
            began = time.monotonic()
            timeline(f"账号 {index:02d}：[{number}/5] {name}")
            outcome, detail = "success", ""
            try:
                if error:
                    outcome, detail = "skipped", "前置步骤失败，跳过"
                elif number == 1:
                    access_token, next_token, rotated = self.refresh_access_token()
                    detail = "登录凭据有效" + ("，刷新令牌已轮换（内容隐藏）" if rotated else "")
                    if self.identity:
                        timeline("官方账号身份：" + json.dumps(self.identity, ensure_ascii=False), "└─")
                elif number == 2:
                    detail = self.account_information(access_token)
                elif number == 3:
                    days = self.sign_in(access_token)
                    detail = f"签到成功，累计 {days} 天"
                elif number == 4:
                    _, detail = self.sign_details()
                elif not claim:
                    outcome, detail = "skipped", "已明确关闭领奖"
                elif claim_all:
                    outcome, detail = self.claim_all_rewards(access_token)
                else:
                    outcome, detail = self.claim_reward(access_token, days)
            except Exception as exc:
                outcome = "failed"
                detail = str(exc) if isinstance(exc, CheckinError) else "处理异常，详情已隐藏"
                if number in (2, 4):
                    # Read-only enrichment must not prevent check-in or reward actions.
                    detail += "；继续签到与领奖，整体将返回失败"
                else:
                    error = detail
            self.stats[outcome] += 1
            icon = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failed": "❌"}[outcome]
            timeline(f"{icon} {detail} │ 阶段耗时 {time.monotonic() - began:.1f} 秒", "└─")
        return AccountResult(not self.stats["failed"], next_token, rotated, days, error)


def persist_tokens(tokens: list[str], destination: str) -> None:
    """Atomically persist rotated credentials using an explicit opt-in adapter."""
    target = Path(destination).expanduser()
    if not target.is_absolute():
        raise CheckinError("ALIYUN_TOKEN_OUTPUT_FILE must be an absolute path")
    if not target.parent.is_dir():
        raise CheckinError("ALIYUN_TOKEN_OUTPUT_FILE parent directory does not exist")

    temp_name = ""
    old_umask = os.umask(0o077)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write("\n".join(tokens) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        os.chmod(target, 0o600)
    finally:
        os.umask(old_umask)
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def main() -> int:
    started = time.monotonic()
    dry_run = enabled("ALIYUN_DRIVE_DRY_RUN")
    tokens = []
    results = []
    task_stats = {"success": 0, "already": 0, "skipped": 0, "failed": 0}
    persistence_failed = False
    try:
        tokens = parse_tokens()
        # Preserve maintained defaults; accept the upstream delay controls only when explicit.
        delay_name = "ALIYUN_MAX_DELAY_SECONDS" if "ALIYUN_MAX_DELAY_SECONDS" in os.environ else "MAX_RANDOM_DELAY"
        max_delay = parse_nonnegative_int(delay_name)
        if "RANDOM_SIGNIN" in os.environ and not enabled("RANDOM_SIGNIN"):
            max_delay = 0
        raw_session = os.getenv("ENABLE_DEVICE_SESSION", "0").strip().lower()
        if raw_session not in TRUE_VALUES | FALSE_VALUES:
            raise CheckinError("ENABLE_DEVICE_SESSION 必须为 1 或 0")
        persistence_enabled = enabled("ALIYUN_PERSIST_ROTATED_TOKENS")
        output_file = os.getenv("ALIYUN_TOKEN_OUTPUT_FILE", "").strip()
        if persistence_enabled and not output_file:
            raise CheckinError("启用持久化时必须设置 ALIYUN_TOKEN_OUTPUT_FILE")
        if persistence_enabled:
            target = Path(output_file).expanduser()
            if not target.is_absolute() or not target.parent.is_dir():
                raise CheckinError("令牌输出文件必须为绝对路径且父目录已存在")
        raw_claim = os.getenv("ALIYUN_CLAIM_REWARD", "1").strip().lower()
        if raw_claim not in TRUE_VALUES | FALSE_VALUES:
            raise CheckinError("ALIYUN_CLAIM_REWARD 必须为 1 或 0")
        claim = raw_claim in TRUE_VALUES
        raw_all = os.getenv("ALIYUN_CLAIM_ALL_REWARDS", "0").strip().lower()
        if raw_all not in TRUE_VALUES | FALSE_VALUES:
            raise CheckinError("ALIYUN_CLAIM_ALL_REWARDS 必须为 1 或 0")
        claim_all = raw_all in TRUE_VALUES
    except CheckinError as exc:
        log_banner("预演" if dry_run else "正式执行", len(tokens))
        timeline(f"❌ 配置失败：{exc}")
        body = summary_text("configuration-error", len(tokens), 0, 0)
        notification = notify_summary(body, dry_run)
        log_task_summary({"status": "configuration_error", "status_label": "配置失败", "accounts_total": len(tokens), "accounts_success": 0, "accounts_failed": 0, "task_stats": task_stats}, notification, started)
        return 2

    log_banner("预演" if dry_run else "正式执行", len(tokens))
    if dry_run:
        print("DRY-RUN: HTTP requests, delays, and token persistence are disabled")
    elif max_delay:
        delay = random.SystemRandom().randint(0, max_delay)
        timeline(f"执行前随机等待 {delay} 秒")
        time.sleep(delay)
    for index, token in enumerate(tokens, 1):
        account_started = time.monotonic()
        client = AliyunDriveClient(token, dry_run)
        result = client.run(index, claim, claim_all)
        results.append(result)
        stats = client.stats
        for key in task_stats:
            task_stats[key] += stats[key]
        timeline(f"账号 {index:02d}：{'✅ 成功' if result.success else '❌ 失败'}")
        timeline(f"总任务 5 │ 成功 {stats['success']} │ 已完成 {stats['already']} │ 跳过 {stats['skipped']} │ 失败 {stats['failed']} │ 用时 {time.monotonic() - account_started:.1f} 秒", "└─")

    rotated_count = sum(result.rotated for result in results)
    if persistence_enabled and rotated_count and not dry_run:
        try:
            persist_tokens([result.refresh_token for result in results], output_file)
            timeline("✅ Rotated-token persistence: SUCCESS")
        except Exception:
            persistence_failed = True
            timeline("❌ Rotated-token persistence: FAILED（文件错误详情已隐藏）")
    elif rotated_count:
        timeline("刷新令牌已轮换；持久化关闭，请在安全渠道更新凭据")
    failures = sum(not result.success for result in results)
    succeeded = len(results) - failures
    exit_code = 1 if failures or persistence_failed else 0
    event = ("partial-failure" if succeeded else "failure") if exit_code else ("dry-run" if dry_run else "success")
    if not exit_code:
        print(f"DRY-RUN SUCCESS: all {len(results)} account(s) simulated" if dry_run else f"ALL ACCOUNTS SUCCEEDED: {len(results)} account(s)")
    else:
        print(f"RUN FAILED: {failures} account failure(s); persistence failed: {persistence_failed}")
    body = summary_text(event, len(results), succeeded, failures, rotated_count)
    body += f"\n子任务：成功 {task_stats['success']}，已完成 {task_stats['already']}，跳过 {task_stats['skipped']}，失败 {task_stats['failed']}；持久化失败 {int(persistence_failed)}"
    notification = notify_summary(body, dry_run)
    log_task_summary({"status": event.replace("-", "_"), "status_label": "失败" if exit_code else ("预演通过" if dry_run else "全部成功"), "accounts_total": len(results), "accounts_success": succeeded, "accounts_failed": failures, "tokens_rotated": rotated_count, "persistence_failed": persistence_failed, "task_stats": task_stats}, notification, started)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
