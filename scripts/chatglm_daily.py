#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 智谱清言每日签到
# cron: 13 1 * * *
# SPDX-License-Identifier: MIT

"""
智谱清言每日签到 - 青龙维护版

基于 L0NE-6/ChatGLM-Daily（MIT）维护，保留原作者全部用户可见能力：
每日登录积分、积分活动与季节活动领取、每日任务中心、新手任务中心、
积分余额与任务进度回读、refresh_token 续期与本地状态记忆。

维护改动：改用 Python 标准库实现带超时与响应大小限制的独立 HTTP 请求；
账号统一为每行一个（备注|access_token|refresh_token|device_id），不再使用
& 分隔账号；新增完全断网预演（CHATGLM_DRY_RUN）、脱敏时间轴日志、
单行 TASK_SUMMARY 汇总与青龙通知策略（notify.py / sendNotify.js）。
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
        _ql_notify_identities = ('75a199c398e3576c', 'scripts/chatglm_daily.py', 'chatglm_daily.py', 'chatglm_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "75a199c398e3576c"
TASK_NAME = "智谱清言每日签到"
BASE_URL_DEFAULT = "https://chatglm.cn"
SIGN_SECRET_PROD = "8a1317a7468aa3ad86e997d08f3f31cb"
SIGN_SECRET_TEST = "befbc3fe57555ffa1daaf52b39be0fbe"
APP_VERSION = "2.0.7"
APP_PLATFORM = "pc"
APP_NAME = "chatglm"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 1024 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

PATH_REFRESH = "/chatglm/user-api/user/refresh"
PATH_MEMBER_INFO = "/chatglm/member-api/member/member_info"
PATH_SCORE_ACTIVITY_DRAW = "/chatglm/member-api/member/score_activity_draw"
PATH_DAILY_LOGIN_SCORE = "/chatglm/member-api/member/daily_login_score"
PATH_SUMMER_DAY_CLAIM_STATUS = "/chatglm/member-api/member/summer_day_claim_status"
PATH_SUMMER_DAY_GIVE_SCORE = "/chatglm/member-api/member/summer_day_give_score"
PATH_TASK_CENTER = "/chatglm/agent-api/task/center"
PATH_TASK_CLICK = "/chatglm/agent-api/task/click"
PATH_TASK_COMPLETE = "/chatglm/agent-api/task/complete"

BEIJING = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def now_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(clock(), message), flush=True)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def parse_timeout() -> float:
    raw = os.getenv("CHATGLM_TIMEOUT", "30").strip()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("CHATGLM_TIMEOUT 必须是数字秒数")
    if value < 1 or value > 60:
        raise ValueError("CHATGLM_TIMEOUT 必须在 1 到 60 秒之间")
    return value


def safe_business_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] if text else "未提供业务消息"


def strip_bearer(token: Any) -> str:
    text = str(token or "").strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text


def decode_jwt_claims(token: str) -> Dict[str, Any]:
    raw = strip_bearer(token)
    parts = raw.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1].replace("-", "+").replace("_", "/")
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        value = json.loads(base64.b64decode(payload).decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def claim_text(claims: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        value = claims.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def save_json(path: str, value: Any) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def state_file() -> str:
    return os.getenv("CHATGLM_STATE_FILE", "").strip() or os.path.join(
        SCRIPT_DIR, "chatglm_state.json"
    )


def load_state() -> Dict[str, Any]:
    value = load_json(state_file(), {})
    if not isinstance(value, dict):
        value = {}
    value.setdefault("accounts", {})
    value.setdefault("onboarding", {})
    return value


def x_timestamp(millis: Optional[int] = None) -> str:
    text = str(int(millis if millis is not None else time.time() * 1000))
    if len(text) < 2:
        return text
    digits = [int(ch) for ch in text]
    checksum = (sum(digits) - digits[-2]) % 10
    return text[:-2] + str(checksum) + text[-1]


def sign_secret(base_url: str) -> str:
    lowered = base_url.lower()
    if "test.chatglm.cn" in lowered or "staging" in lowered or "dev" in lowered:
        return SIGN_SECRET_TEST
    if "chatglm.cn" in lowered:
        return SIGN_SECRET_PROD
    return SIGN_SECRET_TEST


def build_headers(base_url: str, token: str, device_id: str) -> Dict[str, str]:
    timestamp = x_timestamp()
    nonce = uuid.uuid4().hex
    sign = hashlib.md5(
        ("%s-%s-%s" % (timestamp, nonce, sign_secret(base_url))).encode("utf-8")
    ).hexdigest()
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "App-Name": APP_NAME,
        "X-Device-Id": device_id,
        "X-App-Platform": APP_PLATFORM,
        "X-App-Version": APP_VERSION,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Sign": sign,
        "Origin": base_url,
        "Referer": base_url + "/",
        "User-Agent": USER_AGENT,
    }
    cleaned = strip_bearer(token)
    if cleaned:
        headers["Authorization"] = "Bearer " + cleaned
    return headers


def build_opener(proxy: str) -> urllib.request.OpenerDirector:
    handlers: List[Any] = []
    if proxy:
        lowered = proxy.lower()
        if lowered.startswith("socks"):
            raise ValueError(
                "CHATGLM_PROXY 当前仅支持 http(s) 代理；socks 代理请改用标准库兼容的 http 隧道"
            )
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def request_json(
    method: str,
    path: str,
    base_url: str,
    token: str,
    device_id: str,
    timeout: float,
    opener: urllib.request.OpenerDirector,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = base_url + path
    headers = build_headers(base_url, token, device_id)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    elif method == "POST":
        data = b"{}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            payload_bytes = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read(MAX_RESPONSE_BYTES + 1).decode("utf-8"))
        except Exception:
            payload = {"status": -1, "message": "HTTP %s" % exc.code}
        if not isinstance(payload, dict):
            payload = {"status": -1, "message": "HTTP %s" % exc.code}
        return exc.code, payload
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        raise RuntimeError("网络请求失败（{}）".format(type(reason).__name__))
    except TimeoutError:
        raise RuntimeError("网络请求超时")
    if len(payload_bytes) > MAX_RESPONSE_BYTES:
        raise RuntimeError("接口响应超过 1 MiB 安全上限")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("接口未返回有效 JSON")
    if not isinstance(payload, dict):
        raise RuntimeError("接口 JSON 顶层结构无效")
    return status, payload


class ChatGLMError(Exception):
    pass


def envelope(payload: Dict[str, Any], what: str) -> Any:
    status = payload.get("status")
    if status is None:
        return payload.get("result")
    try:
        status = int(status)
    except Exception:
        status = -1
    if status in (0, 200):
        return payload.get("result")
    message = str(payload.get("message") or payload.get("msg") or "上游返回失败")
    raise ChatGLMError("{}失败（status={}）：{}".format(what, status, message))


class ChatGLMClient:
    def __init__(self, account: Dict[str, Any], state: Dict[str, Any], timeout: float):
        self.name = account.get("name") or "账号"
        self.key = account.get("_key") or self.name
        self.state = state
        saved = (state.get("accounts") or {}).get(self.key, {})
        self.base_url = os.getenv("CHATGLM_BASE_URL", "").strip().rstrip("/") or BASE_URL_DEFAULT
        proxy = os.getenv("CHATGLM_PROXY", "").strip()
        self.opener = build_opener(proxy)
        self.access_token = strip_bearer(
            saved.get("access_token") or account.get("access_token")
        )
        self.refresh_token = strip_bearer(
            saved.get("refresh_token") or account.get("refresh_token")
        )
        claims = decode_jwt_claims(self.access_token)
        self.uid = claim_text(claims, ("uid", "user_id", "sub"))
        self.is_guest = bool(claims.get("is_guest"))
        self.device_id = (
            str(saved.get("device_id") or account.get("device_id") or "").strip()
            or claim_text(claims, ("device_id",))
            or str(uuid.uuid4())
        )
        self.timeout = timeout

    def save_tokens(self) -> None:
        self.state.setdefault("accounts", {})[self.key] = {
            "name": self.name,
            "uid": self.uid,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "device_id": self.device_id,
            "updated_at": int(time.time()),
        }
        try:
            save_json(state_file(), self.state)
        except Exception as exc:
            log("令牌状态保存失败：{}".format(exc))

    def refresh(self) -> None:
        if not self.refresh_token:
            raise ChatGLMError("登录态已失效，且没有 refresh_token")
        status, payload = request_json(
            "POST",
            PATH_REFRESH,
            self.base_url,
            self.refresh_token,
            self.device_id,
            self.timeout,
            self.opener,
            {},
        )
        if status in (401, 403):
            raise ChatGLMError("refresh_token 已失效，请重新登录")
        result = envelope(payload, "令牌续期") or {}
        access = strip_bearer(result.get("access_token"))
        if not access:
            raise ChatGLMError("令牌续期未返回 access_token")
        self.access_token = access
        rotated = strip_bearer(result.get("refresh_token"))
        if rotated:
            self.refresh_token = rotated
        uid = str(result.get("user_id") or "").strip()
        if uid:
            self.uid = uid
        claims = decode_jwt_claims(self.access_token)
        self.is_guest = bool(claims.get("is_guest"))
        claim_device = claim_text(claims, ("device_id",))
        if claim_device:
            self.device_id = claim_device
        self.save_tokens()

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, what: str = "上游请求") -> Dict[str, Any]:
        if not self.access_token and self.refresh_token:
            self.refresh()
        if not self.access_token:
            raise ChatGLMError("缺少 access_token")

        status, payload = request_json(
            method, path, self.base_url, self.access_token, self.device_id,
            self.timeout, self.opener, body,
        )
        payload_status = payload.get("status")
        needs_refresh = status in (401, 403) or str(payload_status) == "40103"
        if needs_refresh and self.refresh_token:
            self.refresh()
            status, payload = request_json(
                method, path, self.base_url, self.access_token, self.device_id,
                self.timeout, self.opener, body,
            )
        if status in (401, 403):
            raise ChatGLMError("{}登录态已失效（HTTP {}）".format(what, status))
        if status < 200 or status >= 300:
            message = payload.get("message") or payload.get("msg") or payload
            raise ChatGLMError("{}失败（HTTP {}）：{}".format(what, status, message))
        return payload

    def get(self, path: str, what: str = "查询") -> Dict[str, Any]:
        return self.request("GET", path, what=what)

    def post(self, path: str, body: Optional[Dict[str, Any]] = None, what: str = "提交") -> Dict[str, Any]:
        return self.request("POST", path, body=body or {}, what=what)

    def task_center(self) -> Dict[str, Any]:
        return envelope(self.get(PATH_TASK_CENTER, "任务中心查询"), "任务中心查询") or {}

    def query_balance(self) -> Tuple[Optional[float], Dict[str, Any]]:
        member = envelope(self.get(PATH_MEMBER_INFO, "积分查询"), "积分查询") or {}
        raw = member.get("left_score", member.get("true_left_score", 0))
        try:
            balance = round(float(raw) / 100.0, 2)
        except Exception:
            balance = None
        return balance, member

    def claim_login(self) -> Tuple[bool, str]:
        try:
            payload = self.post(PATH_DAILY_LOGIN_SCORE, {}, "每日登录积分领取")
        except ChatGLMError as exc:
            message = str(exc)
            if any(word in message for word in ("10001", "已领", "already")):
                return True, "今日登录积分已领取"
            raise
        status = payload.get("status")
        if str(status) == "10001":
            return True, "今日登录积分已领取"
        result = envelope(payload, "每日登录积分领取") or {}
        if isinstance(result, dict):
            raw = result.get("score", 0)
        elif isinstance(result, (int, float)):
            raw = result
        else:
            raw = 0
        try:
            score = round(float(raw) / 100.0, 2)
        except Exception:
            score = 0.0
        if score > 0:
            return True, "每日登录积分 +{}".format(score)
        return True, "今日登录积分已领取或活动未开启"

    def claim_bonus(self) -> Tuple[bool, str]:
        messages: List[str] = []
        gained = 0.0
        try:
            payload = self.post(PATH_SCORE_ACTIVITY_DRAW, {}, "积分活动领取")
            status = payload.get("status")
            if str(status) == "0":
                result = envelope(payload, "积分活动领取") or {}
                raw = result.get("score", result.get("reward", 0)) if isinstance(result, dict) else 0
                try:
                    amount = round(float(raw) / 100.0, 2)
                except Exception:
                    amount = 0.0
                if amount > 0:
                    gained += amount
                    messages.append("积分活动 +{}".format(amount))
                else:
                    messages.append("积分活动无可领取")
            else:
                messages.append("积分活动：{}".format(str(payload.get("message") or "活动未开启")[:80]))
        except ChatGLMError as exc:
            messages.append("积分活动：{}".format(str(exc)[:80]))

        try:
            state_payload = self.get(PATH_SUMMER_DAY_CLAIM_STATUS, "季节活动状态查询")
            state = envelope(state_payload, "季节活动状态查询") or {}
            claimable = state.get("claimable")
            if claimable is None and "claimed" in state:
                claimable = not bool(state.get("claimed"))
            if claimable:
                claimed = self.post(PATH_SUMMER_DAY_GIVE_SCORE, {}, "季节活动领取")
                envelope(claimed, "季节活动领取")
                messages.append("季节活动已领取")
            else:
                messages.append("季节活动无可领取")
        except ChatGLMError as exc:
            messages.append("季节活动：{}".format(str(exc)[:80]))

        if not messages:
            messages.append("当前没有可领取的活动")
        return gained > 0, "；".join(messages)

    @staticmethod
    def category(center: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
        categories = center.get("categories")
        if not isinstance(categories, list):
            return None
        for item in categories:
            if isinstance(item, dict) and item.get("code") == code:
                return item
        return None

    def settle_tasks(self, category: Optional[Dict[str, Any]], label: str) -> Tuple[int, int, str]:
        tasks = category.get("tasks") if isinstance(category, dict) else []
        if not isinstance(tasks, list) or not tasks:
            return 0, 0, "{}：没有任务".format(label)

        claimed = 0
        points = 0
        failures: List[str] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            try:
                status = int(task.get("status") or 0)
            except Exception:
                status = 0
            if status >= 3:
                continue
            task_id = str(task.get("task_id") or "").strip()
            title = str(task.get("title") or task_id or "未命名任务")
            if not task_id:
                failures.append("{}缺少 task_id".format(title))
                continue
            try:
                self.post(PATH_TASK_CLICK, {"task_id": task_id}, "任务登记")
                payload = self.post(PATH_TASK_COMPLETE, {"task_id": task_id}, "任务结算")
                result = envelope(payload, "任务结算") or {}
                reward = 0
                if isinstance(result, dict):
                    reward = int(((result.get("reward") or {}).get("points_awarded") or 0))
                claimed += 1
                points += reward
            except ChatGLMError as exc:
                if "登录态已失效" in str(exc):
                    raise
                failures.append("{}：{}".format(title, str(exc)[:80]))
        if failures:
            message = "{}：完成 {} 个，+{} 积分；失败 {}".format(
                label, claimed, points, "；".join(failures[:3])
            )
        else:
            message = "{}：完成 {} 个，+{} 积分".format(label, claimed, points)
        return claimed, points, message

    def query_snapshot(self) -> str:
        balance, _member = self.query_balance()
        center = self.task_center()
        daily = self.category(center, "daily") or {}
        newbie = self.category(center, "newbie") or {}
        return (
            "余额 {} | 每日任务 {}/{} | 新手任务 {}/{}".format(
                balance if balance is not None else "?",
                (daily.get("progress") or {}).get("done", "?"),
                (daily.get("progress") or {}).get("total", "?"),
                (newbie.get("progress") or {}).get("done", "?"),
                (newbie.get("progress") or {}).get("total", "?"),
            )
        )


def notification_selected() -> bool:
    if "QINGLONG_NOTIFY_SCRIPTS" not in os.environ:
        return True
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS", "")
    if not raw.strip():
        return False
    selectors = [part for part in re.split(r"[,;\s]+", raw.strip()) if part]
    script_path = str(Path(__file__).as_posix())
    names = {CATALOG_ID, Path(__file__).name, "candidate.py", "chatglm_daily.py", script_path}
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
    if os.getenv("CHATGLM_NO_NOTIFY", "").strip() == "1":
        log("通知状态：已按 CHATGLM_NO_NOTIFY 关闭")
        return "disabled"
    if not notification_enabled():
        log("通知状态：已按 QINGLONG_NOTIFY 或脚本选择规则关闭")
        return "disabled"
    if dry_run:
        log("通知状态：断网预演中仅生成脱敏通知摘要，不调用通知网络")
        return "dry-run"

    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            log("通知状态：notify.send 已调用")
            return "sent"
    except Exception:
        pass

    for path in python_notifier_paths():
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_notify", str(path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                log("通知状态：notify.py 已调用")
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


def print_summary(summary: Dict[str, Any]) -> None:
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)


def load_accounts() -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    raw = os.getenv("CHATGLM_ACCOUNTS", "").strip()
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|", 3)]
            name = parts[0] or "账号{}".format(len(accounts) + 1)
            access = strip_bearer(parts[1]) if len(parts) > 1 else ""
            refresh = strip_bearer(parts[2]) if len(parts) > 2 else ""
            device = parts[3] if len(parts) > 3 else ""
            if not access and not refresh:
                log("⚠️ 配置：跳过格式不正确的账号条目")
                continue
            accounts.append({
                "name": name,
                "access_token": access,
                "refresh_token": refresh,
                "device_id": device,
            })
    if not accounts:
        token = strip_bearer(os.getenv("CHATGLM_TOKEN", ""))
        refresh = strip_bearer(os.getenv("CHATGLM_REFRESH_TOKEN", ""))
        device = os.getenv("CHATGLM_DEVICE_ID", "").strip()
        if token or refresh:
            accounts.append({
                "name": "账号1",
                "access_token": token,
                "refresh_token": refresh,
                "device_id": device,
            })
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for account in accounts:
        claims = decode_jwt_claims(account.get("access_token") or account.get("refresh_token"))
        uid = claim_text(claims, ("uid", "user_id", "sub"))
        key = uid or account.get("name")
        if key in seen:
            key = "{}-{}".format(key, len(deduped) + 1)
        seen.add(key)
        account["_key"] = key
        deduped.append(account)
    return deduped


def parse_args() -> Tuple[str, bool, bool, bool]:
    only = ""
    query_only = False
    skip_newbie = False
    no_notify = os.getenv("CHATGLM_NO_NOTIFY", "").strip() == "1"
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        if arg == "--only" and index + 1 < len(args):
            only = args[index + 1]
        elif arg == "--query":
            query_only = True
        elif arg == "--skip-newbie":
            skip_newbie = True
        elif arg == "--no-notify":
            no_notify = True
    return only, query_only, skip_newbie, no_notify


def run_account(client: ChatGLMClient, query_only: bool, skip_newbie: bool, dry_run: bool) -> Tuple[bool, Dict[str, Any]]:
    stats = {"total": 5, "success": 0, "skipped": 0, "failed": 0}
    errors: List[str] = []
    label = "账号{}".format(client.name)
    if client.uid:
        label = "账号{}（uid {}）".format(client.name, client.uid)
    started = time.monotonic()

    if client.is_guest:
        log("[{}] ⏭️ 访客账号没有积分体系，跳过".format(label))
        stats["skipped"] += 5
        return True, {"label": label, "ok": True, "stats": stats, "errors": errors, "elapsed": time.monotonic() - started, "messages": ["访客账号没有积分体系，跳过"]}

    if query_only and not dry_run:
        stage_started = time.monotonic()
        log("[{}][1/1] 余额与任务进度回读开始".format(label))
        try:
            snapshot = client.query_snapshot()
            stats["success"] += 1
            log("[{}][1/1] ✅ {}（{:.2f}秒）".format(label, snapshot, time.monotonic() - stage_started))
            return True, {"label": label, "ok": True, "stats": stats, "errors": errors, "elapsed": time.monotonic() - started, "messages": [snapshot]}
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            log("[{}][1/1] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))
            return False, {"label": label, "ok": False, "stats": stats, "errors": errors, "elapsed": time.monotonic() - started, "messages": []}

    messages: List[str] = []
    # 每日登录积分
    stage_started = time.monotonic()
    log("[{}][1/5] 每日登录积分领取开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][1/5] ⏭️ 断网预演：已校验签到请求配置，未发起网络请求（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    else:
        try:
            ok, message = client.claim_login()
            stats["success"] += 1
            messages.append(message)
            log("[{}][1/5] {} {}（{:.2f}秒）".format(label, "✅" if ok else "☑️", message, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            messages.append("每日登录积分领取失败")
            log("[{}][1/5] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))

    # 积分活动与季节活动
    stage_started = time.monotonic()
    log("[{}][2/5] 积分活动与季节活动领取开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][2/5] ⏭️ 断网预演：已校验活动领取请求配置，未发起网络请求（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    else:
        try:
            _ok, message = client.claim_bonus()
            stats["success"] += 1
            messages.append(message)
            log("[{}][2/5] ✅ {}（{:.2f}秒）".format(label, message, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            messages.append("积分活动领取失败")
            log("[{}][2/5] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))

    # 每日任务中心
    stage_started = time.monotonic()
    log("[{}][3/5] 每日任务中心结算开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][3/5] ⏭️ 断网预演：已校验任务中心请求配置，未发起网络请求（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    else:
        try:
            center = client.task_center()
            daily = client.category(center, "daily")
            if daily:
                _c, _p, message = client.settle_tasks(daily, "每日任务")
                messages.append(message)
                stats["success"] += 1
                log("[{}][3/5] ✅ {}（{:.2f}秒）".format(label, message, time.monotonic() - stage_started))
            else:
                messages.append("每日任务：当前没有任务")
                stats["success"] += 1
                log("[{}][3/5] ☑️ 每日任务：当前没有任务（{:.2f}秒）".format(label, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            messages.append("每日任务结算失败")
            log("[{}][3/5] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))

    # 新手任务中心
    stage_started = time.monotonic()
    log("[{}][4/5] 新手任务中心结算开始".format(label))
    if skip_newbie:
        stats["skipped"] += 1
        log("[{}][4/5] ⏭️ 已按 --skip-newbie 跳过（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    elif dry_run:
        stats["skipped"] += 1
        log("[{}][4/5] ⏭️ 断网预演：已校验新手任务请求配置，未发起网络请求（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    else:
        try:
            onboarding = client.state.setdefault("onboarding", {})
            if not onboarding.get(client.key):
                center = client.task_center()
                newbie = client.category(center, "newbie")
                if newbie:
                    _c, _p, message = client.settle_tasks(newbie, "新手任务")
                    messages.append(message)
                    refresh = client.task_center()
                    after = client.category(refresh, "newbie") or {}
                    progress = after.get("progress") or {}
                    try:
                        done = int(progress.get("done") or 0)
                        total = int(progress.get("total") or 0)
                    except Exception:
                        done, total = 0, 0
                    if total > 0 and done >= total:
                        onboarding[client.key] = {"settled_at": int(time.time())}
                        save_json(state_file(), client.state)
                    stats["success"] += 1
                    log("[{}][4/5] ✅ {}（{:.2f}秒）".format(label, message, time.monotonic() - stage_started))
                else:
                    messages.append("新手任务：当前没有任务")
                    stats["success"] += 1
                    log("[{}][4/5] ☑️ 新手任务：当前没有任务（{:.2f}秒）".format(label, time.monotonic() - stage_started))
            else:
                messages.append("新手任务：此前已完成")
                stats["success"] += 1
                log("[{}][4/5] ☑️ 新手任务：此前已完成（{:.2f}秒）".format(label, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            messages.append("新手任务结算失败")
            log("[{}][4/5] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))

    # 余额回读
    stage_started = time.monotonic()
    log("[{}][5/5] 积分余额回读开始".format(label))
    if dry_run:
        stats["skipped"] += 1
        log("[{}][5/5] ⏭️ 断网预演：已校验余额回读请求配置，未发起网络请求（{:.2f}秒）".format(label, time.monotonic() - stage_started))
    else:
        try:
            balance, _member = client.query_balance()
            if balance is not None:
                message = "当前积分 {}".format(balance)
            else:
                message = "当前积分：接口未返回有效余额"
            messages.append(message)
            stats["success"] += 1
            log("[{}][5/5] ✅ {}（{:.2f}秒）".format(label, message, time.monotonic() - stage_started))
        except Exception as exc:
            stats["failed"] += 1
            errors.append(str(exc))
            messages.append("余额回读失败")
            log("[{}][5/5] ❌ {}（{:.2f}秒）".format(label, safe_business_text(exc), time.monotonic() - stage_started))

    elapsed = time.monotonic() - started
    ok = dry_run or stats["failed"] == 0
    log(
        "[{}] 结果={}；总任务={}，成功={}，跳过={}，失败={}，耗时={:.2f}秒".format(
            label,
            "DRY_RUN" if dry_run else ("SUCCESS" if ok else "FAILED"),
            stats["total"],
            stats["success"],
            stats["skipped"],
            stats["failed"],
            elapsed,
        )
    )
    return ok, {"label": label, "ok": ok, "stats": stats, "errors": errors, "elapsed": elapsed, "messages": messages}


def main() -> int:
    overall_started = time.monotonic()
    started_at = now_text()
    dry_run = truthy("CHATGLM_DRY_RUN")
    only, query_only, skip_newbie, no_notify = parse_args()
    print("=" * 56)
    print("{} | 独立维护版".format(TASK_NAME))
    print("开始时间：{}".format(started_at))
    print("运行模式：{}".format("DRY_RUN（完全断网）" if dry_run else "LIVE"))
    print("=" * 56, flush=True)

    try:
        timeout = parse_timeout()
        accounts = load_accounts()
        if not accounts:
            raise ValueError("未配置 CHATGLM_ACCOUNTS 或 CHATGLM_TOKEN")
    except ValueError as exc:
        log("❌ 配置错误：{}".format(exc))
        body = "账号总数：0；成功：0；失败：1；状态：配置错误"
        notify_state = send_notification(TASK_NAME, body, dry_run)
        finished_at = now_text()
        print("-" * 56)
        print("账号结果：总数 0，成功 0，失败 1")
        print("子任务结果：总数 0，成功 0，跳过 0，失败 0")
        print("总耗时：{:.2f}秒".format(time.monotonic() - overall_started))
        print("完成时间：{}".format(finished_at))
        print("通知状态：{}".format(notify_state))
        print("最终状态：CONFIG_ERROR")
        print_summary({
            "status": "configuration-error",
            "mode": "dry-run" if dry_run else "live",
            "accounts": {"total": 0, "success": 0, "failed": 1},
            "tasks": {"total": 0, "success": 0, "skipped": 0, "failed": 0},
            "notification": notify_state,
            "startedAt": started_at,
            "finishedAt": finished_at,
        })
        return 2

    state = load_state()
    selected = 0
    account_results = []
    for index, account in enumerate(accounts, 1):
        if only and str(index) != str(only):
            continue
        selected += 1
        client = ChatGLMClient(account, state, timeout)
        try:
            ok, result = run_account(client, query_only=query_only, skip_newbie=skip_newbie, dry_run=dry_run)
            account_results.append(result)
        except Exception as exc:
            log("[账号{}] ❌ 初始化失败：{}".format(account.get("name") or index, safe_business_text(exc)))
            account_results.append({
                "label": "账号{}".format(account.get("name") or index),
                "ok": False,
                "stats": {"total": 5, "success": 0, "skipped": 0, "failed": 5},
                "errors": [str(exc)],
                "elapsed": 0.0,
                "messages": [],
            })
        if index < len(accounts):
            time.sleep(1.0)

    if selected == 0:
        log("❌ 没有匹配的账号")
        return 1

    account_success = sum(1 for item in account_results if item["ok"])
    account_failed = len(account_results) - account_success
    task_stats = {
        key: sum(item["stats"][key] for item in account_results)
        for key in ("total", "success", "skipped", "failed")
    }
    if dry_run:
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
        len(account_results), account_success, account_failed, status
    )
    notify_state = "disabled" if no_notify else send_notification(TASK_NAME, body, dry_run)
    finished_at = now_text()
    elapsed = time.monotonic() - overall_started
    print("\n" + "-" * 56)
    print("账号结果：总数 {}，成功 {}，失败 {}".format(len(account_results), account_success, account_failed))
    print(
        "子任务结果：总数 {total}，成功 {success}，跳过 {skipped}，失败 {failed}".format(
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
        "accounts": {"total": len(account_results), "success": account_success, "failed": account_failed},
        "tasks": {
            "total": task_stats["total"],
            "success": task_stats["success"],
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
