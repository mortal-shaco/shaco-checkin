#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: WPS天天领福利（可选任务中心）
# cron: 1 1 1 1 1
"""
WPS 天天领福利；可选合并任务中心（同账号、同排期）。
上游：Cat-zaizai/ZaiZaiCat-Checkin，script/wps/daily_benefits.py、api.py、main.py、task_center.py
Original Author: Assistant; Date: 2026-03-11. Effective license: MIT.

功能盘点：双渠道福利入口发现、页面信息、免费会员打卡、断签重开、试用申请、
天天抽奖、七日领奖；相关任务中心提供加密签到、积分/过期积分/抽奖机会查询和抽奖。
logging_utils 为展示辅助；main 为相同排期的两页入口，不独立发布。
maintainedFeatureCoverage 为空；没有 optimizationTarget 或 previousRepairFailure。
所有功能保留在一个脚本，试用、抽奖、重开和任务中心显式启用，避免默认消耗机会
或改变签到系列。默认仅免费会员签到和符合条件时领奖。原 cron 原样保留。

参数获取：浏览器登录 WPS，打开 personal-act.wps.cn 的福利中心；开发者工具
Network 查看 page_info/component_action 请求，复制 Cookie（含登录会话和
act_csrf_token 或 csrf）。任务中心 user_id 从本人官方账号响应或签到请求获得，
不要使用别人的数据。Cookie 与 user_id 是同账号配套参数。
WPS_ACCOUNTS：每个非空行一个账号，格式 Cookie 或 user_id|Cookie，仅分割首个 |。
也支持每行 JSON 对象，保留 cookies、user_id、user_agent、account_name、
max_lottery_limit 字段；不读取私有 token.json。JSON 对象中的账号名仅为本地备注。
WPS_TASKS 默认 checkin,reward，可选 trial,lottery,task_center,task_center_lottery。
WPS_RESTART_SERIES=1 才允许断签后重开；WPS_USER_AGENT 可选公共请求头。
WPS_DRY_RUN=1 完全断网；QINGLONG_NOTIFY=0 关闭通知。
任务中心加密需要公共包 pycryptodome；其他功能仅使用 Python 标准库。
通知可选 Qinglong notify.py 或 sendNotify.js，失败不改变业务退出码；断网模式
仅生成并展示脱敏通知正文，禁止调用会联网的通知发送器。

MIT License
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
import base64
import importlib.util
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


class SafeFailure(Exception):
    pass


def enabled(name):
    return os.environ.get(name, '0').strip().lower() in {'1', 'true', 'yes', 'on'}


def parse_cookie(value):
    cookies = {}
    for part in value.split(';'):
        if not part.strip():
            continue
        key, sep, val = part.strip().partition('=')
        if not sep or not key or not val or any(c in part for c in '\r\n'):
            raise SafeFailure('Cookie 格式错误')
        cookies[key] = val
    if not cookies:
        raise SafeFailure('Cookie 为空')
    return cookies


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeFailure('禁止重定向，防止凭据跨域')


def http_json(method, url, headers, params=None, data=None):
    if enabled('WPS_DRY_RUN'):
        raise SafeFailure('断网预演禁止 HTTP')
    if urlparse(url).scheme != 'https' or urlparse(url).netloc not in {
        'tiance.wps.cn', 'personal-act.wps.cn', 'personal-bus.wps.cn'
    }:
        raise SafeFailure('拒绝非官方 HTTPS 接口')
    if params:
        url += '?' + urlencode(params)
    raw = None if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8')
    endpoint = urlparse(url).netloc + urlparse(url).path
    started = time.monotonic()
    log('请求开始：' + method + ' ' + endpoint)
    try:
        with build_opener(NoRedirect()).open(Request(url, data=raw, headers=headers, method=method), timeout=30) as response:
            if response.status != 200:
                raise SafeFailure('HTTP 状态异常')
            body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            raise SafeFailure('响应过大')
        result = json.loads(body)
        if not isinstance(result, dict):
            raise SafeFailure('响应结构错误')
        log('请求结果：HTTP 200，JSON 结构通过，外层业务状态 ' + ('ok' if result.get('result') == 'ok' else '未确认成功') + '；耗时 %.3f 秒' % (time.monotonic() - started))
        show_identity(result)
        return result
    except SafeFailure:
        log('请求结果：❌ HTTP 或安全校验失败；耗时 %.3f 秒' % (time.monotonic() - started))
        raise
    except Exception:
        log('请求结果：❌ 网络请求或响应解析失败；耗时 %.3f 秒' % (time.monotonic() - started))
        raise SafeFailure('网络请求或响应解析失败') from None


IDENTITIES = set()
CLAIMED_SERIES = set()
SECRET_VALUES = set()

def business_label(value):
    if not isinstance(value, str):
        return '未提供名称'
    text = value
    for secret in sorted(SECRET_VALUES, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已脱敏]')
    text = re.sub(r'(?i)(cookie|token|session|csrf|device)[\w-]*\s*[:=]\s*[^\s;,]+', '[敏感字段已隐藏]', text)
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ' '.join(text.split())[:160] or '未提供名称'

def show_identity(node):
    # Only explicit official public identity fields; never cookie/device/session fields.
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {'nickname', 'nick_name', 'username', 'user_name', 'display_name', 'displayName', 'public_uid', 'uid', 'user_id'} and isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                identity = (key, str(value))
                if identity not in IDENTITIES:
                    IDENTITIES.add(identity)
                    log('官方账号身份 ' + key + ': ' + str(value))
            elif isinstance(value, (dict, list)):
                show_identity(value)
    elif isinstance(node, list):
        for value in node:
            show_identity(value)


# Upstream API has two benign progress logs; no raw diagnostics are emitted.
def configure_logging():
    pass

def get_logger(name):
    logger = logging.getLogger(name)
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger

def bind_logger(logger, **context):
    return logger


class DailyBenefitsTasks:
    page_name = '天天领福利'


class DailyBenefitsAPI:
    """WPS 天天领福利活动接口封装"""
    MARKET_ACTIVITY_URL = 'https://tiance.wps.cn/dce/exec/api/market/activity'
    PAGE_INFO_URL = 'https://personal-act.wps.cn/activity-rubik/activity/page_info'
    COMPONENT_ACTION_URL = 'https://personal-act.wps.cn/activity-rubik/activity/component_action'
    MARKET_ACTIVITY_CHANNELS = [{'channel_code': 'AUTOPCHYZXYYHD3737', 'platform': 8, 'version': '0.0.0.0'}, {'channel_code': 'HYGW5004,GWHD5002', 'version': '', 'platform': 8, 'device': 1, 'hdid': '', 'filter_info': {}}]
    TARGET_POSITIONS = ('pc_nvc_activity_fuli',)
    TARGET_TITLES = {'福利中心', '天天领福利'}

    def __init__(self, cookies: str, user_agent: Optional[str]=None):
        self.cookies = self._parse_cookies(cookies)
        self.user_agent = user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        self.base_headers = {'User-Agent': self.user_agent, 'Accept': 'application/json, text/plain, */*', 'Accept-Encoding': 'gzip, deflate, br, zstd', 'Content-Type': 'application/json; charset=UTF-8', 'sec-ch-ua-platform': '"macOS"', 'sec-ch-ua': '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"', 'sec-ch-ua-mobile': '?0', 'sec-gpc': '1', 'accept-language': 'zh-CN,zh;q=0.7', 'origin': 'https://personal-act.wps.cn', 'referer': 'https://personal-act.wps.cn/', 'priority': 'u=1, i'}
        configure_logging()
        self.logger = bind_logger(get_logger('daily_benefits.api'), page=DailyBenefitsTasks.page_name)

    @staticmethod
    def _parse_cookies(cookie_str: str) -> Dict[str, str]:
        return parse_cookie(cookie_str)

    @staticmethod
    def _extract_error_message(result: Dict[str, Any]) -> str:
        """从返回结果中提取错误消息"""
        return result.get('msg') or result.get('message') or result.get('error') or '未知错误'

    @staticmethod
    def _normalize_server_time(server_time: Any) -> int:
        """兼容秒和毫秒时间戳。"""
        try:
            timestamp = int(server_time)
        except (TypeError, ValueError):
            return 0
        if timestamp > 10 ** 12:
            timestamp //= 1000
        return timestamp

    @classmethod
    def _resolve_sign_date(cls, item: Dict[str, Any], sign_records: List[Dict[str, Any]]) -> str:
        """优先使用服务端时间推导签到日期，缺失时回退到记录中的最新日期。"""
        server_time = cls._normalize_server_time(item.get('server_time', 0))
        if server_time:
            return time.strftime('%Y-%m-%d', time.localtime(server_time))
        today = time.strftime('%Y-%m-%d')
        if any((record.get('sign_date') == today for record in sign_records)):
            return today
        if sign_records:
            return sign_records[0].get('sign_date', today)
        return today

    @staticmethod
    def _count_signed_days(sign_records: List[Dict[str, Any]]) -> int:
        """统计当前系列已签到天数。"""
        return sum((1 for record in sign_records if record.get('sign_status') == 'signed'))

    @staticmethod
    def _safe_int(value: Any, default: int=0) -> int:
        """将接口返回的数字字段安全转为 int。"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _is_auth_expired_message(message: str) -> bool:
        keywords = ('Token已过期', 'ErrNotLogin', 'userNotLogin', '未登录', '请重新登录')
        return any((keyword in str(message) for keyword in keywords))

    def _build_failure_result(self, payload: Dict[str, Any], default_error: str='未知错误') -> Dict[str, Any]:
        error_message = self._extract_error_message(payload) or default_error
        result = {'success': False, 'error': error_message}
        if payload.get('code') == 2000000 or payload.get('ext_msg') == 'userNotLogin' or self._is_auth_expired_message(error_message):
            result['error_type'] = 'token_expired'
        return result

    def get_market_activity(self, payload: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
        """获取单个渠道的市场活动数据"""
        request_payload = payload if payload is not None else self.MARKET_ACTIVITY_CHANNELS[0]
        result = self._request('POST', self.MARKET_ACTIVITY_URL, headers={'sec-fetch-site': 'same-site', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty'}, json_data=request_payload)
        if not result['success']:
            return result
        payload_data = result['data']
        if payload_data.get('result') != 'ok':
            return self._build_failure_result(payload_data)
        return {'success': True, 'data': payload_data}

    def get_benefit_portal(self) -> Dict[str, Any]:
        """跨多个营销渠道发现并选中「天天领福利」活动入口"""
        raw_candidates: List[Dict[str, str]] = []
        channel_errors: List[str] = []
        auth_expired = False
        for channel_payload in self.MARKET_ACTIVITY_CHANNELS:
            channel_code = channel_payload.get('channel_code', '')
            market_result = self.get_market_activity(channel_payload)
            if not market_result['success']:
                channel_errors.append(f"{channel_code}: {market_result.get('error', '未知错误')}")
                if market_result.get('error_type') == 'token_expired':
                    auth_expired = True
                continue
            self._collect_portal_candidates(market_result['data'], raw_candidates)
        parsed_candidates = self._parse_portal_candidates(raw_candidates)
        self.logger.info('入口发现：收集到 %s 个链接，去重后 %s 个入口', len(raw_candidates), len(parsed_candidates), extra={'step': '入口发现'})
        if not parsed_candidates:
            failure = {'success': False, 'error': '未找到福利中心活动入口'}
            if auth_expired:
                failure['error_type'] = 'token_expired'
            elif channel_errors:
                failure['error'] = f"未找到福利中心活动入口（渠道请求失败: {'; '.join(channel_errors)}）"
            return failure
        selected = self._select_benefit_portal(parsed_candidates)
        if selected is None:
            found_positions = sorted({candidate.get('position', '') for candidate in parsed_candidates if candidate.get('position')})
            return {'success': False, 'error': f"未匹配到福利中心入口（期望 position=pc_nvc_activity_fuli），实际发现: {', '.join(found_positions) or '无 position'}"}
        return selected

    def _parse_portal_candidates(self, raw_candidates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """解析候选链接并按 activity/page 去重，附带 position/title。"""
        parsed: List[Dict[str, Any]] = []
        seen: set = set()
        for candidate in raw_candidates:
            portal_info = self._parse_portal_link(candidate['link'])
            if not portal_info['success']:
                continue
            dedup_key = (portal_info['activity_number'], portal_info['page_number'])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            portal_info['title'] = candidate.get('title', '')
            portal_info['pic'] = candidate.get('pic', '')
            portal_info['position'] = portal_info.get('filter_params', {}).get('position', '')
            parsed.append(portal_info)
        return parsed

    def _select_benefit_portal(self, parsed_candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """按 position 精确命中 > position 含 fuli > 标题命中 的顺序选中福利入口。"""
        for candidate in parsed_candidates:
            if candidate.get('position') in self.TARGET_POSITIONS:
                return candidate
        for candidate in parsed_candidates:
            if 'fuli' in (candidate.get('position') or ''):
                return candidate
        for candidate in parsed_candidates:
            if candidate.get('title') in self.TARGET_TITLES:
                return candidate
        return None

    def _collect_portal_candidates(self, node: Any, candidates: List[Dict[str, str]]) -> None:
        """递归收集包含 portal 链接的活动入口（不再要求节点带 title）"""
        if isinstance(node, dict):
            link = node.get('link')
            if isinstance(link, str) and '/rubik2/portal/' in link:
                title = node.get('title')
                candidates.append({'title': title if isinstance(title, str) else '', 'link': link, 'pic': node.get('pic') or node.get('img') or ''})
            for value in node.values():
                self._collect_portal_candidates(value, candidates)
        elif isinstance(node, list):
            for item in node:
                self._collect_portal_candidates(item, candidates)

    def _parse_portal_link(self, link: str) -> Dict[str, Any]:
        if urlparse(link).scheme != 'https' or urlparse(link).netloc != 'personal-act.wps.cn':
            return {'success': False, 'error': '活动链接域名不受信任'}
        '解析活动 portal 链接'
        try:
            parsed = urlparse(link)
            path_parts = [part for part in parsed.path.split('/') if part]
            portal_index = path_parts.index('portal')
            activity_number = path_parts[portal_index + 1]
            page_number = path_parts[portal_index + 2]
            query_params = parse_qs(parsed.query)
            filter_params = {key: values[0] for (key, values) in query_params.items() if values}
            return {'success': True, 'link': link, 'activity_number': activity_number, 'page_number': page_number, 'filter_params': filter_params}
        except (ValueError, IndexError) as exc:
            return {'success': False, 'error': f'活动链接解析失败: {exc}'}

    def get_page_info(self, portal_info: Dict[str, Any]) -> Dict[str, Any]:
        """获取页面全部活动信息"""
        self.logger.info('获取页面活动信息', extra={'step': '页面信息'})
        activity_number = portal_info['activity_number']
        page_number = portal_info['page_number']
        filter_params = portal_info.get('filter_params', {})
        result = self._request('GET', self.PAGE_INFO_URL, headers={'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': portal_info['link']}, params={'activity_number': activity_number, 'page_number': page_number, 'filter_params': json.dumps(filter_params, ensure_ascii=False, separators=(',', ':'))})
        if not result['success']:
            return result
        payload = result['data']
        if payload.get('result') != 'ok':
            return self._build_failure_result(payload)
        return {'success': True, 'data': payload}

    def get_member_trial_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """从总活动返回数据中提取会员免费试用模块"""
        data_list = page_info.get('data', [])
        fallback_item: Optional[Dict[str, Any]] = None
        for item in data_list:
            if not isinstance(item, dict):
                continue
            divide_prize = item.get('divide_prize')
            if not isinstance(divide_prize, dict):
                continue
            details = divide_prize.get('divide_prize_details') or []
            if not details:
                continue
            if fallback_item is None:
                fallback_item = item
            if any(('会员' in str(detail.get('title', '')) for detail in details)):
                return {'success': True, 'component_number': item.get('number', ''), 'component_node_id': item.get('component_node_id', ''), 'remain_times': divide_prize.get('remain_times', 0), 'latest_result': divide_prize.get('latest_result', ''), 'join_reach_limit': divide_prize.get('join_reach_limit', False), 'details': details, 'raw_data': divide_prize}
        if fallback_item is not None:
            divide_prize = fallback_item.get('divide_prize', {})
            return {'success': True, 'component_number': fallback_item.get('number', ''), 'component_node_id': fallback_item.get('component_node_id', ''), 'remain_times': divide_prize.get('remain_times', 0), 'latest_result': divide_prize.get('latest_result', ''), 'join_reach_limit': divide_prize.get('join_reach_limit', False), 'details': divide_prize.get('divide_prize_details') or [], 'raw_data': divide_prize}
        return {'success': False, 'error': '未找到会员免费试用模块'}

    def sign_up_member_trial(self, portal_info: Dict[str, Any], component_number: str, component_node_id: str, cycle_id: str, session_id: str) -> Dict[str, Any]:
        """执行会员免费试用申请"""
        csrf_token = self.cookies.get('act_csrf_token') or self.cookies.get('csrf')
        if not csrf_token:
            return {'success': False, 'error': 'Cookie 中缺少 act_csrf_token/csrf，无法提交试用申请'}
        payload = {'component_uniq_number': {'activity_number': portal_info['activity_number'], 'page_number': portal_info['page_number'], 'component_number': component_number, 'component_node_id': component_node_id, 'filter_params': {}}, 'component_type': 32, 'component_action': 'divide_prize.sign_up', 'divide_prize': {'cycle_id': cycle_id, 'session_id': session_id}}
        result = self._request('POST', self.COMPONENT_ACTION_URL, headers={'Content-Type': 'application/json', 'x-act-csrf-token': csrf_token, 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': f"https://personal-act.wps.cn/rubik2/portal/{portal_info['activity_number']}/{portal_info['page_number']}"}, json_data=payload)
        if not result['success']:
            return result
        payload_data = result['data']
        if payload_data.get('result') != 'ok':
            return self._build_failure_result(payload_data)
        divide_prize = payload_data.get('data', {}).get('divide_prize', {})
        if divide_prize.get('success') is True:
            return {'success': True, 'reason': divide_prize.get('reason', ''), 'data': divide_prize}
        failure_result = {'success': False, 'error': divide_prize.get('reason') or '试用申请失败', 'data': divide_prize}
        if self._is_auth_expired_message(failure_result['error']):
            failure_result['error_type'] = 'token_expired'
        return failure_result

    def get_fragment_collect_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """从总活动返回数据中提取打卡免费领会员模块"""
        data_list = page_info.get('data', [])
        fallback_item: Optional[Dict[str, Any]] = None
        for item in data_list:
            if not isinstance(item, dict):
                continue
            fragment_collect = item.get('fragment_collect')
            if not isinstance(fragment_collect, dict):
                continue
            sign_records = fragment_collect.get('sign_records') or []
            if not sign_records:
                continue
            if fallback_item is None:
                fallback_item = item
            sign_date = self._resolve_sign_date(item, sign_records)
            today_record = next((record for record in sign_records if record.get('sign_date') == sign_date), None)
            sign_series_id = fragment_collect.get('sign_series_id', '')
            if item.get('type') == 42 or today_record is not None:
                return {'success': True, 'component_number': item.get('number', ''), 'component_node_id': item.get('component_node_id', ''), 'sign_date': sign_date, 'sign_series_id': sign_series_id, 'is_new_sign_series': not bool(sign_series_id), 'is_signed': (today_record or {}).get('sign_status') == 'signed', 'today_record': today_record or {}, 'signed_days': self._count_signed_days(sign_records), 'sign_records': sign_records, 'raw_data': fragment_collect}
        if fallback_item is not None:
            fragment_collect = fallback_item.get('fragment_collect', {})
            sign_records = fragment_collect.get('sign_records') or []
            sign_date = self._resolve_sign_date(fallback_item, sign_records)
            today_record = next((record for record in sign_records if record.get('sign_date') == sign_date), None)
            sign_series_id = fragment_collect.get('sign_series_id', '')
            return {'success': True, 'component_number': fallback_item.get('number', ''), 'component_node_id': fallback_item.get('component_node_id', ''), 'sign_date': sign_date, 'sign_series_id': sign_series_id, 'is_new_sign_series': not bool(sign_series_id), 'is_signed': (today_record or {}).get('sign_status') == 'signed', 'today_record': today_record or {}, 'signed_days': self._count_signed_days(sign_records), 'sign_records': sign_records, 'raw_data': fragment_collect}
        return {'success': False, 'error': '未找到打卡免费领会员模块'}

    def sign_in_fragment_collect(self, portal_info: Dict[str, Any], component_number: str, component_node_id: str, sign_date: str, sign_series_id: str, is_new_sign_series: bool) -> Dict[str, Any]:
        """执行打卡免费领会员签到"""
        csrf_token = self.cookies.get('act_csrf_token') or self.cookies.get('csrf')
        if not csrf_token:
            return {'success': False, 'error': 'Cookie 中缺少 act_csrf_token/csrf，无法执行打卡签到'}
        payload = {'component_uniq_number': {'activity_number': portal_info['activity_number'], 'page_number': portal_info['page_number'], 'component_number': component_number, 'component_node_id': component_node_id, 'filter_params': portal_info.get('filter_params', {})}, 'component_type': 42, 'component_action': 'fragment_collect.sign_in', 'fragment_collect': {'sign_date': sign_date, 'series_id': sign_series_id, 'is_new_sign_series': is_new_sign_series}}
        result = self._request('POST', self.COMPONENT_ACTION_URL, headers={'Content-Type': 'application/json', 'x-act-csrf-token': csrf_token, 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': portal_info['link']}, json_data=payload)
        if not result['success']:
            return result
        payload_data = result['data']
        if payload_data.get('result') != 'ok':
            return self._build_failure_result(payload_data)
        fragment_collect = payload_data.get('data', {}).get('fragment_collect', {})
        if fragment_collect.get('success') is True:
            return {'success': True, 'reason': fragment_collect.get('reason', ''), 'data': fragment_collect}
        failure_result = {'success': False, 'error': fragment_collect.get('reason') or '打卡签到失败', 'data': fragment_collect}
        if self._is_auth_expired_message(failure_result['error']):
            failure_result['error_type'] = 'token_expired'
        return failure_result

    @staticmethod
    def _pick_lottery_session(lottery_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """优先挑选进行中的抽奖场次"""
        for session in lottery_list:
            if session.get('session_status') == 'IN_PROGRESS' and session.get('stock_status') in {'IN_STOCK', '', None}:
                return session
        for session in lottery_list:
            if session.get('session_status') == 'IN_PROGRESS':
                return session
        return lottery_list[0] if lottery_list else None

    def get_daily_lottery_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """从总活动返回数据中提取天天抽奖模块"""
        data_list = page_info.get('data', [])
        fallback_item: Optional[Dict[str, Any]] = None
        fallback_session: Optional[Dict[str, Any]] = None
        for item in data_list:
            if not isinstance(item, dict):
                continue
            lottery_v2 = item.get('lottery_v2')
            if not isinstance(lottery_v2, dict):
                continue
            lottery_list = lottery_v2.get('lottery_list') or []
            if not lottery_list:
                continue
            selected_session = self._pick_lottery_session(lottery_list)
            if selected_session is None:
                continue
            if fallback_item is None:
                fallback_item = item
                fallback_session = selected_session
            if selected_session.get('session_status') == 'IN_PROGRESS':
                sign_day = self._safe_int(selected_session.get('times', 0))
                return {'success': True, 'component_number': item.get('number', ''), 'component_node_id': item.get('component_node_id', ''), 'session_id': selected_session.get('session_id'), 'session_name': selected_session.get('session_name', ''), 'remain_times': sign_day, 'sign_day': sign_day, 'stock_status': selected_session.get('stock_status', ''), 'share_times': lottery_v2.get('share_times', False), 'share_times_count': lottery_v2.get('share_times_count', 0), 'lottery_reward_list': selected_session.get('lottery_reward_list', []), 'raw_data': lottery_v2}
        if fallback_item is not None and fallback_session is not None:
            lottery_v2 = fallback_item.get('lottery_v2', {})
            sign_day = self._safe_int(fallback_session.get('times', 0))
            return {'success': True, 'component_number': fallback_item.get('number', ''), 'component_node_id': fallback_item.get('component_node_id', ''), 'session_id': fallback_session.get('session_id'), 'session_name': fallback_session.get('session_name', ''), 'remain_times': 0, 'sign_day': sign_day, 'stock_status': fallback_session.get('stock_status', ''), 'share_times': lottery_v2.get('share_times', False), 'share_times_count': lottery_v2.get('share_times_count', 0), 'lottery_reward_list': fallback_session.get('lottery_reward_list', []), 'raw_data': lottery_v2}
        return {'success': False, 'error': '未找到天天抽奖模块'}

    def exec_daily_lottery(self, portal_info: Dict[str, Any], component_number: str, component_node_id: str, session_id: Any) -> Dict[str, Any]:
        """执行天天抽奖"""
        csrf_token = self.cookies.get('act_csrf_token') or self.cookies.get('csrf')
        if not csrf_token:
            return {'success': False, 'error': 'Cookie 中缺少 act_csrf_token/csrf，无法执行抽奖'}
        payload = {'component_uniq_number': {'activity_number': portal_info['activity_number'], 'page_number': portal_info['page_number'], 'component_number': component_number, 'component_node_id': component_node_id, 'filter_params': portal_info.get('filter_params', {})}, 'component_type': 45, 'component_action': 'lottery_v2.exec', 'lottery_v2': {'session_id': session_id}}
        result = self._request('POST', self.COMPONENT_ACTION_URL, headers={'Content-Type': 'application/json', 'x-act-csrf-token': csrf_token, 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': portal_info['link']}, json_data=payload)
        if not result['success']:
            return result
        payload_data = result['data']
        if payload_data.get('result') != 'ok':
            return self._build_failure_result(payload_data)
        lottery_v2 = payload_data.get('data', {}).get('lottery_v2', {})
        if lottery_v2.get('success') is True:
            return {'success': True, 'reward_name': lottery_v2.get('reward_name', '未知奖品'), 'reward_type': lottery_v2.get('reward_type', ''), 'reward_id': lottery_v2.get('reward_id', 0), 'order_id': lottery_v2.get('order_id', ''), 'img': lottery_v2.get('img', ''), 'data': lottery_v2}
        failure_result = {'success': False, 'error': lottery_v2.get('send_msg') or '抽奖失败', 'error_code': lottery_v2.get('error_code', 0), 'data': lottery_v2}
        if self._is_auth_expired_message(failure_result['error']):
            failure_result['error_type'] = 'token_expired'
        return failure_result

    def receive_daily_lottery_reward(self, portal_info: Dict[str, Any], component_number: str, component_node_id: str, sign_series_id: str) -> Dict[str, Any]:
        """领取天天福利第 7 天奖励"""
        csrf_token = self.cookies.get('act_csrf_token') or self.cookies.get('csrf')
        if not csrf_token:
            return {'success': False, 'error': 'Cookie 中缺少 act_csrf_token/csrf，无法领取第7天奖励'}
        payload = {'component_uniq_number': {'activity_number': portal_info['activity_number'], 'page_number': portal_info['page_number'], 'component_number': component_number, 'component_node_id': component_node_id, 'filter_params': portal_info.get('filter_params', {})}, 'component_type': 42, 'component_action': 'fragment_collect.receive', 'fragment_collect': {'series_id': sign_series_id}}
        result = self._request('POST', self.COMPONENT_ACTION_URL, headers={'Content-Type': 'application/json', 'x-act-csrf-token': csrf_token, 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': portal_info['link']}, json_data=payload)
        if not result['success']:
            return result
        payload_data = result['data']
        if payload_data.get('result') != 'ok':
            return self._build_failure_result(payload_data)
        action_data = payload_data.get('data', {}).get('fragment_collect', {})
        if not action_data:
            action_data = payload_data.get('data', {}).get('lottery_v2', {})
        if action_data.get('success') is True:
            return {'success': True, 'reason': action_data.get('reason', ''), 'reward_name': action_data.get('reward_name', ''), 'data': action_data}
        error_message = action_data.get('reason') or action_data.get('send_msg') or action_data.get('message') or '领取第7天奖励失败'
        failure_result = {'success': False, 'error': error_message, 'data': action_data, 'payload_summary': {'component_type': payload['component_type'], 'component_action': payload['component_action'], 'component_number': component_number, 'component_node_id': component_node_id, 'sign_series_id': sign_series_id}}
        if self._is_auth_expired_message(failure_result['error']):
            failure_result['error_type'] = 'token_expired'
        return failure_result

    def _request(self, method, url, *, headers=None, params=None, json_data=None):
        request_headers = dict(self.base_headers)
        request_headers['Accept-Encoding'] = 'identity'
        if headers:
            request_headers.update(headers)
        request_headers['Cookie'] = '; '.join((k + '=' + v for (k, v) in self.cookies.items()))
        try:
            data = http_json(method, url, request_headers, params, json_data)
            return {'success': True, 'data': data}
        except SafeFailure as exc:
            return {'success': False, 'error': str(exc)}

def log(message):
    print(time.strftime('[%H:%M:%S] ') + message, flush=True)


def checked(result):
    if result.get('success') is not True:
        message = str(result.get('error', ''))
        if result.get('error_type') == 'token_expired' or any(t in message for t in ('未登录', 'userNotLogin', 'ErrNotLogin', 'Token已过期')):
            raise SafeFailure('登录状态失效，请重新获取 Cookie')
        raise SafeFailure('接口未确认业务成功；请检查活动状态和凭据')
    return result


def page(api, portal):
    result = checked(api.get_page_info(portal))['data']
    if not isinstance(result.get('data'), list):
        raise SafeFailure('页面组件结构异常')
    return result


def claim_ready(api, portal, state):
    fragment = checked(api.get_fragment_collect_info(state))
    if fragment.get('sign_series_id') in CLAIMED_SERIES:
        return 'already', '本轮该签到系列的七天奖励已领取'
    if fragment['signed_days'] < 7:
        return 'skipped', '未满足七天签到条件'
    if not fragment.get('sign_series_id'):
        raise SafeFailure('领奖系列缺失，禁止猜测参数')
    received = checked(api.receive_daily_lottery_reward(portal, fragment['component_number'], fragment['component_node_id'], fragment['sign_series_id']))
    if received.get('reward_name'):
        log('第七天奖励：' + business_label(received['reward_name']))
    CLAIMED_SERIES.add(fragment['sign_series_id'])
    return 'success', '第7天奖励领取成功'


def perform_checkin(api, portal, state):
    fragment = checked(api.get_fragment_collect_info(state))
    if fragment['is_signed']:
        return 'already', '今日已签到，累计签到 %s 天' % fragment['signed_days']
    result = api.sign_in_fragment_collect(portal, fragment['component_number'], fragment['component_node_id'], fragment['sign_date'], fragment['sign_series_id'], fragment['is_new_sign_series'])
    msg = str(result.get('error', '')).lower()
    if result.get('success') is not True and ('not in series' in msg or 'series records' in msg):
        if not enabled('WPS_RESTART_SERIES'):
            raise SafeFailure('签到系列失效；重开需设置 WPS_RESTART_SERIES=1')
        log('检测到旧签到系列失效，按显式设置重开一次')
        result = api.sign_in_fragment_collect(portal, fragment['component_number'], fragment['component_node_id'], '', fragment['sign_series_id'], True)
    checked(result)
    refreshed = checked(api.get_fragment_collect_info(page(api, portal)))
    if refreshed['is_signed'] is not True:
        raise SafeFailure('提交后未核验到今日已签到')
    reward = refreshed.get('today_record', {}).get('reward_title')
    if reward:
        log('签到奖励：' + business_label(reward))
    return 'success', '打卡签到成功，累计签到 %s 天' % refreshed['signed_days']


def perform_trial(api, portal, state):
    trial = checked(api.get_member_trial_info(state))
    remain = int(trial['remain_times'])
    candidates = [d for d in trial['details'] if not d.get('has_join')]
    if trial['join_reach_limit'] or remain <= 0 or not candidates:
        return 'skipped', '试用已申请或无可用申请机会'
    failures = 0
    for i, item in enumerate(candidates[:remain], 1):
        result = api.sign_up_member_trial(portal, trial['component_number'], trial['component_node_id'], item['cycle_id'], item['session_id'])
        ok = result.get('success') is True
        log('试用申请 %s（%s）: %s' % (i, business_label(item.get('title')), '✅ 业务成功' if ok else '❌ 业务未成功'))
        failures += not ok
        if result.get('error_type') == 'token_expired':
            break
        if i < min(remain, len(candidates)):
            time.sleep(1)
    if failures:
        raise SafeFailure('会员试用存在失败申请')
    return 'success', '会员试用申请成功 %s 项' % min(remain, len(candidates))


def perform_lottery(api, portal, state):
    info = checked(api.get_daily_lottery_info(state))
    count = int(info['remain_times'])
    if count <= 0:
        return 'skipped', '天天抽奖无可用次数'
    if info.get('session_id') is None:
        raise SafeFailure('缺少抽奖场次，禁止猜测参数')
    for i in range(count):
        result = checked(api.exec_daily_lottery(portal, info['component_number'], info['component_node_id'], info['session_id']))
        log('天天抽奖第 %s 次: ✅ 业务成功；奖品 %s' % (i + 1, business_label(result.get('reward_name'))))
        if i + 1 < count:
            time.sleep(1)
    return 'success', '天天抽奖成功 %s 次' % count


CENTER_ACTIVITY = 'HD2025031821201822'
CENTER_PAGE = 'YM2025041617143388'

def center_request(api, method, url, data=None, params=None, extra_headers=None):
    result = checked(api._request(method, url, json_data=data, params=params, headers=extra_headers))['data']
    if result.get('result') != 'ok':
        if result.get('msg') == 'has sign' and url.endswith('/sign_in'):
            return {'already_signed': True}
        checked(api._build_failure_result(result))
    return result


def center_info(api):
    result = center_request(api, 'GET', api.PAGE_INFO_URL, params={'activity_number': CENTER_ACTIVITY, 'page_number': CENTER_PAGE})
    data = result.get('data')
    if not isinstance(data, list):
        raise SafeFailure('任务中心页面结构异常')
    points = next((d.get('task_center_user_info') for d in data if isinstance(d, dict) and d.get('type') == 36 and isinstance(d.get('task_center_user_info'), dict)), None)
    if points is None or 'integral' not in points or 'advent_integral' not in points:
        raise SafeFailure('任务中心缺少积分字段')
    log('任务中心积分 %s；即将过期积分 %s' % (int(points['integral']), int(points['advent_integral'])))
    lotteries = [d for d in data if isinstance(d, dict) and d.get('type') == 45 and isinstance(d.get('lottery_v2'), dict)]
    return lotteries


def center_sign(api, account):
    uid = account.get('user_id')
    if not uid or not str(uid).isdigit():
        raise SafeFailure('任务中心需要同账号的数字 user_id')
    try:
        from Crypto.Cipher import AES, PKCS1_v1_5
        from Crypto.PublicKey import RSA
        from Crypto.Util.Padding import pad
    except ImportError:
        raise SafeFailure('任务中心需要公共依赖 pycryptodome') from None
    key = center_request(api, 'GET', 'https://personal-bus.wps.cn/sign_in/v1/encrypt/key').get('data')
    if not isinstance(key, str) or not key:
        raise SafeFailure('任务中心公钥响应结构异常')
    aes_key = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(22)) + str(int(time.time()))
    raw = json.dumps({'user_id': int(uid), 'platform': 64}, separators=(',', ':')).encode()
    extra = base64.b64encode(AES.new(aes_key.encode(), AES.MODE_CBC, aes_key[:16].encode()).encrypt(pad(raw, AES.block_size))).decode()
    token = base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(key))).encrypt(aes_key.encode())).decode()
    result = center_request(api, 'POST', 'https://personal-bus.wps.cn/sign_in/v1/sign_in', data={'encrypt': True, 'extra': extra, 'pay_origin': 'pc_ucs_rwzx_sign'}, extra_headers={'token': token})
    rewards = result.get('data', {}).get('rewards', []) if isinstance(result.get('data'), dict) else []
    for reward in rewards:
        if isinstance(reward, dict) and reward.get('reward_name'):
            log('任务中心签到奖励：' + business_label(reward['reward_name']))
    center_info(api)
    return ('already', '任务中心今日已签到') if result.get('already_signed') else ('success', '任务中心签到成功，积分查询成功')


def center_lottery(api, account):
    components = center_info(api)
    limit = account.get('max_lottery_limit', 5)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise SafeFailure('max_lottery_limit 必须为非负整数')
    chosen = None
    for component in components:
        for session in component['lottery_v2'].get('lottery_list', []):
            if session.get('session_status') == 'IN_PROGRESS':
                chosen = (component, session)
                break
        if chosen:
            break
    if not chosen:
        raise SafeFailure('任务中心未提供有效抽奖场次')
    component, session = chosen
    count = min(int(session.get('times', 0)), limit)
    if count <= 0:
        return 'skipped', '任务中心无可用抽奖次数或限制为零'
    portal = {'activity_number': CENTER_ACTIVITY, 'page_number': CENTER_PAGE,
              'link': 'https://personal-act.wps.cn/rubik2/portal/' + CENTER_ACTIVITY + '/' + CENTER_PAGE,
              'filter_params': {'cs_from': '', 'mk_key': 'JkVKsOtv4aCLMdNdAKwUGoz9tfKeFZVKyjEe', 'position': 'mac_grzx_sign'}}
    if not component.get('number') or not component.get('component_node_id') or session.get('session_id') is None:
        raise SafeFailure('任务中心抽奖组件参数缺失')
    for i in range(count):
        result = center_request(api, 'POST', api.COMPONENT_ACTION_URL, data={
            'component_uniq_number': {'activity_number': CENTER_ACTIVITY, 'page_number': CENTER_PAGE,
                'component_number': component['number'], 'component_node_id': component['component_node_id'],
                'filter_params': portal['filter_params']},
            'component_type': 45, 'component_action': 'lottery_v2.exec',
            'lottery_v2': {'session_id': session['session_id']}
        }, extra_headers={'referer': portal['link'] + '?' + urlencode(portal['filter_params']),
                          'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty'})
        action = result.get('data', {}).get('lottery_v2', {})
        if action.get('success') is not True:
            raise SafeFailure('任务中心抽奖未确认业务成功')
        log('任务中心第 %s 次抽奖: ✅ 业务成功；奖品 %s' % (i + 1, business_label(action.get('reward_name'))))
        if i + 1 < count:
            time.sleep(1)
    center_info(api)
    return 'success', '任务中心抽奖成功 %s 次，积分已刷新' % count


def parse_account(line):
    if line.startswith('{'):
        try:
            account = json.loads(line)
        except Exception:
            raise SafeFailure('账号 JSON 格式错误') from None
        if not isinstance(account, dict) or not isinstance(account.get('cookies'), str):
            raise SafeFailure('账号 JSON 必须包含 cookies 字符串')
    else:
        uid, delimiter, cookie = line.partition('|')
        account = {'user_id': uid.strip(), 'cookies': cookie.strip()} if delimiter else {'cookies': line}
    parse_cookie(account['cookies'])
    if account.get('user_agent') is not None and not isinstance(account['user_agent'], str):
        raise SafeFailure('user_agent 必须为字符串')
    if any(c in (account.get('user_agent') or '') for c in '\r\n'):
        raise SafeFailure('user_agent 格式错误')
    return account


TASK_NAMES = {'checkin': '免费会员签到', 'reward': '七天领奖', 'trial': '会员试用申请',
              'lottery': '天天抽奖', 'task_center': '任务中心签到与积分',
              'task_center_lottery': '任务中心抽奖与积分刷新'}


def run_account(index, line, tasks, dry):
    start = time.monotonic()
    IDENTITIES.clear()
    CLAIMED_SERIES.clear()
    SECRET_VALUES.clear()
    records = []
    stage_number = 0
    def stage(name, action):
        nonlocal stage_number
        stage_number += 1
        started = time.monotonic()
        log('账号 %s 阶段 %s：%s 开始' % (index, stage_number, name))
        try:
            status, detail = action()
        except SafeFailure as exc:
            status, detail = 'failure', str(exc)
        except Exception:
            status, detail = 'failure', '内部处理或服务结构异常（已隐藏敏感信息）'
        elapsed = round(time.monotonic() - started, 3)
        records.append({'stage': name, 'status': status, 'seconds': elapsed})
        log('账号 %s 阶段 %s：%s %s；耗时 %.3f 秒' % (index, stage_number, {'success':'✅', 'already':'☑️', 'skipped':'⏭️', 'failure':'❌'}[status], detail, elapsed))
        return status != 'failure'
    account = None
    def config():
        nonlocal account
        account = parse_account(line)
        SECRET_VALUES.add(account['cookies'])
        SECRET_VALUES.update(parse_cookie(account['cookies']).values())
        if {'task_center', 'task_center_lottery'} & tasks and (not str(account.get('user_id', '')).isdigit()):
            raise SafeFailure('已启用任务中心，需要数字 user_id|Cookie')
        if 'task_center_lottery' in tasks:
            limit = account.get('max_lottery_limit', 5)
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise SafeFailure('max_lottery_limit 必须为非负整数')
        return 'success', '账号参数格式通过（不代表凭据有效）'
    valid = stage('参数校验', config)
    if valid:
        if dry:
            for key in TASK_NAMES:
                if key in tasks:
                    stage(TASK_NAMES[key], lambda: ('skipped', 'DRY_RUN_OK：已预演任务计划，未发送请求或修改账号'))
        else:
            api = DailyBenefitsAPI(account['cookies'], account.get('user_agent') or os.environ.get('WPS_USER_AGENT'))
            if 'task_center' in tasks:
                stage(TASK_NAMES['task_center'], lambda: center_sign(api, account))
            if 'task_center_lottery' in tasks:
                stage(TASK_NAMES['task_center_lottery'], lambda: center_lottery(api, account))
            if {'checkin', 'reward', 'trial', 'lottery'} & tasks:
                portal = None
                def discover():
                    nonlocal portal
                    portal = checked(api.get_benefit_portal())
                    page(api, portal)
                    return 'success', '福利中心入口与页面业务状态已确认'
                if stage('双渠道入口发现与页面查询', discover):
                    # Claim an old completed series before check-in can start a new one.
                    if 'reward' in tasks:
                        stage('检查历史七天领奖', lambda: claim_ready(api, portal, page(api, portal)))
                    for key, action in (('checkin', perform_checkin), ('trial', perform_trial), ('lottery', perform_lottery)):
                        if key in tasks:
                            stage(TASK_NAMES[key], lambda action=action: action(api, portal, page(api, portal)))
                    if 'reward' in tasks and {'checkin', 'lottery'} & tasks:
                        stage('刷新后七天领奖', lambda: claim_ready(api, portal, page(api, portal)))
    stats = {k: sum(r['status'] == k for r in records) for k in ('success', 'already', 'skipped', 'failure')}
    ok = valid and stats['failure'] == 0
    duration = round(time.monotonic() - start, 3)
    log('账号 %s 统计：任务 %s，成功 %s，已完成 %s，跳过 %s，失败 %s；耗时 %.3f 秒；%s' % (index, len(records), stats['success'], stats['already'], stats['skipped'], stats['failure'], duration, '预演通过' if dry and ok else '成功' if ok else '失败'))
    return {'account': index, 'success': ok, 'statistics': stats, 'stages': records, 'seconds': duration}


def notify_summary(body, dry):
    if os.environ.get('QINGLONG_NOTIFY', '1').strip().lower() in {'0', 'false', 'no', 'off'}:
        return '已关闭'
    if dry:
        log('断网预演通知正文：' + body.replace('\n', '；'))
        return '断网预演已生成通知，未发送'
    title = 'WPS天天领福利'
    # Run every notifier in a bounded child; never print notifier output or exceptions.
    child = """import importlib.util, sys
if sys.argv[1]:
    spec = importlib.util.spec_from_file_location('qinglong_notification', sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(sys.argv[2], sys.argv[3])
"""
    def run(command):
        try:
            completed = subprocess.run(command, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return completed.returncode == 0
        except Exception:
            return False
    if run([sys.executable, '-c', child, '', title, body]):
        return '已调用 notify.py'
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for directory in filter(None, directories):
        py = Path(directory) / 'notify.py'
        if py.is_file():
            return '已调用 notify.py' if run([sys.executable, '-c', child, str(py), title, body]) else '通知调用失败，业务退出码保持不变'
        js = Path(directory) / 'sendNotify.js'
        if js.is_file():
            command = ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(js), title, body]
            return '已调用 sendNotify.js' if run(command) else '通知调用失败，业务退出码保持不变'
    return '通知模块不可用，业务退出码保持不变'


def main():
    started = time.monotonic()
    dry = enabled('WPS_DRY_RUN')
    lines = [s.strip() for s in os.environ.get('WPS_ACCOUNTS', '').splitlines() if s.strip()]
    log('========== WPS天天领福利 ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('模式：' + ('断网预演' if dry else '正式执行') + '；账号数量：' + str(len(lines)))
    results = []
    config_error = None
    tasks = set(s.strip() for s in os.environ.get('WPS_TASKS', 'checkin,reward').split(',') if s.strip())
    if not lines:
        config_error = '未配置 WPS_ACCOUNTS'
    elif not tasks or tasks - TASK_NAMES.keys():
        config_error = 'WPS_TASKS 为空或包含未知任务'
    elif any(c in os.environ.get('WPS_USER_AGENT', '') for c in '\r\n'):
        config_error = 'WPS_USER_AGENT 格式错误'
    if config_error:
        log('阶段 1 参数校验：❌ ' + config_error + '；耗时 0 秒')
    else:
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, tasks, dry))
    success = sum(r['success'] for r in results)
    failed = len(lines) - success
    status = 'configuration-error' if config_error else 'failure' if failed and not success else 'partial-failure' if failed else 'dry-run' if dry else 'success'
    code = 1 if config_error or failed else 0
    body = '模式：%s\n账号总数：%s\n成功数：%s\n失败数：%s\n最终状态：%s' % ('断网预演' if dry else '正式执行', len(lines), success, failed, status)
    for result in results:
        body += '\n账号 %s：%s；阶段失败 %s' % (result['account'], '预演通过' if dry and result['success'] else '成功' if result['success'] else '失败', result['statistics']['failure'])
    notification = notify_summary(body, dry)
    totals = {k: sum(r['statistics'][k] for r in results) for k in ('success', 'already', 'skipped', 'failure')}
    finish = time.strftime('%Y-%m-%d %H:%M:%S')
    duration = round(time.monotonic() - started, 3)
    log('----------------------------------------')
    log('任务统计：账号总数 %s，成功 %s，失败 %s；子任务成功 %s，已完成 %s，跳过 %s，失败 %s；总耗时 %.3f 秒' % (len(lines), success, failed, totals['success'], totals['already'], totals['skipped'], totals['failure'], duration))
    log('通知状态：' + notification)
    log('完成时间：' + finish + '；最终状态：' + status)
    if not code:
        log('DRY_RUN_OK：断网预演通过' if dry else 'WPS_TASK_SUCCESS：全部账号业务已核验成功')
    print('TASK_SUMMARY=' + json.dumps({'task': 'WPS天天领福利', 'mode': 'dry-run' if dry else 'live', 'status': status, 'accounts': len(lines), 'success': success, 'failed': failed, 'statistics': totals, 'results': results, 'notification': notification, 'seconds': duration, 'finishedAt': finish, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
