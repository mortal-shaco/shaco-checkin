#!/usr/bin/env python3
# name: AutoClaw 国内版每日签到
# cron: 15 8 * * *
# 来源: L0NE-6/AutoClaw-Daily, autoclaw_cn_daily.py、autoclaw_intl_daily.py
# 协议和参数获取参考: autoclaw_login.py（MIT）
# 上游许可: MIT；维护版本采用 MIT，保留上游署名。
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
AutoClaw 国内版每日签到（兼容国际版的独立维护版）
功能：每日签到、登录态过期续期（含 agent-refresh 备用接口）、只读任务清单诊断、
北京当天活动积分流水核查；--promotion claim 显式触发登录活跃奖励并复核到账。
AUTOCLAW_PROMOTION 默认 off 保持既有签到行为；read 只读，claim 允许触发；仅续期模式不查活动。
上游新增活动接口与国际版参考一致，签名/每日签到/续期协议未变；无真实接口验证。
活动异常单独统计，不改写签到结论；任何已启用阶段失败仍以非零退出。
原脚本未提供 cron；此处建议每天北京时间 08:15 运行，可在青龙调整。
参数：AUTOCLAW_CN_TOKENS 每个非空行一个账号，禁止用 & 或 @ 分隔账号。
建议每行 JSON 对象：{"access":"登录态","refresh":"续期登录态","device_id":"设备标识"}。
兼容 token、token|refresh_token、token|refresh_token|device_id、备注|token|refresh_token|device_id。
也兼容旧备注|JWT、备注|JWT|refresh_token；不明确时请使用 JSON。
字段逐次仅按第一个 | 分割，最后一字段保留剩余文本；JWT 可带 Bearer 前缀。
获取：在 AutoClaw 国内版官方桌面端自行登录，从自己的登录响应安全提取
access_token、refresh_token 和同次登录的 device_id（不是接口 X-Authorization 的其他产品密钥）。
不要将登录响应发给他人。只有 access_token 时仍可签到，过期后需重新登录。
国际版：--region intl 使用 AUTOCLAW_INTL_TOKENS（同样的逐行格式）；
--region both 同时处理两地区；也可设置 AUTOCLAW_REGION=cn/intl/both。
默认 --region cn 保持国内版既有行为；--only N 使用所选地区列表中的序号，
both 时先国内版再国际版；显式选择的每个地区均须配置账号。
国际版必须使用国际版官方桌面端登录态。可从自己的登录响应提取；
若官方客户端只提供本机配置，在自己的电脑查看 ~/.openclaw-autoclaw/openclaw.json，
定位 models.providers 下 models[].headers 的 X-Authorization，去掉 Bearer 前缀后
填入 AUTOCLAW_INTL_TOKENS。运行脚本不读取、不依赖该文件或桌面端程序。
该来源通常只有 access，无法续期；失效后须重新登录并更新环境变量。
国际版可选 AUTOCLAW_INTL_STORE_FILE 与国内缓存隔离；国际凭据绝不发往国内接口。
AUTOCLAW_INTL_DRY_RUN=1 也启用全任务断网预演。
命令：--refresh-only 只续期；--only N 只运行第 N 个账号；--no-notify 关闭通知。
默认不落盘凭据；如需保存续期结果，显式设置 AUTOCLAW_CN_STORE_FILE 为受保护的
私有绝对路径，文件以 0600 原子写入，必须排除出公开订阅/仓库。续期仅刷新本次内存。
AUTOCLAW_CN_DRY_RUN=1 完全断网预演，既不读写缓存也不发送真实通知。
QINGLONG_NOTIFY 默认 auto（本脚本在默认通知名单中）；显式 1 开启、0 关闭。
QINGLONG_NOTIFY_SCRIPTS 设置后替换默认名单，支持目录相对路径、文件名通配符、目录编号；
以逗号、分号或空白分隔，空值关闭所有自动通知，* 全选；--no-notify 优先关闭。
支持青龙 notify.py/sendNotify.js，并保留青龙 API、PushPlus、Bark、企业微信、钉钉备用链。
定时脚本不发送短信、不登录新账号、不读取桌面配置；登录工具仅用作凭据获取参考。
无需私有仓库或桌面端程序参与执行；仅使用 Python 标准库，无额外运行依赖。
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
        _ql_notify_identities = ('3813c988ddc0c592', 'scripts/autoclaw_cn_daily.py', 'autoclaw_cn_daily.py', 'autoclaw_cn_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import datetime
import fnmatch
import re
import hashlib
import hmac
import importlib.util
import json
import os
import platform as host_platform
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import ssl
import urllib.error
import urllib.request
from urllib.parse import quote

USERAPI = "https://autoglm-acceleration-api.zhipuai.cn"
REGION_APIS = {"cn": USERAPI, "intl": "https://autoglm-api.autoglm.ai"}
TASK_COMPLETE_PATH = "/autoclaw-proxy/proxy/autoclaw-task-complete"
TASK_LIST_PATH = "/autoclaw-proxy/proxy/autoclaw-task-list"
REFRESH_PATH = "/userapi/v1/refresh"
REFRESH_FALLBACK_PATH = "/userapi/v1/agent-refresh"
TASK_ID = "daily_signin"
APP_ID = "100003"
APP_KEY = "38d2391985e2369a5fb8227d8e6cd5e5"
CLIENT_VERSION = "1.18.5"
AUTH_EXPIRED_CODES = (410000, 400000)
DRY = any(os.environ.get(name, "").lower() in ("1", "true", "yes", "on")
          for name in ("AUTOCLAW_CN_DRY_RUN", "AUTOCLAW_INTL_DRY_RUN"))
TITLE = "AutoClaw 国内版每日签到"
CATALOG_ID = "3813c988ddc0c592"
LEDGERS_PATH = ("/agent-assetmgr/api/v1/ledgers_std?asset_type=point&wallet_type=all"
                "&cursor=&page_size=50&flow_direction=income")
USER_INFO_PATH = "/userapi/v1/user-info"
ACTIVE_EVENT_TYPE_PREFIXES = ("autoclaw_user_active", "autoclaw_user_signup_day")
ACTIVE_ACTIVITY_PREFIXES = ("autoclaw_user_active_reward", "autoclaw_user_active_bonus",
                            "autoclaw_new_user_day_1_to_7_bonus")
PROMOTION_SETTLE_SECONDS = 1.5
SECRETS = set()


def remember_secrets(account):
    for field in ("access", "refresh", "device_id"):
        if account.get(field):
            SECRETS.add(account[field])


def log(message):
    text = str(message)
    for secret in sorted(SECRETS, key=len, reverse=True):
        text = text.replace(secret, "[凭据已隐藏]")
    print(time.strftime("[%H:%M:%S] ") + text, flush=True)


class TaskError(Exception):
    pass


def strip_bearer(value):
    value = str(value or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else value


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    def json(self):
        return json.loads(self.content.decode("utf-8"))


def request(method, url, headers=None, body=None, timeout=20):
    if DRY:
        raise TaskError("断网预演禁止请求")
    if not url.startswith("https://"):
        raise TaskError("拒绝非 HTTPS 请求")
    # 默认验证 TLS，不使用环境代理、不跟随重定向，不重试状态变更请求。
    request_headers = dict(headers or {})
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            response = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            content = response.read(1048577)
            if len(content) > 1048576:
                raise TaskError("接口响应超过大小限制")
            return Response(response.code, content)
    except (urllib.error.URLError, OSError, ValueError):
        raise TaskError("网络请求失败或超时（详情已脱敏）") from None


def json_of(response):
    try:
        value = response.json()
        if isinstance(value, dict):
            return value
    except (ValueError, TypeError, UnicodeError):
        pass
    raise TaskError("接口未返回有效 JSON 对象")


def accepted(response, payload):
    return response.status_code == 200 and type(payload.get("code")) is int and payload["code"] == 0


def show_identity(payload, account):
    data = payload.get("data")
    if not isinstance(data, dict):
        return
    # 登录/续期返回的新凭据同样不得通过身份字段泄漏。
    for key in ("access_token", "accessToken", "token", "refresh_token", "refreshToken", "device_id"):
        if isinstance(data.get(key), str) and data[key]:
            value = strip_bearer(data[key])
            if value:
                SECRETS.add(value)
    holders = [data]
    for key in ("user", "user_info", "account"):
        if isinstance(data.get(key), dict):
            holders.append(data[key])
    for holder in holders:
        for key in ("nickname", "username", "display_name", "displayName", "public_uid", "uid"):
            value = holder.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                # 非凭据身份原样展示；手机号或包含凭据的异常字段不展示。
                phone = re.search(r"(?<!\d)(?:\+?86[ -]?)?1[3-9](?:[ -]?\d){9}(?!\d)", str(value))
                if not phone and not any(secret in str(value) for secret in SECRETS):
                    log("官方账号身份 " + key + ": " + json.dumps(value, ensure_ascii=False))


def signed_headers(token):
    timestamp = str(int(time.time()))
    sign = hashlib.md5(("%s&%s&%s" % (APP_ID, timestamp, APP_KEY)).encode("utf-8")).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "X-Version": CLIENT_VERSION,
        "X-Product": "autoclaw",
        "X-Client-Type": "pc",
        "X-Harness-Type": "zcode",
        # 平台标识只认官方桌面端的 win / mac；Linux（容器）回落 win，发 linux 会被部分账号 403
        "X-Tm": "mac" if host_platform.system().lower() == "darwin" else "win",
        "X-Lang": "zh-CN",
        "X-Channel": "official",
        "X-Auth-Appid": APP_ID,
        "X-Auth-TimeStamp": timestamp,
        "X-Auth-Sign": sign,
        "X-Trace-Id": uuid.uuid4().hex,
    }
    if token:
        headers["authorization"] = "Bearer %s" % token
    return headers


def looks_like_token(value):
    return value.startswith(("eyJ", "Bearer ", "bearer ")) or value.count(".") >= 2 or len(value) > 80


def parse_account(line):
    if line.startswith("{"):
        try:
            obj = json.loads(line)
        except ValueError:
            raise TaskError("账号 JSON 格式错误") from None
        if not isinstance(obj, dict) or any(not isinstance(obj.get(k, ""), str) for k in ("access", "refresh", "device_id")):
            raise TaskError("账号 JSON 字段必须为文本")
        account = {k: obj.get(k, "") for k in ("access", "refresh", "device_id")}
    else:
        parts = []
        rest = line
        while "|" in rest and len(parts) < 3:
            value, rest = rest.split("|", 1)
            parts.append(value.strip())
        parts.append(rest.strip())
        access = refresh = device = ""
        if len(parts) == 4:
            _, access, refresh, device = parts
        elif len(parts) == 3:
            if looks_like_token(parts[0]):
                access, refresh, device = parts
            else:
                _, access, refresh = parts
        elif len(parts) == 2:
            if not looks_like_token(parts[0]) and looks_like_token(parts[1]):
                _, access = parts
            else:
                access, refresh = parts
        else:
            access = parts[0]
        account = {"access": access, "refresh": refresh, "device_id": device}
    account["access"] = strip_bearer(account["access"])
    account["refresh"] = strip_bearer(account["refresh"])
    if not account["access"] or any(c in account["access"] for c in "\r\n"):
        raise TaskError("账号缺少有效登录态")
    if "&" in line and not line.startswith("{"):
        raise TaskError("账号必须按换行分隔；含特殊字符的凭据请使用 JSON")
    return account


def cache_keys(account):
    return [hashlib.sha256(v.encode()).hexdigest() for v in (account.get("refresh"), account["access"]) if v]


def store_path(account):
    variable = "AUTOCLAW_INTL_STORE_FILE" if account.get("region") == "intl" else "AUTOCLAW_CN_STORE_FILE"
    value = os.environ.get(variable, "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise TaskError("缓存路径必须为非符号链接的私有绝对路径")
    return path


def read_store(path):
    if not path.exists():
        return {}
    if path.stat().st_mode & 0o077:
        raise TaskError("凭据缓存权限不安全，须设为 0600")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
    except (OSError, ValueError):
        pass
    raise TaskError("凭据缓存读取失败")


def apply_store(account):
    path = store_path(account)
    if not path:
        return
    store = read_store(path)
    for key in cache_keys(account):
        saved = store.get(key)
        if isinstance(saved, dict) and saved.get("access"):
            for field in ("access", "refresh", "device_id"):
                if not isinstance(saved.get(field, ""), str):
                    raise TaskError("凭据缓存字段无效")
            account.update({field: saved.get(field) or account[field] for field in ("access", "refresh", "device_id")})
            remember_secrets(account)
            log("使用显式配置的私有凭据缓存")
            return


def persist(account, old_keys):
    path = store_path(account)
    if not path:
        log("续期成功，仅更新本次内存；未启用凭据落盘")
        return
    temporary = None
    try:
        store = read_store(path)
        for key in set(old_keys + cache_keys(account)):
            store[key] = dict(account)
        with tempfile.NamedTemporaryFile(mode="w", dir=str(path.parent), delete=False, encoding="utf-8") as handle:
            temporary = handle.name
            os.chmod(temporary, 0o600)
            json.dump(store, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        log("续期结果已保存至私有缓存（0600）")
    except OSError:
        raise TaskError("私有凭据缓存保存失败") from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def refresh_account(account):
    if not account.get("refresh"):
        raise TaskError("账号没有 refresh_token，无法续期；请在官方客户端重新登录")
    old_keys = cache_keys(account)
    for path in (REFRESH_PATH, REFRESH_FALLBACK_PATH):
        log("续期请求：" + ("主接口" if path == REFRESH_PATH else "agent-refresh 备用接口"))
        body = {"refresh_token": account["refresh"], "source_id": "autoclaw"}
        if account.get("device_id"):
            body["device_id"] = account["device_id"]
        response = request("POST", REGION_APIS[account.get("region", "cn")] + path, signed_headers(account["access"]), body)
        payload = json_of(response)
        if payload.get("code") == 400002 and path == REFRESH_PATH:
            log("主接口签名校验未通过，尝试上游支持的备用接口")
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        access = strip_bearer(first_text(data.get("access_token"), data.get("accessToken"), data.get("token")))
        if not accepted(response, payload) or not access:
            raise TaskError("续期未通过业务校验；请重新获取该账号登录态")
        show_identity(payload, account)
        account["access"] = access
        account["refresh"] = strip_bearer(first_text(data.get("refresh_token"), data.get("refreshToken"))) or account["refresh"]
        remember_secrets(account)
        persist(account, old_keys)
        return
    raise TaskError("两个续期接口均未通过")


def task_list_hint(account):
    log("阶段诊断：读取任务清单（只读）")
    response = request("GET", REGION_APIS[account.get("region", "cn")] + TASK_LIST_PATH, signed_headers(account["access"]))
    payload = json_of(response)
    if not accepted(response, payload):
        raise TaskError("任务清单未通过业务校验")
    show_identity(payload, account)
    rows = payload.get("data")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("task_id") == TASK_ID and row.get("completed") is True:
                log("任务清单显示今日已完成；未证明本次领取奖励")
                return
    log("任务清单未确认今日已完成")


def do_checkin(account):
    def complete():
        response = request("POST", REGION_APIS[account.get("region", "cn")] + TASK_COMPLETE_PATH, signed_headers(account["access"]), {"task_id": TASK_ID})
        return response, {} if response.status_code == 401 else json_of(response)
    log("提交每日签到任务")
    response, payload = complete()
    if response.status_code == 401 or payload.get("code") in AUTH_EXPIRED_CODES:
        refresh_account(account)
        log("续期后重新提交签到")
        response, payload = complete()
    if not accepted(response, payload):
        raise TaskError("签到接口未通过 HTTP 或业务码校验")
    show_identity(payload, account)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    reward = data.get("reward_points", 0)
    try:
        reward = int(reward) if not isinstance(reward, bool) else 0
    except (ValueError, TypeError, OverflowError):
        reward = 0
    if data.get("success") is False:
        raise TaskError("接口明确返回签到失败")
    if reward > 0 or (data.get("success") is True and data.get("already_completed") is not True):
        log("✅ 签到成功，获得 %d 积分" % reward)
        return "success"
    if data.get("already_completed") is True:
        log("☑️ 今天已签到（接口明确确认）")
        return "alreadyComplete"
    task_list_hint(account)
    raise TaskError("上游未返回签到成功或已完成标记")


def today_key():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")


def _promotion_entry(entry, today):
    if not isinstance(entry, dict):
        return None
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    if str(meta.get("grant_date") or "") != today:
        return None
    event = str(meta.get("event_type") or "")
    activity = str(meta.get("activity_id") or "")
    if not (event.startswith(ACTIVE_EVENT_TYPE_PREFIXES)
            or activity.startswith(ACTIVE_ACTIVITY_PREFIXES)):
        return None
    value = entry.get("amount")
    try:
        points = int(value) if not isinstance(value, bool) else 0
    except (TypeError, ValueError, OverflowError):
        points = 0
    if points <= 0:
        raise TaskError("活动流水命中，但缺少有效正积分，无法确认到账")
    # 保留逐笔明细和合计能力，不输出服务端自由文本。
    return {"points": points, "date": today}


def promotion_status(account):
    log("只读查询北京当天活动积分流水（最近 50 笔收入）")
    response = request("GET", REGION_APIS[account.get("region", "cn")] + LEDGERS_PATH,
                       signed_headers(account["access"]))
    payload = json_of(response)
    if not accepted(response, payload):
        raise TaskError("活动流水未通过 HTTP 或业务码校验")
    show_identity(payload, account)
    data = payload.get("data")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise TaskError("活动流水缺少有效 entries 列表")
    today = today_key()
    matched = [item for item in (_promotion_entry(entry, today) for entry in entries) if item]
    return {"granted": bool(matched), "points": sum(item["points"] for item in matched),
            "entries": matched}


def trigger_login_active(account):
    log("显式授权：调用登录活跃接口触发活动奖励，不主动轮换 refresh_token")
    response = request("POST", REGION_APIS[account.get("region", "cn")] + USER_INFO_PATH,
                       signed_headers(account["access"]),
                       {"source_id": "autoclaw", "device_id": account.get("device_id", "")})
    payload = json_of(response)
    if not accepted(response, payload):
        raise TaskError("登录活跃触发未通过 HTTP 或业务码校验")
    show_identity(payload, account)
    log("✅ 活跃接口已受理，等待流水复核；尚不视为奖励到账")


def do_promotion(account, mode):
    if mode == "off":
        log("⏭️ 活动福利已关闭")
        return "skipped"
    status = promotion_status(account)
    if not status["granted"] and mode == "claim":
        trigger_login_active(account)
        time.sleep(PROMOTION_SETTLE_SECONDS)
        status = promotion_status(account)
    if status["granted"]:
        for number, item in enumerate(status["entries"], 1):
            log("活动入账第 %d 笔：北京日期 %s，+%d 积分" % (number, item["date"], item["points"]))
        log("✅ 活动福利 +%d 已到账，共 %d 笔" % (status["points"], len(status["entries"])))
        return "success"
    if mode == "claim":
        raise TaskError("活跃触发后流水仍未确认当天奖励，可能未处于活动期或存在延迟；不宣称到账")
    log("☑️ 流水查询通过，最近 50 笔未发现当天活动入账；只读模式不触发奖励")
    return "success"


def post_json(url, payload, timeout=20):
    return request("POST", url, body=payload, timeout=timeout)


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
        return answer.status_code == 200 and str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "AutoClaw"})
        return answer.status_code == 200 and json_of(answer).get("code") == 200
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
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
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
                stamp, quote(base64.b64encode(digest)))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_ql(title, content):
    # 在独立子进程中加载青龙通知组件；捕获组件输出，防止第三方日志泄漏。
    candidates = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "")
    if directory:
        candidates.append(Path(directory) / "notify.py")
    try:
        spec = importlib.util.find_spec("notify")
        if spec and spec.origin:
            candidates.append(Path(spec.origin))
    except (ImportError, ValueError):
        pass
    candidates += [Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")]
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        code = "import importlib.util,json,sys; s=importlib.util.spec_from_file_location('notify',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); a=json.load(sys.stdin); m.send(*a)"
        try:
            result = subprocess.run([sys.executable, "-c", code, str(path)], input=json.dumps([title, content]), text=True, capture_output=True, timeout=30)
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    js_paths = ([Path(directory) / "sendNotify.js"] if directory else []) + [Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")]
    for path in js_paths:
        if path.is_file():
            code = "let x='';process.stdin.on('data',d=>x+=d);process.stdin.on('end',async()=>{try{await require(process.argv[1]).sendNotify(...JSON.parse(x));}catch(e){process.exitCode=1;}});"
            try:
                result = subprocess.run(["node", "-e", code, str(path)], input=json.dumps([title, content]), text=True, capture_output=True, timeout=30)
                if result.returncode == 0:
                    return True
            except (OSError, subprocess.TimeoutExpired):
                pass
    # 保留上游显式配置的青龙 API 推送备用通道。
    endpoint, token = _env("QL_URL").rstrip("/"), _env("QL_TOKEN")
    if endpoint and token:
        try:
            response = post_json(endpoint + "/api/system/notify?token=" + quote(token, safe=""), {"title": title, "content": content}, timeout=15)
            return response.status_code == 200 and str(json_of(response).get("code")) in ("0", "200")
        except Exception:
            pass
    return False


def notification_enabled(disabled):
    switch = _env("QINGLONG_NOTIFY").lower()
    if disabled or switch in ("0", "false", "no", "off"):
        return False
    if switch in ("1", "true", "yes", "on"):
        return True
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True  # 本维护任务是默认通知名单成员。
    selectors = [s for s in re.split(r"[,;\s]+", os.environ["QINGLONG_NOTIFY_SCRIPTS"]) if s]
    names = {CATALOG_ID, Path(__file__).name, "autoclaw_cn_daily.py",
             "checkin/autoclaw_cn_daily.py", "scripts/checkin/autoclaw_cn_daily.py",
             "candidates/3813c988ddc0c592/autoclaw_cn_daily.py"}
    # 同时支持脚本实际位于青龙 scripts 目录中的相对路径。
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            names.add(Path(__file__).absolute().relative_to(root).as_posix())
        except ValueError:
            pass
    return any(fnmatch.fnmatchcase(name, selector) for selector in selectors for name in names)


def notify_all(content, disabled):
    if not notification_enabled(disabled):
        log("⏭️ 通知已关闭")
        return "disabled"
    if DRY:
        log("⏭️ 断网预演：模拟通知，摘要：" + content)
        return "dry-run"
    delivered = notify_ql(TITLE, content)
    if not delivered:
        for handler in (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk):
            if handler(TITLE, content):
                delivered = True
                break
    log("✅ 脱敏通知已发送" if delivered else "⚠️ 通知不可用或发送失败，保留业务退出码")
    return "sent" if delivered else "unavailable"


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError("命令参数无效；支持 --region cn/intl/both、--only 正整数、--refresh-only、--promotion off/read/claim、--no-notify")


def main():
    started = time.monotonic()
    log("========== " + TITLE + " ==========")
    log("开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("运行模式：" + ("断网预演" if DRY else "真实运行"))
    lines = []
    results = []
    configuration_error = False
    disabled = "--no-notify" in sys.argv
    try:
        parser = SafeParser(description=TITLE)
        parser.add_argument("--region", choices=("cn", "intl", "both"), default=_env("AUTOCLAW_REGION") or "cn")
        parser.add_argument("--promotion", choices=("off", "read", "claim"), default=_env("AUTOCLAW_PROMOTION") or "off")
        parser.add_argument("--only", type=int)
        parser.add_argument("--refresh-only", action="store_true")
        parser.add_argument("--no-notify", action="store_true")
        args = parser.parse_args()
        disabled = args.no_notify
        if args.region not in ("cn", "intl", "both"):
            raise TaskError("AUTOCLAW_REGION 只能为 cn、intl 或 both")
        if args.promotion not in ("off", "read", "claim"):
            raise TaskError("AUTOCLAW_PROMOTION 只能为 off、read 或 claim")
        regions = ("cn", "intl") if args.region == "both" else (args.region,)
        missing = []
        for region in regions:
            variable = "AUTOCLAW_CN_TOKENS" if region == "cn" else "AUTOCLAW_INTL_TOKENS"
            entries = [line.strip() for line in _env(variable).splitlines()
                       if line.strip() and not line.strip().startswith("#")]
            if not entries:
                missing.append(variable)
            lines.extend((region, line) for line in entries)
        log("地区模式：" + args.region + "；配置账号数：%d" % len(lines))
        if missing:
            log("❌ 缺少所选地区凭据：" + "、".join(missing))
            configuration_error = True
        if not lines:
            raise TaskError("所选地区未配置账号；请按每个非空行一个账号填写")
        if args.only is not None and not 1 <= args.only <= len(lines):
            raise TaskError("--only 必须指定存在的账号序号")
        for index, (region, line) in enumerate(lines, 1):
            if args.only is not None and index != args.only:
                continue
            account_start = time.monotonic()
            stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
            failed = False
            log("----- 账号 %d（%s）-----" % (index, "国际版" if region == "intl" else "国内版"))
            stages = [("参数校验", None), ("凭据缓存", None), ("仅续期" if args.refresh_only else "每日签到", None)]
            if not args.refresh_only:
                stages.append(("活动福利（%s）" % args.promotion, None))
            account = None
            for number, (name, _) in enumerate(stages, 1):
                stage_start = time.monotonic()
                stats["total"] += 1
                log("阶段 %d/%d：%s" % (number, len(stages), name))
                outcome = "success"
                try:
                    if failed:
                        outcome = "skipped"
                        log("⏭️ 前置阶段失败，跳过")
                    elif number == 1:
                        account = parse_account(line)
                        account["region"] = region
                        remember_secrets(account)
                        log("✅ 参数校验通过（凭据不显示）")
                    elif DRY:
                        outcome = "skipped"
                        log("⏭️ DRY_RUN_OK：模拟阶段，不联网、不读写凭据")
                    elif number == 2:
                        apply_store(account)
                        log("✅ 缓存阶段完成")
                    elif number == 4:
                        outcome = do_promotion(account, args.promotion)
                    elif args.refresh_only:
                        refresh_account(account)
                        log("✅ token 续期成功")
                    else:
                        outcome = do_checkin(account)
                except TaskError as error:
                    log("❌ " + str(error))
                    outcome, failed = "failure", True
                except Exception:
                    log("❌ 阶段异常（已隐藏原始异常及响应）")
                    outcome, failed = "failure", True
                stats[outcome] += 1
                log("阶段 %d 耗时 %.2f 秒" % (number, time.monotonic() - stage_start))
            log("账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒" % (index, stats["total"], stats["success"], stats["alreadyComplete"], stats["skipped"], stats["failure"], time.monotonic() - account_start))
            results.append({"account": index, "region": region, "status": "failure" if failed else ("dry-run" if DRY else "success"), "tasks": stats})
    except TaskError as error:
        log("配置账号数：%d" % len(lines))
        log("❌ 配置错误：" + str(error))
        configuration_error = True
    failures = sum(r["status"] == "failure" for r in results)
    successes = len(results) - failures
    exit_code = 1 if configuration_error or failures else 0
    status = "configuration-error" if configuration_error else ("partial-failure" if failures and successes else "failure" if failures else "dry-run" if DRY else "success")
    count = len(results) if results else len(lines)
    configuration_failures = len(missing) if configuration_error and "missing" in locals() and missing else (1 if configuration_error else 0)
    reported_failures = failures
    content = "账号总数 %d，成功数 %d，失败数 %d；状态 %s" % (count, successes, reported_failures, status)
    content += "；配置错误数 %d" % configuration_failures
    log("汇总阶段 1/1：任务汇总与通知")
    notification_start = time.monotonic()
    try:
        notification = notify_all(content, disabled)
    except Exception:
        log("⚠️ 通知组件异常，保留业务退出码（详情已脱敏）")
        notification = "unavailable"
    log("汇总阶段 1 耗时 %.2f 秒" % (time.monotonic() - notification_start))
    totals = {key: sum(r["tasks"][key] for r in results) for key in ("total", "success", "alreadyComplete", "skipped", "failure")}
    log("----------------------------------------")
    log(content)
    log("子任务统计：" + json.dumps(totals, ensure_ascii=False))
    log("总耗时：%.2f 秒" % (time.monotonic() - started))
    log("完成时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("最终状态：" + status + "；通知状态：" + notification)
    print("TASK_SUMMARY=" + json.dumps({"status": status, "mode": "dry-run" if DRY else "live", "accountCount": count, "successCount": successes, "failureCount": reported_failures, "accounts": results, "tasks": totals, "notification": notification, "exitCode": exit_code, "configurationFailureCount": configuration_failures}, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
