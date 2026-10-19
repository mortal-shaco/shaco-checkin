#!/usr/bin/env python3
# name: 塔吉多（异环）自动签到
# cron: 0 1 * * *
# 来源: Candy-QAQ/NTE-Auto-Sign, nte.py 与 qinglong.py
# 上游提交: 38d77e1f7dc784f2baeb49c41cd4352deadf2b24
# SPDX-License-Identifier: MIT
# 上游提供的文件未含额外版权声明；保留原作者归属。

# MIT License
# Attribution: Candy-QAQ/NTE-Auto-Sign (upstream repository)
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

"""每日社区/游戏签到及可选云异环时长查询。
NTE_TOKEN 每个非空行一个账号，兼容 TOKEN。可使用纯 refreshToken，
或 JSON 对象组合 refreshToken、uid、deviceId、gameId、roleIds、
cloudToken、cloudUserId、cloudDeviceId。无任何默认凭据文件读写。
请在本人官方客户端登录，获取用户中心 refreshToken 响应；云端使用
云异环登录响应 token/userId。不要将这些响应或设备标识公开。
NTE_DRY_RUN=1 只验证配置，不请求接口或通知服务。
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
        _ql_notify_identities = ('6919295133257387', 'scripts/nte.py', 'nte.py', 'nte')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import hashlib
import importlib
import importlib.util
import json
import logging
import os
import re
import secrets
import string
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib import parse, request, error

game_id_env = os.environ.get('TGD_GAME_ID')
sign_game_ids_env = os.environ.get('TGD_SIGN_GAME_IDS')
role_ids_env = os.environ.get('TGD_ROLE_IDS')
DRY = os.environ.get('NTE_DRY_RUN', '0').lower() in {'1','true','yes','on'}
SECRETS = set()

DEFAULT_GAME_ID = '1289'
COMMUNITY_ID = '1'
APP_ID = '10550'
USER_CENTER_APP_ID = '10551'
SECRET = '89155cc4e8634ec5b1b6364013b23e3e'
DEVICETYPE = 'LGE-AN10'
TYPE = '16'
DEVICENAME = 'LGE-AN10'
VERSIONCODE = '1'
AREACODEID = '1'
DEVICESYS = '12'
DEVICEMODEL = 'LGE-AN10'
SDKVERSION = '4.129.0'
BID = 'com.pwrd.htassistant'
CHANNELID = '1'
USER_CENTER_APPVERSION = '1.2.5'
USER_CENTER_DS_SECRET = 'pUds3dfMkl'
OKHTTP_UA = 'okhttp/4.12.0'
WEBVIEW_UA = 'Mozilla/5.0 (Linux; Android 15; TB321FU Build/AQ3A.240912.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/148.0.7778.28 Safari/537.36'
CLOUD_APP_ID = '10597'
CLOUD_SECRET = 'f1b7f11fc3774f898e387368cce4da04'
CLOUD_DEVICE_TYPE = 'TB321FU'
CLOUD_DEVICE_NAME = 'TB321FU'
CLOUD_DEVICE_SYS = '15'
CLOUD_DEVICE_MODEL = 'TB321FU'
CLOUD_VERSION_CODE = '32'
CLOUD_APP_VERSION = '1.1.0'
CLOUD_LOGIN_SDK_VERSION = '4.327.1'
CLOUD_GAME_SDK_VERSION = '1.34.0'
CLOUD_BID = 'com.pwrd.cloud.yh.laohu'
CLOUD_CHANNEL_ID = '1'
CLOUD_NETWORK = 'wifi'
CLOUD_PROVIDER = '0'
CLOUD_LOGIN_UA = 'LaohuSDK/4.327.1 (android os 15;mobile  manufacturer LENOVO; model TB321FU)'
CLOUD_GAME_UA = 'okhttp/${project.version}'
REQUEST_HEADERS_BASE = {'platform': 'android', 'Content-Type': 'application/x-www-form-urlencoded'}
CLOUD_LOGIN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'User-Agent': CLOUD_LOGIN_UA}
CLOUD_GAME_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': CLOUD_GAME_UA}
SEND_CAPTCHA_URL = 'https://user.laohu.com/m/newApi/sendPhoneCaptchaWithOutLogin'
CHECK_CAPTCHA_URL = 'https://user.laohu.com/m/newApi/checkPhoneCaptchaWithOutLogin'
LOGIN_URL = 'https://user.laohu.com/openApi/sms/new/login'
SECURE_PASSWORD_LOGIN_URL = 'https://user.laohu.com/openApi/secureLogin'
CLOUD_QUERY_PASSWORD_URL = 'https://user.laohu.com/m/newApi/query/whetherSetPassword'
USER_CENTER_LOGIN_URL = 'https://bbs-api.tajiduo.com/usercenter/api/login'
REFRESH_TOKEN_URL = 'https://bbs-api.tajiduo.com/usercenter/api/refreshToken'
GET_GAME_ROLES_URL = 'https://bbs-api.tajiduo.com/usercenter/api/v2/getGameRoles'
APP_SIGNIN_URL = 'https://bbs-api.tajiduo.com/apihub/api/signin'
GAME_SIGNIN_URL = 'https://bbs-api.tajiduo.com/apihub/awapi/sign'
GAME_SIGNIN_STATE_URL = 'https://bbs-api.tajiduo.com/apihub/awapi/signin/state'
GAME_SIGN_REWARDS_URL = 'https://bbs-api.tajiduo.com/apihub/awapi/sign/rewards'
CLOUD_USER_INFO_URL = 'https://user.laohu.com/cloud/game/getUserInfo'
CLOUD_UNTREATED_COUNT_URL = 'https://user.laohu.com/cloud/game/query/duration/give/untreatedCount'

def _dedup_list(items):
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result

def generate_signature_with_secret(params, secret):
    sorted_keys = sorted(params.keys())
    values = ''.join((str(params[key]) for key in sorted_keys))
    return hashlib.md5((values + secret).encode('utf-8')).hexdigest()

def generate_signature(params):
    return generate_signature_with_secret(params, SECRET)

def _user_center_ds():
    timestamp = str(int(time.time()))
    alphabet = string.ascii_letters + string.digits
    nonce = ''.join((secrets.choice(alphabet) for _ in range(8)))
    digest = hashlib.md5(f'{timestamp}{nonce}{USER_CENTER_APPVERSION}{USER_CENTER_DS_SECRET}'.encode('utf-8')).hexdigest()
    return f'{timestamp},{nonce},{digest}'

def _cloud_generate_signature(params):
    return generate_signature_with_secret(params, CLOUD_SECRET)

def _random_device_id():
    return uuid.uuid4().hex

def _default_game_id():
    v = (game_id_env or DEFAULT_GAME_ID).strip()
    return v if v else DEFAULT_GAME_ID

def _candidate_sign_game_ids(primary_game_id):
    candidates = []
    env_candidates = _parse_role_ids(sign_game_ids_env)
    if env_candidates:
        candidates.extend(env_candidates)
    candidates.extend([str(primary_game_id or '').strip(), _default_game_id(), '1289', '1257'])
    return _dedup_list(candidates)

def _parse_role_ids(role_text):
    if not role_text:
        return []
    if isinstance(role_text, list):
        return _dedup_list([str(i).strip() for i in role_text if str(i).strip()])
    text = str(role_text).replace('\n', ',')
    return _dedup_list([i.strip() for i in text.split(',') if i.strip()])

def _request_form(url, data, headers):
    return HTTP.post(url, data=parse.urlencode(data), headers=headers)

def parse_account_line(line):
    line = line.strip()
    if not line:
        return None
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return {'refreshToken': line, 'uid': '', 'deviceId': _random_device_id(), 'gameId': _default_game_id(), 'roleIds': []}
    if not isinstance(raw, dict):
        raise ValueError('账号内容必须是JSON对象')
    refresh_token = str(raw.get('refreshToken') or raw.get('token') or '').strip()
    cloud_raw = raw.get('cloud')
    if not isinstance(cloud_raw, dict):
        cloud_raw = {}
    cloud_token = str(raw.get('cloudToken') or raw.get('cloud_token') or cloud_raw.get('token') or '').strip()
    cloud_user_id = str(raw.get('cloudUserId') or raw.get('cloud_user_id') or raw.get('cloudUid') or cloud_raw.get('userId') or cloud_raw.get('uid') or '').strip()
    if not refresh_token and (not (cloud_token and cloud_user_id)):
        raise ValueError('账号缺少 refreshToken 或 cloudToken/cloudUserId')
    uid = str(raw.get('uid') or '').strip()
    device_id = str(raw.get('deviceId') or raw.get('deviceid') or '').strip() or _random_device_id()
    cloud_device_id = str(raw.get('cloudDeviceId') or raw.get('cloud_device_id') or cloud_raw.get('deviceId') or '').strip() or device_id
    game_id = str(raw.get('gameId') or raw.get('game_id') or _default_game_id()).strip() or _default_game_id()
    role_ids = _parse_role_ids(raw.get('roleIds') or raw.get('role_ids') or raw.get('roleId'))
    account = {'refreshToken': refresh_token, 'uid': uid, 'deviceId': device_id, 'gameId': game_id, 'roleIds': role_ids}
    if cloud_token:
        account['cloudToken'] = cloud_token
    if cloud_user_id:
        account['cloudUserId'] = cloud_user_id
    if cloud_token or cloud_user_id:
        account['cloudDeviceId'] = cloud_device_id
    return account

def _is_already_signed(message):
    for key in ['已签到', '签到过', '重复签到']:
        if key in message:
            return True
    return False

def refresh_access_token(account):
    headers = {**REQUEST_HEADERS_BASE, 'Accept': 'application/json, text/plain, */*', 'deviceId': account['deviceId'], 'Authorization': account['refreshToken'], 'appVersion': USER_CENTER_APPVERSION, 'uid': str(account.get('uid') or '0'), 'debug-uid': '3', 'ds': _user_center_ds(), 'User-Agent': OKHTTP_UA}
    response = HTTP.post(REFRESH_TOKEN_URL, headers=headers)
    if response.status_code == 402:
        raise RuntimeError('refreshToken 已失效，请重新登录')
    resp = _safe_json(response, '刷新token')
    if not _is_ok(resp):
        raise RuntimeError(f"刷新token失败：{resp.get('message') or resp.get('msg') or '业务请求失败'}")
    data = resp.get('data') or {}
    access_token = data.get('accessToken')
    refresh_token = data.get('refreshToken')
    if not access_token or not refresh_token:
        raise RuntimeError(f"刷新token返回缺少accessToken/refreshToken：{'响应字段异常'}")
    account['refreshToken'] = refresh_token
    if data.get('uid'):
        account['uid'] = str(data['uid'])
    return access_token

def get_game_role_ids(access_token, uid, device_id, game_id):
    headers = {'Accept': 'application/json', 'platform': 'android', 'authorization': access_token, 'uid': uid, 'deviceid': device_id, 'appversion': USER_CENTER_APPVERSION, 'ds': _user_center_ds(), 'User-Agent': OKHTTP_UA}
    response = HTTP.get(GET_GAME_ROLES_URL, headers=headers, params={'gameId': game_id})
    resp = _safe_json(response, '获取角色列表')
    if not _is_ok(resp):
        raise RuntimeError(f"获取角色列表失败：{resp.get('msg') or '业务请求失败'}")
    data = resp.get('data') or {}
    roles = data.get('roles', []) if isinstance(data, dict) else []
    role_ids = []
    for role in roles:
        role_id = str(role.get('roleId', '')).strip()
        if role_id:
            role_ids.append(role_id)
    return _dedup_list(role_ids)

def app_signin(access_token, uid, device_id):
    headers = {**REQUEST_HEADERS_BASE, 'Accept': 'application/json', 'authorization': access_token, 'uid': uid, 'deviceid': device_id, 'appversion': USER_CENTER_APPVERSION, 'ds': _user_center_ds(), 'User-Agent': OKHTTP_UA}
    response = _request_form(APP_SIGNIN_URL, {'communityId': COMMUNITY_ID}, headers)
    resp = _safe_json(response, '社区签到')
    if _is_ok(resp):
        data = resp.get('data') or {}
        exp = data.get('exp', 0)
        coin = data.get('goldCoin', 0)
        return (True, f'社区签到成功，获得{exp}经验，{coin}金币')
    msg = str(resp.get('msg') or resp.get('message') or '业务请求失败')
    if _is_already_signed(msg):
        return (True, '社区今日已签到')
    return (False, msg)

def get_game_sign_state(access_token, game_id):
    response = HTTP.get(GAME_SIGNIN_STATE_URL, headers={'Authorization': access_token}, params={'gameId': game_id})
    resp = _safe_json(response, f'查询游戏签到状态(gameId={game_id})')
    if not _is_ok(resp):
        raise RuntimeError(f"查询游戏签到状态失败(gameId={game_id})：{resp.get('msg') or '业务请求失败'}")
    data = resp.get('data') or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"查询游戏签到状态返回结构异常(gameId={game_id})：{'响应字段异常'}")
    return data

def get_game_sign_rewards(access_token, role_id, game_id):
    params = {'gameId': game_id}
    if role_id:
        params['roleId'] = role_id
    response = HTTP.get(GAME_SIGN_REWARDS_URL, headers={'Authorization': access_token}, params=params)
    resp = _safe_json(response, f'查询游戏签到奖励(gameId={game_id})')
    if not _is_ok(resp):
        raise RuntimeError(f"查询游戏签到奖励失败(gameId={game_id})：{resp.get('msg') or '业务请求失败'}")
    data = resp.get('data')
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ['items', 'rewards', 'list']:
            items = data.get(key)
            if isinstance(items, list):
                return items
    raise RuntimeError(f"查询游戏签到奖励返回结构异常(gameId={game_id})：{'响应字段异常'}")

def _format_reward_item_text(item):
    if not isinstance(item, dict):
        return ''
    name = str(item.get('name') or item.get('itemName') or item.get('title') or '').strip()
    if not name:
        return ''
    num = item.get('num')
    if num is None:
        num = item.get('count')
    if num is None:
        num = item.get('quantity')
    if num is None or str(num).strip() == '':
        return name
    return f'{name}x{num}'

def _today_reward_text(access_token, role_id, game_id, state_data=None):
    state = state_data if isinstance(state_data, dict) else get_game_sign_state(access_token, game_id)
    try:
        days = int(state.get('days') or 0)
    except (TypeError, ValueError):
        return ''
    if days <= 0:
        return ''
    rewards = get_game_sign_rewards(access_token, role_id, game_id)
    if len(rewards) < days:
        return ''
    return _format_reward_item_text(rewards[days - 1])

def game_signin(access_token, role_id, game_id):

    def _state_of(gid):
        try:
            return get_game_sign_state(access_token, gid)
        except Exception as ex:
            logging.warning(f'查询游戏签到状态失败(gameId={gid})：{ex}')
            return None

    def _reward_suffix(gid, state_data=None):
        try:
            reward_text = _today_reward_text(access_token, role_id, gid, state_data=state_data)
            return f'，今日道具：{reward_text}' if reward_text else ''
        except Exception as ex:
            logging.warning(f'读取游戏签到道具失败(gameId={gid}, roleId={role_id})：{ex}')
            return ''
    headers = {**REQUEST_HEADERS_BASE, 'authorization': access_token, 'appversion': USER_CENTER_APPVERSION, 'User-Agent': OKHTTP_UA}
    errors = []
    for sign_game_id in _candidate_sign_game_ids(game_id):
        response = _request_form(GAME_SIGNIN_URL, {'roleId': role_id, 'gameId': sign_game_id}, headers)
        resp = _safe_json(response, f'游戏签到(gameId={sign_game_id})')
        if _is_ok(resp):
            return (True, f'签到成功（gameId={sign_game_id}）{_reward_suffix(sign_game_id)}')
        msg = str(resp.get('msg') or resp.get('message') or '业务请求失败')
        if _is_already_signed(msg):
            state_data = _state_of(sign_game_id)
            if state_data and (state_data.get('todaySign') is True or type(state_data.get('todaySign')) is int and state_data['todaySign'] == 1):
                return (True, f'今日已签到（gameId={sign_game_id}）{_reward_suffix(sign_game_id, state_data=state_data)}')
            errors.append(f'gameId={sign_game_id} 返回“{msg}”但状态未签到')
            continue
        errors.append(f'gameId={sign_game_id}: {msg}')
    return (False, '；'.join(errors) if errors else '游戏签到失败')

def _cloud_game_params(account):
    cloud_token = str(account.get('cloudToken') or '').strip()
    cloud_user_id = str(account.get('cloudUserId') or '').strip()
    if not cloud_token or not cloud_user_id:
        raise RuntimeError('云异环账号缺少 cloudToken/cloudUserId')
    device_id = str(account.get('cloudDeviceId') or account.get('deviceId') or _random_device_id()).strip()
    if not device_id:
        device_id = _random_device_id()
    account['cloudDeviceId'] = device_id
    data = {'userId': cloud_user_id, 'token': cloud_token, 't': str(int(time.time())), 'appId': CLOUD_APP_ID, 'deviceId': device_id, 'deviceType': CLOUD_DEVICE_TYPE, 'deviceName': CLOUD_DEVICE_NAME, 'channelId': CLOUD_CHANNEL_ID, 'deviceModel': CLOUD_DEVICE_MODEL, 'deviceSys': CLOUD_DEVICE_SYS, 'version': CLOUD_APP_VERSION, 'sdkVersion': CLOUD_GAME_SDK_VERSION, 'network': CLOUD_NETWORK, 'bid': CLOUD_BID, 'provider': CLOUD_PROVIDER, 'idfa': ''}
    data['sign'] = _cloud_generate_signature(data)
    return data

def cloud_get_user_info(account):
    resp = _safe_json(_request_form(CLOUD_USER_INFO_URL, _cloud_game_params(account), CLOUD_GAME_HEADERS), '云异环查询时长')
    if not _is_ok(resp):
        raise RuntimeError(f"云异环查询时长失败：{resp.get('message') or resp.get('msg') or '业务请求失败'}")
    result = resp.get('result') or {}
    if not isinstance(result, dict):
        raise RuntimeError(f"云异环查询时长返回结构异常：{'响应字段异常'}")
    return result

def cloud_untreated_count(account):
    response = HTTP.get(CLOUD_UNTREATED_COUNT_URL, headers=CLOUD_GAME_HEADERS, params=_cloud_game_params(account))
    resp = _safe_json(response, '云异环查询待领取时长')
    if not _is_ok(resp):
        raise RuntimeError(f"云异环查询待领取时长失败：{resp.get('message') or resp.get('msg') or '业务请求失败'}")
    result = resp.get('result') or {}
    if not isinstance(result, dict) or 'count' not in result:
        raise RuntimeError('云端待领取数量字段缺失')
    try:
        count = int(result['count'])
    except (TypeError, ValueError):
        raise RuntimeError('云端待领取数量字段类型异常') from None
    if count < 0:
        raise RuntimeError('云端待领取数量非法')
    return count


def redact(value):
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已脱敏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已脱敏]', text)
    return ''.join(c for c in text if c.isprintable())


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {redact(text)}', flush=True)


class SafeLog(logging.Handler):
    def emit(self, record):
        log(record.getMessage())


class Response:
    def __init__(self, status, raw):
        self.status_code = status
        self.raw = raw

    def json(self):
        return json.loads(self.raw)


class NoRedirect(request.HTTPRedirectHandler):
    # 凭据请求不自动跟随跳转，防止把鉴权转发到其他主机。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTP:
    @staticmethod
    def call(method, url, headers=None, params=None, data=None):
        if DRY:
            raise RuntimeError('预演禁止网络请求')
        if parse.urlsplit(url).scheme != 'https':
            raise RuntimeError('只允许 HTTPS')
        if params:
            url += '?' + parse.urlencode(params)
        payload = data.encode('utf-8') if isinstance(data, str) else data
        req = request.Request(url, data=payload, headers=headers or {}, method=method)
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=20) as res:
                raw = res.read(1048577)
                if len(raw) > 1048576:
                    raise RuntimeError('响应超过大小限制')
                log(f'接口 {method} {parse.urlsplit(url).path}：HTTP {res.status}')
                return Response(res.status, raw)
        except error.HTTPError as ex:
            status = ex.code
            ex.close()
            log(f'接口 {method} {parse.urlsplit(url).path}：HTTP {status}')
            return Response(status, b'')
        except (error.URLError, TimeoutError, OSError):
            raise RuntimeError('网络请求失败或超时（详情已脱敏）') from None

    @staticmethod
    def get(url, headers=None, params=None):
        return HTTP.call('GET', url, headers, params)

    @staticmethod
    def post(url, headers=None, data=None):
        return HTTP.call('POST', url, headers, data=data)


def _is_ok(resp):
    return isinstance(resp, dict) and type(resp.get('code')) is int and resp['code'] == 0


def remember(value, key=''):
    if isinstance(value, dict):
        for k, v in value.items():
            remember(v, str(k).lower())
    elif isinstance(value, list):
        for item in value:
            remember(item, key)
    elif value is not None and any(x in key for x in ('token','password','device','phone','captcha','authorization','session','cookie','sign')):
        SECRETS.add(str(value))


def _safe_json(response, endpoint):
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f'{endpoint}：HTTP {response.status_code}')
    try:
        resp = response.json()
    except (ValueError, UnicodeError):
        raise RuntimeError(f'{endpoint}：响应不是有效 JSON') from None
    if not isinstance(resp, dict) or type(resp.get('code')) is not int:
        raise RuntimeError(f'{endpoint}：缺少有效业务状态码')
    remember(resp)
    # 原始业务消息只用于识别已签到，日志不回显服务端自由文本。
    already = any(_is_already_signed(str(resp.get(k) or '')) for k in ('msg','message'))
    for key in ('msg', 'message'):
        if key in resp:
            resp[key] = '已签到' if already else f'业务状态码 {resp["code"]}'
    if _is_ok(resp):
        for section in ('data', 'result'):
            data = resp.get(section)
            if isinstance(data, dict):
                for key in ('nickname', 'nickName', 'username', 'displayName', 'uid', 'userId'):
                    if data.get(key) is not None:
                        log(f'官方账号身份 {key}：{data[key]}')
                roles = data.get('roles')
                if isinstance(roles, list):
                    for role in roles:
                        if isinstance(role, dict) and role.get('roleName'):
                            log(f'官方角色名称：{role["roleName"]}')
    return resp


# 社区重复签到同样要求官方状态查询确认，不能仅凭业务文案退出成功。
_original_app_signin = app_signin

def app_signin(access_token, uid, device_id):
    ok, msg = _original_app_signin(access_token, uid, device_id)
    if ok and msg == '社区今日已签到':
        # 上游没有提供社区独立状态查询接口，明确失败闭合。
        return False, '社区返回重复签到，但缺少可核验状态；未验证成功'
    return ok, msg


# 未找到可验证的“领取”接口；保留 getUserInfo 与 untreatedCount 查询能力。
def cloud_query(account):
    info = cloud_get_user_info(account)
    if not any(k in info for k in ('remainedDuration', 'remainedFreeDuration', 'remainedRechargeDuration')):
        raise RuntimeError('云端缺少时长字段')
    def number(key):
        value = info.get(key)
        if value is None:
            return '未返回'
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise RuntimeError('云端时长字段类型异常') from None
        return str(result)
    log('云异环：剩余' + number('remainedDuration') + '分钟，免费' + number('remainedFreeDuration') + '分钟，充值' + number('remainedRechargeDuration') + '分钟')
    for key, title in (('perDayFirstLoginGiveDuration', '每日首登分钟数'), ('firstGameGiveDuration', '首次游戏赠送分钟数'), ('remainedVipDuration', 'VIP剩余天数')):
        if key in info:
            log(f'{title}：{number(key)}')
    count = cloud_untreated_count(account)
    log(f'待领取消息：{count}个；本任务未调用领取接口')
    return True, '云异环时长查询成功'


def notify_summary(body):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower() in {'0','false','no','off'}:
        return '已关闭'
    if DRY:
        log('通知预演：' + body)
        return '预演已生成（断网不投递）'
    import subprocess
    # 使用子进程隔离通知模块输出，防止异常打印配置；限制投递耗时。
    helper = r'''
import importlib, importlib.util, os, sys
from pathlib import Path
try:
    try:
        mod = importlib.import_module('notify')
    except ImportError:
        candidates = []
        if os.environ.get('QINGLONG_NOTIFY_DIR'):
            candidates.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        candidates += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
        mod = None
        for path in candidates:
            if path.is_file():
                spec = importlib.util.spec_from_file_location('ql_notification', str(path))
                mod = importlib.util.module_from_spec(spec)
                sys.path.insert(0, str(path.parent))
                spec.loader.exec_module(mod)
                break
        if mod is None:
            sys.exit(2)
    mod.send('塔吉多（异环）自动签到', sys.stdin.read())
except Exception:
    sys.exit(2)
'''
    try:
        result = subprocess.run([sys.executable, '-c', helper], input=body, text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return '已调用通知模块' if result.returncode == 0 else '通知不可用或投递失败'
    except (OSError, subprocess.TimeoutExpired):
        return '通知不可用或投递超时'


def main():
    started = time.monotonic()
    log('========== 塔吉多（异环）自动签到 ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if DRY else "正式执行"}')
    root = logging.getLogger()
    root.handlers = [SafeLog()]
    root.setLevel(logging.INFO)
    rows = [line.strip() for line in (os.environ.get('NTE_TOKEN') or os.environ.get('TOKEN') or '').splitlines() if line.strip()]
    log(f'账号总数：{len(rows)}')
    results = []
    config_error = not rows
    if config_error:
        log('❌ 配置错误：请添加 NTE_TOKEN，每个非空行一个账号')
    for i, row in enumerate(rows, 1):
        account_start = time.monotonic()
        stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
        sequence = 0
        def stage(title, fn):
            nonlocal sequence
            sequence += 1
            stats['total'] += 1
            begin = time.monotonic()
            log(f'账号 {i} / 阶段 {sequence}：{title}')
            try:
                value = fn()
                if isinstance(value, tuple):
                    ok, message = value
                    if not ok:
                        log('❌ 业务结果：' + message)
                        raise RuntimeError('业务未验证成功')
                    status = 'alreadyComplete' if '今日已签到' in message else 'success'
                    log(f'{"☑️" if status == "alreadyComplete" else "✅"} {message}')
                else:
                    status = 'success'
                    log('✅ ' + title + '完成')
                stats[status] += 1
                return value
            except Exception as ex:
                stats['failure'] += 1
                # 不输出异常正文：第三方/格式异常可能夹带凭据。
                detail = str(ex) if isinstance(ex, RuntimeError) else '配置或响应字段类型不合法'
                log(f'❌ {title}失败（{type(ex).__name__}）：{detail}；请核对凭据、参数和接口业务状态')
                return None
            finally:
                log(f'账号 {i} / 阶段 {sequence} 耗时 {time.monotonic()-begin:.2f} 秒')
        def parse_config():
            if row.startswith(('{', '[')):
                raw = json.loads(row)
                if not isinstance(raw, dict):
                    raise ValueError('账号必须为 JSON 对象')
                remember(raw)
                for key in ('refreshToken', 'token', 'cloudToken', 'cloud_token', 'cloudUserId', 'cloud_user_id', 'uid', 'deviceId', 'cloudDeviceId'):
                    if key in raw and not isinstance(raw[key], (str, int)):
                        raise ValueError('账号字段类型不合法')
            else:
                SECRETS.add(row)
            account = parse_account_line(row)
            remember(account)
            if bool(account.get('cloudToken')) != bool(account.get('cloudUserId')):
                raise ValueError('云端凭据必须成对提供')
            return account
        account = stage('读取并校验账号配置', parse_config)
        if account is None:
            config_error = True
        elif DRY:
            stage('断网预演', lambda: (True, 'DRY_RUN_OK：凭据格式通过；不登录、不签到、不查询、不保存凭据'))
            log(f'计划：社区/游戏签到={bool(account.get("refreshToken"))}，云时长查询={bool(account.get("cloudToken"))}；gameId={account["gameId"]}；显式角色数={len(account["roleIds"])}')
        else:
            if account.get('refreshToken'):
                access = stage('刷新用户中心令牌', lambda: refresh_access_token(account))
                if access:
                    uid = account.get('uid')
                    if uid:
                        stage('社区签到', lambda: app_signin(access, uid, account['deviceId']))
                    else:
                        stage('社区签到参数检查', lambda: (False, '缺少 uid'))
                    roles = _dedup_list(account['roleIds'] + _parse_role_ids(role_ids_env))
                    if not roles and uid:
                        roles = stage('发现游戏角色', lambda: get_game_role_ids(access, uid, account['deviceId'], account['gameId'])) or []
                    if not roles:
                        stage('游戏角色参数检查', lambda: (False, '未找到角色'))
                    for role in roles:
                        stage('游戏角色签到及奖励查询', lambda role=role: game_signin(access, role, account['gameId']))
                else:
                    stats['skipped'] += 2
                    stats['total'] += 2
                    log('⏭️ 刷新失败，社区和游戏签到跳过')
            if account.get('cloudToken'):
                stage('查询云异环时长及待领取数量', lambda: cloud_query(account))
        elapsed = round(time.monotonic()-account_start, 2)
        ok = stats['failure'] == 0
        log(f'账号 {i} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {elapsed} 秒')
        results.append(dict(account=i, ok=ok, statistics=stats, durationSeconds=elapsed))
    success = sum(r['ok'] for r in results)
    failed = len(results) - success
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and success else 'failure' if failed else 'dry-run' if DRY else 'success')
    totals = {k: sum(r['statistics'][k] for r in results) for k in ('total','success','alreadyComplete','skipped','failure')}
    body = f'状态：{status}；账号总数 {len(rows)}，成功 {success}，失败 {failed}；子任务成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，失败 {totals["failure"]}'
    notification = notify_summary(body)
    log('----------------------------------------')
    log('最终任务统计：' + body)
    log(f'子任务总数 {totals["total"]}，跳过 {totals["skipped"]}；通知状态：{notification}')
    finished = datetime.now().isoformat(timespec='seconds')
    duration = round(time.monotonic()-started, 2)
    log(f'完成时间：{finished}；总耗时 {duration} 秒；最终状态：{status}；退出码：{exit_code}')
    print('TASK_SUMMARY=' + json.dumps(dict(applicationKey='nte', mode='dry-run' if DRY else 'live', status=status, accountCount=len(rows), successCount=success, failureCount=failed, statistics=totals, accounts=results, notification=notification, durationSeconds=duration, finishTime=finished, exitCode=exit_code), ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
