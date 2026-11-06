# -*- coding: utf-8 -*-
# name: 联想商城每日签到
# cron: 22 10 * * *
# SPDX-License-Identifier: Apache-2.0
# Derived from fukfsa/lenovo_auto_signin_zyc, main.py
# https://github.com/fukfsa/lenovo_auto_signin_zyc
# Original notices:
# @Time : 2021/1/24 0:27
# @Auther : cmodog
# @File : main.py
# @Software: PyCharm
"""联想商城登录、签到、查询连续天数。仅使用 Python 标准库。

LENOVO_ACCOUNTS：每个非空行一个 账号|密码，只在第一个 | 分割。
账号密码取自本人联想账号；密码含 | 时仍完整保留，账号不能含 |。
未设置该变量时兼容单账号 USERNAME、PASSWORD，不打印这些值。
LENOVO_DRY_RUN=1 完全断网，仅验证配置和执行流程。
LENOVO_TICKET 是上游共享的业务 ticket 参数，可从本人官方网页登录
请求中的 ticket/sts 字段核对；默认保留上游值，不沿用上游固定 Cookie。
PUSH_KEY 为可选的旧版 Server 酱密钥；推荐使用青龙统一通知。
上游没有定时声明，此处建议每日北京时间 08:15，依赖青龙所在时区。
不重试签到写请求，避免网络不确定时重复操作。
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
        _ql_notify_identities = ('293255e8d83b79db', 'scripts/task_293255e8.py', 'task_293255e8.py', 'task_293255e8')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib import error, parse, request

TITLE = "联想商城每日签到"
CATALOG = "293255e8d83b79db"
TICKET = "e40e7004-4c8a-4963-8564-31271a8337d8"  # 上游业务参数，不是登录 Cookie
UA = "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/86.0.4240.185 Mobile Safari/537.36/lenovoofficialapp/16112154380982287_10181446134/newversion/versioncode-124/"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def scrub(value, secrets):
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[已脱敏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    return " ".join(text.split())[:160]


def accounts_from_env():
    if "LENOVO_ACCOUNTS" in os.environ:
        lines = [line for line in os.environ["LENOVO_ACCOUNTS"].splitlines() if line.strip()]
        accounts = []
        for line in lines:
            user, sep, password = line.partition("|")
            accounts.append((user.strip(), password) if sep else ("", ""))
        return accounts
    if os.getenv("USERNAME") or os.getenv("PASSWORD"):
        return [(os.getenv("USERNAME", ""), os.getenv("PASSWORD", ""))]
    return []


class SafeRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = parse.urlparse(newurl)
        host = target.hostname or ""
        if target.scheme != "https" or not (host == "lenovo.com.cn" or host.endswith(".lenovo.com.cn")):
            raise TaskError("拒绝非官方或非 HTTPS 跳转")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookies), SafeRedirect())

    def fetch(self, url, fields=None):
        data = parse.urlencode(fields).encode() if fields is not None else None
        req = request.Request(url, data=data, headers={"User-Agent": UA, "Referer": "https://www.lenovo.com.cn/"})
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError("官方接口 HTTP 状态异常")
                payload = response.read(1048577)
                if len(payload) > 1048576:
                    raise TaskError("官方响应超过大小限制")
                charset = response.headers.get_content_charset() or "utf-8"
                return payload.decode(charset)
        except (error.URLError, OSError, ValueError, UnicodeError, LookupError):
            raise TaskError("请求失败、超时或响应编码无效") from None


def json_object(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        raise TaskError("接口未返回可核验的 JSON，可能需要验证码或接口已变更") from None


def identity(payload, secrets):
    if not isinstance(payload, dict):
        return None
    for obj in (payload, payload.get("data"), payload.get("user")):
        if isinstance(obj, dict):
            for key in ("nickname", "nickName", "displayName", "username", "publicUid", "uid"):
                if isinstance(obj.get(key), (str, int)) and not isinstance(obj.get(key), bool):
                    return scrub(obj[key], secrets)
    return None


def check_sign(text):
    payload = json_object(text)
    # 上游仅依据 true 和“乐豆”判定。这里要求结构化布尔成功与明确业务结果，
    # 不将任意包含 true 的页面或所有无“乐豆”的响应误报为重复签到。
    positive = payload is True or (isinstance(payload, dict) and any(
        payload.get(key) is True for key in ("success", "result", "status")))
    if not positive:
        raise TaskError("签到响应没有明确布尔成功标记")
    message = json.dumps(payload, ensure_ascii=False)
    if any(word in message for word in ("已签到", "已经签到", "重复签到", "已签过")):
        return "already"
    if "乐豆" in message and not any(word in message for word in ("失败", "未登录", "异常")):
        return "success"
    raise TaskError("签到结果不明确，不能确认奖励或今日已完成")


class DaysParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "p" and "signInTimeMiddleBtn" in dict(attrs).get("class", "").split():
            self.capture = True

    def handle_endtag(self, tag):
        if tag == "p":
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def read_days(text):
    parser = DaysParser()
    parser.feed(text)
    label = " ".join("".join(parser.parts).split())
    match = re.search(r"(?:连续|累计|已)?\s*签到\s*(\d+)\s*天", label)
    if not match:
        match = re.fullmatch(r"\s*(\d+)\s*(?:天)?\s*", label)
    if not match:
        raise TaskError("连续签到天数节点缺失或格式已变更")
    return int(match.group(1))


def run_account(index, account, dry_run, ticket):
    started = time.monotonic()
    result = {"account": index, "total": 3, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    user, password = account
    failed = False
    client = None
    for stage, name in enumerate(("登录", "每日签到", "查询连续签到天数"), 1):
        tick = time.monotonic()
        detail = ""
        state = "success"
        try:
            if failed:
                state, detail = "skipped", "前置步骤未完成"
            elif not user or not password:
                raise TaskError("缺少账号或密码；请检查 LENOVO_ACCOUNTS 或兼容变量")
            elif dry_run:
                state, detail = "skipped", "离线预演：配置有效，不发起请求、不签到"
            elif stage == 1:
                client = Client()
                body = client.fetch("https://reg.lenovo.com.cn/auth/v3/dologin", {"account": user, "password": password, "ticket": ticket})
                if not any(c.name == "cerpreg-passport" and c.value and (c.domain.lstrip(".") == "lenovo.com.cn" or c.domain.endswith(".lenovo.com.cn")) for c in client.cookies):
                    raise TaskError("登录未获得有效会话；请核对密码、业务 ticket 或验证码要求")
                detail = "获得官方登录会话"
                try:
                    who = identity(json.loads(body), (password, ticket, os.getenv("PUSH_KEY", "")))
                    if who:
                        detail += f"；官方身份：{who}"
                except (ValueError, TypeError):
                    pass
            elif stage == 2:
                body = client.fetch("https://i.lenovo.com.cn/signIn/add.jhtml?" + parse.urlencode({"sts": ticket}))
                state = check_sign(body)
                detail = "今日已签到" if state == "already" else "签到成功，响应包含乐豆结果"
            else:
                days = read_days(client.fetch("https://club.lenovo.com.cn/signlist/"))
                detail = f"连续签到 {days} 天"
                result["days"] = days
        except TaskError as exc:
            state, detail, failed = "failed", str(exc), True
        except Exception:
            state, detail, failed = "failed", "处理响应失败，已隐藏异常内容", True
        result[state] += 1
        log(f"账号 {index} · 阶段 {stage}/3 {name} · {state} · {detail} · 耗时 {time.monotonic() - tick:.2f} 秒")
    result["ok"] = not failed
    result["seconds"] = round(time.monotonic() - started, 2)
    log(f"账号 {index} 统计：总任务 3，成功 {result['success']}，已完成 {result['already']}，跳过 {result['skipped']}，失败 {result['failed']}，耗时 {result['seconds']} 秒")
    return result


def notify(summary, dry_run):
    switch = os.getenv("QINGLONG_NOTIFY", "auto").lower().strip()
    if switch in FALSE:
        return "已全局关闭"
    if dry_run:
        return "离线预演：已生成通知摘要，禁止网络投递"
    selected = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    names = (CATALOG, "candidate.py", Path(__file__).name, "scripts/" + Path(__file__).name)
    enabled = switch in TRUE if selected is None else any(
        fnmatch.fnmatch(name, pattern) for pattern in re.split(r"[,;\s]+", selected.strip()) if pattern for name in names)
    body = f"账号总数 {summary['accounts']}，成功 {summary['succeeded']}，失败 {summary['failed']}；状态 {summary['status']}。"
    body += " 子任务成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}。".format(**summary["tasks"])
    statuses = []
    if enabled:
        # 在子进程中执行通知，屏蔽通知模块可能输出的凭据和原始响应。
        program = "import importlib.util,sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location('qinglong_notify',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])"
        directories = [os.getenv("QINGLONG_NOTIFY_DIR"), "/ql/data/scripts", "/ql/scripts"]
        candidates = []
        try:
            spec = importlib.util.find_spec("notify")
            if spec and spec.origin:
                candidates.append(Path(spec.origin))
        except (ImportError, ValueError):
            pass
        candidates.extend(Path(d) / "notify.py" for d in directories if d)
        delivered = False
        for path in dict.fromkeys(candidates):
            if not path.is_file():
                continue
            try:
                proc = subprocess.run([sys.executable, "-c", program, str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                if proc.returncode == 0:
                    delivered = True
                    break
            except (OSError, subprocess.SubprocessError):
                pass
        if not delivered:
            for directory in directories:
                path = Path(directory) / "sendNotify.js" if directory else None
                if path and path.is_file():
                    try:
                        proc = subprocess.run(["node", "-e", "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))", str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                        if proc.returncode == 0:
                            delivered = True
                            break
                    except (OSError, subprocess.SubprocessError):
                        pass
        statuses.append("青龙通知已调用" if delivered else "青龙通知不可用或失败，保留业务退出码")
    else:
        statuses.append("未列入青龙通知名单")
    key = os.getenv("PUSH_KEY", "")
    if key:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            statuses.append("旧版推送密钥格式无效")
        else:
            try:
                days = [f"账号 {r['account']}：连续签到 {r['days']} 天" for r in summary["results"] if "days" in r]
                payload = json_object(Client().fetch("https://sc.ftqq.com/" + key + ".send", {"text": TITLE, "desp": body + "\n" + "\n".join(days)}))
                if not isinstance(payload, dict) or not any(type(payload.get(k)) is int and payload[k] == 0 for k in ("errno", "code")):
                    raise TaskError("推送未确认")
                statuses.append("旧版推送成功")
            except Exception:
                statuses.append("旧版推送失败，保留业务退出码")
    return "；".join(statuses)


def main():
    started = time.monotonic()
    start_time = datetime.now().astimezone().isoformat(timespec="seconds")
    dry_run = os.getenv("LENOVO_DRY_RUN", "0").lower().strip() in TRUE
    accounts = accounts_from_env()
    log(f"========== {TITLE} ==========\n开始时间：{start_time}\n运行模式：{'离线预演' if dry_run else '正式执行'}\n账号数：{len(accounts)}")
    results = []
    ticket = os.getenv("LENOVO_TICKET", TICKET).strip()
    configuration_error = not accounts or not ticket
    if configuration_error:
        log("配置错误：未提供账号或业务 ticket 为空")
    else:
        results = [run_account(i, account, dry_run, ticket) for i, account in enumerate(accounts, 1)]
    succeeded = sum(r["ok"] for r in results)
    failed = len(accounts) - succeeded
    code = 1 if configuration_error or failed else 0
    status = "configuration-error" if configuration_error else ("partial-failure" if failed and succeeded else "failure" if failed else "dry-run" if dry_run else "success")
    summary = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts": len(accounts), "succeeded": succeeded, "failed": failed,
               "tasks": {k: sum(r[k] for r in results) for k in ("total", "success", "already", "skipped", "failed")}, "results": results, "exitCode": code, "startTime": start_time}
    try:
        notification = notify(summary, dry_run)
    except Exception:
        notification = "通知异常，保留业务退出码"
    summary.update(notification=notification, seconds=round(time.monotonic() - started, 2), finishTime=datetime.now().astimezone().isoformat(timespec="seconds"))
    log(f"--------------------\n账号统计：总数 {len(accounts)}，成功 {succeeded}，失败 {failed}\n子任务统计：{json.dumps(summary['tasks'], ensure_ascii=False)}\n总耗时：{summary['seconds']} 秒\n完成时间：{summary['finishTime']}\n通知状态：{notification}\n最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
