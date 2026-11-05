#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Elantran社区签到
# cron: 28 9 * * *
# SPDX-License-Identifier: MIT
"""Elantran 小程序社区签到与互动（青龙维护版）。

Upstream: https://github.com/wangjin0601/ensign
Original path: elantran_checkin.py
Branch: main
Commit: d7b3aac51ec6fd6a15caa38ac8fba6ca3fe37453
License: MIT

Copyright (c) 2025 wongcw / wangjin0601
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

功能清点（相对上游 elantran_checkin.py）：
- 每日签到（查状态 /home/bbs/sign_today_user_status，执行 /home/bbs/sign）
- 查询签到明细明日积分、用户总积分
- 周五：点赞最多 3 个未赞帖子 + 发帖 + 评论
- 周六/周日：发帖 + 评论；周一至周四仅签到
- JWT 解码展示公开昵称（name）与公开 UID（id），不打印 Token
- 多账号：ELANTRAN_AUTH 每行一个 Bearer Token（不再使用 & 分隔）
- 公开发帖/评论文案：优先一言 HTTPS，失败回退本地文案；dry-run 不请求一言
- 移除私有 content_engine / AI 配图依赖与 verify=False；标准库 urllib 实现 HTTP
- 移除默认 0–10 分钟启动抖动、60–600 秒互动间隔与账号间 10 分钟硬等待
- ELANTRAN_DRY_RUN 完全断网预演、时间轴日志、青龙通知、TASK_SUMMARY
- 任一账号失败整体非零退出；不打印 Cookie/Token/原始响应

ELANTRAN_DRY_RUN=1：完全断网预演，不发起任何网络请求。
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
        _ql_notify_selectors = [
            item.lower()
            for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip())
            if item
        ]
        _ql_notify_identities = (
            "734c839033d16d32",
            "scripts/elantran_checkin.py",
            "elantran_checkin.py",
            "candidate.py",
            "output/candidate.py",
            "elantran",
            "Elantran社区签到",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import html
import importlib.util
import json
import os
import random
import re
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

CATALOG_ID = "734c839033d16d32"
SCRIPT_NAME = "Elantran社区签到"
SCRIPT_FILENAME = "candidate.py"
SCRIPT_IDENTITIES = (
    CATALOG_ID,
    SCRIPT_FILENAME,
    "output/candidate.py",
    "elantran_checkin.py",
    "scripts/elantran_checkin.py",
    "elantran",
    SCRIPT_NAME,
)

AUTH_ENV = "ELANTRAN_AUTH"
DRY_RUN_ENV = "ELANTRAN_DRY_RUN"
TIMEOUT_ENV = "ELANTRAN_TIMEOUT"
LOCAL_TEXT_ENV = "ELANTRAN_LOCAL_TEXT"
SKIP_SOCIAL_ENV = "ELANTRAN_SKIP_SOCIAL"
ACTION_DELAY_ENV = "ELANTRAN_ACTION_DELAY_SEC"
ACCOUNT_DELAY_ENV = "ELANTRAN_ACCOUNT_DELAY_SEC"

BASE_URL = "https://elantran.vintro.cn"
API_HOST = "elantran.vintro.cn"
FORUM_ID = "e51bcafdf3f8b55bae08b4bcb816faa9"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
HITOKOTO_HOST = "v1.hitokoto.cn"
HITOKOTO_TIMEOUT = 8
HITOKOTO_MAX_BYTES = 16384
HTTP_TIMEOUT = 30
MAX_RESPONSE_BYTES = 512 * 1024
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Windows WindowsWechat/WMPF"
)

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

STATUS_ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}

LOCAL_FALLBACK_TEXTS = [
    "今天也来社区冒个泡，祝大家开车平安、心情愉快。",
    "路过打个卡，分享一下今日好心情。",
    "支持一下好内容，感谢分享。",
    "周末愉快，记得按时保养爱车。",
    "来签个到，顺便看看大家最近都在聊什么。",
]


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


def _now() -> datetime:
    return datetime.now().astimezone()


def _clock() -> str:
    return _now().strftime("%H:%M:%S")


def _full_ts() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str = "") -> None:
    if msg:
        print(f"[{_clock()}] {msg}", flush=True)
    else:
        print(flush=True)


def env_raw(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def compact(text: str, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)] + "…"


def normalize_public_text(text: Any) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value


def parse_accounts(raw: str) -> List[str]:
    """每个非空行一个 Token；账号之间只用换行分隔。"""
    accounts: List[str] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if any(ord(ch) < 32 for ch in text):
            raise SafeError(f"第 {line_no} 行凭据含非法控制字符")
        accounts.append(text)
    return accounts


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def identity_from_token(token: str) -> Tuple[str, str]:
    data = decode_jwt_payload(token) or {}
    name = str(data.get("name") or "").strip()
    uid = str(data.get("id") or "").strip()
    return name, uid


def check_token_local(token: str) -> Tuple[bool, str, str, str]:
    if not token:
        return False, "未配置认证 Token", "", ""
    data = decode_jwt_payload(token)
    if not data:
        return False, "Token 格式无效", "", ""
    name = str(data.get("name") or "").strip()
    uid = str(data.get("id") or "").strip()
    exp = data.get("exp", 0)
    try:
        exp_num = int(exp)
    except (TypeError, ValueError):
        exp_num = 0
    if exp_num > 0:
        # 上游按毫秒时间戳处理
        exp_sec = exp_num / 1000.0 if exp_num > 10_000_000_000 else float(exp_num)
        if time.time() >= exp_sec:
            return False, "Token 已过期", name, uid
    return True, "Token 结构有效", name, uid


def int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env_raw(name).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError(f"{name} 须为整数") from exc
    if value < minimum or value > maximum:
        raise SafeError(f"{name} 须在 {minimum} 到 {maximum} 之间")
    return value


def http_json(
    url: str,
    *,
    method: str = "POST",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: float = HTTP_TIMEOUT,
    dry_run: bool = False,
    allow_hosts: Tuple[str, ...] = (API_HOST,),
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Dict[str, Any]:
    if dry_run:
        raise SafeError("断网预演禁止 HTTP 请求")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    if host not in allow_hosts:
        raise SafeError("拒绝访问非白名单主机")
    request_headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Host": host,
    }
    if headers:
        request_headers.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            status = int(response.getcode())
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        status = int(error.code)
        try:
            raw = error.read(max_bytes + 1)
        except Exception:
            raw = b""
        finally:
            try:
                error.close()
            except Exception:
                pass
    except Exception:
        raise SafeError("网络请求失败：请求异常") from None
    if len(raw) > max_bytes:
        raise SafeError("响应过大，已中止解析")
    text = raw.decode("utf-8", errors="replace")
    payload: Any = None
    if text.strip():
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
    return {"status": status, "json": payload}


def business_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "msg", "title"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact(value, 120)
    return ""


def format_hitokoto(payload: Any) -> str:
    text = normalize_public_text(payload.get("hitokoto") if isinstance(payload, dict) else "")
    if not text:
        raise SafeError("文案缺失")
    author = normalize_public_text(payload.get("from_who") if isinstance(payload, dict) else "")
    source = normalize_public_text(payload.get("from") if isinstance(payload, dict) else "")
    if author and source:
        text = f"{text} —— {author}《{source}》"
    elif source:
        text = f"{text} ——《{source}》"
    elif author:
        text = f"{text} —— {author}"
    text = normalize_public_text(text)
    if not text:
        raise SafeError("文案缺失")
    if len(text) > 280:
        raise SafeError("署名后的文案过长")
    return text


def local_public_text() -> str:
    override = normalize_public_text(env_raw(LOCAL_TEXT_ENV))
    if override:
        return override[:280]
    return random.choice(LOCAL_FALLBACK_TEXTS)


def fetch_public_text(*, dry_run: bool, timeout: float) -> Tuple[str, str]:
    if dry_run:
        return local_public_text(), "dry-run-local"
    try:
        result = http_json(
            HITOKOTO_URL,
            method="GET",
            body=None,
            timeout=min(timeout, HITOKOTO_TIMEOUT),
            dry_run=False,
            allow_hosts=(HITOKOTO_HOST,),
            max_bytes=HITOKOTO_MAX_BYTES,
        )
        if result["status"] != 200 or not isinstance(result["json"], dict):
            raise SafeError("http-error")
        return format_hitokoto(result["json"]), "一言"
    except SafeError:
        return local_public_text(), "local-fallback"
    except Exception:
        return local_public_text(), "local-fallback"


def render_post_payload(title: str, content: str) -> Dict[str, Any]:
    title = (title or "").strip()[:30] or "来冒个泡"
    paragraphs = [p.strip() for p in (content or "").split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = ["冒个泡"]
    html_parts = []
    ops: List[Any] = []
    for para in paragraphs:
        html_parts.append(f"<p>{html.escape(para)}</p>")
        ops.append({"insert": f"{para}\n"})
    html_parts.append("<p><br></p>")
    return {
        "forum_id": FORUM_ID,
        "topic_id": "",
        "title": title,
        "content": "".join(html_parts),
        "content_origin": json.dumps({"ops": ops}, ensure_ascii=False),
        "cover": "",
    }


def weekday_plan(skip_social: bool) -> Dict[str, bool]:
    """按上游星期逻辑决定互动动作。"""
    if skip_social:
        return {"like": False, "post": False, "comment": False}
    weekday = _now().weekday()  # 0=周一
    if weekday in (5, 6):
        return {"like": False, "post": True, "comment": True}
    if weekday == 4:
        return {"like": True, "post": True, "comment": True}
    return {"like": False, "post": False, "comment": False}


def weekday_name() -> str:
    return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][_now().weekday()]


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


def _notify_global_mode() -> str:
    raw = env_raw("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in TRUE_VALUES:
        return "enabled"
    if raw in FALSE_VALUES:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if raw is None:
        return None
    if raw.strip() == "":
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _selector_match(selector: str) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if sel == "*":
        return True
    candidates = {c.lower() for c in SCRIPT_IDENTITIES}
    sel_l = sel.lower()
    if sel_l in candidates:
        return True
    for identity in SCRIPT_IDENTITIES:
        if _ql_notify_fnmatch.fnmatch(identity.lower(), sel_l):
            return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
    if mode == "enabled":
        return True
    selectors = _script_selectors()
    if selectors is None:
        return True
    if not selectors:
        return False
    return any(_selector_match(s) for s in selectors)


def _load_notify_send():
    try:
        from notify import send as notify_send  # type: ignore

        return notify_send
    except Exception:
        pass
    candidates: List[str] = []
    custom = env_raw("QINGLONG_NOTIFY_DIR").strip()
    if custom:
        candidates.append(os.path.join(custom, "notify.py"))
    candidates.extend(
        [
            "/ql/data/scripts/notify.py",
            "/ql/scripts/notify.py",
        ]
    )
    for path in candidates:
        try:
            if not os.path.isfile(path):
                continue
            spec = importlib.util.spec_from_file_location("ql_notify_mod", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = getattr(module, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, content: str) -> str:
    if not _should_notify():
        return "skipped"
    send = _load_notify_send()
    if send is None:
        log(f"{STATUS_ICONS['warning']} 未找到可用 notify.py，跳过通知并保留业务退出码")
        return "unavailable"
    try:
        send(title, content)
        return "sent"
    except Exception:
        log(f"{STATUS_ICONS['warning']} 通知发送失败，已忽略并保留业务退出码")
        return "failed"


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------


class ElantranClient:
    def __init__(self, token: str, timeout: float, dry_run: bool = False):
        self.token = token
        self.timeout = timeout
        self.dry_run = dry_run
        self.headers = {
            "Host": API_HOST,
            "xweb_xhr": "1",
            "nversion": "169",
            "authorization": f"Bearer {token}",
            "user-agent": UA,
            "content-type": "application/json",
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
        }

    def api(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        return http_json(
            url,
            method="POST",
            headers=self.headers,
            body={} if body is None else body,
            timeout=self.timeout,
            dry_run=self.dry_run,
            allow_hosts=(API_HOST,),
        )

    def sign_status(self) -> Tuple[str, str]:
        result = self.api("/home/bbs/sign_today_user_status", {})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"签到状态请求失败 HTTP {result['status']}")
        code = payload.get("code", -1)
        if code == 403:
            raise SafeError("认证已失效，请重新获取 ELANTRAN_AUTH")
        if code != 0:
            raise SafeError(f"签到状态检查失败：{business_message(payload) or '未知错误'}")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        status = str(data.get("status") or "UNKNOWN")
        if status == "IS":
            return "alreadyComplete", "今日已签到"
        if status == "NOT":
            return "pending", "今日未签到"
        raise SafeError(f"签到状态未知：{status}")

    def sign(self) -> Tuple[str, str]:
        result = self.api("/home/bbs/sign", {})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"签到请求失败 HTTP {result['status']}")
        code = payload.get("code", -1)
        if code == 403:
            raise SafeError("认证已失效，请重新获取 ELANTRAN_AUTH")
        if code != 0:
            raise SafeError(f"签到失败：{business_message(payload) or '未知错误'}")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        title = str(data.get("title") or "签到成功")
        msg = str(data.get("msg") or "").replace("<br>", " ")
        detail = compact(f"{title} {msg}".strip(), 160)
        return "success", detail or "签到成功"

    def sign_detail_tomorrow(self) -> Optional[int]:
        today = _now().strftime("%Y-%m-%d")
        result = self.api("/home/bbs/sign_detail", {"day_type": "WEEK", "day": today})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            return None
        if payload.get("code") != 0:
            return None
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        point = data.get("tomorrow_point")
        try:
            return int(point)
        except (TypeError, ValueError):
            return None

    def total_point(self) -> Optional[int]:
        result = self.api("/home/user/get_my_stat_info", {})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            return None
        if payload.get("code") != 0:
            return None
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        point = data.get("total_point")
        try:
            return int(point)
        except (TypeError, ValueError):
            return None

    def get_post_list(self, page: int = 1) -> List[Dict[str, Any]]:
        result = self.api(
            "/home/bbs/get_post_list",
            {"is_choice": "IS", "page": page, "limit": 10},
        )
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"获取帖子列表失败 HTTP {result['status']}")
        if payload.get("code") != 0:
            raise SafeError(f"获取帖子列表失败：{business_message(payload) or '未知错误'}")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        posts = data.get("list")
        if not isinstance(posts, list):
            return []
        return [p for p in posts if isinstance(p, dict)]

    def like_post(self, post_id: Any) -> None:
        result = self.api("/home/bbs/like_post", {"id": post_id})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"点赞失败 HTTP {result['status']}")
        if payload.get("code") != 0:
            raise SafeError(f"点赞失败：{business_message(payload) or '未知错误'}")

    def create_post(self, title: str, content: str) -> None:
        result = self.api("/home/bbs/save_post_info", render_post_payload(title, content))
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"发帖失败 HTTP {result['status']}")
        if payload.get("code") != 0:
            raise SafeError(f"发帖失败：{business_message(payload) or '未知错误'}")

    def get_post_detail(self, post_id: Any) -> Dict[str, Any]:
        result = self.api("/home/bbs/get_post_detail", {"id": post_id})
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"获取帖子详情失败 HTTP {result['status']}")
        if payload.get("code") != 0:
            raise SafeError(f"获取帖子详情失败：{business_message(payload) or '未知错误'}")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    def comment_post(self, post_id: Any, comment: str) -> None:
        body = {
            "post_id": post_id,
            "comment_id": "",
            "content": f"<p>{html.escape(comment)}<br></p>",
            "content_origin": json.dumps(
                {"ops": [{"insert": f"{comment}\n"}]}, ensure_ascii=False
            ),
            "at_uid": "",
        }
        result = self.api("/home/bbs/save_post_comment_info", body)
        payload = result["json"]
        if result["status"] != 200 or not isinstance(payload, dict):
            raise SafeError(f"评论失败 HTTP {result['status']}")
        if payload.get("code") != 0:
            raise SafeError(f"评论失败：{business_message(payload) or '未知错误'}")


def action_delay(seconds: float, dry_run: bool) -> None:
    if dry_run or seconds <= 0:
        return
    time.sleep(seconds)


def run_account_dry(
    index: int,
    total: int,
    token: str,
    plan: Dict[str, bool],
) -> Dict[str, Any]:
    started = time.monotonic()
    ok_token, token_msg, name, uid = check_token_local(token)
    identity = name or (f"UID:{uid}" if uid else f"账号{index}")
    log(f"—— 账号 {index}/{total}（{identity}）——")
    stats = {
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    stages: List[str] = []

    def stage(num: int, title: str, state: str, detail: str) -> None:
        icon = STATUS_ICONS.get(state, STATUS_ICONS["failure"])
        log(f"阶段{num} {title}：{icon} {detail}")
        stages.append(f"{num}:{title}:{state}")
        if state == "success":
            stats["success"] += 1
        elif state == "alreadyComplete":
            stats["alreadyComplete"] += 1
        elif state == "skipped":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

    stage(1, "校验Token", "success" if ok_token else "failure", token_msg)
    if not ok_token:
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": token_msg,
            "stats": stats,
        }

    if name:
        log(f"公开身份: {name}" + (f" / UID {uid}" if uid else ""))
    elif uid:
        log(f"公开身份: UID {uid}")

    stage(2, "签到状态", "success", "dry-run 跳过真实查询")
    stage(3, "执行签到", "success", "dry-run 模拟签到成功")
    if plan["like"]:
        stage(4, "点赞互动", "success", "dry-run 模拟点赞")
    else:
        stage(4, "点赞互动", "skipped", f"{weekday_name()}不执行点赞")
    if plan["post"]:
        text, source = fetch_public_text(dry_run=True, timeout=HTTP_TIMEOUT)
        stage(5, "发帖", "success", f"dry-run 使用{source}文案（{compact(text, 40)}）")
    else:
        stage(5, "发帖", "skipped", f"{weekday_name()}不执行发帖")
    if plan["comment"]:
        text, source = fetch_public_text(dry_run=True, timeout=HTTP_TIMEOUT)
        stage(6, "评论", "success", f"dry-run 使用{source}文案（{compact(text, 40)}）")
    else:
        stage(6, "评论", "skipped", f"{weekday_name()}不执行评论")
    stage(7, "积分查询", "skipped", "dry-run 不查询积分")

    elapsed = time.monotonic() - started
    log(
        f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
    )
    return {
        "ok": True,
        "identity": identity,
        "status": "dry-run-success",
        "message": "断网预演通过",
        "stats": stats,
    }


def run_account_live(
    index: int,
    total: int,
    token: str,
    *,
    timeout: float,
    plan: Dict[str, bool],
    action_delay_sec: float,
) -> Dict[str, Any]:
    started = time.monotonic()
    ok_token, token_msg, name, uid = check_token_local(token)
    identity = name or (f"UID:{uid}" if uid else f"账号{index}")
    log(f"—— 账号 {index}/{total}（{identity}）——")
    stats = {
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    messages: List[str] = []
    account_ok = True

    def mark(state: str) -> None:
        if state == "success":
            stats["success"] += 1
        elif state == "alreadyComplete":
            stats["alreadyComplete"] += 1
        elif state == "skipped":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

    def stage(num: int, title: str, state: str, detail: str) -> None:
        icon = STATUS_ICONS.get(state, STATUS_ICONS["failure"])
        log(f"阶段{num} {title}：{icon} {detail}")
        mark(state)
        messages.append(f"{title}:{detail}")

    stage_t0 = time.monotonic()
    if not ok_token:
        stage(1, "校验Token", "failure", token_msg)
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": token_msg,
            "stats": stats,
        }
    stage(1, "校验Token", "success", f"{token_msg}（耗时 {time.monotonic() - stage_t0:.2f}秒）")
    if name:
        log(f"公开身份: {name}" + (f" / UID {uid}" if uid else ""))
        identity = name
    elif uid:
        log(f"公开身份: UID {uid}")
        identity = f"UID:{uid}"

    client = ElantranClient(token, timeout=timeout, dry_run=False)

    try:
        stage_t0 = time.monotonic()
        status_state, status_detail = client.sign_status()
        if status_state == "alreadyComplete":
            stage(
                2,
                "签到状态",
                "alreadyComplete",
                f"{status_detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
            )
            stage(3, "执行签到", "alreadyComplete", "今日已签到，跳过重复签到")
        else:
            stage(
                2,
                "签到状态",
                "success",
                f"{status_detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
            )
            stage_t0 = time.monotonic()
            sign_state, sign_detail = client.sign()
            tomorrow = client.sign_detail_tomorrow()
            if tomorrow is not None:
                sign_detail = f"{sign_detail}；明日可获 {tomorrow} 积分"
            stage(
                3,
                "执行签到",
                sign_state,
                f"{sign_detail}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
            )
    except SafeError as exc:
        account_ok = False
        stage(2, "签到", "failure", str(exc))
        elapsed = time.monotonic() - started
        log(
            f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
            f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
            f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
        )
        return {
            "ok": False,
            "identity": identity,
            "status": "failure",
            "message": str(exc),
            "stats": stats,
        }

    posts: List[Dict[str, Any]] = []
    if plan["like"]:
        stage_t0 = time.monotonic()
        try:
            unliked: List[Dict[str, Any]] = []
            page = 1
            while len(unliked) < 3 and page <= 5:
                batch = client.get_post_list(page=page)
                if not batch:
                    break
                posts.extend(batch)
                for post in batch:
                    if post.get("has_like") == "NOT":
                        unliked.append(post)
                page += 1
                action_delay(min(action_delay_sec, 1.5), False)
            liked = 0
            for post in unliked[:3]:
                client.like_post(post.get("id"))
                liked += 1
                action_delay(action_delay_sec, False)
            if liked == 0:
                stage(
                    4,
                    "点赞互动",
                    "skipped",
                    f"无可点赞帖子（耗时 {time.monotonic() - stage_t0:.2f}秒）",
                )
            else:
                stage(
                    4,
                    "点赞互动",
                    "success",
                    f"点赞 {liked} 个帖子（耗时 {time.monotonic() - stage_t0:.2f}秒）",
                )
        except SafeError as exc:
            account_ok = False
            stage(4, "点赞互动", "failure", str(exc))
    else:
        stage(4, "点赞互动", "skipped", f"{weekday_name()}不执行点赞")

    if plan["post"]:
        stage_t0 = time.monotonic()
        try:
            if not posts:
                try:
                    posts = client.get_post_list(page=1)
                except SafeError:
                    posts = []
            text, source = fetch_public_text(dry_run=False, timeout=timeout)
            title = compact(text, 28) or "来冒个泡"
            client.create_post(title, text)
            stage(
                5,
                "发帖",
                "success",
                f"发布成功（文案来源 {source}，耗时 {time.monotonic() - stage_t0:.2f}秒）",
            )
            action_delay(action_delay_sec, False)
        except SafeError as exc:
            account_ok = False
            stage(5, "发帖", "failure", str(exc))
    else:
        stage(5, "发帖", "skipped", f"{weekday_name()}不执行发帖")

    if plan["comment"]:
        stage_t0 = time.monotonic()
        try:
            if not posts:
                posts = client.get_post_list(page=1)
            if not posts:
                stage(6, "评论", "skipped", "没有可评论的帖子")
            else:
                target = random.choice(posts)
                post_id = target.get("id")
                try:
                    client.get_post_detail(post_id)
                except SafeError:
                    pass
                text, source = fetch_public_text(dry_run=False, timeout=timeout)
                reply = compact(text, 80) or "支持一下，好帖子。"
                client.comment_post(post_id, reply)
                stage(
                    6,
                    "评论",
                    "success",
                    f"评论成功（文案来源 {source}，耗时 {time.monotonic() - stage_t0:.2f}秒）",
                )
                action_delay(action_delay_sec, False)
        except SafeError as exc:
            account_ok = False
            stage(6, "评论", "failure", str(exc))
    else:
        stage(6, "评论", "skipped", f"{weekday_name()}不执行评论")

    try:
        stage_t0 = time.monotonic()
        point = client.total_point()
        if point is None:
            stage(7, "积分查询", "skipped", "未获取到积分")
        else:
            stage(
                7,
                "积分查询",
                "success",
                f"当前总积分 {point}（耗时 {time.monotonic() - stage_t0:.2f}秒）",
            )
    except SafeError as exc:
        stage(7, "积分查询", "skipped", str(exc))

    elapsed = time.monotonic() - started
    log(
        f"账号统计：总任务 {sum(stats.values())}，成功 {stats['success']}，"
        f"已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，"
        f"失败 {stats['failed']}，耗时 {elapsed:.2f}秒"
    )
    status = "success" if account_ok and stats["failed"] == 0 else "failure"
    return {
        "ok": account_ok and stats["failed"] == 0,
        "identity": identity,
        "status": status,
        "message": "；".join(messages)[:240],
        "stats": stats,
    }


def main() -> int:
    task_start = _now()
    dry = env_truthy(DRY_RUN_ENV, False)
    mode = "dry-run" if dry else "live"

    print("=" * 56, flush=True)
    log(f"任务: {SCRIPT_NAME}")
    log(f"开始时间: {task_start.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")
    log(f"今日: {weekday_name()}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        timeout = float(int_env(TIMEOUT_ENV, HTTP_TIMEOUT, 5, 90))
        action_delay_sec = float(int_env(ACTION_DELAY_ENV, 2, 0, 120))
        account_delay_sec = float(int_env(ACCOUNT_DELAY_ENV, 3, 0, 600))
        skip_social = env_truthy(SKIP_SOCIAL_ENV, False)
        plan = weekday_plan(skip_social)
        log(
            "互动计划: "
            f"点赞={'开' if plan['like'] else '关'} / "
            f"发帖={'开' if plan['post'] else '关'} / "
            f"评论={'开' if plan['comment'] else '关'}"
            + ("（已强制跳过社区互动）" if skip_social else "")
        )

        raw = env_raw(AUTH_ENV)
        if not raw.strip():
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{STATUS_ICONS['failure']} 未配置必填环境变量 {AUTH_ENV}")
            log(
                "获取方式: 打开 Elantran 微信小程序，抓包任意业务请求，复制 "
                "Authorization: Bearer 后的 JWT，写入青龙环境变量 ELANTRAN_AUTH；"
                "每行一个账号。"
            )
            log("账号数量: 0")
        else:
            accounts = parse_accounts(raw)
            log(f"账号数量: {len(accounts)}")
            if not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{STATUS_ICONS['failure']} 未解析到任何有效账号")
            else:
                total = len(accounts)
                for idx, token in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, token, plan)
                    else:
                        ar = run_account_live(
                            idx,
                            total,
                            token,
                            timeout=timeout,
                            plan=plan,
                            action_delay_sec=action_delay_sec,
                        )
                    account_results.append(ar)
                    if idx < total and account_delay_sec > 0 and not dry:
                        log(f"账号间隔等待 {account_delay_sec:.0f} 秒")
                        time.sleep(account_delay_sec)

                failed = [a for a in account_results if not a.get("ok")]
                succeeded = [a for a in account_results if a.get("ok")]
                if failed and succeeded:
                    summary_status = "partial-failure"
                    exit_code = 1
                elif failed:
                    summary_status = "failure"
                    exit_code = 1
                else:
                    summary_status = "dry-run" if dry else "success"
                    exit_code = 0
    except SafeError as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{STATUS_ICONS['failure']} 配置错误: {exc}")
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{STATUS_ICONS['failure']} 未处理异常: {type(exc).__name__}")
        traceback.print_exc()

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56, flush=True)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(int((a.get("stats") or {}).get("success") or 0) for a in account_results)
    sub_fail = sum(int((a.get("stats") or {}).get("failed") or 0) for a in account_results)
    sub_skip = sum(int((a.get("stats") or {}).get("skipped") or 0) for a in account_results)
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0) for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {task_end.strftime('%Y-%m-%d %H:%M:%S')}")

    if dry and not config_error:
        event = "dry-run"
    elif config_error:
        event = "configuration-error"
    elif fail_count and ok_count:
        event = "partial-failure"
    elif fail_count:
        event = "failure"
    else:
        event = "success"

    lines = [
        f"任务: {SCRIPT_NAME}",
        f"模式: {mode}",
        f"事件: {event}",
        f"账号总数: {total_accounts if not config_error else 0}",
        f"成功: {ok_count}",
        f"失败: {fail_count}",
        f"状态: {summary_status}",
    ]
    for a in account_results:
        lines.append(
            f"- {a.get('identity')}: {a.get('status')} / {compact(str(a.get('message', '')), 120)}"
        )
    notify_status = send_notification(SCRIPT_NAME, "\n".join(lines))
    log(f"通知状态: {notify_status}")

    final_status = summary_status
    if exit_code == 0 and dry and not config_error:
        print("DRY_RUN_OK", flush=True)
        final_status = "dry-run-success"
        log(f"{STATUS_ICONS['success']} 最终状态: dry-run-success")
    elif exit_code == 0:
        log(f"{STATUS_ICONS['success']} 最终状态: success")
    elif config_error:
        log(f"{STATUS_ICONS['failure']} 最终状态: configuration-error")
    else:
        log(f"{STATUS_ICONS['failure']} 最终状态: {summary_status}")

    task_summary = {
        "catalogId": CATALOG_ID,
        "script": SCRIPT_FILENAME,
        "task": SCRIPT_NAME,
        "mode": mode,
        "status": final_status if exit_code == 0 else summary_status,
        "exitCode": exit_code,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSucceeded": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notifyStatus": notify_status,
        "finishedAt": task_end.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(
        "TASK_SUMMARY="
        + json.dumps(task_summary, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
