#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 顺丰速运签到
# cron: 17 0 * * *
"""顺丰速运签到（独立维护版）。

Upstream: agluo/ql-script-hub/SFSU_checkin.py
Original sources credited upstream:
  https://github.com/faintout/myself-script/blob/main/sfsy.py
  https://github.com/Xx1aoy1/scripts/blob/main/sf2.py
License: MIT

Required environment:
  sfsyUrl  One URL-encoded SF Express login/share URL per non-empty line.
            Obtain it after signing in to the SF Express app/mini-program, open
            My > Points, and capture either shareGiftReceiveRedirect or
            share/app/shareRedirect. Store the complete captured URL; do not
            paste it into logs or notifications.

Optional environment:
  SFSU_DRY_RUN=1       Offline validation; performs no network or account writes.
  SF_AUTO_COUPON=1     Permit a free life-privilege coupon order. Default: off.
  SF_RANDOM_DELAY_MAX  Maximum initial random delay in seconds. Default: 0.
  QINGLONG_NOTIFY=0    Disable Qinglong notification. Default: enabled.
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
        _ql_notify_identities = ('19b2285cc7b8a82e', 'scripts/sfsu_checkin.py', 'sfsu_checkin.py', 'sfsu_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

NAME = "顺丰速运签到"
BASE = "https://mcs-mimp-web.sf-express.com/mcs-mimp"
TIMEOUT = (10, 30)
FALSE_VALUES = {"0", "false", "no", "off"}
SKIP_POINT_TITLES = {"用行业模板寄件下单", "去新增一个收件偏好", "参与积分活动"}
SKIP_MEMBER_TYPES = {
    "SEND_SUCCESS", "INVITEFRIENDS_PARTAKE_ACTIVITY", "OPEN_SVIP",
    "OPEN_NEW_EXPRESS_CARD", "OPEN_FAMILY_CARD", "CHARGE_NEW_EXPRESS_CARD",
    "INTEGRAL_EXCHANGE", "OPEN_SUPER_CARD",
}


def enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in FALSE_VALUES and value.strip() != ""


def clean_message(value: Any) -> str:
    """Return a short diagnostic without URLs, cookies, tokens, or responses."""
    text = re.sub(r"https?://\S+", "[URL已脱敏]", str(value or "未知错误"))
    text = re.sub(r"(?i)(cookie|token|signature|authorization)\s*[:=]\s*\S+", r"\1=[已脱敏]", text)
    return " ".join(text.split())[:180]


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Counts:
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

    def merge(self, other: "Counts") -> None:
        for key in ("total", "success", "already", "skipped", "failed"):
            setattr(self, key, getattr(self, key) + getattr(other, key))

    def data(self) -> Dict[str, int]:
        return {k: getattr(self, k) for k in ("total", "success", "already", "skipped", "failed")}


class Account:
    def __init__(self, credential: str, number: int, dry_run: bool, coupon: bool):
        self.credential = credential
        self.number = number
        self.label = f"账号{number}"
        self.dry_run = dry_run
        self.coupon = coupon
        self.counts = Counts()
        self.started = time.monotonic()
        self.user_id = ""
        self.phone_mask = ""
        self.member_blocked = False
        self.headers = {
            "User-Agent": "Mozilla/5.0 MicroMessenger/7.0 MiniProgram",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "platform": "MINI_PROGRAM",
        }
        self.session = requests.Session() if requests is not None else None

    def log(self, message: str) -> None:
        print(f"[{self.label}] {message}")

    def result(self, status: str, message: str) -> bool:
        icons = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failed": "❌"}
        self.counts.add(status)
        self.log(f"{icons[status]} {message}")
        return status != "failed"

    def sign_headers(self) -> None:
        timestamp = str(int(time.time() * 1000))
        raw = f"token=wwesldfs29aniversaryvdld29&timestamp={timestamp}&sysCode=MCS-MIMP-CORE"
        self.headers.update({
            "sysCode": "MCS-MIMP-CORE", "timestamp": timestamp,
            "signature": hashlib.md5(raw.encode()).hexdigest(),
        })

    def request(self, route: str, payload: Optional[dict] = None, method: str = "POST") -> Dict[str, Any]:
        if self.dry_run:
            raise RuntimeError("dry-run attempted network access")
        self.sign_headers()
        url = BASE + route
        last = "请求失败"
        for attempt in range(1, 4):
            try:
                response = self.session.request(
                    method, url, headers=self.headers,
                    json=payload if method == "POST" else None,
                    timeout=TIMEOUT, allow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("响应不是JSON对象")
                return data
            except Exception as exc:
                last = clean_message(exc)
                if attempt < 3:
                    time.sleep(attempt)
        return {"success": False, "errorMessage": last, "_transportFailure": True}

    @staticmethod
    def ok(data: Dict[str, Any]) -> bool:
        return data.get("success") is True

    def login(self) -> bool:
        if self.dry_run:
            return self.result("success", "离线预演：登录参数格式已验证（未发送）")
        try:
            response = self.session.get(self.credential, headers=self.headers, timeout=TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            cookies = self.session.cookies.get_dict()
            phone = str(cookies.get("_login_mobile_", ""))
            self.user_id = str(cookies.get("_login_user_id_", ""))
            if not phone or not self.user_id:
                return self.result("failed", "登录失败：未取得完整账户会话，请重新抓取URL")
            self.phone_mask = phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else "已登录账户"
            return self.result("success", f"登录成功（{self.phone_mask}）")
        except Exception as exc:
            return self.result("failed", f"登录请求失败：{clean_message(exc)}")

    def daily_sign(self) -> None:
        if self.dry_run:
            self.result("success", "离线预演：将执行每日签到")
            return
        data = self.request(
            "/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage",
            {"comeFrom": "vioin", "channelFrom": "WEIXIN"},
        )
        if not self.ok(data):
            self.result("failed", f"签到失败：{clean_message(data.get('errorMessage'))}")
            return
        obj = data.get("obj") or {}
        packets = obj.get("integralTaskSignPackageVOList") or []
        if packets:
            self.result("success", f"签到成功，本周累计{int(obj.get('countDay', 0)) + 1}天")
        else:
            self.result("already", f"今日已签到，本周累计{int(obj.get('countDay', 0)) + 1}天")

    def point_tasks(self) -> None:
        if self.dry_run:
            self.result("success", "离线预演：将查询积分、完成安全任务并领取奖励")
            return
        route = "/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES"
        data = self.request(route, {"channelType": "1", "deviceId": self.device_id()})
        if not self.ok(data) or not isinstance(data.get("obj"), dict):
            self.result("failed", f"积分任务查询失败：{clean_message(data.get('errorMessage'))}")
            return
        obj = data["obj"]
        self.result("success", f"执行前积分：{obj.get('totalPoint', '未知')}")
        for task in obj.get("taskTitleLevels") or []:
            title = clean_message(task.get("title", "未命名任务"))
            if task.get("status") == 3:
                self.result("already", f"积分任务已完成：{title}")
                continue
            if title in SKIP_POINT_TITLES:
                self.result("skipped", f"积分任务需真实业务操作，已跳过：{title}")
                continue
            code, task_id, strategy = task.get("taskCode"), task.get("taskId"), task.get("strategyId")
            if not all((code, task_id, strategy)):
                self.result("failed", f"积分任务字段缺失：{title}")
                continue
            done = self.request("/commonRoutePost/memberEs/taskRecord/finishTask", {"taskCode": code})
            if not self.ok(done):
                self.result("failed", f"积分任务失败：{title}；{clean_message(done.get('errorMessage'))}")
                continue
            self.result("success", f"积分任务完成：{title}")
            reward = self.request(
                "/commonPost/~memberNonactivity~integralTaskStrategyService~fetchIntegral",
                {"strategyId": strategy, "taskId": task_id, "taskCode": code, "deviceId": self.device_id()},
            )
            self.result("success" if self.ok(reward) else "failed", f"积分奖励{'领取成功' if self.ok(reward) else '领取失败'}：{title}")
        final = self.request(route, {"channelType": "1", "deviceId": self.device_id()})
        if self.ok(final) and isinstance(final.get("obj"), dict):
            self.result("success", f"当前积分：{final['obj'].get('totalPoint', '未知')}")
        else:
            self.result("failed", "最终积分查询失败")

    def honey_tasks(self) -> None:
        if self.dry_run:
            self.result("success", "离线预演：将完成丰蜜任务、冒险、扩容并领取丰蜜")
            self.result("success" if self.coupon else "skipped", "离线预演：生活特权领券" + ("已授权" if self.coupon else "未授权（SF_AUTO_COUPON=1可启用）"))
            return
        self.headers["channel"] = "wxwdsj"
        detail = self.request("/commonPost/~memberNonactivity~receiveExchangeIndexService~taskDetail", {})
        if not self.ok(detail) or not isinstance(detail.get("obj"), dict):
            self.result("failed", f"丰蜜任务查询失败：{clean_message(detail.get('errorMessage'))}")
            return
        for item in detail["obj"].get("list") or []:
            task_type = str(item.get("taskType", "未知任务"))
            if item.get("status") == 3:
                self.result("already", f"丰蜜任务已完成：{task_type}")
                continue
            code = item.get("taskCode")
            if task_type == "DAILY_VIP_TASK_TYPE":
                self.coupon_task(code)
            elif code:
                done = self.request("/commonPost/~memberEs~taskRecord~finishTask", {"taskCode": code})
                self.result("success" if self.ok(done) else "failed", f"丰蜜任务{'完成' if self.ok(done) else '失败'}：{task_type}")
            if task_type == "BEES_GAME_TASK_TYPE":
                self.honey_game()
        index_route = "/commonPost/~memberNonactivity~receiveExchangeIndexService~indexData"
        index = self.request(index_route, {"inviteUserId": ""})
        if not self.ok(index) or not isinstance(index.get("obj"), dict):
            self.result("failed", f"丰蜜首页查询失败：{clean_message(index.get('errorMessage'))}")
            return
        obj = index["obj"]
        self.result("success", f"执行前丰蜜：{obj.get('usableHoney', '未知')}；活动截止：{clean_message(obj.get('activityEndTime', '未知'))}")
        for task in obj.get("taskDetail") or []:
            task_type = task.get("type")
            reward = self.request("/commonPost/~memberNonactivity~receiveExchangeIndexService~receiveHoney", {"taskType": task_type})
            message = str(reward.get("errorMessage", ""))
            status = "success" if self.ok(reward) else ("already" if "已" in message else "failed")
            self.result(status, f"丰蜜奖励{'领取成功' if self.ok(reward) else clean_message(message)}：{clean_message(task_type)}")
        final = self.request(index_route, {"inviteUserId": ""})
        if self.ok(final) and isinstance(final.get("obj"), dict):
            self.result("success", f"当前丰蜜：{final['obj'].get('usableHoney', '未知')}")
        else:
            self.result("failed", "最终丰蜜查询失败")

    def coupon_task(self, task_code: Any) -> None:
        if not self.coupon:
            self.result("skipped", "生活特权领券未授权（设置SF_AUTO_COUPON=1启用）")
            return
        listing = self.request("/commonPost/~memberGoods~mallGoodsLifeService~list", {"memGrade": 2, "categoryCode": "SHTQ", "showCode": "SHTQWNTJ"})
        if not self.ok(listing):
            self.result("failed", "生活特权券列表查询失败")
            return
        goods_list = [g for group in (listing.get("obj") or []) for g in (group.get("goodsList") or [])]
        eligible = [g for g in goods_list if g.get("goodsNo") and g.get("exchangeTimesLimit", 0) >= 1]
        if not eligible:
            self.result("already", "没有可领取的生活特权券")
            return
        goods = eligible[0]
        order = self.request("/commonPost/~memberGoods~pointMallService~createOrder", {
            "from": "Point_Mall", "orderSource": "POINT_MALL_EXCHANGE",
            "goodsNo": goods["goodsNo"], "quantity": 1, "taskCode": task_code,
        })
        self.result("success" if self.ok(order) else "failed", "生活特权券" + ("领取成功" if self.ok(order) else "领取失败"))

    def honey_game(self) -> None:
        for number in range(1, 6):
            data = self.request("/commonPost/~memberNonactivity~receiveExchangeGameService~gameReport", {"gatherHoney": 20})
            if self.ok(data):
                self.result("success", f"丰蜜大冒险第{number}次完成")
                continue
            if data.get("errorMessage") == "容量不足":
                expanded = self.request("/commonPost/~memberNonactivity~receiveExchangeIndexService~expand", {})
                self.result("success" if self.ok(expanded) else "failed", "丰蜜容器" + ("扩容成功" if self.ok(expanded) else "扩容失败"))
                if self.ok(expanded):
                    continue
            self.result("failed", f"丰蜜大冒险第{number}次失败：{clean_message(data.get('errorMessage'))}")
            break

    def member_day(self) -> None:
        if not 26 <= datetime.now().day <= 28:
            self.result("skipped", "当前非会员日执行窗口（每月26–28日）")
            return
        if self.dry_run:
            self.result("success", "离线预演：将执行会员日任务、抽奖及红包合成/提取")
            return
        index = self.request("/commonPost/~memberNonactivity~memberDayIndexService~index", {"inviteUserId": ""})
        if not self.ok(index):
            message = clean_message(index.get("errorMessage"))
            status = "skipped" if "没有资格" in message else "failed"
            self.result(status, f"会员日不可执行：{message}")
            return
        obj = index.get("obj") or {}
        if obj.get("canReceiveInviteAward"):
            invite_reward = self.request(
                "/commonPost/~memberNonactivity~memberDayIndexService~receiveInviteAward",
                {"inviteUserId": ""},
            )
            self.result(
                "success" if self.ok(invite_reward) else "failed",
                "会员日邀请奖励" + ("领取成功" if self.ok(invite_reward) else "领取失败"),
            )
        for number in range(int(obj.get("lotteryNum", 0))):
            lottery = self.request("/commonPost/~memberNonactivity~memberDayLotteryService~lottery", {})
            self.result("success" if self.ok(lottery) else "failed", f"会员日第{number + 1}次抽奖" + ("成功" if self.ok(lottery) else "失败"))
        tasks = self.request("/commonPost/~memberNonactivity~activityTaskService~taskList", {"activityCode": "MEMBER_DAY", "channelType": "MINI_PROGRAM"})
        if not self.ok(tasks) or not isinstance(tasks.get("obj"), list):
            self.result("failed", "会员日任务查询失败")
        else:
            for task in tasks["obj"]:
                self.member_task(task)
        self.member_packets()

    def member_task(self, task: dict) -> None:
        name = clean_message(task.get("taskName", "未命名任务"))
        task_type = task.get("taskType")
        if task_type in SKIP_MEMBER_TYPES:
            self.result("skipped", f"会员日任务需真实消费/邀请，已跳过：{name}")
            return
        if task.get("status") == 1:
            repeats = 0
        elif task.get("status") == 2:
            repeats = max(0, int(task.get("restFinishTime", 0)))
        else:
            self.result("already", f"会员日任务无需执行：{name}")
            return
        code = task.get("taskCode") or task_type
        for _ in range(repeats):
            done = self.request("/commonPost/~memberEs~taskRecord~finishTask", {"taskCode": code})
            if not self.ok(done):
                self.result("failed", f"会员日任务失败：{name}")
                return
            self.result("success", f"会员日任务完成：{name}")
        reward = self.request("/commonPost/~memberNonactivity~activityTaskService~fetchMixTaskReward", {"taskType": task_type, "activityCode": "MEMBER_DAY", "channelType": "MINI_PROGRAM"})
        self.result("success" if self.ok(reward) else "failed", f"会员日奖励{'领取成功' if self.ok(reward) else '领取失败'}：{name}")

    def member_packets(self) -> None:
        route = "/commonPost/~memberNonactivity~memberDayPacketService~redPacketStatus"
        status = self.request(route, {})
        if not self.ok(status):
            self.result("failed", "会员日红包状态查询失败")
            return
        packet_map = {int(p["level"]): int(p["count"]) for p in (status.get("obj") or {}).get("packetList", [])}
        for level in range(1, 8):
            while packet_map.get(level, 0) >= 2:
                merged = self.request("/commonPost/~memberNonactivity~memberDayPacketService~redPacketMerge", {"level": level, "num": 2})
                if not self.ok(merged):
                    self.result("failed", f"会员日{level}级红包合成失败")
                    break
                packet_map[level] -= 2
                packet_map[level + 1] = packet_map.get(level + 1, 0) + 1
                self.result("success", f"会员日{level}级红包合成成功")
        if packet_map.get(8, 0) > 0:
            drawn = self.request("/commonPost/~memberNonactivity~memberDayPacketService~redPacketDraw", {"level": "8"})
            self.result("success" if self.ok(drawn) else "failed", "会员日8级红包" + ("提取成功" if self.ok(drawn) else "提取失败"))
        else:
            self.result("skipped", "会员日暂无8级红包可提取")

    @staticmethod
    def device_id() -> str:
        chars = "abcdef0123456789"
        return "".join(random.choice(chars) if c == "x" else c for c in "xxxxxxxx-xxxx-xxxx")

    def run(self) -> bool:
        print(f"\n--- {self.label} ---")
        print(f"[{self.label}] [1/4] 登录验证")
        if not self.login():
            return False
        print(f"[{self.label}] [2/4] 每日签到与积分任务")
        self.daily_sign()
        self.point_tasks()
        print(f"[{self.label}] [3/4] 丰蜜任务")
        self.honey_tasks()
        print(f"[{self.label}] [4/4] 会员日任务")
        self.member_day()
        return self.counts.failed == 0

    def finish(self) -> None:
        elapsed = round(time.monotonic() - self.started, 2)
        self.log(f"账号统计：总任务{self.counts.total}，成功{self.counts.success}，已完成{self.counts.already}，跳过{self.counts.skipped}，失败{self.counts.failed}，耗时{elapsed}秒")


def notify(title: str, body: str) -> str:
    if not enabled("QINGLONG_NOTIFY", True):
        print("⚠️ 通知已由QINGLONG_NOTIFY关闭")
        return "disabled"
    candidates: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        candidates.append(Path(custom) / "notify.py")
    candidates += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    try:
        from notify import send
        send(title, body)
        print("✅ 通知发送成功")
        return "sent"
    except Exception:
        pass
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(title, body)
            print("✅ 通知发送成功")
            return "sent"
        except Exception as exc:
            print(f"⚠️ 通知发送失败：{clean_message(exc)}")
            return "failed"
    print("⚠️ 未找到Qinglong通知模块，任务退出码不受影响")
    return "unavailable"


def parse_accounts(raw: str) -> List[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def main() -> int:
    started_at = now_text()
    timer = time.monotonic()
    dry_run = enabled("SFSU_DRY_RUN")
    coupon = enabled("SF_AUTO_COUPON")
    accounts = parse_accounts(os.getenv("sfsyUrl", ""))
    mode = "DRY-RUN（完全断网）" if dry_run else "LIVE"
    print(f"======== {NAME} ========")
    print(f"开始时间：{started_at}")
    print(f"运行模式：{mode}")
    print(f"账号数量：{len(accounts)}")
    print(f"安全设置：生活特权领券={'启用' if coupon else '关闭'}")

    total = Counts()
    successes = 0
    failures = 0
    config_error = False
    if not accounts:
        print("❌ 配置错误：缺少sfsyUrl；请按文档每行配置一个完整登录URL")
        config_error = True
    elif requests is None and not dry_run:
        print("❌ 运行依赖缺失：请安装requests")
        config_error = True
    else:
        delay_max_raw = os.getenv("SF_RANDOM_DELAY_MAX", "0").strip() or "0"
        try:
            delay_max = max(0, min(int(delay_max_raw), 86400))
        except ValueError:
            print("❌ 配置错误：SF_RANDOM_DELAY_MAX必须是0至86400的整数")
            delay_max = 0
            config_error = True
        if delay_max and not dry_run and not config_error:
            delay = random.randint(0, delay_max)
            print(f"⏳ 随机延迟：{delay}秒")
            time.sleep(delay)
        if not config_error:
            for number, credential in enumerate(accounts, 1):
                account = Account(credential, number, dry_run, coupon)
                ok = account.run()
                account.finish()
                total.merge(account.counts)
                successes += int(ok)
                failures += int(not ok)

    if config_error:
        final_status, business_code = "configuration-error", 2
        failures = len(accounts) or 1
    elif failures:
        final_status, business_code = ("partial-failure" if successes else "failure"), 1
    else:
        final_status, business_code = ("dry-run" if dry_run else "success"), 0

    duration = round(time.monotonic() - timer, 2)
    body = f"模式：{mode}\n账号总数：{len(accounts)}\n成功：{successes}\n失败：{failures}\n状态：{final_status}"
    notification = notify(NAME, body)
    finished_at = now_text()
    print("\n======== 任务统计 ========")
    print(f"账号结果：总计{len(accounts)}，成功{successes}，失败{failures}")
    print(f"子任务结果：总计{total.total}，成功{total.success}，已完成{total.already}，跳过{total.skipped}，失败{total.failed}")
    print(f"通知状态：{notification}")
    print(f"总耗时：{duration}秒")
    print(f"完成时间：{finished_at}")
    print(f"最终状态：{final_status}")
    summary = {
        "task": "sfsu", "status": final_status, "mode": "dry-run" if dry_run else "live",
        "accounts": {"total": len(accounts), "success": successes, "failed": failures},
        "steps": total.data(), "notification": notification, "durationSeconds": duration,
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return business_code


if __name__ == "__main__":
    sys.exit(main())
