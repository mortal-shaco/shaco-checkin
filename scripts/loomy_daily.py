#!/usr/bin/env python3
# name: Loomy 每日积分与新手任务
# cron: 54 0 * * *
# 来源: L0NE-6/Loomy-Daily, loomy_daily.py
# 上游提交: 3d0f19b0b6486ff9096507805a5f9d061604058f
# SPDX-License-Identifier: MIT
# 上游提供的两个 Python 源文件没有额外版权或许可证正文。
"""
Loomy 每日积分与新手任务。仅依赖 Python 标准库。
LOOMY_TOKENS 必填，每个非空行一个账号：session 或 备注|session。
仅在第一个 | 处分割；不使用 & 或 @ 分隔账号。
在官方 Loomy 客户端登录，在本人授权的开发者工具/网络请求中获取
loomyad.xunfei.cn 请求的 token 头或 Authorization: Bearer 后的 session。
不要分享凭据。失效后在官方客户端重新登录并更新环境变量。
默认只 POST 每日积分刷新（按天幂等），不虚报八项新手任务完成。
仅在实际完成任务并确认领取时设 LOOMY_ONBOARDING=1 批量领取；
LOOMY_ONBOARDING=0 或 --no-onboarding 禁用批量领取。
--tasks 查询八项进度；--claim KEY 显式单项领取；--refresh 强制查询；
--only N 只运行第 N 个账号；--no-notify 禁用通知。
八项结清后写入脚本旁 loomy_onboarding.json，只存凭据指纹和进度。
LOOMY_DRY_RUN=1 完全断网、无结算文件写入、仅演练通知。
QINGLONG_NOTIFY=0 全局关闭推送。QINGLONG_NOTIFY_DIR 指向青龙通知目录。
保留可选 PUSHPLUS_TOKEN、BARK_URL、WECOM_WEBHOOK、DINGTALK_WEBHOOK、
DINGTALK_SECRET 推送通道；不再通过含 token 的青龙 URL API 推送。
上游未指定 cron，维护版本建议每天 08:00，用户可在青龙修改。
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
        _ql_notify_identities = ('5e0e668122f2807b', 'scripts/loomy_daily.py', 'loomy_daily.py', 'loomy_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import hashlib
import hmac
import json
import os
import sys
import time

import urllib.request
import urllib.error
import urllib.parse



try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

BASE = "https://loomyad.xunfei.cn"
FIRST_LOGIN_PATH = "/api/v1/points/first-login"
TASKS_PATH = "/api/v1/onboarding/tasks"
COMPLETE_PATH = "/api/v1/onboarding/tasks/complete"
SUCCESS_CODE = "000000"
AUTH_ERROR_CODES = ("020002", "100002")

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loomy_onboarding.json")
TOTAL_POINTS = 10000

TASKS = [
    ("初识 Loomy", "first_message", "发送你的第一条消息", 500),
    ("初识 Loomy", "pick_skill", "试试选择一个技能", 1000),
    ("初识 Loomy", "generate_ppt", "生成第一份 PPT", 1500),
    ("打造你的专属 Loomy", "set_schedule", "设置定时任务", 1000),
    ("打造你的专属 Loomy", "install_skill", "在技能广场安装一个技能", 1500),
    ("打造你的专属 Loomy", "configure_remote", "配置远程控制", 1000),
    ("遇见你的 AI 搭子", "create_soul", "创建你的第一个搭子", 1500),
    ("遇见你的 AI 搭子", "share_soul", "把搭子分享给朋友", 2000),
]

ONLY = None
NO_ONBOARDING = False
NO_NOTIFY = False
FORCE_REFRESH = False


def log(msg):
    msg = redact(msg)
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload

    def json(self):
        return self.payload


def http_json(method, url, headers=None, body=None, timeout=20):
    if DRY_RUN:
        raise RuntimeError("预演禁止网络请求")
    if not url.startswith("https://"):
        raise RuntimeError("只允许 HTTPS 请求")
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # 系统 CA 校验；不继承代理；不允许重定向泄漏凭据；有界读取。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as answer:
            if not 200 <= answer.status < 300:
                raise RuntimeError("HTTP 请求失败")
            raw = answer.read(1048577)
            if len(raw) > 1048576:
                raise RuntimeError("响应超过大小限制")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("响应结构异常")
            return Response(answer.status, payload)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("网络请求失败或超时") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("响应不是有效 JSON") from None


def request(method, url, headers=None, body=None, timeout=20, retries=1):
    response = http_json(method, url, headers, body, timeout)
    show_identity(response.json())
    return response


def json_of(response):
    try:
        return response.json()
    except Exception:
        return {}


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def token_headers(session_token):
    return {"token": session_token, "Authorization": "Bearer %s" % session_token}


def business_code(payload):
    return str(payload.get("code") or "").strip()


def upstream_message(payload):
    # 不转发可能包含凭据、手机号或服务端回显的消息。
    return "服务端未确认业务成功"


# ---------- 上游协议 ----------

def first_login(session_token):
    response = request("POST", BASE + FIRST_LOGIN_PATH, headers=token_headers(session_token),
                       body={}, timeout=20)
    payload = json_of(response)
    code = business_code(payload)
    if response.status_code in (401, 403) or code in AUTH_ERROR_CODES:
        raise RuntimeError("登录状态失效，重新登录一下吧该账号")
    if code != SUCCESS_CODE:
        message = upstream_message(payload) or "服务端未确认业务成功"
        return False, "每日积分刷新失败：%s" % message
    balance = None
    data = payload.get("data")
    if isinstance(data, dict):
        balance = data.get("dailyBalance")
        if balance is None and isinstance(data.get("data"), dict):
            balance = data["data"].get("dailyBalance")
    if isinstance(balance, bool) or not isinstance(balance, (int, float)):
        balance = None
    return True, ("每日赠送积分已刷新（当前 %s）" % balance) if balance is not None else "每日赠送积分已刷新"


def token_fp(session_token):
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()[:16]


# ---------- 新手任务结算记录（一次性福利，领完不再重复查询） ----------

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
    except Exception as error:
        log("⚠️ 新手任务结算记录写入失败")


def settled_snapshot(state, session_token):
    snapshot = state.get(token_fp(session_token))
    if not isinstance(snapshot, dict):
        return None
    rows = snapshot.get("tasks")
    if not isinstance(rows, list) or len(rows) != len(TASKS):
        return None
    expected, earned, unclaimed = task_rows({key: True for _, key, _, _ in TASKS})
    if rows != expected or snapshot.get("earned") != earned or snapshot.get("total") != TOTAL_POINTS:
        return None
    return snapshot


def settled_view(snapshot):
    return {"tasks": snapshot.get("tasks"), "earned": snapshot.get("earned"),
            "total": snapshot.get("total"), "unclaimed": 0, "settled": True,
            "settledAt": snapshot.get("at"), "fromMemory": True}


def remember(state, session_token, payload, previous):
    """按响应结论同步本地记录：结清就记住，出现待领就清掉旧记录。"""
    fingerprint = token_fp(session_token)
    if payload.get("settled"):
        at = previous.get("at") if previous and previous.get("tasks") == payload.get("tasks") else None
        if not isinstance(at, (int, float)):
            at = int(time.time() * 1000)
        state[fingerprint] = {"at": at, "tasks": payload.get("tasks"),
                              "earned": payload.get("earned"), "total": payload.get("total")}
        save_state(state)
        payload["settledAt"] = at
    elif fingerprint in state:
        del state[fingerprint]
        save_state(state)


def task_rows(done):
    rows, earned, unclaimed = [], 0, 0
    for group, key, title, points in TASKS:
        is_done = bool(done.get(key))
        if is_done:
            earned += points
        else:
            unclaimed += 1
        rows.append({"key": key, "title": title, "group": group,
                     "points": points, "done": is_done})
    return rows, earned, unclaimed


def fetch_onboarding(session_token):
    """查询任务清单与进度：key / 标题 / 分组 / 分值 / 是否完成，一次只读。"""
    response = request("GET", BASE + TASKS_PATH, headers=token_headers(session_token))
    payload = json_of(response)
    code = business_code(payload)
    if response.status_code in (401, 403) or code in AUTH_ERROR_CODES:
        raise RuntimeError("登录状态失效，重新登录一下吧该账号")
    if code != SUCCESS_CODE:
        raise RuntimeError("新手任务查询失败：%s" % upstream_message(payload))
    raw = ((payload.get("data") or {}).get("tasks") or {}) if isinstance(payload.get("data"), dict) else {}
    if not isinstance(raw, dict) or any(not isinstance(raw.get(key), bool) for _, key, _, _ in TASKS):
        raise RuntimeError("新手任务响应缺少有效的完成状态")
    done = {key: raw.get(key) is True for _group, key, _title, _points in TASKS}
    rows, earned, unclaimed = task_rows(done)
    return {"tasks": rows, "earned": earned, "total": TOTAL_POINTS,
            "unclaimed": unclaimed, "settled": unclaimed == 0}


def claim_task(session_token, key):
    """上报单个任务 key。返回 (成功, 此前已完成, 失败原因)。"""
    response = request("POST", BASE + COMPLETE_PATH, headers=token_headers(session_token),
                       body={"key": key})
    payload = json_of(response)
    code = business_code(payload)
    if response.status_code in (401, 403) or code in AUTH_ERROR_CODES:
        raise RuntimeError("登录状态失效，重新登录一下吧该账号")
    if code != SUCCESS_CODE:
        return False, False, upstream_message(payload) or "服务端未确认业务成功"
    data = payload.get("data")
    already = bool(isinstance(data, dict) and data.get("alreadyCompleted") is True)
    return True, already, ""


def onboarding_view(session_token, refresh=False):
    """清单查询入口：已结清直接给本地记录（零请求），否则实查并同步记录。"""
    state = load_state()
    previous = settled_snapshot(state, session_token)
    if previous and not refresh:
        return settled_view(previous)
    payload = fetch_onboarding(session_token)
    remember(state, session_token, payload, previous)
    return payload


def claim_onboarding(session_token, refresh=False):
    """一键领取未完成任务。返回 (新到账摘要, 失败列表, 明细)。"""
    state = load_state()
    previous = settled_snapshot(state, session_token)
    if previous and not refresh:
        return [], [], settled_view(previous)
    before = fetch_onboarding(session_token)
    done = {row["key"]: row["done"] for row in before["tasks"]}
    newly, failed, results = [], [], []
    claimed_points = 0
    for _group, key, title, points in TASKS:
        if done.get(key):
            continue
        try:
            ok, already, message = claim_task(session_token, key)
        except Exception as error:
            failed.append("%s(%s)" % (title, str(error)[:40]))
            results.append({"key": key, "ok": False, "error": str(error)[:80]})
            time.sleep(1.0)
            continue
        if not ok:
            failed.append("%s(%s)" % (title, message[:40]))
            results.append({"key": key, "ok": False, "error": message[:80]})
            time.sleep(1.0)
            continue
        done[key] = True
        claimed_points += 0 if already else points
        results.append({"key": key, "ok": True, "already": already, "points": points})
        newly.append("%s（此前已完成）" % title if already else "%s+%d" % (title, points))
        time.sleep(1.0)
    rows, earned, unclaimed = task_rows(done)
    payload = {"results": results,
               "claimed": len([row for row in results if row.get("ok")]),
               "failed": len(failed), "claimedPoints": claimed_points,
               "tasks": rows, "earned": earned, "total": TOTAL_POINTS,
               "unclaimed": unclaimed, "settled": unclaimed == 0}
    remember(state, session_token, payload, None)
    return newly, failed, payload


def claim_single(session_token, key, refresh=False):
    """单独领取某个 key（幂等上报，不依赖清单里那一行是否勾选）。"""
    state = load_state()
    previous = settled_snapshot(state, session_token)
    if previous and not refresh:
        return settled_view(previous)
    ok, already, message = claim_task(session_token, key)
    payload = {"key": key, "ok": ok, "already": already, "error": message}
    if ok:
        try:
            view = fetch_onboarding(session_token)
            remember(state, session_token, view, previous)
            payload.update(view)
        except Exception as error:
            payload["refreshError"] = str(error)[:80]
    return payload


def log_task_list(payload):
    log("   📋 新手任务进度：已得 %s / %s，待领 %s%s"
        % (payload.get("earned"), payload.get("total"), payload.get("unclaimed"),
           "（本地结算记录）" if payload.get("fromMemory") else ""))
    for row in payload.get("tasks") or []:
        log("      %s [%s] %s +%s" % ("✅" if row.get("done") else "⬜",
                                       row.get("group", ""), row.get("title"),
                                       row.get("points")))


def post_json(url, payload, timeout=20):
    return http_json("POST", url, body=payload, timeout=timeout)


def _env(name):
    return os.environ.get(name, "").strip()


def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json("https://www.pushplus.plus/send",
                           {"token": token, "title": title, "content": text, "template": "txt"})
        return str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "Loomy"})
        return json_of(answer).get("code") == 200
    except Exception:
        return False


def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("http"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": ("%s\n%s" % (title, content))[:2000]}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(secret.encode(), ("%s\n%s" % (stamp, secret)).encode(),
                              hashlib.sha256).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp, urllib.parse.quote(base64.b64encode(digest), safe=""))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False



# ---------- 维护版执行、统计和青龙通知 ----------
import argparse
import re
import subprocess
from pathlib import Path

DRY_RUN = os.environ.get("LOOMY_DRY_RUN", "0").lower() in ("1", "true", "yes", "on")
SECRETS = []


def redact(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[凭据已隐藏]")
    return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)


def show_identity(payload):
    # 只输出正式响应中允许的身份字段，不输出服务端消息或整个响应。
    data = payload.get("data")
    if not isinstance(data, dict):
        return
    for item in (data, data.get("data"), data.get("user"), data.get("userInfo")):
        if not isinstance(item, dict):
            continue
        for key in ("nickname", "username", "displayName", "userid", "uid"):
            value = item.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                log("官方账号身份 %s: %s" % (key, value))
                return


def parse_accounts(raw):
    accounts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        note, token = line.split("|", 1) if "|" in line else ("", line)
        token = token.strip()
        if token:
            SECRETS.append(token)
        accounts.append({"session": token, "valid": bool(token) and not any(c in token for c in "\r\n")})
    return accounts


def notify_ql(title, content):
    """通知组件是可选集成，独立业务执行不依赖它。"""
    directories = [os.environ.get("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    # 通知隔离在有超时的子进程中，禁止组件回显凭据或原始响应。
    program = """import sys, importlib.util
try:
    import notify
    result = notify.send(sys.argv[2], sys.argv[3])
except ImportError:
    spec = importlib.util.spec_from_file_location('loomy_ql_notify', sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.send(sys.argv[2], sys.argv[3])
sys.exit(1 if result is False else 0)
"""
    paths = [""] + [str(Path(d) / "notify.py") for d in directories if d and (Path(d) / "notify.py").is_file()]
    for path in paths:
        try:
            result = subprocess.run([sys.executable, "-c", program, path, title, content],
                                    timeout=30, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, check=False)
            if result.returncode == 0:
                return True
        except Exception:
            continue
    for directory in directories:
        if directory and (Path(directory) / "sendNotify.js").is_file():
            try:
                result = subprocess.run(
                    ["node", "-e", "require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]).catch(()=>process.exit(1))",
                     str(Path(directory) / "sendNotify.js"), title, content],
                    timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if result.returncode == 0:
                    return True
            except Exception:
                continue
    return False


def notify_all(title, content, disabled=False):
    if disabled or os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() in ("0", "false", "no", "off"):
        log("⏭️ 通知已关闭")
        return "disabled"
    if DRY_RUN:
        log("⏭️ dry-run 通知总结已生成；断网模式不调用通知组件")
        return "dry-run"
    if notify_ql(title, content):
        log("✅ 青龙通知已交付")
        return "sent"
    log("⚠️ 青龙通知组件不可用或发送失败")
    for handler in (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk):
        if handler(title, content):
            log("✅ 兼容推送通道已交付")
            return "fallback-sent"
    log("⚠️ 通知未交付；保留业务退出码")
    return "unavailable"


class ConfigurationError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ConfigurationError("命令行参数无效，请使用 --help 查看说明")


def main():
    started = time.monotonic()
    log("========== Loomy 每日积分与新手任务 ==========")
    log("开始时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("运行模式: " + ("dry-run（完全断网）" if DRY_RUN else "正式执行"))
    log("阶段0 参数检查开始")
    accounts = parse_accounts(os.environ.get("LOOMY_TOKENS", ""))
    log("账号总数: %d" % len(accounts))
    results = []
    totals = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
    config_error = False
    args = None
    try:
        parser = Parser(description=__doc__)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--tasks", action="store_true")
        mode.add_argument("--claim", choices=[row[1] for row in TASKS])
        parser.add_argument("--no-onboarding", action="store_true")
        parser.add_argument("--refresh", action="store_true")
        parser.add_argument("--only", type=int)
        parser.add_argument("--no-notify", action="store_true")
        args = parser.parse_args()
        if not accounts:
            raise ConfigurationError("未配置 LOOMY_TOKENS；每个非空行填写一个 session 或 备注|session")
        if args.only is not None and not 1 <= args.only <= len(accounts):
            raise ConfigurationError("--only 必须指定存在的账号序号")
        setting = os.environ.get("LOOMY_ONBOARDING", "0").strip()
        if setting not in ("0", "1"):
            raise ConfigurationError("LOOMY_ONBOARDING 只能为 0 或 1")
        bulk = setting == "1" and not args.no_onboarding
        log("任务模式: " + ("任务查询" if args.tasks else "单项领取" if args.claim else "每日积分与显式新手领取" if bulk else "仅每日积分"))
        for index, account in enumerate(accounts, 1):
            if args.only is not None and index != args.only:
                log("账号%d ⏭️ 未选中" % index)
                continue
            account_start = time.monotonic()
            stats = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
            stage_number = 0

            def stage(name, action):
                nonlocal stage_number
                stage_number += 1
                mark = time.monotonic()
                log("账号%d 阶段%d %s 开始" % (index, stage_number, name))
                try:
                    result = action()
                    log("账号%d 阶段%d %s ✅ 完成，耗时 %.2f 秒" % (index, stage_number, name, time.monotonic() - mark))
                    return result
                except Exception:
                    log("账号%d 阶段%d %s ❌ 失败，耗时 %.2f 秒" % (index, stage_number, name, time.monotonic() - mark))
                    raise

            try:
                if not account["valid"]:
                    raise ConfigurationError("账号行缺少 session")
                if DRY_RUN:
                    planned = ["新手任务查询"] if args.tasks else ["单项领取 " + args.claim] if args.claim else ["每日积分刷新"] + (["显式新手任务领取"] if bulk else [])
                    for name in planned:
                        stage(name, lambda: log("DRY_RUN_OK：参数和任务路由验证通过；未调用任何网络或写入记录"))
                        stats["skipped"] += 1
                elif args.tasks:
                    view = stage("新手任务查询", lambda: onboarding_view(account["session"], args.refresh))
                    log_task_list(view)
                    stats["success"] += 1
                elif args.claim:
                    view = stage("显式单项领取", lambda: claim_single(account["session"], args.claim, args.refresh))
                    if view.get("fromMemory"):
                        log("☑️ 新手任务已结清（本地记录；--refresh 可强制核验）")
                        stats["alreadyComplete"] += 1
                    elif not view.get("ok") or view.get("refreshError"):
                        log("❌ 领取或领取后进度核验未成功")
                        stats["failed"] += 1
                    else:
                        stats["alreadyComplete" if view.get("already") else "success"] += 1
                        log_task_list(view)
                else:
                    ok, message = stage("每日积分刷新", lambda: first_login(account["session"]))
                    log(("✅ " if ok else "❌ ") + message)
                    stats["success" if ok else "failed"] += 1
                    if bulk and ok:
                        newly, failed, view = stage("显式批量新手领取", lambda: claim_onboarding(account["session"], args.refresh))
                        for item in view.get("results", []):
                            key = "alreadyComplete" if item.get("already") else "success" if item.get("ok") else "failed"
                            stats[key] += 1
                            log("新手任务 %s: %s" % (item["key"], "☑️ 已完成" if key == "alreadyComplete" else "✅ 领取成功" if key == "success" else "❌ 领取失败"))
                        if not view.get("results"):
                            stats["alreadyComplete"] += 1
                        log_task_list(view)
                    else:
                        log("⏭️ 未执行新手领取（需显式开启且每日积分成功）")
                        stats["skipped"] += 1
            except ConfigurationError as error:
                log("❌ 账号%d 配置错误: %s" % (index, error))
                stats["failed"] += 1
            except Exception:
                log("❌ 账号%d 请求、响应或业务核验失败；检查登录态及任务状态" % index)
                stats["failed"] += 1
            result = {"account": index, "ok": stats["failed"] == 0, "statistics": stats,
                      "elapsedSeconds": round(time.monotonic() - account_start, 2)}
            results.append(result)
            for key in totals:
                totals[key] += stats[key]
            log("账号%d 统计: 总任务%d，成功%d，已完成%d，跳过%d，失败%d，耗时%.2f秒" %
                (index, sum(stats.values()), stats["success"], stats["alreadyComplete"], stats["skipped"], stats["failed"], result["elapsedSeconds"]))
    except ConfigurationError as error:
        config_error = True
        log("❌ 配置错误: " + str(error))
    success_count = sum(r["ok"] for r in results)
    failure_count = len(results) - success_count
    exit_code = int(config_error or failure_count > 0)
    status = "configuration-error" if config_error else "partial-failure" if failure_count and success_count else "failure" if failure_count else "dry-run" if DRY_RUN else "success"
    log("----------------------------------------")
    log("任务统计: 配置账号%d，执行账号%d，成功%d，失败%d，子任务成功%d，已完成%d，跳过%d，失败%d" %
        (len(accounts), len(results), success_count, failure_count, totals["success"], totals["alreadyComplete"], totals["skipped"], totals["failed"]))
    body = "账号总数%d，执行%d，成功%d，失败%d；状态%s；子任务成功%d，失败%d" % (len(accounts), len(results), success_count, failure_count, status, totals["success"], totals["failed"])
    notification = notify_all("Loomy 每日积分与新手任务", body, args.no_notify if args else "--no-notify" in sys.argv)
    finished = time.strftime("%Y-%m-%d %H:%M:%S")
    log("完成时间: %s；总耗时 %.2f 秒；最终状态: %s；通知: %s" % (finished, time.monotonic() - started, status, notification))
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if DRY_RUN else "live", "accountCount": len(accounts), "executedAccounts": len(results), "successCount": success_count, "failureCount": failure_count, "configurationError": config_error, "statistics": totals, "accounts": results, "notification": notification, "finishTime": finished, "exitCode": exit_code}, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
