# -*- coding: utf-8 -*-
# name: 塔斯汀每日签到
# cron: 40 9 * * *
"""塔斯汀小程序每日自动签到，原作者 LeapYa。
上游：https://github.com/LeapYa/tastin-sign （tastin_sign.py）
MIT License
Copyright (c) LeapYa

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

配置：TASTIN_ACCOUNTS 每行 token|memberPhone，仅在第一个 | 处分割。
在本人登录的塔斯汀微信小程序中，通过本人授权的 HTTPS 调试记录，获取
sss-web.tastientech.com 请求头 user-token，以及签到请求体 memberPhone
（加密手机号令牌，原样保留）。不得填写明文手机号。
旧单账号 TASTIN_USER_TOKEN + TASTIN_MEMBER_PHONE 仍可使用；新变量优先。
TASTIN_SHOP_ID=28416，TASTIN_VERSION=3.78.0，TASTIN_ACTIVITY_ID=74
分别对应本人请求的 gray-shop-id、version、activityId；活动编号是探测起点。
TASTIN_DRY_RUN=1 完全断网预演，通知同样只模拟。
仅签到改变服务端状态；不消费、不发帖、不修改资料。
不再自动下载免费代理或关闭证书校验；确需代理时自行配置可信 TASTIN_PROXY。
保留可选 SMTP_* 邮件参数；非 465 端口必须成功 STARTTLS 才发送凭据。
上游只声明每日运行，未附具体触发时刻；cron 建议青龙本地时间每日 09:00。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('b2b2643c2ae50051', 'scripts/tastin_sign.py', 'tastin_sign.py', 'tastin_sign')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import fnmatch
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

TITLE = "塔斯汀每日签到"
CATALOG_ID = "b2b2643c2ae50051"
BASE_URL = "https://sss-web.tastientech.com"
TZ = timezone(timedelta(hours=8))
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
SECRETS = []


def now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def safe(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return " ".join(text.split())[:500]


def log(text):
    print(f"[{datetime.now(TZ):%H:%M:%S}] {safe(text)}", flush=True)


class TaskError(Exception):
    def __init__(self, message, retry=False, expired=False):
        super().__init__(message)
        self.retry = retry
        self.expired = expired


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 禁止将认证头转发到重定向地址


class Client:
    def __init__(self, token, phone, config):
        self.phone = phone
        self.config = config
        self.deadline = time.monotonic() + 900
        self.headers = {
            "Content-Type": "application/json", "user-token": token,
            "gray-shop-id": str(config["shop"]), "channel": "1",
            "version": config["version"], "xweb_xhr": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
                          "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
                          "MiniProgramEnv/Windows WindowsWechat/WMPF "
                          "WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541b36) XWEB/20089",
            "Referer": "https://servicewechat.com/wx557473f23153a429/537/page-frame.html",
        }
        proxy = config["proxy"]
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy} if proxy else {}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())

    def request(self, path, body, mutation=False):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TaskError("账号运行已达 900 秒上限")
        request = urllib.request.Request(BASE_URL + path,
                                        data=json.dumps(body).encode("utf-8"),
                                        headers=self.headers, method="POST")
        try:
            with self.opener.open(request, timeout=min(15, left)) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise TaskError("响应超过安全大小限制")
            result = json.loads(raw)
            if not isinstance(result, dict) or "code" not in result:
                raise TaskError("响应结构无效，未确认业务成功")
            return result
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 401:
                raise TaskError("认证失效，请从本人小程序重新获取配套凭据", expired=True) from None
            if exc.code in (403, 405):
                raise TaskError("HTTP 拦截，检查网络或显式配置可信代理") from None
            raise TaskError(f"HTTP {exc.code}，未确认业务成功",
                            retry=not mutation and exc.code >= 500) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            message = "签到请求结果不确定，停止自动重发，请在小程序核对" if mutation else "网络或证书连接失败"
            raise TaskError(message, retry=not mutation) from None
        except (ValueError, UnicodeError):
            raise TaskError("响应无法解析，未确认业务成功") from None


def data_result(response, label):
    if response.get("code") != 200:
        raise TaskError(label + "业务未成功", expired=response.get("code") == 401)
    result = response.get("result")
    if not isinstance(result, dict) or not result:
        raise TaskError(label + "响应缺少有效结果")
    return result


def display_account(result):
    # 仅允许官方非机密身份字段，不输出 phone、memberPhone、token 等字段。
    for key in ("nickname", "nickName", "username", "userName", "displayName", "publicUid"):
        if isinstance(result.get(key), (str, int)) and not isinstance(result[key], bool):
            log(f"官方账号 {key}: {result[key]}")


def activity(client):
    response = client.request("/api/minic/shop/intelligence/banner/c/list/sign", {
        "shopId": client.config["shop"], "birthday": "", "gender": 0,
        "nickName": None, "phone": client.phone})
    ids = []
    if response.get("code") == 200 and isinstance(response.get("result"), list):
        for item in response["result"]:
            if not isinstance(item, dict) or item.get("jumpCode") != "SIGN":
                continue
            try:
                params = item.get("jumpPara", "{}")
                if isinstance(params, str):
                    params = json.loads(params)
                aid = int(params["activityId"])
                if aid > 0:
                    ids.append(aid)
            except (ValueError, TypeError, KeyError):
                continue
    if not ids:
        log("入口未提供活动编号，开始最多 30 个编号的只读探测")
    start = client.config["activity"]
    ids.extend(range(start, start + 30))
    for aid in dict.fromkeys(ids):
        r = client.request("/api/sign/member/signInfoV2", {"activityId": aid})
        if r.get("code") != 200 or not isinstance(r.get("result"), dict):
            continue
        result = r["result"]
        info = result.get("activityInfo")
        if not isinstance(info, dict):
            continue
        st, et = info.get("startTime"), info.get("endTime")
        if (isinstance(st, (int, float)) and isinstance(et, (int, float))
                and st <= int(time.time() * 1000) <= et):
            if info.get("daySignOpen") not in (True, 1):
                raise TaskError("当前活动每日签到未开放，未执行签到")
            log(f"有效活动 ID={aid}，活动名称: {info.get('name', '未提供')}，每日签到开启")
            return aid
    raise TaskError("未能核验有效且开放的当期活动，未使用默认编号盲目签到")


def show_rewards(result):
    log(f"连续签到: {result.get('continuousNum', '未提供')} 天")
    rewards = result.get("rewardInfoList")
    if isinstance(rewards, list):
        for reward in rewards:
            if not isinstance(reward, dict):
                continue
            log(f"奖励: {reward.get('rewardName', '未提供')}，积分: {reward.get('point', 0)}")
            coupons = reward.get("couponInfo")
            if isinstance(coupons, list):
                for coupon in coupons:
                    if isinstance(coupon, dict):
                        log(f"优惠券: {coupon.get('name', '未提供')}；"
                            f"{coupon.get('couponContent', '')}；{coupon.get('couponTime', '')}")


@contextlib.contextmanager
def stage(number, title, stats):
    start = time.monotonic()
    log(f"阶段 {number} / {title} 开始")
    stats["total"] += 1
    try:
        yield
    except Exception:
        stats["failed"] += 1
        log(f"❌ 阶段 {number} / {title} 失败，耗时 {time.monotonic() - start:.2f} 秒")
        raise
    else:
        stats["success"] += 1
        log(f"✅ 阶段 {number} / {title} 完成，耗时 {time.monotonic() - start:.2f} 秒")


def run_account(client, stats):
    for attempt in range(1, 6):
        log(f"只读准备第 {attempt}/5 次尝试")
        try:
            with stage(1, "验证认证及查询积分", stats):
                point = data_result(client.request("/api/wx/point/myPoint", {}), "认证及积分查询")
                display_account(point)
                log(f"当前积分: {point.get('point', '未提供')}")
            with stage(2, "发现并核验签到活动", stats):
                aid = activity(client)
            break
        except TaskError as exc:
            if not exc.retry or attempt == 5:
                raise
            delay = 30 * 2 ** (attempt - 1)
            if time.monotonic() + delay >= client.deadline:
                raise TaskError("重试将超过账号时限") from None
            log(f"网络暂时失败，{delay} 秒后重试只读准备")
            time.sleep(delay)
    with stage(3, "执行每日签到", stats):
        response = client.request("/api/sign/member/signV2/sign", {
            "activityId": aid, "memberName": "", "memberPhone": client.phone}, mutation=True)
        # 保留上游的已签提示兼容，但仅接受完整明确的提示，拒绝模糊子串误判。
        already = response.get("msg") in {
            "今天已经签过了", "今天已经签过了！", "今日已签到", "今日已签到！",
            "今天已签到", "您今天已经签到过了", "您今天已签到", "今日已签", "今天已签过"}
        if already:
            stats["alreadyComplete"] += 1
            stats["success"] -= 1
            log("☑️ 今天已经签过了")
        else:
            result = data_result(response, "签到")
            log("签到成功")
            show_rewards(result)
    with stage(4, "查询最终积分", stats):
        result = data_result(client.request("/api/wx/point/myPoint", {}), "最终积分查询")
        display_account(result)
        log(f"最终积分: {result.get('point', '未提供')}")
    return "already-complete" if already else "success"


def parse_accounts():
    raw = os.environ.get("TASTIN_ACCOUNTS", "")
    if raw.strip():
        accounts = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            fields = line.strip().split("|", 1)
            accounts.append(tuple(x.strip() for x in fields) if len(fields) == 2 else ("", ""))
        return accounts
    token = os.environ.get("TASTIN_USER_TOKEN", "").strip()
    phone = os.environ.get("TASTIN_MEMBER_PHONE", "").strip()
    return [(token, phone)] if token or phone else []


def configuration():
    try:
        shop = int(os.environ.get("TASTIN_SHOP_ID", "28416"))
        aid = int(os.environ.get("TASTIN_ACTIVITY_ID", "74"))
        if shop <= 0 or aid <= 0:
            raise ValueError
    except ValueError:
        raise TaskError("门店编号和活动起点必须为正整数") from None
    proxy = os.environ.get("TASTIN_PROXY", "").strip()
    if proxy:
        try:
            parsed = urllib.parse.urlsplit(proxy)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.fragment:
                raise ValueError
            _ = parsed.port
        except ValueError:
            raise TaskError("TASTIN_PROXY 必须为可信 HTTP 或 HTTPS 代理地址") from None
    return {"shop": shop, "activity": aid, "version": os.environ.get("TASTIN_VERSION", "3.78.0"),
            "proxy": proxy}


def notification_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    # 本任务属于默认通知名单；显式列表替换默认名单。
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", CATALOG_ID).strip())
    file = Path(__file__)
    identifiers = (CATALOG_ID, file.name, file.as_posix(), "output/" + file.name)
    return any(fnmatch.fnmatchcase(value, selector) for selector in selectors if selector
               for value in identifiers)


def notify_summary(body, dry):
    if not notification_enabled():
        return "disabled"
    if dry:
        log("⏭️ 断网预演：仅模拟青龙通知，不加载可能联网的通知模块")
        return "simulated"
    # 使用隔离子进程，限制通知运行时间并屏蔽通知模块输出，避免凭据泄露。
    worker = (
        "import importlib.util,json,sys; title,body=json.loads(sys.stdin.read()); "
        "p=sys.argv[1]; "
        "spec=importlib.util.spec_from_file_location('ql_notify',p) if p else None; "
        "m=importlib.util.module_from_spec(spec) if spec else __import__('notify'); "
        "spec.loader.exec_module(m) if spec else None; m.send(title,body)"
    )
    dirs = [os.environ.get("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    candidates = [[sys.executable, "-c", worker, ""]]
    for directory in dirs:
        if directory:
            file = Path(directory) / "notify.py"
            if file.is_file():
                candidates.append([sys.executable, "-c", worker, str(file)])
    for directory in dirs:
        if directory:
            file = Path(directory) / "sendNotify.js"
            if file.is_file():
                js = "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',async()=>{try{const [t,b]=JSON.parse(s);await require(process.argv[1]).sendNotify(t,b)}catch(e){process.exitCode=1}})"
                candidates.append(["node", "-e", js, str(file)])
    for command in candidates:
        try:
            result = subprocess.run(command, input=json.dumps([TITLE, body]), text=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                return "sent"
        except (OSError, subprocess.TimeoutExpired):
            pass
    log("⚠️ 青龙通知不可用或发送失败，保留业务退出码")
    return "unavailable-or-failed"


def email_summary(body, expired, dry):
    if dry or not notification_enabled():
        return "skipped"
    if not expired and os.environ.get("SMTP_NOTIFY_SIGN", "").lower() not in TRUE:
        return "skipped"
    host, user, password = (os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    if not all((host, user, password)):
        return "unconfigured"
    try:
        port = int(os.environ.get("SMTP_PORT", "465"))
        recipient = os.environ.get("SMTP_TO", "") or user
        msg = EmailMessage()
        msg["Subject"] = TITLE + ("认证失效提醒" if expired else "任务结果")
        msg["From"], msg["To"] = user, recipient
        msg.set_content(body)
        context = ssl.create_default_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
        with server:
            if port != 465:
                server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
        log("邮件通知已发送")
        return "sent"
    except Exception:
        log("⚠️ 邮件发送失败，保留业务退出码")
        return "failed"


def main():
    started, clock = now(), time.monotonic()
    dry = os.environ.get("TASTIN_DRY_RUN", "").lower() in TRUE
    accounts = parse_accounts()
    for token, phone in accounts:
        SECRETS.extend([token, phone])
    SECRETS.extend(os.environ.get(k, "") for k in (
        "TASTIN_USER_TOKEN", "TASTIN_MEMBER_PHONE", "TASTIN_PROXY", "SMTP_PASS", "SMTP_USER", "SMTP_TO"))
    log("=" * 60)
    log(TITLE + " | 原作者 LeapYa | MIT")
    log(f"开始时间: {started}；模式: {'断网预演' if dry else '真实执行'}；账号数: {len(accounts)}")
    results, expired, config_error = [], False, False
    try:
        config = configuration()
        if not accounts:
            raise TaskError("缺少 TASTIN_ACCOUNTS，或旧单账号配套认证参数")
    except TaskError as exc:
        log(f"❌ 配置错误: {exc}")
        config_error, config = True, None
    for index, (token, phone) in enumerate(accounts, 1):
        begin = time.monotonic()
        stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        status = "failure"
        log(f"--- 账号 {index}/{len(accounts)} ---")
        try:
            if not config:
                raise TaskError("公共配置无效")
            if not token or not phone or any(c in token + phone for c in "\r\n"):
                raise TaskError("账号行必须包含 token|memberPhone 两项非空凭据")
            if re.fullmatch(r"(?:\+?86)?1[3-9]\d{9}", phone):
                raise TaskError("memberPhone 需要加密令牌，不能填写明文手机号")
            if dry:
                for number, name in enumerate(("认证及积分查询", "发现并核验活动", "每日签到", "最终积分查询"), 1):
                    log(f"⏭️ 阶段 {number} / {name} 已模拟，耗时 0.00 秒，未发请求")
                stats.update(total=4, skipped=4)
                log("DRY_RUN_OK：凭据结构有效；未创建 HTTP 客户端，未发送签到、邮件或通知")
                status = "dry-run"
            else:
                status = run_account(Client(token, phone, config), stats)
        except TaskError as exc:
            expired |= exc.expired
            if stats["failed"] == 0:
                stats["total"] += 1
                stats["failed"] += 1
            log(f"❌ 账号 {index}: {exc}")
        except Exception:
            stats["total"] += 1
            stats["failed"] += 1
            log(f"❌ 账号 {index}: 执行异常，未确认业务成功；异常详情已隐藏")
        duration = round(time.monotonic() - begin, 2)
        results.append({"account": index, "status": status, "tasks": stats, "durationSeconds": duration})
        log(f"账号 {index} 统计: 总任务 {stats['total']}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}；"
            f"耗时 {duration} 秒；状态 {status}")
    failed = sum(r["status"] == "failure" for r in results)
    success = sum(r["status"] in ("success", "already-complete") for r in results)
    simulated = sum(r["status"] == "dry-run" for r in results)
    exit_code = 1 if config_error or failed else 0
    status = ("configuration-error" if config_error else
              "partial-failure" if failed and success + simulated else
              "failure" if failed else "dry-run" if dry else "success")
    body = f"状态 {status}；账号总数 {len(accounts)}；成功 {success}；失败 {failed}；预演 {simulated}；配置错误 {int(config_error)}"
    notification = notify_summary(body, dry)
    mail = email_summary(body, expired, dry)
    totals = {key: sum(r["tasks"][key] for r in results)
              for key in ("total", "success", "alreadyComplete", "skipped", "failed")}
    finished = now()
    duration = round(time.monotonic() - clock, 2)
    log("-" * 60)
    log(f"任务统计: {body}；子任务统计: {json.dumps(totals, ensure_ascii=False)}")
    log(f"结束时间: {finished}；总耗时 {duration} 秒；通知状态 {notification}；邮件状态 {mail}；最终状态 {status}")
    if expired:
        print("::error::塔斯汀 token 已过期，需要手动更新！")
    elif exit_code:
        print("::error::签到失败，请检查脱敏日志及环境变量配置")
    summary = {"task": TITLE, "status": status, "mode": "dry-run" if dry else "live",
               "accountCount": len(accounts), "success": success, "failed": failed,
               "simulated": simulated, "configurationError": config_error, "tasks": totals,
               "accounts": results, "startTime": started, "finishTime": finished,
               "durationSeconds": duration, "notification": notification, "email": mail, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
