#!/usr/bin/env python3
# name: 爱奇艺账号与抽奖维护
# cron: 15 9 * * *
"""独立维护版，来源 Sitoi/dailycheckin dailycheckin/iqiyi/main.py。

IQIYI_COOKIE：每行一个完整 Cookie，必需 P00001；普通抽奖需 P00003。
登录爱奇艺官网，在浏览器开发者工具的网络面板复制本人请求的 Cookie。
默认仅查询；IQIYI_ACTIONS 可用逗号选择 info,draw,shake,platinum,grant,level。
grant 会领取浏览/预约任务次数，level 会领取升级权益，必须主动选择。
IQIYI_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。

上游许可：MIT；上游源码未附单独版权声明。保留项目署名 Sitoi/dailycheckin。
MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from uuid import uuid4


TITLE = "爱奇艺账号与抽奖维护"
DISABLED = {"0", "false", "no", "off"}
LABELS = {"info": "VIP 信息查询", "draw": "普通抽奖", "shake": "每日摇一摇",
          "platinum": "白金抽奖", "grant": "领取浏览及预约任务次数", "level": "V7 星钻权益领取"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def safe_text(value, secrets):
    """只展示已选择的业务字段，移除凭据和手机号。"""
    text = str(value).replace("\n", " ").replace("\r", " ")
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已脱敏]")
            text = text.replace(urllib.parse.quote(secret, safe=""), "[已脱敏]")
    text = re.sub(r"(?i)(cookie|token|p0000[123]|session|deviceid|qyid|__dfp)\s*[:=]\s*[^\s;]+", r"\1=[已脱敏]", text)
    return re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)[:300]


def parse_cookie(line):
    pairs = {}
    for part in line.split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            pairs[key] = value
    if not pairs.get("P00001"):
        raise TaskError("Cookie 缺少 P00001")
    return pairs


class Client:
    def __init__(self, cookie, timeout):
        self.cookie = cookie
        self.timeout = timeout
        # 禁止重定向，避免凭据被转发至其他主机。
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, url, params, post=False):
        if os.getenv("IQIYI_DRY_RUN", "0").lower() not in DISABLED:
            raise TaskError("预演禁止网络请求")
        encoded = urllib.parse.urlencode(params)
        req = urllib.request.Request(url if post else url + "?" + encoded,
                                     data=encoded.encode() if post else None,
                                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = response.read(1048577)
            if len(payload) > 1048576:
                raise TaskError("响应超过大小限制")
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise TaskError("接口响应不是对象")
            return result
        except TaskError:
            raise
        except Exception:
            # 异常常含带凭据的 URL，不能打印原始异常。
            raise TaskError("请求失败：网络、HTTP 或 JSON 异常") from None

    def api(self, url, params, post=False):
        result = self.request(url, params, post)
        if result.get("code") != "A00000":
            raise TaskError("业务响应未确认成功")
        data = result.get("data")
        return data if isinstance(data, dict) else {}

    def info(self):
        data = self.api("https://serv.vip.iqiyi.com/vipgrowth/query.action", {"P00001": self.cookie["P00001"]})
        keys = {"level": "VIP 等级", "growthvalue": "当前成长", "todayGrowthValue": "今日成长",
                "distance": "升级还需", "deadline": "VIP 到期"}
        if not any(key in data for key in keys):
            raise TaskError("账号信息缺少业务字段")
        secrets = list(self.cookie.values())
        for key in ("nickname", "user_name", "username", "displayName", "uid"):
            if data.get(key) is not None:
                identity_secrets = [value for name, value in self.cookie.items() if name != "P00003"] if key == "uid" else secrets
                log(f"账号身份 {key}：{safe_text(data[key], identity_secrets)}")
        return "；".join(f"{label}：{safe_text(data[key], secrets)}" for key, label in keys.items() if key in data)

    def draw_call(self, query):
        if not self.cookie.get("P00003"):
            raise TaskError("普通抽奖需要同一 Cookie 中的 P00003")
        params = {"app_k": "b398b8ccbaeacca840073a7ee9b7e7e6", "app_v": "11.6.5", "platform_id": 10,
                  "dev_os": "8.0.0", "dev_ua": "FRD-AL10", "net_sts": 1,
                  "qyid": self.cookie.get("QC005") or "2655b332a116d2247fac3dd66a5285011102",
                  "psp_uid": self.cookie["P00003"], "psp_cki": self.cookie["P00001"], "psp_status": 3,
                  "secure_v": 1, "secure_p": "GPhone", "req_sn": round(time.time() * 1000)}
        if query:
            params["lottery_chance"] = 1
        result = self.request("https://iface2.iqiyi.com/aggregate/3.0/lottery_activity", params)
        # 上游约定无 code 表示成功，但还必须有可校验的业务字段。
        if result.get("code"):
            raise TaskError("普通抽奖业务失败")
        chance = result.get("daysurpluschance")
        if isinstance(chance, bool) or not re.fullmatch(r"\d+", str(chance)):
            raise TaskError("普通抽奖次数字段无效")
        if not query and not isinstance(result.get("awardName"), str):
            raise TaskError("普通抽奖缺少奖励字段")
        return int(chance), result.get("awardName", "")

    def draw(self, limit):
        chance, _ = self.draw_call(True)
        if chance > limit:
            raise TaskError("抽奖次数超过安全上限；请核实后调整 IQIYI_MAX_DRAWS")
        if chance == 0:
            return "already", "接口确认抽奖机会不足"
        for number in range(chance):
            _, award = self.draw_call(False)
            log(f"普通抽奖 {number + 1}/{chance}：{safe_text(award, list(self.cookie.values()))}")
            if number + 1 < chance:
                time.sleep(3)
        return "success", f"完成 {chance} 次普通抽奖"

    def shake(self, limit):
        for number in range(limit):
            params = {"P00001": self.cookie["P00001"], "deviceID": str(uuid4()), "version": "15.3.0",
                      "platform": str(uuid4())[:16], "lotteryType": "0", "actCode": "0k9GkUcjqqj4tne8",
                      "extendParams": json.dumps({"appIds": "iqiyi_pt_vip_iphone_video_autorenew_12m_348yuan_v2",
                                                   "supportSk2Identity": True, "testMode": "0",
                                                   "iosSystemVersion": "17.4", "bundleId": "com.qiyi.iphone"})}
            result = self.request("https://act.vip.iqiyi.com/shake-api/lottery", params)
            if result.get("msg") == "抽奖次数用完" and result.get("code") != "A00000":
                return ("already" if number == 0 else "success"), f"接口确认次数用完，本轮完成 {number} 次"
            if result.get("code") != "A00000" or not isinstance(result.get("data"), dict) or not result["data"].get("title"):
                raise TaskError("摇一摇未确认奖励或业务失败")
            log(f"摇一摇 {number + 1}：{safe_text(result['data']['title'], list(self.cookie.values()))}")
            if number + 1 < limit:
                time.sleep(3)
        raise TaskError("摇一摇达到安全上限，尚未确认次数耗尽")

    def grant(self):
        for number, code in enumerate(("browseWeb", "browseWeb", "bookingMovie"), 1):
            self.api("https://pcell.iqiyi.com/lotto/giveTimes", {"actCode": "bcf9d354bc9f677c", "timesCode": code,
                                                             "P00001": self.cookie["P00001"]})
            log(f"领取次数 {number}/3：业务成功（{code}）")
        return "success", "已确认三次次数领取"

    def platinum(self):
        for number in range(5):
            data = self.api("https://pcell.iqiyi.com/lotto/lottery", {"actCode": "bcf9d354bc9f677c", "P00001": self.cookie["P00001"]})
            if not isinstance(data.get("giftName"), str) or not data["giftName"]:
                raise TaskError("白金抽奖缺少奖励字段")
            log(f"白金抽奖 {number + 1}/5：{safe_text(data['giftName'], list(self.cookie.values()))}")
        return "success", "已确认五次白金抽奖结果"

    def level(self):
        result = self.request("https://act.vip.iqiyi.com/level-right/receive",
                              {"code": "k8sj74234c683f", "P00001": self.cookie["P00001"]}, True)
        if result.get("code") != "A00000":
            raise TaskError("星钻权益领取未确认成功；请核实会员资格")
        return "success", "接口确认星钻权益领取成功"


def notify(summary, dry):
    if os.getenv("QINGLONG_NOTIFY", "1").lower() in DISABLED:
        return "已关闭"
    if dry:
        log("通知预演：" + summary)
        return "预演已模拟（未联网）"
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    try:
        module = importlib.import_module("notify")
    except Exception:
        module = None
    for path in paths:
        if module is not None and callable(getattr(module, "send", None)):
            break
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                module = None
    if module is None or not callable(getattr(module, "send", None)):
        return "通知不可用，保留业务退出码"
    try:
        # 通知模块输出可能包含推送凭据，避免转发其输出或异常。
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            module.send(TITLE, summary)
        return "已发送"
    except Exception:
        return "通知失败，保留业务退出码"


def main():
    started = time.monotonic()
    dry = os.getenv("IQIYI_DRY_RUN", "0").lower() not in DISABLED
    lines = [line.strip() for line in os.getenv("IQIYI_COOKIE", "").splitlines() if line.strip()]
    log(f"========== {TITLE} ==========")
    log(f"开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；模式：{'断网预演' if dry else '实时执行'}；账号数：{len(lines)}")
    totals = {"success": 0, "already": 0, "skipped": 0, "failed": 0}
    good = bad = 0
    config_error = False
    try:
        actions = list(dict.fromkeys(item.strip() for item in os.getenv("IQIYI_ACTIONS", "info").split(",")))
        if not actions or any(item not in LABELS for item in actions):
            raise TaskError("IQIYI_ACTIONS 包含空值或不支持的动作")
        # 无论输入顺序如何，先领取次数再进行白金抽奖。
        if "grant" in actions and "platinum" in actions:
            actions.remove("grant")
            actions.insert(actions.index("platinum"), "grant")
        # 上游在操作前后查询成长，保留操作后的最新状态展示。
        if "info" in actions and any(action != "info" for action in actions) and actions[-1] != "info":
            actions.append("info")
        timeout = float(os.getenv("IQIYI_TIMEOUT", "15"))
        limit = int(os.getenv("IQIYI_MAX_DRAWS", "20"))
        if not 1 <= timeout <= 60 or not 1 <= limit <= 100:
            raise TaskError("超时应为 1～60 秒，抽奖上限应为 1～100")
        if not lines:
            raise TaskError("未配置必需变量 IQIYI_COOKIE")
    except (ValueError, TaskError) as error:
        log("❌ 配置错误：" + (str(error) if isinstance(error, TaskError) else "数值参数格式无效"))
        config_error = True
        actions = []
    if not config_error:
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            counts = {"success": 0, "already": 0, "skipped": 0, "failed": 0}
            try:
                cookie = parse_cookie(line)
                if "draw" in actions and not cookie.get("P00003"):
                    raise TaskError("普通抽奖需要 Cookie 中的 P00003")
                client = Client(cookie, timeout)
            except TaskError as error:
                log(f"账号 {index} ❌ 配置错误：{error}")
                counts["failed"] = 1
                counts["skipped"] = len(actions)
                client = None
            if client:
                for number, action in enumerate(actions, 1):
                    step_start = time.monotonic()
                    log(f"账号 {index} 阶段 {number}/{len(actions)}：{LABELS[action]}")
                    try:
                        if dry:
                            status, message = "skipped", "预演参数校验通过；不请求接口，不改变账号状态"
                        elif action == "info":
                            status, message = "success", client.info()
                        elif action in ("draw", "shake"):
                            status, message = getattr(client, action)(limit)
                        else:
                            status, message = getattr(client, action)()
                    except Exception as error:
                        status = "failed"
                        message = str(error) if isinstance(error, TaskError) else "执行异常（详情已抑制，防止凭据泄漏）"
                    counts[status] += 1
                    icon = {"success": "✅", "already": "☑️", "skipped": "⏭️", "failed": "❌"}[status]
                    log(f"账号 {index} {icon} {LABELS[action]}：{message}；耗时 {time.monotonic() - step_start:.2f} 秒")
            bad += int(counts["failed"] > 0)
            good += int(counts["failed"] == 0)
            for key in totals:
                totals[key] += counts[key]
            log(f"账号 {index} 统计：总任务 {sum(counts.values())}，成功 {counts['success']}，已完成 {counts['already']}，跳过 {counts['skipped']}，失败 {counts['failed']}；耗时 {time.monotonic() - account_start:.2f} 秒")
    exit_code = 1 if config_error or bad else 0
    status = "configuration-error" if config_error else ("partial-failure" if bad and good else "failure" if bad else "dry-run" if dry else "success")
    body = f"账号总数 {len(lines)}，成功 {'（预演校验）' if dry else ''}{good}，失败 {bad}；状态 {status}；子任务成功 {totals['success']}，已完成 {totals['already']}，跳过 {totals['skipped']}，失败 {totals['failed']}"
    delivery = notify(body, dry)
    log("----------------------------------------")
    log(body)
    log(f"完成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；总耗时 {time.monotonic() - started:.2f} 秒；通知：{delivery}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps({"task": TITLE, "mode": "dry-run" if dry else "live", "status": status,
                                         "accounts": len(lines), "successfulAccounts": good, "failedAccounts": bad,
                                         "steps": totals, "notification": delivery, "exitCode": exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
