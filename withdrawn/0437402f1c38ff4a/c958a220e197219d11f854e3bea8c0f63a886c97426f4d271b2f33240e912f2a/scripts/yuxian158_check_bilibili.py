# -*- coding: utf-8 -*-
# name: 哔哩哔哩每日任务
# cron: 2 0 * * *
# publish: scripts/bilibili_daily.py
# SPDX-License-Identifier: MIT
# 上游: yuxian158/check dailycheckin_scripts/ck_bilibili.py
# 提交: 723c834f121ff4eef2dec7afe521071a7efff1a9，许可: MIT
# 原任务名称: new Env('哔哩哔哩每日任务');
"""哔哩哔哩每日任务独立维护版（Python 3.9+，仅使用标准库）。

功能盘点：登录及公开身份核验、漫画签到、直播签到、每日经验核验、
直播金银瓜子余额查询；可选观看上报、分享计数、投币/点赞、大会员权益、
漫画大会员福利与指定用户充电。观看、分享、投币、权益与充电均为显式开关，
避免默认产生额外副作用。分享接口只登记分享计数，不发布文本，因此不适用
随机文本提供方策略。

必填 BILIBILI_COOKIE：登录网页后，从浏览器开发者工具 Network 中本人发往
api.bilibili.com 的请求复制完整 Cookie 值（不要包含 ``Cookie:`` 标题）。
每行一个账号，必须含 SESSDATA 和 bili_jct；Cookie 字段只按首个等号切分。
完整参数、开关和副作用说明见 contract.json。本脚本不依赖私有 utils.check。

MIT License
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
        _ql_notify_identities = ('0437402f1c38ff4a', 'scripts/yuxian158_check_bilibili.py', 'yuxian158_check_bilibili.py', 'yuxian158_check_bilibili')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime as dt
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


TITLE = "哔哩哔哩每日任务"
CATALOG_ID = "0437402f1c38ff4a"
PUBLISH_PATH = "scripts/bilibili_daily.py"
API = "https://api.bilibili.com"
MANGA = "https://manga.bilibili.com"
LIVE = "https://api.live.bilibili.com"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class TaskError(Exception):
    """可安全展示、且不包含凭据的任务错误。"""


def log(message):
    print(f"[{dt.datetime.now():%H:%M:%S}] {message}", flush=True)


def boolean_value(name, default=False):
    value = os.getenv(name, "1" if default else "0").strip().lower()
    if value not in TRUE_VALUES | FALSE_VALUES:
        raise TaskError(f"{name} 必须为布尔值")
    return value in TRUE_VALUES


def integer_value(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise TaskError(f"{name} 必须为整数") from None
    if not low <= value <= high:
        raise TaskError(f"{name} 超出允许范围 {low} 至 {high}")
    return value


def configuration():
    return {
        "manga": boolean_value("BILIBILI_MANGA_SIGN", True),
        "live": boolean_value("BILIBILI_LIVE_SIGN", True),
        "watch": boolean_value("BILIBILI_WATCH", False),
        "share": boolean_value("BILIBILI_SHARE", False),
        "like": boolean_value("BILIBILI_SELECT_LIKE", False),
        "vip": boolean_value("BILIBILI_VIP_RECEIVE", False),
        "vip_manga": boolean_value("BILIBILI_VIP_MANGA", False),
        "coins": integer_value("BILIBILI_COIN_NUM", 0, 0, 5),
        "coin_type": integer_value("BILIBILI_COIN_TYPE", 1, 0, 1),
        "charge": integer_value("BILIBILI_ELEC_NUM", 0, 0, 10000),
        "charge_uid": integer_value("BILIBILI_ELEC_UID", 0, 0, 10**15),
        "aid": integer_value("BILIBILI_AID", 0, 0, 10**15),
        "cid": integer_value("BILIBILI_CID", 0, 0, 10**15),
        "progress": integer_value("BILIBILI_PROGRESS", 300, 1, 86400),
        "region": integer_value("BILIBILI_REGION", 1, 1, 10000),
        "timeout": integer_value("BILIBILI_TIMEOUT", 15, 1, 60),
    }


def parse_cookie(line):
    if any(ord(char) < 32 or ord(char) == 127 for char in line):
        raise TaskError("Cookie 含非法控制字符")
    result = {}
    for item in line.split(";"):
        item = item.strip()
        if not item:
            continue
        key, delimiter, value = item.partition("=")
        if not delimiter or not key.strip() or not value.strip():
            raise TaskError("Cookie 格式错误，应为分号分隔的名称=值")
        result[key.strip()] = value.strip()
    if not result.get("SESSDATA") or not result.get("bili_jct"):
        raise TaskError("Cookie 缺少 SESSDATA 或 bili_jct")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, cookies, timeout, dry_run):
        self.cookies = cookies
        self.timeout = timeout
        self.dry_run = dry_run
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, base, path, params=None, form=None, payload=None):
        if self.dry_run:
            raise TaskError("预演禁止 HTTP 请求")
        if base not in (API, MANGA, LIVE) or not path.startswith("/"):
            raise TaskError("请求地址不在允许列表")
        url = base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com/",
            "Cookie": "; ".join(f"{key}={value}" for key, value in self.cookies.items()),
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        body = None
        if form is not None:
            body = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        try:
            request = urllib.request.Request(url, data=body, headers=headers)
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise TaskError("接口响应超过大小限制")
                result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 请求失败（状态 {exc.code}）") from None
        except Exception:
            raise TaskError("接口网络、超时或响应解析失败") from None
        if not isinstance(result, dict) or type(result.get("code")) is not int:
            raise TaskError("接口响应缺少业务状态码")
        return result

    def get(self, path, params=None, base=API):
        return self.request(base, path, params=params)

    def post(self, path, form=None, payload=None, base=API):
        return self.request(base, path, form=form, payload=payload)


def checked(result):
    if result["code"] != 0:
        raise TaskError(f"接口业务失败（代码 {result['code']}）")
    return result.get("data")


def mapping(data):
    if not isinstance(data, dict):
        raise TaskError("接口数据结构不符合预期")
    return data


def number(data, key):
    value = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise TaskError(f"接口缺少有效数值字段 {key}")
    return value


class Account:
    def __init__(self, index, cookie, config, dry_run):
        self.index = index
        self.cookie = cookie
        self.config = config
        self.dry_run = dry_run
        self.stats = {"total": 0, "success": 0, "already_complete": 0,
                      "skipped": 0, "failed": 0}
        self.started = time.monotonic()
        self.client = None
        self.nav = None
        self.videos = None

    def stage(self, title, action=None, enabled=True):
        self.stats["total"] += 1
        stage_number = self.stats["total"]
        started = time.monotonic()
        log(f"账号 {self.index} 阶段 {stage_number}：{title}")
        try:
            if not enabled:
                status, detail = "skipped", "未启用"
            elif self.dry_run:
                status, detail = "skipped", "DRY_RUN：已检查配置，不发请求或改变账号"
            else:
                status, detail = action()
            self.stats[status] += 1
            icon = {"success": "✅", "already_complete": "☑️", "skipped": "⏭️"}[status]
            log(f"{icon} {detail}（阶段耗时 {time.monotonic() - started:.2f} 秒）")
            return True
        except TaskError as exc:
            detail = str(exc)
        except Exception:
            detail = "执行异常或响应字段不符合预期"
        self.stats["failed"] += 1
        log(f"❌ {detail}（阶段耗时 {time.monotonic() - started:.2f} 秒）")
        return False

    def setup(self):
        cookies = parse_cookie(self.cookie)
        if self.config["charge"] and not self.config["charge_uid"]:
            raise TaskError("启用充电必须设置 BILIBILI_ELEC_UID")
        self.client = Client(cookies, self.config["timeout"], self.dry_run)

    def login(self):
        data = mapping(checked(self.client.get("/x/web-interface/nav")))
        if data.get("isLogin") is not True:
            raise TaskError("账号未登录或 Cookie 已失效")
        self.nav = data
        log(f"账号 {self.index} 昵称：{data.get('uname', '未返回')}；公开 UID：{data.get('mid', '未返回')}")
        return "success", "登录验证通过"

    def sign(self, manga):
        if manga:
            result = self.client.post(
                "/twirp/activity.v1.Activity/ClockIn",
                form={"platform": "android"}, base=MANGA,
            )
            if result["code"] != 0 and result.get("msg") == "clockin clockin is duplicate":
                return "already_complete", "漫画今日已签到"
        else:
            result = self.client.get("/xlive/web-ucenter/v1/sign/DoSign", base=LIVE)
            if result["code"] == 1011040:
                return "already_complete", "直播今日已签到"
        checked(result)
        return "success", ("漫画" if manga else "直播") + "签到成功"

    def get_videos(self):
        if self.videos is not None:
            return self.videos
        config = self.config
        if config["aid"]:
            data = mapping(checked(self.client.get("/x/web-interface/view", {"aid": config["aid"]})))
            self.videos = [{"aid": config["aid"], "cid": config["cid"] or data.get("cid")}]
        else:
            data = mapping(checked(self.client.get(
                "/x/web-interface/dynamic/region", {"ps": 6, "rid": config["region"]},
            )))
            entries = data.get("archives")
            if not isinstance(entries, list):
                raise TaskError("分区视频列表格式无效")
            self.videos = [item for item in entries if isinstance(item, dict) and item.get("aid")]
        if not self.videos:
            raise TaskError("没有可用视频，未执行后续动作")
        return self.videos

    def watch(self):
        video = self.get_videos()[0]
        cid = self.config["cid"] or video.get("cid")
        if not cid:
            data = mapping(checked(self.client.get("/x/web-interface/view", {"aid": video["aid"]})))
            cid = data.get("cid")
        if not cid:
            raise TaskError("没有有效视频 CID，未上报")
        checked(self.client.post("/x/v2/history/report", form={
            "aid": video["aid"], "cid": cid, "progres": self.config["progress"],
            "csrf": self.client.cookies["bili_jct"],
        }))
        return "success", f"观看进度上报成功：{self.config['progress']} 秒"

    def share(self):
        checked(self.client.post("/x/web-interface/share/add", form={
            "aid": self.get_videos()[0]["aid"], "csrf": self.client.cookies["bili_jct"],
        }))
        return "success", "视频分享计数提交成功（不发布文本）"

    def reward(self):
        return mapping(checked(self.client.get("/x/member/web/exp/reward")))

    def coin(self):
        reward = self.reward()
        completed = int(number(reward, "coins") // 10)
        target = self.config["coins"]
        if completed >= target:
            return "already_complete", f"今日投币目标已完成：{completed}/{target}"
        if number(self.nav, "money") < target - completed:
            raise TaskError("硬币余额不足，未执行投币")
        videos = list(self.get_videos())
        if self.config["coin_type"] == 1:
            data = mapping(checked(self.client.get("/x/relation/followings", {
                "vmid": self.nav["mid"], "pn": 1, "ps": 50,
                "order": "desc", "order_type": "attention",
            })))
            followings = data.get("list")
            if not isinstance(followings, list):
                raise TaskError("关注列表格式无效")
            for user in followings:
                if not isinstance(user, dict) or not user.get("mid"):
                    continue
                data = mapping(checked(self.client.get("/x/space/arc/search", {
                    "mid": user["mid"], "pn": 1, "ps": 100, "tid": 0,
                    "order": "pubdate", "keyword": "",
                })))
                entries = mapping(data.get("list")).get("vlist")
                if not isinstance(entries, list):
                    raise TaskError("关注投稿列表格式无效")
                videos.extend(item for item in entries if isinstance(item, dict) and item.get("aid"))
        seen = set()
        for video in reversed(videos):
            aid = video["aid"]
            if aid in seen:
                continue
            seen.add(aid)
            result = self.client.post("/x/web-interface/coin/add", form={
                "aid": aid, "multiply": 1, "select_like": int(self.config["like"]),
                "cross_domain": "true", "csrf": self.client.cookies["bili_jct"],
            })
            if result["code"] == 34005:
                log("⏭️ 视频投币达到上限，尝试下一条")
                continue
            checked(result)
            completed += 1
            log(f"✅ 已投币：今日 {completed}/{target}")
            if completed >= target:
                return "success", f"今日投币目标完成：{completed}/{target}"
        raise TaskError(f"可投视频不足，今日投币未达目标：{completed}/{target}")

    def privilege(self, kind):
        if not self.nav.get("vipType"):
            return "skipped", "非大会员账号，跳过权益领取"
        if kind == "manga":
            checked(self.client.post(
                "/twirp/user.v1.User/GetVipReward", payload={"reason_id": 1}, base=MANGA,
            ))
        else:
            checked(self.client.post("/x/vip/privilege/receive", form={
                "type": kind, "csrf": self.client.cookies["bili_jct"],
            }))
        return "success", "大会员权益领取成功"

    def charge(self):
        uid = self.config["charge_uid"]
        checked(self.client.post("/x/ugcpay/trade/elec/pay/quick", form={
            "elec_num": self.config["charge"], "up_mid": uid,
            "otype": "up", "oid": uid, "csrf": self.client.cookies["bili_jct"],
        }))
        return "success", f"充电成功：电池数量 {self.config['charge']}"

    def final_info(self):
        nav = mapping(checked(self.client.get("/x/web-interface/nav")))
        if nav.get("isLogin") is not True:
            raise TaskError("最终登录状态验证失败")
        reward = self.reward()
        experience = number(mapping(nav.get("level_info")), "current_exp")
        coin_experience = number(reward, "coins")
        for field in ("login", "watch", "share"):
            if field not in reward or reward[field] not in (True, False, 0, 1):
                raise TaskError(f"经验接口缺少有效字段 {field}")
        if not reward["login"]:
            raise TaskError("每日登录经验尚未确认")
        if self.config["watch"] and not reward["watch"]:
            raise TaskError("观看经验尚未确认")
        if self.config["share"] and not reward["share"]:
            raise TaskError("分享经验尚未确认")
        if coin_experience < self.config["coins"] * 10:
            raise TaskError("投币经验尚未确认")
        today = sum(5 for key in ("login", "watch", "share") if reward[key]) + coin_experience
        days = max(0, int((28800 - experience + today - 1) // today)) if today else "无法估算"
        log(f"今日经验：{today}；当前经验：{experience}；到六级预计天数：{days}；硬币：{number(nav, 'money')}")
        return "success", "每日经验及已启用动作验证通过"

    def balance(self):
        data = mapping(checked(self.client.get("/pay/v1/Exchange/getStatus", base=LIVE)))
        log(f"直播余额：硬币 {number(data, 'coin')}；金瓜子 {number(data, 'gold')}；银瓜子 {number(data, 'silver')}")
        return "success", "直播余额查询成功"

    def run(self):
        self.stats["total"] += 1
        started = time.monotonic()
        log(f"账号 {self.index} 阶段 1：参数校验")
        try:
            self.setup()
            self.stats["success"] += 1
            log(f"✅ Cookie 结构校验通过（阶段耗时 {time.monotonic() - started:.2f} 秒）")
        except TaskError as exc:
            self.stats["failed"] += 1
            log(f"❌ {exc}（阶段耗时 {time.monotonic() - started:.2f} 秒）")
            return self.finish()
        if not self.stage("账号登录与身份", self.login):
            return self.finish()
        config = self.config
        self.stage("漫画签到", lambda: self.sign(True), config["manga"])
        self.stage("直播签到", lambda: self.sign(False), config["live"])
        self.stage("视频观看进度上报", self.watch, config["watch"])
        self.stage("视频分享计数", self.share, config["share"])
        self.stage("投币及可选点赞", self.coin, config["coins"] > 0)
        self.stage("大会员 B 币券", lambda: self.privilege(1), config["vip"])
        self.stage("大会员优惠券", lambda: self.privilege(2), config["vip"])
        self.stage("漫画大会员福利", lambda: self.privilege("manga"), config["vip_manga"])
        self.stage("指定用户充电", self.charge, config["charge"] > 0)
        self.stage("账号与经验核验", self.final_info)
        self.stage("直播金银瓜子余额", self.balance)
        return self.finish()

    def finish(self):
        self.stats["seconds"] = round(time.monotonic() - self.started, 2)
        log(
            f"账号 {self.index} 统计：总任务 {self.stats['total']}，成功 {self.stats['success']}，"
            f"已完成 {self.stats['already_complete']}，跳过 {self.stats['skipped']}，"
            f"失败 {self.stats['failed']}，耗时 {self.stats['seconds']} 秒"
        )
        return {"index": self.index, **self.stats}


# 通知模块在隔离子进程中运行；不转发其输出。预演时审计钩子禁止网络。
NOTIFY_RUNNER = r'''
import importlib.util, os, socket, subprocess, sys
if sys.argv[3] == "1":
    def deny(*args, **kwargs):
        raise RuntimeError("dry-run network disabled")
    def audit(event, args):
        if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn", "os.system")):
            deny()
    sys.addaudithook(audit)
    socket.socket.sendto = deny
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    subprocess.Popen = deny
    os.system = deny
    os.posix_spawn = deny
    os.posix_spawnp = deny
path = sys.argv[1]
if path:
    spec = importlib.util.spec_from_file_location("notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send("哔哩哔哩每日任务", sys.argv[2])
'''


def notification_selected():
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ["QINGLONG_NOTIFY_SCRIPTS"]
    if not raw.strip():
        return False
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    identities = {CATALOG_ID, PUBLISH_PATH, Path(PUBLISH_PATH).name, Path(__file__).name}
    return any(selector == "*" or any(fnmatch.fnmatch(identity, selector) for identity in identities)
               for selector in selectors)


def notify(body, dry_run):
    switch_value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch_value in FALSE_VALUES:
        return "全局关闭"
    if switch_value not in TRUE_VALUES | {"auto"}:
        return "全局开关值无效，未发送"
    if not notification_selected():
        return "脚本未被通知选择器选中"
    candidates = [""]
    directory = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        candidates.append(str(Path(directory) / "notify.py"))
    candidates.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    for path in candidates:
        if path and not Path(path).is_file():
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-c", NOTIFY_RUNNER, path, body, "1" if dry_run else "0"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False,
            )
            if result.returncode == 0:
                return "预演本地通知已调用（网络禁用）" if dry_run else "已发送"
        except Exception:
            continue
    return "预演通知不可用或网络已阻止" if dry_run else "通知不可用或发送失败"


def main():
    started = time.monotonic()
    start_time = dt.datetime.now().isoformat(timespec="seconds")
    dry_run_value = os.getenv("BILIBILI_DRY_RUN", "0").strip().lower()
    dry_run = dry_run_value in TRUE_VALUES
    if dry_run_value not in TRUE_VALUES | FALSE_VALUES:
        # 用户试图配置预演但写错值时，仍按断网边界收尾，避免误触真实接口。
        dry_run = True
        initial_error = "BILIBILI_DRY_RUN 必须为布尔值"
    else:
        initial_error = None
    account_lines = [line.strip() for line in os.getenv("BILIBILI_COOKIE", "").splitlines() if line.strip()]
    results = []
    config_error = False
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{start_time}；模式：{'断网预演' if dry_run else '正式执行'}；账号数：{len(account_lines)}")
    try:
        if initial_error:
            raise TaskError(initial_error)
        if not account_lines:
            raise TaskError("缺少必填 BILIBILI_COOKIE，必须每行一个账号")
        config = configuration()
        for index, cookie in enumerate(account_lines, 1):
            results.append(Account(index, cookie, config, dry_run).run())
    except TaskError as exc:
        config_error = True
        log(f"❌ 配置错误：{exc}")
    except Exception:
        config_error = True
        log("❌ 未预期执行异常（详情已脱敏）")

    failed_accounts = sum(1 for result in results if result["failed"])
    if config_error:
        failed_accounts = len(account_lines)
    successful_accounts = len(results) - sum(1 for result in results if result["failed"])
    exit_code = 1 if config_error or failed_accounts else 0
    status = (
        "configuration-error" if config_error else
        "partial-failure" if failed_accounts and successful_accounts else
        "failure" if failed_accounts else
        "dry-run" if dry_run else "success"
    )
    body = (f"状态：{status}；账号总数：{len(account_lines)}；"
            f"成功数：{successful_accounts}；失败数：{failed_accounts}。")
    if dry_run:
        body += "断网预演仅校验配置，未验证真实业务。"
    notification = notify(body, dry_run)
    finish_time = dt.datetime.now().isoformat(timespec="seconds")
    totals = {
        key: sum(result[key] for result in results)
        for key in ("total", "success", "already_complete", "skipped", "failed")
    }
    summary = {
        "task": TITLE, "status": status, "dryRun": dry_run,
        "accounts": len(account_lines), "success": successful_accounts,
        "failed": failed_accounts, "configurationError": config_error,
        "accountResults": results, "notification": notification,
        "exitCode": exit_code, "startTime": start_time, "finishTime": finish_time,
        "seconds": round(time.monotonic() - started, 2), "publishPath": PUBLISH_PATH,
    }
    log("--------------------------------------------------")
    log(body)
    log(
        f"子任务统计：总数 {totals['total']}，成功 {totals['success']}，"
        f"已完成 {totals['already_complete']}，跳过 {totals['skipped']}，失败 {totals['failed']}"
    )
    log(f"完成时间：{finish_time}；总耗时：{summary['seconds']} 秒；通知：{notification}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
