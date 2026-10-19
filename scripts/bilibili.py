#!/usr/bin/env python3
# name: B站每日任务
# cron: 6 2 * * *
# new Env("B站每日任务")
# 来源: CN-Grace/QinglongScripts / Bilibili.py
# 上游版本: a40a2b080e0160bd8e0b0b807081115537b87153
# SPDX-License-Identifier: MIT
# License: MIT（任务提供的有效许可）；保留上游 Bilibili 每日任务署名。
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""独立 Bilibili 每日任务；配置获取和安全开关详见配套 contract.json。
BILIBILI_COOKIE 每个非空行一个完整 Cookie，保留字段值中的等号。
投币默认 0，点赞、分享和银瓜子兑换默认关闭；观看与漫画签到默认开启。
分享仅调用视频分享接口，不发布文字，不适用随机文本提供方。
"""
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
        _ql_notify_identities = ('ca4e1c75a27952c1', 'scripts/bilibili.py', 'bilibili.py', 'bilibili')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime as dt
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "B站每日任务"
TZ = dt.timezone(dt.timedelta(hours=8))
API = "https://api.bilibili.com"
LIVE = "https://api.live.bilibili.com"
MANGA = "https://manga.bilibili.com"
LIMIT = 2 * 1024 * 1024


class TaskError(Exception):
    pass


def stamp():
    return dt.datetime.now(TZ).strftime("%H:%M:%S")


def log(message):
    print(f"[{stamp()}] {message}", flush=True)


def flag(name, default=False):
    value = os.environ.get(name, "1" if default else "0").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise TaskError(f"{name} 必须是布尔开关")


def integer(name, default, low, high):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise TaskError(f"{name} 必须是整数") from None
    if not low <= value <= high:
        raise TaskError(f"{name} 超出允许范围 {low} 至 {high}")
    return value


def parse_cookie(line):
    if any(ord(c) < 32 or ord(c) == 127 for c in line):
        raise TaskError("Cookie 包含非法控制字符")
    fields = {}
    for field in line.split(";"):
        if not field.strip():
            continue
        key, sep, value = field.strip().partition("=")
        if not sep or not key or not value:
            raise TaskError("Cookie 格式错误，需提供完整请求 Cookie")
        fields[key] = value
    if not fields.get("SESSDATA") or not fields.get("bili_jct"):
        raise TaskError("Cookie 缺少 SESSDATA 或 bili_jct，请重新获取")
    return fields


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, fields, dry=False):
        self.fields = fields
        self.dry = dry
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, base, path, params=None, post=False, duplicate=False):
        if self.dry:
            raise TaskError("离线模式禁止 HTTP")
        if base not in {API, LIVE, MANGA} or not path.startswith("/"):
            raise TaskError("禁止访问未授权域名")
        params = dict(params or {})
        if post:
            params.setdefault("csrf", self.fields["bili_jct"])
        encoded = urllib.parse.urlencode(params).encode()
        url = base + path
        if not post and params:
            url += "?" + encoded.decode()
        req = urllib.request.Request(url, data=encoded if post else None, headers={
            "Cookie": "; ".join(f"{k}={v}" for k, v in self.fields.items()),
            "User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
            "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise TaskError("响应超过安全大小限制")
                result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 请求失败，状态码 {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络请求失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("响应不是有效 JSON") from None
        if not isinstance(result, dict) or type(result.get("code")) is not int:
            raise TaskError("响应缺少有效业务状态码")
        if duplicate and result.get("msg") == "clockin clockin is duplicate":
            return {"already": True}
        if result["code"] != 0:
            raise TaskError(f"接口业务失败，代码 {result['code']}")
        return result.get("data")

    def nav(self):
        data = self.call(API, "/x/web-interface/nav")
        if not isinstance(data, dict) or data.get("isLogin") is not True:
            raise TaskError("登录状态无效，请更新 Cookie")
        if type(data.get("mid")) is not int or data["mid"] <= 0 or not isinstance(data.get("level_info"), dict):
            raise TaskError("账号资料字段缺失")
        if type(data.get("money")) not in (int, float):
            raise TaskError("硬币余额字段异常")
        return data

    def exp(self):
        data = self.call(API, "/x/member/web/exp/log", {"jsonp": "jsonp"})
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            raise TaskError("经验记录结构异常")
        today = dt.datetime.now(TZ).strftime("%Y-%m-%d")
        entries = [x for x in data["list"] if isinstance(x, dict) and str(x.get("time", "")).split(" ")[0] == today]
        if any(type(x.get("delta")) not in (int, float) for x in entries):
            raise TaskError("经验记录数值异常")
        return entries

    def popular(self):
        for path, params in [("/x/web-interface/popular", {"pn": 1, "ps": 6}),
                             ("/x/web-interface/ranking/v2", {"rid": 1, "type": "all"})]:
            try:
                data = self.call(API, path, params)
                videos = data.get("list") if isinstance(data, dict) else None
                if not isinstance(videos, list) or not any(isinstance(v, dict) and v.get("aid") for v in videos):
                    raise TaskError("视频列表为空或结构异常")
                log("视频来源请求成功：" + ("热门" if "popular" in path else "排行榜"))
                return [v for v in videos if isinstance(v, dict) and v.get("aid")]
            except TaskError as exc:
                log(f"⚠️ 视频来源失败：{exc}，尝试下一来源")
        raise TaskError("热门和排行榜均未获得有效视频")

    def follow_videos(self, uid, needed):
        data = self.call(API, "/x/relation/followings", {
            "vmid": uid, "pn": 1, "ps": 50, "order": "desc", "order_type": "attention"})
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            raise TaskError("关注列表结构异常")
        videos = []
        for user in data["list"]:
            if not isinstance(user, dict) or not user.get("mid"):
                continue
            try:
                result = self.call(API, "/x/space/arc/search", {"mid": user["mid"], "pn": 1, "ps": 30, "tid": 0, "order": "pubdate", "keyword": ""})
                listing = result.get("list", {}).get("vlist") if isinstance(result, dict) else None
                if not isinstance(listing, list):
                    raise TaskError("投稿列表结构异常")
                videos.extend(v for v in listing[:2] if isinstance(v, dict) and v.get("aid"))
                log("关注 UP 主投稿读取成功")
            except TaskError as exc:
                log(f"⚠️ 投稿读取失败：{exc}，继续下一位 UP 主")
            if len(videos) >= needed:
                break
        return videos


def identity(value):
    # 官方非凭据昵称和公开 UID 按原值显示；去除日志控制字符。
    return "".join(c for c in str(value) if ord(c) >= 32 and ord(c) != 127)


def account(index, line, config, dry):
    started = time.monotonic()
    stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
    state = {}

    def stage(name, fn=None, enabled=True):
        stats["total"] += 1
        number = stats["total"]
        tick = time.monotonic()
        log(f"账号 {index} 阶段 {number}：{name} 开始")
        try:
            if not enabled:
                stats["skipped"] += 1
                log("⏭️ 未启用或前置条件未满足")
                return None
            if dry:
                stats["skipped"] += 1
                log("⏭️ DRY_RUN：离线检查通过，不请求、不变更账户")
                return None
            result = fn()
            already = isinstance(result, dict) and result.get("already") is True
            stats["alreadyComplete" if already else "success"] += 1
            log("☑️ 已完成" if already else "✅ 接口业务结果验证成功")
            return result
        except TaskError as exc:
            stats["failed"] += 1
            log(f"❌ {exc}")
        except Exception:
            stats["failed"] += 1
            log("❌ 返回字段异常或执行失败（已隐藏异常原文）")
        finally:
            log(f"账号 {index} 阶段 {number}：{name} 耗时 {time.monotonic() - tick:.2f} 秒")
        return None

    try:
        fields = parse_cookie(line)
        client = Client(fields, dry)
    except TaskError as exc:
        stats.update(total=1, failed=1)
        log(f"账号 {index} 配置失败：{exc}")
    else:
        nav = stage("验证登录及账号资料", client.nav)
        ready = dry or nav is not None
        if nav:
            log(f"账号 {index} 昵称：{identity(nav.get('uname', ''))}；UID：{identity(nav['mid'])}；硬币：{nav.get('money', 0)}")
        stage("漫画签到", lambda: client.call(MANGA, "/twirp/activity.v1.Activity/ClockIn", {"platform": "android"}, True, True), ready and config["manga"])
        videos = stage("热门视频与排行榜备选", client.popular, ready and (config["watch"] or config["share"] or config["coins"] > 0))
        entries = stage("今日经验记录", client.exp, ready)

        def coins():
            if entries is None or nav is None or videos is None:
                raise TaskError("无法核实已投币数、余额或视频来源，停止支出")
            done = sum(max(0, int(x["delta"] // 10)) for x in entries if x.get("reason") == "视频投币奖励")
            need = max(0, config["coins"] - done)
            log(f"今日已投币 {done}，目标 {config['coins']}，还需 {need}")
            if not need:
                return {"already": True}
            if not isinstance(nav.get("money"), (int, float)) or nav["money"] < need:
                raise TaskError("硬币余额不足，未完成投币目标")
            candidates = list(videos)
            if config["coin_type"] == 1:
                try:
                    following = client.follow_videos(nav["mid"], need)
                    candidates.extend(following)
                    if not following:
                        log("⚠️ 关注投稿为空，使用热门和排行榜候选")
                except TaskError as exc:
                    log(f"⚠️ 关注来源失败：{exc}，使用热门和排行榜候选")
            seen = set()
            for video in reversed(candidates):
                aid = video.get("aid")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                try:
                    client.call(API, "/x/web-interface/coin/add", {"aid": aid, "multiply": 1, "select_like": int(config["like"]), "cross_domain": "true"}, True)
                except TaskError as exc:
                    if str(exc) == "接口业务失败，代码 34005":
                        log("☑️ 此视频投币额度已满，继续下一视频")
                        continue
                    raise
                need -= 1
                log(f"✅ 已验证投币 1 个，剩余目标 {need}")
                if not need:
                    return {}
            raise TaskError("候选视频不足，投币目标未完成")

        stage("按目标投币（可选点赞）", coins, ready and config["coins"] > 0)

        def video_action(share=False):
            if not videos:
                raise TaskError("没有可用视频")
            video = videos[0]
            if share:
                return client.call(API, "/x/web-interface/share/add", {"aid": video["aid"]}, True)
            cid = video.get("cid")
            if not cid:
                detail = client.call(API, "/x/web-interface/view", {"aid": video["aid"]})
                cid = detail.get("cid") if isinstance(detail, dict) else None
            if not cid:
                raise TaskError("未获取到有效视频 cid")
            return client.call(API, "/x/v2/history/report", {"aid": video["aid"], "cid": cid, "progres": 300}, True)

        stage("上报视频观看进度 300 秒", video_action, ready and config["watch"])
        stage("分享视频", lambda: video_action(True), ready and config["share"])
        stage("银瓜子兑换硬币", lambda: client.call(LIVE, "/xlive/revenue/v1/wallet/silver2coin", {}, True), ready and config["silver"])

        def balances():
            data = client.call(LIVE, "/pay/v1/Exchange/getStatus")
            if not isinstance(data, dict) or any(type(data.get(k)) not in (int, float, str) for k in ("coin", "gold", "silver")):
                raise TaskError("直播余额结构异常")
            values = {k: float(data[k]) for k in ("coin", "gold", "silver")}
            log(f"直播硬币 {values['coin']}；金瓜子 {values['gold']}；银瓜子 {values['silver']}")
            return values

        stage("查询直播余额", balances, ready)

        def experience():
            fresh = client.nav()
            records = client.exp()
            current = fresh["level_info"].get("current_exp")
            if type(current) not in (int, float):
                raise TaskError("当前经验字段异常")
            today = sum(x["delta"] for x in records)
            days = math.ceil(max(0, 28800 - current) / today) if today > 0 else "未知"
            log(f"今日经验 {today}；当前经验 {current}；预计达到六级还需 {days} 天；硬币 {fresh.get('money', 0)}")
            return {"todayExp": today, "currentExp": current, "upgradeDays": days}

        state = stage("经验及升级天数统计", experience, ready) or {}
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['elapsedSeconds']} 秒")
    return {"index": index, "status": "failed" if stats["failed"] else ("dry-run" if dry else "success"), "statistics": stats, "experience": state}


def notify_summary(body, dry):
    value = os.environ.get("QINGLONG_NOTIFY", "1").strip().lower()
    if value in {"0", "false", "no", "off"}:
        return "已关闭"
    if dry:
        # 通知模块也可能联网；离线预演仅生成通知正文，不加载或调用传输。
        log("离线通知摘要：" + body)
        return "离线预演已生成摘要，未发送"
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            if os.environ.get("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                log("⚠️ 未找到青龙 notify.py；保留业务退出码")
                return "不可用"
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        return "已发送"
    except Exception:
        log("⚠️ 通知发送失败（隐藏异常原文）；保留业务退出码")
        return "失败"


def main():
    start = time.monotonic()
    started = dt.datetime.now(TZ).isoformat(timespec="seconds")
    log(f"========== {TITLE} ==========；开始时间 {started}")
    lines = [line.strip() for line in os.environ.get("BILIBILI_COOKIE", "").splitlines() if line.strip()]
    results = []
    dry = False
    config_error = False
    try:
        dry = flag("BILIBILI_DRY_RUN")
        log(f"运行模式：{'离线预演' if dry else '实际执行'}；账号数量：{len(lines)}")
        config = {
            "coins": integer("BILIBILI_COIN_NUM", 0, 0, 5),
            "coin_type": integer("BILIBILI_COIN_TYPE", 1, 1, 2),
            "manga": flag("BILIBILI_MANGA", True), "watch": flag("BILIBILI_WATCH", True),
            "share": flag("BILIBILI_SHARE"), "like": flag("BILIBILI_SELECT_LIKE"),
            "silver": flag("BILIBILI_SILVER2COIN"),
        }
        if not lines:
            raise TaskError("必须设置 BILIBILI_COOKIE，每个非空行一个账号")
        for index, line in enumerate(lines, 1):
            results.append(account(index, line, config, dry))
    except TaskError as exc:
        config_error = True
        log(f"❌ 配置错误：{exc}")
    failed = sum(r["status"] == "failed" for r in results)
    passed = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = "configuration-error" if config_error else ("partial-failure" if failed and passed else "failure" if failed else "dry-run" if dry else "success")
    totals = {k: sum(r["statistics"][k] for r in results) for k in ("total", "success", "alreadyComplete", "skipped", "failed")}
    body = f"状态 {status}；账号总数 {len(lines)}，成功/预演通过 {passed}，失败 {failed}；配置错误 {int(config_error)}；子任务 {json.dumps(totals, ensure_ascii=False)}"
    notification = notify_summary(body, dry)
    finish = dt.datetime.now(TZ).isoformat(timespec="seconds")
    log("----------------------------------------")
    log(body)
    log(f"总耗时 {time.monotonic() - start:.2f} 秒；完成时间 {finish}；通知状态 {notification}；最终状态 {status}")
    summary = {"task": TITLE, "status": status, "mode": "dry-run" if dry else "live", "accountCount": len(lines), "successCount": passed, "failureCount": failed, "configurationError": config_error, "statistics": totals, "accounts": results, "startedAt": started, "finishedAt": finish, "elapsedSeconds": round(time.monotonic() - start, 2), "notification": notification, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
