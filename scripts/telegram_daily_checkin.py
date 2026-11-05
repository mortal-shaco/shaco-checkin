#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Telegram每日Bot签到
# cron: 33 8 * * *
# dependencies: telethon,PySocks
"""Telegram 每日 Bot 签到（青龙维护版）。

MIT License
Copyright (c) 2026 Md. Redwan Ahmed

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

Derived from redwan-cse/telegram-daily-checkin telegram_daily_checkin.py
(commit 67be15b79b34cdd112208e33cfe7524d90df7e45, MIT).
Catalog 2422813024d0fddc / SHA256
922182284336e7a766b32e1772f392c0c327834c32d112a83835d4021d50d81c.

保留上游用户可见能力：多账号、每账号多 Bot、send_command / send_message /
click_button、显式 manual_ui_required 失败、可选 SOCKS5、Bot 间与账号间随机
间隔、Bot 失败隔离、展示 Telegram 公开身份。

青龙适配：
- 凭据改为环境变量，每行一个账号；不再依赖 YAML / Docker / 交互式登录。
- 必须预先准备 Telethon StringSession；定时任务禁止交互输入验证码。
- 默认关闭随机延迟与会话落盘，避免不安全的默认副作用。
- TELEGRAM_DAILY_DRY_RUN=1 完全断网预演；不导入 Telethon、不触网。
- 时间轴日志、TASK_SUMMARY、青龙 notify.py / sendNotify.js 脱敏通知。

参数获取：
1. 打开 https://my.telegram.org/apps 登录本人账号，创建应用取得 api_id / api_hash。
2. 在可信本机用 Telethon 一次性登录并导出 StringSession（勿把会话发给他人）。
3. 将账号标签、api_id、api_hash、StringSession 与机器人动作写入
   TELEGRAM_DAILY_ACCOUNTS，每行一个账号。

仅对本人授权操作的 Telegram 账号与 Bot 使用。
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
        _ql_notify_identities = ('2422813024d0fddc', 'scripts/telegram_daily_checkin.py', 'telegram_daily_checkin.py', 'telegram_daily_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import asyncio
import fnmatch
import importlib.util
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

TASK_NAME = "Telegram每日Bot签到"
CATALOG_ID = "2422813024d0fddc"
NOTIFY_IDENTITIES = (
    CATALOG_ID,
    "scripts/telegram_daily_checkin.py",
    "telegram_daily_checkin.py",
    "candidate.py",
    "output/candidate.py",
)
DRY_RUN_ENV = "TELEGRAM_DAILY_DRY_RUN"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
SUPPORTED_ACTIONS = {"send_command", "send_message", "click_button", "manual_ui_required"}
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class BotAction:
    type: str
    value: str
    wait_seconds: int = 5


@dataclass(frozen=True)
class BotCheckin:
    username: str
    actions: tuple[BotAction, ...]


@dataclass(frozen=True)
class AccountConfig:
    account_id: str
    api_id: int
    api_hash: str
    session: str
    bots: tuple[BotCheckin, ...]


@dataclass
class StageStat:
    name: str
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    already: int = 0


@dataclass
class AccountResult:
    index: int
    account_id: str
    identity: str
    ok: bool
    message: str
    stages: list[dict[str, Any]]
    elapsed: float
    bot_ok: int = 0
    bot_fail: int = 0


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str, icon: str = "◆") -> None:
    print(f"{clock()}  {icon} {message}", flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(name: str) -> bool:
    return env(name).lower() in TRUE_VALUES


def dry_run_enabled() -> bool:
    return truthy(DRY_RUN_ENV)


def parse_bool(value: str, label: str) -> bool:
    normalized = str(value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES or normalized == "":
        return False
    raise ValueError(f"{label} 必须是布尔值")


def parse_non_negative_int(name: str, default: int) -> int:
    raw = env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if value < 0:
        raise ValueError(f"{name} 不能为负数")
    return value


def normalize_bot_username(username: str) -> str:
    text = username.strip()
    if not text:
        raise ValueError("机器人用户名不能为空")
    if not text.startswith("@"):
        text = "@" + text
    if not text.lstrip("@").strip():
        raise ValueError("机器人用户名不能为空")
    return text


def parse_simple_bots(spec: str) -> tuple[BotCheckin, ...]:
    bots: list[BotCheckin] = []
    for raw_item in spec.split(";"):
        item = raw_item.strip()
        if not item:
            continue
        if ":" not in item:
            username = normalize_bot_username(item)
            bots.append(BotCheckin(username=username, actions=(BotAction("send_command", "/checkin"),)))
            continue
        username_raw, command = item.split(":", 1)
        username = normalize_bot_username(username_raw)
        command = command.strip()
        if not command:
            raise ValueError(f"{username} 的命令/消息不能为空")
        action_type = "send_command" if command.startswith("/") else "send_message"
        bots.append(BotCheckin(username=username, actions=(BotAction(action_type, command),)))
    if not bots:
        raise ValueError("至少配置一个机器人")
    return tuple(bots)


def parse_json_bots(spec: str) -> tuple[BotCheckin, ...]:
    try:
        payload = json.loads(spec)
    except json.JSONDecodeError as exc:
        raise ValueError("机器人 JSON 配置无效") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("机器人 JSON 必须是非空数组")
    bots: list[BotCheckin] = []
    for index, item in enumerate(payload, start=1):
        if isinstance(item, str):
            bots.append(
                BotCheckin(
                    username=normalize_bot_username(item),
                    actions=(BotAction("send_command", "/checkin"),),
                )
            )
            continue
        if not isinstance(item, dict):
            raise ValueError(f"bots[{index}] 必须是字符串或对象")
        username = normalize_bot_username(str(item.get("username") or ""))
        actions_raw = item.get("actions")
        if actions_raw is None:
            command = str(item.get("command") or "/checkin").strip()
            if not command:
                raise ValueError(f"{username} command 不能为空")
            action_type = "send_command" if command.startswith("/") else "send_message"
            actions = (BotAction(action_type, command),)
        else:
            if not isinstance(actions_raw, list) or not actions_raw:
                raise ValueError(f"{username} actions 必须是非空数组")
            parsed: list[BotAction] = []
            for action_index, action_raw in enumerate(actions_raw, start=1):
                if not isinstance(action_raw, dict):
                    raise ValueError(f"{username} action[{action_index}] 必须是对象")
                action_type = str(action_raw.get("type") or "").strip()
                if action_type not in SUPPORTED_ACTIONS:
                    raise ValueError(f"{username} 不支持的动作类型 {action_type!r}")
                value = str(
                    action_raw.get("value")
                    or action_raw.get("text")
                    or action_raw.get("button_text")
                    or ""
                ).strip()
                if not value:
                    raise ValueError(f"{username} action[{action_index}] value 不能为空")
                wait_seconds = int(action_raw.get("wait_seconds", 5))
                if wait_seconds < 0:
                    raise ValueError(f"{username} wait_seconds 不能为负数")
                parsed.append(BotAction(action_type, value, wait_seconds))
            actions = tuple(parsed)
        bots.append(BotCheckin(username=username, actions=actions))
    return tuple(bots)


def parse_bots(spec: str) -> tuple[BotCheckin, ...]:
    text = spec.strip()
    if not text:
        raise ValueError("机器人配置不能为空")
    if text.startswith("["):
        return parse_json_bots(text)
    return parse_simple_bots(text)


def parse_account_line(line: str, index: int, global_api_id: int, global_api_hash: str) -> AccountConfig:
    # 按有限次 | 拆分，保留机器人配置原文（可含 JSON 与冒号）。
    parts = [item.strip() for item in line.split("|", 4)]
    account_id = f"account{index}"
    api_id = global_api_id
    api_hash = global_api_hash
    session = ""
    bots_spec = ""

    if len(parts) == 5:
        # 账号标签|api_id|api_hash|string_session|机器人配置
        account_id = parts[0] or account_id
        try:
            api_id = int(parts[1] or global_api_id)
        except ValueError as exc:
            raise ValueError(f"账号 {account_id} 的 api_id 必须是整数") from exc
        api_hash = parts[2] or global_api_hash
        session = parts[3]
        bots_spec = parts[4]
    elif len(parts) == 4:
        if parts[0].isdigit():
            # api_id|api_hash|string_session|机器人配置
            api_id = int(parts[0])
            api_hash = parts[1] or global_api_hash
            session = parts[2]
            bots_spec = parts[3]
        elif parts[1].isdigit():
            # 账号标签|api_id|api_hash|string_session（机器人用 TELEGRAM_DAILY_BOTS）
            account_id = parts[0] or account_id
            api_id = int(parts[1])
            api_hash = parts[2] or global_api_hash
            session = parts[3]
            bots_spec = ""
        else:
            raise ValueError(
                "四字段格式请使用 api_id|api_hash|string_session|机器人配置，"
                "或 账号标签|api_id|api_hash|string_session"
            )
    elif len(parts) == 3:
        # 账号标签|string_session|机器人配置（依赖全局 TELEGRAM_API_ID/HASH）
        account_id = parts[0] or account_id
        session = parts[1]
        bots_spec = parts[2]
    elif len(parts) == 2:
        # string_session|机器人配置
        session = parts[0]
        bots_spec = parts[1]
    else:
        raise ValueError(
            "账号行格式无效。推荐：账号标签|api_id|api_hash|string_session|机器人配置"
        )

    if not account_id:
        raise ValueError("账号标签不能为空")
    if api_id <= 0 or not api_hash:
        raise ValueError(
            f"账号 {account_id} 缺少有效 api_id/api_hash；"
            "请写在行内或设置 TELEGRAM_API_ID 与 TELEGRAM_API_HASH"
        )
    if not session:
        raise ValueError(f"账号 {account_id} 缺少 StringSession")
    if any(ch in session for ch in ("\r", "\n", "\x00")):
        raise ValueError(f"账号 {account_id} 的会话值包含非法控制字符")
    if not bots_spec:
        bots_spec = env("TELEGRAM_DAILY_BOTS")
    if not bots_spec:
        raise ValueError(
            f"账号 {account_id} 缺少机器人配置；请写在行末或设置 TELEGRAM_DAILY_BOTS"
        )
    bots = parse_bots(bots_spec)
    return AccountConfig(
        account_id=account_id,
        api_id=api_id,
        api_hash=api_hash,
        session=session,
        bots=bots,
    )


def load_accounts() -> list[AccountConfig]:
    raw = env("TELEGRAM_DAILY_ACCOUNTS")
    if not raw:
        raise ValueError(
            "缺少必填凭据 TELEGRAM_DAILY_ACCOUNTS。"
            "每行一个账号：账号标签|api_id|api_hash|string_session|机器人配置"
        )
    global_api_id = 0
    api_id_raw = env("TELEGRAM_API_ID")
    if api_id_raw:
        try:
            global_api_id = int(api_id_raw)
        except ValueError as exc:
            raise ValueError("TELEGRAM_API_ID 必须是整数") from exc
    global_api_hash = env("TELEGRAM_API_HASH")

    accounts: list[AccountConfig] = []
    seen: set[str] = set()
    for index, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        account = parse_account_line(line, index, global_api_id, global_api_hash)
        if account.account_id in seen:
            raise ValueError(f"重复的账号标签：{account.account_id}")
        seen.add(account.account_id)
        accounts.append(account)
    if not accounts:
        raise ValueError("TELEGRAM_DAILY_ACCOUNTS 没有有效账号行")
    return accounts


def summarize_actions(bot: BotCheckin) -> str:
    return ", ".join(f"{action.type}:{action.value}" for action in bot.actions)


def notification_enabled() -> bool:
    value = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    if value != "auto":
        log("QINGLONG_NOTIFY 值无效，按 auto 处理", ICONS["warning"])
    selectors_raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if selectors_raw is None:
        return True
    selectors = [
        item.lower()
        for item in re.split(r"[,;\s]+", selectors_raw.strip())
        if item
    ]
    if not selectors:
        return False
    if "*" in selectors:
        return True
    return any(
        fnmatch.fnmatch(identity.lower(), selector)
        for selector in selectors
        for identity in NOTIFY_IDENTITIES
    )


def send_notify(title: str, content: str) -> str:
    if not notification_enabled():
        return f"{ICONS['skipped']} 已关闭"
    if dry_run_enabled():
        log(f"断网预演通知汇总：{content}", ICONS["skipped"])
        return f"{ICONS['skipped']} 断网预演：已生成通知汇总，未加载通知组件"
    sender = None
    try:
        from notify import send as sender  # type: ignore
    except Exception:
        roots = [
            env("QINGLONG_NOTIFY_DIR"),
            "/ql/data/scripts",
            "/ql/scripts",
        ]
        for root in filter(None, roots):
            for filename in ("notify.py", "sendNotify.js"):
                path = Path(root) / filename
                if filename.endswith(".py") and path.is_file():
                    spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                    if not spec or not spec.loader:
                        continue
                    try:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        candidate = getattr(module, "send", None)
                        if callable(candidate):
                            sender = candidate
                            break
                    except Exception:
                        continue
            if callable(sender):
                break
            js_path = Path(root) / "sendNotify.js"
            if js_path.is_file():
                try:
                    import subprocess

                    subprocess.run(
                        ["node", str(js_path), title, content],
                        check=False,
                        timeout=30,
                        capture_output=True,
                        text=True,
                    )
                    return f"{ICONS['success']} 已推送"
                except Exception as error:
                    log(f"sendNotify.js 调用失败：{type(error).__name__}", ICONS["warning"])
                    return f"{ICONS['warning']} 推送失败"
    if not callable(sender):
        log("未找到青龙 notify.py，已跳过任务总结推送", ICONS["warning"])
        return f"{ICONS['warning']} 未找到通知组件"
    try:
        sender(title, content)
        return f"{ICONS['success']} 已推送"
    except Exception as error:
        log(f"通知发送失败：{type(error).__name__}", ICONS["warning"])
        return f"{ICONS['warning']} 推送失败"


def build_proxy_tuple() -> Any:
    if not truthy("TELEGRAM_DAILY_PROXY_ENABLED") and not truthy("PROXY_ENABLED"):
        return None
    host = env("TELEGRAM_DAILY_PROXY_HOST") or env("PROXY_HOST")
    port_raw = env("TELEGRAM_DAILY_PROXY_PORT") or env("PROXY_PORT") or "1080"
    if not host:
        raise ValueError("已启用代理但未设置 TELEGRAM_DAILY_PROXY_HOST / PROXY_HOST")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError("代理端口必须是整数") from exc
    username = env("TELEGRAM_DAILY_PROXY_USERNAME") or env("PROXY_USERNAME") or None
    password = env("TELEGRAM_DAILY_PROXY_PASSWORD") or env("PROXY_PASSWORD") or None
    try:
        import socks  # type: ignore
    except ImportError as exc:
        raise RuntimeError("已启用代理但未安装 PySocks，请从 PyPI 安装") from exc
    return (socks.SOCKS5, host, port, True, username or None, password or None)


async def click_latest_button_by_text(client: Any, entity: Any, button_text: str) -> None:
    messages = await client.get_messages(entity, limit=5)
    for message in messages:
        buttons = getattr(message, "buttons", None)
        if not buttons or not any(button.text == button_text for row in buttons for button in row):
            continue
        try:
            await message.click(text=button_text)
            return
        except ValueError:
            continue
    raise RuntimeError(f"在最近消息中未找到按钮 {button_text!r}")


async def execute_bot_action(client: Any, entity: Any, account_id: str, bot: BotCheckin, action: BotAction) -> str:
    if action.type in {"send_command", "send_message"}:
        await client.send_message(entity, action.value)
        return f"{action.type} 已发送"
    if action.type == "click_button":
        if action.wait_seconds > 0:
            log(
                f"账号 {account_id} 等待 {action.wait_seconds}s 后点击 {bot.username} 按钮",
                ICONS["skipped"],
            )
            await asyncio.sleep(action.wait_seconds)
        await click_latest_button_by_text(client, entity, action.value)
        return f"已点击按钮: {action.value}"
    if action.type == "manual_ui_required":
        raise RuntimeError(
            "manual_ui_required：该 Bot 需要 Telegram 客户端原生界面点击，"
            "青龙 MTProto 任务无法完成，请改用独立桌面自动化"
        )
    raise RuntimeError(f"不支持的动作类型: {action.type}")


async def sleep_jitter(label: str, minimum: int, maximum: int) -> None:
    if minimum < 0 or maximum < 0 or minimum > maximum:
        raise ValueError(f"{label} 延迟窗口无效")
    seconds = random.randint(minimum, maximum)
    if seconds <= 0:
        return
    log(f"{label} 等待 {seconds}s", ICONS["skipped"])
    await asyncio.sleep(seconds)


def public_identity(user: Any) -> str:
    parts: list[str] = []
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    user_id = getattr(user, "id", None)
    if username:
        parts.append("@" + str(username))
    display = " ".join(str(item) for item in (first_name, last_name) if item).strip()
    if display:
        parts.append(display)
    if user_id is not None:
        parts.append(f"uid:{user_id}")
    return " / ".join(parts) if parts else ""


async def run_account_live(account: AccountConfig, proxy: Any, timeout: int) -> AccountResult:
    started = time.monotonic()
    stages: list[dict[str, Any]] = []
    bot_ok = 0
    bot_fail = 0
    identity = ""

    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
    from telethon.sessions import StringSession

    client = TelegramClient(
        StringSession(account.session),
        account.api_id,
        account.api_hash,
        proxy=proxy,
        connection_retries=3,
        request_retries=2,
        timeout=timeout,
    )
    try:
        stage_start = time.monotonic()
        log(f"[阶段1] 连接并校验会话 · {account.account_id}")
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("StringSession 未授权或已失效，请在本机重新导出会话后更新环境变量")
        me = await client.get_me()
        identity = public_identity(me) or account.account_id
        if identity:
            log(f"账号身份 {identity}", ICONS["success"])
        stages.append(
            {
                "stage": 1,
                "name": "连接会话",
                "status": "success",
                "elapsed": round(time.monotonic() - stage_start, 3),
                "detail": identity or "已授权",
            }
        )

        for bot_index, bot in enumerate(account.bots, start=1):
            stage_no = bot_index + 1
            stage_start = time.monotonic()
            action_summary = summarize_actions(bot)
            log(f"[阶段{stage_no}] 处理 {bot.username} · {action_summary}")
            try:
                entity = await client.get_entity(bot.username)
                details: list[str] = []
                for action in bot.actions:
                    details.append(
                        await execute_bot_action(client, entity, account.account_id, bot, action)
                    )
                detail = "; ".join(details) or "completed"
                log(f"{bot.username} 完成：{detail}", ICONS["success"])
                bot_ok += 1
                stages.append(
                    {
                        "stage": stage_no,
                        "name": bot.username,
                        "status": "success",
                        "elapsed": round(time.monotonic() - stage_start, 3),
                        "detail": detail,
                    }
                )
            except FloodWaitError as exc:
                bot_fail += 1
                detail = f"触发限流，需等待 {exc.seconds}s"
                log(f"{bot.username} 失败：{detail}", ICONS["failure"])
                stages.append(
                    {
                        "stage": stage_no,
                        "name": bot.username,
                        "status": "failure",
                        "elapsed": round(time.monotonic() - stage_start, 3),
                        "detail": detail,
                    }
                )
            except Exception as exc:
                bot_fail += 1
                detail = f"{type(exc).__name__}"
                log(f"{bot.username} 失败：{detail}", ICONS["failure"])
                stages.append(
                    {
                        "stage": stage_no,
                        "name": bot.username,
                        "status": "failure",
                        "elapsed": round(time.monotonic() - stage_start, 3),
                        "detail": detail,
                    }
                )
            if bot_index < len(account.bots):
                await sleep_jitter(
                    "Bot间隔",
                    parse_non_negative_int("TELEGRAM_DAILY_BETWEEN_BOT_MIN_SECONDS", 0),
                    parse_non_negative_int("TELEGRAM_DAILY_BETWEEN_BOT_MAX_SECONDS", 0),
                )
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    ok = bot_fail == 0 and bot_ok > 0
    message = f"成功 {bot_ok} 个Bot，失败 {bot_fail} 个"
    return AccountResult(
        index=0,
        account_id=account.account_id,
        identity=identity or account.account_id,
        ok=ok,
        message=message,
        stages=stages,
        elapsed=round(time.monotonic() - started, 3),
        bot_ok=bot_ok,
        bot_fail=bot_fail,
    )


def run_account_dry(account: AccountConfig) -> AccountResult:
    started = time.monotonic()
    stages: list[dict[str, Any]] = []
    log(f"[阶段1] 校验账号配置 · {account.account_id}")
    if account.api_id <= 0 or not account.api_hash or not account.session:
        raise RuntimeError("账号凭据不完整")
    stages.append(
        {
            "stage": 1,
            "name": "校验配置",
            "status": "success",
            "elapsed": 0.0,
            "detail": f"bots={len(account.bots)}",
        }
    )
    bot_ok = 0
    for bot_index, bot in enumerate(account.bots, start=1):
        stage_no = bot_index + 1
        for action in bot.actions:
            if action.type not in SUPPORTED_ACTIONS:
                raise RuntimeError(f"不支持的动作 {action.type}")
            if action.type == "manual_ui_required":
                raise RuntimeError("存在 manual_ui_required，预演判定为需人工处理的失败配置")
        detail = f"预演动作 {summarize_actions(bot)}"
        log(f"[阶段{stage_no}] {bot.username} · {detail}")
        log(f"DRY_RUN_OK {bot.username}", ICONS["success"])
        bot_ok += 1
        stages.append(
            {
                "stage": stage_no,
                "name": bot.username,
                "status": "success",
                "elapsed": 0.0,
                "detail": detail,
            }
        )
    return AccountResult(
        index=0,
        account_id=account.account_id,
        identity=account.account_id,
        ok=True,
        message=f"预演通过，Bot数 {bot_ok}",
        stages=stages,
        elapsed=round(time.monotonic() - started, 3),
        bot_ok=bot_ok,
        bot_fail=0,
    )


def print_banner(mode: str, total: int) -> None:
    print(TASK_NAME, flush=True)
    print("═" * 62, flush=True)
    print(f"开始时间  {now_text()}", flush=True)
    print(f"运行模式  {mode}", flush=True)
    print(f"账号数量  {total}", flush=True)
    print("═" * 62, flush=True)


def print_account_stats(result: AccountResult) -> None:
    total_stages = len(result.stages)
    success = sum(1 for item in result.stages if item.get("status") == "success")
    failed = sum(1 for item in result.stages if item.get("status") == "failure")
    skipped = sum(1 for item in result.stages if item.get("status") == "skipped")
    already = sum(1 for item in result.stages if item.get("status") == "alreadyComplete")
    log(
        f"账号统计 {result.identity}：总任务 {total_stages}，成功 {success}，"
        f"已完成 {already}，跳过 {skipped}，失败 {failed}，耗时 {result.elapsed}s"
    )


def build_notify_body(results: list[AccountResult], final_status: str) -> str:
    success = sum(1 for item in results if item.ok)
    failed = len(results) - success
    lines = [
        f"状态：{final_status}",
        f"账号总数：{len(results)}",
        f"成功：{success}",
        f"失败：{failed}",
    ]
    for item in results:
        icon = ICONS["success"] if item.ok else ICONS["failure"]
        lines.append(f"{icon} {item.identity}：{item.message}")
    return "\n".join(lines)


def emit_task_summary(payload: dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


async def async_main() -> int:
    mode = "dry-run" if dry_run_enabled() else "live"
    results: list[AccountResult] = []
    notify_status = f"{ICONS['skipped']} 未发送"
    exit_code = 1
    final_status = "failure"
    started_at = now_text()
    task_started = time.monotonic()

    try:
        accounts = load_accounts()
    except Exception as exc:
        print_banner(mode, 0)
        log(f"配置错误：{exc}", ICONS["failure"])
        notify_status = send_notify(TASK_NAME, f"状态：configuration-error\n错误：配置无效")
        emit_task_summary(
            {
                "task": TASK_NAME,
                "catalogId": CATALOG_ID,
                "status": "configuration_error",
                "mode": mode,
                "accounts": 0,
                "success": 0,
                "failed": 0,
                "notify": notify_status,
                "startedAt": started_at,
                "finishedAt": now_text(),
            }
        )
        print("─" * 62, flush=True)
        print(f"完成时间  {now_text()}", flush=True)
        print(f"最终状态  {ICONS['failure']} 配置错误", flush=True)
        print(f"通知状态  {notify_status}", flush=True)
        return 2

    print_banner(mode, len(accounts))
    if dry_run_enabled():
        log("完全断网预演：不导入 Telethon、不连接 Telegram、不发送消息")
    else:
        timeout = parse_non_negative_int("TELEGRAM_DAILY_TIMEOUT", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT
        try:
            proxy = build_proxy_tuple()
        except Exception as exc:
            log(f"代理配置错误：{exc}", ICONS["failure"])
            notify_status = send_notify(TASK_NAME, "状态：configuration-error\n错误：代理配置无效")
            emit_task_summary(
                {
                    "task": TASK_NAME,
                    "catalogId": CATALOG_ID,
                    "status": "configuration_error",
                    "mode": mode,
                    "accounts": len(accounts),
                    "success": 0,
                    "failed": len(accounts),
                    "notify": notify_status,
                    "startedAt": started_at,
                    "finishedAt": now_text(),
                }
            )
            print(f"最终状态  {ICONS['failure']} 配置错误", flush=True)
            return 2
        if proxy:
            log("SOCKS5 代理已启用（不输出主机凭据）")
        await sleep_jitter(
            "初始延迟",
            parse_non_negative_int("TELEGRAM_DAILY_INITIAL_DELAY_MIN_SECONDS", 0),
            parse_non_negative_int("TELEGRAM_DAILY_INITIAL_DELAY_MAX_SECONDS", 0),
        )

    for index, account in enumerate(accounts, start=1):
        log(f"—— 账号 {index}/{len(accounts)}：{account.account_id} ——")
        try:
            if dry_run_enabled():
                result = run_account_dry(account)
            else:
                result = await run_account_live(
                    account,
                    proxy,
                    parse_non_negative_int("TELEGRAM_DAILY_TIMEOUT", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT,
                )
            result.index = index
        except Exception as exc:
            result = AccountResult(
                index=index,
                account_id=account.account_id,
                identity=account.account_id,
                ok=False,
                message=f"{type(exc).__name__}",
                stages=[
                    {
                        "stage": 1,
                        "name": "账号执行",
                        "status": "failure",
                        "elapsed": 0.0,
                        "detail": type(exc).__name__,
                    }
                ],
                elapsed=0.0,
                bot_ok=0,
                bot_fail=1,
            )
            log(f"账号失败：{type(exc).__name__}", ICONS["failure"])
        results.append(result)
        print_account_stats(result)
        if index < len(accounts) and not dry_run_enabled():
            await sleep_jitter(
                "账号间隔",
                parse_non_negative_int("TELEGRAM_DAILY_BETWEEN_ACCOUNT_MIN_SECONDS", 0),
                parse_non_negative_int("TELEGRAM_DAILY_BETWEEN_ACCOUNT_MAX_SECONDS", 0),
            )

    success_count = sum(1 for item in results if item.ok)
    failed_count = len(results) - success_count
    if dry_run_enabled() and failed_count == 0:
        final_status = "dry_run"
        exit_code = 0
        status_text = f"{ICONS['success']} 预演通过"
    elif failed_count == 0:
        final_status = "success"
        exit_code = 0
        status_text = f"{ICONS['success']} 全部成功"
    elif success_count == 0:
        final_status = "failure"
        exit_code = 1
        status_text = f"{ICONS['failure']} 全部失败"
    else:
        final_status = "partial_failure"
        exit_code = 1
        status_text = f"{ICONS['warning']} 部分失败"

    notify_map = {
        "dry_run": "dry-run",
        "success": "success",
        "failure": "failure",
        "partial_failure": "partial-failure",
    }
    notify_status = send_notify(
        TASK_NAME,
        build_notify_body(results, notify_map.get(final_status, final_status)),
    )

    elapsed = round(time.monotonic() - task_started, 3)
    print("─" * 62, flush=True)
    log(
        f"任务统计：账号成功 {success_count}/{len(results)}，"
        f"Bot成功 {sum(item.bot_ok for item in results)}，"
        f"Bot失败 {sum(item.bot_fail for item in results)}，总耗时 {elapsed}s"
    )
    print(f"完成时间  {now_text()}", flush=True)
    print(f"最终状态  {status_text}", flush=True)
    print(f"通知状态  {notify_status}", flush=True)
    emit_task_summary(
        {
            "task": TASK_NAME,
            "catalogId": CATALOG_ID,
            "status": final_status,
            "mode": mode,
            "accounts": len(results),
            "success": success_count,
            "failed": failed_count,
            "botSuccess": sum(item.bot_ok for item in results),
            "botFailed": sum(item.bot_fail for item in results),
            "elapsedSeconds": elapsed,
            "notify": notify_status,
            "startedAt": started_at,
            "finishedAt": now_text(),
        }
    )
    if dry_run_enabled() and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    return exit_code


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print(f"{ICONS['warning']} 用户中断", flush=True)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
