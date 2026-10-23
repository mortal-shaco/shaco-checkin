#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ModelScope 魔搭每日签到
# cron: 30 0 * * *
# SPDX-License-Identifier: MIT
# Based on L0NE-6/ModelScope-Daily, modelscope_daily.py (MIT).
"""ModelScope 国内站和国际站每日签到。

每行一个账号：MODELSCOPE_ACCOUNTS = cn:备注|m_session_id 或 intl:备注|m_session_id。
旧变量 MODELSCOPE_CN_TOKENS / MODELSCOPE_INTL_TOKENS = 备注|m_session_id。
备注可省略；只在第一个 | 处分割，其余字符属于会话值。国内站与国际站凭据分别配置。
单账号旧变量 MODELSCOPE_CN_TOKEN / MODELSCOPE_INTL_TOKEN 仍可用，且仅在对应多账号变量为空时使用。
登录对应站点后，在浏览器开发者工具的 Cookie 中取得 m_session_id；不要在日志中粘贴该值。
--query 保留原行为：调用登录信息接口，可能触发签到，再查询余额等信息。
--only N 只运行第 N 个账号；--no-notify 或 MODELSCOPE_NO_NOTIFY=1 关闭推送。
MODELSCOPE_PROXY 配置 HTTP(S) 代理；MODELSCOPE_VERIFY_DELAY 默认为 2 秒。
MODELSCOPE_DRY_RUN=1 只检查配置并展示预演结果，完全不访问网络。
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
        _ql_notify_identities = ('2d3c603c8a58ed00', 'scripts/modelscope_daily.py', 'modelscope_daily.py', 'modelscope_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import datetime as dt
import fnmatch
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import error, parse, request

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

REGIONS = {
    "cn": {"label": "国内版", "site": "https://modelscope.cn", "many": "MODELSCOPE_CN_TOKENS", "one": "MODELSCOPE_CN_TOKEN"},
    "intl": {"label": "国际版", "site": "https://www.modelscope.ai", "many": "MODELSCOPE_INTL_TOKENS", "one": "MODELSCOPE_INTL_TOKEN"},
}
LOGIN_INFO_PATH = "/api/v1/users/login/info"
BALANCE_PATH = "/openapi/v1/magicubes/balance"
TRANSACTIONS_PATH = "/openapi/v1/magicubes/transactions?page=1&page_size=50"
RATE_LIMIT_PATH = "/api/v1/inference/rate-limit"
DAILY_RULES = ("daily_active", "aliyun_bindlogin")
CATALOG_ID = "2d3c603c8a58ed00"
TITLE = "ModelScope 魔搭每日签到"


class ModelScopeError(Exception):
    pass


def stamp():
    return dt.datetime.now().astimezone().strftime("%H:%M:%S")


def log(text):
    print("[%s] %s" % (stamp(), text), flush=True)


def elapsed(start):
    return "%.2f秒" % (time.monotonic() - start)


def clean_public(value, secrets=()):
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:160]


def first_text(record, keys):
    if not isinstance(record, dict):
        return ""
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_accounts(many_env, one_env):
    accounts = []
    raw = os.getenv(many_env, "")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        remark, token = line.split("|", 1) if "|" in line else ("", line)
        accounts.append({"remark": remark.strip(), "token": token.strip(),
                         "error": "会话值为空" if not token.strip() else ""})
    if not accounts and os.getenv(one_env, "").strip():
        accounts.append({"remark": "", "token": os.environ[one_env].strip()})
    return accounts


def configured_jobs():
    raw = os.getenv("MODELSCOPE_ACCOUNTS", "")
    if raw.strip():
        jobs = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            left, token = line.split("|", 1) if "|" in line else ("", "")
            region, remark = left.split(":", 1) if ":" in left else ("", "")
            region = region.strip().lower()
            bad = "站点应为 cn 或 intl" if region not in REGIONS else ("会话值为空" if not token.strip() else "")
            jobs.append((region, {"remark": remark.strip(), "token": token.strip(), "error": bad}))
        return jobs
    jobs = []
    for region, cfg in REGIONS.items():
        for account in parse_accounts(cfg["many"], cfg["one"]):
            jobs.append((region, account))
    return jobs


def envelope_data(payload):
    value = payload.get("Data", payload.get("data"))
    return value if isinstance(value, dict) else {}


def envelope_ok(payload):
    if not isinstance(payload, dict):
        return False
    for key in ("Success", "success"):
        if isinstance(payload.get(key), bool):
            return payload[key]
    code = payload.get("Code", payload.get("code"))
    return str(code) == "200" if code is not None else False


def today_cn():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()


def daily_records_for_day(records, day):
    return [row for row in records if isinstance(row, dict)
            and str(row.get("type") or "").upper() == "EARN"
            and str(row.get("gmt_created") or "")[:10] == day
            and str(row.get("rule_key") or "").lower() in DAILY_RULES] if isinstance(records, list) else []


def json_http(url, *, headers=None, body=None, proxy=None, timeout=15):
    handlers = [request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else [request.ProxyHandler()]
    opener = request.build_opener(*handlers)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise ModelScopeError("HTTP %s" % response.status)
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ModelScopeError("响应超过大小限制")
            return json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        raise ModelScopeError("HTTP %s" % exc.code) from None
    except (error.URLError, TimeoutError, OSError):
        raise ModelScopeError("网络连接失败或超时") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ModelScopeError("响应 JSON 格式异常") from None


class ModelScopeClient:
    def __init__(self, region, account):
        self.region = region
        self.config = REGIONS[region]
        self.token = account["token"]
        self.secrets = (self.token, os.getenv("MODELSCOPE_PROXY", ""))
        self.stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
        self.identity = ""

    def get(self, path, label):
        try:
            return json_http(self.config["site"] + path,
                             headers={"Cookie": "m_session_id=" + self.token, "Accept": "application/json"},
                             proxy=os.getenv("MODELSCOPE_PROXY", "").strip() or None, timeout=30)
        except ModelScopeError as exc:
            raise ModelScopeError("%s失败：%s" % (label, exc)) from None

    def login_info(self):
        payload = self.get(LOGIN_INFO_PATH, "每日签到")
        if not envelope_ok(payload):
            raise ModelScopeError("每日签到业务结果未成功")
        return payload

    def balance(self):
        payload = self.get(BALANCE_PATH, "魔粒余额查询")
        if not envelope_ok(payload):
            raise ModelScopeError("魔粒余额查询业务结果未成功")
        data = envelope_data(payload)
        if "available_balance" not in data:
            raise ModelScopeError("魔粒余额响应缺少可用余额")
        return {"available": data["available_balance"], "total": data.get("total_balance"),
                "frozen": data.get("frozen_amount")}

    def used_today(self):
        payload = self.get(RATE_LIMIT_PATH, "今日用量查询")
        if not envelope_ok(payload):
            raise ModelScopeError("今日用量查询业务结果未成功")
        data = envelope_data(payload)
        if "currentUsagePerDay" not in data:
            raise ModelScopeError("今日用量响应缺少用量")
        return data["currentUsagePerDay"]

    def transactions(self):
        payload = self.get(TRANSACTIONS_PATH, "魔粒账单查询")
        if not envelope_ok(payload):
            raise ModelScopeError("魔粒账单查询业务结果未成功")
        records = envelope_data(payload).get("records")
        if not isinstance(records, list):
            raise ModelScopeError("魔粒账单响应缺少记录列表")
        return records

    def daily_earn(self):
        return daily_records_for_day(self.transactions(), today_cn())

    def run(self, query_only=False, stage=None):
        def step(number, name, action, optional=False):
            started = time.monotonic()
            self.stats["total"] += 1
            if stage:
                stage(number, name, "开始", "")
            try:
                value = action()
                self.stats["success"] += 1
                if stage:
                    stage(number, name, "成功", elapsed(started))
                return value, ""
            except ModelScopeError as exc:
                self.stats["failed" if not optional else "skipped"] += 1
                message = clean_public(exc, self.secrets)
                if stage:
                    stage(number, name, "跳过" if optional else "失败", elapsed(started) + "；" + message)
                if not optional:
                    raise
                return None, message

        before = []
        before_error = ""
        if self.region == "cn":
            before, before_error = step(1, "签到前账单回读", self.daily_earn, optional=True)
            before = before or []
        payload, _ = step(2, "调用登录签到接口", self.login_info)
        identity = envelope_data(payload)
        self.identity = clean_public(first_text(identity, ("NickName", "Name", "nickname", "name", "userName", "uid", "HavanaId")), self.secrets)
        parts = []
        confirmed = True
        if self.region == "cn":
            daily = list(before)
            after_error = ""
            if not daily:
                daily, after_error = step(3, "签到后账单回读", self.daily_earn, optional=True)
                daily = daily or []
                if not daily:
                    try:
                        delay = max(0, min(30, int(os.getenv("MODELSCOPE_VERIFY_DELAY", "2"))))
                    except ValueError:
                        delay = 2
                    if delay:
                        time.sleep(delay)
                    daily, after_error = step(4, "延迟账单核验", self.daily_earn, optional=True)
                    daily = daily or []
            if daily:
                try:
                    credit = sum(float(row.get("total_amount") or 0) for row in daily)
                except (TypeError, ValueError, OverflowError):
                    credit = 0
                titles = [clean_public(row.get("title") or row.get("rule_key") or "", self.secrets) for row in daily]
                titles = [title for title in titles if title]
                amount = int(credit) if credit == int(credit) else credit
                parts.append("%s %s 魔粒%s" % ("今日已领取" if before else "签到到账", amount,
                             "（%s）" % " + ".join(titles) if titles else ""))
                if before:
                    self.stats["alreadyComplete"] += 1
            else:
                confirmed = False
                self.stats["total"] += 1
                self.stats["failed"] += 1
                if stage:
                    stage(7, "签到到账核验", "失败", "未查到当日到账记录")
                parts.append("登录已触达，但今日未查到到账记录%s" %
                             ("（账单查询失败：%s）" % (after_error or before_error) if (after_error or before_error)
                              else "（账号可能不在活动范围）"))
        elif query_only:
            parts.append("登录态有效")
        else:
            parts.append("每日签到已触发（国际站无账单回读）")
        if self.identity:
            parts.append(self.identity)
        wallet, balance_error = step(5, "查询魔粒余额", self.balance, optional=True)
        if wallet is not None:
            parts.append("可用魔粒 %s" % clean_public(wallet["available"], self.secrets))
            if wallet["total"] is not None:
                parts.append("总计 %s" % clean_public(wallet["total"], self.secrets))
        else:
            parts.append("余额查询失败：%s" % balance_error)
        used, _ = step(6, "查询今日用量", self.used_today, optional=True)
        if used is not None:
            parts.append("今日已用 %s 次" % clean_public(used, self.secrets))
        return confirmed, "；".join(parts)


def notification_selected():
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in ("0", "false", "no", "off") or os.getenv("MODELSCOPE_NO_NOTIFY", "").strip() == "1":
        return False
    selected = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selected is not None:
        selectors = re.split(r"[,;\s]+", selected.strip())
        choices = (CATALOG_ID, "candidate.py", "output/candidate.py", "modelscope_daily.py")
        return any(fnmatch.fnmatch(choice, pattern) for pattern in selectors if pattern for choice in choices)
    return True


def qinglong_notify(body):
    try:
        module = importlib.import_module("notify")
        send = getattr(module, "send", None)
        if callable(send):
            send(TITLE, body)
            return True
    except Exception:
        pass
    paths = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        paths.append(Path(custom) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = getattr(module, "send", None)
            if callable(send):
                send(TITLE, body)
                return True
        except Exception:
            continue
    return False


def legacy_notify(body):
    destinations = []
    if os.getenv("PLUSPLUS_TOKEN", "").strip():
        destinations.append(("https://www.pushplus.plus/send", {"token": os.environ["PLUSPLUS_TOKEN"], "title": TITLE, "content": body, "template": "txt"}))
    if os.getenv("BARK_URL", "").strip():
        destinations.append((os.environ["BARK_URL"].strip().rstrip("/") + "/" + parse.quote(TITLE, safe=""), {"body": body}))
    wecom = os.getenv("WECOM_WEBHOOK", "").strip() or os.getenv("QYWX_TOKEN", "").strip()
    if wecom:
        if "key=" not in wecom and "/send?" not in wecom:
            wecom = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + wecom
        destinations.append((wecom, {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}))
    if os.getenv("DINGTALK_WEBHOOK", "").strip():
        destinations.append((os.environ["DINGTALK_WEBHOOK"].strip(), {"msgtype": "text", "text": {"content": TITLE + "\n" + body}}))
    count = 0
    for url, payload in destinations:
        if not url.startswith("https://"):
            continue
        try:
            json_http(url, headers={"Content-Type": "application/json"}, body=payload, timeout=15)
            count += 1
        except Exception:
            pass
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--query", action="store_true", help="保留旧查询模式；登录接口仍可能触发签到")
    parser.add_argument("--only", type=int, help="只运行指定序号的账号")
    parser.add_argument("--no-notify", action="store_true", help="关闭通知")
    args = parser.parse_args(argv)
    started = time.monotonic()
    start_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    dry = os.getenv("MODELSCOPE_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on")
    log("===== %s =====" % TITLE)
    log("开始时间：%s；模式：%s" % (start_at, "无网络预演" if dry else "正式运行"))
    jobs = []
    config_error = ""
    try:
        jobs = configured_jobs()
        if not jobs:
            raise ModelScopeError("未配置 MODELSCOPE_ACCOUNTS 或旧版站点凭据变量")
        if args.only is not None:
            if args.only < 1 or args.only > len(jobs):
                raise ModelScopeError("--only 账号序号超出范围")
            jobs = [jobs[args.only - 1]]
    except ModelScopeError as exc:
        config_error = str(exc)
    log("账号数量：%d" % len(jobs))
    succeeded = 0
    failed = 0
    substats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
    summary_lines = []
    if config_error:
        log("❌ 配置错误：%s" % config_error)
        failed = 1
    else:
        for index, (region, account) in enumerate(jobs, 1):
            account_start = time.monotonic()
            label = REGIONS[region]["label"] if region in REGIONS else "未知站点"
            log("----- 账号 %d/%d：%s -----" % (index, len(jobs), label))
            if account.get("error"):
                failed += 1
                substats["total"] += 1
                substats["failed"] += 1
                log("[阶段1] ❌ 凭据格式检查：%s；耗时%s" % (account["error"], elapsed(account_start)))
                log("账号%d统计：总任务1，成功0，已完成0，跳过0，失败1，耗时%s" % (index, elapsed(account_start)))
                summary_lines.append("账号%d %s：配置失败；%s" % (index, label, account["error"]))
                continue
            if dry:
                log("[阶段1] ⏭️ 凭据格式检查：已提供会话值；耗时 0.00秒")
                log("[阶段2] ⏭️ 网络请求：无网络预演，未执行；耗时 0.00秒")
                log("账号%d统计：总任务2，成功0，已完成0，跳过2，失败0，耗时%s" % (index, elapsed(account_start)))
                substats["total"] += 2
                substats["skipped"] += 2
                summary_lines.append("账号%d %s：无网络预演通过" % (index, label))
                succeeded += 1
                continue
            client = ModelScopeClient(region, account)
            def stage(number, name, result, detail):
                icon = {"开始": "·", "成功": "✅", "跳过": "⏭️", "失败": "❌"}[result]
                log("[阶段%d] %s %s：%s%s" % (number, icon, name, result, "；" + detail if detail else ""))
            try:
                confirmed, message = client.run(query_only=args.query, stage=stage)
                if confirmed:
                    succeeded += 1
                    log("✅ 账号%d %s：%s" % (index, label, message))
                    summary_lines.append("账号%d %s：成功；%s" % (index, label, message))
                else:
                    failed += 1
                    log("❌ 账号%d %s：未确认；%s" % (index, label, message))
                    summary_lines.append("账号%d %s：未确认；%s" % (index, label, message))
            except ModelScopeError as exc:
                failed += 1
                why = clean_public(exc, client.secrets)
                log("❌ 账号%d %s：%s" % (index, label, why))
                summary_lines.append("账号%d %s：失败；%s" % (index, label, why))
            except Exception:
                failed += 1
                log("❌ 账号%d %s：运行异常，详情已隐藏" % (index, label))
                summary_lines.append("账号%d %s：失败；运行异常，详情已隐藏" % (index, label))
            for key in substats:
                substats[key] += client.stats[key]
            stat = client.stats
            log("账号%d统计：总任务%d，成功%d，已完成%d，跳过%d，失败%d，耗时%s" %
                (index, stat["total"], stat["success"], stat["alreadyComplete"], stat["skipped"], stat["failed"], elapsed(account_start)))
            if index < len(jobs):
                time.sleep(1)
    status = "配置错误" if config_error else (
        ("预演完成" if failed == 0 else "预演部分失败" if succeeded else "预演失败") if dry
        else ("成功" if failed == 0 else "部分失败" if succeeded else "失败"))
    business_exit = 1 if failed else 0
    body = "账号总数%d，成功%d，失败%d；状态：%s" % (len(jobs), succeeded, failed, status)
    if summary_lines:
        body += "\n" + "\n".join(summary_lines)
    notify_status = "已关闭"
    if not args.no_notify and notification_selected():
        if dry:
            notify_status = "预演跳过（无网络）"
        else:
            ql_ok = qinglong_notify(body[:1800])
            legacy_count = legacy_notify(body[:1800])
            notify_status = "青龙已发送" if ql_ok else "青龙不可用或发送失败"
            if legacy_count:
                notify_status += "；兼容渠道发送%d个" % legacy_count
    log("===== ModelScope 签到汇总 =====")
    for line in summary_lines:
        log(line)
    log("------------------------------")
    log("账号结果：总数%d，成功%d，失败%d" % (len(jobs), succeeded, failed))
    log("子任务结果：总数%d，成功%d，已完成%d，跳过%d，失败%d" % tuple(substats.values()))
    log("总耗时：%s；通知状态：%s" % (elapsed(started), notify_status))
    finish_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    log("完成时间：%s；最终状态：%s" % (finish_at, status))
    summary = {"task": "modelscope_daily", "mode": "dry-run" if dry else "live", "status": status,
               "accounts": {"total": len(jobs), "success": succeeded, "failed": failed},
               "subtasks": substats, "notification": notify_status, "exitCode": business_exit,
               "startedAt": start_at, "finishedAt": finish_at}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return business_exit


if __name__ == "__main__":
    sys.exit(main())
