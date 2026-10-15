#!/usr/bin/env python3
# name: 小浣熊每日积分
# cron: 14 2 * * *
# SPDX-License-Identifier: MIT
# 上游: L0NE-6/Raccoon-Daily, raccoon_daily.py
# 参考: 同仓库 raccoon_login.py（仅凭据获取说明，未合并交互式登录）
"""小浣熊每日积分维护版（Python 3，仅标准库）。

RACCOON_TOKENS：每个非空行一个账号，token 或 备注|token；仅在第一个 | 拆分，
支持 Bearer 前缀。网页登录 https://xiaohuanxiong.com 后，在浏览器开发者工具
网络面板找到本站已登录请求的 Authorization，私下复制 Bearer 后的值到青龙。
不要复制 Cookie、回调地址或把凭据发到日志。交互式授权登录工具不属于定时任务。
RACCOON_STATE_FILE：奖励台账路径，默认本脚本旁 raccoon_onboarding.json。
RACCOON_MAIN_SITE_URL：可选 HTTPS 站点，默认 https://xiaohuanxiong.com。
RACCOON_DRY_RUN=1：完全断网、无文件写入的预演（通知仅模拟）。
--query：只查今日入账；--skip-onboarding：不领取新手奖励；--only N：筛选账号；
--no-notify 或 QINGLONG_NOTIFY=0：关闭推送。正常运行自动领取两端一次性奖励。
通知优先调用青龙 notify.py，保留 PUSHPLUS_TOKEN、BARK_URL、WECOM_WEBHOOK、
DINGTALK_WEBHOOK/DINGTALK_SECRET 和 QL_URL/QL_TOKEN 兼容渠道。
上游未声明 cron；维护版建议每天北京时间 09:00，青龙应设置相应时区。

MIT License
本文件继承任务声明的上游 MIT 许可；所提供源文件未含额外版权声明。
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
import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib import request, parse, error

BEIJING = timezone(timedelta(hours=8))
TITLE = "小浣熊每日积分"
SETTINGS = "/api/web/office/v3/setting_info"
BILLS = "/api/web/points/v1/bills?paging.limit=20&paging.offset=0"
GRANTS = (("desktop_login_grant", "首次电脑端登录奖励", "desktop-windows", "v1.0.0", "/api/web/desktop/v1/login/points/grant"),
          ("mobile_login_grant", "首次手机端登录奖励", "app-android", "v1.0.3", "/api/web/mobile/v1/login/points/grant"))
DISABLED = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(datetime.now(BEIJING).strftime("[%H:%M:%S] ") + message, flush=True)


def enabled(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in DISABLED | {""}


def secure_url(url):
    parts = parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise TaskError("地址必须为无内嵌凭据的 HTTPS 地址")
    return url


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url, headers=None, body=None, timeout=20):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止网络请求")
    secure_url(url)
    hdr = {"Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=hdr, method="POST" if body is not None else "GET")
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError("接口 HTTP 状态异常")
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise TaskError("接口响应过大")
            payload = json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        raise TaskError("登录状态失效" if exc.code in (401, 403) else "接口 HTTP %d" % exc.code) from None
    except (error.URLError, TimeoutError, OSError):
        raise TaskError("网络或 TLS 错误、请求超时") from None
    except (ValueError, UnicodeError):
        raise TaskError("接口未返回有效 JSON") from None
    if not isinstance(payload, dict):
        raise TaskError("接口返回结构异常")
    return payload


def unwrap(payload):
    # 上游统一 code/data 契约；缺少业务码不能视为成功。
    if type(payload.get("code")) not in (int, str) or str(payload["code"]) != "0":
        raise TaskError("业务码缺失或业务未成功")
    if not isinstance(payload.get("data"), dict):
        raise TaskError("业务数据结构异常")
    return payload["data"]


def headers(token, platform="desktop-windows", version="v1.0.0"):
    return {"Authorization": "Bearer " + token, "X-Client-Platform": platform,
            "X-Client-Version": version, "X-Raccoon-Language": "zh"}


def accounts_from(raw):
    accounts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split("|", 1)[1].strip() if "|" in line else line
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token or any(c in token for c in "\r\n"):
            raise TaskError("账号凭据为空或格式异常")
        accounts.append(token)
    if not accounts:
        raise TaskError("请配置 RACCOON_TOKENS，每个非空行一个账号")
    return accounts


def show_identity(data):
    # 只显示官方明确的非秘密身份字段，绝不输出整段响应或用户备注。
    sources = [data]
    for field in ("user", "user_info", "profile"):
        if isinstance(data.get(field), dict):
            sources.append(data[field])
    for source in sources:
        for field in ("nickname", "username", "display_name", "public_uid"):
            value = source.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                text = str(value)
                # 电话号码、设备/会话字段不作为身份输出。
                if not re.fullmatch(r"\+?\d{11,15}", text):
                    log("官方账号身份：" + text.replace("\r", " ").replace("\n", " "))
                return


def state_path():
    return Path(os.environ.get("RACCOON_STATE_FILE") or Path(__file__).with_name("raccoon_onboarding.json"))


def load_state():
    path = state_path()
    if not path.exists():
        return {"version": 1, "accounts": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("accounts"), dict):
            raise ValueError()
        return state
    except (OSError, ValueError):
        raise TaskError("奖励台账读取失败，拒绝覆盖已有文件") from None


def save_state(state):
    if enabled("RACCOON_DRY_RUN"):
        raise TaskError("预演禁止写入台账")
    path = state_path()
    temp = None
    try:
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temp = handle.name
            json.dump(state, handle, ensure_ascii=False)
        os.replace(temp, path)
    except OSError:
        raise TaskError("奖励台账保存失败") from None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def daily_total(data):
    if not isinstance(data.get("items"), list):
        raise TaskError("账单缺少 items 列表")
    today = datetime.now(BEIJING).date()
    total, count = 0, 0
    for item in data["items"]:
        if not isinstance(item, dict):
            raise TaskError("账单条目结构异常")
        try:
            points = int(item.get("points") or 0)
            if points <= 0:
                continue
            stamp = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
            stamp = stamp.replace(tzinfo=BEIJING) if stamp.tzinfo is None else stamp.astimezone(BEIJING)
        except (ValueError, TypeError, OverflowError):
            raise TaskError("正积分账单字段无效") from None
        if stamp.date() == today:
            total += points
            count += 1
    if total <= 0:
        raise TaskError("北京时间今日未见正积分入账，不能确认签到成功")
    return "账单核验成功：今日 %d 笔正积分，共 +%d" % (count, total)


def run_account(index, token, args, origin, dry):
    started = time.monotonic()
    stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
    def stage(name, action):
        stats["total"] += 1
        step = stats["total"]
        begin = time.monotonic()
        log("账号%d 阶段%d：%s" % (index, step, name))
        try:
            status, message = ("skipped", "断网预演：仅检查任务计划") if dry else action()
            stats[status] += 1
            log("%s %s（%.2f秒）" % ({"success": "✅", "alreadyComplete": "☑️", "skipped": "⏭️"}[status], message, time.monotonic() - begin))
        except Exception as exc:
            stats["failure"] += 1
            log("❌ %s（%.2f秒）" % (str(exc) if isinstance(exc, TaskError) else "执行失败（已隐藏异常细节）", time.monotonic() - begin))
    def trigger():
        data = unwrap(http_json(origin + SETTINGS, headers(token)))
        show_identity(data)
        return "success", "每日触发接口业务成功；最终签到结果以账单为准"
    def bills():
        data = unwrap(http_json(origin + BILLS, headers(token), timeout=30))
        show_identity(data)
        return "success", daily_total(data)
    if not args.query:
        stage("每日积分触发", trigger)
    stage("北京时间今日账单核验", bills)
    if not args.query and not args.skip_onboarding:
        for key, title, platform, version, path in GRANTS:
            def claim(key=key, platform=platform, version=version, path=path):
                state = load_state()
                account_key = hashlib.sha256(token.encode()).hexdigest()[:16]
                ledger = state["accounts"].get(account_key, {})
                if not isinstance(ledger, dict):
                    raise TaskError("账号奖励台账结构异常")
                if ledger.get(key):
                    return "alreadyComplete", "本地台账已结算，不重复请求"
                data = unwrap(http_json(origin + path, headers(token, platform, version), body={}))
                show_identity(data)
                if type(data.get("granted")) is not bool:
                    raise TaskError("奖励接口缺少明确 granted 布尔结果")
                ledger[key] = int(time.time() * 1000)
                state["accounts"][account_key] = ledger
                save_state(state)
                if not data["granted"]:
                    return "alreadyComplete", "接口确认奖励此前已发放"
                popup = data.get("popup")
                points = popup.get("points") if isinstance(popup, dict) else None
                message = "接口确认首次登录奖励已领取"
                if type(points) is int and points > 0:
                    message += "，+%d 积分" % points
                return "success", message
            stage(title, claim)
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log("账号%d统计：任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒" % (index, stats["total"], stats["success"], stats["alreadyComplete"], stats["skipped"], stats["failure"], stats["elapsedSeconds"]))
    return {"account": index, **stats, "ok": stats["failure"] == 0}


def notify_summary(body, disabled, dry):
    if disabled or not enabled("QINGLONG_NOTIFY", "1"):
        return "已关闭"
    if dry:
        log("⏭️ 预演通知模拟：" + body)
        return "预演模拟（未调用通知模块）"
    # 不依赖青龙；通知模块缺失或发送失败不改变业务退出码。
    try:
        from notify import send
        send(TITLE, body)
        return "青龙已发送"
    except Exception:
        pass
    candidates = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        candidates.append(Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    candidates.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(TITLE, body)
            return "青龙已发送"
        except Exception:
            log("⚠️ 青龙通知调用失败（细节已隐藏）")
    # 保留原脚本兼容渠道；所有请求校验 TLS，错误只记录固定文字。
    e = lambda name: os.environ.get(name, "").strip()
    channels = []
    if e("PUSHPLUS_TOKEN"):
        channels.append(("https://www.pushplus.plus/send", {"token": e("PUSHPLUS_TOKEN"), "title": TITLE, "content": body, "template": "txt"}, "code", 200))
    if e("BARK_URL"):
        channels.append((e("BARK_URL").rstrip("/"), {"title": TITLE, "body": body, "group": "小浣熊"}, "code", 200))
    if e("WECOM_WEBHOOK"):
        hook = e("WECOM_WEBHOOK")
        if not hook.startswith("https://"):
            hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + parse.quote(hook, safe="")
        channels.append((hook, {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}, "errcode", 0))
    if e("DINGTALK_WEBHOOK"):
        hook = e("DINGTALK_WEBHOOK")
        secret = e("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            sig = base64.b64encode(hmac.new(secret.encode(), (stamp + "\n" + secret).encode(), hashlib.sha256).digest()).decode()
            hook += ("&" if "?" in hook else "?") + parse.urlencode({"timestamp": stamp, "sign": sig})
        channels.append((hook, {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}, "errcode", 0))
    if e("QL_URL") and e("QL_TOKEN"):
        channels.append((e("QL_URL").rstrip("/") + "/api/system/notify?" + parse.urlencode({"token": e("QL_TOKEN")}), {"title": TITLE, "content": body}, "code", (0, 200)))
    for url, payload, field, expected in channels:
        try:
            result = http_json(url, body=payload, timeout=15)
            allowed = expected if isinstance(expected, tuple) else (expected,)
            if str(result.get(field)) in {str(v) for v in allowed}:
                return "兼容渠道已发送"
        except Exception:
            pass
    log("⚠️ 通知不可用或失败，保留业务退出码")
    return "不可用或失败"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError("命令参数无效，请使用 --query、--skip-onboarding、--only N、--no-notify")


def main():
    start = time.monotonic()
    dry = enabled("RACCOON_DRY_RUN")
    log("========== " + TITLE + " ==========")
    log("开始时间：" + datetime.now(BEIJING).isoformat(timespec="seconds"))
    log("运行模式：" + ("断网预演" if dry else "正式执行"))
    results, config_error, selected = [], False, []
    args = argparse.Namespace(no_notify=False)
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--query", action="store_true")
        parser.add_argument("--skip-onboarding", action="store_true")
        parser.add_argument("--only", type=int)
        parser.add_argument("--no-notify", action="store_true")
        args = parser.parse_args()
        accounts = accounts_from(os.environ.get("RACCOON_TOKENS", ""))
        if args.only is not None and not 1 <= args.only <= len(accounts):
            raise TaskError("--only 必须是已配置账号的有效序号")
        selected = [(i, token) for i, token in enumerate(accounts, 1) if args.only is None or args.only == i]
        origin = secure_url((os.environ.get("RACCOON_MAIN_SITE_URL", "").strip() or "https://xiaohuanxiong.com").rstrip("/"))
        if parse.urlsplit(origin).query or parse.urlsplit(origin).path not in ("", "/"):
            raise TaskError("站点配置仅允许 HTTPS 域名及可选端口")
        log("账号数：配置%d，本次%d" % (len(accounts), len(selected)))
        for index, token in selected:
            results.append(run_account(index, token, args, origin, dry))
    except Exception as exc:
        config_error = True
        log("❌ 配置错误：" + (str(exc) if isinstance(exc, TaskError) else "配置处理失败（细节已隐藏）"))
        log("账号数：本次%d" % len(selected))
    good = sum(r["ok"] for r in results)
    bad = len(results) - good
    exit_code = 1 if config_error or bad else 0
    status = "configuration-error" if config_error else "partial-failure" if bad and good else "failure" if bad else "dry-run" if dry else "success"
    totals = {k: sum(r[k] for r in results) for k in ("total", "success", "alreadyComplete", "skipped", "failure")}
    body = "状态：%s；账号总数%d，成功%d，失败%d；子任务%d，成功%d，已完成%d，跳过%d，失败%d%s" % (status, len(selected), good, bad, totals["total"], totals["success"], totals["alreadyComplete"], totals["skipped"], totals["failure"], "；配置错误" if config_error else "")
    log("----------------------------------------")
    log(body)
    notification = notify_summary(body, args.no_notify, dry)
    summary = {"task": TITLE, "status": status, "dryRun": dry, "accountCount": len(selected), "successCount": good, "failureCount": bad, "configurationError": config_error, "accounts": results, "stages": totals, "notification": notification, "elapsedSeconds": round(time.monotonic() - start, 2), "exitCode": exit_code}
    log("通知状态：" + notification)
    log("总耗时：%.2f秒；完成时间：%s；最终状态：%s" % (summary["elapsedSeconds"], datetime.now(BEIJING).isoformat(timespec="seconds"), status))
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
