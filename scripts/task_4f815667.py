#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 昆明医科大疫情健康填报
# cron: 43 8 * * *
"""
昆明医科大学学工疫情每日健康填报（维护版）

上游来源: https://github.com/tom125730/Epidemic (main.py)
Commit: 5de5592190d58ff358e3793c37e3dc357f6a1246
许可证: MIT

MIT License

Copyright (c) tom125730 / Epidemic contributors

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

功能:
  - 使用学号与密码登录昆明医科大学学工 SPCP 平台
  - 打开疫情填报表单；若当日已登记则视为已完成
  - 在可填报时段提交健康信息（默认「健康/无症状」选项，与上游一致）
  - 识别「非填报时段」「填报未开启」等业务提示

环境变量:
  KMMU_EPIDEMIC           必填。每行一个账号：学号&密码
  KMMU_EPIDEMIC_DRY_RUN   设为 1/true/yes/on 时启用完全断网预演
  KMMU_EPIDEMIC_UA        可选。自定义 User-Agent
  QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS  通知开关

定时: 10 8 * * *（平台允许 1 点至 18 点填报）
"""

from __future__ import annotations
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
        _ql_notify_identities = ('4f8156672d8cb5bd', 'scripts/task_4f815667.py', 'task_4f815667.py', 'task_4f815667')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import json
import os
import re
import sys
import traceback
import uuid
from datetime import datetime
from html import unescape
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
SCRIPT_NAME = "昆明医科大疫情健康填报"
CATALOG_ID = "4f8156672d8cb5bd"
SCRIPT_FILENAME = "candidate.py"
BASE = "https://xg.kmmu.edu.cn"
LOGIN_URL = f"{BASE}/SPCP/Web/"
CHOOSE_SYS_URL = f"{BASE}/SPCP/Web/Account/ChooseSys"
REPORT_URL = f"{BASE}/SPCP/Web/Report/Index"
DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "yiban_iOS/4.9.3"
)
HTTP_TIMEOUT = 25
DRY_RUN_ENV = "KMMU_EPIDEMIC_DRY_RUN"
CRED_ENV = "KMMU_EPIDEMIC"
UA_ENV = "KMMU_EPIDEMIC_UA"

ICON_OK = "✅"
ICON_DONE = "☑️"
ICON_SKIP = "⏭️"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"

# 上游默认「健康」问卷选项（与原 main.py 一致）
DEFAULT_RADIO = {
    "radio_1": "71a16876-3d52-4510-8c96-09b232a0161b",
    "radio_2": "083d90f5-5fa2-4a6d-a231-fe315b5104a3",
    "radio_3": "994c60eb-6f68-48bd-8bda-49a8a7ea812c",
    "radio_4": "18e9be47-deee-4eb0-8318-935f7ec832fd",
    "radio_5": "8dce119f-8eba-45b7-ac3c-ecb49e480dd3",
    "radio_6": "fe8b77d7-0014-49e1-bea0-46b0bff13898",
}
DEFAULT_PZDATA = [
    {
        "OptionName": "以上症状都没有",
        "SelectId": "71a16876-3d52-4510-8c96-09b232a0161b",
        "TitleId": "eb0c8db7-b4dd-4ad6-b58a-626fc3336f16",
        "OptionType": "0",
    },
    {
        "OptionName": "否，身体健康",
        "SelectId": "083d90f5-5fa2-4a6d-a231-fe315b5104a3",
        "TitleId": "a9a30b10-f88e-4776-ac74-b5a10fa11886",
        "OptionType": "0",
    },
    {
        "OptionName": "否，不是疑似感染者",
        "SelectId": "994c60eb-6f68-48bd-8bda-49a8a7ea812c",
        "TitleId": "37e33b7d-5575-48c3-b59b-d4b7f6a6a0b5",
        "OptionType": "0",
    },
    {
        "OptionName": "否",
        "SelectId": "18e9be47-deee-4eb0-8318-935f7ec832fd",
        "TitleId": "986a95ff-5ce4-4417-9810-b1e190594f34",
        "OptionType": "0",
    },
    {
        "OptionName": "否",
        "SelectId": "8dce119f-8eba-45b7-ac3c-ecb49e480dd3",
        "TitleId": "3a3a10c8-02a7-4f16-95e5-f8ef5c8bfd75",
        "OptionType": "0",
    },
    {
        "OptionName": "健康",
        "SelectId": "fe8b77d7-0014-49e1-bea0-46b0bff13898",
        "TitleId": "6002f891-d80d-4e01-ad6d-651e01df394b",
        "OptionType": "0",
    },
]


# ---------------------------------------------------------------------------
# 时间 / 日志
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now()


def _ts(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%H:%M:%S")


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def log_stage(index: int, title: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    log(f"阶段{index} {title}{suffix}")


# ---------------------------------------------------------------------------
# 环境 / 账号解析
# ---------------------------------------------------------------------------
def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_dry_run() -> bool:
    return _env_truthy(DRY_RUN_ENV)


def _user_agent() -> str:
    custom = os.getenv(UA_ENV, "").strip()
    return custom or DEFAULT_UA


def parse_accounts(raw: str) -> List[Dict[str, str]]:
    """每行一个账号；仅按第一个 & 分割学号与密码。"""
    accounts: List[Dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "&" not in text:
            raise ValueError(f"第 {line_no} 行账号格式无效：缺少学号与密码分隔符 &")
        username, password = text.split("&", 1)
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise ValueError(f"第 {line_no} 行账号格式无效：学号或密码为空")
        accounts.append({"username": username, "password": password})
    return accounts


# ---------------------------------------------------------------------------
# 通知（青龙 notify.py）
# ---------------------------------------------------------------------------
def _notify_global_mode() -> str:
    raw = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if raw in {"", "auto"}:
        return "auto"
    if raw in {"1", "true", "yes", "on"}:
        return "enabled"
    if raw in {"0", "false", "no", "off"}:
        return "disabled"
    return "auto"


def _script_selectors() -> Optional[List[str]]:
    raw = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
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
    candidates = {
        CATALOG_ID,
        SCRIPT_FILENAME,
        f"scripts/{SCRIPT_FILENAME}",
        SCRIPT_NAME,
        "kmmu_epidemic.py",
        "scripts/kmmu_epidemic.py",
    }
    if sel in candidates:
        return True
    if sel.endswith("*") and SCRIPT_FILENAME.startswith(sel[:-1]):
        return True
    return False


def _should_notify() -> bool:
    mode = _notify_global_mode()
    if mode == "disabled":
        return False
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
    search_dirs = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        search_dirs.append(custom)
    search_dirs.extend(["/ql/data/scripts", "/ql/scripts"])
    for directory in search_dirs:
        path = os.path.join(directory, "notify.py")
        if not os.path.isfile(path):
            continue
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("ql_notify", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            send = getattr(mod, "send", None)
            if callable(send):
                return send
        except Exception:
            continue
    return None


def send_notification(title: str, body: str) -> str:
    if not _should_notify():
        log("通知: 已跳过（全局开关或脚本选择未启用）")
        return "skipped"
    sender = _load_notify_send()
    if sender is None:
        log(f"{ICON_WARN} 通知: 未找到 notify.py，已跳过发送")
        return "unavailable"
    try:
        sender(title, body)
        log(f"{ICON_OK} 通知: 已发送")
        return "sent"
    except Exception as exc:
        log(f"{ICON_WARN} 通知发送失败: {type(exc).__name__}")
        return "failed"


# ---------------------------------------------------------------------------
# HTTP（标准库）
# ---------------------------------------------------------------------------
class HttpClient:
    def __init__(self, ua: str, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.ua = ua
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        referer: Optional[str] = None,
    ) -> str:
        body = None
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if referer:
            headers["Referer"] = referer
        if data is not None:
            encoded: Dict[str, str] = {}
            for key, value in data.items():
                encoded[key] = "" if value is None else str(value)
            body = urlencode(encoded).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except HTTPError as exc:
            try:
                raw = exc.read()
                charset = exc.headers.get_content_charset() if exc.headers else None
                text = raw.decode(charset or "utf-8", errors="replace")
            except Exception:
                text = ""
            if text:
                return text
            raise RuntimeError(f"HTTP {exc.code}: {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"网络错误: {exc.reason}") from exc
        except Exception as exc:
            raise RuntimeError(f"请求失败: {type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------------------
# HTML 解析辅助（不依赖 lxml）
# ---------------------------------------------------------------------------
def _input_value(html: str, field_id: str) -> str:
    patterns = [
        rf'id=["\']{re.escape(field_id)}["\'][^>]*\bvalue=["\']([^"\']*)["\']',
        rf'\bvalue=["\']([^"\']*)["\'][^>]*id=["\']{re.escape(field_id)}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return unescape(m.group(1).strip())
    return ""


def _script_alerts(html: str) -> str:
    parts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.I | re.S)
    return "\n".join(parts)


def _data_defaultvalues(html: str) -> List[str]:
    return re.findall(r'data-defaultvalue=["\']([^"\']*)["\']', html, flags=re.I)


def _require_fields(html: str, ids: List[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    missing: List[str] = []
    for field_id in ids:
        value = _input_value(html, field_id)
        if not value and field_id not in {"MoveTel"}:
            # MoveTel 允许空，其余关键身份字段必须存在
            if field_id in {
                "StudentId",
                "Name",
                "Sex",
                "SpeType",
                "CollegeNo",
                "SpeGrade",
                "SpecialtyName",
                "ClassName",
                "IdCard",
            }:
                missing.append(field_id)
        values[field_id] = value
    if missing:
        raise RuntimeError(f"填报表单缺少字段: {', '.join(missing)}")
    return values


def _build_location_payload(html: str) -> Dict[str, str]:
    """按上游逻辑从 data-defaultvalue 与隐藏域组装现住址/家庭住址。"""
    defaults = [d for d in _data_defaultvalues(html) if d]
    # 上游 xpath：现住址与家庭住址各取 select[2]/select[3]；
    # 页面通常按 省/市/县 × 2 给出 6 个 data-defaultvalue。
    city = defaults[1] if len(defaults) > 1 else ""
    county = defaults[2] if len(defaults) > 2 else ""
    fa_city = defaults[4] if len(defaults) > 4 else city
    fa_county = defaults[5] if len(defaults) > 5 else county
    if not city and len(defaults) >= 1:
        city = defaults[0]
    if not city:
        raise RuntimeError("未能从填报表单解析现住址地区编码")

    province = f"{city[0:2]}0000" if len(city) >= 2 else ""
    fa_province = f"{fa_city[0:2]}0000" if len(fa_city) >= 2 else province

    # 详细地址输入框（上游取 div 内 input/@value）
    address_inputs = re.findall(
        r'<input[^>]*\bvalue=["\']([^"\']*)["\'][^>]*>',
        html,
        flags=re.I,
    )
    # 过滤已知隐藏身份字段值，优先取较长中文地址
    known = {
        _input_value(html, x)
        for x in (
            "StudentId",
            "Name",
            "Sex",
            "SpeType",
            "CollegeNo",
            "SpeGrade",
            "SpecialtyName",
            "ClassName",
            "MoveTel",
            "IdCard",
            "ProvinceName",
            "CityName",
            "CountyName",
            "FaProvinceName",
            "FaCityName",
            "FaCountyName",
        )
    }
    candidates = [
        unescape(v.strip())
        for v in address_inputs
        if v.strip() and v.strip() not in known and not re.fullmatch(r"[\da-f-]{8,}", v.strip(), re.I)
    ]
    come_where = candidates[0] if candidates else _input_value(html, "ComeWhere")
    fa_come = candidates[1] if len(candidates) > 1 else (
        _input_value(html, "FaComeWhere") or come_where
    )

    return {
        "Province": province,
        "City": city,
        "County": county or city,
        "ComeWhere": come_where,
        "FaProvince": fa_province,
        "FaCity": fa_city or city,
        "FaCounty": fa_county or county or city,
        "FaComeWhere": fa_come,
        "ProvinceName": _input_value(html, "ProvinceName"),
        "CityName": _input_value(html, "CityName"),
        "CountyName": _input_value(html, "CountyName"),
        "FaProvinceName": _input_value(html, "FaProvinceName"),
        "FaCityName": _input_value(html, "FaCityName"),
        "FaCountyName": _input_value(html, "FaCountyName"),
    }


def _build_submit_payload(html: str) -> Tuple[Dict[str, Any], str]:
    base_fields = _require_fields(
        html,
        [
            "StudentId",
            "Name",
            "Sex",
            "SpeType",
            "CollegeNo",
            "SpeGrade",
            "SpecialtyName",
            "ClassName",
            "MoveTel",
            "IdCard",
        ],
    )
    location = _build_location_payload(html)
    identity_name = base_fields.get("Name") or ""
    payload: Dict[str, Any] = {
        **base_fields,
        **location,
        **DEFAULT_RADIO,
        "text_1": "",
        "Other": "",
        "GetAreaUrl": "/SPCP/Web/Report/GetArea",
        "radioCount": "6",
        "checkboxCount": "0",
        "blackCount": "1",
        "PZData": str(DEFAULT_PZDATA),
        "ReSubmiteFlag": str(uuid.uuid4()),
    }
    return payload, identity_name


# ---------------------------------------------------------------------------
# 业务
# ---------------------------------------------------------------------------
def login(client: HttpClient, username: str, password: str) -> None:
    # 先打开登录页拿会话 Cookie（不再使用上游硬编码过期 ticket）
    client.request(LOGIN_URL, method="GET")
    form = {
        "ReSubmiteFlag": str(uuid.uuid4()),
        "StuLoginMode": "1",
        "txtUid": username,
        "txtPwd": password,
        "codeInput": "",
    }
    resp = client.request(LOGIN_URL, method="POST", data=form, referer=LOGIN_URL)
    alert = _script_alerts(resp)
    if "用户名或者密码错误" in alert or "用户名或者密码错误" in resp:
        raise RuntimeError("登录失败：学号或密码错误")
    # 登录成功通常会跳转或进入系统选择；若仍停在带错误脚本的登录页则失败
    if "txtUid" in resp and "txtPwd" in resp and "alert(" in alert.lower():
        # 其他登录失败文案
        m = re.search(r"alert\(['\"]([^'\"]+)['\"]\)", alert)
        if m and ("错误" in m.group(1) or "失败" in m.group(1)):
            raise RuntimeError(f"登录失败：{m.group(1)[:80]}")


def open_report_page(client: HttpClient) -> str:
    client.request(CHOOSE_SYS_URL, method="GET", referer=LOGIN_URL)
    return client.request(REPORT_URL, method="GET", referer=CHOOSE_SYS_URL)


def interpret_report_gate(html: str) -> Optional[Dict[str, Any]]:
    """若页面以脚本提示拦截填报，返回已处理结果；否则返回 None 继续提交。"""
    alert = _script_alerts(html)
    combined = alert or html
    if "已登记" in combined:
        return {
            "ok": True,
            "already": True,
            "message": "当前采集日期已登记",
            "identity": "",
        }
    if "只能1点至18点" in combined:
        return {
            "ok": False,
            "already": False,
            "message": "非填报时段（仅 1 点至 18 点可填报）",
            "identity": "",
        }
    if "填报信息还未配置或开启" in combined:
        return {
            "ok": False,
            "already": False,
            "message": "填报信息还未配置或开启，不能填报",
            "identity": "",
        }
    # 有表单则继续
    if _input_value(html, "StudentId"):
        return None
    if "alert(" in combined.lower():
        m = re.search(r"alert\(['\"]([^'\"]+)['\"]\)", combined)
        tip = m.group(1) if m else "页面提示未知"
        return {
            "ok": False,
            "already": False,
            "message": f"无法进入填报：{tip[:100]}",
            "identity": "",
        }
    raise RuntimeError("未能识别填报页状态（无表单且无业务提示）")


def submit_report(client: HttpClient, form_html: str) -> Dict[str, Any]:
    payload, identity = _build_submit_payload(form_html)
    resp = client.request(
        REPORT_URL, method="POST", data=payload, referer=REPORT_URL
    )
    if "提交成功" in resp:
        return {
            "ok": True,
            "already": False,
            "message": "提交成功",
            "identity": identity,
        }
    if "已登记" in resp:
        return {
            "ok": True,
            "already": True,
            "message": "当前采集日期已登记",
            "identity": identity,
        }
    if "只能1点至18点" in resp:
        return {
            "ok": False,
            "already": False,
            "message": "非填报时段（仅 1 点至 18 点可填报）",
            "identity": identity,
        }
    # 脱敏失败信息，不回传整页
    raise RuntimeError("提交未成功：响应中未包含「提交成功」")


# ---------------------------------------------------------------------------
# 账号执行
# ---------------------------------------------------------------------------
def run_account_dry(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始（预演）——")
    stats = {
        "total": 3,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": label,
        "ok": True,
        "status": "success",
        "message": "预演通过",
        "elapsedMs": 0,
    }

    log_stage(1, "校验账号格式", "学号与密码均已提供")
    stats["success"] += 1
    log(f"  {ICON_OK} 格式有效（不输出凭据）")

    log_stage(2, "预演登录", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将登录 {BASE}/SPCP/Web/")

    log_stage(3, "预演健康填报", "跳过真实网络请求")
    stats["skipped"] += 1
    log(f"  {ICON_SKIP} 断网预演：将访问 Report/Index 并提交健康信息")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    result["stats"] = stats
    log(
        f"{label} 统计: 总任务={stats['total']} 成功={stats['success']} "
        f"已完成={stats['alreadyComplete']} 跳过={stats['skipped']} "
        f"失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


def run_account_live(
    index: int, total: int, account: Dict[str, str]
) -> Dict[str, Any]:
    started = _now()
    label = f"账号{index}"
    log(f"—— {label}/{total} 开始 ——")
    stats = {
        "total": 3,
        "success": 0,
        "alreadyComplete": 0,
        "skipped": 0,
        "failed": 0,
    }
    result: Dict[str, Any] = {
        "index": index,
        "identity": label,
        "ok": False,
        "status": "failure",
        "message": "",
        "elapsedMs": 0,
        "stats": stats,
    }
    try:
        log_stage(1, "登录学工 SPCP")
        client = HttpClient(ua=_user_agent())
        login(client, account["username"], account["password"])
        stats["success"] += 1
        log(f"  {ICON_OK} 登录请求已完成（尚未确认身份）")

        log_stage(2, "打开疫情填报页")
        page = open_report_page(client)
        gated = interpret_report_gate(page)
        identity = _input_value(page, "Name") or label
        if identity and identity != label:
            result["identity"] = identity
            log(f"  {ICON_OK} 页面身份: {identity}")
        else:
            log(f"  {ICON_OK} 已进入填报流程")

        if gated is not None:
            if gated.get("identity"):
                result["identity"] = gated["identity"]
            elif identity:
                result["identity"] = identity
            if gated.get("already"):
                stats["success"] += 1
                log(f"  {ICON_OK} 已进入填报页")
                log_stage(3, "健康填报")
                stats["alreadyComplete"] += 1
                log(f"  {ICON_DONE} {gated['message']}")
                result["ok"] = True
                result["status"] = "success"
                result["message"] = gated["message"]
            elif gated.get("ok"):
                stats["success"] += 1
                log(f"  {ICON_OK} {gated['message']}")
                result["ok"] = True
                result["status"] = "success"
                result["message"] = gated["message"]
            else:
                stats["failed"] += 1
                log(f"  {ICON_FAIL} {gated['message']}")
                result["ok"] = False
                result["status"] = "failure"
                result["message"] = gated["message"]
        else:
            stats["success"] += 1
            log(f"  {ICON_OK} 表单可填报")
            log_stage(3, "提交健康填报")
            outcome = submit_report(client, page)
            if outcome.get("identity"):
                result["identity"] = outcome["identity"]
                log(f"  身份: {outcome['identity']}")
            if outcome.get("already"):
                stats["alreadyComplete"] += 1
                log(f"  {ICON_DONE} {outcome['message']}")
            elif outcome.get("ok"):
                stats["success"] += 1
                log(f"  {ICON_OK} {outcome['message']}")
            else:
                stats["failed"] += 1
                log(f"  {ICON_FAIL} {outcome['message']}")
            result["ok"] = bool(outcome.get("ok"))
            result["status"] = "success" if outcome.get("ok") else "failure"
            result["message"] = outcome.get("message") or ""
    except Exception as exc:
        stats["failed"] += 1
        result["ok"] = False
        result["status"] = "failure"
        result["message"] = str(exc)[:200]
        log(f"  {ICON_FAIL} {result['message']}")

    elapsed = int((_now() - started).total_seconds() * 1000)
    result["elapsedMs"] = elapsed
    log(
        f"{result['identity']} 统计: 总任务={stats['total']} "
        f"成功={stats['success']} 已完成={stats['alreadyComplete']} "
        f"跳过={stats['skipped']} 失败={stats['failed']} 耗时={elapsed}ms"
    )
    return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    task_start = _now()
    dry = _is_dry_run()
    mode = "dry-run" if dry else "live"

    print("=" * 56)
    print(f"  {SCRIPT_NAME}")
    print("=" * 56)
    log(f"开始时间: {_iso(task_start)}")
    log(f"运行模式: {mode}")
    log(f"目录 ID: {CATALOG_ID}")

    notify_status = "pending"
    exit_code = 0
    account_results: List[Dict[str, Any]] = []
    config_error = False
    summary_status = "success"

    try:
        raw = os.getenv(CRED_ENV, "")
        if not raw or not raw.strip():
            config_error = True
            exit_code = 2
            summary_status = "configuration-error"
            log(f"{ICON_FAIL} 未配置必填环境变量 {CRED_ENV}")
            log(
                f"获取方式: 在青龙环境变量中新增 {CRED_ENV}，"
                "每行一个账号，格式 学号&密码"
            )
            log("账号数量: 0")
        else:
            log(f"凭据来源: {CRED_ENV}（内容已脱敏）")
            try:
                accounts = parse_accounts(raw)
            except ValueError as exc:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 账号解析失败: {exc}")
                accounts = []

            log(f"账号数量: {len(accounts)}")
            if not config_error and not accounts:
                config_error = True
                exit_code = 2
                summary_status = "configuration-error"
                log(f"{ICON_FAIL} 未解析到任何有效账号")

            if not config_error:
                total = len(accounts)
                for idx, acc in enumerate(accounts, start=1):
                    if dry:
                        ar = run_account_dry(idx, total, acc)
                    else:
                        ar = run_account_live(idx, total, acc)
                    account_results.append(ar)

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
    except Exception as exc:
        config_error = True
        exit_code = 2
        summary_status = "configuration-error"
        log(f"{ICON_FAIL} 未处理异常: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    task_end = _now()
    elapsed_ms = int((task_end - task_start).total_seconds() * 1000)
    ok_count = sum(1 for a in account_results if a.get("ok"))
    fail_count = sum(1 for a in account_results if not a.get("ok"))
    total_accounts = len(account_results)

    print("-" * 56)
    log("任务统计")
    log(f"  账号结果: 总数={total_accounts} 成功={ok_count} 失败={fail_count}")
    sub_success = sum(
        int((a.get("stats") or {}).get("success") or 0) for a in account_results
    )
    sub_fail = sum(
        int((a.get("stats") or {}).get("failed") or 0) for a in account_results
    )
    sub_skip = sum(
        int((a.get("stats") or {}).get("skipped") or 0) for a in account_results
    )
    sub_done = sum(
        int((a.get("stats") or {}).get("alreadyComplete") or 0)
        for a in account_results
    )
    log(
        f"  子任务结果: 成功={sub_success} 已完成={sub_done} "
        f"跳过={sub_skip} 失败={sub_fail}"
    )
    log(f"  总耗时: {elapsed_ms}ms")
    log(f"  完成时间: {_iso(task_end)}")

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
            f"- {a.get('identity')}: {a.get('status')} / {a.get('message', '')[:80]}"
        )
    body = "\n".join(lines)
    notify_status = send_notification(SCRIPT_NAME, body)
    log(f"通知状态: {notify_status}")

    final_icon = {
        "success": ICON_OK,
        "dry-run": ICON_OK,
        "partial-failure": ICON_WARN,
        "failure": ICON_FAIL,
        "configuration-error": ICON_FAIL,
    }.get(summary_status, ICON_WARN)
    log(f"最终状态: {final_icon} {summary_status}")

    task_summary = {
        "script": SCRIPT_NAME,
        "catalogId": CATALOG_ID,
        "mode": mode,
        "status": summary_status,
        "accountsTotal": total_accounts if not config_error else 0,
        "accountsSuccess": ok_count,
        "accountsFailed": fail_count,
        "elapsedMs": elapsed_ms,
        "notify": notify_status,
        "dryRun": dry,
        "exitCode": exit_code,
    }
    print(f"TASK_SUMMARY={json.dumps(task_summary, ensure_ascii=False)}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
