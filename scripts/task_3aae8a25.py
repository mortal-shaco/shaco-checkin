#!/usr/bin/env python3
# coding: utf-8
# name: 雨云签到与安全续费
# cron: 40 0 * * *
# 上游: LMTXQ/Rainyun-QingLong main.py
# 上游提交: c589e71cebb4c15fc6b0e3087a2bff4aaf032be1
# 原项目基于 SerendipityR-2022/Rainyun-Qiandao 与 fatekey/Rainyun-Qiandao
# 兼容来源: cloudcranes/some_scripts rainyun.py 与 FalseHappiness/RainyunCheckIn app.py
"""雨云每日签到与可选服务器积分续费。

使用 RAINYUN_ACCOUNT（兼容旧变量 rainyun_ck），每个非空行代表一个账号。推荐每行填写一个
JSON 对象：{"username":"用户名","password":"密码","autoRenew":false,
"apiKey":"可选 API Key"}。仅签到时也兼容“用户名#密码”，只在第一个 #
处分隔，密码内后续的 # 会保留；还兼容上游的 JSON 二维数组。

autoRenew 默认关闭。只有同一账号行明确设置为 true 且提供 apiKey 时，才会按
RAINYUN_CONFIG 的到期阈值、续费天数和最低积分保留值执行续费。
RAINYUN_DRY_RUN=1 启用完全断网预演；QINGLONG_NOTIFY=0 可关闭通知。

MIT License

Copyright (c) LMTXQ/Rainyun-QingLong contributors
Copyright (c) SerendipityR-2022/Rainyun-Qiandao contributors
Copyright (c) fatekey/Rainyun-Qiandao contributors
Copyright (c) cloudcranes/some_scripts contributors
Copyright (c) FalseHappiness/RainyunCheckIn contributors

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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('3aae8a254cd15cdd', 'scripts/task_3aae8a25.py', 'task_3aae8a25.py', 'task_3aae8a25', '89f2e9b460331a75', 'scripts/rainyun.py', 'rainyun.py', 'rainyun')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import http.cookiejar
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime


TITLE = "雨云签到与安全续费"
CATALOG_ID = "3aae8a254cd15cdd"
APPLICATION_KEY = "lmtxq/rainyun-qinglong::main"
BASE_URL = "https://api.v2.rainyun.com"
ORIGIN = "https://api.rainyun.com"
MAX_RESPONSE_BYTES = 256 * 1024
DEFAULT_TIMEOUT = 20
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class TaskError(Exception):
    """可以安全展示且不含响应正文、URL 参数或凭据的错误。"""


@dataclass(frozen=True)
class Account:
    username: str
    password: str
    auto_renew: bool = False
    api_key: str = ""
    position: int = 0


@dataclass(frozen=True)
class Settings:
    timeout: int = DEFAULT_TIMEOUT
    renew_days: int = 7
    renew_threshold_days: int = 3
    min_points_reserve: int = 5000


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def env_enabled(name, default="0"):
    value = os.environ.get(name, default).strip().lower()
    return value in TRUE_VALUES


def parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in FALSE_VALUES | {""}:
            return False
    return default


def bounded_int(value, name, minimum, maximum):
    if isinstance(value, bool):
        raise TaskError(f"RAINYUN_CONFIG 的 {name} 必须是整数")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise TaskError(f"RAINYUN_CONFIG 的 {name} 必须是整数") from None
    if not minimum <= number <= maximum:
        raise TaskError(
            f"RAINYUN_CONFIG 的 {name} 必须在 {minimum} 到 {maximum} 之间"
        )
    return number


def load_settings():
    raw = os.environ.get("RAINYUN_CONFIG", "").strip()
    if not raw:
        return Settings()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise TaskError("RAINYUN_CONFIG 必须是有效 JSON 对象") from None
    if not isinstance(data, dict):
        raise TaskError("RAINYUN_CONFIG 必须是 JSON 对象")

    # 仅接受原上游中与独立 HTTP 版本相关且不会改变请求目的地的安全配置。
    return Settings(
        timeout=bounded_int(
            data.get("api_request_timeout", data.get("timeout", DEFAULT_TIMEOUT)),
            "api_request_timeout",
            5,
            60,
        ),
        renew_days=bounded_int(data.get("renew_days", 7), "renew_days", 1, 365),
        renew_threshold_days=bounded_int(
            data.get("renew_threshold_days", 3),
            "renew_threshold_days",
            0,
            365,
        ),
        min_points_reserve=bounded_int(
            data.get("min_points_reserve", 5000),
            "min_points_reserve",
            0,
            1000000000,
        ),
    )


def account_from_sequence(item, position=0):
    if not isinstance(item, list) or len(item) < 2:
        raise TaskError("旧版账号项必须至少包含用户名和密码")
    username = item[0]
    password = item[1]
    auto_renew = parse_bool(item[2]) if len(item) >= 3 else False
    api_key = item[3] if len(item) >= 4 else ""
    return make_account(username, password, auto_renew, api_key, position)


def account_from_mapping(item, position=0):
    username = item.get("username", item.get("user", ""))
    password = item.get("password", item.get("passwd", ""))
    auto_renew = parse_bool(item.get("autoRenew", item.get("auto_renew", False)))
    api_key = item.get("apiKey", item.get("api_key", ""))
    return make_account(username, password, auto_renew, api_key, position)


def make_account(username, password, auto_renew=False, api_key="", position=0):
    if not isinstance(username, str) or not isinstance(password, str):
        raise TaskError("用户名和密码必须是字符串")
    if not isinstance(api_key, str):
        raise TaskError("API Key 必须是字符串")
    username = username.strip()
    api_key = api_key.strip()
    if not username or not password:
        raise TaskError("用户名和密码不能为空")
    if auto_renew and not api_key:
        raise TaskError("启用自动续费时，同一账号行必须提供 apiKey")
    return Account(username, password, bool(auto_renew), api_key, position)


def parse_accounts():
    raw = account_input()
    if not raw.strip():
        return [], ["缺少账号配置 RAINYUN_ACCOUNT 或 rainyun_ck"]

    accounts = []
    errors = []
    stripped = raw.strip()

    # 兼容上游的完整 JSON 二维数组；新配置仍推荐一行一个 JSON 对象。
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise TaskError("旧版 RAINYUN_ACCOUNT 必须是 JSON 数组")
            for index, item in enumerate(parsed, 1):
                try:
                    if isinstance(item, dict):
                        accounts.append(account_from_mapping(item, index))
                    else:
                        accounts.append(account_from_sequence(item, index))
                except TaskError as exc:
                    errors.append(f"账号 {index}：{exc}")
            return accounts, errors
        except (ValueError, UnicodeError):
            return [], ["RAINYUN_ACCOUNT 的旧版 JSON 数组格式无效"]

    for index, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            if line.lstrip().startswith("{"):
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise TaskError("每行 JSON 必须是对象")
                accounts.append(account_from_mapping(item, index))
            else:
                username, delimiter, password = line.partition("#")
                if not delimiter:
                    raise TaskError("简写格式必须为 用户名#密码")
                accounts.append(make_account(username, password, position=index))
        except (ValueError, UnicodeError):
            errors.append(f"账号 {index}：JSON 格式无效")
        except TaskError as exc:
            errors.append(f"账号 {index}：{exc}")
    return accounts, errors


def account_input():
    """Prefer the maintained setting, while keeping the old rainyun_ck task usable."""
    return os.environ.get("RAINYUN_ACCOUNT", "") or os.environ.get("rainyun_ck", "")


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    """拒绝把 Cookie、密码或 API Key 转发到重定向目的地。"""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class RainyunHTTP:
    """单账号独立 Cookie 会话；仅连接固定的雨云 HTTPS API。"""

    def __init__(self, account, timeout):
        self.account = account
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            RejectRedirect(), urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(self, path, payload=None, api_key=False):
        if not path.startswith("/"):
            raise TaskError("内部接口路径无效")
        url = BASE_URL + path
        headers = {
            "Accept": "application/json",
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/",
            "User-Agent": "Mozilla/5.0 Qinglong-Rainyun-Maintained/1.0",
        }
        if api_key:
            headers["x-api-key"] = self.account.api_key
        else:
            for cookie in self.cookies:
                if cookie.name.lower() == "x-csrf-token":
                    headers["X-CSRF-Token"] = cookie.value
                    break

        body = None
        method = "GET"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        request = urllib.request.Request(
            url, data=body, headers=headers, method=method
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.geturl() != url:
                    raise TaskError("接口重定向，已拒绝转发凭据")
                if response.status != 200:
                    raise TaskError(f"HTTP 状态异常：{response.status}")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                raise TaskError("接口重定向，已拒绝转发凭据") from None
            raise TaskError(f"HTTP 错误：{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError("网络连接失败或请求超时") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TaskError("接口响应超过安全大小限制")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError("接口响应不是有效 JSON") from None
        if not isinstance(result, dict):
            raise TaskError("接口响应结构无效")
        code = result.get("code")
        if isinstance(code, bool) or code not in (200, "200"):
            raise TaskError("接口业务码未确认成功")
        return result

    def login(self):
        return self.request(
            "/user/login",
            {"field": self.account.username.lower(), "password": self.account.password},
        )

    def signin(self):
        return self.request(
            "/user/reward/tasks", {"task_name": "每日签到", "verifyCode": ""}
        )

    def query_user(self):
        result = self.request("/user/")
        data = result.get("data")
        if not isinstance(data, dict):
            raise TaskError("用户信息结构无效")
        points = first_value(data, "points", "Points")
        if not valid_number(points):
            raise TaskError("积分字段缺失或格式无效")
        return result, points

    def logout(self):
        return self.request("/user/logout", {})

    def api_request(self, path, payload=None):
        return self.request(path, payload, api_key=True)


def first_value(mapping, *names):
    if not isinstance(mapping, dict):
        return None
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def public_identity(result, password):
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, dict):
        return None
    for key in (
        "nickname",
        "Nickname",
        "username",
        "Username",
        "display_name",
        "displayName",
        "uid",
        "UID",
    ):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            continue
        value = str(value).strip()
        if not value or (password and password in value):
            continue
        if re.fullmatch(r"1[3-9]\d{9}", value):
            continue
        return value
    return None


def parse_expiry(value):
    if isinstance(value, bool):
        raise TaskError("服务器到期时间格式无效")
    if isinstance(value, (int, float)) and math.isfinite(value):
        timestamp = value / 1000 if value > 10000000000 else value
        try:
            return datetime.fromtimestamp(timestamp)
        except (OSError, OverflowError, ValueError):
            raise TaskError("服务器到期时间格式无效") from None
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo:
                return parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
    raise TaskError("服务器到期时间格式无效")


def run_auto_renew(client, settings):
    user_result = client.api_request("/user/")
    user_data = user_result.get("data")
    points = first_value(user_data, "points", "Points")
    if not valid_number(points):
        raise TaskError("API Key 用户积分字段缺失或格式无效")
    current_points = points

    query = urllib.parse.urlencode({"product_type": "rgs"})
    list_result = client.api_request("/product/id_list?" + query)
    list_data = list_result.get("data")
    server_ids = first_value(list_data, "rgs", "Rgs")
    if not isinstance(server_ids, list):
        raise TaskError("服务器列表结构无效")
    if not server_ids:
        return {"total": 0, "renewed": 0, "skipped": 0, "failed": 0}

    counts = {"total": len(server_ids), "renewed": 0, "skipped": 0, "failed": 0}
    for server_id in server_ids:
        if isinstance(server_id, bool) or not isinstance(server_id, (str, int)):
            counts["failed"] += 1
            continue
        try:
            quoted_id = urllib.parse.quote(str(server_id), safe="")
            detail_result = client.api_request(f"/product/rgs/{quoted_id}/")
            detail = detail_result.get("data")
            if not isinstance(detail, dict):
                raise TaskError("服务器详情结构无效")
            server_data = first_value(detail, "Data", "data")
            prices = first_value(detail, "RenewPointPrice", "renewPointPrice")
            if not isinstance(server_data, dict) or not isinstance(prices, dict):
                raise TaskError("服务器续费信息结构无效")
            expiry = parse_expiry(first_value(server_data, "ExpDate", "expDate"))
            days_left = math.floor((expiry - datetime.now()).total_seconds() / 86400)
            if days_left > settings.renew_threshold_days:
                counts["skipped"] += 1
                continue
            cost = prices.get(str(settings.renew_days))
            if not valid_number(cost) or cost < 0:
                raise TaskError("续费积分价格缺失或格式无效")
            if current_points - cost < settings.min_points_reserve:
                counts["skipped"] += 1
                continue
            client.api_request(
                "/product/point_renew",
                {
                    "duration_day": settings.renew_days,
                    "product_id": server_id,
                    "product_type": "rgs",
                },
            )
            current_points -= cost
            counts["renewed"] += 1
        except TaskError:
            counts["failed"] += 1
    return counts


def notification_selected():
    switch = os.environ.get("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES or switch == "":
        return False, "QINGLONG_NOTIFY 已关闭"
    if switch not in TRUE_VALUES | {"auto"}:
        log("⚠️ QINGLONG_NOTIFY 值无法识别，按 auto 处理")

    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True, "默认通知范围"
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    selectors = [item for item in re.split(r"[,;\s]+", raw) if item]
    if not selectors:
        return False, "QINGLONG_NOTIFY_SCRIPTS 为空"
    candidates = (
        CATALOG_ID,
        "candidate.py",
        "main.py",
        APPLICATION_KEY,
        "89f2e9b460331a75",
        "scripts/rainyun.py",
        "rainyun.py",
        "rainyun",
    )
    for selector in selectors:
        if selector == "*" or any(
            fnmatch.fnmatchcase(candidate, selector) for candidate in candidates
        ):
            return True, f"匹配选择器 {selector}"
    return False, "未被 QINGLONG_NOTIFY_SCRIPTS 选中"


def python_notifiers():
    modules = []
    try:
        modules.append(importlib.import_module("notify"))
    except Exception:
        pass
    paths = []
    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    seen = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            spec = importlib.util.spec_from_file_location(
                f"qinglong_notify_{len(modules)}", resolved
            )
            if spec is None or spec.loader is None:
                raise ImportError
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules.append(module)
        except Exception:
            log("⚠️ Python 通知模块加载失败（详情已脱敏）")
    return modules


def javascript_notifiers():
    paths = []
    notify_dir = os.environ.get("QINGLONG_NOTIFY_DIR")
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend(
        (Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js"))
    )
    result = []
    seen = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in seen and resolved.is_file():
            result.append(resolved)
            seen.add(resolved)
    return result


def notification_body(summary):
    return (
        f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
        f"成功：{summary['success']}；失败：{summary['failed']}；"
        f"配置错误：{summary['configurationErrors']}；"
        f"子任务成功：{summary['steps']['success']}；"
        f"子任务失败：{summary['steps']['failed']}"
    )


def send_notification(summary, dry_run):
    selected, reason = notification_selected()
    if not selected:
        log(f"⏭️ 通知已跳过：{reason}")
        return "disabled"
    if dry_run:
        log("⏭️ 断网预演：已生成脱敏通知摘要，未调用可能联网的通知渠道")
        return "dry-run-skipped"
    body = notification_body(summary)
    for module in python_notifiers():
        sender = getattr(module, "send", None)
        if not callable(sender):
            continue
        try:
            sender(TITLE, body)
            log("✅ Python 通知发送完成")
            return "sent"
        except Exception:
            log("⚠️ Python 通知发送失败（详情已脱敏）")

    node = shutil.which("node")
    if node:
        wrapper = (
            "const m=require(process.argv[1]);"
            "const f=typeof m==='function'?m:(m.sendNotify||m.send);"
            "if(typeof f!=='function')process.exit(2);"
            "Promise.resolve(f(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(3));"
        )
        for path in javascript_notifiers():
            try:
                result = subprocess.run(
                    [node, "-e", wrapper, str(path), TITLE, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("✅ JavaScript 通知发送完成")
                    return "sent"
                log("⚠️ JavaScript 通知发送失败（详情已脱敏）")
            except (OSError, subprocess.SubprocessError):
                log("⚠️ JavaScript 通知执行失败（详情已脱敏）")
    log("⚠️ 通知不可用；业务退出码保持不变")
    return "unavailable"


def empty_stats(total):
    return {
        "total": total,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }


def record_step(stats, account_index, number, total, name, state, detail, started):
    stats[state] += 1
    icon = {
        "success": "✅",
        "alreadyComplete": "☑️",
        "skipped": "⏭️",
        "failed": "❌",
    }[state]
    elapsed = time.monotonic() - started
    log(
        f"{icon} 账号 {account_index} 阶段 {number}/{total} {name}："
        f"{detail}；耗时 {elapsed:.2f} 秒"
    )


def run_account(index, account, settings, dry_run):
    account_started = time.monotonic()
    actions = ["登录", "每日签到", "查询积分"]
    if account.auto_renew:
        actions.append("检查并续费服务器")
    actions.append("退出登录")
    stats = empty_stats(len(actions))
    client = None if dry_run else RainyunHTTP(account, settings.timeout)
    logged_in = False
    workflow_ok = True
    log(f"--- 账号 {index} ---")

    for number, action in enumerate(actions, 1):
        step_started = time.monotonic()
        state = "skipped"
        detail = "前置阶段失败，跳过"
        if dry_run:
            detail = "DRY_RUN_OK：参数与执行计划已验证，未发起网络请求"
        elif action == "登录":
            try:
                result = client.login()
                logged_in = True
                state, detail = "success", "业务码确认成功"
                identity = public_identity(result, account.password)
                if identity:
                    log(f"账号 {index} 官方身份：{identity}")
            except TaskError as exc:
                state, detail = "failed", str(exc)
                workflow_ok = False
        elif action == "退出登录":
            if not logged_in:
                detail = "未创建登录会话，跳过"
            else:
                try:
                    client.logout()
                    state, detail = "success", "业务码确认成功，登录会话已退出"
                except TaskError as exc:
                    state, detail = "failed", str(exc)
                    workflow_ok = False
        elif not workflow_ok:
            pass
        elif action == "每日签到":
            try:
                result = client.signin()
                message = result.get("message", "")
                already = isinstance(message, str) and any(
                    word in message for word in ("已签到", "已完成", "重复")
                )
                if already:
                    state, detail = "alreadyComplete", "今日任务已完成"
                else:
                    state, detail = "success", "成功签到并领取积分"
            except TaskError as exc:
                state, detail = "failed", str(exc)
                workflow_ok = False
        elif action == "查询积分":
            try:
                result, points = client.query_user()
                state, detail = "success", f"积分查询成功：{points}"
                identity = public_identity(result, account.password)
                if identity:
                    log(f"账号 {index} 官方身份：{identity}")
            except TaskError as exc:
                state, detail = "failed", str(exc)
                workflow_ok = False
        elif action == "检查并续费服务器":
            try:
                counts = run_auto_renew(client, settings)
                if counts["failed"]:
                    state = "failed"
                    workflow_ok = False
                elif counts["renewed"]:
                    state = "success"
                elif counts["total"] == 0:
                    state = "alreadyComplete"
                else:
                    state = "skipped"
                detail = (
                    f"服务器总数 {counts['total']}，已续费 {counts['renewed']}，"
                    f"安全跳过 {counts['skipped']}，失败 {counts['failed']}"
                )
            except TaskError as exc:
                state, detail = "failed", str(exc)
                workflow_ok = False
        record_step(
            stats, index, number, len(actions), action, state, detail, step_started
        )

    ok = stats["failed"] == 0
    status = "dry-run" if dry_run and ok else "success" if ok else "failure"
    result = {
        "account": index,
        "status": status,
        "autoRenew": account.auto_renew,
        "steps": stats,
        "durationSeconds": round(time.monotonic() - account_started, 3),
    }
    log(
        f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}；耗时 {result['durationSeconds']} 秒"
    )
    return result, ok


def main():
    started = time.monotonic()
    dry_run = env_enabled("RAINYUN_DRY_RUN")
    accounts, account_errors = parse_accounts()
    settings_error = None
    try:
        settings = load_settings()
    except TaskError as exc:
        settings = Settings()
        settings_error = str(exc)

    has_account_value = bool(account_input().strip())
    invalid_account_count = len(account_errors) if has_account_value else 0
    configured_account_count = len(accounts) + invalid_account_count
    summary = {
        "task": TITLE,
        "applicationKey": APPLICATION_KEY,
        "mode": "dry-run" if dry_run else "live",
        "startedAt": stamp(),
        "accounts": configured_account_count,
        "success": 0,
        "failed": invalid_account_count,
        "configurationErrors": len(account_errors) + (1 if settings_error else 0),
        "steps": empty_stats(0),
        "accountResults": [],
    }
    log(f"===== {TITLE} =====")
    log(f"开始时间：{summary['startedAt']}")
    log(f"运行模式：{'断网预演' if dry_run else '正式执行'}")
    log(f"账号数量：{configured_account_count}")
    for error in account_errors:
        log(f"❌ 配置错误：{error}")
    if settings_error:
        log(f"❌ 配置错误：{settings_error}")

    if not settings_error:
        for fallback_index, account in enumerate(accounts, 1):
            index = account.position or fallback_index
            result, ok = run_account(index, account, settings, dry_run)
            summary["success" if ok else "failed"] += 1
            summary["accountResults"].append(result)
            for key in summary["steps"]:
                summary["steps"][key] += result["steps"][key]
    elif accounts:
        summary["failed"] += len(accounts)

    failed = bool(summary["failed"] or summary["configurationErrors"])
    if summary["configurationErrors"]:
        summary["status"] = "configuration-error"
    elif failed and summary["success"]:
        summary["status"] = "partial-failure"
    elif failed:
        summary["status"] = "failure"
    elif dry_run:
        summary["status"] = "dry-run"
    else:
        summary["status"] = "success"

    summary["notification"] = send_notification(summary, dry_run)
    summary["finishedAt"] = stamp()
    summary["durationSeconds"] = round(time.monotonic() - started, 3)
    log("----------------------------------------")
    log(
        f"任务统计：账号总数 {summary['accounts']}，成功 {summary['success']}，"
        f"失败 {summary['failed']}，配置错误 {summary['configurationErrors']}；"
        f"子任务 {summary['steps']}"
    )
    log(
        f"完成时间：{summary['finishedAt']}；总耗时 {summary['durationSeconds']} 秒；"
        f"通知：{summary['notification']}；最终状态：{summary['status']}"
    )
    print(
        "TASK_SUMMARY="
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
