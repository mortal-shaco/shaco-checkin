#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 全民K歌每日任务
# cron: 35 2 * * *
"""全民K歌每日奖励任务（独立维护版）。

上游来源：yuxian158/check 的 dailycheckin_scripts/ck_kgqq.py
上游提交：723c834f121ff4eef2dec7afe521071a7efff1a9
许可证：MIT（SPDX-License-Identifier: MIT）

环境变量：
  KGQQ_COOKIE       必填。每行一个账号的完整 Cookie，Cookie 内必须含 uid。
  KGQQ              可选。KGQQ_COOKIE 未设置时使用的旧变量别名，同样每行一账号。
  KGQQ_DRY_RUN      设为 1/true/yes/on 时断网预演，不发业务请求或通知。
  KGQQ_TIMEOUT      可选，请求超时秒数，默认 15，范围 1～60。
  QINGLONG_NOTIFY   可选，全局通知开关；默认 auto。

Cookie 获取：登录全民K歌网页版，在浏览器开发者工具的网络请求中复制 Cookie
请求头的完整值。Cookie 属于敏感凭据，请仅保存到青龙环境变量中。
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
        _ql_notify_identities = ('e11f1f2a1bfb0af5', 'scripts/ck_kgqq.py', 'ck_kgqq.py', 'ck_kgqq')
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
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TASK_NAME = "全民K歌每日任务"
CATALOG_ID = "e11f1f2a1bfb0af5"
DRY_RUN_ENV = "KGQQ_DRY_RUN"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
MAX_RESPONSE_BYTES = 1024 * 1024

PROFILE_MAP_EXT = (
    "JTdCJTIyZmlsZSUyMiUzQSUyMnByb2ZpbGVfd2ViYXBwSmNlJTIyJTJDJTIyY21kTmFtZSUy"
    "JTNBJTIyUHJvZmlsZUdldCUyMiUyQyUyMmFwcGlkJTIyJTNBMTAwMDYyNiUyQyUyMmRjYXBpJTIy"
    "JTNBJTdCJTIyaW50ZXJmYWNlSWQlMjIlM0EyMDUzNTk1OTclN0QlMkMlMjJsNWFwaSUyMiUzQSU3"
    "QiUyMm1vZGlkJTIyJTNBMjk0MDE3JTJDJTIyY21kJTIyJTNBMjYyMTQ0JTdEJTJDJTIyaXAlMjIl"
    "M0ElMjIxMDAuMTEzLjE2Mi4xNzglMjIlMkMlMjJwb3J0JTIyJTNBJTIyMTI0MDYlMjIlN0Q="
)
LOTTERY_MAP_EXT = (
    "JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVy"
    "eVJlcSUyMiUyQyUyMnduc0NvbmZpZyUyMiUzQSU3QiUyMmFwcGlkJTIyJTNBMTAwMDU1NyU3RCUy"
    "QyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQlMjIlM0E1ODk4"
    "MjQlN0QlN0Q="
)
SIGNIN_MAP_EXT = (
    "JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2ln"
    "bkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2"
    "MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIy"
    "JTNBNTg5ODI0JTdEJTdE"
)
LOTTERY_103_MAP_EXT = (
    "JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVy"
    "eVJlcSUyMiUyQyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQl"
    "MjIlM0E1ODk4MjQlN0QlMkMlMjJsNWFwaV9leHAxJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E4MTcw"
    "ODklMkMlMjJjbWQlMjIlM0EzODAxMDg4JTdEJTdE"
)
MUSIC_MAP_EXT = (
    "JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldEJhdGNoTXVzaWNDYXJkc1JlcSUyMiUyQyUyMmZpbGUl"
    "MjIlM0ElMjJwcm90b19tdXNpY19zdGF0aW9uSmNlJTIyJTJDJTIyd25zRGlzcGF0Y2hlciUyMiUz"
    "QXRydWUlN0Q="
)
MUSIC_REWARD_MAP_EXT = (
    "JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldFJld2FyZFJlcSUyMiUyQyUyMmZpbGUlMjIlM0ElMjJw"
    "cm90b19tdXNpY19zdGF0aW9uSmNlJTIyJTJDJTIyd25zRGlzcGF0Y2hlciUyMiUzQXRydWUlN0Q="
)
VIP_REWARD_MAP_EXT = "JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldFZpcERheVJld2FyZCUyMiU3RA=="


class SafeTaskError(Exception):
    """可安全显示、且不包含响应原文或请求凭据的任务错误。"""


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def clock_text() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def safe_message(value: Any, limit: int = 120) -> str:
    """只保留短业务提示，并清除可能出现的手机号或凭据字段。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)(cookie|token|session|skey|uin|uid)\s*[:=]\s*[^\s,;]+", r"\1=[已隐藏]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit] if text else "接口未提供提示"


def public_identity(value: str, limit: int = 80) -> str:
    """展示官方公开昵称；仅折叠空白，并按安全要求遮蔽疑似手机号。"""
    text = re.sub(r"\s+", " ", value).strip()
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit]


def cookie_uid(cookie: str) -> str:
    for part in cookie.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key.strip().lower() == "uid" and value.strip():
            return value.strip()
    raise SafeTaskError("Cookie 缺少非空 uid 字段")


def read_accounts() -> Tuple[List[str], str]:
    source = "KGQQ_COOKIE"
    raw = os.getenv(source, "")
    if not raw.strip():
        source = "KGQQ"
        raw = os.getenv(source, "")
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    return accounts, source


def request_json(url: str, cookie: str, timeout: float) -> Dict[str, Any]:
    request = Request(
        url,
        headers={
            "Cookie": cookie,
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 Qinglong-KGQQ-Maintained/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise SafeTaskError(f"HTTP 状态异常：{status}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise SafeTaskError(f"HTTP 状态异常：{exc.code}") from None
    except URLError:
        raise SafeTaskError("网络连接失败") from None
    except TimeoutError:
        raise SafeTaskError("请求超时") from None
    except OSError:
        raise SafeTaskError("网络请求失败") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SafeTaskError("响应超过 1 MiB 安全上限")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SafeTaskError("响应不是有效 JSON") from None
    if not isinstance(payload, dict):
        raise SafeTaskError("响应 JSON 顶层不是对象")
    return payload


def code_number(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def checked_node(
    payload: Dict[str, Any], expected_key: str, *, allow_terminal_1000: bool = False
) -> Tuple[str, Optional[Dict[str, Any]], str]:
    """验证根业务码、预期响应节点和节点内显式业务码。"""
    root_code = code_number(payload.get("code"))
    root_message = safe_message(payload.get("msg") or payload.get("message"))
    if root_code == 1000 and allow_terminal_1000:
        return "already", None, root_message
    if root_code not in (None, 0, 200):
        raise SafeTaskError(f"业务码 {root_code}：{root_message}")
    data = payload.get("data")
    if not isinstance(data, dict) or expected_key not in data:
        raise SafeTaskError(f"响应缺少业务节点 {expected_key}")
    node = data.get(expected_key)
    if not isinstance(node, dict):
        raise SafeTaskError(f"业务节点 {expected_key} 格式异常")
    for key in ("iRet", "ret", "resultCode", "iResult"):
        if key in node:
            nested_code = code_number(node.get(key))
            if nested_code not in (None, 0, 200):
                detail = safe_message(node.get("strTips") or node.get("msg") or node.get("message"))
                raise SafeTaskError(f"业务节点返回码 {nested_code}：{detail}")
    detail = safe_message(node.get("strTips") or node.get("msg") or root_message)
    return "success", node, detail


def api_call(
    url: str,
    cookie: str,
    timeout: float,
    expected_key: str,
    *,
    allow_terminal_1000: bool = False,
) -> Tuple[str, Optional[Dict[str, Any]], str]:
    payload = request_json(url, cookie, timeout)
    return checked_node(payload, expected_key, allow_terminal_1000=allow_terminal_1000)


def proxy_url(params: Dict[str, Any]) -> str:
    return "https://node.kg.qq.com/webapp/proxy?" + urlencode(params)


def profile_url(uid: str) -> str:
    return proxy_url(
        {
            "ns": "proto_profile",
            "cmd": "profile.getProfile",
            "mapExt": PROFILE_MAP_EXT,
            "t_uUid": uid,
        }
    )


def daily_urls(uid: str) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for lottery_type in ("1", "2"):
        result.append(
            (
                f"抽奖入口 {lottery_type}",
                proxy_url(
                    {
                        "ns": "KG_TASK",
                        "cmd": "task.getLottery",
                        "ns_inbuf": "",
                        "mapExt": LOTTERY_MAP_EXT,
                        "t_uid": uid,
                        "t_iShowEntry": "1",
                        "t_type": lottery_type,
                    }
                ),
            )
        )
    for entry in ("1", "2", "4", "16", "128", "512"):
        result.append(
            (
                f"签到奖励入口 {entry}",
                proxy_url(
                    {
                        "ns": "KG_TASK",
                        "cmd": "task.signinGetAward",
                        "mapExt": SIGNIN_MAP_EXT,
                        "t_uid": uid,
                        "t_iShowEntry": entry,
                    }
                ),
            )
        )
    result.append(
        (
            "抽奖入口 104",
            proxy_url(
                {
                    "ns": "KG_TASK",
                    "cmd": "task.getLottery",
                    "mapExt": LOTTERY_MAP_EXT,
                    "t_uid": uid,
                    "t_iShowEntry": "4",
                    "t_type": "104",
                }
            ),
        )
    )
    result.append(
        (
            "抽奖入口 103",
            proxy_url(
                {
                    "ns": "KG_TASK",
                    "cmd": "task.getLottery",
                    "mapExt": LOTTERY_103_MAP_EXT,
                    "t_uid": uid,
                    "t_type": "103",
                }
            ),
        )
    )
    return result


@dataclass
class Counters:
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

    def merge(self, other: "Counters") -> None:
        for key in ("total", "success", "already", "skipped", "failed"):
            setattr(self, key, getattr(self, key) + getattr(other, key))


@dataclass
class AccountResult:
    index: int
    identity: str
    ok: bool
    counters: Counters = field(default_factory=Counters)
    flower_before: Optional[int] = None
    flower_after: Optional[int] = None
    elapsed: float = 0.0


def stage(index: int, title: str, operation: Callable[[], None]) -> None:
    started = time.monotonic()
    print(f"[{clock_text()}]   [{index}/6] {title}", flush=True)
    operation()
    print(f"[{clock_text()}]   [{index}/6] {title}完成，耗时 {time.monotonic() - started:.2f}s", flush=True)


def fetch_profile(uid: str, cookie: str, timeout: float) -> Tuple[str, int]:
    _, node, _ = api_call(profile_url(uid), cookie, timeout, "profile.getProfile")
    assert node is not None
    person = node.get("stPersonInfo")
    nickname = person.get("sKgNick") if isinstance(person, dict) else None
    if not isinstance(nickname, str) or not nickname.strip():
        raise SafeTaskError("个人资料缺少昵称")
    try:
        flowers = int(node["uFlowerNum"])
    except (KeyError, TypeError, ValueError):
        raise SafeTaskError("个人资料缺少有效鲜花数量") from None
    return nickname.strip(), flowers


def run_account(index: int, cookie: str, timeout: float, dry_run: bool) -> AccountResult:
    started = time.monotonic()
    counters = Counters()
    identity = f"账号{index}"
    before: Optional[int] = None
    after: Optional[int] = None
    uid = ""
    print(f"\n[{clock_text()}] ┌─ 账号 {index}", flush=True)

    def validate() -> None:
        nonlocal uid
        try:
            uid = cookie_uid(cookie)
            counters.add("success")
            print(f"[{clock_text()}]     ✅ 凭据结构有效（敏感值已隐藏）", flush=True)
        except SafeTaskError as exc:
            counters.add("failed")
            print(f"[{clock_text()}]     ❌ {exc}", flush=True)

    stage(1, "验证账号配置", validate)
    if not uid:
        elapsed = time.monotonic() - started
        print(f"[{clock_text()}] └─ 账号 {index}失败：总任务 1，失败 1，耗时 {elapsed:.2f}s", flush=True)
        return AccountResult(index, identity, False, counters, elapsed=elapsed)

    if dry_run:
        for number, title in enumerate(
            ("读取领取前资料", "执行签到与抽奖", "领取音乐卡片奖励", "检查 VIP 每日奖励", "读取领取后资料"),
            start=2,
        ):
            def preview(label: str = title) -> None:
                counters.add("skipped")
                print(f"[{clock_text()}]     ⏭️ 断网预演：将执行“{label}”", flush=True)

            stage(number, title, preview)
        elapsed = time.monotonic() - started
        print(
            f"[{clock_text()}] └─ 账号 {index}预演完成：总任务 {counters.total}，成功 {counters.success}，"
            f"已完成 {counters.already}，跳过 {counters.skipped}，失败 {counters.failed}，耗时 {elapsed:.2f}s",
            flush=True,
        )
        return AccountResult(index, identity, True, counters, elapsed=elapsed)

    def before_profile() -> None:
        nonlocal identity, before
        try:
            identity, before = fetch_profile(uid, cookie, timeout)
            counters.add("success")
            print(f"[{clock_text()}]     ✅ 官方账号昵称：{public_identity(identity)}；当前鲜花：{before}", flush=True)
        except SafeTaskError as exc:
            counters.add("failed")
            print(f"[{clock_text()}]     ❌ 读取资料失败：{exc}", flush=True)

    stage(2, "读取领取前资料", before_profile)

    def daily_rewards() -> None:
        for label, url in daily_urls(uid):
            expected = "task.signinGetAward" if "签到" in label else "task.getLottery"
            try:
                status, _, detail = api_call(url, cookie, timeout, expected)
                counters.add(status)
                print(f"[{clock_text()}]     ✅ {label}：{detail}", flush=True)
            except SafeTaskError as exc:
                counters.add("failed")
                print(f"[{clock_text()}]     ❌ {label}：{exc}", flush=True)

    stage(3, "执行签到与抽奖", daily_rewards)

    def music_rewards() -> None:
        for attempt in range(16):
            cards_url = proxy_url(
                {
                    "ns": "proto_music_station",
                    "cmd": "message.batch_get_music_cards",
                    "mapExt": MUSIC_MAP_EXT,
                    "t_uUid": uid,
                    "g_tk_openkey": str(attempt),
                }
            )
            try:
                status, node, detail = api_call(
                    cards_url,
                    cookie,
                    timeout,
                    "message.batch_get_music_cards",
                    allow_terminal_1000=True,
                )
                if status == "already":
                    counters.add("already")
                    print(f"[{clock_text()}]     ☑️ 音乐奖励已处理完：{detail}", flush=True)
                    break
                assert node is not None
                cards = node.get("vctMusicCards")
                if not isinstance(cards, list) or not cards:
                    counters.add("already")
                    print(f"[{clock_text()}]     ☑️ 当前没有可领取的音乐卡片", flush=True)
                    break
                usable = [card for card in cards if isinstance(card, dict) and isinstance(card.get("stReward"), dict)]
                if not usable:
                    raise SafeTaskError("音乐卡片缺少奖励信息")
                card = max(usable, key=lambda item: code_number(item["stReward"].get("uFlowerNum")) or 0)
                amount = code_number(card["stReward"].get("uFlowerNum")) or 0
                ugc_id = card.get("strUgcId")
                key = card.get("strKey")
                if amount <= 0 or not isinstance(ugc_id, str) or not ugc_id or not isinstance(key, str) or not key:
                    raise SafeTaskError("音乐卡片奖励字段不完整")
                reward_object = (
                    '{"uInteractiveType":1,"uRewardType":0,"uFlowerNum":15}'
                    if amount > 10
                    else '{"uInteractiveType":0,"uRewardType":0,"uFlowerNum":10}'
                )
                reward_url = proxy_url(
                    {
                        "t_stReward:object": reward_object,
                        "ns": "proto_music_station",
                        "cmd": "message.get_reward",
                        "mapExt": MUSIC_REWARD_MAP_EXT,
                        "t_uUid": uid,
                        "t_strUgcId": ugc_id,
                        "t_strKey": key,
                    }
                )
                reward_status, _, reward_detail = api_call(
                    reward_url, cookie, timeout, "message.get_reward"
                )
                counters.add(reward_status)
                print(f"[{clock_text()}]     ✅ 第 {attempt + 1} 次音乐卡片领取：{reward_detail}", flush=True)
            except SafeTaskError as exc:
                counters.add("failed")
                print(f"[{clock_text()}]     ❌ 第 {attempt + 1} 次音乐卡片处理失败：{exc}", flush=True)
                break

    stage(4, "领取音乐卡片奖励", music_rewards)

    def vip_reward() -> None:
        info_url = proxy_url(
            {
                "ns": "proto_vip_webapp",
                "cmd": "vip.get_vip_info",
                "t_uUid": uid,
                "t_uWebReq": "1",
                "t_uGetDataFromC4B": "1",
            }
        )
        try:
            _, node, _ = api_call(info_url, cookie, timeout, "vip.get_vip_info")
            assert node is not None
            core = node.get("stVipCoreInfo")
            if not isinstance(core, dict) or code_number(core.get("uStatus")) is None:
                raise SafeTaskError("VIP 信息缺少状态字段")
            if code_number(core.get("uStatus")) != 1:
                counters.add("skipped")
                print(f"[{clock_text()}]     ⏭️ 非 VIP 用户，无需领取 VIP 奖励", flush=True)
                return
            reward_url = proxy_url(
                {
                    "t_uUid": uid,
                    "ns": "proto_vip_webapp",
                    "cmd": "vip.get_vip_day_reward",
                    "ns_inbuf": "",
                    "mapExt": VIP_REWARD_MAP_EXT,
                    "g_tk_openkey": "642424811",
                }
            )
            status, reward_node, detail = api_call(
                reward_url, cookie, timeout, "vip.get_vip_day_reward"
            )
            counters.add(status)
            count = reward_node.get("uCurRewardNum") if reward_node else None
            count_text = f"，道具数量 {count}" if isinstance(count, (int, float)) else ""
            print(f"[{clock_text()}]     ✅ VIP 每日奖励：{detail}{count_text}", flush=True)
        except SafeTaskError as exc:
            counters.add("failed")
            print(f"[{clock_text()}]     ❌ VIP 奖励处理失败：{exc}", flush=True)

    stage(5, "检查 VIP 每日奖励", vip_reward)

    def after_profile() -> None:
        nonlocal identity, after
        try:
            identity, after = fetch_profile(uid, cookie, timeout)
            counters.add("success")
            delta = after - before if before is not None else None
            delta_text = f"；本次增加：{delta}" if delta is not None else ""
            print(
                f"[{clock_text()}]     ✅ 官方账号昵称：{public_identity(identity)}；当前鲜花：{after}{delta_text}",
                flush=True,
            )
        except SafeTaskError as exc:
            counters.add("failed")
            print(f"[{clock_text()}]     ❌ 读取最终资料失败：{exc}", flush=True)

    stage(6, "读取领取后资料", after_profile)
    elapsed = time.monotonic() - started
    ok = counters.failed == 0
    icon = "✅" if ok else "❌"
    print(
        f"[{clock_text()}] └─ {icon} {public_identity(identity)}：总任务 {counters.total}，成功 {counters.success}，"
        f"已完成 {counters.already}，跳过 {counters.skipped}，失败 {counters.failed}，耗时 {elapsed:.2f}s",
        flush=True,
    )
    return AccountResult(index, identity, ok, counters, before, after, elapsed)


def selector_matches(value: str) -> bool:
    selectors = [item for item in re.split(r"[,;\s]+", value) if item]
    if not selectors:
        return False
    current = Path(__file__)
    candidates = {CATALOG_ID, current.name, current.as_posix(), "ck_kgqq.py", "output/candidate.py"}
    return any(selector == "*" or any(fnmatch.fnmatch(candidate, selector) for candidate in candidates) for selector in selectors)


def notification_enabled() -> Tuple[bool, str]:
    raw = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in FALSE_VALUES:
        return False, "全局开关已关闭"
    if raw in TRUE_VALUES:
        return True, "全局开关已开启"
    if "QINGLONG_NOTIFY_SCRIPTS" in os.environ:
        selected = selector_matches(os.environ.get("QINGLONG_NOTIFY_SCRIPTS", ""))
        return selected, "脚本选择列表已匹配" if selected else "脚本选择列表未匹配"
    return True, "按计划任务默认策略开启"


def notify(title: str, body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if dry_run:
        return "已跳过（断网预演禁止通知网络）"
    if not enabled:
        return f"已跳过（{reason}）"
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            return "已发送（notify.send）"
    except Exception:
        pass
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    python_paths = []
    javascript_paths = []
    if notify_dir:
        python_paths.append(Path(notify_dir) / "notify.py")
        javascript_paths.append(Path(notify_dir) / "sendNotify.js")
    python_paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    javascript_paths.extend((Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")))
    for path in python_paths:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify_local", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                return f"已发送（{path.name}）"
        except Exception:
            continue
    node = shutil.which("node")
    if node:
        for path in javascript_paths:
            if not path.is_file():
                continue
            try:
                completed = subprocess.run(
                    [node, str(path), title, body],
                    check=False,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if completed.returncode == 0:
                    return f"已发送（{path.name}）"
            except (OSError, subprocess.TimeoutExpired):
                continue
    return "发送失败（未找到可用通知器或通知器执行失败）"


def parse_timeout() -> float:
    raw = os.getenv("KGQQ_TIMEOUT", "15").strip()
    try:
        value = float(raw)
    except ValueError:
        raise SafeTaskError("KGQQ_TIMEOUT 必须是数字") from None
    if not 1 <= value <= 60:
        raise SafeTaskError("KGQQ_TIMEOUT 必须在 1～60 秒之间")
    return value


def print_final(
    started_wall: str,
    started_mono: float,
    results: List[AccountResult],
    dry_run: bool,
    config_error: Optional[str] = None,
) -> int:
    total_accounts = len(results)
    succeeded = sum(1 for item in results if item.ok)
    failed = total_accounts - succeeded
    aggregate = Counters()
    for result in results:
        aggregate.merge(result.counters)
    if config_error:
        status = "configuration-error"
        exit_code = 2
    elif dry_run:
        status = "dry-run" if failed == 0 else "failure"
        exit_code = 0 if failed == 0 else 1
    elif failed == 0:
        status = "success"
        exit_code = 0
    elif succeeded:
        status = "partial-failure"
        exit_code = 1
    else:
        status = "failure"
        exit_code = 1
    body = f"账号总数：{total_accounts}；成功：{succeeded}；失败：{failed}；状态：{status}。"
    if config_error:
        body += " 配置错误，请检查必填环境变量。"
    notification = notify(TASK_NAME, body, dry_run)
    finished = now_text()
    elapsed = time.monotonic() - started_mono
    print("\n" + "=" * 60, flush=True)
    print(f"任务统计：账号总数 {total_accounts}，成功 {succeeded}，失败 {failed}", flush=True)
    print(
        f"子任务统计：总数 {aggregate.total}，成功 {aggregate.success}，已完成 {aggregate.already}，"
        f"跳过 {aggregate.skipped}，失败 {aggregate.failed}",
        flush=True,
    )
    print(f"开始时间：{started_wall}", flush=True)
    print(f"完成时间：{finished}", flush=True)
    print(f"总耗时：{elapsed:.2f}s", flush=True)
    print(f"通知状态：{notification}", flush=True)
    display_status = {
        "success": "SUCCESS",
        "partial-failure": "PARTIAL_FAILURE",
        "failure": "FAILURE",
        "configuration-error": "CONFIGURATION_ERROR",
        "dry-run": "DRY_RUN",
    }[status]
    print(f"最终状态: {display_status}", flush=True)
    summary = {
        "task": TASK_NAME,
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": {"total": total_accounts, "success": succeeded, "failed": failed},
        "subtasks": {
            "total": aggregate.total,
            "success": aggregate.success,
            "alreadyComplete": aggregate.already,
            "skipped": aggregate.skipped,
            "failed": aggregate.failed,
        },
        "notification": notification,
        "exitCode": exit_code,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


def main() -> int:
    started_wall = now_text()
    started_mono = time.monotonic()
    dry_run = env_truthy(DRY_RUN_ENV)
    print("=" * 60, flush=True)
    print(f"{TASK_NAME}", flush=True)
    print("=" * 60, flush=True)
    print(f"开始时间：{started_wall}", flush=True)
    print(f"运行模式：{'断网预演' if dry_run else '正式执行'}", flush=True)
    accounts, source = read_accounts()
    print(f"账号数量：{len(accounts)}", flush=True)
    if accounts:
        print(f"凭据来源：{source}（内容已隐藏）", flush=True)
    if not accounts:
        error = "缺少必填环境变量 KGQQ_COOKIE（兼容旧变量 KGQQ）"
        print(f"[{clock_text()}] ❌ 配置错误：{error}", flush=True)
        return print_final(started_wall, started_mono, [], dry_run, error)
    try:
        timeout = parse_timeout()
    except SafeTaskError as exc:
        print(f"[{clock_text()}] ❌ 配置错误：{exc}", flush=True)
        return print_final(started_wall, started_mono, [], dry_run, str(exc))
    results: List[AccountResult] = []
    for index, cookie in enumerate(accounts, start=1):
        try:
            results.append(run_account(index, cookie, timeout, dry_run))
        except Exception as exc:
            # 最后的账户级隔离：不显示可能携带敏感数据的异常正文。
            print(f"[{clock_text()}] ❌ 账号 {index}发生未预期的 {type(exc).__name__}", flush=True)
            failed_counter = Counters(total=1, failed=1)
            results.append(AccountResult(index, f"账号{index}", False, failed_counter))
    return print_final(started_wall, started_mono, results, dry_run)


if __name__ == "__main__":
    sys.exit(main())
