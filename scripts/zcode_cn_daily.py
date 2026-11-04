#!/usr/bin/env python3
# name: ZCode 国内版领套餐
# cron: 1 9 * * *
# 来源：L0NE-6/ZCode-Daily，zcode_cn_daily.py、zcode_intl_daily.py；登录说明参考 zcode_login.py
# 上游许可：MIT；本维护版本沿用 MIT。
"""
ZCode 国内版限时套餐领取（不是传统签到）。Python 3，仅使用标准库。
功能清点：预览 billing 套餐与 marketing/touch 活动位并合并、按最高优先级
（同优先取首项）或指定套餐领取、营销回执确认与可选复查、本地领取台账、
验证码、版本参数、单账号筛选、北京时间、多渠道通知；激活事件改为显式开启。
上游未提供 cron；建议每日北京时间 09:00，青龙调度时区需设 Asia/Shanghai。
国际版 JWT 不通用，使用独立账号变量及区域选择，绝不自动转换凭据。
默认 --region cn 保持既有国内版任务；--region intl 只运行国际版；
--region all 按国内、国际顺序处理已配置账号，--only 使用所选范围的统一编号。
可用 ZCODE_REGION 设置默认区域（cn/intl/all），命令行优先。
ZCODE_INTL_TOKENS：国际版账号，格式与 ZCODE_CN_TOKENS 相同；从官方国际版
登录后的 billing/preview 或 billing/claim 请求获取套餐 JWT、设备及验证码。
也可在官方客户端完成网页授权登录后抓取同一请求，勿使用推理 access_token。
ZCODE_INTL_DRY_RUN=1 或 ZCODE_CN_DRY_RUN=1 均使整个进程完全断网。
国际版兼容读取已有 zcode_intl_devices.json，缺省设备值按国际版独立生成。
交互登录工具只作为凭据获取参考，不自动授权、不输出凭据。

ZCODE_CN_TOKENS：每行一个账号，不用 & 或 @ 分隔。兼容以下格式：
jwt；jwt|device_mid；jwt|device_mid|captcha；备注|jwt|device_mid|captcha。
备注前缀要求下一段为 JWT；依次仅在第一个 | 拆字段，最后验证码保留全部字符。
在官方 ZCode 国内版登录后，在浏览器开发者工具的网络面板查看套餐
billing/preview 或 billing/claim 请求：Authorization 的 Bearer 后内容为套餐 JWT，
X-Device-Mid 为设备值；claim 的 X-Aliyun-Captcha-Verify-Param 为验证码参数。
不要使用推理 API Key 或国际版 Token。验证码可能短时一次性，3007 时重新抓取。
设备值优先显式填写；兼容读取脚本旁已有 zcode_cn_devices.json，缺省确定性生成，
不创建或修改任何设备文件。JWT 更换会改变自动生成的设备值，建议固定显式设备值。
ZCODE_PLAN_ID：可选指定预览返回的 plan_id；ZCODE_APP_VERSION：默认 3.18.0。
marketing/touch 需要客户端版本 3.17.1+；低于该版本时跳过营销来源并继续 billing。
ZCODE_CAPTCHA_PARAM：可选全局验证码，仅补齐账号未填写的值，优先使用账号内参数。
ZCODE_ACTIVATION：默认 0；设 1 显式补报 app_launch/app_daily_active，可能影响领取资格。
ZCODE_MARKETING_RECHECK：默认 1；领取后复查营销活动位；设 0 关闭复查。
--preview：只读预览（绝不上报事件或领取）；--only N：仅运行第 N 个账号；
--no-notify：禁用通知；ZCODE_CN_DRY_RUN=1：完全断网，通知仅模拟，不验证真实账号。
QINGLONG_NOTIFY 默认 auto，按通知策略仅通知选中的脚本；未配置选择列表时不推送。
设 1/true/yes/on 开启；0/false/no/off 关闭，--no-notify 优先关闭。
QINGLONG_NOTIFY_SCRIPTS 设置后替换默认选择，空值关闭；逗号、分号或空白分隔，
支持目录相对路径、文件名、文件名通配符及目录编号 a0a7b04503bfb900，* 选择全部。
自动发现青龙 notify.py 或 sendNotify.js；可用 QINGLONG_NOTIFY_DIR 指定目录。
通知失败不改变业务退出码；预演只模拟通知，绝不导入或运行通知模块。
原推送参数 PUSHPLUS_TOKEN/BARK_URL/WECOM_WEBHOOK/DINGTALK_WEBHOOK/
DINGTALK_SECRET 保留，青龙通知不可用时尝试。不得配置非 HTTPS 推送地址。
不自动登录、不安装软件、不发布文本、不重试领取 POST，以避免重复副作用。
已确认领取写入区域台账 zcode_{cn|intl}_claim_ledger.json（仅哈希与套餐标识，保留 90 天）；
预演与 --preview 不写入台账；不创建或改写设备文件。
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
        _ql_notify_identities = ('a0a7b04503bfb900', 'scripts/zcode_cn_daily.py', 'zcode_cn_daily.py', 'zcode_cn_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
# 随任务提供的源码没有额外版权声明；保留来源归属及 MIT 许可。
#
# MIT License
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

import argparse
import base64
import hashlib
import hmac
import fnmatch
import importlib.util
import json
import os
import platform as host_platform
import re
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta, timezone

ORIGIN = "https://zcode.z.ai"
PREVIEW_PATH = "/api/v1/zcode-plan/billing/preview"
EVENT_REPORT_PATH = "/api/v1/event/report"
CLAIM_PATH = "/api/v1/zcode-plan/billing/claim"
MARKETING_QUERY_PATH = "/api/v1/marketing/touch"
MARKETING_ACTION_PATH = "/api/v1/marketing/touch/action"
DEFAULT_APP_VERSION = "3.18.0"
MARKETING_MIN_APP_VERSION = "3.17.1"
MARKETING_MAX_DEPTH = 12
MARKETING_MAX_NODES = 4096
MARKETING_MAX_DELIVERIES = 32
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
CLAIM_LEDGER_VERSION = 1
CLAIM_LEDGER_RETENTION_SECONDS = 90 * 24 * 60 * 60
BEIJING_TZ = timezone(timedelta(hours=8))
FAILURE_LABELS = {
    1001: "没有这个套餐",
    1002: "活动未开始或已结束",
    1003: "已领取本期套餐",
    1004: "账号或版本不在活动范围",
    1005: "今日次数用完",
    3001: "参数错误，请检查设备参数",
    3007: "验证码未通过，请从 claim 请求重新获取验证码参数",
    401: "登录失效，请重新登录",
}
DRY = False
SECRETS = []


def log(message):
    print(beijing_now().strftime("[%H:%M:%S] ") + str(message), flush=True)


def safe(value, public_uid=False):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[已脱敏]")
    text = re.sub(r"[\r\n\x00-\x1f\x7f]", " ", text)
    if not public_uid:
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已脱敏]", text)
    return text


class TaskError(Exception):
    pass


class Response:
    def __init__(self, status, payload, raw_size=0):
        self.status_code = status
        self.payload = payload
        self.raw_size = raw_size

    def json(self):
        return self.payload


def request(method, url, headers=None, body=None, timeout=15, max_bytes=None):
    if DRY:
        raise TaskError("预演禁止网络请求")
    if not url.startswith("https://"):
        raise TaskError("拒绝非 HTTPS 请求")
    limit = MAX_RESPONSE_BYTES if max_bytes is None else max_bytes

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    raw = None if body is None else json.dumps(body).encode()
    hdr = dict(headers or {})
    if body is not None:
        hdr.setdefault("Content-Type", "application/json")
    try:
        req = urllib.request.Request(url, data=raw, headers=hdr, method=method)
        try:
            response = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            data = response.read(limit + 1)
        if len(data) > limit:
            raise TaskError("响应过大")
        if not data:
            return Response(status, {}, 0)
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError()
        return Response(status, payload, len(data))
    except TaskError:
        raise
    except Exception:
        raise TaskError("网络、TLS 或响应格式异常（已隐藏原始内容）") from None


def json_of(response):
    return response.json()


def post_json(url, payload, timeout=20):
    return request("POST", url, body=payload, timeout=timeout)


def local_timezone():
    return "Asia/Shanghai"


def local_os_version():
    return ""


def beijing_now():
    return datetime.now(BEIJING_TZ)


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def app_version():
    return os.environ.get("ZCODE_APP_VERSION", "").strip() or DEFAULT_APP_VERSION


def client_platform():
    system = host_platform.system().lower()
    machine = host_platform.machine().lower()
    if system == "windows":
        return "win32-x64"
    if system == "darwin":
        return "darwin-arm64" if "arm" in machine else "darwin-x64"
    return "linux-arm64" if ("arm" in machine or "aarch64" in machine) else "linux-x64"


def os_category():
    system = host_platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def activation_event_body(event, user_id, device_mid):
    return {
        "event_id": str(uuid.uuid4()),
        "client_timezone": local_timezone(),
        "client_language": "zh-CN",
        "element_name": event,
        "event_region": "app",
        "event_type": "view",
        "event_text": "",
        "event_extra_detail": {},
        "user_id": user_id,
        "screen_resolution": "2560x1440",
        "app_version": app_version(),
        "device_os_category": os_category(),
        "device_os_version": local_os_version(),
        "device_mid": device_mid,
        "source_page": "",
        "source_element": "{}",
    }


def preview(region_jwt, device_mid):
    url = "%s%s?app_version=%s&platform=%s" % (
        ORIGIN,
        PREVIEW_PATH,
        urllib.parse.quote(app_version(), safe=""),
        urllib.parse.quote(client_platform(), safe=""),
    )
    headers = {"X-Device-Mid": device_mid} if device_mid else {}
    if region_jwt:
        headers["Authorization"] = "Bearer %s" % region_jwt
    return request("GET", url, headers=headers)


def claim(jwt, plan_id, device_mid, captcha):
    headers = {
        "Authorization": "Bearer %s" % jwt,
        "Content-Type": "application/json",
        "X-ZCode-App-Version": app_version(),
        "X-Platform": client_platform(),
    }
    if captcha:
        headers["X-Aliyun-Captcha-Verify-Param"] = captcha
    if device_mid:
        headers["X-Device-Mid"] = device_mid
    return request("POST", ORIGIN + CLAIM_PATH, headers=headers, body={"plan_id": plan_id})


def _env(name):
    return os.environ.get(name, "").strip()


def _int_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _epoch_seconds(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def _safe_identifier(value, limit=256):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > limit or any(ord(char) < 32 for char in value):
        return ""
    return value


def _version_tuple(value):
    text = str(value or "").strip().lower().lstrip("v").split("-", 1)[0]
    if not text:
        return None
    parts = text.split(".")
    numbers = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except (TypeError, ValueError):
            return None
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def _version_at_least(value, minimum):
    current = _version_tuple(value)
    required = _version_tuple(minimum)
    if current is None or required is None:
        return False
    return current >= required


def _parse_entitlements(raw):
    entitlements = []
    if not isinstance(raw, list):
        return entitlements
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        show_name = first_text(entry.get("show_name"), entry.get("showName"), entry.get("name"))
        if not show_name:
            continue
        entitlements.append({
            "name": show_name,
            "unit": first_text(entry.get("unit_type"), entry.get("unitType"), entry.get("unit")),
            "grant": entry.get("grant_units", entry.get("grantUnits", entry.get("grant", 0))),
            "period": first_text(entry.get("period")),
        })
    return entitlements


def _normalize_plan(raw, source, default_priority=0, campaign_ids=None):
    if not isinstance(raw, dict):
        return None
    plan_id = _safe_identifier(first_text(raw.get("plan_id"), raw.get("planId")))
    if not plan_id:
        return None
    priority = _int_value(raw.get("priority"))
    if priority is None:
        priority = default_priority
    campaigns = []
    for campaign in campaign_ids or []:
        campaign = _safe_identifier(campaign)
        if campaign and campaign not in campaigns:
            campaigns.append(campaign)
    return {
        "plan_id": plan_id,
        "name": first_text(raw.get("name")) or plan_id,
        "description": first_text(raw.get("description")),
        "priority": priority,
        "starts_at": _epoch_seconds(raw.get("starts_at", raw.get("startsAt"))),
        "ends_at": _epoch_seconds(raw.get("ends_at", raw.get("endsAt"))),
        "entitlements": _parse_entitlements(raw.get("entitlements")),
        "sources": [source],
        "campaign_ids": campaigns,
    }


def parse_plans(payload):
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw = data.get("plans")
    plans = []
    if isinstance(raw, list):
        for item in raw:
            plan = _normalize_plan(item, "billing")
            if plan is not None:
                plans.append(plan)
    return plans


def _merge_plan_into(existing, incoming):
    if not existing.get("name") or existing.get("name") == existing.get("plan_id"):
        existing["name"] = incoming.get("name") or existing.get("name")
    if not existing.get("description"):
        existing["description"] = incoming.get("description", "")
    existing["priority"] = max(existing.get("priority", 0), incoming.get("priority", 0))
    if existing.get("starts_at") is None and incoming.get("starts_at") is not None:
        existing["starts_at"] = incoming["starts_at"]
    if existing.get("ends_at") is None and incoming.get("ends_at") is not None:
        existing["ends_at"] = incoming["ends_at"]
    if not existing.get("entitlements") and incoming.get("entitlements"):
        existing["entitlements"] = [dict(entry) for entry in incoming["entitlements"]]
    for source in incoming.get("sources", []):
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for campaign in incoming.get("campaign_ids", []):
        if campaign not in existing["campaign_ids"]:
            existing["campaign_ids"].append(campaign)


def merge_plan_sources(*groups):
    plans = []
    by_id = {}
    for group in groups:
        for raw in group or []:
            if not isinstance(raw, dict):
                continue
            plan_id = _safe_identifier(raw.get("plan_id"))
            if not plan_id:
                continue
            incoming = {
                "plan_id": plan_id,
                "name": first_text(raw.get("name")) or plan_id,
                "description": first_text(raw.get("description")),
                "priority": _int_value(raw.get("priority")) or 0,
                "starts_at": _epoch_seconds(raw.get("starts_at")),
                "ends_at": _epoch_seconds(raw.get("ends_at")),
                "entitlements": _parse_entitlements(raw.get("entitlements")),
                "sources": list(raw.get("sources") or []),
                "campaign_ids": list(raw.get("campaign_ids") or []),
            }
            existing = by_id.get(plan_id)
            if existing is None:
                by_id[plan_id] = incoming
                plans.append(incoming)
            else:
                _merge_plan_into(existing, incoming)
    return plans


def _marketing_headers(jwt, device_mid):
    headers = {
        "X-Client-Language": "zh-CN",
        "X-ZCode-App-Version": app_version(),
    }
    if jwt:
        headers["Authorization"] = "Bearer %s" % jwt
    if device_mid:
        headers["X-Device-Mid"] = device_mid
    return headers


def _source_result(ok, plans=None, error="", skipped=False, deployed=True, delivery_count=None):
    return {
        "ok": bool(ok),
        "plans": plans or [],
        "error": error,
        "skipped": bool(skipped),
        "deployed": bool(deployed),
        "delivery_count": delivery_count,
    }


def _marketing_plan_metadata(raw, default_priority):
    plan = _normalize_plan(raw, "marketing", default_priority)
    if plan is None:
        plan = _normalize_plan(
            raw.get("zcode_plan") if isinstance(raw, dict) else None,
            "marketing",
            default_priority,
        )
    return plan


def _walk_marketing_delivery(delivery):
    metadata = {}
    action_plan_ids = []
    seen = set()
    budget = [MARKETING_MAX_NODES]
    delivery_priority = _int_value(delivery.get("priority")) or 0

    def remember_plan(plan):
        if plan is None:
            return
        existing = metadata.get(plan["plan_id"])
        if existing is None:
            metadata[plan["plan_id"]] = plan
        else:
            _merge_plan_into(existing, plan)

    def walk(node, depth):
        if depth > MARKETING_MAX_DEPTH or budget[0] <= 0:
            return
        if isinstance(node, (dict, list)):
            marker = id(node)
            if marker in seen:
                return
            seen.add(marker)
        budget[0] -= 1
        if isinstance(node, dict):
            remember_plan(_marketing_plan_metadata(node, delivery_priority))
            nested = node.get("zcode_plan")
            if isinstance(nested, dict):
                remember_plan(_normalize_plan(nested, "marketing", delivery_priority))
            action = node.get("action")
            if isinstance(action, dict) and action.get("type") == "claim_zcode_plan":
                args = action.get("args")
                plan_id = _safe_identifier(args.get("plan_id")) if isinstance(args, dict) else ""
                if plan_id and plan_id not in action_plan_ids:
                    action_plan_ids.append(plan_id)
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(delivery, 0)
    campaign_id = _safe_identifier(delivery.get("campaign_id"))
    found = []
    for plan_id in action_plan_ids:
        plan = metadata.get(plan_id)
        if plan is None:
            plan = {
                "plan_id": plan_id,
                "name": plan_id,
                "description": "",
                "priority": delivery_priority,
                "starts_at": None,
                "ends_at": None,
                "entitlements": [],
                "sources": ["marketing"],
                "campaign_ids": [],
            }
        else:
            plan = dict(plan)
            plan["entitlements"] = [dict(entry) for entry in plan.get("entitlements", [])]
            plan["sources"] = list(plan.get("sources", []))
            plan["campaign_ids"] = list(plan.get("campaign_ids", []))
        if campaign_id and campaign_id not in plan["campaign_ids"]:
            plan["campaign_ids"].append(campaign_id)
        found.append(plan)
    return found


def parse_marketing_plans(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    deliveries = data.get("deliveries") if isinstance(data, dict) else None
    if not isinstance(deliveries, list):
        return [], "营销套餐查询失败：上游未返回有效活动列表"
    if len(deliveries) > MARKETING_MAX_DELIVERIES:
        return [], "营销套餐查询失败：活动列表超过上限 %d" % MARKETING_MAX_DELIVERIES
    plans = []
    for delivery in deliveries:
        if not isinstance(delivery, dict):
            continue
        plans.extend(_walk_marketing_delivery(delivery))
    return merge_plan_sources(plans), ""


def query_billing_plans(jwt, device_mid):
    try:
        response = preview(jwt, device_mid)
    except TaskError as error:
        return _source_result(False, error="套餐预览请求失败: %s" % error)
    if response.status_code == 404:
        return _source_result(False, error="领取接口尚未部署（活动未上线）")
    if response.status_code == 401:
        return _source_result(False, error="登录状态失效，请重新登录")
    payload = json_of(response)
    code = _int_value(payload.get("code"))
    if response.status_code != 200 or code not in (0, None):
        label = FAILURE_LABELS.get(code) if isinstance(code, int) else None
        return _source_result(False, error="套餐预览查询失败: %s" % (label or "业务响应未确认成功"))
    if not isinstance(payload.get("data"), dict):
        return _source_result(False, error="套餐预览响应缺少有效 data")
    log_identities(payload)
    return _source_result(True, plans=parse_plans(payload))


def query_marketing_plans(jwt, device_mid):
    version = app_version()
    if not _version_at_least(version, MARKETING_MIN_APP_VERSION):
        return _source_result(
            False,
            error="营销套餐查询跳过：ZCODE_APP_VERSION=%s 低于 marketing/touch 最低版本 %s"
                  % (version, MARKETING_MIN_APP_VERSION),
            skipped=True,
        )
    try:
        response = request(
            "GET",
            ORIGIN + MARKETING_QUERY_PATH + "?seq=0",
            headers=_marketing_headers(jwt, device_mid),
            timeout=15,
        )
    except TaskError as error:
        return _source_result(False, error="营销套餐查询失败: %s" % error)
    if response.status_code == 404:
        return _source_result(True, plans=[], deployed=False)
    payload = json_of(response)
    code = _int_value(payload.get("code"))
    if response.status_code != 200 or code != 0 or payload.get("success") is False:
        label = FAILURE_LABELS.get(code) if isinstance(code, int) else None
        return _source_result(False, error="营销套餐查询失败: %s" % (label or "业务响应未确认成功"))
    plans, error = parse_marketing_plans(payload)
    if error:
        return _source_result(False, error=error)
    data = payload.get("data") if isinstance(payload, dict) else None
    deliveries = data.get("deliveries") if isinstance(data, dict) else None
    return _source_result(True, plans=plans, delivery_count=len(deliveries) if isinstance(deliveries, list) else None)


def source_warning(*sources):
    failures = []
    skipped = []
    for label, result in sources:
        if result.get("ok"):
            continue
        item = "%s: %s" % (label, result.get("error") or "未知错误")
        if result.get("skipped"):
            skipped.append(item)
        else:
            failures.append(item)
    parts = []
    if failures:
        parts.append("部分来源失败: %s" % "；".join(failures))
    if skipped:
        parts.append("来源未查询: %s" % "；".join(skipped))
    return "；" + "；".join(parts) if parts else ""


def confirm_marketing_claim(jwt, device_mid, plan):
    campaign_ids = []
    for campaign in plan.get("campaign_ids") or []:
        campaign = _safe_identifier(campaign)
        if campaign and campaign not in campaign_ids:
            campaign_ids.append(campaign)
    if not campaign_ids:
        return None, ""
    errors = []
    confirmed = 0
    for campaign_id in campaign_ids:
        try:
            response = request(
                "POST",
                ORIGIN + MARKETING_ACTION_PATH,
                headers=_marketing_headers(jwt, device_mid),
                body={"campaign_id": campaign_id, "action_type": "confirm"},
                timeout=15,
            )
        except TaskError as error:
            errors.append("%s: %s" % (campaign_id, error))
            continue
        payload = json_of(response)
        code = _int_value(payload.get("code"))
        if 200 <= response.status_code < 300 and code == 0 and payload.get("success") is not False:
            confirmed += 1
        else:
            label = FAILURE_LABELS.get(code) if isinstance(code, int) else None
            errors.append("%s: %s" % (campaign_id, label or "业务响应未确认成功"))
    if errors:
        if confirmed:
            return False, "营销回执部分成功（%d/%d）: %s" % (confirmed, len(campaign_ids), "；".join(errors))
        return False, "营销回执失败: %s" % "；".join(errors)
    return True, "营销回执已确认（%d 个 campaign）" % confirmed


def recheck_marketing_claim(jwt, device_mid, plan):
    if _env("ZCODE_MARKETING_RECHECK") == "0":
        return ""
    result = query_marketing_plans(jwt, device_mid)
    if not result.get("ok"):
        return "；营销复查询失败: %s" % result.get("error")
    if not result.get("deployed", True):
        return "；营销复查询接口未部署，不能作为活动位下线证据"
    delivery_count = result.get("delivery_count")
    if delivery_count == 0:
        return "；营销活动位已下线（正向证据）"
    remaining = any(item.get("plan_id") == plan.get("plan_id") for item in result.get("plans", []))
    if remaining:
        return "；营销活动位仍返回该套餐（不作为失败）"
    if delivery_count is not None:
        return "；营销活动位仍有 %d 条，但未匹配到该套餐（不作为下线证据）" % delivery_count
    return "；营销复查询未返回 deliveries 数量，不能作为活动位下线证据"


def finalize_marketing_claim(account, plan, preview_only=False):
    if preview_only or not plan.get("campaign_ids"):
        return ""
    notes = []
    confirmed, confirm_note = confirm_marketing_claim(account["jwt"], account["device_mid"], plan)
    if confirmed is True:
        notes.append(confirm_note)
    elif confirmed is False:
        notes.append(confirm_note + "（不影响已确认领取）")
    recheck_note = recheck_marketing_claim(account["jwt"], account["device_mid"], plan)
    if recheck_note:
        notes.append(recheck_note.lstrip("；"))
    return "；" + "；".join(notes) if notes else ""


def ledger_path(region):
    return Path(__file__).with_name("zcode_%s_claim_ledger.json" % region)


def empty_claim_ledger():
    return {"version": CLAIM_LEDGER_VERSION, "claims": []}


def _same_beijing_day(timestamp, now):
    try:
        claimed = datetime.fromtimestamp(int(timestamp), BEIJING_TZ)
    except (TypeError, ValueError, OverflowError, OSError):
        return False
    return claimed.date() == now.astimezone(BEIJING_TZ).date()


def _normalize_claim_ledger(raw, now, region):
    if not isinstance(raw, dict) or raw.get("version") != CLAIM_LEDGER_VERSION:
        return empty_claim_ledger()
    raw_claims = raw.get("claims")
    if not isinstance(raw_claims, list):
        return empty_claim_ledger()
    now_ts = int(now.timestamp())
    cutoff = now_ts - CLAIM_LEDGER_RETENTION_SECONDS
    claims = []
    seen = set()
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        account_hash = _safe_identifier(item.get("account"), 64)
        item_region = _safe_identifier(item.get("region"), 16)
        plan_id = _safe_identifier(item.get("plan_id"))
        claimed_at = _epoch_seconds(item.get("claimed_at"))
        expiry = _epoch_seconds(item.get("expiry"))
        if len(account_hash) != 64 or any(char not in "0123456789abcdef" for char in account_hash):
            continue
        if item_region != region or not plan_id or claimed_at is None or claimed_at < cutoff:
            continue
        if claimed_at > now_ts + 24 * 60 * 60:
            continue
        claim_item = {
            "account": account_hash,
            "region": region,
            "plan_id": plan_id,
            "claimed_at": claimed_at,
            "expiry": expiry,
        }
        key = (account_hash, plan_id, claimed_at, expiry)
        if key in seen:
            continue
        seen.add(key)
        claims.append(claim_item)
    claims.sort(key=lambda claim: claim["claimed_at"])
    return {"version": CLAIM_LEDGER_VERSION, "claims": claims}


def save_claim_ledger(ledger, region):
    if DRY:
        return False, "预演禁止写入台账"
    path = ledger_path(region)
    temp_path = Path("%s.%s.tmp" % (path, uuid.uuid4().hex))
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
        return True, ""
    except Exception as error:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        return False, safe(error)


def load_claim_ledger(region):
    path = ledger_path(region)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty_claim_ledger()
    except Exception:
        log("⚠️ 领取台账不可读，按服务端现状继续")
        return empty_claim_ledger()
    if not isinstance(raw, dict) or raw.get("version") != CLAIM_LEDGER_VERSION or not isinstance(raw.get("claims"), list):
        log("⚠️ 领取台账格式或版本不支持，按服务端现状继续")
        return empty_claim_ledger()
    ledger = _normalize_claim_ledger(raw, beijing_now(), region)
    if ledger != raw and not DRY:
        saved, error = save_claim_ledger(ledger, region)
        if not saved:
            log("⚠️ 领取台账清理后保存失败: %s" % error)
    return ledger


def stable_account_hash(account):
    user_id = str(account.get("user_id") or "").strip()
    if user_id:
        subject = "user:" + user_id
    else:
        token_hash = hashlib.sha256(str(account.get("jwt") or "").encode("utf-8")).hexdigest()
        subject = "token:" + token_hash
    return hashlib.sha256(("%s:%s" % (account.get("region") or "cn", subject)).encode("utf-8")).hexdigest()


def _claim_matches_plan(claim_item, plan, now):
    if claim_item.get("plan_id") != plan.get("plan_id"):
        return False
    now_ts = int(now.timestamp())
    claim_expiry = _epoch_seconds(claim_item.get("expiry"))
    claimed_at = _epoch_seconds(claim_item.get("claimed_at"))
    plan_expiry = _epoch_seconds(plan.get("ends_at"))
    plan_start = _epoch_seconds(plan.get("starts_at"))
    if claim_expiry is not None and claim_expiry <= now_ts:
        return False
    if claim_expiry is not None and plan_start is not None:
        if plan_start >= claim_expiry:
            return False
        if plan_expiry is not None and claimed_at is not None and plan_expiry <= claimed_at:
            return False
        return True
    if claim_expiry is not None and plan_expiry is not None and claim_expiry == plan_expiry:
        return True
    return _same_beijing_day(claim_item.get("claimed_at"), now)


def find_claimed_plan(ledger, account_hash, plan, now, region):
    for claim_item in ledger.get("claims", []):
        if (
            claim_item.get("account") == account_hash
            and claim_item.get("region") == region
            and _claim_matches_plan(claim_item, plan, now)
        ):
            return claim_item
    return None


def latest_account_claim(ledger, account_hash, now, region, plan_id=""):
    candidates = [
        claim_item
        for claim_item in ledger.get("claims", [])
        if claim_item.get("account") == account_hash
        and claim_item.get("region") == region
        and (not plan_id or claim_item.get("plan_id") == plan_id)
    ]
    same_day = [claim_item for claim_item in candidates if _same_beijing_day(claim_item.get("claimed_at"), now)]
    if same_day:
        return max(same_day, key=lambda claim_item: claim_item["claimed_at"])
    now_ts = int(now.timestamp())
    active = [
        claim_item
        for claim_item in candidates
        if _epoch_seconds(claim_item.get("expiry")) is not None
        and _epoch_seconds(claim_item.get("expiry")) > now_ts
    ]
    if active:
        return max(active, key=lambda claim_item: claim_item["claimed_at"])
    return None


def claim_status_message(claim_item, now):
    plan_id = claim_item.get("plan_id")
    expiry = _epoch_seconds(claim_item.get("expiry"))
    if _same_beijing_day(claim_item.get("claimed_at"), now):
        message = "今日已领取: %s" % plan_id
    else:
        message = "当前无新套餐；最近已领取: %s" % plan_id
    if expiry:
        message += "（有效期至 %s）" % format_time(expiry)
    return message


def record_confirmed_claim(ledger, account_hash, plan, result, now, region):
    expiry = _epoch_seconds(plan.get("ends_at")) or _epoch_seconds(
        result.get("ends_at", result.get("endsAt")) if isinstance(result, dict) else None
    )
    claim_item = {
        "account": account_hash,
        "region": region,
        "plan_id": plan["plan_id"],
        "claimed_at": int(now.timestamp()),
        "expiry": expiry,
    }
    claims = []
    for existing in ledger.get("claims", []):
        same_period = (
            existing.get("account") == account_hash
            and existing.get("region") == region
            and existing.get("plan_id") == claim_item["plan_id"]
            and (
                _epoch_seconds(existing.get("expiry")) == expiry
                or (
                    _epoch_seconds(existing.get("expiry")) is None
                    and expiry is None
                    and _same_beijing_day(existing.get("claimed_at"), now)
                )
            )
        )
        if not same_period:
            claims.append(existing)
    claims.append(claim_item)
    ledger["claims"] = claims
    ledger = _normalize_claim_ledger(ledger, now, region)
    return save_claim_ledger(ledger, region)


def pick_plan(plans):
    wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
    if wanted:
        for plan in plans:
            if plan["plan_id"] == wanted:
                return plan
        return None
    best = None
    for plan in plans:
        if best is None or plan["priority"] > best["priority"]:
            best = plan
    return best


def _best_plan(plans):
    best = None
    for plan in plans:
        if best is None or plan.get("priority", 0) > best.get("priority", 0):
            best = plan
    return best


def plan_window_state(plan, now):
    now_ts = int(now.timestamp())
    starts_at = _epoch_seconds(plan.get("starts_at"))
    ends_at = _epoch_seconds(plan.get("ends_at"))
    if starts_at is not None and now_ts < starts_at:
        return "future"
    if ends_at is not None and now_ts >= ends_at:
        return "expired"
    return "active"


def format_time(seconds):
    if not seconds:
        return "立即"
    try:
        return datetime.fromtimestamp(int(seconds), BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(seconds)


def describe_plan(plan):
    text = plan["name"]
    if plan.get("entitlements"):
        parts = []
        for entry in plan["entitlements"]:
            unit = entry.get("unit") or ""
            grant = entry.get("grant") or 0
            period = "每日" if entry.get("period") == "daily" else "一次性"
            parts.append("%s %s%s（%s）" % (entry["name"], grant, unit, period))
        text += "：" + "，".join(parts)
    return text


def _plan_sources(plan):
    sources = plan.get("sources") or []
    return "/".join(sources) if sources else "unknown"


def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json(
            "https://www.pushplus.plus/send",
            {"token": token, "title": title, "content": text, "template": "txt"},
        )
        return answer.status_code == 200 and str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "ZCode"})
        return answer.status_code == 200 and json_of(answer).get("code") == 200
    except Exception:
        return False


def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("http"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(
            hook,
            {"msgtype": "text", "text": {"content": ("%s\n%s" % (title, content))[:2000]}},
        )
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(
                secret.encode(),
                ("%s\n%s" % (stamp, secret)).encode(),
                hashlib.sha256,
            ).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp,
                urllib.parse.quote(base64.b64encode(digest)),
            )
        answer = post_json(
            hook,
            {"msgtype": "text", "text": {"content": "%s\n%s" % (title, content)}},
        )
        return answer.status_code == 200 and json_of(answer).get("errcode") == 0
    except Exception:
        return False


def looks_like_jwt(value):
    value = (value or "").strip()
    return value.startswith("eyJ") or value.count(".") >= 2


def jwt_user_id(jwt):
    """从 JWT 载荷里取用户标识（激活事件上报用）；取不到返回空串。"""
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return ""
    for key in ("user_id", "userId", "uid", "sub", "id"):
        value = claims.get(key) if isinstance(claims, dict) else None
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    data = claims.get("data") if isinstance(claims, dict) else None
    if isinstance(data, dict):
        for key in ("id", "user_id", "uid"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def account_lines(raw):
    return [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def parse_account(line, region="cn"):
    first, sep, rest = line.partition("|")
    if sep and not looks_like_jwt(first) and looks_like_jwt(rest.partition("|")[0]):
        token, sep, rest = rest.partition("|")
    else:
        token = first
    mid, _, captcha = rest.partition("|") if sep else ("", "", "")
    token, mid = token.strip(), mid.strip()
    captcha = captcha.strip() or _env("ZCODE_CAPTCHA_PARAM")
    SECRETS.extend([token, mid, captcha])
    if not token or not looks_like_jwt(token) or any(c in token for c in "\r\n&@ "):
        raise TaskError("账号格式错误：请每行填写一个套餐 JWT，可附带设备及验证码参数")
    if not mid and not DRY:
        try:
            store = json.loads(Path(__file__).with_name("zcode_%s_devices.json" % region).read_text())
            mid = store[hashlib.sha256(token.encode()).hexdigest()[:16]]["mid"]
            if not isinstance(mid, str):
                mid = ""
        except Exception:
            mid = ""
    if not mid:
        mid = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "zcode-" + region + ":" + hashlib.sha256(token.encode()).hexdigest(),
            )
        )
    SECRETS.append(mid)
    return {
        "jwt": token,
        "device_mid": mid,
        "captcha": captcha,
        "user_id": jwt_user_id(token),
        "region": region,
    }


def log_identities(payload):
    data = payload.get("data")
    if not isinstance(data, dict):
        return
    identities = [data.get("user"), data.get("account"), data]
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        for key in ("nickname", "username", "display_name", "displayName", "public_uid", "user_id", "uid"):
            value = identity.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                log(
                    "👤 官方账号身份 "
                    + key
                    + ": "
                    + safe(value, public_uid=key in ("public_uid", "user_id", "uid"))
                )


def verify_claim(response, selected, captcha):
    """只接受参考源码确认的业务码；不信任远端错误文本。"""
    payload = json_of(response)
    code = payload.get("code")
    if response.status_code == 200 and type(code) is int and code == 1003:
        log_identities(payload)
        log("☑️ ALREADY_COMPLETE：官方确认该账号已领取本期套餐")
        return "alreadyComplete", payload
    if response.status_code != 200 or type(code) is not int or code != 0:
        label = FAILURE_LABELS.get(code) if isinstance(code, int) else None
        hints = ""
        if type(code) is int and code == 1005:
            data = payload.get("data")
            plan = data.get("plan") if isinstance(data, dict) else None
            if isinstance(plan, dict):
                ends = plan.get("ends_at", plan.get("endsAt"))
                if isinstance(ends, (int, float)) and not isinstance(ends, bool):
                    try:
                        retry_at = datetime.fromtimestamp(ends, BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
                        hints = "；下轮重试不早于 " + retry_at
                    except (ValueError, OverflowError, OSError):
                        pass
        if type(code) is int and code == 3007 and not captcha:
            hints += "；从浏览器 claim 请求获取验证码，填入账号行末段或 ZCODE_CAPTCHA_PARAM"
        if type(code) is int and code == 3001:
            hints += "；检查设备值、客户端版本及验证码有效期"
        raise TaskError(
            "套餐领取失败："
            + (label or "业务响应未确认成功")
            + "（HTTP %d）" % response.status_code
            + hints
        )
    log_identities(payload)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TaskError("领取响应缺少有效 data")
    plan = data.get("plan")
    if not isinstance(plan, dict) or not plan:
        raise TaskError("领取响应缺少有效套餐，未确认成功")
    returned_id = first_text(plan.get("plan_id"), plan.get("planId"))
    if returned_id and returned_id != selected["plan_id"]:
        raise TaskError("返回套餐与目标不一致")
    log(
        "✅ CLAIM_SUCCESS：领取成功；"
        + safe(selected["name"])
        + "（"
        + safe(format_time(plan.get("starts_at", plan.get("startsAt"))))
        + " ~ "
        + safe(format_time(plan.get("ends_at", plan.get("endsAt"))))
        + "）"
    )
    return "success", payload


def run_account(account, args, index):
    stats = {"total": 0, "success": 0, "alreadyComplete": 0, "skipped": 0, "failure": 0}
    started = time.monotonic()

    def stage(number, title, action=None):
        stamp = time.monotonic()
        stats["total"] += 1
        log("账号%d 阶段%d：%s" % (index, number, title))
        try:
            if action is None:
                stats["skipped"] += 1
                log("⏭️ 已跳过；耗时 %.2fs" % (time.monotonic() - stamp))
                return None
            result = action()
            completed = isinstance(result, str) and result == "alreadyComplete"
            stats["alreadyComplete" if completed else "success"] += 1
            log(
                ("☑️ 阶段已完成" if completed else "✅ 阶段完成")
                + "；耗时 %.2fs" % (time.monotonic() - stamp)
            )
            return result
        except Exception as error:
            stats["failure"] += 1
            msg = str(error) if isinstance(error, TaskError) else "处理异常（原始内容已隐藏）"
            log("❌ " + safe(msg) + "；耗时 %.2fs" % (time.monotonic() - stamp))
            raise TaskError(msg) from None

    try:
        if DRY:
            stage(1, "断网参数预演", lambda: log("DRY_RUN_OK：参数已解析，未发送请求或写入设备/台账文件"))
            stage(2, "激活事件预演（不发送）")
            stage(3, "套餐预览、营销活动位及领取预演（不发送）")
            stage(4, "营销回执与台账预演（不发送）")
        else:
            if args.preview or _env("ZCODE_ACTIVATION") != "1":
                stage(1, "激活事件（默认关闭，预览模式始终关闭）")
            else:

                def activate():
                    if not account["user_id"]:
                        raise TaskError("JWT 缺少用户标识，无法补报激活事件")
                    for event in ("app_launch", "app_daily_active"):
                        response = request(
                            "POST",
                            ORIGIN + EVENT_REPORT_PATH,
                            body=activation_event_body(event, account["user_id"], account["device_mid"]),
                            timeout=10,
                        )
                        payload = json_of(response)
                        if (
                            response.status_code != 200
                            or type(payload.get("code")) is not int
                            or payload["code"] != 0
                        ):
                            raise TaskError("激活事件未确认成功")
                        log("✅ " + event + " 已确认")

                try:
                    stage(1, "显式补报激活事件", activate)
                except TaskError:
                    pass

            region = account["region"]
            ledger = load_claim_ledger(region)
            account_hash = stable_account_hash(account)

            def inspect_and_claim():
                now = beijing_now()
                billing = query_billing_plans(account["jwt"], account["device_mid"])
                marketing = query_marketing_plans(account["jwt"], account["device_mid"])
                plans = merge_plan_sources(billing.get("plans", []), marketing.get("plans", []))
                warning = source_warning(("billing", billing), ("marketing", marketing))
                for plan in plans:
                    log(
                        "套餐："
                        + safe(describe_plan(plan))
                        + "；来源 "
                        + safe(_plan_sources(plan))
                        + "；有效期 "
                        + safe(format_time(plan["starts_at"]))
                        + " ~ "
                        + safe(format_time(plan["ends_at"]))
                    )
                log(
                    "✅ PREVIEW_SUCCESS：已验证套餐来源；billing=%s marketing=%s 合并套餐数 %d%s"
                    % (
                        "ok" if billing.get("ok") else "fail",
                        "ok" if marketing.get("ok") else ("skip" if marketing.get("skipped") else "fail"),
                        len(plans),
                        safe(warning),
                    )
                )
                if args.preview:
                    return "preview"

                wanted = os.environ.get("ZCODE_PLAN_ID", "").strip()
                if not plans:
                    ledger_claim = latest_account_claim(ledger, account_hash, now, region, wanted)
                    if ledger_claim is None and wanted:
                        ledger_claim = latest_account_claim(ledger, account_hash, now, region)
                    if ledger_claim is not None:
                        log("📒 服务端两来源为空，本地台账确认已有领取记录")
                        log("☑️ ALREADY_COMPLETE：" + safe(claim_status_message(ledger_claim, now)))
                        return "alreadyComplete"
                    if warning:
                        raise TaskError("套餐来源查询未完成且本地台账无命中%s" % warning)
                    raise TaskError("现在没有可领取的套餐，未确认领取成功")

                target = pick_plan(plans)
                if target is None:
                    ledger_claim = latest_account_claim(ledger, account_hash, now, region, wanted)
                    if ledger_claim is not None:
                        log("☑️ ALREADY_COMPLETE：" + safe(claim_status_message(ledger_claim, now)))
                        return "alreadyComplete"
                    if warning:
                        raise TaskError("指定套餐未在完整来源中确认%s" % warning)
                    raise TaskError("指定的 ZCODE_PLAN_ID 不在可领列表")

                target_claim = find_claimed_plan(ledger, account_hash, target, now, region)
                if wanted and target_claim is not None:
                    log("📒 本地台账确认该活动期已领取，跳过重复请求")
                    note = finalize_marketing_claim(account, target, preview_only=False)
                    log("☑️ ALREADY_COMPLETE：" + safe(claim_status_message(target_claim, now) + note))
                    return "alreadyComplete"

                candidates = [target] if wanted else plans
                claimed_candidates = []
                available = []
                for candidate in candidates:
                    claim_record = find_claimed_plan(ledger, account_hash, candidate, now, region)
                    if claim_record is None:
                        available.append(candidate)
                    else:
                        claimed_candidates.append((candidate, claim_record))
                if not available:
                    candidate, claim_record = claimed_candidates[0]
                    note = finalize_marketing_claim(account, candidate, preview_only=False)
                    log("📒 当前套餐活动期均已在本地台账确认")
                    log("☑️ ALREADY_COMPLETE：" + safe(claim_status_message(claim_record, now) + note))
                    return "alreadyComplete"

                future, active, expired = [], [], []
                for candidate in available:
                    state = plan_window_state(candidate, now)
                    if state == "future":
                        future.append(candidate)
                    elif state == "expired":
                        expired.append(candidate)
                    else:
                        active.append(candidate)
                if not active:
                    if future:
                        plan = min(future, key=lambda item: item.get("starts_at") or 0)
                        raise TaskError(
                            "活动窗口未开启: %s（北京时间 %s 开启）%s"
                            % (plan["name"], format_time(plan.get("starts_at")), warning)
                        )
                    plan = _best_plan(expired)
                    raise TaskError(
                        "活动已结束: %s（北京时间 %s 结束）%s"
                        % (plan["name"], format_time(plan.get("ends_at")), warning)
                    )

                selected = _best_plan(active)
                log(
                    "目标套餐："
                    + safe(describe_plan(selected))
                    + "；来源 "
                    + safe(_plan_sources(selected))
                )
                response = claim(
                    account["jwt"],
                    selected["plan_id"],
                    account["device_mid"],
                    account["captcha"],
                )
                outcome, payload = verify_claim(response, selected, account["captcha"])
                result_plan = {}
                data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(data, dict) and isinstance(data.get("plan"), dict):
                    result_plan = data["plan"]
                saved, save_error = record_confirmed_claim(
                    ledger, account_hash, selected, result_plan, beijing_now(), region
                )
                if not saved:
                    log("⚠️ 本地领取台账保存失败: %s" % save_error)
                note = finalize_marketing_claim(account, selected, preview_only=False)
                if note:
                    log("营销收尾：" + safe(note.lstrip("；")))
                if warning:
                    log("来源提示：" + safe(warning.lstrip("；")))
                return outcome

            result = stage(2, "读取 billing/marketing 套餐并领取", inspect_and_claim)
            if args.preview or result == "preview":
                stage(3, "只读预览，未领取")
                stage(4, "营销回执与台账（预览跳过）")
            elif result == "alreadyComplete":
                stage(3, "领取已由官方或本地台账确认", lambda: "alreadyComplete")
                stage(4, "营销收尾已在领取阶段处理", lambda: "alreadyComplete")
            else:
                stage(3, "套餐领取已确认", lambda: "ok")
                stage(4, "营销回执与台账已处理", lambda: "ok")
    except TaskError:
        pass
    stats["elapsedSeconds"] = round(time.monotonic() - started, 2)
    log(
        ("账号%d 统计：" % index)
        + (
            "总任务 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failure)d；耗时 %(elapsedSeconds).2fs"
            % stats
        )
    )
    return stats


def notification_selected():
    switch = _env("QINGLONG_NOTIFY").lower() or "auto"
    if switch in ("0", "false", "no", "off"):
        return False
    if "QINGLONG_NOTIFY_SCRIPTS" in os.environ:
        selectors = re.split(r"[,;\s]+", _env("QINGLONG_NOTIFY_SCRIPTS"))
        identities = (
            "a0a7b04503bfb900",
            "zcode_cn_daily.py",
            "zcode_intl_daily.py",
            "checkin/zcode_cn_daily.py",
            "checkin/zcode_intl_daily.py",
            "candidates/a0a7b04503bfb900/zcode_cn_daily.py",
            Path(__file__).name,
        )
        return any(
            fnmatch.fnmatchcase(identity, selector)
            for selector in selectors
            if selector
            for identity in identities
        )
    return switch in ("1", "true", "yes", "on")


def deliver_notification(title, content, disabled=False):
    if disabled or not notification_selected():
        log("⏭️ 通知已关闭")
        return "disabled"
    if DRY:
        log("✅ 通知预演：" + content)
        return "simulated"
    dirs = [Path(__file__).parent]
    configured = _env("QINGLONG_NOTIFY_DIR")
    if configured:
        dirs.append(Path(configured))
    dirs += [Path("/ql/data/scripts"), Path("/ql/scripts")]
    candidates = [p / "notify.py" for p in dirs]
    try:
        spec = importlib.util.find_spec("notify")
    except (ImportError, ValueError, AttributeError):
        spec = None
    if spec and spec.origin:
        candidates.insert(0, Path(spec.origin))
    runner = (
        "import importlib.util,json,sys; p,t,c=json.load(sys.stdin); "
        's=importlib.util.spec_from_file_location("notify",p); m=importlib.util.module_from_spec(s); '
        'sys.path.insert(0,str(__import__("pathlib").Path(p).parent)); s.loader.exec_module(m); '
        "r=m.send(t,c); sys.exit(1 if r is False else 0)"
    )
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-c", runner],
                input=json.dumps([str(path), title, content]),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if result.returncode == 0:
                log("✅ 青龙通知已调用")
                return "sent"
        except Exception:
            pass
    js_runner = (
        'const fs=require("fs"); const [p,t,c]=JSON.parse(fs.readFileSync(0,"utf8")); '
        "Promise.resolve().then(()=>require(p).sendNotify(t,c))"
        ".then(r=>{process.exitCode=r===false?1:0}).catch(()=>{process.exitCode=1});"
    )
    for path in dict.fromkeys(p / "sendNotify.js" for p in dirs):
        if not path.is_file():
            continue
        try:
            result = subprocess.run(
                ["node", "-e", js_runner],
                input=json.dumps([str(path.resolve()), title, content]),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if result.returncode == 0:
                log("✅ 青龙 JavaScript 通知已调用")
                return "sent"
        except Exception:
            pass
    for handler in (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk):
        if handler(title, content):
            log("✅ 兼容推送已发送")
            return "sent"
    endpoint, token = _env("QL_URL").rstrip("/"), _env("QL_TOKEN")
    if endpoint and token:
        try:
            response = post_json(
                endpoint + "/api/system/notify?" + urllib.parse.urlencode({"token": token}),
                {"title": title, "content": content},
                timeout=15,
            )
            if response.status_code == 200 and str(response.json().get("code")) in ("0", "200"):
                log("✅ 青龙接口通知已发送")
                return "sent"
        except Exception:
            pass
    log("⚠️ 通知不可用或发送失败；保留业务退出码")
    return "unavailable"


def main():
    global DRY
    DRY = any(
        _env(name).lower() in ("1", "true", "yes", "on")
        for name in ("ZCODE_CN_DRY_RUN", "ZCODE_INTL_DRY_RUN")
    )
    started = time.monotonic()
    log("======== ZCode 套餐领取（国内及国际版） ========")
    log("开始时间：" + beijing_now().isoformat(timespec="seconds"))
    log("模式：" + ("断网预演" if DRY else "实际执行"))
    lines = []
    for name in (
        "ZCODE_CAPTCHA_PARAM",
        "PUSHPLUS_TOKEN",
        "BARK_URL",
        "WECOM_WEBHOOK",
        "DINGTALK_WEBHOOK",
        "DINGTALK_SECRET",
        "QL_TOKEN",
    ):
        SECRETS.append(_env(name))
    results, config_error, no_notify = [], False, "--no-notify" in sys.argv[1:]
    parser = argparse.ArgumentParser(description="ZCode 套餐领取（默认国内版，可显式选择国际版）")
    parser.add_argument("--region", choices=("cn", "intl", "all"), default=_env("ZCODE_REGION") or "cn")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--only", type=int)
    parser.add_argument("--no-notify", action="store_true")
    try:

        class QuietParser(argparse.ArgumentParser):
            def error(self, message):
                raise TaskError(
                    "命令参数错误：支持 --region cn/intl/all、--preview、--only 正整数、--no-notify"
                )

        parser.__class__ = QuietParser
        args = parser.parse_args()
        if args.region not in ("cn", "intl", "all"):
            raise TaskError("ZCODE_REGION 仅支持 cn、intl 或 all")
        regions = ("cn", "intl") if args.region == "all" else (args.region,)
        lines = [
            (region, line)
            for region in regions
            for line in account_lines(os.environ.get("ZCODE_%s_TOKENS" % region.upper(), ""))
        ]
        log("区域：%s；账号总数：%d" % (args.region, len(lines)))
        if not lines:
            raise TaskError(
                "所选区域未配置账号：国内版用 ZCODE_CN_TOKENS，国际版用 ZCODE_INTL_TOKENS，每行一个套餐 JWT"
            )
        if args.only is not None and not 1 <= args.only <= len(lines):
            raise TaskError("--only 超出账号范围")
        if _env("ZCODE_ACTIVATION") not in ("", "0", "1"):
            raise TaskError("ZCODE_ACTIVATION 仅支持 0 或 1")
        if _env("ZCODE_MARKETING_RECHECK") not in ("", "0", "1"):
            raise TaskError("ZCODE_MARKETING_RECHECK 仅支持 0 或 1")
        for index, (region, line) in enumerate(lines, 1):
            if args.only is not None and index != args.only:
                continue
            log("-------- 账号%d（%s） --------" % (index, "国内版" if region == "cn" else "国际版"))
            try:
                account = parse_account(line, region)
                stats = run_account(account, args, index)
            except Exception as error:
                log("❌ 阶段0：" + (safe(error) if isinstance(error, TaskError) else "参数处理异常"))
                stats = {
                    "total": 1,
                    "success": 0,
                    "alreadyComplete": 0,
                    "skipped": 0,
                    "failure": 1,
                    "elapsedSeconds": 0,
                }
                log("账号%d 统计：总任务1，成功0，已完成0，跳过0，失败1；耗时0s" % index)
            results.append({"account": index, "region": region, **stats})
    except TaskError as error:
        config_error = True
        log("账号总数：%d" % len(lines))
        log("❌ 阶段0：配置检查失败；" + safe(error) + "；耗时 %.2fs" % (time.monotonic() - started))
    failure = sum(r["failure"] > 0 for r in results)
    success = len(results) - failure
    exit_code = 1 if config_error or failure else 0
    status = (
        "configuration-error"
        if config_error
        else (
            "partial-failure"
            if failure and success
            else "failure"
            if failure
            else "dry-run"
            if DRY
            else "success"
        )
    )
    task_stats = {
        key: sum(r[key] for r in results)
        for key in ("total", "success", "alreadyComplete", "skipped", "failure")
    }
    summary = {
        "status": status,
        "mode": "dry-run" if DRY else "live",
        "accountCount": len(lines),
        "processedAccounts": len(results),
        "successAccounts": success,
        "failedAccounts": failure,
        "configurationError": config_error,
        "tasks": task_stats,
        "accounts": results,
        "exitCode": exit_code,
    }
    log("------------------------------------")
    log("任务统计：账号总数 %d，处理 %d，成功 %d，失败 %d" % (len(lines), len(results), success, failure))
    log("子任务统计：" + json.dumps(task_stats, ensure_ascii=False))
    content = "账号总数 %d，处理 %d，成功 %d，失败 %d；配置错误 %s；状态 %s" % (
        len(lines),
        len(results),
        success,
        failure,
        "是" if config_error else "否",
        status,
    )
    try:
        summary["notification"] = deliver_notification("ZCode 套餐领取", content, no_notify)
    except Exception:
        summary["notification"] = "unavailable"
        log("⚠️ 通知异常；保留业务退出码")
    summary["elapsedSeconds"] = round(time.monotonic() - started, 2)
    summary["finishedAt"] = beijing_now().isoformat(timespec="seconds")
    log(
        "总耗时 %.2fs；完成时间 %s；通知状态 %s；最终状态 %s"
        % (summary["elapsedSeconds"], summary["finishedAt"], summary["notification"], status)
    )
    print("TASK_SUMMARY=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
