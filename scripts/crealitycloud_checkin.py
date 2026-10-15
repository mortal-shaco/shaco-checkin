#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 创想云国内站签到
# cron: 44 2 * * *
# SPDX-License-Identifier: MIT
# 上游作者及来源：xz0609/crealitycloud-checkin-ql
# https://github.com/xz0609/crealitycloud-checkin-ql (ba2872b75372f62157b1f0cdcdf57ed59f9bd1fb)
"""
cron: 44 2 * * *
new Env('创想云国内站签到')

创想云国内站 · 自动签到脚本 · 青龙面板版
=================================================
站点   : https://www.crealitycloud.cn  （3D 打印模型平台，国内 CN 站）
登录   : 账号（手机号 / 邮箱）+ 密码
功能   : 每日签到（连续签到）
依赖   : 无（仅 Python 标准库 urllib）
适配   : 青龙面板（单文件、零依赖，支持订阅式部署与定时任务）

用法
-------------------------------------------------
1. 配置账号：设置环境变量  CREALITY_ACCOUNTS  或直接改下方 CONFIG_ACCOUNTS
   格式：每行「账号 密码」（账号与密码用空格分隔），多个账号用换行分隔
   - 手机号：直接填 11 位手机号（自动补 +86 区号）；也可填「8613800138000」这种已带区号
   - 邮箱  ：直接填邮箱地址

2. 青龙面板定时规则： 0 9 * * *   （每天 09:00 执行）
3. 运行：python3 crealitycloud_checkin.py

说明
-------------------------------------------------
- 登录走官方账号中心 id.creality.cn（OAuth 统一登录）
- 签到接口 api.crealitycloud.cn，认证 header 为 __CXY_TOKEN_ / __CXY_UID_
- 已内置「直接登录态签到 → OAuth 授权码换取」双路径降级，提升兼容性
- 支持青龙 notify.py；CREALITY_DRY_RUN=1 断网预演，通知在禁网子进程中尝试发送
- 密码在官方国内站注册或重置后取得；无需抓取 Cookie 或 Token
- 仅签到改变服务端状态；不会发帖、评论、分享或消费创想币
- 每个非空非注释行都是一个账号；格式错误也计为失败，其他账号继续执行
"""

import datetime
import importlib.util
import json
import os
import random
import re
import ssl
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from http.cookiejar import CookieJar

# ============================================================
# 配置区（二选一：环境变量优先于下方配置）
# ============================================================

# 环境变量名（青龙面板中配置，格式：每行「账号 密码」，多账号换行分隔）
ENV_ACCOUNTS = "CREALITY_ACCOUNTS"

# 随机延时开关与上限（签到开始前的整体随机延时，防风控）
ENV_RANDOM_SIGNIN = "RANDOM_SIGNIN"        # 开关：默认 true 开启，设 false 关闭
ENV_MAX_RANDOM_DELAY = "MAX_RANDOM_DELAY"  # 随机延时上限（秒），默认 3600

# 内置账号配置：仅当环境变量未设置时生效
# 格式：每行「账号 密码」（账号与密码用空格分隔）；手机号自动补 86 区号，邮箱直接填
CONFIG_ACCOUNTS = """
# 示例：
# 13800138000 你的密码
# your_email@example.com 你的密码
"""

# ============================================================
# 常量（接口地址、clientId、请求头模板）
# ============================================================

# 登录 / OAuth 授权 / 签到相关接口
LOGIN_URL = "https://id.creality.cn/api/cxy/account/v2/loginV2"          # 账号密码登录
AUTHORIZE_URL = "https://id.creality.cn/api/cxy/oauth2/authorize"        # OAuth 授权拿 code
OAUTH_LOGIN_URL = "https://api.crealitycloud.cn/api/cxy/account/v2/oauthLogin"  # code 换 token
CHECKIN_URL = "https://api.crealitycloud.cn/api/cxy/v2/task/checkinV2"    # 签到
LAST_CHECKIN_URL = "https://api.crealitycloud.cn/api/cxy/v2/task/getLastCheckin"  # 最近签到状态
USER_INFO_URL = "https://api.crealitycloud.cn/api/cxy/v2/user/getInfo"           # 用户信息（含总积分）

# 国内 CN 站 clientId（从官方前端环境配置提取）
CLIENT_ID = "8ea5010984fa52a298f12110af8b05d0"

# OAuth 回调地址（创想云 oauth 路由）
OAUTH_REDIRECT_URI = "https://www.crealitycloud.cn/oauth"

# 登录中心（id.creality.cn）与主站（api.crealitycloud.cn）的设备标识
APP_ID_SSO = "creality_account"   # 登录中心 appId
APP_ID_CN = "cxy-gen2"            # 国内站 appId
APP_VER_SSO = "0.0.1"
APP_VER_CN = "7.3.28"

# 稳定设备唯一标识（可自行修改，避免频繁变动触发风控）
DEVICE_DUID = "wb-checkin-duid-2026"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 错误码含义（官方前端提取）
ERR_MSG = {
    0: "成功",
    1: "参数错误",
    4: "Token 无效",
    5: "身份无效",
    9: "账号不存在",
    35: "用户被封禁",
}

def _uuid():
    return str(uuid.uuid4())


def _build_sso_headers(extra=None):
    """登录中心（id.creality.cn）请求头"""
    h = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": UA,
        "__CXY_REQUESTID_": _uuid(),
        "__CXY_APP_ID_": APP_ID_SSO,
        "__CXY_APP_VER_": APP_VER_SSO,
        "__CXY_OS_LANG_": "1",
        "__CXY_PLATFORM_": "pc",
        "__CXY_DUID_": DEVICE_DUID,
        "__CXY_TIMEZONE_": "GMT+08:00",
    }
    if extra:
        h.update(extra)
    return h


def _build_cn_headers(token="", uid="", extra=None):
    """国内主站（api.crealitycloud.cn）请求头"""
    h = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": UA,
        "__CXY_REQUESTID_": _uuid(),
        "__CXY_APP_ID_": APP_ID_CN,
        "__CXY_APP_VER_": APP_VER_CN,
        "__CXY_OS_LANG_": "1",
        "__CXY_PLATFORM_": "2",
        "__CXY_DUID_": DEVICE_DUID,
        "__CXY_TIMEZONE_": "GMT+08:00",
        "__CXY_TOKEN_": token or "",
        "__CXY_UID_": str(uid or ""),
    }
    if extra:
        h.update(extra)
    return h


def parse_account(account):
    """解析账号，返回 (type, 标准账号)

    type: 1=手机号  2=邮箱
    """
    account = account.strip()
    if "@" in account:
        return 2, account
    # 手机号：去掉可能存在的 +、空格、- 后应得到 11 位（或 86+11=13 位）
    phone = account.replace("+", "").replace(" ", "").replace("-", "")
    if not phone.isdigit():
        raise ValueError("账号格式错误：应为邮箱或国内手机号")
    if len(phone) == 11:
        return 1, "86" + phone           # 纯 11 位手机号，补 +86 区号
    if len(phone) == 13 and phone.startswith("86"):
        return 1, phone                   # 已带 86 区号
    raise ValueError("手机号格式错误：应为 11 位或 86 加 11 位")



# MIT License (上游按任务元数据采用 MIT；原文件无独立版权声明)
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

TITLE = "创想云签到"
FALSE_VALUES = {"0", "false", "no", "off"}
MAX_RESPONSE = 1024 * 1024


def dry_run():
    return os.getenv("CREALITY_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


class ApiError(RuntimeError):
    """只包含本地安全错误描述，不携带原始响应、请求或凭据。"""


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 禁止将凭据随重定向发送至其他路径、主机或协议。
        raise ApiError("接口出现非预期重定向，已拒绝转发凭据")


def _build_opener():
    return urllib.request.build_opener(
        SafeRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        urllib.request.HTTPCookieProcessor(CookieJar()),
    )


def http_request(url, method="POST", headers=None, data=None, opener=None):
    if dry_run():
        raise ApiError("断网预演禁止业务网络请求")
    allowed = {LOGIN_URL, AUTHORIZE_URL, OAUTH_LOGIN_URL, CHECKIN_URL,
               LAST_CHECKIN_URL, USER_INFO_URL}
    if url.split("?", 1)[0] not in allowed:
        raise ApiError("拒绝请求未知接口")
    body_bytes = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body_bytes, headers=headers or {}, method=method)
    try:
        with (opener or _build_opener()).open(req, timeout=30) as resp:
            if resp.status != 200:
                raise ApiError(f"HTTP 状态异常：{resp.status}")
            raw = resp.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ApiError("接口响应超出大小限制")
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ApiError("接口未返回有效 JSON") from None
            if not isinstance(body, dict):
                raise ApiError("接口响应结构错误")
            return body
    except urllib.error.HTTPError as exc:
        raise ApiError(f"HTTP 状态异常：{exc.code}") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ApiError("网络、超时或 TLS 校验失败") from None


def require_ok(body, action):
    # bool 与数字 0 在 Python 中相等，必须排除 false 伪成功。
    code = body.get("code")
    if type(code) is not int or code != 0:
        safe_code = str(code) if type(code) is int else "缺失或格式错误"
        raise ApiError(f"{action}业务失败，业务码：{safe_code}")
    return body


def result_dict(body):
    result = body.get("result")
    if not isinstance(result, dict):
        raise ApiError("接口 result 字段缺失或格式错误")
    return result


def credentials(body):
    result = result_dict(body)
    token, uid = result.get("token"), result.get("userId")
    if not isinstance(token, str) or not token or not isinstance(uid, (str, int)) or not str(uid):
        raise ApiError("登录结果缺少有效 Token 或用户标识")
    return token, uid


def login(account, password):
    kind, normalized = parse_account(account)
    opener = _build_opener()
    body = http_request(LOGIN_URL, headers=_build_sso_headers(), data={
        "type": kind, "account": normalized, "password": password, "clientId": CLIENT_ID,
    }, opener=opener)
    require_ok(body, "登录")
    token, uid = credentials(body)
    return token, uid, opener


def oauth_exchange_token(token, opener):
    params = {
        "response_type": "code", "client_id": CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI, "state": "checkin",
        "timestamp": int(time.time() * 1000), "uid": _uuid(),
    }
    body = http_request(AUTHORIZE_URL + "?" + urllib.parse.urlencode(params),
                        method="GET", headers=_build_sso_headers(), opener=opener)
    require_ok(body, "OAuth 授权")
    location = result_dict(body).get("location")
    if not isinstance(location, str):
        raise ApiError("OAuth 授权缺少跳转地址")
    auth_code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query).get("code", [""])[0]
    if not auth_code:
        raise ApiError("OAuth 授权缺少授权码")
    body = http_request(OAUTH_LOGIN_URL, headers=_build_cn_headers(), data={
        "code": auth_code, "clientId": CLIENT_ID, "redirecturi": OAUTH_REDIRECT_URI,
    })
    require_ok(body, "OAuth 换取登录态")
    return credentials(body)


def get_last_checkin(token, uid):
    return http_request(LAST_CHECKIN_URL, headers=_build_cn_headers(token, uid), data={})


def do_checkin(token, uid):
    return http_request(CHECKIN_URL, headers=_build_cn_headers(token, uid), data={})


def get_user_info(token, uid):
    body = http_request(USER_INFO_URL, headers=_build_cn_headers(token, uid), data={})
    return require_ok(body, "用户信息查询")


def numeric(value):
    # 只显示数字，避免意外将服务端任意字符串作为积分/奖励记录。
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def show_checkin_details(body):
    last = result_dict(body).get("lastCheckin") or {}
    if not isinstance(last, dict):
        raise ApiError("签到详情字段格式错误")
    days = last.get("continueStep")
    if numeric(days):
        log(f"📅 已连续签到 {days} 天")
    rewards = last.get("rewards")
    if isinstance(rewards, list):
        for reward in rewards:
            if not isinstance(reward, dict) or not numeric(reward.get("rewardValue")):
                continue
            kind = reward.get("rewardType")
            label = {1: "积分", 2: "经验"}.get(kind, "其他奖励") if numeric(kind) else "其他奖励"
            log(f"🎁 本次奖励：{label}+{reward['rewardValue']}")


def show_user_info(body, secrets):
    result = result_dict(body)
    info = result.get("userInfo")
    if not isinstance(info, dict):
        raise ApiError("用户信息字段缺失或格式错误")
    # 昵称/公开 UID 保持官方原值；手机号、凭据和设备信息不输出。
    for key in ("nickname", "nickName", "username", "displayName", "userId", "uid"):
        value = info.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
            text = str(value)
            if any(secret and secret in text for secret in secrets):
                continue
            if re.search(r"(?<!\d)(?:\+?86)?1[3-9]\d{9}(?!\d)", text):
                continue
            log(f"账号身份 {key}：{json.dumps(value, ensure_ascii=False)}")
    for key, label in (("kwbeans", "当前总积分"), ("expPoints", "经验值"), ("coin", "创想币")):
        value = info.get(key)
        if numeric(value):
            log(f"{label}：{value}")


class Stages:
    def __init__(self, index):
        self.index = index
        self.counts = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
        self.number = 0

    def run(self, label, action, outcome="success"):
        self.number += 1
        start = time.monotonic()
        log(f"账号 {self.index} · 阶段 {self.number} · {label} 开始")
        try:
            result = action()
        except Exception:
            self.counts["failure"] += 1
            log(f"❌ 阶段 {self.number} · {label} 失败，耗时 {time.monotonic()-start:.2f} 秒")
            raise
        self.counts[outcome] += 1
        icon = {"success": "✅", "skipped": "⏭️", "alreadyComplete": "☑️"}[outcome]
        log(f"{icon} 阶段 {self.number} · {label} 完成，耗时 {time.monotonic()-start:.2f} 秒")
        return result


def run_single(index, line):
    started = time.monotonic()
    stages = Stages(index)
    ok = False
    already = False
    try:
        def parse():
            parts = line.split(None, 1)
            if len(parts) != 2 or not parts[1].strip():
                raise ValueError("账号行应为：账号 空格 密码")
            parse_account(parts[0])
            return parts[0], parts[1]
        account, password = stages.run("参数检查", parse)
        if dry_run():
            for label in ("密码登录及 OAuth 回退", "最近签到状态查询", "每日签到", "连续天数及奖励回查", "身份与积分查询"):
                stages.run(label, lambda: log("断网预演：已验证流程配置，未请求接口、未修改账户"), "skipped")
            log("DRY_RUN_OK：账号参数有效；业务未执行")
            ok = True
        else:
            token, uid, opener = stages.run("密码登录", lambda: login(account, password))
            log(f"登录成功，官方用户标识：{json.dumps(uid, ensure_ascii=False)}" if
                not re.search(r"(?:\+?86)?1[3-9]\d{9}", str(uid)) and
                not any(secret and secret in str(uid) for secret in (account, password, token))
                else "登录成功")

            def authenticated(action):
                nonlocal token, uid
                body = action(token, uid)
                if type(body.get("code")) is int and body["code"] == 4:
                    log("⚠️ 直接登录态失效，使用原有 OAuth 授权码回退")
                    token, uid = stages.run("OAuth 授权码换取登录态", lambda: oauth_exchange_token(token, opener))
                    body = action(token, uid)
                return require_ok(body, "请求")

            def status_query():
                body = authenticated(get_last_checkin)
                has_did = result_dict(body).get("hasDid")
                if type(has_did) is not bool and not (type(has_did) is int and has_did in (0, 1)):
                    raise ApiError("签到状态 hasDid 缺失或格式错误；拒绝盲目签到")
                return body
            last = stages.run("最近签到状态查询", status_query)
            already = bool(result_dict(last)["hasDid"])
            if already:
                stages.run("每日签到", lambda: log("今日已签到，无需重复"), "alreadyComplete")
                stages.run("连续天数与奖励", lambda: show_checkin_details(last))
            else:
                stages.run("每日签到", lambda: authenticated(do_checkin))
                log("🎉 签到成功：官方业务码为 0")
                # 与上游一致，回查及积分失败只提示，不改变已确认的签到结果。
                try:
                    def details():
                        body = authenticated(get_last_checkin)
                        show_checkin_details(body)
                    stages.run("连续天数与奖励回查", details)
                except Exception as exc:
                    reason = str(exc) if isinstance(exc, ApiError) else "辅助查询结构或运行异常（已脱敏）"
                    log(f"⚠️ {reason}；签到结果已确认")
            try:
                stages.run("身份与积分查询", lambda: show_user_info(get_user_info(token, uid), (account, password, token)))
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ApiError) else "辅助查询结构或运行异常（已脱敏）"
                log(f"⚠️ {reason}；签到结果已确认")
            ok = True
    except (ApiError, ValueError) as exc:
        log(f"❌ 账号 {index}：{exc}")
    except Exception:
        log(f"❌ 账号 {index}：响应结构或运行异常（详情已脱敏）")
    elapsed = round(time.monotonic() - started, 2)
    total = sum(stages.counts.values())
    log(f"账号 {index} 统计：总任务 {total}，成功 {stages.counts['success']}，已完成 {stages.counts['alreadyComplete']}，跳过 {stages.counts['skipped']}，失败 {stages.counts['failure']}；耗时 {elapsed} 秒；{'成功' if ok else '失败'}")
    return dict(account=index, ok=ok, alreadyComplete=already, stages=stages.counts, elapsedSeconds=elapsed)


def load_accounts():
    raw = os.environ.get(ENV_ACCOUNTS, "").strip() or CONFIG_ACCOUNTS.strip()
    return [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def random_delay():
    if dry_run() or os.getenv(ENV_RANDOM_SIGNIN, "true").lower() != "true":
        return
    try:
        maximum = int(os.getenv(ENV_MAX_RANDOM_DELAY, "3600") or "3600")
    except ValueError:
        maximum = 3600  # 保留上游兼容行为
    remaining = random.randint(0, max(0, maximum))
    while remaining:
        log(f"整体随机延时剩余 {remaining} 秒")
        step = min(10, remaining)
        time.sleep(step)
        remaining -= step


def notify_user(content):
    if os.getenv("QINGLONG_NOTIFY", "1").strip().lower() in FALSE_VALUES:
        log("⏭️ 通知已通过 QINGLONG_NOTIFY 关闭")
        return "disabled"
    # 隔离通知模块的输出/异常及退出码；限时结束，不影响业务退出码。
    # dry-run 尝试调用通知模块，但审计钩子禁止网络与外部命令。
    child = r'''
import importlib.util, json, os, sys
payload = json.loads(sys.stdin.read())
if payload["dry"]:
    def deny(event, args):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"}:
            raise RuntimeError("dry-run network disabled")
    sys.addaudithook(deny)
try:
    try:
        from notify import send
    except ImportError:
        send = None
        paths = []
        if os.getenv("QINGLONG_NOTIFY_DIR"):
            paths.append(os.path.join(os.environ["QINGLONG_NOTIFY_DIR"], "notify.py"))
        paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
        for path in paths:
            if os.path.isfile(path):
                spec = importlib.util.spec_from_file_location("qinglong_notify", path)
                mod = importlib.util.module_from_spec(spec)
                sys.path.insert(0, os.path.dirname(path))
                spec.loader.exec_module(mod)
                send = mod.send
                break
    if send is None:
        sys.exit(3)
    send(payload["title"], payload["body"])
except Exception:
    sys.exit(4)
'''
    env = dict(os.environ)
    env.pop(ENV_ACCOUNTS, None)
    try:
        proc = subprocess.run([sys.executable, "-c", child],
                              input=json.dumps(dict(title=TITLE, body=content, dry=dry_run())),
                              text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=os.path.dirname(os.path.abspath(__file__)), env=env, timeout=30)
        status = "sent" if proc.returncode == 0 else "unavailable" if proc.returncode == 3 else "failed"
    except (OSError, subprocess.TimeoutExpired):
        status = "failed"
    log(f"通知状态：{status}" + ("（断网预演，网络发送被禁止）" if dry_run() else "") + "；保留业务退出码")
    return status


def main():
    started = time.monotonic()
    start_time = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    mode = "dry-run" if dry_run() else "live"
    print("=" * 56)
    log(TITLE + " · 国内站")
    log(f"开始时间：{start_time}；运行模式：{mode}")
    accounts = load_accounts()
    log(f"账号总数：{len(accounts)}")
    results = []
    if not accounts:
        log("❌ 配置错误：请设置 CREALITY_ACCOUNTS，每行账号 空格 密码")
    else:
        log("阶段 0 · 整体随机延时" + ("（预演跳过）" if dry_run() else ""))
        random_delay()
        for index, line in enumerate(accounts, 1):
            if index > 1 and not dry_run():
                delay = random.uniform(10, 30)
                log(f"账号间随机等待 {delay:.1f} 秒")
                time.sleep(delay)
            results.append(run_single(index, line))
    success = sum(item["ok"] for item in results)
    failed = len(results) - success
    exit_code = 0 if accounts and not failed else 1
    status = "configuration-error" if not accounts else "dry-run" if dry_run() and not failed else "success" if not failed else "partial-failure" if success else "failure"
    counts = {key: sum(item["stages"][key] for item in results) for key in ("success", "alreadyComplete", "skipped", "failure")}
    print("-" * 56)
    log(f"签到结果：账号总数 {len(accounts)}，成功 {success} 个，失败 {failed} 个")
    log(f"子任务统计：总任务 {sum(counts.values())}，成功 {counts['success']}，已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failure']}")
    report = f"{TITLE}：模式 {mode}，状态 {status}；账号总数 {len(accounts)}，成功 {success}，失败 {failed}；子任务失败 {counts['failure']}。"
    notification = notify_user(report)
    finish = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    elapsed = round(time.monotonic() - started, 2)
    log(f"完成时间：{finish}；总耗时 {elapsed} 秒；最终状态：{status}；退出码：{exit_code}")
    print("TASK_SUMMARY=" + json.dumps(dict(task=TITLE, mode=mode, status=status,
        accounts=len(accounts), success=success, failed=failed, stages=counts,
        results=results, startTime=start_time, finishTime=finish,
        elapsedSeconds=elapsed, notification=notification, exitCode=exit_code), ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
