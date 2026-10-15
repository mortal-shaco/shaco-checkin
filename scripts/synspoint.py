#!/usr/bin/env python3
# name: 所有女生会员服务中心积分版
# cron: 16 8,12 * * *
# SPDX-License-Identifier: MIT
# 原作者及来源：Rookie-wb-WH/ql_scripts，synspoint.py
# 来源提交：08e5c06461c4a0112ea3735f48fe671734bb7707
"""
原始说明（保留）：
vx小程序 -- 所有女生会员服务中心 积分版
抓包域名 7.wawo.cc 下的authorization 只需要填写 bearer 后的数据
export synshd='authorization1#authorization2" 多账号使用 # 隔开
cron: 16 8,12 * * *

维护说明：Python 3.9+，仅标准库。synshd 保留变量名，改为每个非空行一个
账号的 bearer 后凭据，也接受完整 Bearer 前缀；不再使用 # 分隔账号。
登录微信小程序“所有女生会员服务中心”，在本人授权的网络调试工具中获取
7.wawo.cc 请求的 Authorization，凭据失效后重新登录获取。不要公开凭据。
默认运行用户信息、积分、签到、浏览商城及最终积分查询。
SYNSPOINT_APPOINTMENT=1 显式开启原上播预约后取消流程；活动 ID 默认 818，
商品默认从原作者列表随机选取。可设置 SYNSPOINT_ACTIVITY_ID、SYNSPOINT_GOODS_ID。
仅为真实需要的预约开启该功能，旧活动可能失效；取消仅在本次预约成功后执行。
SYNSPOINT_DRY_RUN=1 完全断网预演（通知也仅模拟，不调用通知模块）。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。可用 QINGLONG_NOTIFY_DIR 指定
青龙通知文件目录；通知失败不影响业务退出码。无已验证成功的业务响应不会算成功。

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
import urllib.request

TITLE = "所有女生会员服务中心积分版"
BASE = "https://7.wawo.cc"
DISABLED = {"0", "false", "no", "off"}
GOODS = [68976, 68977, 68824, 68825, 68857, 68947, 68948, 68990, 68515, 68717, 68479, 68495, 69040, 69041, 69042, 68059, 68587, 68135, 67400, 67405, 68659, 67420, 68711, 68436, 68910, 68911, 68963, 68774, 68804, 68814, 68818, 68821, 68854, 68855, 68885, 68639, 68651, 68962, 68665, 68695, 67292, 67813, 67814, 68599, 67862, 68632, 68944, 68954, 68961, 68672, 68677, 68681, 68689, 68739, 68740, 68741]  # 原作者商品列表


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


def flag(name, default="0"):
    value = os.getenv(name, default).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in DISABLED:
        return False
    raise ValueError("开关必须填写 1/0、true/false、yes/no 或 on/off")


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError("拒绝接口重定向，防止凭据外发")


class Client:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, payload=None, form=False):
        body = None
        if payload is not None:
            if form:
                from urllib.parse import urlencode
                body = urlencode(payload).encode()
            else:
                body = json.dumps(payload, separators=(",", ":")).encode()
        # 原源码签到及浏览任务用 requests.post(data=dict)，是表单编码；
        # 预约及取消用 data=json.dumps(dict)，是 JSON。保留其实际请求编码。
        headers = {
            "authorization": "bearer " + self.token,
            "referer": "https://servicewechat.com/wx7d1403fe84339669/744/page-frame.html",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/8447",
            "content-type": "application/json",
        }
        req = urllib.request.Request(BASE + path, data=body, headers=headers,
                                     method="GET" if payload is None else "POST")
        try:
            with self.opener.open(req, timeout=15) as res:
                if res.status != 200:
                    raise TaskError("HTTP 状态异常")
                raw = res.read(262145)
            if len(raw) > 262144:
                raise TaskError("接口响应超出大小限制")
            result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError(f"HTTP 请求失败（状态 {exc.code}）") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络请求失败或超时") from None
        except (ValueError, UnicodeError):
            raise TaskError("接口响应不是有效 JSON") from None
        if not isinstance(result, dict) or result.get("code") != "000":
            # 不输出服务端 message，以免回显凭据或个人信息。
            raise TaskError("接口未返回业务成功码 000；请检查登录状态或活动有效性")
        return result.get("data")


def safe_identity(value, tokens):
    if not isinstance(value, str) or not value:
        raise TaskError("用户信息缺少有效昵称")
    # 官方非敏感昵称原样展示；凭据、手机号或多行注入不进入日志。
    import re
    if any(token and token in value for token in tokens) or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
        return "身份包含敏感内容，已隐藏"
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return "身份含控制字符，已隐藏"
    return value


def notify(summary, dry):
    try:
        enabled = os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in DISABLED
        if not enabled:
            return "已关闭"
        if dry:
            log("⏭️ 通知：断网预演，仅模拟脱敏总结发送")
            return "预演模拟"
        body = (f"状态：{summary['status']}；账号总数 {summary['accounts']}，"
                f"成功 {summary['success']}，失败 {summary['failed']}；"
                f"子任务成功 {summary['steps']['success']}，失败 {summary['steps']['failed']}，"
                f"跳过 {summary['steps']['skipped']}")
        file = None
        try:
            spec = importlib.util.find_spec("notify")
            if spec and spec.origin:
                file = spec.origin
        except (ImportError, ValueError):
            pass
        if not file:
            for directory in [os.getenv("QINGLONG_NOTIFY_DIR", ""),
                              "/ql/data/scripts", "/ql/scripts"]:
                if directory and (Path(directory) / "notify.py").is_file():
                    file = str(Path(directory) / "notify.py")
                    break
        if file:
            # 通知模块仅在有超时的子进程加载，防止导入或发送无限阻塞。
            code = ("import importlib.util,sys; "
                    "from pathlib import Path; sys.path.insert(0,str(Path(sys.argv[1]).parent)); "
                    "s=importlib.util.spec_from_file_location('notify',sys.argv[1]); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "m.send(sys.argv[2],sys.argv[3])")
            completed = subprocess.run([sys.executable, "-c", code, file, TITLE, body],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=30, check=False)
            return "已发送" if completed.returncode == 0 else "发送失败"
        for directory in [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]:
            if directory and (Path(directory) / "sendNotify.js").is_file():
                code = "require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]).catch(()=>process.exit(1))"
                done = subprocess.run(["node", "-e", code, str(Path(directory) / "sendNotify.js"), TITLE, body],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      timeout=30, check=False)
                return "已发送" if done.returncode == 0 else "发送失败"
        return "通知模块不可用"
    except Exception:
        return "发送失败或不可用"


def main():
    start = time.monotonic()
    started = stamp()
    dry = os.getenv("SYNSPOINT_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}
    lines = [line.strip() for line in os.getenv("synshd", "").splitlines() if line.strip()]
    tokens = ["" if line.lower() == "bearer" else line[7:].strip() if line.lower().startswith("bearer ") else line for line in lines]
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "accounts": len(tokens),
               "success": 0, "failed": 0, "status": "failure", "startedAt": started,
               "steps": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0},
               "accountResults": []}
    print(f"========== {TITLE} ==========")
    log(f"开始时间：{started}；模式：{'断网预演' if dry else '正式运行'}；账号数：{len(tokens)}")
    config_error = False
    try:
        appointment = flag("SYNSPOINT_APPOINTMENT")
        flag("SYNSPOINT_DRY_RUN")
        activity = int(os.getenv("SYNSPOINT_ACTIVITY_ID", "818"))
        goods_value = os.getenv("SYNSPOINT_GOODS_ID", "").strip()
        goods = int(goods_value) if goods_value else None
        if activity <= 0 or (goods is not None and goods <= 0):
            raise ValueError()
        if not tokens:
            raise ValueError()
    except ValueError:
        config_error = True
        log("❌ 配置错误：请检查 synshd、开关及活动／商品正整数参数")
    if not config_error:
        for index, token in enumerate(tokens, 1):
            begin = time.monotonic()
            stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            client = Client(token)
            log(f"账号 {index} 开始")
            authorized = False
            booked = False
            goods_id = goods or random.choice(GOODS)

            def stage(number, name, action=None, skip=None):
                tick = time.monotonic()
                stats["total"] += 1
                log(f"账号 {index} 阶段 {number}：{name}")
                if skip:
                    stats["skipped"] += 1
                    log(f"⏭️ {skip}；耗时 {time.monotonic() - tick:.2f} 秒")
                    return False
                if dry:
                    stats["skipped"] += 1
                    log(f"⏭️ DRY_RUN：模拟 {name}，未发起请求；耗时 {time.monotonic() - tick:.2f} 秒")
                    return True
                try:
                    detail = action()
                    stats["success"] += 1
                    log(f"✅ {name}：业务已验证成功{('；' + detail) if detail else ''}；耗时 {time.monotonic() - tick:.2f} 秒")
                    return True
                except TaskError as exc:
                    stats["failed"] += 1
                    log(f"❌ {name}：{exc}；耗时 {time.monotonic() - tick:.2f} 秒")
                    return False
                except Exception:
                    stats["failed"] += 1
                    log(f"❌ {name}：响应结构异常或执行失败；耗时 {time.monotonic() - tick:.2f} 秒")
                    return False

            def info():
                data = client.request("/api/account/wx/member/info/own")
                if not isinstance(data, dict):
                    raise TaskError("用户信息缺少 data 对象")
                return "昵称：" + safe_identity(data.get("nickName"), tokens)

            def assets():
                data = client.request("/api/account/wx/member/assets")
                if not isinstance(data, dict) or isinstance(data.get("score"), bool):
                    raise TaskError("积分响应字段缺失")
                value = data.get("score")
                if not isinstance(value, (int, float, str)):
                    raise TaskError("积分响应字段异常")
                import decimal
                try:
                    number = decimal.Decimal(str(value))
                    if not number.is_finite() or number < 0:
                        raise ValueError()
                except (decimal.InvalidOperation, ValueError):
                    raise TaskError("积分响应字段异常") from None
                return "积分：" + str(number)

            valid = bool(token) and not any(ord(c) < 32 or ord(c) == 127 for c in token) and "#" not in token
            if valid:
                authorized = stage(1, "用户信息", info)
            else:
                stats["total"] += 1
                stats["failed"] += 1
                log(f"账号 {index} 阶段 1：用户信息；❌ 凭据格式错误；每行一个账号，不使用 # 分隔；耗时 0.00 秒")
            guard = None if authorized else "用户信息未验证，停止该账号的后续接口请求"
            stage(2, "初始积分查询", assets, guard)
            stage(3, "签到任务", lambda: (client.request("/api/operate/wx/record/signIn", {}, form=True), "")[1], guard)
            booked = stage(4, "上播预约", lambda: (client.request("/api/live/wx/strategy/appointment", {"activityId": activity, "goodsId": goods_id, "type": 1}), "")[1], guard or (None if appointment else "预约功能默认关闭；显式开启后运行"))
            if booked and not dry:
                time.sleep(random.uniform(3, 5))
            stage(5, "取消本次上播预约", lambda: (client.request("/api/live/wx/strategy/cancelAppointment", {"activityId": activity, "goodsIds": [goods_id], "type": 1}), "")[1], None if booked else "本次未成功预约，不执行取消")
            stage(6, "浏览会员商城", lambda: (client.request("/api/operate/wx/rewards/task/done?taskId=38", {"taskId": 38}, form=True), "")[1], guard)
            if not dry and authorized:
                time.sleep(random.uniform(1, 3))
            stage(7, "最终积分查询", assets, guard)
            ok = stats["failed"] == 0 and authorized
            summary["success" if ok else "failed"] += 1
            summary["accountResults"].append({"account": index, "status": "dry-run" if dry and ok else "success" if ok else "failure", "steps": stats})
            for key in stats:
                summary["steps"][key] += stats[key]
            log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {time.monotonic() - begin:.2f} 秒")
    if config_error:
        summary["status"] = "configuration-error"
        summary["failed"] = len(tokens)
    elif summary["failed"]:
        summary["status"] = "partial-failure" if summary["success"] else "failure"
    else:
        summary["status"] = "dry-run" if dry else "success"
    exit_code = 1 if config_error or summary["failed"] else 0
    summary["notification"] = notify(summary, dry)
    summary["finishedAt"] = stamp()
    summary["elapsedSeconds"] = round(time.monotonic() - start, 2)
    summary["exitCode"] = exit_code
    print("----------------------------------------")
    log(f"账号统计：总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}")
    s = summary["steps"]
    log(f"子任务统计：总数 {s['total']}，成功 {s['success']}，已完成 {s['alreadyComplete']}，跳过 {s['skipped']}，失败 {s['failed']}")
    log(f"总耗时：{summary['elapsedSeconds']} 秒；完成时间：{summary['finishedAt']}；通知：{summary['notification']}")
    log(f"最终状态：{summary['status']}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
