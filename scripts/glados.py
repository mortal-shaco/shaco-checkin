#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: GLaDOS每日签到
# cron: 58 0 * * *
# SPDX-License-Identifier: Apache-2.0

"""
File: checkin.py(GLaDOS签到)
Author: Hennessey
cron: 58 0 * * *
new Env('GLaDOS每日签到');
Update: 2023/7/27

维护说明：本文件在保留原作者署名、签到和状态查询能力的基础上，增加了
多账号、超时、业务成功校验、完全断网预演、脱敏日志和青龙通知集成。
同产品参考：jiang7f/checkin-glados，checkin.py，MIT；原来源未附额外版权声明。
本维护文件适用 Apache-2.0，保留上方原作者署名。

参数获取：在对应 GLaDOS 网站登录，在开发者工具「网络」中查看自己
/api/user/status 或 /api/user/checkin 请求的 Cookie 请求头，完整复制到
GR_COOKIE；每个非空行一个账号，不用 & 或 @ 分隔，也无需账号库或浏览器程序。
兼容 GLADOS_COOKIE；或成对的 GLADOS_GLD_SESS/GLADOS_GLD_SESS_SIG、
GLADOS_KOA_SESS/GLADOS_KOA_SESS_SIG（同一账号值来自同一个 Cookie）。
默认保留 glados.rocks、token=glados.one、每日 00:40、15 秒超时及两个阶段。
GLADOS_SITE=cloud 显式改用参考来源的 glados.cloud、token=glados.cloud；
不会自动跨域切换或传递 Cookie。GLADOS_POINTS=1 增加积分和连续天数查询，
cloud 模式默认开启，rocks 模式默认关闭；GLADOS_POINTS=0 可关闭新增查询。
GLADOS_RETRIES=0..5 为可选签到重试次数，默认 0，不重试登录失效或拒绝访问。
GLADOS_USER_AGENT 可覆盖浏览器标识；CHECKIN_PROXY_URL 可配置 HTTP(S) 代理。
GLADOS_DRY_RUN=1 完全断网，仅检查配置并生成摘要，不执行通知或签到。
QINGLONG_NOTIFY=off 关闭通知；其余通知选择和发现规则见导入契约。
可选 FEISHU_WEBHOOK 与 FEISHU_SECRET 启用飞书签名通知，遵守相同通知开关。
不会自动登录、读取浏览器凭据、创建账号文件、迁移或删除本地数据。
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
        _ql_notify_identities = ('2d633fe3129937b6', 'scripts/glados.py', 'glados.py', 'glados')
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
import fnmatch
import math
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CATALOG_ID = "2d633fe3129937b6"
TASK_NAME = "GLaDOS每日签到"
CHECKIN_TOKEN = "glados.one"
POINTS_URL = "https://glados.rocks/api/user/points"
POINTS_ENABLED = False
RETRIES = 0
PROXY_URL = ""
SECRETS: List[str] = []
CHECKIN_URL = "https://glados.rocks/api/user/checkin"
STATUS_URL = "https://glados.rocks/api/user/status"
REFERER = "https://glados.rocks/console/checkin"
ORIGIN = "https://glados.rocks"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
MAX_RESPONSE_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def parse_timeout() -> float:
    raw = os.getenv("GLADOS_TIMEOUT", "15").strip()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("GLADOS_TIMEOUT 必须是数字秒数")
    if not math.isfinite(value) or value < 1 or value > 60:
        raise ValueError("GLADOS_TIMEOUT 必须在 1 到 60 秒之间")
    return value


def configure() -> None:
    global CHECKIN_URL, STATUS_URL, POINTS_URL, REFERER, ORIGIN
    global CHECKIN_TOKEN, USER_AGENT, POINTS_ENABLED, RETRIES, PROXY_URL
    site = os.getenv("GLADOS_SITE", "rocks").strip().lower()
    if site not in ("rocks", "cloud"):
        raise ValueError("GLADOS_SITE 只能是 rocks 或 cloud")
    ORIGIN = "https://glados." + site
    CHECKIN_URL = ORIGIN + "/api/user/checkin"
    STATUS_URL = ORIGIN + "/api/user/status"
    POINTS_URL = ORIGIN + "/api/user/points"
    REFERER = ORIGIN + "/console/checkin"
    CHECKIN_TOKEN = "glados.cloud" if site == "cloud" else "glados.one"
    points = os.getenv("GLADOS_POINTS", "1" if site == "cloud" else "0").strip().lower()
    if points not in TRUE_VALUES | FALSE_VALUES:
        raise ValueError("GLADOS_POINTS 必须是开关值 1 或 0")
    POINTS_ENABLED = points in TRUE_VALUES
    try:
        RETRIES = int(os.getenv("GLADOS_RETRIES", "0"))
    except ValueError:
        raise ValueError("GLADOS_RETRIES 必须是 0 到 5 的整数") from None
    if not 0 <= RETRIES <= 5:
        raise ValueError("GLADOS_RETRIES 必须是 0 到 5 的整数")
    USER_AGENT = os.getenv("GLADOS_USER_AGENT", "").strip() or USER_AGENT
    if any(ord(c) < 32 or ord(c) == 127 for c in USER_AGENT):
        raise ValueError("GLADOS_USER_AGENT 不能包含控制字符")
    PROXY_URL = os.getenv("CHECKIN_PROXY_URL", "").strip()
    if PROXY_URL:
        try:
            proxy = urllib.parse.urlsplit(PROXY_URL)
            if proxy.scheme not in ("http", "https") or not proxy.hostname or not proxy.port:
                raise ValueError
        except ValueError:
            raise ValueError("CHECKIN_PROXY_URL 必须是带端口的 HTTP(S) 代理地址") from None
    for name in ("FEISHU_WEBHOOK", "FEISHU_SECRET", "CHECKIN_PROXY_URL"):
        value = os.getenv(name, "").strip()
        if value:
            SECRETS.append(value)


def credential_lines(name: str) -> List[str]:
    return [line.strip() for line in os.getenv(name, "").splitlines() if line.strip()]


def load_accounts() -> List[str]:
    """每行一个完整 Cookie；Cookie 内的 &、@、=、; 均不会分割账号。"""
    accounts = credential_lines("GR_COOKIE") or credential_lines("GLADOS_COOKIE")
    if not accounts:
        for prefix, cookie_name in (("GLADOS_GLD", "gld:sess"), ("GLADOS_KOA", "koa:sess")):
            sessions = credential_lines(prefix + "_SESS")
            signatures = credential_lines(prefix + "_SESS_SIG")
            if sessions or signatures:
                if not sessions or len(sessions) != len(signatures):
                    raise ValueError(prefix + "_SESS 与 " + prefix + "_SESS_SIG 必须逐行配对；建议合并为 GR_COOKIE")
                accounts = [cookie_name + "=" + value + "; " + cookie_name + ".sig=" + signature
                            for value, signature in zip(sessions, signatures)]
                break
    if not accounts:
        raise ValueError("未配置 GR_COOKIE；请按每行一个完整 Cookie 填写；兼容 GLADOS_COOKIE 或成对会话变量")
    for cookie in accounts:
        SECRETS.append(cookie)
        for item in cookie.split(";"):
            key, delimiter, value = item.strip().partition("=")
            if delimiter and value:
                SECRETS.append(value)
    return accounts


def validate_cookie(cookie: str) -> None:
    if any(ord(c) < 32 or ord(c) == 127 for c in cookie):
        raise ValueError("Cookie 含控制字符，请重新复制完整请求头")
    if not any(key.strip() and value.strip() for key, sep, value in
               (item.partition("=") for item in cookie.split(";")) if sep):
        raise ValueError("Cookie 格式无效，需要非空的名称=值")


def safe_business_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已隐藏]")
    text = re.sub(r"(?i)(cookie|token|session|authorization|signature|device[_-]?id)\s*[:=]\s*[^\s,;]+", "[敏感字段已隐藏]", text)
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
    return text[:limit] if text else "未提供业务消息"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("接口重定向已阻止，未转发凭据")


def request_json(
    method: str,
    url: str,
    cookie: str,
    timeout: float,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {
        "Referer": REFERER,
        "Origin": ORIGIN,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        # 禁止重定向，避免将 Cookie 或 webhook 签名转发给其他地址。
        handlers = [NoRedirect()]
        if PROXY_URL:
            handlers.append(urllib.request.ProxyHandler({"http": PROXY_URL, "https": PROXY_URL}))
        with urllib.request.build_opener(*handlers).open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("接口返回 HTTP {}".format(exc.code))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        reason_name = type(reason).__name__ if reason is not None else "网络错误"
        raise RuntimeError("网络请求失败（{}）".format(reason_name))
    except TimeoutError:
        raise RuntimeError("网络请求超时")

    if status < 200 or status >= 300:
        raise RuntimeError("接口返回 HTTP {}".format(status))
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("接口响应超过 1 MiB 安全上限")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("接口未返回有效 JSON")
    if not isinstance(result, dict):
        raise RuntimeError("接口 JSON 顶层结构无效")
    return result


def classify_checkin(response: Dict[str, Any]) -> Tuple[str, str]:
    code = response.get("code")
    # 仅使用原文判定业务，不将服务器消息或错误原文写入日志。
    message = str(response.get("message") or response.get("msg") or response.get("error") or "")
    if type(code) in (int, str) and code in (0, "0"):
        return "success", "签到成功"
    already_markers = (
        "checkin repeats", "check-in repeats", "already check", "already signed",
        "try tomorrow", "已签到", "重复签到", "明天再来", "today's observation logged",
    )
    if type(code) in (int, str) and code in (1, "1") and any(marker in message.casefold() for marker in already_markers):
        return "already", "今日已签到"
    if code in (-2, "-2", 401, "401"):
        raise RuntimeError("登录已过期，请在相应网站重新获取 Cookie")
    if code in (403, "403"):
        raise RuntimeError("访问被拒绝，请检查登录状态与网络")
    if code in (4, "4") and response.get("reason") == "device-mismatch":
        raise RuntimeError("登录设备不匹配，请在原浏览器重新获取 Cookie")
    raise RuntimeError("签到业务失败，未取得成功或今日已完成凭证")


def numeric(value: Any, label: str) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not math.isfinite(number):
            raise ValueError
        return int(number)
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError(label + "字段不是有效数字") from None


def parse_status(response: Dict[str, Any]) -> Tuple[str, str]:
    code = response.get("code")
    # 兼容旧规范来源无 code 的状态结构，但显式失败码不能当成成功。
    if code is not None and not (type(code) in (int, str) and code in (0, "0")):
        raise RuntimeError("状态查询业务失败，请检查登录状态")
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("状态响应缺少 data")
    identity = (data.get("nickname") or data.get("displayName") or data.get("username")
                or data.get("name") or data.get("email") or data.get("uid"))
    if type(identity) not in (str, int) or not str(identity).strip():
        raise RuntimeError("状态响应缺少账号身份")
    identity = str(identity)
    # 正常官方公开身份原样输出；疑似凭据、手机号或控制字符不进入日志。
    if any(ord(c) < 32 or ord(c) == 127 for c in identity) or safe_business_text(identity, len(identity)) != identity:
        raise RuntimeError("账号身份含敏感内容或控制字符，已禁止输出")
    if data.get("leftDays") is None:
        raise RuntimeError("状态响应缺少剩余天数")
    return identity, str(numeric(data["leftDays"], "剩余天数"))


def parse_points(response: Dict[str, Any]) -> Dict[str, int]:
    if not (type(response.get("code")) in (int, str) and response.get("code") in (0, "0")):
        raise RuntimeError("积分查询业务失败")
    points = response.get("points")
    history = response.get("history")
    if points is None and isinstance(history, list) and history and isinstance(history[0], dict):
        points = history[0].get("balance")
    values = {}
    for key, value, label in (("points", points, "积分"), ("streak", response.get("streak"), "连续天数")):
        if value is not None:
            values[key] = numeric(value, label)
    if not values:
        raise RuntimeError("积分响应缺少积分与连续天数字段")
    return values


def perform_checkin(cookie: str, timeout: float) -> Tuple[str, str, Dict[str, Any]]:
    for attempt in range(RETRIES + 1):
        try:
            response = request_json("POST", CHECKIN_URL, cookie, timeout, {"token": CHECKIN_TOKEN})
            outcome, message = classify_checkin(response)
            return outcome, message, response
        except Exception as exc:
            message = safe_business_text(exc)
            if attempt == RETRIES or any(marker in message for marker in ("登录", "拒绝", "设备", "HTTP 401", "HTTP 403", "重定向")):
                raise
            log("签到重试 {}/{}：{}".format(attempt + 1, RETRIES, message))
            time.sleep(min(attempt + 1, 3))
    raise RuntimeError("签到未取得结果")


def run_account(index: int, cookie: str, timeout: float, dry_run: bool) -> Dict[str, Any]:
    started = time.monotonic()
    total = 3 if POINTS_ENABLED else 2
    stats = {"total": total, "success": 0, "already": 0, "skipped": 0, "failed": 0}
    label = "账号{}".format(index)
    errors: List[str] = []
    metrics: Dict[str, int] = {}
    checkin_metrics: Dict[str, int] = {}
    print("\n========== {} ==========".format(label), flush=True)
    try:
        validate_cookie(cookie)
        cookie_valid = True
    except ValueError as exc:
        cookie_valid = False
        log("[{}] ❌ {}".format(label, safe_business_text(exc)))
    stages = ["签到请求", "账号状态查询"]
    if POINTS_ENABLED:
        stages.append("积分与连续签到天数查询")
    for stage, name in enumerate(stages, 1):
        stage_started = time.monotonic()
        prefix = "[账号{}][{}/{}]".format(index, stage, total)
        log("{} {}开始".format(prefix, name))
        try:
            if not cookie_valid:
                raise RuntimeError("账号 Cookie 配置无效，未发起请求")
            if dry_run:
                stats["skipped"] += 1
                log("{} ⏭️ 断网预演：已校验{}配置，未发起网络请求（{:.2f}秒）".format(prefix, name, time.monotonic() - stage_started))
                continue
            outcome = "success"
            if stage == 1:
                outcome, message, response = perform_checkin(cookie, timeout)
                for key in ("points", "streak"):
                    if response.get(key) is not None:
                        try:
                            checkin_metrics[key] = numeric(response[key], key)
                        except RuntimeError:
                            pass
            elif stage == 2:
                identity, left_days = parse_status(request_json("GET", STATUS_URL, cookie, timeout))
                label = identity
                message = "身份：{}；剩余天数：{}".format(identity, left_days)
            else:
                metrics = parse_points(request_json("GET", POINTS_URL, cookie, timeout))
                metrics = dict(checkin_metrics, **metrics)
                message = "；".join(("积分" if key == "points" else "连续天数") + "：" + str(value) for key, value in metrics.items())
            stats["already" if outcome == "already" else "success"] += 1
            log("{} {} {}（{:.2f}秒）".format(prefix, "☑️" if outcome == "already" else "✅", message, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            # 所有内部异常仅打印已知错误，未知异常不输出原文。
            message = safe_business_text(exc) if isinstance(exc, (RuntimeError, ValueError)) else "处理失败（{}）".format(type(exc).__name__)
            errors.append(message)
            log("{} ❌ {}（{:.2f}秒）".format(prefix, message, time.monotonic() - stage_started))
            if stage == 3 and checkin_metrics:
                metrics = checkin_metrics
                log("{} 签到响应补充统计：{}".format(prefix, json.dumps(metrics, ensure_ascii=False)))
    elapsed = time.monotonic() - started
    ok = stats["failed"] == 0
    log("[账号{}] 结果={}；总任务={}，成功={}，已完成={}，跳过={}，失败={}，耗时={:.2f}秒".format(
        index, "DRY_RUN" if dry_run and ok else ("SUCCESS" if ok else "FAILED"),
        stats["total"], stats["success"], stats["already"], stats["skipped"], stats["failed"], elapsed))
    return {"index": index, "identity": label, "ok": ok, "stats": stats,
            "elapsed": elapsed, "errors": errors, "metrics": metrics}


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {CATALOG_ID, Path(__file__).name, "candidate.py", "checkin.py", "glados.py", "scripts/glados.py", script_path}
    for selector in selectors:
        if selector == "*":
            return True
        if any(fnmatch.fnmatch(name, selector) for name in names):
            return True
    return False


def notification_enabled() -> bool:
    value = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if value in FALSE_VALUES:
        return False
    if value not in TRUE_VALUES and value != "auto":
        log("⚠️ QINGLONG_NOTIFY 值无效，按 auto 处理")
    return notification_selected()


def python_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "notify.py")
    paths.extend([Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")])
    return paths


def js_notifier_paths() -> List[Path]:
    paths: List[Path] = []
    notify_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if notify_dir:
        paths.append(Path(notify_dir) / "sendNotify.js")
    paths.extend([Path("/ql/data/scripts/sendNotify.js"), Path("/ql/scripts/sendNotify.js")])
    return paths


def send_notification(title: str, body: str, dry_run: bool) -> str:
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    python_runner = (
        "import importlib,importlib.util,json,sys;"
        "sys.path.insert(0,sys.argv[2]);"
        "p=sys.argv[1];"
        "s=importlib.util.spec_from_file_location('qinglong_notify',p) if p else None;"
        "m=importlib.util.module_from_spec(s) if s else importlib.import_module('notify');"
        "s.loader.exec_module(m) if s else None;"
        "a=json.load(sys.stdin);m.send(a['title'],a['body'])"
    )
    paths = [None] + [path for path in python_notifier_paths() if path.is_file()]
    for path in paths:
        try:
            completed = subprocess.run(
                [sys.executable, "-c", python_runner, str(path) if path else "", str(Path(__file__).resolve().parent)],
                input=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30, check=False,
            )
            if completed.returncode == 0:
                log("通知状态：{} 已调用".format("notify.py" if path else "notify.send"))
                return "sent"
        except Exception:
            continue

    node = shutil.which("node")
    if node:
        js_runner = (
            "const n=require(process.argv[1]);"
            "Promise.resolve(n.sendNotify(process.argv[2],process.argv[3]))"
            ".then(()=>process.exit(0)).catch(()=>process.exit(1));"
        )
        for path in js_notifier_paths():
            if not path.is_file():
                continue
            try:
                result = subprocess.run(
                    [node, "-e", js_runner, str(path), title, body],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知状态：sendNotify.js 已调用")
                    return "sent"
            except Exception:
                continue

    log("⚠️ 通知状态：未找到可用通知器或通知发送失败，不改变业务退出码")
    return "unavailable"


def notify_summary(title: str, body: str, dry_run: bool) -> str:
    state = send_notification(title, body, dry_run)
    if dry_run or not notification_enabled() or not os.getenv("FEISHU_WEBHOOK", "").strip():
        return state
    try:
        webhook = os.environ["FEISHU_WEBHOOK"].strip()
        url = urllib.parse.urlsplit(webhook)
        if (url.scheme != "https" or url.hostname not in ("open.feishu.cn", "open.larksuite.com")
                or not url.path.startswith("/open-apis/bot/v2/hook/") or url.username or url.password
                or url.port not in (None, 443) or url.query or url.fragment):
            raise RuntimeError("飞书 webhook 必须是官方 HTTPS 自定义机器人地址")
        payload = {"msg_type": "text", "content": {"text": title + "\n" + body}}
        secret = os.getenv("FEISHU_SECRET", "").strip()
        if secret:
            timestamp = str(int(time.time()))
            key = (timestamp + "\n" + secret).encode("utf-8")
            payload.update(timestamp=timestamp, sign=base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode("ascii"))
        response = request_json("POST", webhook, "", 15, payload)
        keys = [key for key in ("StatusCode", "code", "errcode") if key in response]
        if not keys or any(type(response[key]) is not int or response[key] != 0 for key in keys):
            raise RuntimeError("飞书未返回业务成功状态")
        log("通知状态：飞书已发送")
        return state + "+feishu-sent"
    except Exception:
        log("⚠️ 飞书通知失败，不改变业务退出码")
        return state + "+feishu-failed"


def print_summary(summary: Dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("GLADOS_DRY_RUN")
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        configure()
        timeout = parse_timeout()
        accounts = load_accounts()
    except ValueError as exc:
        log("账号数量：0")
        log("[0/0] ❌ 配置错误：{}".format(safe_business_text(exc)))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误"
        notify_state = notify_summary(TASK_NAME, body, dry_run)
        finished_at = now_text()
        print("-" * 56)
        print("账号结果：总数 0，成功 0，失败 1")
        print("子任务结果：总数 0，成功 0，已完成 0，跳过 0，失败 0")
        print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
        print("完成时间：{}".format(finished_at))
        print("通知状态：{}".format(notify_state))
        print("最终状态：CONFIG_ERROR")
        print_summary({
            "status": "configuration-error",
            "mode": "dry-run" if dry_run else "live",
            "accounts": {"total": 0, "success": 0, "failed": 1},
            "tasks": {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failed": 0},
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        })
        return 2

    log("账号数量：{}".format(len(accounts)))
    results = [run_account(i, cookie, timeout, dry_run) for i, cookie in enumerate(accounts, 1)]
    account_success = sum(1 for item in results if item["ok"])
    account_failed = len(results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in results)
        for key in ("total", "success", "already", "skipped", "failed")
    }
    if dry_run and account_failed == 0:
        status = "dry-run"
        exit_code = 0
    elif account_failed == 0:
        status = "success"
        exit_code = 0
    elif account_success:
        status = "partial-failure"
        exit_code = 1
    else:
        status = "failure"
        exit_code = 1

    body = "账号总数：{}；成功：{}；失败：{}；状态：{}".format(
        len(results), account_success, account_failed, status
    )
    notify_state = notify_summary(TASK_NAME, body, dry_run)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    print("\n" + "-" * 56)
    print("账号结果：总数 {}，成功 {}，失败 {}".format(len(results), account_success, account_failed))
    print(
        "子任务结果：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}".format(
            **task_stats
        )
    )
    print("总耗时：{:.2f}秒".format(elapsed))
    print("完成时间：{}".format(finished_at))
    print("通知状态：{}".format(notify_state))
    print("最终状态：{}".format(status.upper()))
    print_summary({
        "status": status,
        "mode": "dry-run" if dry_run else "live",
        "accounts": {"total": len(results), "success": account_success, "failed": account_failed},
        "tasks": {
            "total": task_stats["total"],
            "success": task_stats["success"],
            "alreadyComplete": task_stats["already"],
            "skipped": task_stats["skipped"],
            "failed": task_stats["failed"],
        },
        "notification": notify_state,
        "elapsedSeconds": round(elapsed, 3),
        "startedAt": started_at,
        "finishedAt": finished_at,
    })
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
