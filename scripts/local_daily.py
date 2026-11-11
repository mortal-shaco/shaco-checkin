#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WorkBuddy 每日签到
# cron: 38 10 * * *
# 原签到调度 30 9 * * * 仍可由青龙独立配置。
# 合并来源：suows/workbuddy-auto-checkin scripts/checkin.py，MIT。
# 合并来源：JackieZheng/xueren-workbuddy-checkin scripts/workbuddy_checkin.py，MIT。
# SPDX-License-Identifier: MIT
# 来源：Peng-Can/local-daily-checkin，checkin.py，MIT。
"""WorkBuddy 每日签到，Python 标准库独立实现。

WORKBUDDY_ACCOUNTS：每个非空行一个账号，格式 uid|accessToken，仅分割首个 |。
在本人 WorkBuddy 已登录会话的开发者工具 Network 中查看签到状态请求，
复制 X-User-Id 和 Authorization 中 Bearer 后的值；不要分享请求或凭据。
兼容单账号 WORKBUDDY_ACCESS_TOKEN + WORKBUDDY_UID；优先使用合并变量。
默认执行 run；status 仅查询；--json 保留逐账号 JSON 输出。
WORKBUDDY_DRY_RUN=1 完全断网预演。调度由青龙负责，沿用维护版本发布计划每日 10:38，亦兼容原每日 09:30。
--status 等价于 status；--verify-wallet 显式启用真实余额与本次资源包增长核验。
该开关在 status 模式只读余额，run 模式领取后确认增长，余额读取失败即失败。
credits（或 --expire）只读查询逐笔积分到期；--expiring-days N 筛选临期，--html 输出安全 HTML。
该入口按上游依次查询资源汇总及付费、免费发放记录，时间统一为北京时间。
余额快照仅保留在内存中。成长、补登、兑换和模型对话由已有维护脚本提供。
不扫描进程、不读客户端文件、不安装自启动、不改代理、不落盘凭据。

MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
        _ql_notify_identities = ('022a9a680ac352c1', 'scripts/local_daily.py', 'local_daily.py', 'local_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import argparse
import fnmatch
import json
import hashlib
import html
import math
from typing import Any
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

TITLE = 'WorkBuddy 每日签到'
CATALOG_ID = '022a9a680ac352c1'
BASES = ('https://www.codebuddy.cn/v2/billing/meter/',
         'https://copilot.tencent.com/v2/billing/meter/')
WALLET_PAGE_SIZE = 100
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    def __init__(self, message, retryable=False, fallback=False):
        super().__init__(message)
        self.retryable = retryable
        self.fallback = fallback


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def field(data, *names):
    for name in names:
        if name in data:
            return data[name]
    return None


def describe(payload):
    if not isinstance(payload, dict):
        raise TaskError('接口结构异常')
    code = field(payload, 'code', 'Code', 'retcode')
    if type(code) not in (int, str) or code not in (0, '0', 200, '200', 10001, '10001'):
        raise TaskError('业务状态失败或缺少明确成功码')
    data = payload.get('data', payload)
    if not isinstance(data, dict):
        raise TaskError('业务数据结构异常')
    checked = field(data, 'today_checked_in', 'todayCheckedIn', 'today_checked')
    if type(checked) is bool:
        pass
    elif type(checked) in (str, int) and checked in (0, 1, '0', '1', 'true', 'false'):
        checked = checked in (1, '1', 'true')
    else:
        checked = None
    def integer(*names):
        value = field(data, *names)
        return value if type(value) is int else None
    return {
        'code': code, 'checked_in': checked,
        'reward': integer('today_credit', 'credit', 'points', 'reward', 'amount', 'credits', 'todayCredit', 'daily_credit'),
        'streak_days': integer('streak_days', 'streakDays', 'continuousDays'),
        'total_credits': integer('total_credits', 'totalCredits', 'total_credit', 'accumulated_credit'),
        'streak_bonus': integer('streak_bonus_credit', 'streakBonusCredit'),
        'checked_dates': [v for v in (field(data, 'checkin_dates', 'checkinDates') or [])
                          if isinstance(v, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', v)]
                         if isinstance(field(data, 'checkin_dates', 'checkinDates'), list) else [],
        'active': field(data, 'active'),
        'identity': field(data, 'nickname', 'username', 'displayName', 'display_name', 'uid'),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不允许重定向把凭据带往另一个入口。
        return None


class ApiClient:
    def __init__(self, uid, token, timeout):
        self.uid, self.token, self.timeout = uid, token, timeout
        self.base = BASES[0]
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, action, base, payload=None):
        request = urllib.request.Request(base + action,
            data=json.dumps({} if payload is None else payload).encode('utf-8'),
            method='POST', headers={
                'Authorization': 'Bearer ' + self.token, 'X-User-Id': self.uid,
                'Content-Type': 'application/json', 'Accept': 'application/json',
                'User-Agent': 'WorkBuddy-LocalCheckin/1.0.0',
            })
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise TaskError('响应超过大小限制')
                body = json.loads(raw)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            retryable = code in (408, 429, 500, 502, 503, 504)
            raise TaskError(f'HTTP {code} 请求失败', retryable,
                            retryable or code in (404, 405)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络连接失败或超时', True, True) from None
        except (ValueError, UnicodeError):
            raise TaskError('接口未返回有效 JSON', fallback=True) from None
        if not isinstance(body, dict):
            raise TaskError('接口结构异常', fallback=True)
        return body

    def post(self, action):
        return describe(self.request(action, self.base))

    def status(self, attempts):
        for attempt in range(attempts):
            last_error = None
            for base in BASES:
                for path in ('checkin-activity-status', 'checkin-status'):
                    try:
                        info = describe(self.request(path, base))
                        if info['code'] in (10001, '10001') or info['checked_in'] is None:
                            raise TaskError('状态接口缺少有效的今日签到状态', fallback=True)
                        self.base = base
                        return info
                    except TaskError as exc:
                        if not exc.fallback:
                            raise
                        # 保留本轮临时错误，以便在全部只读入口失败时有限重试。
                        if last_error is None or exc.retryable:
                            last_error = exc
            if not last_error.retryable or attempt + 1 == attempts:
                raise last_error
            delay = (5, 15, 45)[attempt]
            log(f'状态查询临时失败，{delay} 秒后重试（{attempt + 1}/{attempts}）')
            time.sleep(delay)

    def wallet(self):
        payload = {'PageNumber': 1, 'PageSize': WALLET_PAGE_SIZE,
                   'ProductCode': 'p_tcaca', 'Status': [0, 3], 'OnlyValidPeriod': True}
        for base in BASES:
            try:
                body = self.request('get-user-resource', base, payload)
                code = body.get('code')
                if type(code) not in (str, int) or code not in (0, '0', 200, '200'):
                    raise TaskError('余额接口缺少明确成功码或业务失败')
                return parse_wallet_body(body)
            except TaskError as exc:
                if not exc.fallback or base == BASES[-1]:
                    raise



    def credit_packages(self):
        # 上游逐笔接口位于根路径，不能复用余额接口的 /v2 前缀。
        roots = tuple(base.replace('/v2/billing/', '/billing/') for base in BASES)
        for base in roots:
            try:
                return read_credit_packages(self, base)
            except TaskError as exc:
                if not exc.fallback or base == roots[-1]:
                    raise


def credit_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        if not math.isfinite(number):
            return None
        return int(number) if number.is_integer() else number
    return None


def add_credit(left: int | float, right: int | float) -> int | float:
    total = left + right
    if isinstance(total, float) and total.is_integer():
        return int(total)
    return total


def sub_credit(after: int | float, before: int | float) -> int | float:
    return add_credit(after, -before)


def _walk_path(body: dict[str, Any], path: tuple[str, ...]) -> tuple[Any, dict[str, Any] | None]:
    node: Any = body
    parent: dict[str, Any] | None = None
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None, None
        parent = node
        node = node[key]
    return node, parent


def extract_wallet_accounts(body: dict[str, Any]) -> tuple[list[Any] | None, int | float | None]:
    paths = (
        ("data", "Response", "Data", "Accounts"),
        ("data", "data", "Response", "Data", "Accounts"),
        ("Response", "Data", "Accounts"),
        ("data", "resources"),
        ("data", "data", "resources"),
        ("resources",),
    )
    for path in paths:
        node, parent = _walk_path(body, path)
        if not isinstance(node, list):
            continue
        total_count = None
        if isinstance(parent, dict):
            total_count = credit_number(
                parent.get("TotalCount") if parent.get("TotalCount") is not None else parent.get("totalCount")
            )
        return node, total_count
    return None, None


def parse_wallet_body(body: dict[str, Any]) -> dict[str, Any]:
    """把 get-user-resource 的有效资源包剩余额度加总。用过的包（Status=3）不算进当前总额。"""
    accounts, total_count = extract_wallet_accounts(body)
    if accounts is None:
        raise TaskError(
            "get-user-resource 响应里没有资源包列表，不能把签到接口的本期累计当成账户总额",
            False,
        )
    if len(accounts) >= WALLET_PAGE_SIZE and (total_count is None or total_count > len(accounts)):
        raise TaskError(
            "真实余额资源包超过一页，没有把残缺合计当成当前总额",
            False,
        )
    total: int | float = 0
    packages = 0
    items: list[dict[str, Any]] = []
    for item in accounts:
        if not isinstance(item, dict):
            raise TaskError("真实余额的资源包格式无效", False)
        status = credit_number(item.get("Status") if item.get("Status") is not None else item.get("status"))
        if status not in (None, 0):
            continue
        size = credit_number(
            item.get("CycleCapacitySizePrecise")
            if item.get("CycleCapacitySizePrecise") is not None
            else item.get("CycleCapacitySize")
            if item.get("CycleCapacitySize") is not None
            else item.get("CapacitySizePrecise")
            if item.get("CapacitySizePrecise") is not None
            else item.get("CapacitySize")
            if item.get("CapacitySize") is not None
            else item.get("total")
            if item.get("total") is not None
            else item.get("limitNum")
            if item.get("limitNum") is not None
            else item.get("limit_num")
        )
        remain = credit_number(
            item.get("CycleCapacityRemainPrecise")
            if item.get("CycleCapacityRemainPrecise") is not None
            else item.get("CycleCapacityRemain")
            if item.get("CycleCapacityRemain") is not None
            else item.get("CapacityRemainPrecise")
            if item.get("CapacityRemainPrecise") is not None
            else item.get("CapacityRemain")
            if item.get("CapacityRemain") is not None
            else item.get("remaining")
            if item.get("remaining") is not None
            else item.get("remain")
        )
        if size is None or remain is None or size < 0 or remain < 0:
            raise TaskError(
                "真实余额里有无法使用的资源包读数，没有用残缺合计当成当前总额",
                False,
            )
        total = add_credit(total, remain)
        packages += 1
        items.append(_package_view(item, size, remain))
    return {"total": total, "packages": packages, "items": items}


def _short_hash(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _first_text(item: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return ""


def _norm_time(value: str) -> str:
    text = value.strip().replace("T", " ")
    if "." in text:
        text = text.split(".", 1)[0]
    if text.endswith("Z"):
        text = text[:-1]
    return text


def _package_view(item: dict[str, Any], size: int | float, remain: int | float) -> dict[str, Any]:
    """资源包只留比对用的键和额度。账号类原始编号只做哈希，不进账本。"""
    identity = ""
    for field in ("ResourceId", "resourceId", "PkgId", "PackageId", "packageId", "DealName", "dealName"):
        identity = _first_text(item, field)
        if identity:
            key = "id:" + _short_hash(field, identity)
            break
    else:
        for field in ("AccountId", "accountId"):
            identity = _first_text(item, field)
            if identity:
                key = "acct:" + _short_hash(identity)
                break
        else:
            code = _first_text(item, "PackageCode", "packageCode", "package_code")
            start = _norm_time(
                _first_text(item, "DeductionStartTime", "PackageStartTime", "CycleStartTime", "BeginTime")
            )
            end = _norm_time(
                _first_text(
                    item,
                    "DeductionEndTime",
                    "PackageEndTime",
                    "ExpiredTime",
                    "CycleEndTime",
                )
            )
            key = "pkg:" + _short_hash(code, start, end) if code or start or end else "anon"
    end = _norm_time(
        _first_text(
            item,
            "DeductionEndTime",
            "PackageEndTime",
            "ExpiredTime",
            "CycleEndTime",
            "end",
        )
    )
    return {"key": key, "size": size, "remain": remain, "end": end}


def _package_groups(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        grouped.setdefault(str(item["key"]), []).append(item)
    for group in grouped.values():
        group.sort(key=lambda row: (credit_number(row.get("size")) or 0, credit_number(row.get("remain")) or 0, str(row.get("end") or "")))
    return grouped


def _pair_package_delta(before: dict[str, Any], after: dict[str, Any]) -> tuple[int | float, int | float]:
    """同一资源包上，新增额度算增长，缩掉或换期留下的剩余算失效，花掉的不算。"""
    before_size = credit_number(before.get("size")) or 0
    after_size = credit_number(after.get("size")) or 0
    before_remain = credit_number(before.get("remain")) or 0
    after_remain = credit_number(after.get("remain")) or 0
    before_end = str(before.get("end") or "")
    after_end = str(after.get("end") or "")
    if before_end and after_end and before_end != after_end:
        return after_size, before_remain
    growth: int | float = 0
    expired: int | float = 0
    if after_size > before_size:
        growth = sub_credit(after_size, before_size)
    elif after_size < before_size and before_remain > after_remain:
        shrink = sub_credit(before_size, after_size)
        remain_drop = sub_credit(before_remain, after_remain)
        expired = shrink if shrink < remain_drop else remain_drop
    return growth, expired


def diff_packages(
    before_items: list[dict[str, Any]],
    after_items: list[dict[str, Any]],
) -> tuple[int | float, int | float]:
    """增长额是新出现或变大的额度。消失的剩余额度记为失效，不从增长额里扣掉。"""
    before_groups = _package_groups(before_items)
    after_groups = _package_groups(after_items)
    growth: int | float = 0
    expired: int | float = 0
    for key in set(before_groups) | set(after_groups):
        previous = before_groups.get(key, [])
        current = after_groups.get(key, [])
        paired = min(len(previous), len(current))
        for index in range(paired):
            gained, lapsed = _pair_package_delta(previous[index], current[index])
            growth = add_credit(growth, gained)
            expired = add_credit(expired, lapsed)
        for extra in current[paired:]:
            growth = add_credit(growth, credit_number(extra.get("size")) or 0)
        for missing in previous[paired:]:
            expired = add_credit(expired, credit_number(missing.get("remain")) or 0)
    return growth, expired



BEIJING = timezone(timedelta(hours=8))


def package_time(value):
    """官方无时区时间按北京时间解析，兼容秒、毫秒和 ISO 时间。"""
    number = credit_number(value)
    if number is not None:
        timestamp = number / 1000 if number > 100000000000 else number
        try:
            datetime.fromtimestamp(timestamp, BEIJING)
            return timestamp
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BEIJING)
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def format_package_time(value):
    return datetime.fromtimestamp(value, BEIJING).strftime('%Y-%m-%d %H:%M:%S') if value is not None else None


def credit_data(body):
    if type(body.get('code')) not in (int, str) or body['code'] not in (0, '0'):
        raise TaskError('积分到期接口业务失败或缺少明确成功码')
    data = body.get('data')
    if not isinstance(data, dict):
        raise TaskError('积分到期接口缺少有效数据')
    return data


def safe_credit_text(value, client):
    if not isinstance(value, str):
        return ''
    value = value.replace(client.token, '[凭据已隐藏]').replace(client.uid, '[账号字段已隐藏]')
    value = re.sub(r'(?i)bearer\s+\S+|eyJ[\w.=-]+|(?:\+?86)?1[3-9]\d{9}', '[敏感内容已隐藏]', value)
    return re.sub(r'[\x00-\x1f\x7f]', ' ', value)[:160]


def read_credit_packages(client, base):
    data = credit_data(client.request('get-user-resource-summary', base))
    identity({'identity': field(data, 'nickname', 'username', 'displayName', 'display_name', 'uid')}, client.uid, client.token)
    packages = data.get('Packages')
    if not isinstance(packages, list):
        raise TaskError('资源汇总缺少包代码列表')
    codes = []
    for package in packages:
        if not isinstance(package, dict) or not isinstance(package.get('PackageCode'), str) or not package['PackageCode']:
            raise TaskError('资源包代码格式异常')
        if package['PackageCode'] not in codes:
            codes.append(package['PackageCode'])
    rows, seen = [], set()
    now = time.time()
    # 两类记录都读完才报告完整成功，分页有界，超限时失败闭合。
    for action in ('get-user-resource-paid-packages', 'get-user-resource-free-packages') if codes else ():
        endpoint_seen = set()
        for page in range(1, 51):
            payload = dict(PageNumber=page, PageSize=200, PackageCodes=codes,
                           Status=[0, 3], IsDisplayTotalInfo=True)
            data = credit_data(client.request(action, base, payload))
            accounts = data.get('Accounts')
            count = credit_number(data.get('TotalCount'))
            if not isinstance(accounts, list) or len(accounts) > 200:
                raise TaskError('逐笔资源包列表无效')
            if count is not None and (count < 0 or count != int(count)):
                raise TaskError('逐笔资源包总数无效')
            for item in accounts:
                if not isinstance(item, dict):
                    raise TaskError('逐笔资源包结构异常')
                key = tuple(_first_text(item, name) for name in ('AccountId', 'PackageCode', 'CycleStartTime'))
                if not key[0] or not key[1]:
                    raise TaskError('逐笔资源包缺少去重标识')
                if key in endpoint_seen:
                    raise TaskError('逐笔资源包分页重复，无法确认完整结果')
                endpoint_seen.add(key)
                if key in seen:
                    continue
                seen.add(key)
                remain = credit_number(field(item, 'CycleCapacityRemainPrecise', 'CycleCapacityRemain'))
                total = credit_number(field(item, 'CycleCapacitySizePrecise', 'CycleCapacitySize'))
                status = credit_number(item.get('Status'))
                if remain is None or total is None or remain < 0 or total < 0 or status not in (0, 3):
                    raise TaskError('逐笔资源包额度或状态无效')
                expiry = None
                expiry_source = None
                for name in ('DeductionEndTime', 'CycleEndTime', 'ExpiredTime'):
                    expiry = package_time(item.get(name))
                    if expiry is not None:
                        expiry_source = name
                        break
                refresh = package_time(item.get('CycleEndTime'))
                source = {}
                for attribute in item.get('AccountAttributes') or []:
                    if isinstance(attribute, dict) and attribute.get('Key') in ('grantReason', 'grantSource'):
                        source[attribute['Key']] = safe_credit_text(attribute.get('Value'), client)
                state = '已用完' if status == 3 or remain == 0 else '使用中' if remain < total else '未使用'
                rows.append(dict(remain=remain, total=total, status=status, state=state,
                                 source=source.get('grantReason') or source.get('grantSource') or '未知来源',
                                 expire_ts=expiry, expire_at=format_package_time(expiry),
                                 expire_source=expiry_source, refresh_at=format_package_time(refresh),
                                 expire_kind='周期刷新' if refresh is not None and expiry is not None and refresh < expiry else '到期失效',
                                 days_left=math.floor((expiry - now) / 86400) if expiry is not None else None))
            received = (page - 1) * 200 + len(accounts)
            if count is not None and received > count:
                raise TaskError('逐笔资源包总数与分页不一致')
            if len(accounts) < 200:
                if count is not None and received < count:
                    raise TaskError('逐笔资源包分页不完整')
                break
            if count is not None and received == count:
                break
        else:
            raise TaskError('逐笔资源包超出分页上限')
    rows.sort(key=lambda row: (row['expire_ts'] is None, row['expire_ts'] or 0, -row['remain']))
    return rows


def credits_report(rows, days):
    live = [row for row in rows if row['status'] == 0 and row['remain'] > 0
            and (row['expire_ts'] is None or row['expire_ts'] > time.time())]
    soon = [row for row in live if row['days_left'] is not None and 0 <= row['days_left'] <= days] if days is not None else []
    displayed = soon if days is not None else rows
    anchor = next((i for i, row in enumerate(displayed) if row['state'] == '使用中'), None)
    if anchor is None:
        anchor = next((i for i, row in enumerate(displayed) if row['state'] == '未使用'), 0)
    start, end = max(0, anchor - 10), min(len(displayed), anchor + 11)
    return dict(packages=rows, total_remaining=sum(row['remain'] for row in live),
                expiring_days=days, expiring_soon=soon,
                window=dict(records=displayed[start:end], anchor=anchor, start=start, end=end,
                            truncated=len(displayed) > end - start))


def print_credits(report, as_html=False):
    rows = report['window']['records']
    log(f"积分到期查询完成，有效剩余 {report['total_remaining']}，记录 {len(report['packages'])}，展示 {len(rows)}")
    if as_html:
        cells = ''.join('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in
                        (row['source'], row['state'], row['remain'], row['total'], row['expire_at'] or '未知', row['expire_kind'], row['refresh_at'] or '未知')) + '</tr>' for row in rows)
        print('<section><h2>积分到期明细（北京时间）</h2><table><thead><tr><th>获取方式</th><th>状态</th><th>剩余</th><th>总量</th><th>到期时间</th><th>类型</th><th>周期结束</th></tr></thead><tbody>' + cells + '</tbody></table></section>')
    else:
        for row in rows:
            log(f"{row['source']}，{row['state']}，剩余 {row['remain']}/{row['total']}，到期 {row['expire_at'] or '未知'}，{row['expire_kind']}，周期结束 {row['refresh_at'] or '未知'}")


def identity(info, uid, token):
    value = info.get('identity')
    if not isinstance(value, (str, int)) or not str(value):
        return
    value = str(value)
    if token in value or re.search(r'(?i)bearer|eyJ|[\r\n\x00-\x1f]|(?:\+?86)?1[3-9]\d{9}', value):
        return
    log('官方账号身份：' + value)


def stage(number, title, action):
    started = time.monotonic()
    log(f'阶段 {number}：{title}')
    try:
        result = action()
    except Exception:
        log(f'阶段 {number}：失败，耗时 {time.monotonic() - started:.2f} 秒')
        raise
    log(f'阶段 {number}：完成，耗时 {time.monotonic() - started:.2f} 秒')
    return result


def account(index, line, mode, dry, timeout, attempts, verify_wallet=False, expiring_days=None, as_html=False):
    start = time.monotonic()
    record = dict(account=index, status='failed', action=mode, tasks=0, success=0,
                  alreadyComplete=0, skipped=0, failed=0, reward=0)
    def credentials():
        uid, delimiter, token = line.partition('|')
        uid, token = uid.strip(), token.strip()
        if not delimiter or not uid or not token or any(ord(c) < 32 or ord(c) == 127 for c in uid + token):
            raise TaskError('账号格式错误，需要 uid|accessToken')
        if len(uid) > 256 or len(token) > 32768:
            raise TaskError('凭据长度超出限制')
        return uid, token
    def execute(number, title, action):
        record['tasks'] += 1
        value = stage(number, title, action)
        record['success'] += 1
        return value
    log(f'账号 {index} 开始')
    try:
        uid, token = execute(1, '检查账号参数', credentials)
        if dry:
            log('DRY_RUN_OK：参数有效，未发送请求、未修改任何状态')
            record.update(status='dry-run', action='dry-run')
        elif mode == 'credits':
            client = ApiClient(uid, token, timeout)
            rows = execute(2, '查询积分发放与到期记录', client.credit_packages)
            report = credits_report(rows, expiring_days)
            print_credits(report, as_html)
            record.update(status='success', credits=report)
            log('业务核验成功')
        else:
            client = ApiClient(uid, token, timeout)
            info = execute(2, '查询今日状态', lambda: client.status(attempts))
            identity(info, uid, token)
            before = None
            if verify_wallet:
                before = execute(3, '读取真实余额基准', client.wallet)
                log(f"有效资源包 {before['packages']}，真实余额 {before['total']}")
                record['wallet'] = dict(total=before['total'], packages=before['packages'])
            log(f"今日已签到={info['checked_in']}，连续天数={info['streak_days']}，累计积分={info['total_credits']}")
            if mode == 'run' and not info['checked_in']:
                if info['active'] is False:
                    raise TaskError('签到活动未开启，停止领取')
                # 写请求不自动重试；避免响应丢失时重复领取。下次运行先查服务端状态。
                ck = execute(4 if verify_wallet else 3, '领取每日签到积分', lambda: client.post('daily-checkin'))
                after = execute(5 if verify_wallet else 4, '核验服务端签到状态', lambda: client.status(attempts))
                if not after['checked_in']:
                    record['tasks'] += 1
                    raise TaskError('二次查询未确认已签到')
                if verify_wallet:
                    def verify_balance():
                        snapshot = client.wallet()
                        growth, expired = diff_packages(before['items'], snapshot['items'])
                        expected = ck['reward'] if ck['reward'] and ck['reward'] > 0 else 100
                        if growth < expected:
                            time.sleep(2)
                            snapshot = client.wallet()
                            growth, expired = diff_packages(before['items'], snapshot['items'])
                        record['wallet'] = dict(total=snapshot['total'], packages=snapshot['packages'],
                                                growth=growth, expired=expired, baseline=before['total'])
                        log(f"真实余额 {snapshot['total']}，增长 {growth}，失效 {expired}")
                        if growth < expected:
                            raise TaskError('真实资源包增长未达到本次签到奖励，停止并保留失败状态')
                    execute(6, '核验真实资源包增长', verify_balance)
                info = after
                record['reward'] = ck['reward'] or 0
                record['streak_bonus'] = ck['streak_bonus']
            elif mode == 'run':
                record['alreadyComplete'] = 1
                log('服务端确认今天已签到，跳过领取')
            record.update(status='success', streak_days=info['streak_days'],
                          total_credits=info['total_credits'], checked_dates=info['checked_dates'])
            log('业务核验成功')
    except TaskError as exc:
        record['failed'] += 1
        record['message'] = str(exc)
        log('❌ ' + str(exc))
    except Exception:
        record['failed'] += 1
        record['message'] = '执行异常（详细内容已隐藏）'
        log('❌ 执行异常（详细内容已隐藏）')
    record['elapsedSeconds'] = round(time.monotonic() - start, 3)
    log(f"账号 {index} 统计：总任务 {record['tasks']}，成功 {record['success']}，已完成 {record['alreadyComplete']}，跳过 {record['skipped']}，失败 {record['failed']}，耗时 {record['elapsedSeconds']} 秒")
    return record


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in FALSE:
        return '已关闭'
    selected = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if switch not in TRUE:
        selectors = re.split(r'[,;\s]+', selected or '')
        names = [CATALOG_ID, 'local_daily.py', 'scripts/local_daily.py',
                 Path(__file__).name, 'scripts/' + Path(__file__).name]
        if not any(fnmatch.fnmatch(n, p) for n in names for p in selectors if p):
            return '未入选通知清单'
    body = f"账号总数 {summary['accounts']}，成功 {summary['succeeded']}，失败 {summary['failed']}，状态 {summary['status']}"
    # 通知在子进程隔离执行；dry-run 禁止连接，仍可调用本地通知桩。
    code = '''import contextlib, importlib.util, io, socket, sys
if sys.argv[3] == '1':
    def denied(*a, **k): raise OSError('dry-run')
    def audit(event, args):
        if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork'):
            denied()
    sys.addaudithook(audit)
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.getaddrinfo = denied
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    if sys.argv[4]:
        spec = importlib.util.spec_from_file_location('notify', sys.argv[4])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        import notify as module
    module.send(sys.argv[1], sys.argv[2])
'''
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    path = next((str(p) for p in paths if p.is_file()), '')
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, body, '1' if dry else '0', path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return '已发送' if result.returncode == 0 else ('断网预演通知不可用' if dry else '通知不可用或发送失败')
    except Exception:
        return '通知不可用或发送失败'


class TaskParser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令参数无效，请使用 --help 查看用法')


def main():
    start = time.monotonic()
    parser = TaskParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['run', 'status', 'credits'], default='run')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--status', action='store_true', help='只查询今日状态')
    parser.add_argument('--verify-wallet', action='store_true', help='显式核验真实余额及资源包增长')
    parser.add_argument('--expire', action='store_true', help='只读积分到期查询')
    parser.add_argument('--expiring-days', type=int, help='仅展示指定天数内到期的有效记录')
    parser.add_argument('--html', action='store_true', help='积分到期明细以 HTML 片段输出')
    argument_error = None
    try:
        args = parser.parse_args()
    except TaskError as exc:
        argument_error = str(exc)
        args = argparse.Namespace(action='run', dry_run=False, json=False,
                                  status=False, verify_wallet=False, expire=False, expiring_days=None, html=False)
    if args.expire:
        args.action = 'credits'
    if args.status:
        if args.action == 'credits':
            argument_error = '积分到期入口与签到状态入口不能同时选择'
        args.action = 'status'
    if (args.expiring_days is not None or args.html) and args.action != 'credits':
        argument_error = '临期筛选和 HTML 输出仅适用于 credits'
    if args.expiring_days is not None and args.expiring_days < 0:
        argument_error = '临期天数须为非负整数'
    if args.action == 'credits' and args.verify_wallet:
        argument_error = 'credits 与 --verify-wallet 须分别运行'
    dry = args.dry_run or os.getenv('WORKBUDDY_DRY_RUN', '').strip().lower() in TRUE
    if dry:
        def deny_network(event, arguments):
            if event.startswith('socket.'):
                raise OSError('断网预演禁止网络')
        sys.addaudithook(deny_network)
    raw = os.getenv('WORKBUDDY_ACCOUNTS', '')
    if not raw.strip() and os.getenv('WORKBUDDY_ACCESS_TOKEN', '').strip():
        raw = os.getenv('WORKBUDDY_UID', '') + '|' + os.environ['WORKBUDDY_ACCESS_TOKEN']
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else args.action}；账号数：{len(lines)}')
    records = []
    config_error = argument_error
    try:
        timeout = float(os.getenv('WORKBUDDY_TIMEOUT', '15'))
        attempts = int(os.getenv('WORKBUDDY_MAX_ATTEMPTS', '4'))
        if not 1 <= timeout <= 120 or not 1 <= attempts <= 4:
            raise ValueError()
        if not lines:
            config_error = '缺少 WORKBUDDY_ACCOUNTS（兼容输入需同时提供 Token 与 UID）'
    except ValueError:
        config_error = '超时应为 1 至 120 秒，查询尝试次数应为 1 至 4'
    if config_error:
        log('❌ 配置错误：' + config_error)
    else:
        for index, line in enumerate(lines, 1):
            records.append(account(index, line, args.action, dry, timeout, attempts, args.verify_wallet, args.expiring_days, args.html))
    failed = sum(r['status'] == 'failed' for r in records)
    succeeded = len(records) - failed
    status = ('configuration-error' if config_error else 'partial-failure' if failed and succeeded
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(accounts=len(lines), succeeded=succeeded, failed=failed, status=status,
                   tasks=sum(r['tasks'] for r in records),
                   taskSuccess=sum(r['success'] for r in records),
                   taskFailed=sum(r['failed'] for r in records),
                   alreadyComplete=sum(r['alreadyComplete'] for r in records),
                   skipped=sum(r['skipped'] for r in records))
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - start, 3)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    log('--------------------------------------------------')
    log(f'任务统计：账号 {len(lines)}，成功 {succeeded}，失败 {failed}；子任务 {summary["tasks"]}，成功 {summary["taskSuccess"]}，失败 {summary["taskFailed"]}，已完成 {summary["alreadyComplete"]}，跳过 {summary["skipped"]}')
    log(f'完成时间：{summary["finishTime"]}；耗时 {summary["elapsedSeconds"]} 秒；通知：{summary["notification"]}；最终状态：{status}')
    if args.json:
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return 1 if config_error or failed else 0


if __name__ == '__main__':
    sys.exit(main())
