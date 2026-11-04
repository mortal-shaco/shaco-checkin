#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NewAPI 活动中心签到
# cron: 22 8 * * *
# SPDX-License-Identifier: MIT
"""NewAPI fork「活动中心 / 星河 / 晚晚舟」独立签到（仅标准库）。

来源：yan470777-commits/checkin，activity_checkin.py；MIT License。
上游适配部分深度定制 new-api fork：传统 POST /api/user/checkin 被替换为
活动中心白银签到、星河每日领取或晚晚舟 /api/v1 签到。系统访问令牌(nap_)只读，
写操作需账号密码登录获取 JWT。本维护版转为青龙可调度独立任务，不依赖私有
仓库、上游模块或外部可执行文件。

ACTIVITY_CHECKIN_ACCOUNTS：每个非空行一个账号。推荐 JSON：
{"url":"https://站点根","username":"用户名","password":"密码"}；
可选 user_id、site_hint（activity_center / xingya / wanwanzhou / auto）。
也支持「站点|用户名|密码」；仅拆前两个竖线，密码可含竖线。若密码后仍有
「|数字用户ID」或「|site_hint」字段，可再追加；site_hint 须为上述关键字。
在浏览器登录本人站点，使用自己的用户名与密码；user_id 可从 /api/user/self
的 data.id 或请求头 New-Api-User 取得，不能凭用户名猜测。
ACTIVITY_CHECKIN_TIMEOUT：单次请求超时秒数，默认 30，范围 5..120。
ACTIVITY_CHECKIN_DRY_RUN=1：完全断网预演，只校验配置，不声明业务成功。
QINGLONG_NOTIFY=auto/1/0；QINGLONG_NOTIFY_SCRIPTS 与 QINGLONG_NOTIFY_DIR 见契约。
上游未声明 cron；本版建议每天 08:22。不打印密码、JWT、原始响应。

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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "1e2ace06c33b3dec",
            "scripts/activity_checkin.py",
            "activity_checkin.py",
            "candidate.py",
            "activity_checkin",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

TITLE = "NewAPI 活动中心签到"
CATALOG_ID = "1e2ace06c33b3dec"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
SITE_HINTS = {"activity_center", "xingya", "wanwanzhou", "auto"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 1024 * 1024


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def redact_text(value, secrets):
    text = str(value)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def clean_identity(value, secrets):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if not text or any(secret and secret in text for secret in secrets):
        return ""
    if re.fullmatch(r"(?i)bearer\s+\S+", text):
        return ""
    return redact_text(text, secrets)


def normalize_base_url(raw):
    if not isinstance(raw, str):
        raise SafeError("站点地址必须是字符串")
    value = raw.strip().rstrip("/")
    if not value or any(c.isspace() for c in value):
        raise SafeError("站点地址格式错误")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        raise SafeError("站点地址无法解析") from exc
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise SafeError("站点地址须为 http(s) 根地址且含主机名")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SafeError("站点地址不能包含嵌入凭据、查询参数或片段")
    if parsed.path not in ("", "/"):
        raise SafeError("请填写站点根地址，不要带业务路径")
    return "{}://{}".format(parsed.scheme, parsed.netloc)


def parse_timeout():
    raw = os.environ.get("ACTIVITY_CHECKIN_TIMEOUT", "30").strip() or "30"
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("ACTIVITY_CHECKIN_TIMEOUT 必须是整数秒") from exc
    if value < 5 or value > 120:
        raise SafeError("ACTIVITY_CHECKIN_TIMEOUT 允许范围 5..120")
    return value


def parse_account_line(line, index):
    text = line.strip()
    if not text:
        raise SafeError("账号 {} 为空行".format(index))
    data = None
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise SafeError("账号 {} JSON 无法解析".format(index)) from exc
        if not isinstance(payload, dict):
            raise SafeError("账号 {} JSON 必须是对象".format(index))
        data = payload
    else:
        parts = text.split("|", 2)
        if len(parts) < 3:
            raise SafeError(
                "账号 {} 格式错误；请使用 JSON 或「站点|用户名|密码」".format(index)
            )
        url, username, rest = parts[0].strip(), parts[1].strip(), parts[2]
        user_id = None
        site_hint = "auto"
        password = rest
        # 从右侧剥离已知 site_hint，再剥离纯数字 user_id；保留密码中的竖线。
        trail = rest
        while True:
            if "|" not in trail:
                password = trail
                break
            left, right = trail.rsplit("|", 1)
            right = right.strip()
            if right.lower() in SITE_HINTS:
                site_hint = right.lower()
                trail = left
                continue
            if re.fullmatch(r"\d{1,18}", right):
                user_id = right
                trail = left
                continue
            password = trail
            break
        data = {
            "url": url,
            "username": username,
            "password": password,
            "user_id": user_id,
            "site_hint": site_hint,
        }

    url = normalize_base_url(data.get("url") or data.get("base_url") or "")
    username = data.get("username") or data.get("email") or ""
    password = data.get("password") or ""
    if not isinstance(username, str) or not username.strip():
        raise SafeError("账号 {} 缺少用户名".format(index))
    if not isinstance(password, str) or not password:
        raise SafeError("账号 {} 缺少密码".format(index))
    if any(c in username for c in "\r\n") or any(c in password for c in "\r\n"):
        raise SafeError("账号 {} 用户名或密码不能跨行".format(index))
    user_id = data.get("user_id")
    if user_id is None or user_id == "":
        user_id = None
    else:
        user_id = str(user_id).strip()
        if not re.fullmatch(r"\d{1,18}", user_id):
            raise SafeError("账号 {} 的 user_id 须为数字".format(index))
    site_hint = str(data.get("site_hint") or data.get("mode") or "auto").strip().lower()
    if site_hint not in SITE_HINTS:
        raise SafeError(
            "账号 {} 的 site_hint 仅允许 activity_center/xingya/wanwanzhou/auto".format(
                index
            )
        )
    return {
        "url": url,
        "username": username.strip(),
        "password": password,
        "user_id": user_id,
        "site_hint": site_hint,
    }


def load_accounts():
    raw = os.environ.get("ACTIVITY_CHECKIN_ACCOUNTS", "")
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise SafeError(
            "未配置 ACTIVITY_CHECKIN_ACCOUNTS；每个非空行一个账号（JSON 或 站点|用户名|密码）"
        )
    return [parse_account_line(line, index) for index, line in enumerate(lines, 1)]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpClient:
    def __init__(self, timeout, dry_run=False):
        self.timeout = timeout
        self.dry_run = dry_run
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def request(self, url, method="GET", headers=None, body=None, allow_redirect_location=False):
        if self.dry_run:
            raise SafeError("断网预演禁止 HTTP 请求")
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": USER_AGENT,
        }
        if headers:
            request_headers.update(headers)
        if payload is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=payload, headers=request_headers, method=method
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = response.getcode()
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                location = response.headers.get("Location", "")
        except urllib.error.HTTPError as error:
            status = error.code
            location = error.headers.get("Location", "") if error.headers else ""
            try:
                raw = error.read(MAX_RESPONSE_BYTES + 1)
            except Exception:
                raw = b""
            finally:
                error.close()
            if allow_redirect_location and status in (301, 302, 303, 307, 308):
                return status, None, location
        except Exception as exc:
            raise SafeError("网络、超时或 TLS 校验失败") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SafeError("响应超过大小限制")
        if not raw:
            return status, None, location
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeError, ValueError):
            data = None
        return status, data, location


def auth_headers(base_url, jwt, user_id, referer_path="/activities/checkin"):
    return {
        "Authorization": "Bearer {}".format(jwt),
        "New-Api-User": str(user_id or ""),
        "Origin": base_url,
        "Referer": "{}{}".format(base_url, referer_path),
        "Content-Type": "application/json",
    }


def extract_message(payload):
    if not isinstance(payload, dict):
        return "响应不是 JSON 对象"
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()[:160]
    error = payload.get("error")
    if isinstance(error, dict):
        nested = error.get("message")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()[:160]
    return "业务失败"


def jwt_login(http, base_url, username, password):
    status, data, _ = http.request(
        "{}/api/user/login".format(base_url),
        method="POST",
        body={"username": username, "password": password},
    )
    if status in (401, 403):
        raise SafeError("登录凭据无效")
    if status != 200 or not isinstance(data, dict):
        raise SafeError("登录失败（HTTP {}）".format(status))
    token = (data.get("data") or {}).get("access_token") if isinstance(data.get("data"), dict) else None
    if not isinstance(token, str) or not token:
        raise SafeError("登录失败：未返回 JWT")
    user = (data.get("data") or {}).get("user") if isinstance(data.get("data"), dict) else {}
    if not isinstance(user, dict):
        user = {}
    return token, user


def identity_from_user(user, secrets):
    if not isinstance(user, dict):
        return ""
    for key in ("display_name", "displayName", "nickname", "username", "name", "id", "uid"):
        value = clean_identity(user.get(key), secrets)
        if value:
            return value
    return ""


def checkin_activity_center(http, base_url, jwt, user_id):
    headers = auth_headers(base_url, jwt, user_id)
    status, payload, _ = http.request(
        "{}/api/user/activities/status".format(base_url), headers=headers
    )
    if status in (401, 403):
        raise SafeError("活动中心状态查询凭据无效")
    if status != 200 or not isinstance(payload, dict):
        raise SafeError("活动中心状态查询失败（HTTP {}）".format(status))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    checkin = data.get("checkin") if isinstance(data.get("checkin"), dict) else {}
    today = data.get("today")
    calendar = checkin.get("calendar") if isinstance(checkin.get("calendar"), list) else []
    today_records = [item for item in calendar if isinstance(item, dict) and item.get("day") == today]
    if today_records:
        silver = today_records[0].get("silver", 0)
        if not isinstance(silver, (int, float)) or isinstance(silver, bool):
            silver = 0
        return "alreadyComplete", "今日已签到（+{} 白银）".format(int(silver))

    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    if data.get("paused") or not config.get("enabled", True):
        raise SafeError("活动中心签到未启用或已暂停")

    request_id = str(uuid.uuid4())
    status, result, _ = http.request(
        "{}/api/user/activities/command".format(base_url),
        method="POST",
        headers=headers,
        body={"kind": "checkin", "target": None, "request_id": request_id},
    )
    if status in (401, 403):
        raise SafeError("签到命令凭据无效")
    if not isinstance(result, dict):
        raise SafeError("签到命令响应无效（HTTP {}）".format(status))
    if not result.get("success"):
        raise SafeError("活动中心签到失败：{}".format(redact_text(extract_message(result), [])))

    silver = 0
    try:
        status2, status_payload, _ = http.request(
            "{}/api/user/activities/status".format(base_url), headers=headers
        )
        if status2 == 200 and isinstance(status_payload, dict):
            data2 = status_payload.get("data") if isinstance(status_payload.get("data"), dict) else {}
            checkin2 = data2.get("checkin") if isinstance(data2.get("checkin"), dict) else {}
            calendar2 = checkin2.get("calendar") if isinstance(checkin2.get("calendar"), list) else []
            rec = [item for item in calendar2 if isinstance(item, dict) and item.get("day") == today]
            if rec:
                value = rec[0].get("silver", 0)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    silver = int(value)
    except SafeError:
        silver = 0
    return "success", "签到成功（+{} 白银）".format(silver)


def checkin_xingya(http, base_url, jwt, user_id):
    headers = auth_headers(base_url, jwt, user_id, referer_path="/personal")
    status, result, _ = http.request(
        "{}/api/user/xingya-daily-claim".format(base_url),
        method="POST",
        headers=headers,
    )
    if status in (401, 403):
        raise SafeError("星河领取凭据无效")
    if not isinstance(result, dict):
        raise SafeError("星河领取响应无效（HTTP {}）".format(status))
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if result.get("success") or data:
        quota = data.get("quota_awarded", 0)
        if not isinstance(quota, (int, float)) or isinstance(quota, bool):
            quota = 0
        if data.get("already_claimed"):
            return "alreadyComplete", "今日已领取（{} 额度）".format(int(quota))
        return "success", "签到成功（+{} 额度）".format(int(quota))
    raise SafeError("星河领取失败：{}".format(redact_text(extract_message(result), [])))


def is_activity_center_site(http, base_url, jwt, user_id):
    headers = auth_headers(base_url, jwt, user_id)
    try:
        status, _, _ = http.request(
            "{}/api/user/activities/status".format(base_url), headers=headers
        )
    except SafeError:
        return False
    return status != 404


def checkin_wanwanzhou(http, base_url, username, password):
    login_body = {"username": username, "email": username, "password": password}
    headers = {"Content-Type": "application/json"}
    status, data, location = http.request(
        "{}/api/v1/auth/login".format(base_url),
        method="POST",
        headers=headers,
        body=login_body,
        allow_redirect_location=True,
    )
    current_base = base_url
    if status in (301, 302, 303, 307, 308):
        if not isinstance(location, str) or not location.startswith("https://"):
            raise SafeError("登录重定向目标不安全，已停止")
        parsed = urllib.parse.urlsplit(location)
        current_base = "{}://{}".format(parsed.scheme, parsed.netloc)
        status, data, _ = http.request(
            location,
            method="POST",
            headers=headers,
            body=login_body,
        )
    if status in (401, 403):
        raise SafeError("晚晚舟登录凭据无效")
    if not isinstance(data, dict):
        raise SafeError("晚晚舟登录失败（HTTP {}）".format(status))
    token = (data.get("data") or {}).get("access_token") if isinstance(data.get("data"), dict) else None
    if not isinstance(token, str) or not token:
        raise SafeError("晚晚舟登录失败：{}".format(redact_text(extract_message(data), [])))
    user = (data.get("data") or {}).get("user") if isinstance(data.get("data"), dict) else {}
    if not isinstance(user, dict):
        user = {}
    user_id = user.get("id")
    auth = {
        "Authorization": "Bearer {}".format(token),
        "New-Api-User": str(user_id or ""),
        "Content-Type": "application/json",
    }
    status, status_payload, _ = http.request(
        "{}/api/v1/user/checkin".format(current_base), headers=auth
    )
    if status in (401, 403):
        raise SafeError("晚晚舟状态查询凭据无效")
    if not isinstance(status_payload, dict):
        raise SafeError("晚晚舟状态查询失败（HTTP {}）".format(status))
    sdata = status_payload.get("data") if isinstance(status_payload.get("data"), dict) else {}
    identity = identity_from_user(user, [password, token, username])
    if sdata.get("checked_in_today"):
        return "alreadyComplete", "今日已签到", identity
    if not sdata.get("unlocked", True):
        need = sdata.get("invites_needed", 0)
        if not isinstance(need, int):
            need = 0
        raise SafeError("签到未解锁：还需邀请 {} 人".format(need))

    status, result, _ = http.request(
        "{}/api/v1/user/checkin".format(current_base),
        method="POST",
        headers=auth,
    )
    if status in (401, 403):
        raise SafeError("晚晚舟签到凭据无效")
    if not isinstance(result, dict):
        raise SafeError("晚晚舟签到响应无效（HTTP {}）".format(status))
    rdata = result.get("data") if isinstance(result.get("data"), dict) else {}
    if result.get("code") == 0 or rdata:
        if rdata.get("already_checked_in"):
            return "alreadyComplete", "今日已签到", identity
        message = rdata.get("message")
        if isinstance(message, str) and message.strip():
            detail = "签到成功（{}）".format(redact_text(message.strip(), [password, token])[:80])
        else:
            detail = "签到成功"
        return "success", detail, identity
    raise SafeError("晚晚舟签到失败：{}".format(redact_text(extract_message(result), [])))


def run_activity_flow(http, account, jwt, user_id):
    hint = account["site_hint"]
    if hint == "xingya":
        return checkin_xingya(http, account["url"], jwt, user_id)
    if hint == "activity_center":
        return checkin_activity_center(http, account["url"], jwt, user_id)
    if is_activity_center_site(http, account["url"], jwt, user_id):
        return checkin_activity_center(http, account["url"], jwt, user_id)
    state, detail = checkin_xingya(http, account["url"], jwt, user_id)
    return state, detail


class AccountRunner:
    def __init__(self, number):
        self.number = number
        self.started = time.monotonic()
        self.stats = dict.fromkeys(STATES, 0)
        self.status = "failure"
        self.identity = ""

    def stage(self, number, name, operation):
        started = time.monotonic()
        log("账号 {} · 阶段 {} {}：开始".format(self.number, number, name))
        state, detail = "failure", "操作未完成"
        try:
            state, detail, result = operation()
            return result
        except SafeError as error:
            detail = str(error)
            raise
        except Exception:
            detail = "内部处理失败，已抑制异常详情"
            raise SafeError(detail) from None
        finally:
            self.stats[state] += 1
            log(
                "账号 {} · 阶段 {} {}：{} {}（{:.2f}秒）".format(
                    self.number,
                    number,
                    name,
                    ICONS.get(state, ICONS["failure"]),
                    detail,
                    time.monotonic() - started,
                )
            )

    def skip(self, number, name, reason):
        self.stage(number, name, lambda: ("skipped", reason, None))

    def finish(self):
        label = self.identity or "账号{}".format(self.number)
        log(
            "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒；状态 {}".format(
                self.number,
                label,
                sum(self.stats.values()),
                self.stats["success"],
                self.stats["alreadyComplete"],
                self.stats["skipped"],
                self.stats["failure"],
                time.monotonic() - self.started,
                self.status,
            )
        )


def run_account(runner, account, http, dry_run):
    secrets = [account["password"], account["username"]]

    def parameter_check():
        normalize_base_url(account["url"])
        if account["site_hint"] not in SITE_HINTS:
            raise SafeError("site_hint 无效")
        return "success", "凭据与站点本地格式检查通过，内容不输出", None

    runner.stage(1, "参数检查", parameter_check)
    if dry_run:
        for number, name in (
            (2, "账号密码登录"),
            (3, "公开身份提取"),
            (4, "识别站点并签到"),
        ):
            runner.skip(number, name, "断网预演：不请求登录或签到接口")
        runner.status = "dry-run"
        log("账号 {}：断网预演通过；未验证真实身份、凭据或业务结果".format(runner.number))
        return

    if account["site_hint"] == "wanwanzhou":
        def wanwanzhou():
            state, detail, identity = checkin_wanwanzhou(
                http, account["url"], account["username"], account["password"]
            )
            return state, detail, identity

        runner.skip(2, "账号密码登录", "晚晚舟流程内嵌登录，随后统一提取公开身份")
        identity = runner.stage(3, "识别站点并签到", wanwanzhou)
        if identity:
            runner.identity = identity
            runner.stage(
                4,
                "公开身份提取",
                lambda: ("success", "公开账号身份：" + identity, None),
            )
        else:
            runner.skip(4, "公开身份提取", "登录响应未提供可显示公开身份，使用账号序号")
        runner.status = (
            "alreadyComplete" if runner.stats["alreadyComplete"] else "success"
        )
        return

    def login():
        token, user = jwt_login(http, account["url"], account["username"], account["password"])
        secrets.append(token)
        identity = identity_from_user(user, secrets)
        return "success", "JWT 登录成功", (token, user, identity)

    token, user, identity = runner.stage(2, "账号密码登录", login)
    secrets.append(token)
    if identity:
        runner.identity = identity
        runner.stage(
            3,
            "公开身份提取",
            lambda: ("success", "公开账号身份：" + identity, None),
        )
    else:
        runner.skip(3, "公开身份提取", "登录响应未提供可显示公开身份，使用账号序号")

    user_id = account["user_id"] or (str(user.get("id")) if isinstance(user.get("id"), (int, str)) else None)

    def checkin():
        state, detail = run_activity_flow(http, account, token, user_id)
        return state, detail, None

    runner.stage(4, "识别站点并签到", checkin)
    runner.status = "alreadyComplete" if runner.stats["alreadyComplete"] else "success"


PY_NOTIFY_RUNNER = r'''
import importlib, importlib.util, json, os, socket, subprocess, sys
specification = json.loads(sys.stdin.read())
if specification["dry_run"]:
    def denied(*args, **kwargs):
        raise RuntimeError("dry-run forbids network and external processes")
    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied
        sendmsg = denied
    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
    os.system = denied
    os.popen = denied
    for name in dir(os):
        if name.startswith(("exec", "spawn")) or name in ("fork", "forkpty", "posix_spawn", "posix_spawnp"):
            setattr(os, name, denied)
sys.path.insert(0, specification["directory"])
module = None
if specification["path"] is None:
    try:
        module = importlib.import_module("notify")
    except ModuleNotFoundError as error:
        sys.exit(3 if error.name == "notify" else 1)
else:
    spec = importlib.util.spec_from_file_location("qinglong_notify_adapter", specification["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
sender = getattr(module, "send", None)
if not callable(sender):
    sys.exit(3)
result = sender(specification["title"], specification["body"])
sys.exit(1 if result is False else 0)
'''

JS_NOTIFY_RUNNER = r'''
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (input.dry_run) {
  const denied = () => { throw new Error('dry-run forbids network and external processes'); };
  require('net').Socket.prototype.connect = denied;
  require('dgram').createSocket = denied;
  for (const name of ['http', 'https']) {
    require(name).request = denied;
    require(name).get = denied;
  }
  require('tls').connect = denied;
  require('http2').connect = denied;
  const dns = require('dns');
  for (const key of Object.keys(dns)) if (typeof dns[key] === 'function') dns[key] = denied;
  for (const key of Object.keys(dns.promises)) if (typeof dns.promises[key] === 'function') dns.promises[key] = denied;
  const cp = require('child_process');
  for (const key of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) cp[key] = denied;
  require('worker_threads').Worker = denied;
  globalThis.fetch = denied;
}
Promise.resolve().then(() => require(input.path).sendNotify(input.title, input.body))
  .then(result => process.exit(result === false ? 1 : 0))
  .catch(() => process.exit(1));
'''


def notification_enabled():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "").strip())
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "activity_checkin.py",
        "candidate.py",
        "scripts/activity_checkin.py",
    }
    for root in (Path("/ql/data/scripts"), Path("/ql/scripts")):
        try:
            identities.add(script.relative_to(root).as_posix())
        except ValueError:
            pass
    enabled = any(
        selector
        and any(fnmatch.fnmatchcase(identity, selector) for identity in identities)
        for selector in selectors
    )
    return enabled, "已匹配通知选择列表" if enabled else "默认仅通知名单内脚本，本任务未被选择"


def notify(body, dry_run):
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    specification = {
        "title": TITLE,
        "body": body,
        "dry_run": dry_run,
        "directory": str(Path(__file__).resolve().parent),
        "path": None,
    }
    paths = []
    directory = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if directory:
        paths.append(Path(directory).expanduser())
    paths.extend((Path("/ql/data/scripts"), Path("/ql/scripts")))
    adapters = [("python", None)]
    adapters.extend(
        ("python", directory / "notify.py")
        for directory in paths
        if (directory / "notify.py").is_file()
    )
    node = shutil.which("node")
    if node:
        adapters.extend(
            ("javascript", directory / "sendNotify.js")
            for directory in paths
            if (directory / "sendNotify.js").is_file()
        )
    for kind, path in adapters:
        specification["path"] = str(path.resolve()) if path is not None else None
        command = (
            [sys.executable, "-c", PY_NOTIFY_RUNNER]
            if kind == "python"
            else [node, "-e", JS_NOTIFY_RUNNER]
        )
        try:
            result = subprocess.run(
                command,
                input=json.dumps(specification, ensure_ascii=False),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                log(
                    "通知：✅ 脱敏总结已交给青龙适配器"
                    + ("（断网保护启用）" if dry_run else "")
                )
                return "sent"
        except Exception:
            pass
    log("通知：⚠️ 青龙适配器不可用、投递失败或被断网保护阻止；保留业务退出码")
    return "unavailable-or-failed"


def main():
    started = time.monotonic()
    started_at = clock()
    dry_setting = os.environ.get("ACTIVITY_CHECKIN_DRY_RUN", "0").strip().lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts = []
    parsed = []
    config_error = None
    log("========== {} ==========".format(TITLE))
    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES:
            raise SafeError("ACTIVITY_CHECKIN_DRY_RUN 配置无效，停止执行")
        timeout = parse_timeout()
        parsed = load_accounts()
        http = HttpClient(timeout=timeout, dry_run=dry_run)
    except SafeError as error:
        config_error = str(error)
        log("开始时间：{}；运行模式：{}；账号数：0".format(
            started_at, "断网预演" if dry_run else "真实执行"
        ))
        log("阶段 0 参数配置：❌ " + config_error)
    else:
        log(
            "开始时间：{}；运行模式：{}；账号数：{}".format(
                started_at, "断网预演" if dry_run else "真实执行", len(parsed)
            )
        )
        for number, account in enumerate(parsed, 1):
            runner = AccountRunner(number)
            accounts.append(runner)
            try:
                run_account(runner, account, http, dry_run)
            except SafeError:
                runner.status = "failure"
            except Exception:
                runner.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                runner.finish()
            if not dry_run and number != len(parsed):
                time.sleep(1)

    counts = {
        state: sum(item.status == state for item in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
    }
    account_total = len(parsed) if not config_error else 0
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    if config_error and not parsed:
        # 配置阶段失败时仍按「至少一次失败」闭合退出。
        failed = max(failed, 1)
    exit_code = 1 if config_error or failed else 0
    status = (
        "configuration-error"
        if config_error
        else "partial-failure"
        if failed and (succeeded or counts["dry-run"])
        else "failure"
        if failed
        else "dry-run"
        if dry_run
        else "success"
    )
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
    body = "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
        status,
        account_total if not config_error else 0,
        succeeded,
        failed,
        counts["dry-run"],
        "是" if config_error else "否",
    )
    log("阶段 5 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 5 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total if not config_error else 0,
            succeeded,
            counts["alreadyComplete"],
            failed,
            counts["dry-run"],
        )
    )
    log(
        "子任务统计：总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}".format(
            sum(tasks.values()),
            tasks["success"],
            tasks["alreadyComplete"],
            tasks["skipped"],
            tasks["failure"],
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；通知状态 {}；最终状态 {}".format(
            finished_at, elapsed, notification, status
        )
    )
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "catalogId": CATALOG_ID,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total if not config_error else 0,
                "success": succeeded,
                "alreadyComplete": counts["alreadyComplete"],
                "failure": failed,
                "dryRun": counts["dry-run"],
                "configurationError": bool(config_error),
                "tasks": tasks,
                "notification": notification,
                "startTime": started_at,
                "finishTime": finished_at,
                "durationSeconds": elapsed,
                "exitCode": exit_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
