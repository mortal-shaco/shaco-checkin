#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: mybt 每日签到与访问积分
# cron: 2 8 * * *
"""独立 mybt 维护脚本，Python 3.9+，仅使用标准库。

来源：elongou-checkin/mybt-signin / signin.py，MIT 许可。
上游提交：f4bafa58df133dc3185e1f7908bb21ffc5d577e6。
提供的源文件未包含单独的版权声明；保留其来源与许可归属。

MIT License
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

参数：MYBT_ACCOUNTS 每个非空行一个 JSON 对象；推荐字段 token，或 username、
password。可同时提供两种登录方式，自动登录失败后回退 token。可选字段 cookie、
user_id、turnstile_token、secret。不要使用 & 或 @ 分隔账号。
也支持 username|password，每行仅在第一个 | 分割，密码里的 | 保留。
Token/Cookie 从本人登录 mybt 后的开发者工具网络请求中获取；账号密码为本人
Casdoor 账号；验证码令牌须从本人交互式验证获取，过期后重新验证，不绕过验证。
旧环境变量 MYBT_TOKEN、MYBT_USERNAME/MYBT_PASSWORD（兼容 CASDOOR_*）等
仅在未设置 MYBT_ACCOUNTS 时作为单账号输入。详细字段见同包 contract.json。
MYBT_DO_VISIT 默认 1；MYBT_DRY_RUN=1 完全断网，只检查配置，不声明业务成功。
上游没有 cron 元数据；这里建议每日 08:00，按青龙服务器时区运行。
不自动注册、修改资料、发帖、消费积分或保存新令牌。
"""
from __future__ import annotations
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
        _ql_notify_identities = ('3ec01ce8ee76b6c7', 'scripts/mybt.py', 'mybt.py', 'mybt')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import hashlib
import hmac
import http.cookiejar
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "mybt 每日签到与访问积分"
CATALOG_ID = "3ec01ce8ee76b6c7"
TRUE = {"1", "true", "yes", "on", "y"}
FALSE = {"0", "false", "no", "off", "n"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
MAX_BYTES = 1024 * 1024


class TaskError(Exception):
    """仅承载脚本生成的安全错误，不包含响应、URL 或凭据。"""


def env(name, default=""):
    return os.environ.get(name, default).strip()


def flag(name, default=False):
    value = env(name, "1" if default else "0").lower()
    if value not in TRUE | FALSE:
        raise TaskError(f"{name} 只能使用布尔开关值")
    return value in TRUE


def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


def origin(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise TaskError("服务地址必须为不含凭据的 HTTPS 地址")
    try:
        port = p.port or 443
    except ValueError:
        raise TaskError("服务地址端口无效") from None
    return p.hostname.lower(), port


def base_address(name, default):
    value = env(name, default).rstrip("/")
    origin(value)
    p = urllib.parse.urlsplit(value)
    if p.path or p.query or p.fragment:
        raise TaskError(f"{name} 仅支持 HTTPS 站点根地址")
    return value


class GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed, enabled):
        self.allowed = allowed
        self.enabled = enabled

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.enabled or origin(newurl) not in self.allowed:
            raise TaskError("拒绝意外重定向，未转发凭据")
        if req.get_method() not in {"GET", "HEAD"}:
            raise TaskError("拒绝重定向带凭据的提交请求")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTP:
    def __init__(self, urls, dry=False, redirects=False):
        self.allowed = {origin(url) for url in urls}
        self.dry = dry
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            GuardedRedirect(self.allowed, redirects),
        )

    def request(self, url, method="GET", obj=None, headers=None, body=None):
        if self.dry:
            raise TaskError("断网预演禁止 HTTP 请求")
        if origin(url) not in self.allowed:
            raise TaskError("拒绝向非预期站点发送请求")
        h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
             "Accept-Language": "zh-CN,zh;q=0.9"}
        if obj is not None:
            body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        request = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        except TaskError:
            raise
        except Exception:
            raise TaskError("网络请求失败或超时，请检查连接及服务状态") from None
        try:
            with response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise TaskError("响应过大，已拒绝处理")
                return response.geturl(), response.code, dict(response.headers), raw
        except TaskError:
            raise
        except Exception:
            raise TaskError("读取网络响应失败") from None


def object_response(result):
    _, status, _, raw = result
    if not 200 <= status < 300:
        raise TaskError(f"接口返回 HTTP {status}，未确认业务成功")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise TaskError("响应不是有效 JSON，未确认业务成功") from None
    if not isinstance(value, dict):
        raise TaskError("响应结构不符，未确认业务成功")
    return value


def rejected(data):
    if data.get("error") or data.get("success") is False or data.get("ok") is False:
        return True
    if "code" in data and (type(data["code"]) not in {str, int} or data["code"] not in (0, 200, "0", "200")):
        return True
    return "status" in data and data["status"] not in ("ok", "success", 0, 200)


def numeric(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def sort_query(query):
    values = {}
    for pair in query.split("&") if query else []:
        key, sep, val = pair.partition("=")
        values[key] = val if sep else None
    return "&".join(k if values[k] is None else f"{k}={values[k]}" for k in sorted(values))


def build_sign_headers(method, api_path, body, secret):
    path, _, query = api_path.partition("?")
    timestamp = str(int(time.time()))
    digest = hashlib.sha256((body or "").encode("utf-8")).hexdigest()
    canonical = f"{method.upper()}\n{path}\n{sort_query(query)}\n{digest}\n{timestamp}"
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"X-Sign": signature, "X-Timestamp": timestamp}


class CasdoorLogin:
    def __init__(self, base, auth, account, dry=False):
        self.base, self.auth, self.account = base, auth, account
        self.http = HTTP([base, auth], dry, redirects=True)

    @staticmethod
    def param(url, key):
        p = urllib.parse.urlsplit(url)
        return (urllib.parse.parse_qs(p.query).get(key) or
                urllib.parse.parse_qs(p.fragment).get(key) or [""])[0].strip()

    def finish(self, result):
        url, status, headers, body = result
        if not 200 <= status < 400:
            raise TaskError(f"登录回调 HTTP {status}")
        location = headers.get("Location") or headers.get("location")
        if location:
            url = urllib.parse.urljoin(url, location)
        if origin(url) != origin(self.base):
            return ""
        token = self.param(url, "token")
        if not token:
            text = body.decode("utf-8", "replace")
            match = re.search(r"[?&#]token=([A-Za-z0-9_\-.]+)", text)
            token = match.group(1) if match else ""
        if token:
            return token
        login_code = self.param(url, "login_code")
        if login_code:
            log("登录回调使用 login_code，正在交换会话令牌")
            payload = object_response(self.http.request(
                self.base + "/api/auth/session", "POST", {"login_code": login_code},
                {"Origin": self.base, "Referer": self.base + "/login"}))
            if rejected(payload):
                raise TaskError("会话交换被服务拒绝")
            token = payload.get("token")
            if not token and isinstance(payload.get("data"), dict):
                token = payload["data"].get("token")
            if isinstance(token, str) and token.strip():
                return token.removeprefix("Bearer ").strip()
            raise TaskError("会话交换未返回令牌")
        return ""

    def login(self):
        result = self.http.request(self.base + "/api/auth/casdoor/login")
        token = self.finish(result)
        if token:
            return token
        authorize_url, status, _, _ = result
        if not 200 <= status < 400:
            raise TaskError(f"OAuth 初始化 HTTP {status}")
        if origin(authorize_url) != origin(self.auth):
            raise TaskError("OAuth 授权站点不匹配，请检查 MYBT_AUTH_URL")
        params = {k: self.param(authorize_url, k) for k in ("client_id", "redirect_uri", "scope", "state")}
        if not params["client_id"] or not params["redirect_uri"]:
            raise TaskError("OAuth 缺少 client_id 或 redirect_uri")
        if origin(params["redirect_uri"]) != origin(self.base):
            raise TaskError("OAuth 回调地址不属于配置的 mybt 站点")
        query = {"clientId": params["client_id"], "responseType": "code", "type": "code",
                 "redirectUri": params["redirect_uri"], "scope": params["scope"] or "openid profile email",
                 "state": params["state"]}
        suffix = "?" + urllib.parse.urlencode(query)
        app_json = object_response(self.http.request(self.auth + "/api/get-app-login" + suffix))
        if app_json.get("status") != "ok" or not isinstance(app_json.get("data"), dict):
            raise TaskError("Casdoor 未返回有效应用信息")
        app = app_json["data"]
        payload = {"application": app.get("name") or "KiteYuan KiteMagnet",
                   "organization": app.get("organization") or "KiteYuan Users Organization",
                   "username": self.account["username"], "password": self.account["password"],
                   "autoSignin": True, "type": "code", "signinMethod": "Password"}
        if self.account.get("turnstile_token"):
            payload.update(captchaType="Cloudflare Turnstile", captchaToken=self.account["turnstile_token"],
                           captchaCode=self.account["turnstile_token"])
        result = self.http.request(self.auth + "/api/login" + suffix, "POST", payload,
                                   {"Origin": self.auth, "Referer": authorize_url})
        data = object_response(result)
        if data.get("status") != "ok":
            message = str(data.get("msg") or data.get("message") or "").lower()
            if any(s in message for s in ("captcha", "turnstile", "人机")):
                raise TaskError("登录需要重新完成本人验证码验证；请更新验证码令牌或使用有效 Token")
            raise TaskError("Casdoor 登录被拒绝，请检查账号密码及验证要求")
        code = ""
        for value in (data.get("data"), data.get("data2")):
            if isinstance(value, dict):
                value = value.get("code") or value.get("authCode")
            if isinstance(value, str) and value:
                if value.startswith(("https://", "http://")):
                    if origin(value) not in {origin(self.base), origin(self.auth)}:
                        raise TaskError("授权结果指向非预期站点")
                    code = self.param(value, "code")
                elif len(value) < 4096:
                    code = value
                if code:
                    break
        if not code:
            log("登录已接受，继续授权回调以获取会话")
            result = self.http.request(authorize_url)
            token = self.finish(result)
            if token:
                return token
            code = self.param(result[0], "code")
            if not code:
                match = re.search(r"code=([A-Za-z0-9_\-.]+)", result[3].decode("utf-8", "replace"))
                code = match.group(1) if match else ""
        if not code:
            raise TaskError("授权结果未提供可用授权码或令牌")
        callback = self.base + "/api/auth/casdoor/callback?" + urllib.parse.urlencode({"code": code, "state": params["state"]})
        token = self.finish(self.http.request(callback))
        if not token:
            raise TaskError("登录回调未返回令牌或 login_code")
        return token


class MybtClient:
    def __init__(self, base, token, account, dry=False):
        self.base = base
        self.token = token.removeprefix("Bearer ").strip()
        self.cookie = account.get("cookie", "")
        self.secret = account.get("secret") or env("MYBT_SECRET", "change-this-secret")
        self.http = HTTP([base], dry)

    def request(self, method, path, obj=None):
        path = "/api" + path
        body = "" if obj is None else json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json",
                   "Origin": self.base, "Referer": self.base + "/"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        headers.update(build_sign_headers(method, path, body, self.secret))
        return self.http.request(self.base + path, method, headers=headers,
                                 body=None if obj is None else body.encode("utf-8"))

    def me(self):
        payload = object_response(self.request("GET", "/auth/me"))
        if rejected(payload) or not isinstance(payload.get("user"), dict) or not payload["user"]:
            raise TaskError("账号信息未通过业务校验，请检查登录凭据")
        user = payload["user"]
        if not any(user.get(k) is not None and user.get(k) != "" for k in ("id", "uid", "username", "nickname", "displayName", "display_name", "name")):
            raise TaskError("账号信息缺少身份字段，未确认登录成功")
        if payload.get("sign_secret"):
            if not isinstance(payload["sign_secret"], str):
                raise TaskError("接口签名密钥格式异常")
            self.secret = payload["sign_secret"]
        return user

    def action(self, name):
        result = self.request("POST", "/auth/points/tasks/" + name, {})
        _, status, _, raw = result
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("任务响应不是有效 JSON，未确认成功") from None
        if not isinstance(data, dict):
            raise TaskError("任务响应结构异常，未确认成功")
        message = str(data.get("error") or data.get("message") or data.get("msg") or "").strip().lower()
        # 不使用上游对任意 2xx 的宽松判定；仅接受已观察到的 added 字段或明确重复完成语义。
        already = message in {"已签到", "今日已签到", "今天已签到", "已完成", "今日已完成", "已领取",
                              "already signed in", "already checked in", "already completed", "already claimed"}
        if status in {200, 400, 409} and already and data.get("success") is not False:
            return "already", "☑️ 服务确认今日已完成"
        if not 200 <= status < 300 or rejected(data):
            raise TaskError(f"任务被拒绝（HTTP {status}），未确认成功")
        added = data.get("added")
        if not numeric(added) or added < 0:
            raise TaskError("任务未返回有效 added 积分字段，未确认成功")
        return "success", f"✅ 任务成功，获得 {added} 积分"


def load_accounts():
    if "MYBT_ACCOUNTS" in os.environ:
        lines = [line for line in os.environ["MYBT_ACCOUNTS"].splitlines() if line.strip()]
        accounts = []
        for line in lines:
            try:
                if line.lstrip().startswith("{"):
                    item = json.loads(line)
                elif "|" in line:
                    username, password = line.split("|", 1)
                    item = {"username": username, "password": password}
                else:
                    raise ValueError()
                accounts.append(item if isinstance(item, dict) else {"_invalid": True})
            except ValueError:
                accounts.append({"_invalid": True})
        return accounts
    item = {
        "token": env("MYBT_TOKEN"), "username": env("MYBT_USERNAME") or env("CASDOOR_USERNAME"),
        "password": env("MYBT_PASSWORD") or env("CASDOOR_PASSWORD"), "cookie": env("MYBT_COOKIE"),
        "user_id": env("MYBT_USER_ID"), "turnstile_token": env("MYBT_TURNSTILE_TOKEN"),
    }
    return [item] if any(item.values()) else []


def validate_account(item):
    allowed = {"token", "username", "password", "cookie", "user_id", "turnstile_token", "secret"}
    if set(item) - allowed:
        raise TaskError("账号行不是有效对象或含未知字段，请按契约填写")
    if any(not isinstance(value, str) or any(c in value for c in "\r\n\x00") for value in item.values()):
        raise TaskError("账号字段必须为无换行的字符串")
    token = item.get("token", "").removeprefix("Bearer ").strip()
    if not token and bool(item.get("username")) != bool(item.get("password")):
        raise TaskError("username 和 password 必须成对提供")
    if not token and not (item.get("username") and item.get("password")):
        raise TaskError("缺少 token 或 username/password 凭据")


def public_value(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value)
    for secret in sorted((s for s in secrets if isinstance(s, str) and s), key=len, reverse=True):
        text = text.replace(secret, "[凭据已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]", " ", text)
    return text


def show_user(user, secrets):
    fields = [(label, public_value(user.get(key), secrets)) for key, label in (
        ("nickname", "昵称"), ("username", "用户名"), ("displayName", "显示名称"),
        ("display_name", "显示名称"), ("name", "名称"), ("uid", "公开 UID"), ("id", "公开 UID"))]
    visible = [f"{label}: {value}" for label, value in fields if value]
    points = user.get("points")
    if numeric(points):
        visible.append(f"积分: {points}")
    log("；".join(visible) if visible else "接口未返回可公开显示的身份")


class AccountRun:
    def __init__(self, number, dry):
        self.number, self.dry = number, dry
        self.started = time.monotonic()
        self.stats = dict(total=0, success=0, already=0, skipped=0, failed=0)

    def stage(self, title, call=None, skip=False):
        self.stats["total"] += 1
        stage = self.stats["total"]
        started = time.monotonic()
        log(f"账号 {self.number} · 阶段 {stage} · {title} · 开始")
        try:
            if skip:
                outcome, message, value = "skipped", "⏭️ 已按配置跳过", None
            elif self.dry and call is None:
                outcome, message, value = "skipped", "⏭️ 断网预演：仅展示计划，未执行业务请求", None
            else:
                value = call()
                outcome, message = value if isinstance(value, tuple) else ("success", "✅ 阶段校验通过")
            self.stats[outcome] += 1
            log(f"账号 {self.number} · 阶段 {stage} · {message} · 耗时 {time.monotonic() - started:.2f} 秒")
            return True, value
        except Exception as exc:
            self.stats["failed"] += 1
            message = str(exc) if isinstance(exc, TaskError) else "内部处理失败（详情已隐藏），请检查接口契约"
            log(f"账号 {self.number} · 阶段 {stage} · ❌ {message} · 耗时 {time.monotonic() - started:.2f} 秒")
            return False, None

    def finish(self):
        elapsed = round(time.monotonic() - self.started, 3)
        ok = not self.stats["failed"]
        log(f"账号 {self.number} 统计：总任务 {self.stats['total']}，成功 {self.stats['success']}，"
            f"已完成 {self.stats['already']}，跳过 {self.stats['skipped']}，失败 {self.stats['failed']}，"
            f"耗时 {elapsed:.2f} 秒，状态 {'预演通过' if self.dry and ok else '成功' if ok else '失败'}")
        return {"account": self.number, "ok": ok, "tasks": self.stats, "seconds": elapsed}


def run_account(number, item, base, auth, dry, do_visit):
    run = AccountRun(number, dry)
    valid, _ = run.stage("配置校验", lambda: validate_account(item))
    if not valid:
        return run.finish()
    if dry:
        for title in ("Casdoor 续期及 Token 兜底计划", "账号与签名密钥校验", "每日签到"):
            run.stage(title)
        run.stage("访问积分", skip=not do_visit)
        run.stage("完成后积分查询")
        return run.finish()
    secrets = [item.get(key, "") for key in ("token", "password", "cookie", "turnstile_token", "secret")]
    secrets.append(env("MYBT_SECRET"))
    secrets.append(item.get("token", "").removeprefix("Bearer ").strip())
    for part in item.get("cookie", "").split(";"):
        if "=" in part:
            secrets.append(part.split("=", 1)[1].strip())

    def authenticate():
        token = item.get("token", "")
        if item.get("username") and item.get("password"):
            try:
                token = CasdoorLogin(base, auth, item).login()
                log("✅ Casdoor 登录成功，令牌仅在内存使用")
            except Exception as exc:
                detail = str(exc) if isinstance(exc, TaskError) else "登录流程异常，详情已隐藏"
                if not token:
                    raise TaskError(detail + "；无备用 Token，请检查账号密码或验证码") from None
                log(f"⚠️ {detail}；回退已有 Token，后续接口将核验其有效性")
        if not token.removeprefix("Bearer ").strip():
            raise TaskError("未获取有效令牌")
        secrets.append(token)
        secrets.append(token.removeprefix("Bearer ").strip())
        return MybtClient(base, token, item)

    ok, client = run.stage("Casdoor 续期及 Token 兜底", authenticate)
    if ok:
        ok, user = run.stage("账号与签名密钥校验", client.me)
        if ok:
            secrets.append(client.secret)
            show_user(user, secrets)
    else:
        run.stage("账号与签名密钥校验", skip=True)
    if not ok:
        for title in ("每日签到", "访问积分", "完成后积分查询"):
            run.stage(title, skip=True)
        return run.finish()
    run.stage("每日签到", lambda: client.action("signin"))
    run.stage("访问积分", lambda: client.action("visit"), skip=not do_visit)
    final_ok, user = run.stage("完成后积分查询", client.me)
    if final_ok:
        secrets.append(client.secret)
        show_user(user, secrets)
        points = user.get("points")
        if numeric(points):
            print(f"points_after: {points}", flush=True)
    return run.finish()


def notification_selected():
    switch = env("QINGLONG_NOTIFY", "auto").lower()
    if switch in FALSE:
        return False
    if switch not in TRUE | {"auto"}:
        log("⚠️ QINGLONG_NOTIFY 无效，通知已禁用")
        return False
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True  # 本脚本列入通知默认清单。
    selectors = re.split(r"[,;\s]+", os.environ["QINGLONG_NOTIFY_SCRIPTS"].strip())
    path = Path(__file__)
    names = {CATALOG_ID, path.name, path.as_posix()}
    for marker in ("/ql/data/scripts/", "/ql/scripts/"):
        if marker in path.as_posix():
            names.add(path.as_posix().split(marker, 1)[1])
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in selectors if pattern for name in names)


def qinglong_notify(body):
    # 子进程隔离青龙通知模块；捕获而不回显第三方日志，异常不能改变业务退出码。
    python_code = """import importlib, importlib.util, json, sys
p = json.load(sys.stdin)
if p['path']:
    spec = importlib.util.spec_from_file_location('qinglong_task_notify', p['path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    module = importlib.import_module('notify')
module.send(p['title'], p['body'])
"""
    paths = [None]
    if env("QINGLONG_NOTIFY_DIR"):
        paths.append(str(Path(env("QINGLONG_NOTIFY_DIR")) / "notify.py"))
    paths.extend(["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"])
    for path in paths:
        if path is not None and not Path(path).is_file():
            continue
        try:
            result = subprocess.run([sys.executable, "-c", python_code],
                input=json.dumps({"path": path, "title": TITLE, "body": body}),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
            if result.returncode == 0:
                return "已调用青龙通知"
        except Exception:
            pass
    directories = ([env("QINGLONG_NOTIFY_DIR")] if env("QINGLONG_NOTIFY_DIR") else [])
    directories.extend(["/ql/data/scripts", "/ql/scripts"])
    node_code = "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));Promise.resolve().then(()=>require(p.path).sendNotify(p.title,p.body)).catch(()=>{process.exitCode=1});"
    for directory in directories:
        path = Path(directory) / "sendNotify.js"
        if not path.is_file():
            continue
        try:
            result = subprocess.run(["node", "-e", node_code],
                input=json.dumps({"path": str(path.resolve()), "title": TITLE, "body": body}),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
            if result.returncode == 0:
                return "已调用青龙通知"
        except Exception:
            pass
    return "青龙通知不可用或失败（不改变业务退出码）"


def legacy_notifications(ok, body):
    """保留上游可选通知：微信测试号优先，失败后 WxPusher 和配置的 PushPlus。"""
    def request(url, payload=None):
        return object_response(HTTP([url]).request(url, "POST" if payload is not None else "GET", payload))

    title = "mybt 签到成功" if ok else "mybt 签到失败"
    appid, secret, template, openid = [env(k) for k in ("WX_TEST_APPID", "WX_TEST_APP_SECRET", "WX_TEST_TEMPLATE_ID", "WX_TEST_OPENID")]
    if all((appid, secret, template, openid)):
        try:
            query = urllib.parse.urlencode({"grant_type": "client_credential", "appid": appid, "secret": secret})
            data = request("https://api.weixin.qq.com/cgi-bin/token?" + query)
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise TaskError("微信测试号未返回令牌")
            data = request("https://api.weixin.qq.com/cgi-bin/message/template/send?" + urllib.parse.urlencode({"access_token": token}),
                {"touser": openid, "template_id": template, "data": {"result": {"value": title}, "detail": {"value": body[:200]}}})
            if data.get("errcode") == 0:
                log("✅ 微信测试号通知已发送")
                return
            raise TaskError("微信测试号返回失败")
        except Exception:
            log("⚠️ 微信测试号通知失败，继续备用通知渠道（详情已隐藏）")
    app_token, uids = env("WXPUSHER_APP_TOKEN"), [x.strip() for x in env("WXPUSHER_UIDS").split(",") if x.strip()]
    if app_token and uids:
        try:
            data = request("https://wxpusher.zjiecode.com/api/send/message", {"appToken": app_token, "content": title + "\n" + body,
                           "summary": title, "contentType": 1, "uids": uids})
            log("✅ WxPusher 通知已发送" if data.get("code") == 1000 else "⚠️ WxPusher 通知失败（详情已隐藏）")
        except Exception:
            log("⚠️ WxPusher 通知失败（详情已隐藏）")
    if env("PUSHPLUS_TOKEN"):
        try:
            data = request("https://www.pushplus.plus/send", {"token": env("PUSHPLUS_TOKEN"), "title": title, "content": body, "template": "txt"})
            log("✅ PushPlus 通知已发送" if data.get("code") == 200 else "⚠️ PushPlus 通知失败（详情已隐藏）")
        except Exception:
            log("⚠️ PushPlus 通知失败（详情已隐藏）")


def main():
    started, start_time = time.monotonic(), time.strftime("%Y-%m-%d %H:%M:%S")
    accounts, results = [], []
    # 错写预演开关时也禁止错误收尾意外联网；flag 随后报告配置错误。
    dry = "MYBT_DRY_RUN" in os.environ and env("MYBT_DRY_RUN").lower() not in FALSE
    configured, interrupted = True, False
    log("========== " + TITLE + " ==========")
    log("开始时间：" + start_time)
    try:
        accounts = load_accounts()
        dry = flag("MYBT_DRY_RUN")
        log(f"运行模式：{'断网预演' if dry else '正式执行'}；账号总数：{len(accounts)}")
        base = base_address("MYBT_BASE_URL", "https://mybt.kiteyuan.info")
        auth = base_address("MYBT_AUTH_URL", "https://auth.kiteyuan.info")
        do_visit = flag("MYBT_DO_VISIT", True)
        if not accounts:
            raise TaskError("未配置账号，请设置 MYBT_ACCOUNTS；兼容旧单账号凭据变量")
        for number, item in enumerate(accounts, 1):
            try:
                result = run_account(number, item, base, auth, dry, do_visit)
            except Exception:
                failed_run = AccountRun(number, dry)
                def account_error():
                    raise TaskError("账号处理异常，详情已隐藏；继续其他账号")
                failed_run.stage("账号处理", account_error)
                result = failed_run.finish()
            results.append(result)
    except KeyboardInterrupt:
        interrupted = True
        log("❌ 用户中断，未完成的账号不能视为成功")
    except Exception as exc:
        configured = False
        log("❌ 配置错误：" + (str(exc) if isinstance(exc, TaskError) else "配置处理失败，详情已隐藏"))
        log(f"运行模式：{'断网预演' if dry else '未执行'}；账号总数：{len(accounts)}")
    successes = sum(item["ok"] for item in results)
    failures = len(accounts) - successes
    exit_code = 130 if interrupted else 2 if not configured else 1 if failures else 0
    status = ("configuration-error" if not configured else "failure" if interrupted else
              "partial-failure" if failures and successes else "failure" if failures else "dry-run" if dry else "success")
    totals = {key: sum(item["tasks"][key] for item in results) for key in ("total", "success", "already", "skipped", "failed")}
    log("--------------------------------------------------")
    body = (f"状态：{status}；模式：{'断网预演，未执行业务' if dry else '正式执行'}；"
            f"账号总数：{len(accounts)}，成功数：{successes}，失败数：{failures}；"
            f"子任务总数：{totals['total']}，成功：{totals['success']}，已完成：{totals['already']}，"
            f"跳过：{totals['skipped']}，失败：{totals['failed']}")
    log(body)
    notification = "已禁用"
    try:
        if notification_selected():
            if dry:
                notification = "断网预演：已生成脱敏通知摘要，未发送通知"
            else:
                notification = qinglong_notify(body)
                legacy_notifications(exit_code == 0, body)
    except Exception:
        notification = "通知异常（不改变业务退出码）"
    log("通知状态：" + notification)
    finish_time = time.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = round(time.monotonic() - started, 3)
    log(f"总耗时：{elapsed:.2f} 秒；完成时间：{finish_time}；最终状态：{status}；退出码：{exit_code}")
    if not dry:
        print("DONE: success" if exit_code == 0 else "DONE: failed", flush=True)
    elif exit_code == 0:
        log("MYBT_DRY_RUN_OK：配置校验通过，未执行网络请求或业务操作")
    summary = {"applicationKey": "mybt", "status": status, "mode": "dry-run" if dry else "live",
               "accounts": len(accounts), "succeeded": successes, "failed": failures, "tasks": totals,
               "accountResults": results, "startTime": start_time, "finishTime": finish_time,
               "seconds": elapsed, "notification": notification, "exitCode": exit_code}
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
