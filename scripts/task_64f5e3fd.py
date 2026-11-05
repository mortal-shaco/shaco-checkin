#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 工软校园健康填报
# cron: 47 8 * * *
# new Env("工软校园健康填报")
#
# 来源：ULige-Enwr/GRXY_autoSign main.py（MIT）
# https://github.com/ULige-Enwr/GRXY_autoSign
# 提交：8ff7e0951ac8eb73d1569edba94d98ff37a507c6
#
# MIT License
#
# Copyright (c) 2022 ALyCE
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""工软校园（xy.4009955.com）学生每日健康填报 - 青龙维护版。

功能清点（相对上游 main.py）：
- 使用学号/密码/学校/openid 登录工软校园统一身份，本地 OCR 识别登录验证码
- 依次获取微信服务大厅与健康填报 token，拉取当日表单并提交「学生每日健康填报」
- 上游默认填报选项：校内、体温正常、无不适、未被隔离、第三针、绿码、未出校等
- 移除脚本内硬编码凭据、原始 Token/Cookie/验证码打印、无限重试与 yagmail 邮件
- 改为青龙环境变量多账号、GRXY_DRY_RUN 断网预演、超时、业务成功判定与青龙通知

GRXY_ACCOUNTS：每个非空行一个账号，格式
  学号|密码|学校|openid|姓名|学院|省|市|区
仅在第一个与末尾固定字段之间保留密码原文（密码可含竖线）；不要用 & 或 @ 分隔账号。
openid：从工软校园微信端登录相关请求参数或 Cookie 中获取，勿公开。
GRXY_TIMEOUT：单次 HTTP 请求超时秒数，默认 20，范围 5..60。
GRXY_MAX_RETRIES：验证码/登录流程最大尝试次数，默认 5，范围 1..10。
GRXY_DRY_RUN=1：完全断网预演，只校验参数与流程，不发起网络请求、不加载 OCR。
建议 Cron：0 8 * * *（表单截止时间参考上游 mrtbjzsj=22:10）。
正式填报依赖公开包 ddddocr（及传递依赖）；预演不需要。
不打印密码、Cookie、Token、openid、验证码或原始响应。
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
            "64f5e3fdafd9fdbb",
            "scripts/grxy_health_form.py",
            "grxy_health_form.py",
            "candidate.py",
            "grxy_health_form",
        )
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request

TITLE = "工软校园健康填报"
CATALOG_ID = "64f5e3fdafd9fdbb"
APPLICATION_KEY = "ulige-enwr/grxy_autosign::main"
BASE = "http://xy.4009955.com"
DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 5
MAX_BYTES = 65536
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 5.0; SM-N9100 Build/LRX21V) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/37.0.0.0 Mobile Safari/537.36 "
    "MicroMessenger/6.0.2.56_r958800.520 NetType/WIFI"
)
SUCCESS_HINTS = ("成功", "提交成功", "填报成功", "保存成功", "已完成")
ALREADY_HINTS = ("已填报", "已提交", "无需重复", "重复提交", "今日已", "已经填报")
_OCR = None


class SafeError(Exception):
    """仅携带可安全打印的说明。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def log(message: str) -> None:
    print("[{}] {}".format(stamp(), message), flush=True)


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in TRUE_VALUES


def env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("{} 必须是整数".format(name)) from exc
    if value < low or value > high:
        raise SafeError("{} 超出范围 {}..{}".format(name, low, high))
    return value


def parse_account_line(line: str, index: int) -> Dict[str, str]:
    # 学号|密码|学校|openid|姓名|学院|省|市|区
    # 从尾部固定取 7 个字段，中间整段作为密码，允许密码含竖线。
    parts = line.split("|")
    if len(parts) < 9:
        raise SafeError(
            "账号{}格式无效：需要 学号|密码|学校|openid|姓名|学院|省|市|区".format(index)
        )
    username = parts[0].strip()
    school = parts[-7].strip()
    openid = parts[-6].strip()
    xm = parts[-5].strip()
    xueyuan = parts[-4].strip()
    province = parts[-3].strip()
    city = parts[-2].strip()
    district = parts[-1].strip()
    password = "|".join(parts[1:-7])
    if not all([username, password, school, openid, xm, xueyuan, province, city, district]):
        raise SafeError("账号{}存在空字段，请检查九段配置".format(index))
    return {
        "username": username,
        "password": password,
        "school": school,
        "openid": openid,
        "xm": xm,
        "xueyuan": xueyuan,
        "province": province,
        "city": city,
        "district": district,
    }


def load_account_lines() -> List[str]:
    raw = os.getenv("GRXY_ACCOUNTS", "")
    lines: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(text)
    return lines


def http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    data: Any = None,
    json_body: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    allow_redirects: bool = True,
) -> Tuple[int, Dict[str, str], bytes, Optional[str]]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    body: Optional[bytes] = None
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json;charset=UTF-8")
    elif data is not None:
        if isinstance(data, (dict, list, tuple)):
            body = urllib.parse.urlencode(data).encode("utf-8")
            hdrs.setdefault(
                "Content-Type", "application/x-www-form-urlencoded;charset=UTF-8"
            )
        elif isinstance(data, bytes):
            body = data
        else:
            body = str(data).encode("utf-8")
    request = Request(url, data=body, headers=hdrs, method=method.upper())
    opener = urllib.request.build_opener()
    if not allow_redirects:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
                return None

        opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            raw = response.read(MAX_BYTES + 1)
            resp_headers = {k: v for k, v in response.headers.items()}
            location = resp_headers.get("Location") or resp_headers.get("location")
            return int(status), resp_headers, raw, location
    except urllib.error.HTTPError as error:
        status = int(error.code)
        raw = error.read(MAX_BYTES + 1) if error.fp is not None else b""
        resp_headers = {k: v for k, v in (error.headers.items() if error.headers else [])}
        location = resp_headers.get("Location") or resp_headers.get("location")
        if status in {301, 302, 303, 307, 308} and not allow_redirects:
            return status, resp_headers, raw, location
        if len(raw) > MAX_BYTES:
            raise SafeError("响应过大") from error
        return status, resp_headers, raw, location
    except Exception as exc:
        raise SafeError("网络连接失败或超时") from exc


def read_limited(raw: bytes) -> bytes:
    if len(raw) > MAX_BYTES:
        raise SafeError("响应过大")
    return raw


def parse_json_bytes(raw: bytes) -> Any:
    raw = read_limited(raw)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SafeError("响应不是有效 JSON") from exc


def extract_cookie_pair(set_cookie: str) -> str:
    if not set_cookie:
        raise SafeError("登录页未返回会话 Cookie")
    first = set_cookie.split(",")[0].split(";")[0].strip()
    if "=" not in first:
        raise SafeError("会话 Cookie 格式异常")
    return first


def extract_query_code(location: Optional[str]) -> str:
    if not location:
        raise SafeError("授权跳转缺少 Location")
    parsed = urllib.parse.urlparse(location)
    query = urllib.parse.parse_qs(parsed.query)
    code = (query.get("code") or [None])[0]
    if not code:
        # 兼容 fragment 或非标准拼接
        match = re.search(r"(?:^|[?&#])code=([^&#]+)", location)
        if not match:
            raise SafeError("授权跳转未包含 code")
        code = urllib.parse.unquote(match.group(1))
    return code


def message_of(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("msg", "message", "errorMsg", "errmsg", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = data.get("data")
        if isinstance(nested, dict):
            return message_of(nested)
    return ""


def classify_business(data: Any, http_ok: bool) -> str:
    msg = message_of(data)
    lowered = msg.lower()
    if any(hint in msg for hint in ALREADY_HINTS) or any(
        hint in lowered for hint in ("already",)
    ):
        return "alreadyComplete"
    if isinstance(data, dict):
        code = data.get("code")
        success = data.get("success")
        status = data.get("status")
        if success is True or status in (0, "0", "success", "ok", "OK"):
            return "success"
        if code in (0, "0", 200, "200", True):
            return "success"
        if code in (1, "1") and any(hint in msg for hint in SUCCESS_HINTS):
            return "success"
        if code not in (None, 0, "0", 200, "200", True) and msg:
            if any(hint in msg for hint in SUCCESS_HINTS):
                return "success"
            return "failure"
    if http_ok and any(hint in msg for hint in SUCCESS_HINTS):
        return "success"
    if http_ok and not msg and isinstance(data, dict):
        # 部分接口成功时仅返回 data 节点
        if data.get("data") is not None or data.get("content") is not None:
            return "success"
    return "failure"


def get_ocr():
    global _OCR
    if _OCR is not None:
        return _OCR
    try:
        import ddddocr  # type: ignore
    except Exception as exc:
        raise SafeError("缺少依赖 ddddocr，无法识别登录验证码") from exc
    try:
        _OCR = ddddocr.DdddOcr(show_ad=False)
    except TypeError:
        _OCR = ddddocr.DdddOcr()
    return _OCR


def recognize_captcha(image_bytes: bytes) -> str:
    ocr = get_ocr()
    try:
        text = ocr.classification(image_bytes)
    except Exception as exc:
        raise SafeError("验证码识别失败") from exc
    if not isinstance(text, str) or not text.strip():
        raise SafeError("验证码识别结果为空")
    return text.strip()


def decode_captcha_payload(payload: Any) -> bytes:
    text = ""
    if isinstance(payload, dict):
        for key in ("data", "content", "yzm", "img", "image", "base64"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
            if isinstance(value, dict):
                nested = decode_captcha_payload(value)
                if nested:
                    return nested
        if not text:
            # 退回扫描任意 data:image base64 字段
            dumped = json.dumps(payload, ensure_ascii=False)
            match = re.search(
                r"data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)", dumped
            )
            if match:
                text = match.group(1)
    elif isinstance(payload, str):
        text = payload
    if not text:
        raise SafeError("验证码响应缺少图像数据")
    if "," in text and "base64" in text[:64].lower():
        text = text.split(",", 1)[1]
    text = re.sub(r"\s+", "", text)
    try:
        return base64.b64decode(text, validate=False)
    except Exception as exc:
        raise SafeError("验证码图像解码失败") from exc


def extract_token(data: Any) -> str:
    candidates: List[Any] = []
    if isinstance(data, dict):
        candidates.append(data)
        nested = data.get("data")
        if isinstance(nested, dict):
            candidates.append(nested)
            content = nested.get("content")
            if isinstance(content, dict):
                candidates.append(content)
            elif isinstance(content, str):
                candidates.append({"token": content})
        content = data.get("content")
        if isinstance(content, dict):
            candidates.append(content)
    for item in candidates:
        for key in ("token", "access_token", "accessToken", "jktb_token", "wxfwdtToken"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise SafeError("响应未返回可用 token")


def extract_form_id(data: Any) -> str:
    keys = (
        "bdtbslid",
        "bdTbslId",
        "formId",
        "form_id",
        "id",
        "todayId",
        "todayid",
    )
    stack: List[Any] = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for key in keys:
                value = cur.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    text = str(value).strip()
                    # 过滤明显非表单 id 的短状态码
                    if key == "id" and text in {"0", "1", "-1"}:
                        continue
                    return text
            for value in cur.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(cur, list):
            stack.extend(cur)
    raise SafeError("未获取到当日健康表单编号")


def build_form_payload(account: Dict[str, str], today_id: str) -> Dict[str, Any]:
    today = datetime.today().strftime("%Y-%m-%d")
    return {
        "list": [
            {
                "zjlx": 3,
                "list": [
                    {"column": "c001", "content": "校内"},
                    {"column": "c002", "content": "校外"},
                ],
                "value": ["c001"],
            },
            {
                "zjlx": 5,
                "list": [
                    {"column": "gSheng", "content": account["province"]},
                    {"column": "gShi", "content": account["city"]},
                    {"column": "gQu", "content": account["district"]},
                ],
                "value": "",
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c010", "content": "37.2℃及以下"},
                    {
                        "column": "c012",
                        "content": "37.3℃-38.4℃（请及时就医并在3天内进行3次核酸检测）",
                    },
                    {
                        "column": "c013",
                        "content": "38.5℃及以上（请及时就医并在3天内进行3次核酸检测）",
                    },
                ],
                "value": ["c010"],
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c014", "content": "没有出现不适症状"},
                    {"column": "c015", "content": "乏力、咳嗽、流涕等感冒症状"},
                    {"column": "c016", "content": "呕吐、腹泻等消化道不适"},
                    {"column": "c017", "content": "与传染病无关的不适症状"},
                ],
                "value": ["c014"],
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c018", "content": "未被隔离"},
                    {
                        "column": "c019",
                        "content": "居家隔离观察（需要医护人员上门核酸采样）",
                    },
                    {"column": "c020", "content": "校外集中隔离点隔离观察"},
                ],
                "value": ["c018"],
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c003", "content": "未接种"},
                    {"column": "c004", "content": "已接种第一针"},
                    {"column": "c005", "content": "已接种第二针"},
                    {"column": "c006", "content": "已接种第三针"},
                ],
                "value": ["c006"],
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c007", "content": "绿码"},
                    {
                        "column": "c008",
                        "content": "灰码（请在到威海后第1、第2、第4天各完成1次核酸检测）",
                    },
                    {"column": "c009", "content": "黄码"},
                    {"column": "c010", "content": "红码"},
                ],
                "value": ["c007"],
            },
            {
                "zjlx": 3,
                "list": [
                    {"column": "c028", "content": "未出校"},
                    {
                        "column": "c029",
                        "content": "出校，未离开威海（须填报出行方式和外出地点）",
                    },
                    {"column": "c030", "content": "离威"},
                ],
                "value": ["c028"],
            },
            {"zjlx": 2, "list": [{"column": "c031", "content": ""}], "value": ""},
            {
                "zjlx": 3,
                "list": [
                    {"column": "c021", "content": "是"},
                    {"column": "c022", "content": "否"},
                ],
                "value": ["c022"],
            },
            {"zjlx": 1, "list": [{"column": "c023", "content": ""}], "value": ""},
            {
                "zjlx": 3,
                "list": [
                    {"column": "c024", "content": "是"},
                    {"column": "c025", "content": "否"},
                ],
                "value": ["c025"],
            },
            {"zjlx": 1, "list": [{"column": "c026", "content": ""}], "value": ""},
            {"zjlx": 2, "list": [{"column": "c027", "content": ""}], "value": ""},
        ],
        "isEdit": 1,
        "tbzt": 0,
        "syxgcs": 3,
        "tbrq": today,
        "mrtbjzsj": "22:10",
        "xm": account["xm"],
        "zzjgmc": account["xueyuan"],
        "bdtbslid": today_id,
        "bdmc": "学生每日健康填报",
    }


def obtain_session(account: Dict[str, str], timeout: int) -> str:
    query = urllib.parse.urlencode(
        {"openid": account["openid"], "dlfs": "zhmm"}
    )
    status, headers, _raw, _loc = http_request(
        "GET",
        BASE + "/sfrzwx/auth/login?" + query,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        allow_redirects=True,
    )
    if status >= 400:
        raise SafeError("获取会话失败，HTTP {}".format(status))
    set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return extract_cookie_pair(set_cookie)


def obtain_captcha(jid: str, timeout: int) -> str:
    status, _headers, raw, _loc = http_request(
        "POST",
        BASE + "/sfrzwx/wxsq/getYzm",
        headers={"User-Agent": USER_AGENT, "Cookie": jid},
        timeout=timeout,
    )
    if status >= 400:
        raise SafeError("获取验证码失败，HTTP {}".format(status))
    # 上游既可能返回 JSON，也可能是嵌套引号字符串
    try:
        payload = parse_json_bytes(raw)
        image = decode_captcha_payload(payload)
    except SafeError:
        text = read_limited(raw).decode("utf-8", errors="ignore")
        match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)", text)
        if not match:
            raise
        image = base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=False)
    code = recognize_captcha(image)
    return code


def login(account: Dict[str, str], jid: str, captcha: str, timeout: int) -> None:
    status, _headers, raw, _loc = http_request(
        "POST",
        BASE + "/sfrzwx/wx/login",
        headers={"User-Agent": USER_AGENT, "Cookie": jid},
        data={
            "openid": account["openid"],
            "dlfs": "zhmm",
            "sjschool": "",
            "sjh": "",
            "zhschool": account["school"],
            "username": account["username"],
            "password": account["password"],
            "code": captcha,
        },
        timeout=timeout,
    )
    if status >= 400:
        raise SafeError("登录请求失败，HTTP {}".format(status))
    # 登录接口可能返回非 JSON；后续授权失败再判定。若 JSON 明确失败则立即退出。
    try:
        payload = parse_json_bytes(raw)
    except SafeError:
        return
    msg = message_of(payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if any(hint in msg for hint in ("验证码", "密码", "用户", "失败", "错误")):
        if not any(hint in msg for hint in SUCCESS_HINTS):
            raise SafeError("登录未通过：{}".format(msg[:80] or "业务拒绝"))
    if code not in (None, 0, "0", 200, "200", True) and msg:
        if not any(hint in msg for hint in SUCCESS_HINTS):
            raise SafeError("登录未通过：{}".format(msg[:80]))


def oauth_code(
    path: str,
    cookie: str,
    timeout: int,
) -> str:
    status, headers, _raw, location = http_request(
        "GET",
        BASE + path,
        headers={"User-Agent": USER_AGENT, "Cookie": cookie},
        timeout=timeout,
        allow_redirects=False,
    )
    if location is None:
        location = headers.get("Location") or headers.get("location")
    if status not in {301, 302, 303, 307, 308} and not location:
        raise SafeError("OAuth 授权未返回跳转")
    return extract_query_code(location)


def login_by_code(api_path: str, cookie: str, code: str, timeout: int) -> str:
    status, _headers, raw, _loc = http_request(
        "POST",
        BASE + api_path,
        headers={"User-Agent": USER_AGENT, "Cookie": cookie},
        json_body={"code": code},
        timeout=timeout,
    )
    if status >= 400:
        raise SafeError("换取 token 失败，HTTP {}".format(status))
    payload = parse_json_bytes(raw)
    return extract_token(payload)


def fetch_today_form_id(cookie: str, timeout: int) -> Tuple[str, str]:
    status, _headers, raw, _loc = http_request(
        "POST",
        BASE + "/jktb-api/jktb_01_01/homePage/getToadyForms",
        headers={"User-Agent": USER_AGENT, "Cookie": cookie},
        timeout=timeout,
    )
    if status >= 400:
        raise SafeError("获取当日表单失败，HTTP {}".format(status))
    payload = parse_json_bytes(raw)
    msg = message_of(payload)
    if any(hint in msg for hint in ALREADY_HINTS):
        return "", "alreadyComplete"
    form_id = extract_form_id(payload)
    return form_id, "ok"


def submit_form(
    account: Dict[str, str], cookie: str, today_id: str, timeout: int
) -> str:
    status, _headers, raw, _loc = http_request(
        "POST",
        BASE + "/jktb-api/jktb_01_01/homePage/saveForm",
        headers={"User-Agent": USER_AGENT, "Cookie": cookie},
        json_body=build_form_payload(account, today_id),
        timeout=timeout,
    )
    if status >= 400:
        raise SafeError("提交健康表单失败，HTTP {}".format(status))
    payload = parse_json_bytes(raw)
    outcome = classify_business(payload, http_ok=True)
    if outcome == "failure":
        msg = message_of(payload) or "业务未确认成功"
        raise SafeError("填报未确认成功：{}".format(msg[:80]))
    return outcome


def run_live_flow(
    account: Dict[str, str], timeout: int, max_retries: int
) -> Tuple[str, str]:
    last_error = "填报失败"
    for attempt in range(1, max_retries + 1):
        try:
            log("尝试 {}/{}：获取会话".format(attempt, max_retries))
            jid = obtain_session(account, timeout)
            log("{} 会话已建立".format(ICONS["success"]))
            log("尝试 {}/{}：识别验证码并登录".format(attempt, max_retries))
            captcha = obtain_captcha(jid, timeout)
            login(account, jid, captcha, timeout)
            log("{} 登录请求已提交".format(ICONS["success"]))
            code1 = oauth_code(
                "/sfrzwx/oauth/authorize?response_type=code&scope=read"
                "&client_id=wxfwdt&redirect_uri=http://xy.4009955.com/wxfwdt/"
                "&state=tysfrz",
                jid,
                timeout,
            )
            wx_token = login_by_code(
                "/wxfwdt-api/layout_01_01/login/loginYdBycode",
                jid,
                code1,
                timeout,
            )
            # 保留上游写法：原始 jid 片段 + token
            cookie_wx = "{};wxfwdtToken={}".format(jid, wx_token)
            code2 = oauth_code(
                "/sfrzwx/oauth/authorize?response_type=code&scope=read"
                "&client_id=jktb&redirect_uri=http://xy.4009955.com/jktb/"
                "&state=tysfrz",
                cookie_wx,
                timeout,
            )
            jk_token = login_by_code(
                "/jktb-api/jktb_01_01/login/loginYdBycode",
                cookie_wx,
                code2,
                timeout,
            )
            cookie_jk = "{};wxfwdtToken={};jktb_token={}".format(
                jid, wx_token, jk_token
            )
            today_id, state = fetch_today_form_id(cookie_jk, timeout)
            if state == "alreadyComplete":
                return "alreadyComplete", "今日已填报"
            cookie_submit = "{};jktb_token={}".format(jid, jk_token)
            outcome = submit_form(account, cookie_submit, today_id, timeout)
            if outcome == "alreadyComplete":
                return "alreadyComplete", "今日已填报"
            return "success", "健康填报成功"
        except SafeError as exc:
            last_error = str(exc)
            log(
                "{} 第{}次未成功：{}".format(
                    ICONS["warning"], attempt, last_error
                )
            )
            if attempt < max_retries:
                time.sleep(min(2 * attempt, 8))
                continue
        except Exception:
            last_error = "网络、超时或响应处理失败"
            log("{} 第{}次异常：{}".format(ICONS["warning"], attempt, last_error))
            if attempt < max_retries:
                time.sleep(min(2 * attempt, 8))
                continue
    return "failure", last_error


def script_selectors() -> List[str]:
    script = Path(__file__).resolve()
    return [
        CATALOG_ID,
        script.name,
        "candidate.py",
        "grxy_health_form.py",
        "output/candidate.py",
        "scripts/grxy_health_form.py",
        script.as_posix(),
    ]


def notification_selected() -> bool:
    switch = os.getenv("QINGLONG_NOTIFY", "auto").strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selected = os.getenv("QINGLONG_NOTIFY_SCRIPTS")
    if selected is None:
        return False
    stripped = selected.strip()
    if stripped == "":
        return False
    if stripped == "*":
        return True
    patterns = [part for part in re.split(r"[,;\s]+", stripped) if part]
    choices = script_selectors()
    return any(
        fnmatch.fnmatchcase(choice, pattern)
        for pattern in patterns
        for choice in choices
    )


def discover_notify_paths() -> Tuple[List[Path], List[Path]]:
    dirs: List[Path] = []
    custom = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom:
        dirs.append(Path(custom))
    dirs.extend([Path("/ql/data/scripts"), Path("/ql/scripts")])
    return [d / "notify.py" for d in dirs], [d / "sendNotify.js" for d in dirs]


def send_via_python(title: str, body: str, paths: List[Path]) -> bool:
    try:
        module = importlib.import_module("notify")
        sender = getattr(module, "send", None)
        if callable(sender):
            sender(title, body)
            return True
    except Exception:
        pass
    for path in paths:
        try:
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                "qinglong_grxy_notify", path
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sender = getattr(module, "send", None)
            if callable(sender):
                sender(title, body)
                return True
        except Exception:
            continue
    return False


def send_via_node(title: str, body: str, paths: List[Path]) -> bool:
    from shutil import which

    node = which("node") or which("nodejs")
    if not node:
        return False
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    worker = (
        "const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));"
        "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body))"
        ".then(r=>process.exit(r===false?1:0)).catch(()=>process.exit(1));"
    )
    for path in paths:
        if not path.is_file():
            continue
        try:
            completed = subprocess.run(
                [node, "-e", worker, str(path.resolve())],
                input=payload,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0:
                return True
        except Exception:
            continue
    return False


def notify(summary: str, dry_run: bool) -> str:
    if not notification_selected():
        log("{} 通知：未启用或未命中通知名单".format(ICONS["skipped"]))
        return "disabled"
    if dry_run:
        log("{} 通知预演：{}".format(ICONS["skipped"], summary))
        return "dry-run"
    py_paths, js_paths = discover_notify_paths()
    try:
        if send_via_python(TITLE, summary, py_paths):
            log("{} 通知已通过 notify.py 发送".format(ICONS["success"]))
            return "sent"
        if send_via_node(TITLE, summary, js_paths):
            log("{} 通知已通过 sendNotify.js 发送".format(ICONS["success"]))
            return "sent"
        log("{} 通知工具不可用；保留业务退出码".format(ICONS["warning"]))
        return "unavailable"
    except Exception:
        log("{} 通知发送失败；保留业务退出码".format(ICONS["warning"]))
        return "failed"


def process_account(
    index: int,
    total: int,
    raw_line: str,
    dry_run: bool,
    timeout: int,
    max_retries: int,
) -> Dict[str, Any]:
    started = time.monotonic()
    result: Dict[str, Any] = {
        "account": index,
        "ok": False,
        "status": "failure",
        "identity": None,
        "message": "",
        "elapsedSeconds": 0.0,
        "tasks": {
            "total": 1,
            "success": 0,
            "alreadyComplete": 0,
            "skipped": 0,
            "failure": 0,
        },
    }
    log("---------- 账号 {}/{} ----------".format(index, total))

    stage1 = time.monotonic()
    log("账号 {} / 阶段 1 参数检查".format(index))
    try:
        account = parse_account_line(raw_line, index)
        if len(account["openid"]) < 6:
            raise SafeError("openid 长度异常")
        identity = account["xm"]
        result["identity"] = identity
        log("账号 {} 公开身份：{}".format(index, identity))
        log(
            "{} 参数检查通过（学校={}，学院={}）；阶段 1 耗时 {:.2f}秒".format(
                ICONS["success"],
                account["school"],
                account["xueyuan"],
                time.monotonic() - stage1,
            )
        )
    except SafeError as exc:
        log("{} {}".format(ICONS["failure"], exc))
        result["message"] = str(exc)
        result["tasks"]["failure"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - started, 3)
        log(
            "账号 {} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1，耗时 {:.2f}秒".format(
                index, result["elapsedSeconds"]
            )
        )
        return result
    identity = account["xm"]

    if dry_run:
        stage2 = time.monotonic()
        log("账号 {} / 阶段 2 登录与验证码（预演）".format(index))
        log("{} DRY_RUN_OK：已预演会话/验证码/登录，未发送请求".format(ICONS["skipped"]))
        log("阶段 2 耗时 {:.2f}秒".format(time.monotonic() - stage2))
        stage3 = time.monotonic()
        log("账号 {} / 阶段 3 拉取表单并提交（预演）".format(index))
        log(
            "{} DRY_RUN_OK：已预演健康填报提交，未发送请求、无副作用".format(
                ICONS["skipped"]
            )
        )
        log("阶段 3 耗时 {:.2f}秒".format(time.monotonic() - stage3))
        result.update(ok=True, status="skipped", message="DRY_RUN_OK")
        result["tasks"]["skipped"] = 1
        result["elapsedSeconds"] = round(time.monotonic() - started, 3)
        log(
            "账号 {}（{}）统计：总任务 1，成功 0，已完成 0，跳过 1，失败 0，耗时 {:.2f}秒".format(
                index, identity, result["elapsedSeconds"]
            )
        )
        return result

    stage2 = time.monotonic()
    log(
        "账号 {} / 阶段 2-3 登录授权并提交健康填报（最多 {} 次）".format(
            index, max_retries
        )
    )
    status, message = run_live_flow(account, timeout, max_retries)
    icon = ICONS.get(status, ICONS["failure"])
    log(
        "{} {}；阶段耗时 {:.2f}秒".format(
            icon, message, time.monotonic() - stage2
        )
    )
    result["message"] = message
    result["status"] = status
    result["ok"] = status in {"success", "alreadyComplete"}
    if status == "success":
        result["tasks"]["success"] = 1
    elif status == "alreadyComplete":
        result["tasks"]["alreadyComplete"] = 1
    else:
        result["tasks"]["failure"] = 1
    result["elapsedSeconds"] = round(time.monotonic() - started, 3)
    log(
        "账号 {}（{}）统计：总任务 1，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}秒".format(
            index,
            identity,
            result["tasks"]["success"],
            result["tasks"]["alreadyComplete"],
            result["tasks"]["skipped"],
            result["tasks"]["failure"],
            result["elapsedSeconds"],
        )
    )
    return result


def main() -> int:
    started = time.monotonic()
    dry_run = env_flag("GRXY_DRY_RUN", "0")
    config_error = False
    config_message = ""
    timeout = DEFAULT_TIMEOUT
    max_retries = DEFAULT_RETRIES
    account_lines: List[str] = []
    try:
        timeout = env_int("GRXY_TIMEOUT", DEFAULT_TIMEOUT, 5, 60)
        max_retries = env_int("GRXY_MAX_RETRIES", DEFAULT_RETRIES, 1, 10)
        account_lines = load_account_lines()
        if not account_lines:
            config_error = True
            config_message = (
                "缺少 GRXY_ACCOUNTS；每个非空行填写 "
                "学号|密码|学校|openid|姓名|学院|省|市|区"
            )
    except SafeError as exc:
        config_error = True
        config_message = str(exc)

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；模式：{}；账号数：{}".format(
            clock(),
            "断网预演" if dry_run else "正式运行",
            len(account_lines),
        )
    )
    if config_error:
        log("{} 阶段 1 参数检查：{}".format(ICONS["failure"], config_message))

    results: List[Dict[str, Any]] = []
    if not config_error:
        for index, raw_line in enumerate(account_lines, 1):
            results.append(
                process_account(
                    index,
                    len(account_lines),
                    raw_line,
                    dry_run,
                    timeout,
                    max_retries,
                )
            )

    success = sum(1 for item in results if item["status"] == "success")
    already = sum(1 for item in results if item["status"] == "alreadyComplete")
    skipped = sum(1 for item in results if item["status"] == "skipped")
    failure = sum(1 for item in results if item["status"] == "failure")
    passed = sum(1 for item in results if item["ok"])
    failed_accounts = len(results) - passed
    exit_code = 1 if config_error or failed_accounts > 0 or not account_lines else 0
    if config_error:
        final_status = "configuration-error"
    elif dry_run and exit_code == 0:
        final_status = "dry-run"
    elif exit_code == 0:
        final_status = "success"
    elif passed > 0 and failed_accounts > 0:
        final_status = "partial-failure"
    else:
        final_status = "failure"

    body = "账号总数 {}，成功 {}，已完成 {}，跳过 {}，失败 {}；状态 {}".format(
        len(account_lines), success, already, skipped, failure, final_status
    )
    if config_error:
        body += "。配置错误：{}".format(config_message)
    if dry_run:
        body += "。断网预演，未进行真实填报"
    notification = notify(body, dry_run)

    log("----------------------------------------")
    log("任务统计：" + body)
    log(
        "子任务统计：成功 {}，已完成 {}，跳过 {}，失败 {}；通知状态：{}".format(
            success, already, skipped, failure, notification
        )
    )
    log(
        "完成时间：{}；总耗时 {:.2f}秒；最终状态：{}；退出码 {}".format(
            clock(), time.monotonic() - started, final_status, exit_code
        )
    )
    summary = {
        "applicationKey": APPLICATION_KEY,
        "task": TITLE,
        "catalogId": CATALOG_ID,
        "mode": "dry-run" if dry_run else "live",
        "status": final_status,
        "accounts": len(account_lines),
        "success": success,
        "alreadyComplete": already,
        "skipped": skipped,
        "failure": failure,
        "passedAccounts": passed,
        "failedAccounts": failed_accounts,
        "configurationError": config_error,
        "dryRun": dry_run,
        "notification": notification,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "exitCode": exit_code,
        "results": [
            {
                "account": item["account"],
                "ok": item["ok"],
                "status": item["status"],
                "identity": item["identity"],
                "elapsedSeconds": item["elapsedSeconds"],
                "tasks": item["tasks"],
            }
            for item in results
        ],
    }
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
