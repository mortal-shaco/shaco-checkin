#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 重庆工程职院顶岗实习
# cron: 49 8 * * *
# SPDX-License-Identifier: MIT
#
# Copyright (c) 2022 AMEN
# Upstream: 2331892928/gcsx_dgsx main.py（MIT）
# https://github.com/2331892928/gcsx_dgsx
# Commit: 9a04faf953a64d0d529b55c17e37b769ae4b9262
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
"""重庆工程职业技术学院数字校园 → 顶岗实习（青龙维护版，仅标准库）。

面向 ai.cqvie.edu.cn / dgsx.cqvie.edu.cn。上游按分钟保活并在固定时刻自动签到、
补写历史日报/周报/月报；本维护版仅允许当日签到与当期报告，移除伪造历史时间的
补签/补报与硬编码百度密钥、设备指纹、报告正文。

GCSX_DGSX_ACCOUNTS：每个非空行一个账号。格式为数字校园 token，或
token#课程名关键字。仅在首个 # 处分割，后续课程关键字原文保留。在数字校园
（ai.cqvie.edu.cn）登录后，从浏览器开发者工具 Cookie / 请求头复制本人 token；
不要分享抓包或凭据。
GCSX_DGSX_LONGITUDE / GCSX_DGSX_LATITUDE / GCSX_DGSX_ADDRESS：签到所需本人真实
实习地点（经度、纬度、完整地址文本）；启用 sign 动作时必填。禁止依赖第三方地理
编码密钥。
GCSX_DGSX_ACTIONS：逗号/分号/空白分隔的动作，默认 sign。可选
sign / daily / week / month / keepalive。不同时刻可对同一脚本配置多条 Cron。
GCSX_DGSX_LOCAL_TEXT：日报/周报/月报在一言不可用时的本地正文（最多 280 字）。
GCSX_DGSX_DRY_RUN=1：完全断网预演，只校验配置，不发起网络请求。
QINGLONG_NOTIFY / QINGLONG_NOTIFY_SCRIPTS / QINGLONG_NOTIFY_DIR：青龙通知策略。
建议 Cron：每天 08:00 签到；日报 0 16 * * *（ACTIONS=daily）；
周五周报 0 17 * * 5（ACTIONS=week）；每月 28 日 0 18 28 * *（ACTIONS=month）。
"""
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
        _ql_notify_identities = ('f8f6237c9f45a8a7', 'scripts/task_f8f6237c.py', 'task_f8f6237c.py', 'task_f8f6237c')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import http.cookiejar
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "重庆工程职院顶岗实习"
CATALOG_ID = "f8f6237c9f45a8a7"
AI_HOST = "ai.cqvie.edu.cn"
DGSX_HOST = "dgsx.cqvie.edu.cn"
DGSX_ORIGIN = "https://dgsx.cqvie.edu.cn"
HITOKOTO_URL = "https://v1.hitokoto.cn/?encode=json"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)
TIMEOUT = 20
MAX_BYTES = 65536
HITOKOTO_TIMEOUT = 8
HITOKOTO_LIMIT = 16384
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ALLOWED_ACTIONS = ("sign", "daily", "week", "month", "keepalive")
LOCAL_TEXTS = (
    "今日按计划完成实习岗位日常工作，整理文档并复盘进度。",
    "完成岗位交接与任务跟进，记录遇到的问题与处理思路。",
    "参与项目协作与资料整理，巩固本周所学技能。",
    "按指导老师要求推进实习任务，保持沟通与总结。",
)
STATES = ("success", "alreadyComplete", "skipped", "failure")
ICONS = {
    "success": "✅",
    "alreadyComplete": "☑️",
    "skipped": "⏭️",
    "warning": "⚠️",
    "failure": "❌",
}


class SafeError(Exception):
    """只允许固定的脱敏说明进入日志。"""


def clock():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(text):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), text), flush=True)


def env(name, default=""):
    return os.environ.get(name, default).strip()


def truthy(name):
    return env(name, "0").lower() in TRUE_VALUES


def take_middle(text, start, end):
    left = text.find(start)
    if left < 0:
        return None
    left += len(start)
    right = text.find(end, left)
    if right < 0:
        return None
    return text[left:right]


def normalize_public_text(value):
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:280]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_request(
    url,
    method="GET",
    headers=None,
    data=None,
    cookies=None,
    timeout=TIMEOUT,
    limit=MAX_BYTES,
    allow_redirects=False,
    dry_run=False,
):
    if dry_run:
        raise SafeError("断网预演禁止 HTTP 请求")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc not in (
        AI_HOST,
        DGSX_HOST,
        "v1.hitokoto.cn",
    ):
        raise SafeError("拒绝访问非白名单主机")
    jar = http.cookiejar.CookieJar()
    if cookies:
        for name, value in cookies.items():
            if value is None:
                continue
            jar.set_cookie(
                http.cookiejar.Cookie(
                    version=0,
                    name=str(name),
                    value=str(value),
                    port=None,
                    port_specified=False,
                    domain=parsed.hostname or "",
                    domain_specified=bool(parsed.hostname),
                    domain_initial_dot=False,
                    path="/",
                    path_specified=True,
                    secure=parsed.scheme == "https",
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
    handlers = [urllib.request.HTTPCookieProcessor(jar), urllib.request.ProxyHandler({})]
    if not allow_redirects:
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        request_headers.update(headers)
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json;charset=UTF-8")
    elif isinstance(data, str):
        body = data.encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.getcode()
            raw = response.read(limit + 1)
            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            raw = error.read(limit + 1)
        except Exception:
            raw = b""
        finally:
            error.close()
        final_url = url
    except Exception as exc:
        raise SafeError("网络、超时或连接失败") from exc
    if len(raw) > limit:
        raise SafeError("响应超过大小限制")
    cookie_dict = {cookie.name: cookie.value for cookie in jar}
    text = ""
    if raw:
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""
    payload = None
    if text:
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
    return {
        "status": status,
        "text": text,
        "json": payload,
        "cookies": cookie_dict,
        "url": final_url,
    }


def parse_accounts(raw):
    accounts = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "#" in text:
            token, course = text.split("#", 1)
        else:
            token, course = text, ""
        token = token.strip()
        course = course.strip()
        if not token or any(ord(ch) < 32 for ch in token):
            raise SafeError("账号 Token 为空或含控制字符")
        if len(token) < 8:
            raise SafeError("账号 Token 过短，请填写完整数字校园 token")
        accounts.append({"token": token, "course": course})
    return accounts


def parse_actions(raw):
    text = (raw or "sign").strip().lower()
    parts = [item for item in re.split(r"[,;\s]+", text) if item]
    if not parts:
        parts = ["sign"]
    unknown = [item for item in parts if item not in ALLOWED_ACTIONS]
    if unknown:
        raise SafeError(
            "GCSX_DGSX_ACTIONS 含未知动作；允许：sign,daily,week,month,keepalive"
        )
    # 保序去重
    ordered = []
    for item in parts:
        if item not in ordered:
            ordered.append(item)
    return ordered


def parse_location(need_location):
    if not need_location:
        return None
    lon_raw = env("GCSX_DGSX_LONGITUDE")
    lat_raw = env("GCSX_DGSX_LATITUDE")
    address = env("GCSX_DGSX_ADDRESS")
    if not lon_raw or not lat_raw or not address:
        raise SafeError(
            "启用签到时须配置 GCSX_DGSX_LONGITUDE、GCSX_DGSX_LATITUDE、GCSX_DGSX_ADDRESS"
        )
    try:
        longitude = float(lon_raw)
        latitude = float(lat_raw)
    except ValueError as exc:
        raise SafeError("经度或纬度不是合法数字") from exc
    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise SafeError("经纬度超出合法范围")
    if len(address) > 200:
        raise SafeError("签到地址过长")
    return longitude, latitude, address


def classify_business(payload, success_markers=(), already_markers=()):
    if not isinstance(payload, dict):
        return "failure", "响应不是可解析的业务对象"
    message = payload.get("msg")
    if not isinstance(message, str):
        message = payload.get("message") if isinstance(payload.get("message"), str) else ""
    normalized = " ".join(message.split())
    default_already = (
        "已签",
        "已打卡",
        "重复",
        "已经签到",
        "今日已签",
        "已填写",
        "已经填写",
        "已提交",
        "请勿重复",
    )
    for marker in tuple(already_markers) + default_already:
        if marker and marker in normalized:
            return "alreadyComplete", "业务提示：已完成（{}）".format(marker)
    for marker in success_markers:
        if marker and marker in normalized:
            return "success", "业务成功（消息字段已核实）"
    code = payload.get("code")
    code_ok = code in (0, 200, "0", "200")
    if payload.get("success") is True or code_ok:
        return "success", "业务成功（业务字段已核实）"
    if payload.get("success") is False or (code is not None and not code_ok):
        return "failure", "业务失败"
    return "failure", "响应缺少可核实的成功字段"


def format_hitokoto(payload):
    text = normalize_public_text(payload.get("hitokoto") if isinstance(payload, dict) else "")
    if not text:
        raise SafeError("文案缺失")
    author = normalize_public_text(payload.get("from_who") if isinstance(payload, dict) else "")
    source = normalize_public_text(payload.get("from") if isinstance(payload, dict) else "")
    if author and source:
        text = "{} —— {}《{}》".format(text, author, source)
    elif source:
        text = "{} ——《{}》".format(text, source)
    elif author:
        text = "{} —— {}".format(text, author)
    text = normalize_public_text(text)
    if not text:
        raise SafeError("文案缺失")
    if len(text) > 280:
        raise SafeError("署名后的文案过长")
    return text


def published_text(dry_run):
    fallback = normalize_public_text(env("GCSX_DGSX_LOCAL_TEXT"))
    if not fallback:
        fallback = random.choice(LOCAL_TEXTS)
    if dry_run:
        return fallback, "断网预演：不请求一言，使用本地文案"
    try:
        result = http_request(
            HITOKOTO_URL,
            timeout=HITOKOTO_TIMEOUT,
            limit=HITOKOTO_LIMIT,
            dry_run=False,
        )
        if result["status"] != 200 or not isinstance(result["json"], dict):
            raise SafeError("文案接口响应不可用")
        return format_hitokoto(result["json"]), "使用一言文案，保留作者和作品署名"
    except Exception:
        return fallback, "一言不可用，使用本地报告文案"


class Account:
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


class DgsxClient:
    def __init__(self, token, course_filter, dry_run=False):
        self.token = token
        self.course_filter = course_filter
        self.dry_run = dry_run
        self.headers = {
            "Referer": DGSX_ORIGIN + "/mobile/index",
            "Origin": DGSX_ORIGIN + "/",
            "Host": DGSX_HOST,
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": USER_AGENT,
            "Authorization": "Bearer ",
        }
        self.cookie = {
            "sidebarStatus": "0",
            "wxSignUrl": DGSX_ORIGIN + "/mobile/",
        }
        self.admin_token = ""

    def login(self):
        millis = int(round(time.time() * 1000))
        # 优先使用无需伪造设备签名的 PC 办公大厅入口；失败时再回退上游移动端地址。
        pc_url = (
            "http://{}/ump/officeHall/getApplicationUrl"
            "?universityId=102574&appKey=pc-officeHall&timestamp={}"
            "&clientCategory=PC&applicationCode=HR0g30274"
        ).format(AI_HOST, millis)
        mobile_url = (
            "http://{}/ump/officeHall/getApplicationUrl"
            "?appKey=mobileplatform&appVersion=5.3.04&applicationCode=HR0g30274"
            "&clientCategory=IOS&equipmentId=QinglongGCSX&equipmentName=iPhone"
            "&equipmentVersion=16.2&nonce=1676887542046OADFSHBWPQWWK"
            "&sign=5D27B0B10DA12FA635FC53DD03971645&timestamp={}"
            "&universityId=102574&userType=STUDENT"
        ).format(AI_HOST, millis)
        redirect_url = None
        last_error = None
        for url in (pc_url, mobile_url):
            try:
                result = http_request(
                    url,
                    headers={"User-Agent": USER_AGENT, "token": self.token},
                    cookies={"token": self.token},
                    dry_run=self.dry_run,
                )
                payload = result["json"] if isinstance(result["json"], dict) else {}
                content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
                redirect_url = content.get("redirectUrl")
                if isinstance(redirect_url, str) and redirect_url.startswith("https://"):
                    break
                last_error = SafeError("数字校园未返回可用跳转地址")
            except SafeError as error:
                last_error = error
                redirect_url = None
        if not isinstance(redirect_url, str) or not redirect_url.startswith("https://"):
            raise last_error or SafeError("数字校园登录跳转失败，请检查 Token 是否有效")
        parsed = urllib.parse.urlsplit(redirect_url)
        if parsed.netloc != DGSX_HOST:
            raise SafeError("跳转地址主机不受信任")
        first = http_request(
            redirect_url,
            headers={"Host": DGSX_HOST, "User-Agent": USER_AGENT},
            allow_redirects=True,
            dry_run=self.dry_run,
        )
        muyun = take_middle(first["text"], "'cookie' : \"", '",')
        if not muyun:
            muyun = take_middle(first["text"], "'cookie' : '", "',")
        cookies = dict(first["cookies"])
        if muyun:
            cookies["muyun_sign_javascript"] = muyun
        second = http_request(
            redirect_url,
            headers={"Host": DGSX_HOST, "User-Agent": USER_AGENT},
            cookies=cookies,
            allow_redirects=True,
            dry_run=self.dry_run,
        )
        cookies.update(second["cookies"])
        admin = cookies.get("Admin-Token") or ""
        if not admin:
            raise SafeError("未能获取实习系统 Admin-Token，Token 可能失效")
        self.admin_token = admin
        self.cookie.update(cookies)
        self.cookie["Admin-Token"] = admin
        self.headers["Authorization"] = "Bearer " + admin
        return admin

    def api(self, method, url, data=None):
        parsed = urllib.parse.urlsplit(url)
        if parsed.netloc != DGSX_HOST or parsed.scheme != "https":
            raise SafeError("拒绝访问非实习系统地址")
        return http_request(
            url,
            method=method,
            headers=self.headers,
            data=data,
            cookies=self.cookie,
            dry_run=self.dry_run,
        )

    def get_student(self):
        url = DGSX_ORIGIN + "/prod-api/internship_pending/distribution/student_list"
        result = self.api("GET", url)
        payload = result["json"] if isinstance(result["json"], dict) else {}
        rows = payload.get("data")
        if not isinstance(rows, list) or not rows:
            raise SafeError("未获取到实习计划列表，请确认账号已分配实习")
        selected = None
        if self.course_filter:
            for item in rows:
                name = str(item.get("internshipPlanName") or "")
                if self.course_filter in name:
                    selected = item
                    break
            if selected is None:
                raise SafeError("课程关键字未匹配到实习计划")
        else:
            selected = rows[0]
        distribution_id = selected.get("distributionId")
        plan_id = selected.get("internshipPlanId")
        start_date = selected.get("internshipPlanStartDate")
        plan_name = selected.get("internshipPlanName") or ""
        if distribution_id is None or plan_id is None:
            raise SafeError("实习计划缺少必要标识字段")
        return {
            "distributionId": distribution_id,
            "internshipPlanId": plan_id,
            "internshipPlanStartDate": start_date,
            "internshipPlanName": str(plan_name),
        }

    def sign_today(self, location):
        longitude, latitude, address = location
        now_time = datetime.datetime.now().isoformat()
        submit = {
            "latitude": latitude,
            "signAddress": address,
            "signDate": now_time,
            "longitude": longitude,
        }
        result = self.api(
            "POST",
            DGSX_ORIGIN + "/prod-api/internship_pending/signrecord",
            data=submit,
        )
        if result["status"] in (401, 403):
            raise SafeError("凭据无效或没有访问权限")
        if result["status"] != 200:
            raise SafeError("签到请求失败（HTTP {}）".format(result["status"]))
        return classify_business(result["json"])

    def daily_today(self, distribution_id, content):
        today = datetime.date.today().isoformat()
        submit = {
            "distributionId": distribution_id,
            "dailyRecordDate": today,
            "dailyRecordContent": content,
        }
        result = self.api(
            "POST",
            DGSX_ORIGIN + "/prod-api/internship_pending/dailyrecord",
            data=submit,
        )
        if result["status"] in (401, 403):
            raise SafeError("凭据无效或没有访问权限")
        if result["status"] != 200:
            raise SafeError("日报请求失败（HTTP {}）".format(result["status"]))
        return classify_business(result["json"])

    def week_current(self, distribution_id, plan_id, content):
        today = datetime.date.today().isoformat()
        week_res = self.api(
            "GET",
            DGSX_ORIGIN
            + "/prod-api/baseinfo/week/student_list?internshipPlanId="
            + urllib.parse.quote(str(plan_id)),
        )
        week_json = week_res["json"] if isinstance(week_res["json"], dict) else {}
        rows = week_json.get("data")
        if not isinstance(rows, list):
            raise SafeError("请求周次列表失败")
        week_id = None
        for item in rows:
            start_date = str(item.get("startDate") or "")
            end_date = str(item.get("endDate") or "")
            if start_date and end_date and end_date >= today >= start_date:
                week_id = item.get("semesterWeekId")
                break
        if week_id is None:
            raise SafeError("当前不在实习周次范围内")
        submit = {
            "semesterWeekId": week_id,
            "distributionId": distribution_id,
            "weekRecordContent": content,
        }
        result = self.api(
            "POST",
            DGSX_ORIGIN + "/prod-api/internship_pending/weekrecord",
            data=submit,
        )
        if result["status"] in (401, 403):
            raise SafeError("凭据无效或没有访问权限")
        if result["status"] != 200:
            raise SafeError("周报请求失败（HTTP {}）".format(result["status"]))
        return classify_business(result["json"])

    def month_current(self, distribution_id, plan_id, content):
        now = datetime.datetime.now()
        month_name = "{}年{}月".format(now.year, now.month)
        month_res = self.api(
            "GET",
            DGSX_ORIGIN
            + "/prod-api/internship_before/month/list_all?internshipPlanId="
            + urllib.parse.quote(str(plan_id)),
        )
        month_json = month_res["json"] if isinstance(month_res["json"], dict) else {}
        rows = month_json.get("data")
        if not isinstance(rows, list):
            raise SafeError("请求月次列表失败")
        month_id = None
        for item in rows:
            if str(item.get("monthName") or "") == month_name:
                month_id = item.get("semesterMonthId")
                break
        if month_id is None:
            raise SafeError("当前不在实习月次范围内")
        semester_res = self.api(
            "GET",
            DGSX_ORIGIN + "/prod-api/baseinfo/semester/list_all",
        )
        semester_json = semester_res["json"] if isinstance(semester_res["json"], dict) else {}
        semester_rows = semester_json.get("data")
        if not isinstance(semester_rows, list) or not semester_rows:
            raise SafeError("请求学期列表失败")
        semester_id = semester_rows[0].get("semesterId")
        list_res = self.api(
            "GET",
            DGSX_ORIGIN
            + "/prod-api/internship_pending/monthrecord/list?internshipPlanSemester="
            + urllib.parse.quote(str(semester_id)),
        )
        list_json = list_res["json"] if isinstance(list_res["json"], dict) else {}
        existing = list_json.get("rows")
        if isinstance(existing, list):
            for item in existing:
                if str(item.get("monthName") or "") == month_name:
                    return "alreadyComplete", "本月已填写月报"
        submit = {
            "monthRecordId": None,
            "monthRecordType": None,
            "monthWeekId": month_id,
            "studentUserId": None,
            "distributionId": distribution_id,
            "monthRecordDate": None,
            "monthRecordTitle": month_name + "的月报",
            "monthRecordContent": content,
            "monthRecordTeacherScore": None,
            "monthRecordTeacherComment": None,
            "monthRecordTeacherUserId": None,
            "monthRecordRatifyStatus": None,
            "delFlag": None,
            "createBy": None,
            "createTime": None,
            "updateBy": None,
            "updateTime": None,
        }
        result = self.api(
            "POST",
            DGSX_ORIGIN + "/prod-api/internship_pending/monthrecord",
            data=submit,
        )
        if result["status"] in (401, 403):
            raise SafeError("凭据无效或没有访问权限")
        if result["status"] != 200:
            raise SafeError("月报请求失败（HTTP {}）".format(result["status"]))
        return classify_business(result["json"])


def run_account(account, item, actions, location, dry_run):
    stage_no = 1

    def parameter_check():
        if len(item["token"]) < 8:
            raise SafeError("Token 格式错误")
        return "success", "凭据本地格式检查通过，内容不输出", None

    account.stage(stage_no, "参数检查", parameter_check)
    stage_no += 1

    client = DgsxClient(item["token"], item["course"], dry_run=dry_run)
    student = None

    if dry_run:
        account.skip(stage_no, "登录实习系统", "断网预演：不请求数字校园与实习系统")
        stage_no += 1
        account.identity = "账号{}".format(account.number)
        account.stage(
            stage_no,
            "公开身份",
            lambda: ("success", "公开账号身份：{}".format(account.identity), None),
        )
        stage_no += 1
        for action in actions:
            account.skip(stage_no, "动作 {}".format(action), "断网预演：不执行业务写入")
            stage_no += 1
        account.status = "dry-run"
        return

    def login_stage():
        client.login()
        return "success", "已换取实习系统会话（Token 不输出）", None

    account.stage(stage_no, "登录实习系统", login_stage)
    stage_no += 1

    def load_student():
        nonlocal student
        student = client.get_student()
        plan_name = normalize_public_text(student.get("internshipPlanName") or "")
        account.identity = plan_name or "distributionId={}".format(student["distributionId"])
        return "success", "公开账号身份：{}".format(account.identity), student

    account.stage(stage_no, "读取实习计划", load_student)
    stage_no += 1

    need_text = any(action in actions for action in ("daily", "week", "month"))
    report_text = None
    if need_text:

        def prepare_text():
            nonlocal report_text
            report_text, detail = published_text(dry_run=False)
            return "success", detail, report_text

        account.stage(stage_no, "准备报告文案", prepare_text)
        stage_no += 1

    for action in actions:
        if action == "keepalive":

            def keepalive():
                if student is None:
                    raise SafeError("缺少实习计划信息")
                return (
                    "success",
                    "会话保活成功；distributionId 已核验",
                    None,
                )

            account.stage(stage_no, "会话保活", keepalive)
        elif action == "sign":

            def do_sign():
                state, detail = client.sign_today(location)
                if state == "failure":
                    raise SafeError(detail)
                return state, detail, None

            account.stage(stage_no, "当日签到", do_sign)
        elif action == "daily":

            def do_daily():
                state, detail = client.daily_today(student["distributionId"], report_text)
                if state == "failure":
                    raise SafeError(detail)
                return state, detail, None

            account.stage(stage_no, "提交日报", do_daily)
        elif action == "week":

            def do_week():
                state, detail = client.week_current(
                    student["distributionId"], student["internshipPlanId"], report_text
                )
                if state == "failure":
                    raise SafeError(detail)
                return state, detail, None

            account.stage(stage_no, "提交周报", do_week)
        elif action == "month":

            def do_month():
                state, detail = client.month_current(
                    student["distributionId"], student["internshipPlanId"], report_text
                )
                if state == "failure":
                    raise SafeError(detail)
                return state, detail, None

            account.stage(stage_no, "提交月报", do_month)
        stage_no += 1

    if account.stats["failure"]:
        account.status = "failure"
    elif account.stats["success"] or account.stats["alreadyComplete"]:
        account.status = (
            "alreadyComplete"
            if account.stats["alreadyComplete"] and not account.stats["success"]
            else "success"
        )
    else:
        account.status = "success"


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
        "cqvie_dgsx.py",
        "candidate.py",
        "scripts/cqvie_dgsx.py",
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
    directory = env("QINGLONG_NOTIFY_DIR")
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
    dry_setting = env("GCSX_DGSX_DRY_RUN", "0").lower()
    dry_run = dry_setting in TRUE_VALUES
    raw_accounts = env("GCSX_DGSX_ACCOUNTS")
    accounts_data = []
    actions = []
    location = None
    config_error = None

    log("========== {} ==========".format(TITLE))
    log(
        "开始时间：{}；运行模式：{}；账号数：待解析".format(
            started_at, "断网预演" if dry_run else "真实执行"
        )
    )

    try:
        if dry_setting not in TRUE_VALUES | FALSE_VALUES | {""}:
            raise SafeError("GCSX_DGSX_DRY_RUN 配置无效，停止执行")
        if not raw_accounts:
            raise SafeError(
                "未配置 GCSX_DGSX_ACCOUNTS；请按每个非空行 token 或 token#课程关键字 填写"
            )
        accounts_data = parse_accounts(raw_accounts)
        if not accounts_data:
            raise SafeError("GCSX_DGSX_ACCOUNTS 没有有效账号行")
        actions = parse_actions(env("GCSX_DGSX_ACTIONS", "sign"))
        location = parse_location("sign" in actions)
        log(
            "运行模式：{}；账号数：{}；动作：{}".format(
                "断网预演" if dry_run else "真实执行",
                len(accounts_data),
                ",".join(actions),
            )
        )
    except SafeError as error:
        config_error = str(error)
        log("阶段 0 参数配置：❌ " + config_error)

    accounts = []
    if config_error is None:
        for number, item in enumerate(accounts_data, 1):
            account = Account(number)
            accounts.append(account)
            try:
                run_account(account, item, actions, location, dry_run)
            except SafeError:
                account.status = "failure"
            except Exception:
                account.status = "failure"
                log("账号 {}：❌ 未预期的本地错误，详情已抑制".format(number))
            finally:
                account.finish()
            if not dry_run and number != len(accounts_data):
                time.sleep(1)

    account_total = len(accounts_data)
    counts = {
        state: sum(a.status == state for a in accounts)
        for state in ("success", "alreadyComplete", "failure", "dry-run")
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
    tasks = {key: sum(account.stats[key] for account in accounts) for key in STATES}
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
                "actions": actions,
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
