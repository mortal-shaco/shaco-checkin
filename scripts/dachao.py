#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 大潮App签到阅读
# cron: 22 10,14,18 * * *
# 来源: Cat-zaizai/ZaiZaiCat-Checkin, script/dachao/{main,api,captcha,http_debug}.py
# 上游提交: d6a334e43d0a0c8f41b039cd410be33593efc35b
# 许可: MIT。原文件未携带单独版权声明；保留上游署名及以下许可。
# MIT License
# Copyright (c) Cat-zaizai/ZaiZaiCat-Checkin contributors
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
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
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('7b77205efaf0158a', 'scripts/dachao.py', 'dachao.py', 'dachao')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import os
import sys
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime
from io import BytesIO
requests = None
np = None
Image = None
"""
滑动验证码偏移量计算（dachao）

说明：
- 该逻辑从 script/dachao_bak/captcha.py 迁移而来，保持算法一致，供 dachao 阅读任务验证码使用。
- 需要依赖：numpy、Pillow、requests（项目 requirements.txt 通常已包含）。
"""
import logging
from io import BytesIO
from typing import Optional
logger = logging.getLogger(__name__)

def _calculate_offset_method1(part1_with_gap: np.ndarray, part3_complete: np.ndarray) -> Optional[int]:
    diff = np.abs(part1_with_gap.astype(int) - part3_complete.astype(int))
    diff_gray = np.sum(diff, axis=2) if len(diff.shape) == 3 else diff
    height = diff_gray.shape[0]
    edge_positions = []
    for row in range(height):
        row_diff = diff_gray[row, :]
        threshold = 30
        if np.max(row_diff) > threshold:
            significant = np.where(row_diff > threshold)[0]
            if len(significant) > 0:
                edge_positions.append(significant[0])
    if edge_positions:
        return int(np.median(edge_positions))
    return None

def _calculate_offset_method2(part2_slider: np.ndarray, part3_complete: np.ndarray, slider_width: int=50) -> int:
    slider = part2_slider[:, 0:slider_width]
    min_diff = float('inf')
    best_x = 0
    img_width = part3_complete.shape[1]
    for x in range(0, img_width - slider_width):
        region = part3_complete[:, x:x + slider_width, :] if len(part3_complete.shape) == 3 else part3_complete[:, x:x + slider_width]
        diff = np.sum((slider.astype(int) - region.astype(int)) ** 2)
        if diff < min_diff:
            min_diff = diff
            best_x = x
    return best_x

def _calculate_offset_method3(part1_with_gap: np.ndarray, part3_complete: np.ndarray) -> Optional[int]:
    diff = np.abs(part1_with_gap.astype(int) - part3_complete.astype(int))
    col_diff = np.sum(diff, axis=(0, 2)) if len(diff.shape) == 3 else np.sum(diff, axis=0)
    threshold = np.mean(col_diff) + 0.8 * np.std(col_diff)
    gap_cols = np.where(col_diff > threshold)[0]
    if len(gap_cols) > 0:
        return int(gap_cols[0])
    return None

def calculate_slide_offset(image_url: str) -> Optional[int]:
    """
    计算滑动验证码的偏移量 tn_x。

    验证码图片由三部分（从上到下）：
    1) 带缺口的背景
    2) 滑块
    3) 完整背景
    """
    img_array = download_captcha_image(image_url)
    if img_array is None:
        return None
    height = img_array.shape[0]
    if height % 3 != 0:
        pass
        return None
    part_height = height // 3
    part1_with_gap = img_array[0:part_height, :]
    part2_slider = img_array[part_height:part_height * 2, :]
    part3_complete = img_array[part_height * 2:part_height * 3, :]
    results = []
    try:
        offset1 = _calculate_offset_method1(part1_with_gap, part3_complete)
        if offset1 is not None:
            results.append(offset1)
    except Exception as e:
        pass
    try:
        offset2 = _calculate_offset_method2(part2_slider, part3_complete)
        if offset2 is not None:
            results.append(offset2)
    except Exception as e:
        pass
    try:
        offset3 = _calculate_offset_method3(part1_with_gap, part3_complete)
        if offset3 is not None:
            results.append(offset3)
    except Exception as e:
        pass
    if not results:
        pass
        return None
    final_offset = int(np.median(results))
    pass
    return final_offset
"""
大潮（新流程）API 模块

特点：
- 账号密码登录（passport -> vapp -> aihoge member）
- 动态获取签到/阅读活动 tid
- RSA 加密 params（PKCS#1 v1.5 + Base64）

注意：
- 部分接口涉及 X-SIGNATURE / signature 字段，线上可能有更严格的校验；本实现提供可覆盖的“签名生成”入口。
- 请勿在日志中打印 token/cookie 等敏感信息。
"""
import base64
import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    serialization = None
    padding = None
logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = (10, 30)
REDEEM_ALREADY_RECEIVED_CODES = {'is_receive_packet'}

def interpret_redeem_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    统一解析红包兑换返回。

    Returns:
        {
          "ok": bool,              # 是否视为成功
          "already_received": bool,# 是否为“已领取”
          "code": str,             # 业务码（字符串化）
          "message": str,          # 业务信息
        }
    """
    if not isinstance(resp, dict):
        return {'ok': False, 'already_received': False, 'code': '', 'message': 'invalid_response'}
    success = resp.get('success')
    if success in (True, 1, '1'):
        return {'ok': True, 'already_received': False, 'code': 'success', 'message': ''}
    if resp.get('code') == 0:
        return {'ok': True, 'already_received': False, 'code': 'code=0', 'message': str(resp.get('message') or '')}
    error_code = resp.get('error_code')
    error_code_str = str(error_code) if error_code is not None else ''
    error_message = str(resp.get('error_message') or resp.get('message') or resp.get('error') or '')
    if error_code_str in REDEEM_ALREADY_RECEIVED_CODES:
        return {'ok': True, 'already_received': True, 'code': error_code_str, 'message': error_message or '已领取'}
    if error_code == 0 or error_code_str == '0':
        return {'ok': True, 'already_received': False, 'code': error_code_str, 'message': error_message}
    return {'ok': False, 'already_received': False, 'code': error_code_str, 'message': error_message or '未知错误'}
PUBLIC_KEY_PEM = '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0G25Cq2HxQQ+gX9H2dzb\n6sbRtHzD8JbHRmOrAFzaWI2kdzbPuga4ZlqxOAyoAm8ucIAeKD4joUn+dN1wYC03\nqCgloNU21KUJUls/Htp2RwxpmoncSIAOZvSQQ6Kl3vLPYlG6GetwYYN83sG85K+3\nw4D89hBGHuYqKQyQsUvntxi5UVoNfo674QsCvqxHxZAuEXKoEagzUoSu8gWrDTuh\nRK4aQcDpnCslwKycaO63UBvfTlBG0Jc7sqzXxapTArbqaA58XCM8dRIZdp7DR/V7\nqucn/PwIOGJrOu09/cjndwIpeki8HXa9rvgWwiwZCy289vgRoxzIcLrQJ2oC1MK2\nRwIDAQAB\n-----END PUBLIC KEY-----'
VAPP_SIGNATURE_SALT = 'FR*r!isE5W'

def _mask_mobile(mobile: str) -> str:
    m = str(mobile or '')
    if len(m) < 7:
        return '*' * len(m)
    return f'{m[:3]}****{m[-4:]}'

def _mask_secret(value: str, keep_head: int=4, keep_tail: int=4) -> str:
    s = str(value or '')
    if not s:
        return ''
    if len(s) <= keep_head + keep_tail:
        return '*' * len(s)
    return f'{s[:keep_head]}...{s[-keep_tail:]}(len={len(s)})'

def _safe_json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))

def _parse_tid_from_url(url: str) -> str:
    if not url:
        return ''
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    tid = (qs.get('tid') or [''])[0]
    return str(tid or '')

@dataclass
class NewDachaoAccountConfig:
    account_name: str
    phone_number: str
    password_encrypted: str
    tenant_id: str = '94'
    client_id: str = '10048'
    session_id: str = ''
    user_agent: str = ''
    passport_cookies: str = ''
    vapp_cookies: str = ''
    aihoge_cookies: str = ''
    forum_session_id: str = ''
    forum_cookies: str = ''
    forum_tenant_id: str = '10'
    redeem_member: str = ''
    redeem_cookies: str = ''
    redeem_user_agent: str = ''
    passport_signature_salt: str = ''
    aihoge_signature_salt: str = ''
    sign_lottery_id: str = ''

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewDachaoAccountConfig':
        account_name = (data.get('account_name') or '未命名账号').strip()
        phone_number = str(data.get('phone_number') or '').strip()
        password_encrypted = str(data.get('password_encrypted') or data.get('password') or '').strip()
        user_agent = str(data.get('user_agent') or data.get('user_agent_vapp') or data.get('user_agent_aihoge') or '').strip()
        if not phone_number:
            raise ValueError('接口返回或账号配置不满足必要契约')
        if not password_encrypted:
            raise ValueError('接口返回或账号配置不满足必要契约')
        if not user_agent:
            raise ValueError('接口返回或账号配置不满足必要契约')
        return cls(account_name=account_name, phone_number=phone_number, password_encrypted=password_encrypted, tenant_id=str(data.get('tenant_id') or '94'), client_id=str(data.get('client_id') or '10048'), session_id=str(data.get('session_id') or ''), user_agent=user_agent, passport_cookies=str(data.get('passport_cookies') or ''), vapp_cookies=str(data.get('vapp_cookies') or ''), aihoge_cookies=str(data.get('cookies') or data.get('aihoge_cookies') or ''), forum_session_id=str(data.get('forum_session_id') or ''), forum_cookies=str(data.get('forum_cookies') or ''), forum_tenant_id=str(data.get('forum_tenant_id') or '10'), redeem_member=str(data.get('redeem_member') or data.get('withdraw_member') or ''), redeem_cookies=str(data.get('redeem_cookies') or ''), redeem_user_agent=str(data.get('redeem_user_agent') or ''), passport_signature_salt=str(data.get('passport_signature_salt') or ''), aihoge_signature_salt=str(data.get('aihoge_signature_salt') or ''), sign_lottery_id=str(data.get('sign_lottery_id') or ''))

@dataclass
class DachaoLoginContext:
    session_id: str
    account_id: str
    tenant_id: str
    nick_name: str
    avatar_url: str
    mobile: str

class RsaEncryptor:

    def __init__(self) -> None:
        if serialization is not None:
            self._pubkey = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode('utf-8'))
        else:
            self._pubkey = None

    def encrypt_base64_pkcs1v15(self, plaintext: str) -> str:
        if self._pubkey is None or padding is None:
            raise RuntimeError('缺少依赖 cryptography，无法进行 RSA 加密；请从公共包仓库安装 cryptography。')
        data = plaintext.encode('utf-8')
        key_size_bytes = self._pubkey.key_size // 8
        max_len = key_size_bytes - 11
        if len(data) > max_len:
            raise ValueError('接口返回或账号配置不满足必要契约')
        ct = self._pubkey.encrypt(data, padding.PKCS1v15())
        return base64.b64encode(ct).decode('ascii')

class VappSigner:

    def __init__(self, salt: str=VAPP_SIGNATURE_SALT):
        self.salt = salt

    @staticmethod
    def _request_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _timestamp_ms() -> str:
        return str(int(time.time() * 1000))

    def signature(self, path: str, session_id: str, request_id: str, timestamp_ms: str, tenant_id: str) -> str:
        preimage = f'{path}&&{session_id}&&{request_id}&&{timestamp_ms}&&{self.salt}&&{tenant_id}'
        return hashlib.sha256(preimage.encode('utf-8')).hexdigest()

class TmuyunPassportClient:
    BASE_URL = 'https://passport.tmuyun.com'

    def __init__(self, session: Optional[requests.Session]=None):
        self.session = session or requests.Session()
        self.session.trust_env = False

    @staticmethod
    def _build_signature_placeholder(path: str, request_id: str, salt: str='') -> str:
        preimage = f'{path}&&{request_id}'
        if salt:
            preimage = f'{preimage}&&{salt}'
        return hashlib.sha256(preimage.encode('utf-8')).hexdigest()

    def credential_auth(self, phone_number: str, password_encrypted: str, client_id: str, user_agent: str, cookies: str='', signature_salt: str='', account_name: str='', timeout: int=30) -> str:
        path = '/web/oauth/credential_auth'
        url = f'{self.BASE_URL}{path}'
        request_id = str(uuid.uuid4())
        signature = self._build_signature_placeholder(path, request_id, salt=signature_salt)
        headers = {'User-Agent': user_agent, 'Content-Type': 'application/x-www-form-urlencoded', 'Accept-Language': 'zh-CN,zh-Hans;q=0.9', 'X-REQUEST-ID': request_id, 'X-SIGNATURE': signature}
        if cookies:
            headers['Cookie'] = cookies
        data = {'client_id': client_id, 'password': password_encrypted, 'phone_number': phone_number}
        payload = request_json(self.session, method='POST', url=url, headers=headers, data=data, timeout=timeout, account_name=account_name)
        if payload.get('code') != 0:
            raise RuntimeError('接口返回或账号配置不满足必要契约')
        code = payload.get('data', {}).get('authorization_code', {}).get('code', '')
        if not code:
            raise RuntimeError('接口返回或账号配置不满足必要契约')
        return str(code)

class TmuyunVappClient:
    BASE_URL = 'https://vapp.tmuyun.com'

    def __init__(self, session: Optional[requests.Session]=None, signer: Optional[VappSigner]=None):
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.signer = signer or VappSigner()

    @staticmethod
    def _random_session_seed() -> str:
        return uuid.uuid4().hex[:24]

    def _signed_headers(self, *, path: str, session_id: str, tenant_id: str, account_id: str='', user_agent: str='', cookies: str='', extra: Optional[Dict[str, str]]=None) -> Dict[str, str]:
        request_id = self.signer._request_id()
        timestamp = self.signer._timestamp_ms()
        signature = self.signer.signature(path, session_id, request_id, timestamp, tenant_id)
        headers = {'User-Agent': user_agent, 'X-TIMESTAMP': timestamp, 'X-SESSION-ID': session_id, 'X-SIGNATURE': signature, 'X-TENANT-ID': tenant_id, 'X-REQUEST-ID': request_id, 'Accept-Language': 'zh-Hans-CN;q=1, en-CN;q=0.9', 'Content-Type': 'application/x-www-form-urlencoded'}
        if account_id:
            headers['X-ACCOUNT-ID'] = account_id
        if cookies:
            headers['Cookie'] = cookies
        if extra:
            headers.update(extra)
        return headers

    def login_with_code(self, code: str, tenant_id: str, user_agent: str, cookies: str='', session_seed: str='', account_name: str='', timeout: int=30) -> DachaoLoginContext:
        path = '/api/zbtxz/login'
        url = f'{self.BASE_URL}{path}'
        seed = session_seed or self._random_session_seed()
        headers = self._signed_headers(path=path, session_id=seed, tenant_id=tenant_id, account_id='', user_agent=user_agent, cookies=cookies, extra={'X-Auth-Token': '', 'YI-TOKEN': ''})
        payload = request_json(self.session, method='POST', url=url, headers=headers, data={'code': code}, timeout=timeout, account_name=account_name)
        if payload.get('code') != 0:
            raise RuntimeError('接口返回或账号配置不满足必要契约')
        data = payload.get('data', {}) or {}
        session_info = data.get('session', {}) or {}
        account_info = data.get('account', {}) or {}
        session_id = str(session_info.get('id') or '')
        account_id = str(account_info.get('id') or '')
        nick_name = str(account_info.get('nick_name') or '')
        avatar_url = str(account_info.get('image_url') or '')
        mobile = str(account_info.get('mobile') or account_info.get('phone_number') or '')
        if not session_id or not account_id:
            raise RuntimeError('接口返回或账号配置不满足必要契约')
        return DachaoLoginContext(session_id=session_id, account_id=account_id, tenant_id=str(tenant_id), nick_name=nick_name, avatar_url=avatar_url, mobile=mobile)

    def mypage_list(self, ctx: DachaoLoginContext, user_agent: str, cookies: str='', account_name: str='', timeout: int=30) -> Dict[str, Any]:
        path = '/api/myPage/list'
        url = f'{self.BASE_URL}{path}'
        headers = self._signed_headers(path=path, session_id=ctx.session_id, tenant_id=ctx.tenant_id, account_id=ctx.account_id, user_agent=user_agent, cookies=cookies, extra={'X-Auth-Token': '', 'YI-TOKEN': ''})
        return request_json(self.session, method='GET', url=url, headers=headers, timeout=timeout, account_name=account_name)

    def buoy_list(self, ctx: DachaoLoginContext, user_agent: str, cookies: str='', account_name: str='', timeout: int=30) -> Dict[str, Any]:
        path = '/api/buoy/list'
        url = f'{self.BASE_URL}{path}'
        headers = self._signed_headers(path=path, session_id=ctx.session_id, tenant_id=ctx.tenant_id, account_id=ctx.account_id, user_agent=user_agent, cookies=cookies, extra={'X-Auth-Token': '', 'YI-TOKEN': ''})
        return request_json(self.session, method='GET', url=url, headers=headers, timeout=timeout, account_name=account_name)

    def report_read_time(self, ctx: DachaoLoginContext, channel_article_id: str, read_time_ms: int, user_agent: str, cookies: str='', account_name: str='', timeout: int=30) -> Dict[str, Any]:
        path = '/api/article/read_time'
        url = f'{self.BASE_URL}{path}'
        params = {'channel_article_id': str(channel_article_id), 'is_end': '1', 'read_time': str(read_time_ms)}
        headers = self._signed_headers(path=path, session_id=ctx.session_id, tenant_id=ctx.tenant_id, account_id=ctx.account_id, user_agent=user_agent, cookies=cookies, extra={'X-Auth-Token': '', 'YI-TOKEN': ''})
        return request_json(self.session, method='GET', url=url, headers=headers, params=params, timeout=timeout, account_name=account_name)

class AihogeClient:
    BASE_URL = 'https://m.aihoge.com'

    def __init__(self, *, member_header: str, account_id: str, session_id: str, cookies: str='', user_agent: str='', redeem_member: str='', redeem_cookies: str='', redeem_user_agent: str='', account_name: str=''):
        self.session = requests.Session()
        self.session.trust_env = False
        self.member_header = member_header
        self.account_id = account_id
        self.session_id = session_id
        self.cookies = cookies
        self.user_agent = user_agent
        self.redeem_member = redeem_member
        self.redeem_cookies = redeem_cookies
        self.redeem_user_agent = redeem_user_agent
        self.account_name = account_name
        self._rsa = RsaEncryptor()
        self._captcha_verified = False

    def _common_headers(self, *, limit_id: str, referer_url: str) -> Dict[str, str]:
        headers = {'User-Agent': self.user_agent, 'Accept': 'application/json, text/plain, */*', 'HTTP-X-H5-VERSION': '1', 'X-CLIENT-VERSION': '1314', 'X-DEVICE-SIGN': 'xsb_hn', 'X-DEVICE-ID': '000', 'Limit': limit_id, 'Referer': referer_url, 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty', 'Accept-Language': 'zh-CN,zh-Hans;q=0.9', 'accountId': self.account_id, 'sessionId': self.session_id, 'member': self.member_header}
        if self.cookies:
            headers['Cookie'] = self.cookies
        return headers

    def sign_in(self, activity_id: str, sign_page_url: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/signhy/client/actSign/actSign'
        payload = {'activity_id': activity_id, 'timestamp': str(int(time.time()))}
        encrypted = self._rsa.encrypt_base64_pkcs1v15(_safe_json_dumps(payload))
        headers = self._common_headers(limit_id=activity_id, referer_url=sign_page_url)
        headers.update({'Content-Type': 'application/json;charset=utf-8', 'Origin': 'https://m.aihoge.com'})
        return request_json(self.session, method='POST', url=url, headers=headers, json_body={'params': encrypted}, timeout=30, account_name=self.account_name)

    def get_news_list(self, news_tid: str, referer_url: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/newshy/api/client/news/list/{news_tid}'
        headers = self._common_headers(limit_id=news_tid, referer_url=referer_url)
        return request_json(self.session, method='GET', url=url, headers=headers, timeout=30, account_name=self.account_name)

    @staticmethod
    def extract_articles(news_list_resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        data = news_list_resp.get('data', [])
        if not data:
            return []
        first = data[0] or {}
        limit = first.get('limit', {}) or {}
        column_set = limit.get('column_set', {}) or {}
        column_list = column_set.get('column_list', []) or []
        if not column_list:
            return []
        articles = (column_list[0] or {}).get('data', []) or []
        return [a for a in articles if isinstance(a, dict)]

    @staticmethod
    def extract_award_activity_id(news_list_resp: Dict[str, Any]) -> str:
        data = news_list_resp.get('data', [])
        if not data:
            return ''
        first = data[0] or {}
        limit = first.get('limit', {}) or {}
        rtc = limit.get('read_task_config', {}) or {}
        return str(rtc.get('awardActivityId') or '')

    def _read_article_internal(self, *, news_tid: str, item_id: str, referer_url: str, tn_x: Optional[int]=None, request_id: Optional[str]=None) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/newshy/api/client/news/readArticle'
        payload: Dict[str, Any] = {'news_id': news_tid, 'item_id': item_id, 'timestamp': str(int(time.time()))}
        if tn_x is not None and request_id is not None:
            payload['tn_x'] = int(tn_x)
            payload['request_id'] = str(request_id)
        encrypted = self._rsa.encrypt_base64_pkcs1v15(_safe_json_dumps(payload))
        headers = self._common_headers(limit_id=news_tid, referer_url=referer_url)
        headers.update({'Content-Type': 'application/json;charset=utf-8', 'Origin': 'https://m.aihoge.com', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
        return request_json(self.session, method='POST', url=url, headers=headers, json_body={'params': encrypted}, timeout=30, account_name=self.account_name)

    def get_captcha(self, news_tid: str, referer_url: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/newshy/api/client/news/getTnCode'
        headers = self._common_headers(limit_id=news_tid, referer_url=referer_url)
        headers['X-Requested-With'] = 'XMLHttpRequest'
        return request_json(self.session, method='GET', url=url, headers=headers, params={'t': str(random.random())}, timeout=30, account_name=self.account_name)

    def complete_read_task(self, news_tid: str, item_id: str, referer_url: str) -> Dict[str, Any]:
        if self._captcha_verified:
            return self._read_article_internal(news_tid=news_tid, item_id=item_id, referer_url=referer_url)
        result = self._read_article_internal(news_tid=news_tid, item_id=item_id, referer_url=referer_url)
        need_captcha = result.get('error_code') == 'INVALID_CODE' or result.get('error_message') == '验证码错误'
        if not need_captcha:
            if result.get('success') == 1:
                self._captcha_verified = True
            return result
        if calculate_slide_offset is None:
            pass
            return result
        captcha = self.get_captcha(news_tid=news_tid, referer_url=referer_url)
        request_id = captcha.get('request_id')
        img_url = captcha.get('img')
        if not request_id or not img_url:
            return result
        tn_x = calculate_slide_offset(img_url)
        if tn_x is None:
            return result
        time.sleep(random.uniform(3, 5))
        result = self._read_article_internal(news_tid=news_tid, item_id=item_id, referer_url=referer_url, tn_x=tn_x, request_id=request_id)
        if result.get('success') == 1:
            self._captcha_verified = True
        return result

    @staticmethod
    def extract_channel_article_id(link: str) -> str:
        if not link:
            return ''
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            return str((params.get('id') or [''])[0] or '')
        except Exception:
            return ''

    def get_lottery_info(self, lottery_id: str, limit_id: str, referer_url: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/lotteryhy/designh5/client/activity/{lottery_id}'
        headers = self._common_headers(limit_id=limit_id, referer_url=referer_url)
        return request_json(self.session, method='GET', url=url, headers=headers, timeout=30, account_name=self.account_name)

    def get_remain_counts(self, lottery_id: str, limit_id: str, referer_url: str) -> int:
        data = self.get_lottery_info(lottery_id=lottery_id, limit_id=limit_id, referer_url=referer_url)
        try:
            return int((data.get('response') or {}).get('remain_counts') or 0)
        except Exception:
            return 0

    def draw_lottery(self, lottery_id: str, limit_id: str, referer_url: str) -> Dict[str, Any]:
        url = f'{self.BASE_URL}/api/lotteryhy/api/client/cj/awd/drw/{lottery_id}'
        headers = self._common_headers(limit_id=limit_id, referer_url=referer_url)
        headers.update({'Content-Type': 'application/json;charset=utf-8', 'Origin': 'https://m.aihoge.com', 'Content-Length': '0'})
        return request_json(self.session, method='POST', url=url, headers=headers, timeout=30, account_name=self.account_name)

    def redeem_red_packet(self, code: str) -> Dict[str, Any]:
        """
        兑换现金红包（抽奖 type=3 时返回的 code）。

        对应你给的 Loon 脚本：
        POST https://m.aihoge.com/api/lotteryhy/api/client/cj/send/pak
        body: {"code": "..."}

        关键点：
        - headers.member 必须使用「兑换 member」（通常 source=wechat）
        - X-DEVICE-SIGN=wechat、Limit=default、Referer 带 code
        """
        if not code:
            return {'success': False, 'error': 'missing_code'}
        if not self.redeem_member:
            return {'success': False, 'error': 'missing_redeem_member'}
        url = f'{self.BASE_URL}/api/lotteryhy/api/client/cj/send/pak'
        headers: Dict[str, str] = {'Accept': 'application/json, text/plain, */*', 'HTTP-X-H5-VERSION': '1', 'Limit': 'default', 'X-DEVICE-SIGN': 'wechat', 'X-DEVICE-ID': '000', 'X-CLIENT-VERSION': '1314', 'Origin': 'https://m.aihoge.com', 'Content-Type': 'application/json;charset=utf-8', 'Accept-Language': 'zh-CN,zh-Hans;q=0.9', 'Referer': f'https://m.aihoge.com/lottery/awardBonus/drawRedPacket?title=%E9%A2%86%E5%8F%96%E7%BA%A2%E5%8C%85&code={code}', 'User-Agent': self.redeem_user_agent or self.user_agent, 'member': self.redeem_member}
        cookie = self.redeem_cookies or self.cookies
        if cookie:
            headers['Cookie'] = cookie
        return request_json(self.session, method='POST', url=url, headers=headers, json_body={'code': code}, timeout=30, account_name=self.account_name)

    def redeem_red_packet_with_retry(self, code: str, *, max_attempts: int=3, min_delay_s: float=1.5, max_delay_s: float=3.5) -> Dict[str, Any]:
        """
        兑换红包并在“无效兑换码”时短暂重试。

        说明：
        - 部分场景下抽奖返回的 code 需要稍等生效，立即兑换会返回 428:无效兑换码。
        - 重试仅针对该类短暂错误，避免对真正失败的请求反复提交。
        """
        attempts = max(1, int(max_attempts))
        last_resp: Dict[str, Any] = {}
        for idx in range(1, attempts + 1):
            resp = self.redeem_red_packet(code)
            last_resp = resp
            meta = interpret_redeem_response(resp)
            if meta['ok']:
                return resp
            code_text = str(meta.get('code') or '')
            message = str(meta.get('message') or '')
            should_retry = code_text == '428' or '无效兑换码' in message
            if not should_retry or idx >= attempts:
                return resp
            delay = random.uniform(min_delay_s, max_delay_s)
            if self.account_name:
                pass
            time.sleep(delay)
        return last_resp

    @staticmethod
    def parse_lottery_result(result: Dict[str, Any]) -> str:
        if result.get('error'):
            return f"抽奖失败: {result.get('error')}"
        award_name = result.get('award_name', '未知奖品')
        award_content = result.get('award_content', '') or award_name
        award_type = result.get('type', 0)
        if award_type == 5:
            points = result.get('prize_integral', 0)
            return f'{award_content} (+{points}积分)'
        if award_type == 3:
            money = result.get('money', 0)
            return f'{award_content} (+{money}元)'
        return award_content

class AihogeMemberBuilder:
    BASE_URL = 'https://m.aihoge.com'

    def __init__(self, session: Optional[requests.Session]=None):
        self.session = session or requests.Session()
        self.session.trust_env = False

    @staticmethod
    def _signature_placeholder(account_id: str, session_id: str, timestamp_ms: str, sign: str, salt: str='') -> str:
        preimage = f'{account_id}&&{session_id}&&{timestamp_ms}&&{sign}'
        if salt:
            preimage = f'{preimage}&&{salt}'
        return hashlib.sha256(preimage.encode('utf-8')).hexdigest()

    def build_member(self, *, ctx: DachaoLoginContext, sign_tid: str, sign_page_url: str, user_agent: str, cookies: str='', signature_salt: str='', account_name: str='', timeout: int=30) -> Tuple[str, Dict[str, Any]]:
        url = f'{self.BASE_URL}/api/memberhy/tm/signature'
        timestamp_ms = str(int(time.time() * 1000))
        signature = self._signature_placeholder(account_id=ctx.account_id, session_id=ctx.session_id, timestamp_ms=timestamp_ms, sign='xsb_hn', salt=signature_salt)
        payload = {'mobile': '1', 'accountId': ctx.account_id, 'user': {'id': ctx.account_id, 'realname': '', 'image_url': ctx.avatar_url, 'nick_name': ctx.nick_name, 'idcard': '', 'is_face_verify': False}, 'signature': signature, 'sessionId': ctx.session_id, 'timestamp': timestamp_ms, 'login': '1', 'sign': 'xsb_hn'}
        headers = {'User-Agent': user_agent, 'Accept': 'application/json, text/plain, */*', 'HTTP-X-H5-VERSION': '1', 'Limit': sign_tid, 'Referer': sign_page_url, 'X-DEVICE-SIGN': 'xsb_hn', 'Origin': 'https://m.aihoge.com', 'X-DEVICE-ID': '000', 'X-CLIENT-VERSION': '1314', 'Accept-Language': 'zh-CN,zh-Hans;q=0.9', 'Content-Type': 'application/json;charset=utf-8'}
        if cookies:
            headers['Cookie'] = cookies
        member_info = request_json(self.session, method='POST', url=url, headers=headers, json_body=payload, timeout=timeout, account_name=account_name)
        member_header = {'id': member_info.get('id', ''), 'black': int(member_info.get('black', 0) or 0), 'btoken': member_info.get('btoken', ''), 'expire': int(member_info.get('expire', 0) or 0), 'token': member_info.get('token', ''), 'source': member_info.get('source', 'xsb_hn'), 'mobile': member_info.get('mobile', ctx.mobile), 'mark': member_info.get('mark', ctx.mobile), 'mtoken': member_info.get('mtoken', ''), 'stoken': member_info.get('stoken', ''), 'nick_name': quote(str(member_info.get('nick_name') or ctx.nick_name), safe=''), 'avatar': member_info.get('avatar', ctx.avatar_url)}
        return (_safe_json_dumps(member_header), member_info)

def discover_sign_page_and_tid(mypage_resp: Dict[str, Any]) -> Tuple[str, str]:
    """
    从 /api/myPage/list 返回中提取签到页面 URL 与 tid。

    对应你抓包的「2.1 获取签到任务信息」：
    GET https://vapp.tmuyun.com/api/myPage/list
    从 data.new_list.records[] 中找到“签到”的 url，并解析 query 里的 tid。
    """
    data = mypage_resp.get('data') or {} if isinstance(mypage_resp, dict) else {}
    new_list = data.get('new_list') or {} if isinstance(data, dict) else {}
    records = new_list.get('records') or [] if isinstance(new_list, dict) else []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get('list_type') == 9 or rec.get('list_title') == '签到' or rec.get('doc_title') == '签到':
            url = str(rec.get('url') or rec.get('web_view_url') or '')
            tid = _parse_tid_from_url(url)
            if url and tid:
                return (url, tid)
    return ('', '')

def discover_news_read_tid(buoy_resp: Dict[str, Any]) -> Tuple[str, str]:
    """
    从 /api/buoy/list 返回中提取阅读有礼 entryLink 与 tid。

    对应你抓包的「3.1 获取阅读有礼活动信息」：
    GET https://vapp.tmuyun.com/api/buoy/list
    从 data.new_down.icon_list[0].turn_to.entryLink 解析 tid。
    """
    data = buoy_resp.get('data') or {} if isinstance(buoy_resp, dict) else {}
    new_down = data.get('new_down') or {} if isinstance(data, dict) else {}
    icon_list = new_down.get('icon_list') or [] if isinstance(new_down, dict) else []
    for icon in icon_list:
        if not isinstance(icon, dict):
            continue
        turn_to = icon.get('turn_to') or {}
        if not isinstance(turn_to, dict):
            continue
        entry = str(turn_to.get('entryLink') or turn_to.get('url') or '')
        tid = _parse_tid_from_url(entry)
        if entry and tid:
            return (entry, tid)
    return ('', '')


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in ('0', 'false', 'no', 'off', '')


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def request_json(session, *, method, url, headers, params=None, data=None,
                 json_body=None, timeout=30, account_name=''):
    if enabled('DACHAO_DRY_RUN'):
        raise RuntimeError('预演禁止网络访问')
    if urlparse(url).scheme != 'https':
        raise RuntimeError('只允许 HTTPS 请求')
    # 禁止重定向携带凭据跨域，限制响应大小，不输出响应和请求内容。
    with session.request(method=method, url=url, headers=headers, params=params,
                         data=data, json=json_body, timeout=(10, min(float(timeout), 30)),
                         allow_redirects=False, stream=True) as resp:
        if not 200 <= resp.status_code < 300:
            raise RuntimeError('HTTP 请求失败')
        body = bytearray()
        for block in resp.iter_content(8192):
            body.extend(block)
            if len(body) > 2 * 1024 * 1024:
                raise RuntimeError('接口响应过大')
        value = json.loads(body)
        if not isinstance(value, dict):
            raise RuntimeError('接口响应结构异常')
        return value


def download_captcha_image(url):
    if enabled('DACHAO_DRY_RUN'):
        raise RuntimeError('预演禁止网络访问')
    if urlparse(url).scheme != 'https':
        raise RuntimeError('验证码图片必须使用 HTTPS')
    # 无账号头和 Cookie 的独立会话。
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, timeout=(10, 20), allow_redirects=False, stream=True) as resp:
            if resp.status_code != 200:
                raise RuntimeError('验证码图片下载失败')
            buf = bytearray()
            for chunk in resp.iter_content(8192):
                buf.extend(chunk)
                if len(buf) > 2 * 1024 * 1024:
                    raise RuntimeError('验证码图片过大')
            image = Image.open(BytesIO(buf))
            if image.width * image.height > 4000000:
                raise RuntimeError('验证码图片尺寸过大')
            return np.array(image.convert('RGB'))


def load_runtime():
    global requests, np, Image
    import requests as req
    import numpy as numpy_module
    from PIL import Image as image_module
    if serialization is None or padding is None:
        raise RuntimeError('缺少 cryptography 依赖')
    requests, np, Image = req, numpy_module, image_module


def check_success(value, kind):
    if not isinstance(value, dict):
        raise RuntimeError('业务响应结构异常')
    if value.get('error') or value.get('error_code') not in (None, 0, '0'):
        raise RuntimeError('业务接口失败')
    if kind == 'vapp' and value.get('code') != 0:
        raise RuntimeError('业务码未确认成功')
    if kind == 'read' and value.get('success') != 1:
        raise RuntimeError('阅读未确认成功')
    if kind == 'sign':
        response = value.get('response')
        if value.get('error_code') != 0 or not isinstance(response, dict):
            raise RuntimeError('签到未确认成功')
        if response.get('success') not in (0, 1) or 'continuous_sign_num' not in response:
            raise RuntimeError('签到状态缺少确认字段')
    if kind == 'lottery':
        if value.get('type') not in (1, 2, 3, 4, 5) or not value.get('award_name'):
            raise RuntimeError('抽奖结果缺少确认字段')


class Stage:
    def __init__(self, result, title):
        self.result, self.title = result, title
    def __enter__(self):
        self.started = time.monotonic()
        self.result['total'] += 1
        log(f"账号{self.result['index']} 阶段{self.result['total']}：{self.title}")
        return self
    def __exit__(self, typ, value, traceback):
        duration = time.monotonic() - self.started
        if typ:
            self.result['failed'] += 1
            log(f'❌ {self.title}失败（{typ.__name__}；详细请求与响应已抑制），耗时{duration:.2f}秒')
        else:
            self.result['success'] += 1
            log(f'✅ {self.title}完成，耗时{duration:.2f}秒')
        return False


def lottery(client, lottery_id, tid, referer, result):
    with Stage(result, '查询抽奖次数'):
        info = client.get_lottery_info(lottery_id, tid, referer)
        check_success(info, 'generic')
        response = info.get('response')
        if not isinstance(response, dict) or 'remain_counts' not in response:
            raise RuntimeError('抽奖次数响应缺少字段')
        remain = int(response['remain_counts'])
        if not 0 <= remain <= 100:
            raise RuntimeError('抽奖次数超出安全范围')
        log(f'可用抽奖次数：{remain}')
    for _ in range(remain):
        try:
            with Stage(result, '使用活动次数抽奖'):
                value = client.draw_lottery(lottery_id, tid, referer)
                check_success(value, 'lottery')
                log(f"抽奖成功：奖励类型{value['type']}（不输出兑换码或原始奖品文本）")
            if value['type'] == 3:
                if enabled('DACHAO_REDEEM'):
                    with Stage(result, '兑换现金红包'):
                        if not client.redeem_member or not value.get('code'):
                            raise RuntimeError('缺少兑换凭据或兑换码')
                        meta = interpret_redeem_response(client.redeem_red_packet_with_retry(str(value['code'])))
                        if not meta['ok']:
                            raise RuntimeError('兑换未确认成功')
                        log('红包已领取' if meta['already_received'] else '红包兑换成功')
                else:
                    result['skipped'] += 1
                    log('⏭️ 红包兑换未开启')
        except Exception:
            pass  # Stage 已记失败，继续其他抽奖，不重复提交不确定请求。
        time.sleep(random.uniform(1, 3))


def run_account(cfg, args, result):
    started = time.monotonic()
    try:
        if enabled('DACHAO_DRY_RUN'):
            with Stage(result, '断网预演配置校验'):
                log(f'模式：{args.mode}；抽奖：{enabled("DACHAO_LOTTERY")}；兑换：{enabled("DACHAO_REDEEM")}；阅读上限：{args.max_articles}')
                log('DRY_RUN_OK：配置有效，未登录、未请求接口、未产生账号副作用')
            return
        with Stage(result, '登录与活动发现'):
            passport, vapp = TmuyunPassportClient(), TmuyunVappClient()
            code = passport.credential_auth(cfg.phone_number, cfg.password_encrypted, cfg.client_id,
                cfg.user_agent, cfg.passport_cookies, cfg.passport_signature_salt)
            ctx = vapp.login_with_code(code, cfg.tenant_id, cfg.user_agent, cfg.vapp_cookies, cfg.session_id)
            if ctx.nick_name:
                log(f'官方昵称：{ctx.nick_name}')
            mypage = vapp.mypage_list(ctx, cfg.user_agent, cfg.vapp_cookies)
            check_success(mypage, 'vapp')
            sign_url, sign_tid = discover_sign_page_and_tid(mypage)
            if not sign_tid:
                raise RuntimeError('没有发现签到入口')
            buoy = vapp.buoy_list(ctx, cfg.user_agent, cfg.vapp_cookies)
            check_success(buoy, 'vapp')
            news_url, news_tid = discover_news_read_tid(buoy)
            member, raw = AihogeMemberBuilder().build_member(ctx=ctx, sign_tid=sign_tid,
                sign_page_url=sign_url, user_agent=cfg.user_agent, cookies=cfg.aihoge_cookies,
                signature_salt=cfg.aihoge_signature_salt)
            check_success(raw, 'generic')
            if not raw.get('id') or not raw.get('token'):
                raise RuntimeError('登录成员凭据未确认有效')
            client = AihogeClient(member_header=member, account_id=ctx.account_id,
                session_id=ctx.session_id, cookies=cfg.aihoge_cookies, user_agent=cfg.user_agent,
                redeem_member=cfg.redeem_member, redeem_cookies=cfg.redeem_cookies,
                redeem_user_agent=cfg.redeem_user_agent)
        if args.mode in ('all', 'sign'):
            try:
                with Stage(result, '签到'):
                    value = client.sign_in(sign_tid, sign_url)
                    check_success(value, 'sign')
                    if value['response']['success'] == 0:
                        result['alreadyComplete'] += 1
                        result['success'] -= 1
                        log('☑️ 今日已签到')
                    else:
                        log('签到成功')
            except Exception:
                pass
            if cfg.sign_lottery_id and enabled('DACHAO_LOTTERY'):
                try:
                    lottery(client, cfg.sign_lottery_id, sign_tid, sign_url, result)
                except Exception:
                    pass
            else:
                result['skipped'] += 1
                log('⏭️ 签到抽奖未开启或未配置活动编号')
        if args.mode in ('all', 'read'):
            if not news_tid:
                result['skipped'] += 1
                log('⏭️ 阅读活动未开放')
                return
            with Stage(result, '获取阅读任务'):
                news = client.get_news_list(news_tid, news_url)
                check_success(news, 'generic')
                if not isinstance(news.get('data'), list) or not news['data']:
                    raise RuntimeError('阅读列表结构异常')
                first = news['data'][0]
                columns = first.get('limit', {}).get('column_set', {}).get('column_list') if isinstance(first, dict) else None
                if not isinstance(columns, list) or not columns or not isinstance(columns[0], dict) or not isinstance(columns[0].get('data'), list):
                    raise RuntimeError('阅读文章列表缺少确认字段')
                articles = client.extract_articles(news)
                unread = [a for a in articles if a.get('is_read') != 1]
                log(f'阅读文章：{len(articles)}；待完成：{len(unread)}')
            for article in unread[:args.max_articles]:
                try:
                    with Stage(result, '阅读并上报实际时长'):
                        if not article.get('item_id'):
                            raise RuntimeError('文章缺少编号')
                        value = client.complete_read_task(news_tid, str(article['item_id']), news_url)
                        check_success(value, 'read')
                        delay = random.uniform(args.read_delay_min, args.read_delay_max)
                        clock = time.monotonic()
                        time.sleep(delay)
                        channel = client.extract_channel_article_id(str(article.get('link') or article.get('link_url') or ''))
                        if not channel:
                            raise RuntimeError('文章缺少时长上报编号')
                        reported = vapp.report_read_time(ctx, channel, int((time.monotonic()-clock)*1000), cfg.user_agent, cfg.vapp_cookies)
                        check_success(reported, 'vapp')
                        log('阅读任务完成成功；实际时长上报成功')
                except Exception:
                    pass
                time.sleep(random.uniform(2, 5))
            award = client.extract_award_activity_id(news)
            if award and enabled('DACHAO_LOTTERY'):
                try:
                    lottery(client, award, news_tid, news_url, result)
                except Exception:
                    pass
            else:
                result['skipped'] += 1
                log('⏭️ 阅读抽奖未开启或未提供活动编号')
    except Exception:
        if result['failed'] == 0:
            result['failed'] += 1
            result['total'] += 1
            log('❌ 账号流程未完成；继续其他账号')
    finally:
        result['durationSeconds'] = round(time.monotonic()-started, 2)
        result['total'] += result['skipped']
        log(f"账号{result['index']}统计：总任务{result['total']}，成功{result['success']}，已完成{result['alreadyComplete']}，跳过{result['skipped']}，失败{result['failed']}，耗时{result['durationSeconds']}秒")


def notify_summary(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        log('通知已通过 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    if dry:
        # 通知脚本可能访问网络，因此断网预演只验证通知摘要，不调用它。
        log('断网预演通知：' + body)
        return 'dry-run-preview'
    try:
        import subprocess
        worker = """
import importlib.util, os, sys, json
from pathlib import Path
try:
    from notify import send
except ImportError:
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR'])/'notify.py')
    paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    file = next((p for p in paths if p.is_file()), None)
    if file is None:
        raise ImportError('通知模块不可用')
    spec = importlib.util.spec_from_file_location('qinglong_notify', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send = module.send
send('大潮App签到阅读', sys.stdin.read())
"""
        # 不向通知子进程传递大潮账号凭据。
        env = {k: v for k, v in os.environ.items() if not k.startswith('DACHAO_')}
        completed = subprocess.run([sys.executable, '-c', worker], input=body,
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20, env=env)
        if completed.returncode != 0:
            raise RuntimeError('通知不可用')
        log('通知发送成功')
        return 'sent'
    except Exception:
        log('⚠️ 通知不可用或发送失败，保留业务退出码')
        return 'unavailable'


def main():
    start = time.monotonic()
    log('========== 大潮App签到阅读 ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}')
    dry = enabled('DACHAO_DRY_RUN')
    log('运行模式：' + ('断网预演' if dry else '实际执行'))
    results, configuration_error = [], False
    raw_accounts = []
    try:
        parser = argparse.ArgumentParser(description='大潮签到阅读；凭据使用 DACHAO_ACCOUNTS 每行一个 JSON 对象')
        parser.add_argument('--config', help='兼容用户指定的旧版配置文件，读取 dachao.accounts；不使用私有默认路径')
        parser.add_argument('--mode', choices=('all', 'sign', 'read'), default=os.getenv('DACHAO_MODE', 'all'))
        parser.add_argument('--max-articles', type=int, default=int(os.getenv('DACHAO_MAX_ARTICLES', '6')))
        parser.add_argument('--read-delay-min', type=float, default=20)
        parser.add_argument('--read-delay-max', type=float, default=30)
        args = parser.parse_args()
        if args.mode not in ('all', 'sign', 'read') or not 1 <= args.max_articles <= 100 or not 1 <= args.read_delay_min <= args.read_delay_max <= 300:
            raise ValueError('运行参数范围错误')
        if os.getenv('DACHAO_ACCOUNTS', '').strip():
            raw_accounts = [s for s in os.environ['DACHAO_ACCOUNTS'].splitlines() if s.strip()]
        elif args.config:
            raw_accounts = json.loads(Path(args.config).read_text())['dachao']['accounts']
        if not isinstance(raw_accounts, list) or not raw_accounts:
            raise ValueError('未配置账号')
        log(f'账号数量：{len(raw_accounts)}')
        if not dry:
            load_runtime()
        for index, raw in enumerate(raw_accounts, 1):
            result = dict(index=index, total=0, success=0, alreadyComplete=0, skipped=0, failed=0, durationSeconds=0)
            results.append(result)
            try:
                with Stage(result, '账号参数校验'):
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    if not isinstance(data, dict):
                        raise ValueError('账号必须为 JSON 对象')
                    # 禁止用用户标签作为身份，官方昵称由登录响应输出。
                    data = dict(data, account_name=f'账号{index}')
                    cfg = NewDachaoAccountConfig.from_dict(data)
                run_account(cfg, args, result)
            except Exception:
                configuration_error = True
                log(f'账号{index}配置失败；继续其他账号')
                log(f"账号{index}统计：总任务{result['total']}，成功{result['success']}，已完成0，跳过0，失败{result['failed']}，耗时0秒")
    except (Exception, SystemExit) as exc:
        configuration_error = True
        log(f'❌ 配置或运行依赖错误（{type(exc).__name__}），未输出输入内容')
    failed = sum(r['failed'] > 0 for r in results) + max(0, len(raw_accounts)-len(results))
    success = sum(r['failed'] == 0 for r in results)
    code = 2 if configuration_error else (1 if failed else 0)
    status = 'configuration-error' if configuration_error else ('partial-failure' if failed and success else 'failure' if failed else 'dry-run' if dry else 'success')
    log('----------------------------------------')
    log(f'任务统计：账号{len(raw_accounts)}，成功{success}，失败{failed}；总耗时{time.monotonic()-start:.2f}秒')
    log('子任务统计：' + '，'.join(f"{key}={sum(r[key] for r in results)}" for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')))
    body = f'账号总数：{len(raw_accounts)}；成功数：{success}；失败数：{failed}；最终状态：{status}'
    notification = notify_summary(body, dry)
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}；通知状态：{notification}')
    summary = dict(status=status, accounts=len(raw_accounts), success=success, failed=failed,
                   configurationError=configuration_error, tasks=results, notification=notification,
                   durationSeconds=round(time.monotonic()-start, 2), exitCode=code)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
