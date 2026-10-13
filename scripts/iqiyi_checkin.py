#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 爱奇艺签到
# cron: 5 10 * * *
# new Env('爱奇艺签到')
# 上游：deeplee/personal-scripts，iqiyi_checkin.py
# 来源提交：c8c7c0f4fd1802df86c32a86c26b5c26cfef5023
# 许可证：MIT；保留上游署名。上游文件未包含单独的版权声明。
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
"""
爱奇艺每日签到，Python 3 标准库独立运行。
IQIYI_COOKIES：每个非空行一个账号完整 Cookie；兼容 IQIYI_COOKIE。
浏览器登录 https://www.iqiyi.com 后，在开发者工具 Application/Cookies 中
获取自己账号的 P00001、P00003 和可选 __dfp，以分号组成一行。
P00001 是登录凭据，P00003 是用户编号；__dfp 取 @ 前段，不用于分隔账号。
默认执行 VIP 查询、自然月签到和积分签到。两类抽奖可能消耗抽奖机会，
仅在 IQIYI_LOTTERY=1、IQIYI_SHAKE=1 时分别执行。保留上游抽奖参数。
IQIYI_DRY_RUN=1 完全断网，只验证配置与请求构造，不代表业务成功。
QINGLONG_NOTIFY 默认 1；设为 0/false/no/off 关闭通知。
可用 QINGLONG_NOTIFY_DIR 指定青龙通知目录；兼容 PUSHPLUS_TOKEN、SENDKEY
作为青龙通知不可用时的可选通知后备。预演不调用任何通知渠道。
每日 10:05 运行。未提供 Cookie、任一账号或启用的步骤失败均非零退出。
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 社区接口固定签名密钥(爱奇艺客户端公开)
TASK_SIGN_KEY = "UKobMjDMsDoScuWOfp6F"   # 自然月签到
SCORE_SIGN_KEY = "DO58SzN6ip9nbJ4QkM8H"  # 网页积分签到

TASK_URL = "https://community.iqiyi.com/openApi/task/execute"
SCORE_URL = "https://community.iqiyi.com/openApi/score/add"
LOTTERY_URL = "https://iface2.iqiyi.com/aggregate/3.0/lottery_activity"
SHAKE_URL = "https://act.vip.iqiyi.com/shake-api/lottery"
VIP_URL = "https://serv.vip.iqiyi.com/vipgrowth/query.action"



DISABLED = {"0", "false", "no", "off"}

def enabled(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    if value not in {"1", "true", "yes", "on"} | DISABLED:
        raise ValueError("开关格式错误")
    return value not in DISABLED

class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 凭据只发送给原定 HTTPS 接口，不随重定向传递。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _http(url, method="GET", data=None, headers=None, timeout=15):
    if urllib.parse.urlsplit(url).scheme != "https":
        return -1, ""
    h = {"Accept": "application/json", "Accept-Language": "zh-CN,zh;q=0.9",
         "User-Agent": UA, "Referer": "https://www.iqiyi.com/",
         "Origin": "https://www.iqiyi.com"}
    h.update(headers or {})
    body = None
    if isinstance(data, dict):
        if h.get("Content-Type", "").startswith("application/json"):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        else:
            body = urllib.parse.urlencode(data).encode("utf-8")
    elif data is not None:
        body = data if isinstance(data, bytes) else data.encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    if enabled("IQIYI_DRY_RUN"):
        raise DryRunRequest()
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as resp:
            raw = resp.read(1048577)
            if len(raw) > 1048576:
                return -1, ""
            return resp.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        # 异常可能含带凭据的 URL，绝不输出异常文本。
        return -1, ""

def _json(txt):
    try:
        value = json.loads(txt)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None

def response(st, txt):
    if st != 200:
        return None, "网络请求失败" if st == -1 else "HTTP %s" % st
    value = _json(txt)
    if value is None:
        return None, "接口响应格式异常"
    return value, ""

def is_already(message):
    # 不把未知的“上限”“次数”等错误当作签到或抽奖成功。
    return isinstance(message, str) and message.strip() in {
        "今日已签到", "今天已签到", "已经签到", "已签到", "您今日已签到", "您今天已经签到过了"
    }

def public_value(value):
    text = str(value).replace("\r", " ").replace("\n", " ")
    for cookie in parse_accounts():
        for item in cookie.split(";"):
            if "=" in item:
                key, secret = item.strip().split("=", 1)
                if key != "P00003" and secret.strip():
                    text = text.replace(secret.strip(), "[凭据已隐藏]")
    for name in ("PUSHPLUS_TOKEN", "SENDKEY"):
        secret = os.environ.get(name, "").strip()
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    # 手机号不是允许展示的账号身份。
    return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)


def identity(data):
    for field in ("nickname", "username", "displayName", "uid", "userId"):
        value = data.get(field)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            print("[%s] 官方身份 %s: %s" % (time.strftime("%H:%M:%S"), field, public_value(value)))

def _md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _rand16():
    return "".join(random.choices(string.ascii_letters + string.digits, k=16))

def _ts13():
    return str(int(time.time() * 1000))

def _sign(params, key):
    """爱奇艺社区接口签名: 参数按 key 排序, | 拼接, 尾加密钥, md5"""
    s = "|".join("%s=%s" % (k, params[k]) for k in sorted(params))
    return _md5(s + "|" + key)

def parse_cookie(cookie_str):
    """提取 P00001 / P00003 / __dfp"""
    p00001 = p00003 = dfp = ""
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "P00001" and not p00001:
            p00001 = v
        elif k == "P00003" and not p00003:
            p00003 = v
        elif k == "__dfp" and not dfp:
            dfp = v.split("@")[0] if "@" in v else v
    return p00001, p00003, dfp

def task_sign(p00001, p00003):
    """自然月签到,返回 (ok, msg)"""
    qyid = _md5(_rand16())
    ts = _ts13()
    params = {
        "agentType": "1",
        "agentversion": "1.0",
        "appKey": "basic_pcw",
        "authCookie": p00001,
        "qyid": qyid,
        "task_code": "natural_month_sign",
        "timestamp": ts,
        "typeCode": "point",
        "userId": p00003,
    }
    sign = _sign(params, TASK_SIGN_KEY)
    url = TASK_URL + "?" + "&".join(
        "%s=%s" % (k, urllib.parse.quote(str(v), safe=""))
        for k, v in params.items()
    ) + "&sign=" + sign
    body = {
        "natural_month_sign": {
            "agentType": "1",
            "agentversion": "1",
            "authCookie": p00001,
            "qyid": qyid,
            "taskCode": "iQIYI_mofhr",
            "verticalCode": "iQIYI",
        }
    }
    hdrs = {"Content-Type": "application/json"}
    st, txt = _http(url, method="POST", data=body, headers=hdrs)
    d, error = response(st, txt)
    if d is None:
        return False, error
    if d.get("code") == "A00000":
        sub = d.get("data")
        if not isinstance(sub, dict):
            return False, "签到响应缺少业务结果"
        if sub.get("code") == "A0000":
            identity(sub)
            days = sub.get("signDays")
            return True, "签到成功" + ("，连签%d天" % days if type(days) is int else "")
        if is_already(sub.get("msg")):
            return True, "今日已签到"
    return False, "Cookie失效，请重新获取" if d.get("code") == "A00401" else "签到未获成功确认"

def score_sign(p00001, p00003, dfp):
    """网页积分签到,返回 (ok, msg)"""
    params = {
        "agenttype": "1",
        "agentversion": "0",
        "appKey": "basic_pca",
        "appver": "0",
        "authCookie": p00001,
        "channelCode": "sign_pcw",
        "dfp": dfp,
        "scoreType": "1",
        "srcplatform": "1",
        "typeCode": "point",
        "userId": p00003,
        "user_agent": UA,
        "verticalCode": "iQIYI",
    }
    sign = _sign(params, SCORE_SIGN_KEY)
    url = SCORE_URL + "?" + "&".join(
        "%s=%s" % (k, urllib.parse.quote(str(v), safe=""))
        for k, v in params.items()
    ) + "&sign=" + sign
    st, txt = _http(url)
    d, error = response(st, txt)
    if d is None:
        return False, error
    if d.get("code") == "A00000":
        data = d.get("data")
        if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
            if all(x.get("code") == "A0000" for x in data):
                for item in data:
                    identity(item)
                return True, "积分签到成功"
            if all(x.get("code") == "A0000" or is_already(x.get("message")) for x in data):
                return True, "今日已签到"
    return False, "Cookie失效，请重新获取" if d.get("code") == "A00401" else "积分签到未获成功确认"

def lottery_draw(p00001, p00003):
    """会员抽奖,返回 (ok, msg)"""
    params = {
        "app_k": "b398b8ccbaeacca840073a7ee9b7e7e6",
        "app_v": "11.6.5",
        "platform_id": "10",
        "dev_os": "8.0.0",
        "dev_ua": "FRD-AL10",
        "net_sts": "1",
        "qyid": _md5(_rand16()),
        "psp_uid": p00003,
        "psp_cki": p00001,
        "psp_status": "3",
        "secure_v": "1",
        "secure_p": "GPhone",
        "req_sn": _ts13(),
    }
    url = LOTTERY_URL + "?" + urllib.parse.urlencode(params)
    st, txt = _http(url)
    d, error = response(st, txt)
    if d is None:
        return False, error
    if type(d.get("code")) in (int, str) and d.get("code") in (0, "0"):
        data = d.get("data")
        if not isinstance(data, dict):
            return False, "抽奖响应缺少结果"
        identity(data)
        prize = data.get("prizeName") or data.get("prize_name")
        return True, "抽奖成功" + ("，获得：" + public_value(prize) if isinstance(prize, str) and prize else "")
    return False, "会员抽奖未获成功确认（登录态、机会或接口异常）"

def shake_lottery(p00001):
    """摇一摇抽奖,返回 (ok, msg)"""
    params = {
        "P00001": p00001,
        "deviceID": _md5(_rand16()),
        "version": "15.3.0",
        "platform": _rand16()[:16],
        "lotteryType": "0",
        "actCode": "0k9GkUcjqqj4tne8",
        "extendParams": json.dumps({
            "appIds": "iqiyi_pt_vip_iphone_video_autorenew_12m_348yuan_v2",
            "supportSk2Identity": True,
            "testMode": "0",
            "iosSystemVersion": "17.4",
            "bundleId": "com.qiyi.iphone",
        }),
    }
    url = SHAKE_URL + "?" + urllib.parse.urlencode(params)
    st, txt = _http(url)
    d, error = response(st, txt)
    if d is None:
        return False, error
    if d.get("code") == "A00000" and isinstance(d.get("data"), dict):
        identity(d["data"])
        prize = d["data"].get("prizeName") or d["data"].get("prize_name")
        return True, "摇一摇成功" + ("，获得：" + public_value(prize) if isinstance(prize, str) and prize else "")
    return False, "摇一摇未获成功确认（登录态、机会或接口异常）"

def vip_info(p00001):
    """查询 VIP 信息,返回 (ok, msg)"""
    url = VIP_URL + "?" + urllib.parse.urlencode({"P00001": p00001})
    st, txt = _http(url)
    d, error = response(st, txt)
    if d is None:
        return False, error
    if d.get("code") == "A00000" and isinstance(d.get("data"), dict) and d["data"]:
        data = d["data"]
        identity(data)
        details = []
        for field in ("level", "vipLevel", "vipDeadline", "expireTime"):
            value = data.get(field)
            if isinstance(value, (int, str)) and str(value):
                # 只输出明确的会员字段，不输出业务错误或任意响应。
                details.append("%s:%s" % (field, public_value(value)))
        return True, "VIP信息查询成功" + (" " + " ".join(details) if details else "")
    return False, "VIP查询未获成功确认"


class DryRunRequest(Exception):
    """请求已构造，但未发送。"""


def parse_accounts():
    multi = os.environ.get("IQIYI_COOKIES", "").strip()
    raw = multi or os.environ.get("IQIYI_COOKIE", "").strip()
    return [line.strip().strip("'\"") for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def notify_summary(title, content, dry_run, notify_enabled):
    if not notify_enabled:
        return "已关闭"
    if dry_run:
        return "预演：已生成脱敏通知，未联网发送"
    # 通知模块属于可选青龙集成，不是业务运行依赖。屏蔽模块自己的输出。
    paths = []
    custom = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        paths.append(Path(custom) / "notify.py")
    paths.extend([Path(__file__).resolve().parent / "notify.py",
                  Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import notify
            notify.send(title, content)
        return "青龙通知已调用"
    except (Exception, SystemExit):
        pass
    for path in paths:
        if not path.is_file():
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                spec = importlib.util.spec_from_file_location("qinglong_notify_optional", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send(title, content)
            return "青龙通知已调用"
        except (Exception, SystemExit):
            continue
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if token:
        st, txt = _http("https://www.pushplus.plus/send", "POST",
                        {"token": token, "title": title, "content": content},
                        {"Content-Type": "application/json"})
        d, _ = response(st, txt)
        if d is not None and type(d.get("code")) is int and d["code"] == 200:
            return "PushPlus通知成功"
    key = os.environ.get("SENDKEY", "").strip()
    if key:
        url = "https://sctapi.ftqq.com/%s.send" % urllib.parse.quote(key, safe="")
        st, txt = _http(url, "POST", {"title": title, "desp": content},
                        {"Content-Type": "application/x-www-form-urlencoded"})
        d, _ = response(st, txt)
        if d is not None and type(d.get("code")) is int and d["code"] == 0:
            return "Server酱通知成功"
    return "通知不可用或发送失败（保留业务退出码）"


def log(message):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), message))


def main():
    start = time.monotonic()
    accounts = parse_accounts()
    dry_run = os.environ.get("IQIYI_DRY_RUN", "0").strip().lower() not in DISABLED
    notify_enabled = os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() not in DISABLED
    print("=" * 56)
    print("爱奇艺签到 | 开始时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S %z"))
    print("运行模式：%s | 账号总数：%d" % ("断网预演" if dry_run else "正式执行", len(accounts)))
    log("阶段0：配置检查")
    results = []
    totals = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    configuration_error = False
    try:
        dry_run = enabled("IQIYI_DRY_RUN")
        notify_enabled = enabled("QINGLONG_NOTIFY", "1")
        lottery_enabled = enabled("IQIYI_LOTTERY")
        shake_enabled = enabled("IQIYI_SHAKE")
        if not accounts:
            raise ValueError("未配置凭据")
    except ValueError:
        configuration_error = True
        log("❌ 配置错误：请检查 Cookie 和开关格式；开关支持 1/0、true/false、yes/no、on/off")
    if not configuration_error:
        for index, cookie in enumerate(accounts, 1):
            if not dry_run and index > 1:
                time.sleep(random.uniform(2, 4))
            account_start = time.monotonic()
            counts = {key: 0 for key in totals}
            ok = True
            p00001, p00003, dfp = parse_cookie(cookie)
            log("账号%d | 阶段1：检查凭据" % index)
            if not p00001 or not p00003:
                ok = False
                counts.update(total=1, failure=1)
                log("❌ 凭据缺少 P00001 或 P00003；耗时 %.3f 秒" % (time.monotonic() - account_start))
            else:
                log("✅ 凭据字段齐全；耗时 %.3f 秒" % (time.monotonic() - account_start))
                stages = [
                    ("VIP查询", True, vip_info, (p00001,)),
                    ("自然月签到", True, task_sign, (p00001, p00003)),
                    ("网页积分签到", True, score_sign, (p00001, p00003, dfp)),
                    ("会员抽奖", lottery_enabled, lottery_draw, (p00001, p00003)),
                    ("摇一摇抽奖", shake_enabled, shake_lottery, (p00001,)),
                ]
                for number, (name, active, action, args) in enumerate(stages, 2):
                    if not dry_run and number > 2 and active:
                        time.sleep(random.uniform(1, 2))
                    began = time.monotonic()
                    counts["total"] += 1
                    log("账号%d | 阶段%d：%s" % (index, number, name))
                    if not active:
                        counts["skipped"] += 1
                        log("⏭️ 未启用；耗时 %.3f 秒" % (time.monotonic() - began))
                        continue
                    try:
                        success, message = action(*args)
                    except DryRunRequest:
                        counts["skipped"] += 1
                        log("⏭️ DRY_RUN_OK：请求构造通过，未发送；耗时 %.3f 秒" % (time.monotonic() - began))
                        continue
                    except Exception:
                        success, message = False, "处理失败（已隐藏异常及响应内容）"
                    if success:
                        key = "alreadyComplete" if message == "今日已签到" else "success"
                        counts[key] += 1
                    else:
                        counts["failure"] += 1
                        ok = False
                    log("%s %s；耗时 %.3f 秒" % ("✅" if success else "❌", message,
                                                time.monotonic() - began))
            elapsed = round(time.monotonic() - account_start, 3)
            log("账号%d统计：总任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.3f秒" %
                (index, counts["total"], counts["success"], counts["alreadyComplete"],
                 counts["skipped"], counts["failure"], elapsed))
            results.append({"account": index, "ok": ok, "tasks": counts, "elapsedSeconds": elapsed})
            for key in totals:
                totals[key] += counts[key]
    passed = sum(item["ok"] for item in results)
    failed = len(accounts) - passed
    exit_code = 1 if configuration_error or failed else 0
    status = ("configuration-error" if configuration_error else
              "partial-failure" if failed and passed else "failure" if failed else
              "dry-run" if dry_run else "success")
    # 预演中通过的是配置检查，绝不记作真实业务成功。
    succeeded = 0 if dry_run else passed
    body = "账号总数：%d；成功数：%d；失败数：%d；预演通过数：%d；状态：%s" % (
        len(accounts), succeeded, failed, passed if dry_run else 0, status)
    notification_start = time.monotonic()
    log("阶段7：汇总通知")
    try:
        notification = notify_summary("爱奇艺签到", body, dry_run, notify_enabled)
    except (Exception, SystemExit):
        notification = "通知发送失败（保留业务退出码）"
    print("-" * 56)
    log(body)
    log("子任务统计：总任务%d 成功%d 已完成%d 跳过%d 失败%d" % (
        totals["total"], totals["success"], totals["alreadyComplete"], totals["skipped"], totals["failure"]))
    log("通知状态：%s；阶段耗时：%.3f秒" % (notification, time.monotonic() - notification_start))
    finish = time.strftime("%Y-%m-%d %H:%M:%S %z")
    elapsed = round(time.monotonic() - start, 3)
    log("完成时间：%s；总耗时：%.3f秒；最终状态：%s；退出码：%d" % (finish, elapsed, status, exit_code))
    summary = {"task": "爱奇艺签到", "status": status, "dryRun": dry_run,
               "accountCount": len(accounts), "successCount": succeeded, "failureCount": failed,
               "dryRunPassedCount": passed if dry_run else 0, "accounts": results,
               "tasks": totals, "notification": notification, "elapsedSeconds": elapsed,
               "finishTime": finish, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
