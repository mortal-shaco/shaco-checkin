#!/usr/bin/env python3
# name: 今日校园东北大学秦皇岛分校签到
# cron: 47 10 * * *
# SPDX-License-Identifier: GPL-3.0
# Derived from imyhui/cpdaily-auto main.py, commit 621efa5e212e3b1978cb5ad03dcf9b2ff3bc93ea.
# Upstream: https://github.com/imyhui/cpdaily-auto (GPL-3.0)
"""独立维护版本。账号使用 CPDAILY_ACCOUNTS，每个非空行是一个 JSON 对象。

Cookie 方式：cookie 为本人在官方签到页面请求中的 Cookie。
密码方式：username/password 为本校统一认证账号，使用 HTTPS 登录；不降级 HTTP。
位置字段 longitude/latitude/position 来自本人实际签到地点，extension 来自本人
官方客户端 submitSign 请求头 Cpdaily-Extension，禁止使用他人设备数据。
可选 isMalposition 为 0/1；设为 1 时必须提供真实 abnormalReason。
默认仅查询；CPDAILY_SUBMIT=1 才提交第一个待签到任务。CPDAILY_DRY_RUN=1 完全断网。
建议每天 08:00，须依学校任务开放时间调整。无需 config.py 或私有仓库。
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
        _ql_notify_identities = ('d941771d29760d88', 'scripts/task_d941771d.py', 'task_d941771d.py', 'task_d941771d')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

TITLE = "今日校园东北大学秦皇岛分校签到"
CATALOG = "d941771d29760d88"
BASE = "https://neuq.cpdaily.com"
LOGIN = "https://ids.neuq.edu.cn/authserver/login?service=https%3A%2F%2Fneuq.cpdaily.com%2Fportal%2Flogin"
API = BASE + "/wec-counselor-sign-apps/stu/sign/"
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}
UA = "Mozilla/5.0 cpdaily/8.1.11 wisedu/8.1.11"


class TaskError(Exception):
    pass


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def flag(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f"{name} 必须为 0 或 1")
    return value in TRUE


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.unsupported = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "input" and data.get("type", "").lower() == "hidden" and data.get("name"):
            self.hidden[data["name"]] = data.get("value", "")
        if data.get("id", "") in {"pwdEncryptSalt", "pwdDefaultEncryptSalt", "captchaResponse"}:
            self.unsupported = True


def safe_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"neuq.cpdaily.com", "ids.neuq.edu.cn"}
            or parsed.username or parsed.password or parsed.port not in {None, 443}):
        raise TaskError("认证跳转目标不安全，已停止")


def request(session, method, url, **kwargs):
    # 不打印异常内容、URL 查询参数、响应正文或请求头。
    for _ in range(8):
        safe_url(url)
        try:
            response = session.request(method, url, timeout=(10, 20), allow_redirects=False,
                                       stream=True, **kwargs)
            with response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    destination = urljoin(url, response.headers.get("Location", ""))
                    safe_url(destination)
                    if method != "GET" and response.status_code in {307, 308}:
                        raise TaskError("拒绝重放携带凭据或签到数据的重定向请求")
                    url, method, kwargs = destination, "GET", {}
                    continue
                if not 200 <= response.status_code < 300:
                    raise TaskError(f"HTTP 请求失败（状态 {response.status_code}）")
                content = bytearray()
                for chunk in response.iter_content(8192):
                    content.extend(chunk)
                    if len(content) > 2 * 1024 * 1024:
                        raise TaskError("响应过大，已停止")
                return bytes(content).decode("utf-8", errors="replace")
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络、TLS 或超时错误，请在官方客户端核验") from None
    raise TaskError("认证重定向次数超限")


def api(session, action, body, headers=None):
    text = request(session, "POST", API + action, json=body, headers=headers or {})
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise TaskError("接口未返回 JSON，可能需要重新认证") from None
    if not isinstance(data, dict) or data.get("message") != "SUCCESS":
        raise TaskError("接口未明确返回 SUCCESS，业务失败")
    if "code" in data and str(data["code"]) != "0":
        raise TaskError("接口业务码非零，业务失败")
    return data


def accounts():
    lines = [line.strip() for line in os.environ.get("CPDAILY_ACCOUNTS", "").splitlines() if line.strip()]
    if not lines:
        raise TaskError("缺少 CPDAILY_ACCOUNTS；请按说明填写每行一个账号的 JSON")
    return lines


def parse_account(line, submit):
    try:
        account = json.loads(line)
    except ValueError:
        raise TaskError("账号行必须为有效 JSON 对象") from None
    if not isinstance(account, dict):
        raise TaskError("账号行必须为 JSON 对象")
    cookie = account.get("cookie")
    if cookie:
        if not isinstance(cookie, str) or "=" not in cookie or any(c in cookie for c in "\r\n"):
            raise TaskError("cookie 格式错误")
    elif not all(isinstance(account.get(k), str) and account[k] for k in ("username", "password")):
        raise TaskError("每个账号需提供 cookie，或成对提供 username/password")
    if submit:
        for key, bound in (("longitude", 180), ("latitude", 90)):
            try:
                value = float(account[key])
                if isinstance(account[key], bool) or not math.isfinite(value) or abs(value) > bound:
                    raise ValueError()
            except (KeyError, ValueError, TypeError, OverflowError):
                raise TaskError(f"{key} 必须为真实有效坐标") from None
        for key in ("position", "extension"):
            if not isinstance(account.get(key), str) or not account[key].strip() or any(c in account[key] for c in "\r\n"):
                raise TaskError(f"提交签到必须提供本人有效的 {key}")
        try:
            account["extension"].encode("ascii")
        except UnicodeEncodeError:
            raise TaskError("extension 必须为官方请求头中的 ASCII 值") from None
        malposition = account.get("isMalposition", 0)
        if type(malposition) is not int or malposition not in (0, 1):
            raise TaskError("isMalposition 必须为整数 0 或 1")
        if malposition and not str(account.get("abnormalReason", "")).strip():
            raise TaskError("异常位置签到必须填写真实 abnormalReason")
    return account


def authenticate(session, account):
    if account.get("cookie"):
        # 绑定学校域名；重定向到认证域时不转发手动 Cookie。
        for item in account["cookie"].split(";"):
            key, sep, value = item.strip().partition("=")
            if sep and key:
                session.cookies.set(key, value, domain="neuq.cpdaily.com", path="/")
        return
    form = LoginForm()
    html = request(session, "GET", LOGIN)
    form.feed(html)
    if form.unsupported or not form.hidden or re.search(r"pwd(?:Default)?EncryptSalt|encryptAES|encryptPassword", html):
        raise TaskError("登录页面需要新的加密或验证码流程；请使用本人官方 Cookie")
    payload = dict(form.hidden)
    payload.update(username=account["username"], password=account["password"])
    request(session, "POST", LOGIN, data=payload)
    if not any(c.name == "MOD_AUTH_CAS" and c.domain.lstrip(".") == "neuq.cpdaily.com" for c in session.cookies):
        raise TaskError("未取得学校认证会话；请检查凭据或使用本人官方 Cookie")


def run_account(account, submit, dry, stats):
    stages = [("认证", None), ("查询今日签到", None), ("提交并核验首个待签到任务", None)]
    session = None
    task_id = None
    index = 0
    started = time.monotonic()
    try:
        if not dry:
            try:
                import requests
            except ImportError:
                raise TaskError("缺少公共依赖 requests，请通过青龙依赖管理安装") from None
            session = requests.Session()
            session.trust_env = False
            session.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                                    "Origin": BASE, "X-Requested-With": "XMLHttpRequest",
                                    "Referer": BASE + "/wec-counselor-sign-apps/stu/mobile/index.html"})
        for index, (name, _) in enumerate(stages, 1):
            started = time.monotonic()
            log(f"阶段 {index}/3：{name}")
            if dry:
                stats["skipped"] += 1
                log(f"⏭️ 阶段 {index} 参数检查通过，断网跳过（{time.monotonic()-started:.2f}秒）")
                continue
            if index == 1:
                authenticate(session, account)
            elif index == 2:
                data = api(session, "getStuSignInfosInOneDay", {})
                datas = data.get("datas")
                if not isinstance(datas, dict) or not isinstance(datas.get("unSignedTasks"), list):
                    raise TaskError("查询响应缺少待签到任务列表")
                # 不输出认证用户名、设备信息、电话或原始响应。
                for key in ("nickname", "userName", "displayName", "publicUid"):
                    identity = datas.get(key)
                    if isinstance(identity, (str, int)) and str(identity).strip():
                        value = str(identity)
                        secrets = [str(account.get(k, "")) for k in ("cookie", "password", "extension")]
                        if not any(s and s in value for s in secrets) and not re.search(r"\b1[3-9]\d{9}\b", value):
                            log("官方账号身份：" + json.dumps(value, ensure_ascii=False))
                pending = datas["unSignedTasks"]
                if pending:
                    first = pending[0]
                    if not isinstance(first, dict) or not first.get("signInstanceWid"):
                        raise TaskError("待签到任务缺少实例编号")
                    task_id = first["signInstanceWid"]
                    log(f"待签到任务数：{len(pending)}；沿用上游每轮处理首个任务")
                else:
                    log("☑️ 当前无待签到任务（不将空列表宣称为今天已签到）")
            elif not submit or task_id is None:
                stats["skipped"] += 1
                log(f"⏭️ 阶段 3 跳过：{'只读模式' if not submit else '无待签到任务'}（{time.monotonic()-started:.2f}秒）")
                continue
            else:
                body = {"signInstanceWid": task_id, "longitude": account["longitude"],
                        "latitude": account["latitude"], "position": account["position"],
                        "isMalposition": account.get("isMalposition", 0),
                        "abnormalReason": account.get("abnormalReason", ""), "signPhotoUrl": ""}
                api(session, "submitSign", body, {"CpdailyStandAlone": "0", "extension": "1",
                                               "Cpdaily-Extension": account["extension"]})
                verified = api(session, "getStuSignInfosInOneDay", {}).get("datas", {})
                remaining = verified.get("unSignedTasks") if isinstance(verified, dict) else None
                if not isinstance(remaining, list) or any(not isinstance(t, dict) or "signInstanceWid" not in t for t in remaining):
                    raise TaskError("提交已获 SUCCESS，但复查数据结构异常；请在官方客户端核验")
                if any(str(t["signInstanceWid"]) == str(task_id) for t in remaining):
                    raise TaskError("提交已获 SUCCESS，但任务仍待签到；请在官方客户端核验")
                log("✅ 签到成功：接口确认且目标已离开待签到列表")
            stats["success"] += 1
            log(f"✅ 阶段 {index} 成功（{time.monotonic()-started:.2f}秒）")
    except TaskError:
        log(f"❌ 阶段 {index} 失败（{time.monotonic()-started:.2f}秒）；后续阶段停止")
        raise
    finally:
        if session is not None:
            session.close()


def notify(body):
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE:
        return "已关闭"
    if switch not in TRUE | {"auto"}:
        return "通知开关无效，未发送"
    if switch == "auto":
        selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
        names = (CATALOG, Path(__file__).name, "scripts/" + Path(__file__).name)
        if not any(s and any(fnmatch.fnmatchcase(n, s) for n in names) for s in selectors):
            return "未被通知名单选中"
    # 在独立子进程中执行青龙通知，超时或失败不改变业务退出码，不回显通知模块输出。
    code = """import importlib, importlib.util, os, pathlib, sys
title, body = sys.argv[1:3]
try:
    module = importlib.import_module('notify')
except ImportError:
    module = None
if module is not None and callable(getattr(module, 'send', None)):
    module.send(title, body)
    sys.exit(0)
paths = []
if os.environ.get('QINGLONG_NOTIFY_DIR'):
    paths.append(pathlib.Path(os.environ['QINGLONG_NOTIFY_DIR']))
paths += [pathlib.Path('/ql/data/scripts'), pathlib.Path('/ql/scripts')]
for root in paths:
    path = root / 'notify.py'
    if path.is_file():
        spec = importlib.util.spec_from_file_location('ql_notify', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.send(title, body)
        sys.exit(0)
    js = root / 'sendNotify.js'
    if js.is_file():
        import subprocess
        sys.exit(subprocess.run(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(js), title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode)
sys.exit(2)
"""
    try:
        result = subprocess.run([sys.executable, "-c", code, TITLE, body], timeout=30,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "已发送" if result.returncode == 0 else "通知不可用或发送失败"
    except Exception:
        return "通知不可用或超时"


def main():
    start = time.monotonic()
    started_at = datetime.now().isoformat(timespec="seconds")
    dry = os.environ.get("CPDAILY_DRY_RUN", "0").strip().lower() in TRUE
    summary = {"task": TITLE, "mode": "dry-run" if dry else "live", "accounts": 0,
               "success": 0, "failed": 0, "configurationErrors": 0,
               "tasks": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}}
    log("========== " + TITLE + " ==========")
    log(f"开始时间：{started_at}；模式：{'断网预演' if dry else '正式'}")
    results = []
    try:
        dry = flag("CPDAILY_DRY_RUN")
        submit = flag("CPDAILY_SUBMIT")
        lines = accounts()
        summary["accounts"] = len(lines)
        log(f"账号数量：{len(lines)}；动作：{'允许提交' if submit else '仅查询'}")
        for number, line in enumerate(lines, 1):
            account_start = time.monotonic()
            stats = {"total": 3, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0}
            log(f"----- 账号 {number} -----")
            try:
                account = parse_account(line, submit)
                run_account(account, submit, dry, stats)
                summary["success"] += 1
            except TaskError as exc:
                stats["failed"] += 1
                log(f"❌ 账号 {number}：{exc}")
                summary["failed"] += 1
            except Exception:
                stats["failed"] += 1
                log(f"❌ 账号 {number}：未预期的响应或运行错误（详情已脱敏）")
                summary["failed"] += 1
            stats["skipped"] += max(0, stats["total"] - sum(stats[k] for k in ("success", "alreadyComplete", "skipped", "failed")))
            for key in summary["tasks"]:
                summary["tasks"][key] += stats[key]
            results.append({"account": number, **stats})
            log(f"账号 {number} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {time.monotonic()-account_start:.2f}秒")
    except TaskError as exc:
        summary["configurationErrors"] += 1
        log(f"❌ 配置错误：{exc}")
        log(f"账号数量：{summary['accounts']}")
    code = 1 if summary["failed"] or summary["configurationErrors"] else 0
    status = "configuration-error" if summary["configurationErrors"] else ("partial-failure" if summary["failed"] and summary["success"] else "failure" if code else "dry-run" if dry else "success")
    summary.update(status=status, accountResults=results, startTime=started_at,
                   finishTime=datetime.now().isoformat(timespec="seconds"), elapsedSeconds=round(time.monotonic()-start, 2))
    body = f"状态 {status}；账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；配置错误 {summary['configurationErrors']}。"
    if dry:
        log("DRY_RUN_OK" if not code else "DRY_RUN_FAILED")
        log("断网预演：不调用业务、随机文本或通知网络")
        summary["notification"] = "断网预演：仅生成通知摘要，未发送"
    else:
        summary["notification"] = notify(body)
    log("----------------------------------------")
    log(body)
    log("子任务统计：" + json.dumps(summary["tasks"], ensure_ascii=False))
    log(f"完成时间：{summary['finishTime']}；耗时 {summary['elapsedSeconds']}秒；通知：{summary['notification']}；最终状态：{status}")
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
