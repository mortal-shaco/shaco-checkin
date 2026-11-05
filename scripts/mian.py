#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: HDSky签到
# cron: 20 9 * * *
#
# 来源：xxlgenius/hdsky-auto-sign-in mian.py（MIT）
# https://github.com/xxlgenius/hdsky-auto-sign-in
# 提交：643376edc2e6914ebc1f575edf4c5d0f8b2c9913
# 相关：config.py、captchaparse.py 及 app/captcha/split/templates
# SPDX-License-Identifier: MIT
#
# MIT License
# Copyright (c) 2024 xxlgenius
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
#
"""HDSky（hdsky.me）每日签到 - 青龙维护版。

功能清点（相对上游 mian.py / config.py / captchaparse.py）：
- 使用已登录 Cookie 访问首页核验登录态（发生登录重定向视为失败）
- 请求 image_code_ajax.php 获取验证码 imagehash，再下载验证码图片
- 使用内嵌字符模板 + OpenCV 模板匹配识别验证码（准确率沿用上游算法）
- POST showup.php 提交 action=showup&imagehash&imagestring 完成签到
- 业务成功：JSON success=true；今日已签到：message=date_unmatch
- 页面返回公开用户名或 UID 时直接展示以便核对账号
- 移除本地 config.json / cookies.json、任意 server_host Webhook 推送、
  临时验证码切图落盘、验证码明文打印与无超时请求
- 增加逐行多账号、HDSKY_DRY_RUN 断网预演、请求超时、时间轴日志、
  青龙通知与 TASK_SUMMARY

HDSKY_COOKIE：每个非空行一个已登录 Cookie（保留分号分隔的键值对），
或一行 JSON 对象（含 c_secure_* 字段，兼容上游 config.json）。
兼容别名 HDSKY_COOKIES（仅当规范变量为空时生效）。
HDSKY_TIMEOUT：单次 HTTPS 请求超时秒数，默认 20，范围 5..60。
HDSKY_CAPTCHA_RETRIES：验证码识别/签到重试次数，默认 3，范围 1..5。
HDSKY_DRY_RUN=1：完全断网预演，只校验配置与流程，不发起网络请求。
建议 Cron：20 9 * * *。不打印 Cookie、Token、会话值、验证码或原始响应。
运行依赖：opencv-python-headless、numpy（仅真实签到识别验证码时加载）。
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
            "71c961d59b5546a3",
            "scripts/hdsky_sign.py",
            "hdsky_sign.py",
            "candidate.py",
            "mian.py",
            "hdsky",
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
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TITLE = "HDSky签到"
CATALOG_ID = "71c961d59b5546a3"
HOST = "hdsky.me"
BASE = "https://hdsky.me/"
LOGIN_URL = BASE + "index.php"
IMAGE_CODE_URL = BASE + "image_code_ajax.php"
SHOWUP_URL = BASE + "showup.php"
IMAGE_URL_TMPL = BASE + "image.php?action=regimage&imagehash={}"
DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 3
MAX_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 512 * 1024
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# 上游 app/captcha/split/templates 内嵌副本（MIT，Copyright (c) 2024 xxlgenius）
CAPTCHA_TEMPLATES_B64: Dict[str, str] = {
    "1": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAMCAAAAAB69aNBAAAAKUlEQVQIHS3BgQkAMBADIW//oVMKrzlhIkZkiDARJsJEmAgTYSLzlfMAKS0KDUVLBBAAAAAASUVORK5CYII=",
    "2": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAL0lEQVQIHT3BgQ2AMAAEIW7/oV9rEyG/MERMJpkw5ZrymeSYyGtCmLxicmSu8nsAZOsMDUIiHvkAAAAASUVORK5CYII=",
    "3": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BgQnAMAAEIW//ob+hgWiemCMyMck15TfJMSK/Sa4p15SJScwReT4a7AwNgC5vpAAAAABJRU5ErkJggg==",
    "4": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAIAAADUCbv3AAAATUlEQVQYGX3BAQqDQAAEscz/H70tgmC5YpJXOWxDhfza5lIhD9vcKuS2DdU2VMhlGypsQ4WwDZXLNlQI2/zTl8M2VMhhGyrksA0V8uoD8U8nDbEi5JwAAAAASUVORK5CYII=",
    "5": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALUlEQVQIHT3BgQkAIAAEIW//oT8oSPNlrmRyZXJlGpGRSZ4pz5QJU0wmYYh8B4LmDg3Vwwl5AAAAAElFTkSuQmCC",
    "6": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BsQ0AMBDEILz/0BcpxUNOGCImk0xYMvkyjcjIJBOmTJhiMglD5Dxm8xENhW/BxwAAAABJRU5ErkJggg==",
    "7": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BgQ2AMAAEIW7/oV9tEyG/zFWuKdeUY5LPRF4TwuQVk08mRyZHfg+f4goN9ibfsAAAAABJRU5ErkJggg==",
    "8": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALElEQVQIHT3BsQEAAAjDIPL/0XUT8sIQMZlkwhSTSRgiJpNMmDJhiskkDJF3a/IRDRR4OxQAAAAASUVORK5CYII=",
    "9": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BsQ0AMBDEILz/0Jci0kNOGCImk0yYMmGKySiMpnxTLEwxmYQhch568xENX17gLwAAAABJRU5ErkJggg==",
    "a": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BgQkAIAAEIW//ob8gSPPlmhCGiMkkE6ZMmDJhyjxlwpQJUyZM+Q4q8BENV4dY2AAAAABJRU5ErkJggg==",
    "b": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BwQ0AMBDDILz/0KnuU8iXOZGJSSZMmZhkTmRikglTJkyZmGRO5Ht17BEN4Hf+CwAAAABJRU5ErkJggg==",
    "c": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAL0lEQVQIHT3BsRHAMBAEIbb/os8/Cgz5hTmJiSmTszJ5MnkyeTJ5MjkrJqYwJ/l9sOsODU30IYUAAAAASUVORK5CYII=",
    "d": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAL0lEQVQIHT3BwQ0AMBDDILz/0KnuU8iXOZGJSSZMmTBlwpQJUyZMmTBlYpI5ke8BuO4SDVDu5KsAAAAASUVORK5CYII=",
    "e": "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAMCAAAAACVN8h/AAAALElEQVQIHTXBgQnAQBAEIaf/ojfcQzS/zFMmJ5OTycmcZHIyOZmcTE7mKb8PeYAKDbqxE+MAAAAASUVORK5CYII=",
    "f": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALUlEQVQIHT3BgQmAABADsdz+Q1d8wSS/zKdMTiYnk5N5RSYnk5PJyeRkcvJ7ALreCg3oSX+GAAAAAElFTkSuQmCC",
    "g": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BwQ0AIADEILr/0KfxIeQLcyUmpkyeTJ5MnkyMMmHKhCkmpjBX8h3B5g8NYaKEDgAAAABJRU5ErkJggg==",
    "h": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAL0lEQVQIHT3BsQ0AMBDEILz/0Jci0kNOJkyZMGXClAlT5isTpkyYMmHKhCkTppwH8O4TDdPfL+oAAAAASUVORK5CYII=",
    "m": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAMElEQVQIHT3BsQ0AMBDEILz/0Jci0kNOJkwZGWW+Mk1TpmnKNE2ZMGXClAlTJkw5D7P1Fg2oFpLOAAAAAElFTkSuQmCC",
    "n": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALklEQVQIHT3BsQEAAAjDIPL/0XUT8jJhyogpQ6YMmTJNU6ZpymQoE6NMjDJhyju+9BYN9prHNQAAAABJRU5ErkJggg==",
    "p": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAALUlEQVQIHT3BsQ0AMBDEILz/0Bfpi0C+zEkmTJkwZcKUOcnkZHIyOZmcTE6+B8vnDQ140a2CAAAAAElFTkSuQmCC",
    "r": "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAMCAAAAAB+AHN8AAAAL0lEQVQIHT3BwQ0AIADEILr/0KfxIeTLPMmEKROmTJgyTzJXyGQiE5NMmDJhyncASOsRDSqmVXwAAAAASUVORK5CYII="
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(text: str) -> None:
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value or "")).split())


def resolve_timeout() -> float:
    raw = env("HDSKY_TIMEOUT")
    if not raw:
        return float(DEFAULT_TIMEOUT)
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafeError("HDSKY_TIMEOUT 须为数字秒数") from exc
    if value < 5 or value > 60:
        raise SafeError("HDSKY_TIMEOUT 须在 5 到 60 秒之间")
    return value


def resolve_retries() -> int:
    raw = env("HDSKY_CAPTCHA_RETRIES")
    if not raw:
        return DEFAULT_RETRIES
    try:
        value = int(raw)
    except ValueError as exc:
        raise SafeError("HDSKY_CAPTCHA_RETRIES 须为整数") from exc
    if value < 1 or value > 5:
        raise SafeError("HDSKY_CAPTCHA_RETRIES 须在 1 到 5 之间")
    return value


def cookie_header_from_mapping(data: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key, value in data.items():
        name = str(key).strip()
        if not name:
            continue
        parts.append("{}={}".format(name, "" if value is None else str(value)))
    return "; ".join(parts)


def normalize_cookie_line(line: str) -> str:
    text = line.strip()
    if not text:
        raise SafeError("Cookie 为空")
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SafeError("Cookie JSON 无法解析") from exc
        if not isinstance(payload, dict):
            raise SafeError("Cookie JSON 须为对象")
        cookies = payload.get("cookies", payload)
        if not isinstance(cookies, dict) or not cookies:
            raise SafeError("Cookie JSON 缺少 cookies 对象或键值")
        text = cookie_header_from_mapping(cookies)
    if "=" not in text:
        raise SafeError("Cookie 格式错误：缺少键值对")
    if any(ord(ch) < 32 or ord(ch) > 255 for ch in text):
        raise SafeError("Cookie 含非法控制字符或非 Latin-1 字节")
    lower = text.lower()
    if "c_secure_" not in lower:
        raise SafeError("Cookie 缺少 HDSky/NexusPHP 常见 c_secure_* 字段，请检查是否复制完整")
    return text


def load_accounts() -> List[str]:
    raw = env("HDSKY_COOKIE")
    source = "HDSKY_COOKIE"
    if not raw:
        raw = env("HDSKY_COOKIES")
        if raw:
            source = "HDSKY_COOKIES"
    if not raw:
        raise SafeError(
            "未配置凭据：请设置 HDSKY_COOKIE（每行一个 Cookie 或 JSON）；"
            "兼容别名 HDSKY_COOKIES"
        )
    accounts: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        accounts.append(normalize_cookie_line(text))
    if not accounts:
        raise SafeError("{} 中没有有效账号行".format(source))
    return accounts


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.netloc.lower() != HOST:
            raise SafeError("拒绝跨站或不安全重定向")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class Client:
    def __init__(self, cookie: str, timeout: float) -> None:
        self.cookie = cookie
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            SameHostRedirect(),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )
        self.no_redirect = urllib.request.build_opener(
            NoRedirect(),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": LOGIN_URL,
            "Cookie": self.cookie,
        }
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        url: str,
        data: Optional[bytes] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        allow_redirect: bool = True,
        expect_json: bool = False,
        binary: bool = False,
        max_bytes: int = MAX_BYTES,
    ) -> Tuple[int, Any, bool]:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() != HOST:
            raise SafeError("拒绝访问非目标站点地址")
        request = urllib.request.Request(
            url,
            data=data,
            headers=self._headers(extra_headers),
            method=method.upper(),
        )
        opener = self.opener if allow_redirect else self.no_redirect
        redirected = False
        try:
            with opener.open(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", None) or response.getcode())
                final = urllib.parse.urlsplit(response.geturl())
                if final.netloc.lower() != HOST:
                    raise SafeError("响应落到非目标站点")
                if final.path.rstrip("/").endswith("login") or "login.php" in final.path:
                    redirected = True
                payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise SafeError("响应过大")
                if binary:
                    return status, payload, redirected
                charset = response.headers.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if expect_json:
                    try:
                        return status, json.loads(text), redirected
                    except json.JSONDecodeError as exc:
                        raise SafeError("接口未返回可解析 JSON") from exc
                return status, text, redirected
        except SafeError:
            raise
        except urllib.error.HTTPError as exc:
            if not allow_redirect and exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location", "")
                target = urllib.parse.urlsplit(urllib.parse.urljoin(url, location))
                if "login" in target.path.lower():
                    return int(exc.code), "", True
                raise SafeError("登录态校验出现意外重定向") from exc
            raise SafeError("HTTP 请求失败（状态 {}）".format(exc.code)) from exc
        except urllib.error.URLError as exc:
            raise SafeError("网络请求失败") from exc
        except Exception as exc:
            raise SafeError("请求过程异常") from exc


def extract_identity(page: str) -> Optional[str]:
    patterns = [
        r'userdetails\.php\?id=(\d+)[^>]*>\s*([^<]{1,64})\s*<',
        r'欢迎[，, ]*([^<>\r\n]{1,64})',
        r'id=["\']info_block["\'][\s\S]{0,1200}?userdetails\.php\?id=(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, re.I)
        if not match:
            continue
        if match.lastindex and match.lastindex >= 2:
            name = plain(match.group(2))
            uid = match.group(1)
            if name and not re.search(r"cookie|token|pass|session", name, re.I):
                return name
            if uid:
                return "UID:" + uid
        elif match.lastindex == 1:
            value = plain(match.group(1))
            if value.isdigit():
                return "UID:" + value
            if value and not re.search(r"cookie|token|pass|session", value, re.I):
                return value[:64]
    return None


def load_cv() -> Tuple[Any, Any]:
    try:
        import cv2 as cv  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        raise SafeError(
            "缺少运行依赖 opencv-python-headless / numpy，无法识别验证码"
        ) from exc
    return cv, np


def _template_score(cv: Any, img: Any, tmp: Any) -> float:
    if img is None or tmp is None:
        return 0.0
    if img.shape[0] < tmp.shape[0] or img.shape[1] < tmp.shape[1]:
        return 0.0
    result = cv.matchTemplate(img, tmp, cv.TM_CCOEFF)
    _min_val, max_val, _min_loc, _max_loc = cv.minMaxLoc(result)
    return float(max_val)


def _decode_templates(cv: Any, np: Any) -> Dict[str, Any]:
    loaded: Dict[str, Any] = {}
    for name, encoded in CAPTCHA_TEMPLATES_B64.items():
        raw = base64.b64decode(encoded)
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv.imdecode(arr, cv.IMREAD_COLOR)
        if image is None:
            raise SafeError("内嵌验证码模板损坏")
        loaded[name] = image
    return loaded


def recognize_captcha(image_data: bytes) -> str:
    """移植上游 captchaparse.binary_captchar，改为内存识别、禁止落盘。"""
    cv, np = load_cv()
    templates = _decode_templates(cv, np)
    arr = np.asarray(bytearray(image_data), dtype="uint8")
    img = cv.imdecode(arr, cv.IMREAD_GRAYSCALE)
    if img is None:
        raise SafeError("验证码图片解码失败")

    _ret, dst = cv.threshold(img, 10, 255, cv.THRESH_BINARY)
    dst = 255 - dst
    _ret, labels = cv.connectedComponents(dst)
    unique, counts = np.unique(labels, return_counts=True)
    labels_counts = dict(zip(unique.tolist(), counts.tolist()))
    _ret, bimg = cv.threshold(img, 127, 255, cv.THRESH_BINARY)
    for i in range(img.shape[0]):
        for j in range(img.shape[1]):
            count = labels_counts.get(int(labels[i, j]), 0)
            bimg[i, j] = 0 if count < 10 or count > 80 else 255

    contours, _hierarchy = cv.findContours(
        bimg, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE
    )
    rects = [cv.minAreaRect(cnt) for cnt in contours]
    boxes = [np.int0(cv.boxPoints(box)) for box in rects]
    leftset = set()
    for box in boxes:
        leftset.add(min(int(point[0]) for point in box))
    left_list = sorted(leftset)

    captcha = ""
    for left in left_list:
        for box in boxes:
            xs = [int(point[0]) for point in box]
            ys = [int(point[1]) for point in box]
            x1 = min(xs)
            if x1 != left:
                continue
            x2 = max(xs)
            y1 = min(ys)
            y2 = max(ys)
            height = y2 - y1
            width = x2 - x1
            y_start = max(0, y1 - 1)
            x_start = max(0, x1 - 1)
            crop = bimg[y_start : y1 + height + 2, x_start : x1 + width + 2]
            if crop.size == 0:
                continue
            crop_bgr = cv.cvtColor(crop, cv.COLOR_GRAY2BGR)
            scores = {
                name: _template_score(cv, crop_bgr, tmp)
                for name, tmp in templates.items()
            }
            best = max(scores, key=scores.get)
            captcha += best
            break
    if not captcha:
        raise SafeError("验证码识别结果为空")
    return captcha.upper()


def notification_enabled() -> Tuple[bool, str]:
    switch = env("QINGLONG_NOTIFY", "auto").lower() or "auto"
    if switch in FALSE_VALUES:
        return False, "全局通知已关闭"
    if switch in TRUE_VALUES:
        return True, "全局通知已启用"
    if switch != "auto":
        return False, "通知开关无效，仅允许 auto 或布尔值"
    selectors = re.split(r"[,;\s]+", env("QINGLONG_NOTIFY_SCRIPTS"))
    script = Path(__file__).resolve()
    identities = {
        CATALOG_ID,
        script.name,
        "hdsky_sign.py",
        "candidate.py",
        "mian.py",
        "scripts/hdsky_sign.py",
        "hdsky",
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


def notify(body: str, dry_run: bool) -> str:
    enabled, reason = notification_enabled()
    if not enabled:
        log("通知：⏭️ " + reason)
        return "disabled"
    if dry_run:
        log("通知：⏭️ 断网预演禁止执行可能联网的通知模块；摘要已生成")
        return "dry-run-skipped"
    paths: List[Path] = []
    directory = env("QINGLONG_NOTIFY_DIR")
    if directory:
        paths.append(Path(directory).expanduser() / "notify.py")
    paths.extend(
        [
            Path("/ql/data/scripts/notify.py"),
            Path("/ql/scripts/notify.py"),
        ]
    )
    try:
        module = None
        try:
            import notify as imported  # type: ignore

            module = imported
        except Exception:
            module = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location(
                        "qinglong_notify", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    module = candidate
                    break
        if module is not None and callable(getattr(module, "send", None)):
            outcome: List[bool] = []

            def deliver() -> None:
                try:
                    module.send(TITLE, body)
                    outcome.append(True)
                except Exception:
                    outcome.append(False)

            worker = threading.Thread(target=deliver, daemon=True)
            worker.start()
            worker.join(20)
            if outcome and outcome[0]:
                log("通知：✅ 脱敏总结已交给青龙 notify.py")
                return "sent"
            log("通知：⚠️ 投递失败或超时；保留业务退出码")
            return "unavailable-or-failed"
        node = shutil.which("node")
        if node:
            for path in paths:
                js_path = path.with_name("sendNotify.js")
                if not js_path.is_file():
                    continue
                result = subprocess.run(
                    [
                        node,
                        "-e",
                        "Promise.resolve(require(process.argv[1]).sendNotify("
                        "process.argv[2],process.argv[3])).catch(()=>process.exit(1))",
                        str(js_path),
                        TITLE,
                        body,
                    ],
                    timeout=20,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    log("通知：✅ 脱敏总结已交给青龙 sendNotify.js")
                    return "sent"
        log("通知：⚠️ 青龙适配器不可用；保留业务退出码")
        return "unavailable-or-failed"
    except Exception:
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
        return "unavailable-or-failed"


class AccountResult:
    def __init__(self, number: int) -> None:
        self.number = number
        self.status = "failure"
        self.identity = "账号{}".format(number)
        self.stats = {key: 0 for key in STATES}
        self.started = time.monotonic()
        self.message = ""


def sign_once(client: Client) -> Tuple[str, str]:
    """返回 (status, message)；status in success|alreadyComplete|failure。"""
    status, payload, _redir = client.request(
        "POST",
        IMAGE_CODE_URL,
        data=b"action=new",
        extra_headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        expect_json=True,
    )
    if status != 200 or not isinstance(payload, dict):
        raise SafeError("获取验证码哈希失败")
    if not payload.get("success", False):
        raise SafeError("站点未返回可用验证码哈希")
    image_hash = str(payload.get("code") or "").strip()
    if not image_hash or not re.fullmatch(r"[0-9a-fA-F]+", image_hash):
        raise SafeError("验证码哈希格式异常")

    img_status, image_data, _ = client.request(
        "GET",
        IMAGE_URL_TMPL.format(image_hash),
        binary=True,
        max_bytes=MAX_IMAGE_BYTES,
    )
    if img_status != 200 or not isinstance(image_data, (bytes, bytearray)):
        raise SafeError("下载验证码图片失败")
    code = recognize_captcha(bytes(image_data))
    if not re.fullmatch(r"[0-9A-Z]+", code):
        raise SafeError("验证码识别结果格式异常")

    body = urllib.parse.urlencode(
        {
            "action": "showup",
            "imagehash": image_hash,
            "imagestring": code,
        }
    ).encode("utf-8")
    sign_status, sign_payload, _ = client.request(
        "POST",
        SHOWUP_URL,
        data=body,
        extra_headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        expect_json=True,
    )
    if sign_status != 200 or not isinstance(sign_payload, dict):
        raise SafeError("签到接口响应异常")
    if sign_payload.get("success", False) is True:
        return "success", "签到成功"
    message = str(sign_payload.get("message") or "").strip()
    if message == "date_unmatch":
        return "alreadyComplete", "今日已经签到"
    # 不回传站点原始 message 全文，仅给出脱敏分类
    if message:
        raise SafeError("签到未成功（业务码已记录为失败）")
    raise SafeError("签到未成功且无业务消息")


def run_account(
    result: AccountResult,
    cookie: str,
    timeout: float,
    retries: int,
    dry_run: bool,
) -> None:
    stages = [
        (1, "核验登录态与账号身份"),
        (2, "获取验证码并提交签到"),
    ]
    total_stages = len(stages)
    log(
        "账号 {}：开始处理（身份待核验）；子任务 {} 项".format(
            result.number, total_stages
        )
    )
    client: Optional[Client] = None
    for index, name in stages:
        tick = time.monotonic()
        log("账号 {} 阶段 {}/{}：{}".format(result.number, index, total_stages, name))
        if dry_run:
            result.stats["skipped"] += 1
            log(
                "{} 参数及流程有效，未发送请求；耗时 {:.2f} 秒".format(
                    ICONS["skipped"], time.monotonic() - tick
                )
            )
            continue
        try:
            if index == 1:
                client = Client(cookie, timeout)
                status, page, redirected = client.request(
                    "GET", LOGIN_URL, allow_redirect=False
                )
                if redirected or status in {301, 302, 303, 307, 308}:
                    raise SafeError("登录失败：请求被重定向到登录页，请更新 Cookie")
                if status != 200 or not isinstance(page, str):
                    raise SafeError("首页访问失败")
                # 再允许跟随站内跳转读取身份
                _status2, page2, redirected2 = client.request("GET", LOGIN_URL)
                if redirected2:
                    raise SafeError("登录失败：会话无效")
                identity_page = page2 if isinstance(page2, str) else page
                nickname = extract_identity(identity_page)
                if nickname:
                    result.identity = nickname
                    log("账号 {} 公开身份：{}".format(result.number, nickname))
                else:
                    log("账号 {}：页面未返回公开身份，使用序号标识".format(result.number))
                result.stats["success"] += 1
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"], time.monotonic() - tick
                    )
                )
            else:
                if client is None:
                    client = Client(cookie, timeout)
                last_error = "签到失败"
                outcome = "failure"
                message = ""
                for attempt in range(1, retries + 1):
                    try:
                        log(
                            "账号 {} 签到尝试 {}/{}".format(
                                result.number, attempt, retries
                            )
                        )
                        outcome, message = sign_once(client)
                        break
                    except SafeError as error:
                        last_error = str(error)
                        outcome = "failure"
                        message = last_error
                        if attempt < retries:
                            log(
                                "{} 第 {} 次尝试未成功，准备重试".format(
                                    ICONS["warning"], attempt
                                )
                            )
                            time.sleep(1)
                if outcome == "success":
                    result.stats["success"] += 1
                    result.status = "success"
                    result.message = message
                    log("{} {}".format(ICONS["success"], message))
                elif outcome == "alreadyComplete":
                    result.stats["alreadyComplete"] += 1
                    result.status = "alreadyComplete"
                    result.message = message
                    log("{} {}".format(ICONS["alreadyComplete"], message))
                else:
                    raise SafeError(last_error)
                log(
                    "{} 阶段完成；耗时 {:.2f} 秒".format(
                        ICONS["success"]
                        if result.status in {"success", "alreadyComplete"}
                        else ICONS["failure"],
                        time.monotonic() - tick,
                    )
                )
        except SafeError as error:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
                log(
                    "账号 {} 阶段 {}/{}：⏭️ 因前置失败跳过".format(
                        result.number, pending, total_stages
                    )
                )
            result.status = "failure"
            result.message = str(error)
            log(
                "{} 账号 {} 阶段 {} 失败：{}；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    str(error),
                    time.monotonic() - tick,
                )
            )
            return
        except Exception:
            result.stats["failure"] += 1
            for pending in range(index + 1, total_stages + 1):
                result.stats["skipped"] += 1
            result.status = "failure"
            log(
                "{} 账号 {} 阶段 {} 失败：未预期本地错误，详情已抑制；耗时 {:.2f} 秒".format(
                    ICONS["failure"],
                    result.number,
                    index,
                    time.monotonic() - tick,
                )
            )
            return
    if dry_run:
        result.status = "dry-run"
        result.stats["success"] = 0
    elif result.status not in {"success", "alreadyComplete"}:
        if result.stats["failure"] == 0 and result.stats["alreadyComplete"] == 0:
            result.status = "success"
    elapsed = time.monotonic() - result.started
    log(
        "账号 {}（{}）统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒".format(
            result.number,
            result.identity,
            total_stages,
            result.stats["success"],
            result.stats["alreadyComplete"],
            result.stats["skipped"],
            result.stats["failure"],
            elapsed,
        )
    )


def main() -> int:
    started = time.monotonic()
    started_at = clock()
    dry_setting = env("HDSKY_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    accounts_data: List[str] = []
    timeout = float(DEFAULT_TIMEOUT)
    retries = DEFAULT_RETRIES
    config_error: Optional[str] = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("HDSKY_DRY_RUN 配置无效，停止执行")
        timeout = resolve_timeout()
        retries = resolve_retries()
        accounts_data = load_accounts()
        log(
            "运行模式：{}；账号数：{}；请求超时：{}秒；验证码重试：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                int(timeout) if timeout.is_integer() else timeout,
                retries,
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    results: List[AccountResult] = []
    if config_error is None:
        for number, cookie in enumerate(accounts_data, 1):
            account = AccountResult(number)
            results.append(account)
            run_account(account, cookie, timeout, retries, dry_run)
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        "success": sum(1 for item in results if item.status == "success"),
        "alreadyComplete": sum(
            1 for item in results if item.status == "alreadyComplete"
        ),
        "failure": sum(1 for item in results if item.status == "failure"),
        "dry-run": sum(1 for item in results if item.status == "dry-run"),
    }
    succeeded = counts["success"] + counts["alreadyComplete"]
    failed = account_total if config_error else counts["failure"]
    exit_code = 1 if config_error or failed else 0
    if config_error:
        status = "configuration-error"
    elif failed and (succeeded or counts["dry-run"]):
        status = "partial-failure"
    elif failed:
        status = "failure"
    elif dry_run:
        status = "dry-run"
    else:
        status = "success"
    tasks = {key: sum(item.stats[key] for item in results) for key in STATES}
    body = (
        "状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}；配置错误：{}。".format(
            status,
            account_total,
            succeeded,
            failed,
            counts["dry-run"],
            "是" if config_error else "否",
        )
    )
    log("阶段 通知：开始")
    notification_started = time.monotonic()
    try:
        notification = notify(body, dry_run)
    except Exception:
        notification = "unavailable-or-failed"
        log("通知：⚠️ 适配器发现或调用失败；保留业务退出码")
    log("阶段 通知：结束（{:.2f}秒）".format(time.monotonic() - notification_started))
    finished_at = clock()
    elapsed = round(time.monotonic() - started, 2)
    log("--------------------------------------------------------")
    log(
        "任务统计：账号 {}，成功 {}（含已完成 {}），失败 {}，预演 {}".format(
            account_total,
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
    if dry_run and exit_code == 0:
        print("DRY_RUN_OK", flush=True)
    print(
        "TASK_SUMMARY="
        + json.dumps(
            {
                "task": TITLE,
                "mode": "dry-run" if dry_run else "live",
                "status": status,
                "accounts": account_total,
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
