#!/usr/bin/env python3
# name: Zippo会员中心
# cron: 56 0 * * *
# SPDX-License-Identifier: MIT
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# 上游作者：Rookie-wb-WH，来源：Rookie-wb-WH/ql_scripts，zippo.py
# 上游未附单独版权声明；保留作者归属，以 task.json 的 MIT 授权维护。
"""Zippo会员中心，Python 3.9 及以上，仅使用标准库。

登录微信小程序 Zippo会员中心，使用自己的抓包工具获取
wx-center.zippo.com.cn 请求头 authorization 的完整值（保留 Bearer 等前缀）。
zippoCookie：每个非空行一个账号；不再支持旧 # 分隔多账号。
ZIPPO_TASKS：逗号分隔 points,sign,goods,favorite,unfavorite,share,comment,invite；
默认 points,sign。goods 查询原分类7的前两页商品；收藏随机选其中一个商品。
unfavorite 必须同时选择 favorite，明确授权收藏后取消收藏。
share 仅记录一次分享任务并领取奖励，不发布自由文本。
comment 仅提交用户明确配置的 ZIPPO_COMMENT_STAR（1至5）与
ZIPPO_COMMENT_TAG（必须在官方候选标签中），最多评价一个未评价商品并领取奖励。
不随机编造评价、不发布自由文本。invite 必须提供 ZIPPO_INTRODUCER，
只使用用户自己的推荐码，不从远程获取；接口没有可核实回显时报告失败。
ZIPPO_DRY_RUN=1 完全断网，只核验配置和执行计划，不代表实际业务成功。
QINGLONG_NOTIFY=0 关闭通知；默认通过青龙 notify.py 发送脱敏汇总。
通知不可用或失败不会改变业务退出码。预演中只生成通知摘要，不加载通知模块或发送网络通知。
"""

import datetime
import importlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Zippo会员中心"
BASE = "https://wx-center.zippo.com.cn/api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 "
      "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
      "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x6309092b) XWEB/8555")
ALLOWED = {"points", "sign", "goods", "favorite", "unfavorite", "share", "comment", "invite"}


class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(text):
    print("[{}] {}".format(stamp(), text), flush=True)


def enabled(name):
    return os.getenv(name, "0").strip().lower() in {"1", "true", "yes", "on"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝重定向，保护账号凭据")


class Client:
    def __init__(self, credential):
        self.credential = credential
        self.opener = urllib.request.build_opener(NoRedirect())
        self.identities = set()

    def request(self, path, method="GET", data=None, params=None, environment="x-environment", version=71):
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"authorization": self.credential, "content-type": "application/json;charset=UTF-8",
                   "referer": "https://servicewechat.com/wxaa75ffd8c2d75da7/{}/page-frame.html".format(version),
                   "user-agent": UA, "x-app-id": "zippo", "x-environment": environment,
                   "x-platform": "wxmp", "x-platform-env": "release", "x-platform-id": "wxaa75ffd8c2d75da7"}
        body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(262145)
                if not 200 <= response.status < 300 or len(raw) > 262144:
                    raise TaskError("HTTP状态异常或响应过大")
            value = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError("HTTP请求失败，状态 {}".format(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络连接失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("响应不是有效JSON") from None
        if not isinstance(value, dict):
            raise TaskError("业务响应结构不符")
        # 上游以 code 字段作为错误标记，没有可支持的新业务码规则。
        if "code" in value or value.get("success") is False or value.get("error"):
            raise TaskError("接口返回业务错误，未输出原始响应")
        for key in ("nickname", "nickName", "username", "displayName", "publicUid"):
            identity = value.get(key)
            if isinstance(identity, (str, int)) and not isinstance(identity, bool):
                text = str(identity)
                if text and text not in self.identities and self.credential not in text:
                    self.identities.add(text)
                    log("官方账号身份 {}：{}".format(key, json.dumps(identity, ensure_ascii=False)))
        return value

    def reward(self, mission):
        r = self.request("/missions/{}/rewards".format(mission), "POST", {"id": mission},
                         version=72 if mission == 5 else 71)
        if "points" not in r or not number(r.get("rewardValue")):
            raise TaskError("奖励未获得可核实的业务成功字段")
        log("✅ 奖励领取成功，积分增加 {}".format(r["rewardValue"]))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def goods(client):
    items = []
    for page in (1, 2):
        r = client.request("/goods/search", "POST", {"page": page, "perPage": 20,
                           "catalogIds": [7], "q": "", "sort": "", "properties": "", "priceRange": []})
        if not number(r.get("total")) or not isinstance(r.get("list"), list):
            raise TaskError("商品查询返回字段不符")
        for item in r["list"]:
            if not isinstance(item, dict) or not isinstance(item.get("skus"), list):
                raise TaskError("商品数据结构异常")
            if item.get("id") is not None and item["skus"] and isinstance(item["skus"][0], dict):
                sku = item["skus"][0].get("id")
                if sku is not None:
                    items.append((item["id"], sku))
        log("✅ 商品查询第 {} 页成功，可用商品 {} 个".format(page, len(items)))
    return items


def action(client, task, cache, settings):
    if task == "points":
        r = client.request("/users/points", environment="")
        if not number(r.get("balance")):
            raise TaskError("积分查询未返回有效余额")
        log("✅ 当前用户积分：{}".format(r["balance"]))
    elif task == "sign":
        r = client.request("/daily-signin", "POST", {}, environment="")
        rewards = r.get("rewards")
        if not isinstance(rewards, list) or not rewards or not all(
                isinstance(x, dict) and number(x.get("count")) for x in rewards):
            raise TaskError("签到未返回有效奖励；不能确认已签到")
        log("✅ 签到成功，奖励积分 {}".format(sum(x["count"] for x in rewards)))
    elif task == "goods":
        cache["items"] = goods(client)
    elif task in {"favorite", "comment"}:
        if "items" not in cache:
            cache["items"] = goods(client)
        if not cache["items"]:
            raise TaskError("无可用商品，未执行变更")
        if task == "favorite":
            _, sku = random.choice(cache["items"])
            r = client.request("/favorites", "POST", {"targetType": "sku", "targetId": sku, "favorited": True}, version=72)
            if r.get("favorited") is not True:
                raise TaskError("收藏未得到成功确认")
            cache["favorite"] = sku
            log("✅ 收藏成功")
            client.reward(5)
        else:
            for item, sku in cache["items"]:
                r = client.request("/item-rating/info", params={"itemId": item, "skuId": sku})
                if not isinstance(r.get("chooseTags"), list) or not isinstance(r.get("cfg"), dict):
                    raise TaskError("评价资格响应字段不符")
                if r["chooseTags"]:
                    continue
                if settings["tag"] not in r["cfg"].get("tags", []):
                    raise TaskError("所配置评价标签不在官方候选中")
                posted = client.request("/item-rating/submit", "POST", {"itemId": item, "skuId": sku,
                                        "star": settings["star"], "chooseTags": [settings["tag"]]})
                if posted.get("chooseTags") != [settings["tag"]]:
                    raise TaskError("评价提交未得到标签确认")
                log("✅ 用户指定标签评价成功")
                client.reward(4)
                return "success"
            log("☑️ 查询确认所有候选商品已有评价")
            return "alreadyComplete"
    elif task == "unfavorite":
        if "favorite" not in cache:
            raise TaskError("本轮没有确认收藏的商品，禁止取消收藏")
        r = client.request("/favorites", "POST", {"targetType": "sku", "targetId": cache["favorite"], "favorited": False}, version=72)
        if r.get("favorited") is not False:
            raise TaskError("取消收藏未得到确认")
        log("✅ 已按显式选择取消本轮收藏")
    elif task == "share":
        client.request("/missions/records", "POST", {"code": "share"}, environment="")
        # 上游记录接口仅以无错误判断；最终必须由奖励响应确认，不能将空响应当成功。
        client.reward(6)
        log("✅ 分享记录及奖励成功；没有发布文本")
    elif task == "invite":
        r = client.request("/users/trace", "POST", {"introducer": settings["introducer"]})
        if r.get("introducer") != settings["introducer"]:
            raise TaskError("推荐人接口没有可核实回显，绑定结果不确定；请人工核对")
        log("✅ 用户指定推荐人绑定得到回显确认")
    return "success"


def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        return "已关闭"
    if dry:
        log("⏭️ 断网预演：通知汇总已生成，不加载或调用通知模块")
        return "预演仅生成汇总"
    body = "状态：{}；账号总数：{}；成功：{}；失败：{}；模式：{}".format(
        summary["status"], summary["accounts"], summary["succeeded"], summary["failed"], summary["mode"])
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--qinglong-notify", body],
                       timeout=20, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "已发送"
    except Exception:
        log("⚠️ 通知不可用或发送失败，保留业务退出码")
        return "发送失败或不可用"


def deliver_notification(body):
    try:
        try:
            module = importlib.import_module("notify")
        except ImportError:
            paths = []
            if os.getenv("QINGLONG_NOTIFY_DIR"):
                paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
            paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise ImportError("通知模块不可用")
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        return 0
    except Exception:
        return 1


def main():
    start = time.monotonic()
    dry = enabled("ZIPPO_DRY_RUN")
    accounts = [s.strip() for s in os.getenv("zippoCookie", "").splitlines() if s.strip()]
    summary = {"accounts": len(accounts), "succeeded": 0, "failed": 0,
               "mode": "dry-run" if dry else "live", "status": "failure", "accountResults": []}
    log("========== {} ==========".format(TITLE))
    log("开始时间：{}；模式：{}；账号数：{}".format(datetime.datetime.now().isoformat(timespec="seconds"), summary["mode"], len(accounts)))
    config_error = False
    try:
        tasks = {s.strip() for s in os.getenv("ZIPPO_TASKS", "points,sign").split(",") if s.strip()}
        if not tasks or tasks - ALLOWED:
            raise TaskError("ZIPPO_TASKS 含未知任务或为空")
        if not accounts:
            raise TaskError("缺少 zippoCookie，每行一个账号")
        if "unfavorite" in tasks and "favorite" not in tasks:
            raise TaskError("unfavorite 必须同时选择 favorite")
        settings = {"tag": os.getenv("ZIPPO_COMMENT_TAG", "").strip(),
                    "introducer": os.getenv("ZIPPO_INTRODUCER", "").strip()}
        if "comment" in tasks:
            try:
                settings["star"] = int(os.getenv("ZIPPO_COMMENT_STAR", ""))
            except ValueError:
                raise TaskError("评价需明确配置 ZIPPO_COMMENT_STAR（1至5）") from None
            if not 1 <= settings["star"] <= 5 or not settings["tag"]:
                raise TaskError("评价需有效星级和官方标签 ZIPPO_COMMENT_TAG")
        if "invite" in tasks and not settings["introducer"]:
            raise TaskError("绑定推荐人需显式配置 ZIPPO_INTRODUCER")
        order = [t for t in ("points", "sign", "goods", "favorite", "unfavorite", "share", "comment", "invite") if t in tasks]
        for index, credential in enumerate(accounts, 1):
            account_start = time.monotonic()
            stats = {"index": index, "total": len(order), "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
            invalid = "#" in credential or any(ord(c) < 32 or ord(c) > 126 for c in credential)
            client = None if dry or invalid else Client(credential)
            cache = {}
            log("---------- 账号 {} ----------".format(index))
            for stage, task in enumerate(order, 1):
                stage_start = time.monotonic()
                log("账号 {} 阶段 {}/{}：{} 开始".format(index, stage, len(order), task))
                try:
                    if invalid:
                        raise TaskError("凭据格式异常；不支持旧 # 分隔多账号，请改为换行")
                    if dry:
                        log("⏭️ DRY_RUN_OK：配置已核验，计划执行 {}；不联网、不变更账号".format(task))
                        result = "skipped"
                    else:
                        result = action(client, task, cache, settings)
                    stats[result] += 1
                except Exception as exc:
                    stats["failure"] += 1
                    log("❌ {}".format(str(exc) if isinstance(exc, TaskError) else "内部处理异常，未输出敏感异常内容"))
                log("阶段 {} 结束，耗时 {:.2f} 秒".format(stage, time.monotonic() - stage_start))
            stats["seconds"] = round(time.monotonic() - account_start, 2)
            summary["accountResults"].append(stats)
            summary["failed" if stats["failure"] else "succeeded"] += 1
            log("账号 {index} 统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failure}，耗时 {seconds} 秒".format(**stats))
    except TaskError as exc:
        config_error = True
        summary["failed"] = len(accounts)
        log("❌ 配置错误：{}".format(exc))
    summary["status"] = ("configuration-error" if config_error else
                         "partial-failure" if summary["failed"] and summary["succeeded"] else
                         "failure" if summary["failed"] else "dry-run" if dry else "success")
    summary["notification"] = notify(summary, dry)
    summary["seconds"] = round(time.monotonic() - start, 2)
    summary["finishedAt"] = datetime.datetime.now().isoformat(timespec="seconds")
    log("----------------------------------------")
    log("任务统计：账号 {}，成功 {}，失败 {}；子任务成功 {}，已完成 {}，跳过 {}，失败 {}".format(
        summary["accounts"], summary["succeeded"], summary["failed"],
        *(sum(s[k] for s in summary["accountResults"]) for k in ("success", "alreadyComplete", "skipped", "failure"))))
    log("完成时间：{}；总耗时 {} 秒；通知：{}；最终状态：{}".format(summary["finishedAt"], summary["seconds"], summary["notification"], summary["status"]))
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 1 if config_error or summary["failed"] else 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--qinglong-notify":
        sys.exit(deliver_notification(sys.argv[2]))
    sys.exit(main())
