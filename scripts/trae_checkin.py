#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Trae 每日签到与积分查询
# cron: 7,23,37 * * * *
"""Trae 每日签到（默认）与积分查询（TRAE_TASK=credits）。
来源：L0NE-6/Trae-AutoCheckin trae_checkin.py，以及 task.json 中同应用 MIT 参考。
合并来源：xz0609/trae-work-checkin-ql trae_work_checkin.py（MIT）；
同应用参考：03_checkin.py、trae_core.py、trae_credit_monitor.py。
网页来源：Cat-zaizai/ZaiZaiCat-Checkin script/trae/web_checkin.py 与 api.py（MIT）；
原网页思路归属 star620/TRAE-Automatic-sign-in，保留署名，不采用随机设备绕过。
网页账号仍用 TRAE_ACCOUNTS 每行一个 JSON：session 和/或 sessionid，加真实 deviceId。
在本人浏览器登录 https://www.trae.cn，F12 → 应用 → Cookie → www.trae.cn，
复制 X-Cloudide-Session 的 Value 到 session；长效 sessionid 的 Value 到 sessionid。
原样保留百分号编码，不粘贴整个 Cookie 请求头；两者须属于同一账号。
兼容 TRAE_SESSION、TRAE_SESSIONID（各按行对应同一账号），--session 单账号；
设备号用同账号 TRAE_DEVICE_ID[_2.._9] 或 JSON deviceId，禁止随机生成及风控换号。
网页会话过期时用 sessionid 换新会话，以 0600 权限缓存；领取后复查今日状态。
主来源 Cat-zaizai/ZaiZaiCat-Checkin script/trae/main.py（MIT），Author: Assistant，Date: 2026-09-07。
主来源原定时 30 8 * * * 可继续为同一脚本配置；默认维护定时保持不变。
兼容主来源 JSON 字段 account_name、expires_at；不扫描客户端、不自动生成或轮换设备号。
只用官方成功响应的公开 UserID 识别重复配置；保留每账号状态核验和真实余额查询。
重复配置单独统计，不将其误报为新领取；任一账号失败仍整体非零退出。
网页鉴权失效时保留同账号显式桌面令牌回退；领取报错时复查官方状态，确认完成才成功。
凭据失效单独统计，方便更新；不记录异常详情或服务端原文。
原定时：23 0 * * * 主签，7,37 * * * * 补签；可分别创建青龙任务。
Trae Work 原定时 0 8,20 * * * 可继续使用同一脚本 checkin 命令。
TRAE_ACCOUNTS：每个非空行一个 JSON 对象，配套凭据放在同一对象中。
字段：accessToken 或 refreshToken，deviceId（同账号官方客户端真实设备号），
deviceKeyPem、devicePubPem、machineId（新版续期需要同设备证明），uid、name 可选。
可从本人已登录官方客户端的登录响应和本地 storage.json 中安全取得这些值，
不要提交、分享或打印凭据；不需要在青龙安装客户端或其他仓库。
兼容旧 JSON 数组、TRAE_REFRESH_TOKEN[_2.._9]、TRAE_ACCESS_TOKEN[_2.._9]。
TRAE_ICUBE_AUTH / TRAE_STORAGE_PATH 仅显式提供时读取，不自动扫描桌面目录。
兼容 auth 文件：每行可写 {"authPath":"本人上传的 auth-用户.json 路径"}，
或显式设置 TRAE_AUTH_DIR 指向 auths 目录；均不会自动扫描客户端或改写源文件。
文件中的 claimDeviceId 优先于 deviceId，保留同设备 fingerprint 的 brand/type/os。
在本人客户端 storage.json 的 iCubeAuthInfo://icube-dc:<数字> 键取得真实设备号，
配套密钥与 machineId 必须属于同一设备；不要生成设备号或借用其他账号设备。
交互登录：TRAE_DEVICE_ID 配置真实设备号后执行 python candidate.py login，
按终端提示在浏览器打开本地登录入口；自动捕获回调或在本地表单隐藏粘贴完整回调。
登录最长 TRAE_LOGIN_TIMEOUT 秒（默认 300），新会话保存为权限 0600 的 auth 文件。
TRAE_AUTH_DIR 默认为脚本同目录 auths（只用于显式 login 的写入；签到读取须显式配置）。
后续可使用 authPath 或 TRAE_AUTH_DIR；令牌轮换仍写 TRAE_TOKEN_CACHE 而不改源文件。
复制客户端的刷新凭据会共用轮换链，建议交互登录建立单独会话。
上游 RANDOM_SIGNIN/MAX_RANDOM_DELAY 显式设置时兼容每账号随机等待；
未设置时保持规范脚本原有启动及账号间错峰，不增加默认一小时等待。
兼容 TRAE_JITTER_MAX 显式设置启动错峰上限；维护默认仍为 20 秒，上游原默认 600 秒不迁移。
TRAE_DRY_RUN=1：只验证配置及列出动作；禁止所有联网和文件写入。
本脚本不会发布帖子、评论或分享。不会自动切换其他账号设备或改写账号源文件。
令牌续期会轮换服务端 refreshToken，并以 0600 权限缓存最新凭据。
仅 code=0、9095 或经过核验的当天完成状态算签到成功；冷却及未开放非成功。

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
        _ql_notify_identities = ('71de90498a3a6ded', 'scripts/trae_checkin.py', 'trae_checkin.py', 'trae_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import datetime
import hashlib
import json
import math
import os
import platform
import random
import re
import subprocess
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
from pathlib import Path

UgHost = 'https://api.trae.cn'
OAuthHost = 'https://api.trae.com.cn'
ClientID = 'en1oxy7wnw8j9n'
ClientIDIde = os.getenv('TRAE_CLIENT_ID', '').strip() or 'ono9krqynydwx5'
IdeVersion = '1.107.1'
UA = 'Trae/' + IdeVersion
EP_STATUS = UgHost + '/trae/api/v2/ug/checkin_credits/status'
EP_CLAIM = UgHost + '/trae/api/v2/ug/checkin_credits/claim'
EP_ENTITLE = UgHost + '/trae/api/v2/pay/user_current_entitlement_list'
EP_USAGE = UgHost + '/trae/api/v2/pay/ide_user_ent_usage'
EP_EXCHANGE = OAuthHost + '/cloudide/api/v3/trae/oauth/ExchangeToken'
EP_EXCHANGE_PROOF = UgHost + '/trae/api/v3/oauth/ExchangeToken'
AUTH_FAIL_CODES = (1001, 1002, 1003, 10085, 401, 403)
RATE_HTTP_CODES = (429, 500, 502, 503, 504)
DISABLED = ('0', 'false', 'no', 'off')
DRY = os.getenv('TRAE_DRY_RUN', '0').lower() not in DISABLED
BJ = datetime.timezone(datetime.timedelta(hours=8))
MAX_RESPONSE = 1024 * 1024


def stamp():
    return datetime.datetime.now(BJ).strftime('%Y-%m-%d %H:%M:%S')


def log(text):
    print('[' + stamp()[11:] + '] ' + text, flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def http(url, headers, body, timeout=30, response_headers=None):
    if DRY:
        raise TaskError('预演禁止网络请求')
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        try:
            response = _opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            if response_headers is not None:
                response_headers.extend(response.headers.get_all('Set-Cookie', []))
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise TaskError('响应过大')
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            raise TaskError('响应结构错误')
        return status, data
    except TaskError:
        raise
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None
    except Exception:
        raise TaskError('网络连接失败或超时') from None


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def code_of(data):
    value = data.get('code')
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and re.fullmatch(r'-?\d{1,8}', value):
        return int(value)
    return None


def root_of(data):
    return data['data'] if isinstance(data.get('data'), dict) else data


def checked_success(status, data):
    return 200 <= status < 300 and code_of(data) == 0


def observe_uid(acc, data):
    # 仅使用成功官方响应的公开身份，不从未核验的 JWT 或配置猜测账号归属。
    for obj in (data, root_of(data), root_of(data).get('user_info', {})):
        if not isinstance(obj, dict):
            continue
        for field in ('UserID', 'userId', 'uid'):
            value = obj.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and value != '':
                text = str(value)
                if re.fullmatch(r'(?:\+?86)?1[3-9]\d{9}', text):
                    continue
                if any(secret and secret in text for secret in SECRETS):
                    continue
                acc['_officialUid'] = text
                return


def identify_duplicate(acc, seen):
    uid = acc.get('_officialUid')
    if not uid:
        return
    owner = seen.setdefault(uid, acc['_index'])
    if owner != acc['_index'] and not acc.get('_duplicateOf'):
        acc['_duplicateOf'] = owner
        log('⚠️ 重复配置：官方公开 UID 与账号%d 相同；仍独立核验状态和余额，不重复领取已完成签到' % owner)


def identity(data):
    for obj in (data, root_of(data), root_of(data).get('user_info', {})):
        if not isinstance(obj, dict):
            continue
        for field in ('nickname', 'username', 'display_name', 'displayName', 'uid', 'userId', 'UserID', 'ScreenName'):
            value = obj.get(field)
            if isinstance(value, (str, int)) and value != '':
                # 仅展示官方身份字段，过滤手机号、控制字符和可能的凭据反射。
                text = str(value)
                if re.fullmatch(r'(?:\+?86)?1[3-9]\d{9}', text):
                    continue
                if any(secret and secret in text for secret in SECRETS):
                    continue
                log('官方账号身份：' + re.sub(r'[\x00-\x1f\x7f]', ' ', text))
                return


SECRETS = []

def ug_headers(token, device_id, acc=None):
    # 与桌面端 _applyUgDeviceHeaders 对齐：缺这些设备头会被服务端拒成 9074
    headers = {'Authorization': 'Cloud-IDE-JWT ' + token, 'X-User-Region': 'CN',
               'User-Agent': UA, 'Content-Type': 'application/json'}
    if device_id:
        headers['x-device-id'] = device_id
    headers['x-device-type'] = platform.system() or 'Windows'
    headers['x-os-version'] = platform.version() or '10.0.19045'
    headers['x-app-version'] = IdeVersion
    brand = os.getenv('TRAE_DEVICE_BRAND', '').strip()
    if brand:
        headers['x-device-brand'] = brand
    # 兼容 Trae Work 登录文件的同设备指纹；不探测或轮换其他设备。
    fingerprint = (acc or {}).get('fingerprint') or {}
    if isinstance(fingerprint, dict):
        for field, header in (('brand', 'x-device-brand'), ('type', 'x-device-type'), ('os', 'x-os-version')):
            if isinstance(fingerprint.get(field), str) and fingerprint[field].strip():
                headers[header] = fingerprint[field].strip()
    return headers


P256_P = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
P256_A = P256_P - 3
P256_N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
P256_GX = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
P256_GY = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5


def _der_tlv(buf, i):
    tag = buf[i]; i += 1
    ln = buf[i]; i += 1
    if ln & 0x80:
        n = ln & 0x7f
        ln = int.from_bytes(buf[i:i + n], 'big'); i += n
    return tag, buf[i:i + ln], i + ln


def _pem_der(pem):
    body = ''.join(l.strip() for l in pem.splitlines() if '---' not in l)
    return base64.b64decode(body)


def ec_private_scalar(pem):
    """从 PKCS#8 / SEC1 PEM 里取出 P-256 私钥标量。"""
    der = _pem_der(pem)
    try:
        _, body, _ = _der_tlv(der, 0)
        i = 0
        _, _, i = _der_tlv(body, i)
        _, _, i = _der_tlv(body, i)
        _, octs, i = _der_tlv(body, i)
        _, inner, _ = _der_tlv(octs, 0)
        j = 0
        _, _, j = _der_tlv(inner, j)
        _, d, j = _der_tlv(inner, j)
        return int.from_bytes(d, 'big')
    except Exception:
        _, body, _ = _der_tlv(der, 0)
        i = 0
        _, _, i = _der_tlv(body, i)
        _, d, i = _der_tlv(body, i)
        return int.from_bytes(d, 'big')


def _ec_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P256_P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1 + P256_A) * pow(2 * y1, -1, P256_P) % P256_P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, P256_P) % P256_P
    x3 = (lam * lam - x1 - x2) % P256_P
    return x3, (lam * (x1 - x3) - y1) % P256_P


def _ec_mul(k, pt):
    r = None
    while k:
        if k & 1:
            r = _ec_add(r, pt)
        pt = _ec_add(pt, pt)
        k >>= 1
    return r


def _der_sig(r, s):
    def enc(x):
        b = x.to_bytes(32, 'big').lstrip(b'\x00') or b'\x00'
        if b[0] & 0x80:
            b = b'\x00' + b
        return b'\x02' + bytes([len(b)]) + b
    body = enc(r) + enc(s)
    return b'\x30' + bytes([len(body)]) + body


def ec_sign(pem, data):
    """ECDSA P-256 / SHA-256 签名，返回 base64(DER)。低 s 归一化，与客户端一致。"""
    d = ec_private_scalar(pem)
    if not 1 <= d < P256_N:
        raise ValueError("设备私钥不合法")
    z = int.from_bytes(hashlib.sha256(data).digest(), 'big')
    while True:
        k = int.from_bytes(os.urandom(32), 'big') % (P256_N - 1) + 1
        x1, _ = _ec_mul(k, (P256_GX, P256_GY))
        r = x1 % P256_N
        if r == 0:
            continue
        s = (pow(k, -1, P256_N) * (z + r * d)) % P256_N
        if s == 0:
            continue
        if s > P256_N // 2:
            s = P256_N - s
        return base64.b64encode(_der_sig(r, s)).decode('ascii')


def norm_pem(v):
    """把环境变量里字面量的 \\n 还原成真换行（复制粘贴友好）。"""
    v = (v or '').strip()
    if '\\n' in v and '\n' not in v:
        v = v.replace('\\n', '\n')
    return v


def device_proof(path, refresh_token, keys, client_id=None, platform_code='IDE_PC'):
    """构造 (DeviceProof, DeviceInfo)，供新版 ExchangeToken 使用。"""
    ts = int(time.time())
    nonce = os.urandom(16).hex()
    canonical = '\n'.join(['POST', path, client_id or ClientID, refresh_token, str(ts), nonce])
    proof = {'Timestamp': ts, 'Nonce': nonce,
             'Signature': ec_sign(keys['privateKeyPem'], canonical.encode('utf-8'))}
    info = {'DeviceID': keys.get('deviceId') or '', 'MachineID': keys.get('machineId') or '',
            'PlatformCode': platform_code, 'DeviceType': 'PC',
            'DeviceName': os.getenv('TRAE_DEVICE_NAME', '').strip() or platform.node() or 'PC',
            'DeviceModel': os.getenv('TRAE_DEVICE_MODEL', '').strip(),
            'ClientVersion': IdeVersion, 'DevicePublicKey': keys['publicKeyPem'],
            'DeviceBrand': os.getenv('TRAE_DEVICE_BRAND', '').strip(), 'DeviceCPU': '',
            'OSInfo': platform.system() or 'Windows', 'OSVersion': platform.release() or ''}
    return proof, info



def read_json(path):
    if not path.exists():
        return {}
    try:
        with path.open(encoding='utf-8') as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise TaskError('本地缓存格式错误，停止以避免丢失轮换凭据') from None


def write_json(path, data):
    if DRY:
        raise TaskError('预演禁止写入')
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.trae-', dir=str(path.parent))
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            os.chmod(temporary, 0o600)
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        raise TaskError('安全缓存写入失败；轮换凭据可能需要重新取得') from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def jwt_exp(token):
    try:
        part = token.split('.')[1]
        return int(json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))).get('exp', 0))
    except Exception:
        return 0


def expiry_seconds(value):
    try:
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            return 0
        return value / 1000 if value > 1e12 else value
    except (TypeError, ValueError):
        return 0


def exchange(acc, cache, cache_path):
    refresh_token = acc.get('refreshToken', '')
    if not refresh_token:
        raise TaskError('缺少 refreshToken，无法续期')
    did = acc['deviceId']
    priv = norm_pem(acc.get('deviceKeyPem') or os.getenv('TRAE_DEVICE_KEY_PEM', ''))
    pub = norm_pem(acc.get('devicePubPem') or os.getenv('TRAE_DEVICE_PUB_PEM', ''))
    keys = {'deviceId': did, 'privateKeyPem': priv, 'publicKeyPem': pub,
            'machineId': acc.get('machineId') or os.getenv('TRAE_MACHINE_ID', '')}
    if bool(priv) != bool(pub):
        raise TaskError('设备私钥和公钥必须配套提供')
    if priv:
        combos = list(dict.fromkeys([(ClientIDIde, 'IDE_PC'), (ClientID, 'IDE_PC'), (ClientID, 'SOLO_PC')]))
    else:
        combos = [(ClientID, None)]
    for cid, platform_code in combos:
        if platform_code:
            try:
                proof, info = device_proof('/trae/api/v3/oauth/ExchangeToken', refresh_token, keys, cid, platform_code)
            except Exception:
                raise TaskError('设备签名失败，请检查同设备的 P-256 密钥') from None
            body = {'ClientID': cid, 'ClientSecret': '', 'RefreshToken': refresh_token,
                    'DeviceInfo': info, 'DeviceProof': proof, 'IDEVersion': IdeVersion}
            url = EP_EXCHANGE_PROOF
            headers = {'Content-Type': 'application/json', 'x-cloudide-token': ''}
        else:
            body = {'ClientID': cid, 'RefreshToken': refresh_token, 'ClientSecret': '-', 'UserID': str(acc.get('uid') or '')}
            url = EP_EXCHANGE
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': UA}
        status, data = http(url, headers, body)
        metadata = data.get('ResponseMetadata')
        error = metadata.get('Error') if isinstance(metadata, dict) else None
        error_code = error.get('Code') if isinstance(error, dict) else None
        if error_code in (10101, 20403, '10101', '20403') and platform_code:
            continue
        if not 200 <= status < 300 or error or ('code' in data and code_of(data) != 0):
            if error_code in (20101, '20101') or status in (401, 403):
                acc['_credentialError'] = True
            hint = {20405: '需要同设备证明', 20403: '设备与凭据不匹配', 10101: '客户端与凭据不匹配',
                    20101: '刷新凭据已失效'}.get(error_code, '接口未确认成功')
            raise TaskError('令牌续期失败：' + hint)
        result = data.get('Result') or data.get('data')
        token = (result.get('Token') or result.get('AccessToken') or result.get('access_token')) if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise TaskError('令牌续期响应缺少 Token')
        new_refresh = result.get('RefreshToken') or result.get('refresh_token') or refresh_token
        if not isinstance(new_refresh, str):
            raise TaskError('续期响应的刷新凭据格式错误')
        acc.update(accessToken=token, refreshToken=new_refresh)
        SECRETS.extend([token, new_refresh])
        expiry = expiry_seconds(result.get('TokenExpireAt') or result.get('expiresAt')) or jwt_exp(token)
        acc['expiresAt'] = expiry
        observe_uid(acc, result)
        cache[acc['_key']] = {'officialUid': acc.get('_officialUid', ''), 'accessToken': token, 'refreshToken': new_refresh,
                              'expiresAt': expiry}
        # 轮换后立即落盘，后续任何业务失败都不能丢掉刷新链。
        write_json(cache_path, cache)
        log('✅ 令牌续期并安全保存成功')
        observe_uid(acc, result)
        identity(result)
        return
    raise TaskError('令牌续期失败：参考支持的客户端组合均不匹配')


def web_headers(cookie_name, value):
    return {'Cookie': cookie_name + '=' + value, 'Referer': 'https://www.trae.cn/',
            'Origin': 'https://www.trae.cn', 'User-Agent': 'VSCode 1.107.1 (TRAE SOLO CN)',
            'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json'}


class WebSessionError(TaskError):
    pass


def web_exchange(acc, cache, cache_path):
    """网页独立 HTTP 链：会话换 JWT，失效时仅续期本账号会话一次。"""
    def fetch():
        status, data = http(UgHost + '/cloudide/api/v3/common/GetUserToken',
                            web_headers('X-Cloudide-Session', acc['session']), {}, 30)
        log('网页换令牌：HTTP %d（凭据及原始响应已隐藏）' % status)
        if status not in (200, 401, 403):
            raise TaskError('网页换令牌服务暂不可用，不轮换会话')
        result = data.get('Result')
        metadata = data.get('ResponseMetadata')
        error = metadata.get('Error') if isinstance(metadata, dict) else None
        if (status != 200 or error or ('code' in data and code_of(data) != 0)
                or not isinstance(result, dict) or not isinstance(result.get('Token'), str)
                or not result['Token'].strip()):
            raise WebSessionError('网页换令牌未确认成功，请更新本账号 Cookie')
        return result

    try:
        if not acc.get('session'):
            raise WebSessionError('缺少网页会话')
        result = fetch()
    except WebSessionError:
        if not acc.get('sessionid'):
            raise
        cookies = []
        status, data = http(UgHost + '/cloudide/api/v3/trae/Login',
                            web_headers('sessionid', acc['sessionid']), {}, 30, cookies)
        metadata = data.get('ResponseMetadata')
        error = metadata.get('Error') if isinstance(metadata, dict) else None
        if status != 200 or error or ('code' in data and code_of(data) != 0):
            if status in (401, 403) or error or ('code' in data and code_of(data) in AUTH_FAIL_CODES):
                raise WebSessionError('长效 Cookie 鉴权失败，请更新本账号 Cookie')
            raise TaskError('长效 Cookie 续期未确认成功')
        new_session = ''
        for header in cookies:
            parsed = SimpleCookie()
            try:
                parsed.load(header)
            except Exception:
                continue
            if 'X-Cloudide-Session' in parsed:
                new_session = parsed['X-Cloudide-Session'].value
        if not new_session or any(c in new_session for c in '\r\n;'):
            raise TaskError('续期响应缺少有效网页会话')
        acc['session'] = new_session
        SECRETS.append(new_session)
        cache.setdefault(acc['_key'], {})['session'] = new_session
        write_json(cache_path, cache)
        log('✅ 长效 Cookie 已续期，本账号新会话已安全保存')
        result = fetch()
    acc['accessToken'] = result['Token']
    acc['expiresAt'] = expiry_seconds(result.get('TokenExpireAt')) or jwt_exp(result['Token'])
    SECRETS.append(result['Token'])
    entry = cache.setdefault(acc['_key'], {})
    observe_uid(acc, result)
    entry.update(accessToken=acc['accessToken'], expiresAt=acc['expiresAt'], session=acc.get('session', ''),
                 officialUid=acc.get('_officialUid', ''))
    write_json(cache_path, cache)
    log('✅ 网页会话换取令牌成功')
    observe_uid(acc, result)
    identity(result)


def renew_access(acc, cache, cache_path):
    if not acc.get('_web'):
        return exchange(acc, cache, cache_path)
    try:
        return web_exchange(acc, cache, cache_path)
    except WebSessionError:
        access = acc.get('_desktopAccessToken', '')
        refresh = acc.get('_desktopRefreshToken', '')
        if not access and not refresh:
            acc['_credentialError'] = True
            raise
        acc['_web'] = False
        acc['accessToken'] = access
        acc['refreshToken'] = refresh
        acc['expiresAt'] = acc.get('_desktopExpiresAt', 0)
        log('⚠️ 网页鉴权失效，回退本账号显式桌面凭据；保留绑定设备，不借用其他账号')
        expiry = jwt_exp(access) or expiry_seconds(acc['expiresAt'])
        if not access or (expiry and expiry <= time.time() + 60):
            return exchange(acc, cache, cache_path)


def request_account(acc, url, body, cache, cache_path, refresh_allowed=True):
    expiry = jwt_exp(acc.get('accessToken', '')) or expiry_seconds(acc.get('expiresAt'))
    if not acc.get('accessToken') or (expiry and expiry <= time.time() + 60):
        renew_access(acc, cache, cache_path)
    status, data = http(url, ug_headers(acc['accessToken'], acc['deviceId'], acc), body, 20)
    if refresh_allowed and (status in (401, 403) or code_of(data) in AUTH_FAIL_CODES
                            or (acc.get('_web') and code_of(data) in (1003, 10085))) and (acc.get('_web') or acc.get('refreshToken')):
        renew_access(acc, cache, cache_path)
        status, data = http(url, ug_headers(acc['accessToken'], acc['deviceId'], acc), body, 20)
    if status in (401, 403) or code_of(data) in AUTH_FAIL_CODES:
        acc['_credentialError'] = True
    log('请求结果：HTTP %d，业务码 %s' % (status, code_of(data) if code_of(data) is not None else '未提供'))
    if checked_success(status, data):
        observe_uid(acc, data)
    identity(data)
    return status, data


def parse_accounts(session_override=None):
    raw = os.getenv('TRAE_ACCOUNTS', '').strip()
    if raw:
        try:
            if raw.startswith('['):
                entries = json.loads(raw)
                if not isinstance(entries, list):
                    raise ValueError()
            else:
                entries = []
                for line in raw.splitlines():
                    if not line.strip():
                        continue
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        entries.append(None)
        except Exception:
            raise TaskError('TRAE_ACCOUNTS 配置格式错误') from None
    else:
        entries = []
        # 显式列出兼容名称，让导入契约与真实执行器识别同一组环境变量。
        token_names = (
            ('TRAE_ACCESS_TOKEN', 'TRAE_REFRESH_TOKEN'),
            ('TRAE_ACCESS_TOKEN_2', 'TRAE_REFRESH_TOKEN_2'),
            ('TRAE_ACCESS_TOKEN_3', 'TRAE_REFRESH_TOKEN_3'),
            ('TRAE_ACCESS_TOKEN_4', 'TRAE_REFRESH_TOKEN_4'),
            ('TRAE_ACCESS_TOKEN_5', 'TRAE_REFRESH_TOKEN_5'),
            ('TRAE_ACCESS_TOKEN_6', 'TRAE_REFRESH_TOKEN_6'),
            ('TRAE_ACCESS_TOKEN_7', 'TRAE_REFRESH_TOKEN_7'),
            ('TRAE_ACCESS_TOKEN_8', 'TRAE_REFRESH_TOKEN_8'),
            ('TRAE_ACCESS_TOKEN_9', 'TRAE_REFRESH_TOKEN_9'),
        )
        for i, (access_name, refresh_name) in enumerate(token_names, 1):
            suffix = '' if i == 1 else '_' + str(i)
            access = os.getenv(access_name, '').strip()
            refresh = os.getenv(refresh_name, '').strip()
            if access or refresh:
                entries.append({'accessToken': access, 'refreshToken': refresh,
                                'deviceId': os.getenv('TRAE_DEVICE_ID' + suffix, ''),
                                'uid': os.getenv('TRAE_UID' + suffix, ''),
                                'name': os.getenv('TRAE_NAME' + suffix, '')})
        if not entries and (session_override or os.getenv('TRAE_SESSION') or os.getenv('TRAE_SESSIONID')):
            sessions = (session_override or os.getenv('TRAE_SESSION', '')).splitlines()
            long_sessions = os.getenv('TRAE_SESSIONID', '').splitlines()
            if sessions and long_sessions and len(sessions) != len(long_sessions):
                raise TaskError('TRAE_SESSION 与 TRAE_SESSIONID 账号行数必须一致')
            for i in range(max(len(sessions), len(long_sessions))):
                suffix = '' if i == 0 else '_' + str(i + 1)
                entries.append({'session': sessions[i].strip() if i < len(sessions) else '',
                                'sessionid': long_sessions[i].strip() if i < len(long_sessions) else '',
                                'deviceId': os.getenv('TRAE_DEVICE_ID' + suffix, '')})
        if not entries and os.getenv('TRAE_ICUBE_AUTH'):
            entries = [{'icubeAuth': os.getenv('TRAE_ICUBE_AUTH'), 'deviceId': os.getenv('TRAE_DEVICE_ID', '')}]
        if not entries and os.getenv('TRAE_STORAGE_PATH'):
            entries = [{'storagePath': os.getenv('TRAE_STORAGE_PATH')}]
        if not entries and os.getenv('TRAE_AUTH_DIR'):
            if DRY:
                raise TaskError('预演不读取 auth 目录，请用 TRAE_ACCOUNTS 提供占位明文凭据')
            directory = Path(os.environ['TRAE_AUTH_DIR'])
            entries = [{'authPath': str(p)} for p in sorted(directory.glob('auth-*.json'))]
    if not entries:
        raise TaskError('请配置 TRAE_ACCOUNTS：每行一个账号 JSON 对象')
    accounts = []
    for index, raw_account in enumerate(entries, 1):
        acc = dict(raw_account) if isinstance(raw_account, dict) else {'_error': '账号必须是 JSON 对象'}
        acc.pop('_error', None) if isinstance(raw_account, dict) else None
        if acc.get('authPath') and not DRY:
            try:
                with open(acc['authPath'], encoding='utf-8') as handle:
                    stored = json.load(handle)
                if not isinstance(stored, dict):
                    raise ValueError()
                stored.update(acc)
                acc = stored
            except Exception:
                acc['_error'] = '显式 auth 凭据文件无法读取或格式错误'
        acc['_index'] = index
        aliases = {'accessToken': ('token', 'access_token'), 'refreshToken': ('refresh_token',),
                   'deviceId': ('claimDeviceId', 'realDeviceId', 'device_id'), 'deviceKeyPem': ('device_key_pem', 'privateKeyPem'),
                   'devicePubPem': ('device_pub_pem', 'publicKeyPem'), 'machineId': ('machine_id',),
                   'uid': ('userId', 'user_id'), 'session': ('X-Cloudide-Session',),
                   'name': ('account_name', 'screenName'), 'expiresAt': ('expires_at',)}
        for canonical, alternatives in aliases.items():
            if not acc.get(canonical):
                acc[canonical] = next((acc[k] for k in alternatives if acc.get(k)), '')
        if acc.get('claimDeviceId'):
            acc['deviceId'] = acc['claimDeviceId']
        if not acc.get('name'):
            acc['name'] = acc.get('screenName', '')
        for field in ('accessToken', 'refreshToken', 'deviceId', 'deviceKeyPem', 'devicePubPem', 'machineId', 'session', 'sessionid'):
            if not isinstance(acc.get(field, ''), str):
                acc['_error'] = '凭据字段必须是字符串'
                acc[field] = ''
            SECRETS.append(acc.get(field, ''))
        if not acc['deviceId'] and len(entries) == 1:
            acc['deviceId'] = os.getenv('TRAE_DEVICE_ID', '').strip()
            SECRETS.append(acc['deviceId'])
        acc['_web'] = bool(acc.get('session') or acc.get('sessionid'))
        if acc['_web']:
            acc['_desktopAccessToken'] = acc.get('accessToken', '')
            acc['_desktopRefreshToken'] = acc.get('refreshToken', '')
            acc['_desktopExpiresAt'] = acc.get('expiresAt', 0)
        for field in ('session', 'sessionid'):
            if any(c in acc.get(field, '') for c in '\r\n;'):
                acc['_error'] = 'Cookie 字段仅填单个 Value，不得包含换行或分号'
        seed = ('authPath:' + str(acc['authPath'])) if acc.get('authPath') else acc.get('sessionid') or acc.get('session') or acc.get('refreshToken') or acc.get('accessToken') or str(index)
        acc['_key'] = hashlib.sha256(('uid:' + str(acc['uid']) if acc.get('uid') else 'credential:' + seed).encode()).hexdigest()
        accounts.append(acc)
    only = os.getenv('TRAE_ONLY', '').strip()
    if only:
        accounts = [a for a in accounts if only in (str(a['_index']), str(a.get('uid', '')), str(a.get('name', '')))]
        if not accounts:
            raise TaskError('TRAE_ONLY 未匹配账号，停止以免误操作其他账号')
    return accounts


def parse_hours(spec):
    result = set()
    for part in spec.replace('，', ',').split(','):
        fields = part.split('-')
        try:
            first, last = int(fields[0]), int(fields[-1])
            if len(fields) > 2 or not 0 <= first <= last <= 23:
                raise ValueError()
            result.update(range(first, last + 1))
        except ValueError:
            raise TaskError('TRAE_PEAK_HOURS 格式错误') from None
    return result


def integer_env(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
        if not minimum <= value <= maximum:
            raise ValueError()
        return value
    except ValueError:
        raise TaskError(name + ' 数值超出允许范围') from None


def balance(acc, cache, cache_path):
    for url, body in ((EP_ENTITLE, {'require_usage': True, 'full_data': True}), (EP_USAGE, {})):
        try:
            status, data = request_account(acc, url, body, cache, cache_path)
            if not checked_success(status, data):
                continue
            root = root_of(data)
            usage = root.get('usage_summary') or root.get('usageSummary') or {}
            if isinstance(usage, dict):
                total, used = usage.get('total_amount'), usage.get('consumed_amount')
                if numeric(total) and numeric(used) and total >= 0 and used >= 0:
                    return {'total': total, 'used': used, 'remain': round(total - used, 2)}
            packs = root.get('user_entitlement_pack_list') or root.get('userEntitlementPackList')
            if isinstance(packs, list) and packs:
                total = used = 0
                for pack in packs:
                    if not isinstance(pack, dict):
                        raise ValueError()
                    base = pack.get('entitlement_base_info') or pack
                    quota = base.get('quota') or base
                    limit = quota.get('credits_limit', quota.get('creditsLimit'))
                    consumption = pack.get('usage') or {}
                    amount = consumption.get('credits_amount', consumption.get('creditsAmount'))
                    if not numeric(limit) or not numeric(amount) or limit < 0 or amount < 0:
                        raise ValueError()
                    total += limit
                    used += amount
                return {'total': total, 'used': used, 'remain': round(total - used, 2)}
        except (TaskError, ValueError, TypeError, AttributeError):
            log('⚠️ 积分查询未通过核验，尝试同应用备用接口')
    raise TaskError('积分余额查询未获得明确成功及有效数值')


def notification(body):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    directory = os.getenv('QINGLONG_NOTIFY_DIR', '')
    paths = ([Path(directory) / 'notify.py'] if directory else []) + [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    py_path = next((p for p in paths if p.is_file()), None)
    # 在子进程中导入，限制时长并截获第三方日志，绝不改变业务退出码。
    program = '''import importlib.util, json, sys
v=json.loads(sys.stdin.read())
if v['dryRun']:
 import socket
 def deny(*args, **kwargs):
  raise RuntimeError('dry-run network disabled')
 socket.socket.connect=deny; socket.socket.connect_ex=deny; socket.socket.sendto=deny
 socket.getaddrinfo=deny; socket.create_connection=deny
if v['path']:
 s=importlib.util.spec_from_file_location('qinglong_notify', v['path']); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
else:
 import notify as m
m.send(v['title'], v['body'])
'''
    payload = {'dryRun': DRY, 'path': str(py_path) if py_path else '', 'title': 'Trae 每日签到与积分查询', 'body': body}
    try:
        result = subprocess.run([sys.executable, '-B', '-c', program], input=json.dumps(payload), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if result.returncode == 0:
            return '已发送'
    except Exception:
        pass
    js_paths = ([Path(directory) / 'sendNotify.js'] if directory else []) + [Path('/ql/data/scripts/sendNotify.js'), Path('/ql/scripts/sendNotify.js')]
    js_path = next((p for p in js_paths if p.is_file()), None)
    if js_path:
        program_js = """const fs=require('fs');const p=JSON.parse(fs.readFileSync(0,'utf8'));
if(p.dryRun){
 const deny=()=>{throw new Error('dry-run network disabled')};
 require('net').Socket.prototype.connect=deny;
 require('net').connect=deny;require('net').createConnection=deny;
 require('tls').connect=deny;require('dns').lookup=deny;require('dns').resolve=deny;
 require('dgram').Socket.prototype.send=deny;
 for(const n of ['http','https']){require(n).request=deny;require(n).get=deny;}
 globalThis.fetch=deny;
 const cp=require('child_process');
 for(const n of ['exec','execFile','spawn','fork','execSync','execFileSync','spawnSync'])cp[n]=deny;
}
Promise.resolve(require(p.path).sendNotify(p.title,p.body)).catch(()=>{process.exitCode=1});"""
        payload['path'] = str(js_path)
        try:
            result = subprocess.run(['node', '-e', program_js], input=json.dumps(payload), text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    if DRY:
        log('⚠️ 已尝试向青龙通知器提交预演摘要；断网保护禁止网络投递')
        return '预演摘要提交；网络投递已阻止或通知器不可用'
    log('⚠️ 青龙通知不可用或发送失败，保留业务退出码')
    return '不可用或失败'


def direct_push(body):
    if DRY or os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return
    key = os.getenv('QYWX_TOKEN') or os.getenv('WECHAT_WEBHOOK')
    if key:
        # 完整 webhook 仅提取 key，主机固定，避免凭据被转发。
        if 'key=' in key:
            from urllib.parse import parse_qs, urlsplit
            key = parse_qs(urlsplit(key).query).get('key', [''])[0]
        try:
            from urllib.parse import quote
            status, data = http('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=' + quote(key, safe=''),
                                {'Content-Type': 'application/json'}, {'msgtype': 'text', 'text': {'content': body}}, 8)
            log('企业微信通知：' + ('已发送' if 200 <= status < 300 and data.get('errcode') == 0 else '失败'))
        except Exception:
            log('企业微信通知：失败')
    token = os.getenv('PLUSPLUS_TOKEN', '')
    if token:
        try:
            status, data = http('https://www.pushplus.plus/send', {'Content-Type': 'application/json'},
                                {'token': token, 'title': 'Trae 每日签到与积分查询', 'content': body}, 8)
            log('PushPlus 通知：' + ('已发送' if 200 <= status < 300 and data.get('code') == 200 else '失败'))
        except Exception:
            log('PushPlus 通知：失败')


class AccountRun:
    def __init__(self, number):
        self.number = number
        self.started = time.monotonic()
        self.counts = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
        self.stage_number = 0
        self.claimed = False

    def stage(self, name, action):
        self.stage_number += 1
        log('账号%d · 阶段%d：%s' % (self.number, self.stage_number, name))
        started = time.monotonic()
        try:
            result = action()
        except Exception:
            self.counts['failure'] += 1
            log('❌ 阶段失败，耗时 %.2f 秒' % (time.monotonic() - started))
            raise
        self.counts['success'] += 1
        log('✅ 阶段完成，耗时 %.2f 秒' % (time.monotonic() - started))
        return result


def run_account(acc, run, task, cache, cache_path, state, state_path, options):
    def validate():
        if acc.get('_error'):
            raise TaskError(acc['_error'])
        if not acc.get('_web') and not acc.get('accessToken') and not acc.get('refreshToken'):
            if DRY and (acc.get('icubeAuth') or acc.get('storagePath') or acc.get('authPath')):
                raise TaskError('预演请提供占位明文凭据，不读取桌面凭据')
            load_explicit_credentials(acc)
        if not acc.get('_web') and not acc.get('accessToken') and not acc.get('refreshToken'):
            raise TaskError('该账号缺少 accessToken 或 refreshToken')
        if not re.fullmatch(r'\d{12,20}', acc.get('deviceId', '')):
            raise TaskError('缺少同账号官方客户端真实 deviceId（12 至 20 位数字）')
        if acc.get('accessToken') and acc.get('accessToken') == acc.get('refreshToken'):
            raise TaskError('accessToken 与 refreshToken 不应相同')
    run.stage('配置核验', validate)
    if DRY:
        if acc.get('_web'):
            log('网页预演：本账号会话换令牌、可选长效 Cookie 续期；保留真实设备号，领取后复查')
        run.stage('断网预演', lambda: log('DRY_RUN_OK：配置有效；计划' + ('查询积分' if task == 'credits' else '查询状态、按需签到、查询余额') + '，未发送请求或写入文件'))
        return 'dry-run'
    if task == 'checkin' and os.getenv('RANDOM_SIGNIN', 'false').strip().lower() not in DISABLED:
        delay = random.randint(0, integer_env('MAX_RANDOM_DELAY', 3600, 0, 86400))
        if delay:
            def wait_random():
                remaining = delay
                while remaining:
                    log('兼容随机等待：剩余 %d 秒' % remaining)
                    step = min(30, remaining)
                    time.sleep(step)
                    remaining -= step
            run.stage('显式随机错峰', wait_random)
    saved = cache.get(acc['_key'], {})
    if isinstance(saved, dict) and isinstance(saved.get('officialUid'), str) and saved['officialUid']:
        # 复用上次官方成功响应的公开 UID，兼容没有身份字段的状态接口。
        acc['_officialUid'] = saved['officialUid']
    identify_duplicate(acc, options['seen'])
    if acc.get('_web') and isinstance(saved, dict):
        for field in ('session', 'accessToken', 'expiresAt'):
            if saved.get(field):
                acc[field] = saved[field]
        SECRETS.extend([acc.get('session', ''), acc.get('accessToken', '')])
    if not acc.get('_web') and isinstance(saved, dict) and saved.get('accessToken') and saved.get('refreshToken'):
        acc['accessToken'] = saved['accessToken']
        acc['refreshToken'] = saved['refreshToken']
        acc['expiresAt'] = saved.get('expiresAt', 0)
        SECRETS.extend([acc['accessToken'], acc['refreshToken']])
    key = acc['_key']
    if task == 'checkin':
        if state['done'].get(key) is True:
            run.counts['alreadyComplete'] += 1
            log('☑️ 当天已核验签到，零请求复用完成状态')
            return 'already-complete'
        if float(state['cooldown'].get(key, 0)) > time.time():
            run.counts['failure'] += 1
            log('❌ 账号限流冷却中，未完成；等待后续定时重试')
            return 'failure'
        def query_status():
            status, data = request_account(acc, EP_STATUS, {'req_source': 1}, cache, cache_path)
            if status in RATE_HTTP_CODES or code_of(data) == 9074:
                state['cooldown'][key] = time.time() + options['cooldown'] * 60
                write_json(state_path, state)
                raise TaskError('状态接口限流，已记录冷却')
            if not checked_success(status, data):
                raise TaskError('签到状态查询未确认成功，不发送领取请求')
            root = root_of(data)
            checked = root.get('checked_in', root.get('checkedIn'))
            enabled = root.get('enable')
            if not isinstance(checked, bool) or not isinstance(enabled, bool):
                raise TaskError('签到状态缺少明确 checked_in 和 enable 布尔字段')
            log('签到状态：今日已签=%s，开放=%s' % ('是' if checked else '否', '是' if enabled else '否'))
            return checked, enabled
        checked, enabled = run.stage('查询签到状态', query_status)
        identify_duplicate(acc, options['seen'])
        if checked:
            run.counts['alreadyComplete'] += 1
        elif not enabled:
            raise TaskError('官方接口明确未开放签到，不发送领取请求')
        else:
            def claim():
                run.claimed = True
                for attempt in range(options['tries']):
                    status, data = request_account(acc, EP_CLAIM, {'req_source': 1}, cache, cache_path)
                    code = code_of(data)
                    if 200 <= status < 300 and code in (0, 9095):
                        if code == 9095:
                            run.counts['alreadyComplete'] += 1
                            log('☑️ 官方领取接口确认今日已签（9095）')
                        else:
                            points = root_of(data).get('points', root_of(data).get('credits'))
                            log('签到成功（code=0）' + ('；领取积分 %s' % points if numeric(points) else ''))
                        return
                    if status in RATE_HTTP_CODES or code == 9074:
                        if attempt + 1 < options['tries']:
                            log('⚠️ 显式重试设置生效，短暂退避后重试')
                            time.sleep(random.randint(4, 9))
                            continue
                        state['cooldown'][key] = time.time() + options['cooldown'] * 60
                        write_json(state_path, state)
                        failure_message = '领取限流，已记冷却，交给后续定时重试'
                    else:
                        failure_message = '领取接口未确认业务成功'
                    log('⚠️ 领取报错，复查本账号今日状态；不会再次发送领取')
                    try:
                        completed, _ = query_status()
                    except TaskError:
                        raise TaskError(failure_message) from None
                    if completed:
                        run.counts['alreadyComplete'] += 1
                        log('☑️ 领取报错但官方复查确认今日已签')
                        return
                    raise TaskError(failure_message)
            run.stage('按需领取签到积分', claim)
            def verify_claim():
                checked_after, _ = query_status()
                if not checked_after:
                    raise TaskError('领取后复查未确认今日已签，不记录完成状态')
                log('☑️ 领取后复查确认今日已签')
            run.stage('领取后状态复查', verify_claim)
        state['done'][key] = True
        state['cooldown'].pop(key, None)
        write_json(state_path, state)
    values = run.stage('查询真实积分余额', lambda: balance(acc, cache, cache_path))
    identify_duplicate(acc, options['seen'])
    log('积分：总额 %s，已用 %s，剩余 %s' % (values['total'], values['used'], values['remain']))
    return 'success'

SALT_A = bytes([82, 9, 106, 213, 48, 54, 165, 56, 191, 64, 163, 158, 129, 243, 215, 251,
                124, 227, 57, 130, 155, 47, 255, 135, 52, 142, 67, 68, 196, 222, 233, 203,
                84, 123, 148, 50, 166, 194, 35, 61, 238, 76, 149, 11, 66, 250, 195, 78,
                8, 46, 161, 102, 40, 217, 36, 178, 118, 91, 162, 73, 109, 139, 209, 37])
SALT_B = bytes([31, 221, 168, 51, 136, 7, 199, 49, 177, 18, 16, 89, 39, 128, 236, 95,
                96, 81, 127, 169, 25, 181, 74, 13, 45, 229, 122, 159, 147, 201, 156, 239,
                160, 224, 59, 77, 174, 42, 245, 176, 200, 235, 187, 60, 131, 83, 153, 97,
                23, 43, 4, 126, 186, 119, 214, 38, 225, 105, 20, 99, 85, 33, 12, 125])
SALT_C = bytes([191, 192, 216, 250, 122, 246, 220, 97, 31, 254, 98, 27, 8, 72, 71, 176,
                135, 99, 96, 18, 127, 101, 203, 104, 211, 102, 191, 125, 37, 72, 150, 156,
                51, 229, 121, 35, 17, 153, 141, 177, 110, 131, 150, 128, 172, 255, 254, 6,
                18, 140, 55, 62, 236, 249, 135, 64, 135, 12, 117, 4, 89, 149, 168, 209])
SALT_D = bytes([246, 204, 26, 232, 232, 70, 129, 109, 223, 146, 169, 242, 23, 241, 105, 145,
                50, 196, 165, 42, 254, 120, 3, 54, 244, 207, 209, 85, 53, 6, 138, 106,
                175, 148, 31, 204, 186, 186, 165, 182, 87, 142, 49, 10, 39, 110, 26, 154,
                86, 56, 173, 125, 18, 64, 198, 225, 99, 99, 83, 82, 191, 134, 76, 170])
SALT_AES = bytes(a ^ b for a, b in zip(SALT_A, SALT_B))
SALT_AES_PRIVATE = bytes(a ^ b for a, b in zip(SALT_C, SALT_D))
STORAGE_KEY = 'iCubeAuthInfo://icube.cloudide'


def enc_type_of(header):
    if header[0:6] == bytes([0x74, 0x63, 0x05, 0x10, 0x00, 0x00]):
        return 'AES'
    if header[0:6] == bytes([18, 57, 32, 32, 2, 3]):
        return 'AES_PRIVATE'
    return 'UNKNOWN'


def key_iv_of(random_bytes, enc_type):
    salt = SALT_AES_PRIVATE if enc_type == 'AES_PRIVATE' else SALT_AES
    final_hash = hashlib.sha512(hashlib.sha512(random_bytes).digest() + salt).digest()
    return final_hash[0:16], final_hash[16:32]


def decrypt_storage_value(base64_value):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise TaskError('解密凭据需要公共包 cryptography，'
                         '请 pip install cryptography；'
                         '或改用 accessToken/refreshToken 方式配置账号（零依赖）')
    buf = base64.b64decode(base64_value)
    enc_type = enc_type_of(buf[0:6])
    if enc_type == 'UNKNOWN':
        raise ValueError('未知的加密类型 (前 6 字节=%s)' % buf[0:6].hex())
    key, iv = key_iv_of(buf[6:38], enc_type)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    decrypted = dec.update(buf[38:]) + dec.finalize()
    stored_hash, plaintext = decrypted[0:64], decrypted[64:]
    # 桌面端写盘用 PKCS7 填充，去掉填充后再校验与解析（旧的非零填充一并兼容）
    pad = plaintext[-1] if plaintext else 0
    if 1 <= pad <= 16:
        plaintext = plaintext[:-pad]
    else:
        plaintext = plaintext.rstrip(b'\x00').rstrip()
    if stored_hash != hashlib.sha512(plaintext).digest():
        raise ValueError('SHA-512 校验失败，解密可能不正确')
    return plaintext.decode('utf-8')


_DEVICE_ID_RE = re.compile(r'^\d{12,20}$')


def is_valid_device_id(d):
    """设备号是否为客户端注册过的那种十进制数字串。

    位数不固定：多数是 16 位，也见过 15 位 —— 16 位只是观察，不是规则。
    服务端认的是「客户端注册过的那串数字」，所以这里只做防呆（12~20 位十进制）。
    """
    return bool(_DEVICE_ID_RE.match(str(d or '').strip()))


def dc_device_id(storage):
    """取客户端真实设备号：storage.json 里 iCubeAuthInfo://icube-dc:<数字> 键。

    也兼容「键名是 iCubeAuthInfo://icube-dc、号写在值里」的写法。
    取不到返回空串（不会回退生成号）。"""
    for k, v in storage.items():
        if k.startswith('iCubeAuthInfo://icube-dc:'):
            d = k[len('iCubeAuthInfo://icube-dc:'):].strip()
            if is_valid_device_id(d):
                return d
        elif k.rstrip(':') == 'iCubeAuthInfo://icube-dc' and is_valid_device_id(v):
            return str(v).strip()
    return ''


def load_explicit_credentials(acc):
    if DRY:
        raise TaskError('预演禁止读取真实凭据文件')
    try:
        if acc.get('icubeAuth'):
            raw = acc['icubeAuth']
        elif acc.get('storagePath'):
            with open(acc['storagePath'], encoding='utf-8') as handle:
                storage = json.load(handle)
            if not acc.get('deviceId'):
                acc['deviceId'] = dc_device_id(storage)
            raw = storage.get(STORAGE_KEY, '')
        else:
            return
        data = json.loads(raw if raw.startswith('{') else decrypt_storage_value(raw))
        acc['accessToken'] = data.get('accessToken') or data.get('token') or ''
        acc['refreshToken'] = data.get('refreshToken') or ''
        SECRETS.extend([acc['accessToken'], acc['refreshToken'], acc.get('deviceId', '')])
    except Exception:
        raise TaskError('显式凭据解密或读取失败，不扫描其他目录') from None


def callback_credentials(url, expected_host, expected_path):
    """只接受本次登录回调；不输出完整地址或异常详情。"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.netloc != expected_host or parsed.path != expected_path or len(url) > 65536:
        raise TaskError('回调地址与本次登录会话不匹配')
    query = urllib.parse.parse_qs(parsed.query, max_num_fields=30)
    def one(key):
        return query.get(key, [''])[0]
    def obj(key):
        value = one(key)
        for raw in (value, urllib.parse.unquote(value)):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
            except ValueError:
                pass
        return {}
    info, jwt = obj('userInfo'), obj('userJwt')
    refresh = one('refreshToken') or one('refresh_token') or one('data') or jwt.get('RefreshToken')
    access = jwt.get('Token') or jwt.get('token') or jwt.get('AccessToken') or ''
    if not isinstance(refresh, str) or not refresh or not isinstance(access, str):
        raise TaskError('登录回调缺少有效刷新凭据')
    SECRETS.extend([refresh, access])
    return {'refreshToken': refresh, 'accessToken': access,
            'uid': str(info.get('UserID') or jwt.get('UserID') or ''),
            'screenName': str(info.get('ScreenName') or info.get('screenName') or ''),
            'expiresAt': expiry_seconds(jwt.get('TokenExpireAt'))}


def interactive_login(device_id, timeout):
    """独立 HTTP OAuth 登录，无客户端、仓库或安装引导依赖。"""
    path = '/authorize/' + secrets.token_urlsafe(24)
    machine_id = os.getenv('TRAE_MACHINE_ID', '').strip() or secrets.token_hex(16)
    SECRETS.extend([device_id, machine_id])
    captured = []
    auth_url = ''
    host = ''

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') != host:
                self.send_error(400)
                return
            if self.path == '/login':
                self.send_response(302)
                self.send_header('Location', auth_url)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                return
            if self.path == '/paste':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                page = ('<!doctype html><meta charset="utf-8"><title>Trae 本地回调</title>'
                        '<p>仅在本机隐藏粘贴本次官方登录的完整回调地址，勿分享。</p>'
                        '<form method="post" action="' + path + '">'
                        '<input type="password" name="callback_url" autocomplete="off" required>'
                        '<button>提交回调</button></form>')
                self.wfile.write(page.encode('utf-8'))
                return
            try:
                cred = callback_credentials('http://' + host + self.path, host, path)
            except (TaskError, ValueError):
                self.send_error(400)
                return
            if not captured:
                captured.append(cred)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write('授权回调已接收，请回终端查看最终核验结果。'.encode('utf-8'))

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Host') != host or self.path != path or not 0 < length <= 65536:
                    raise ValueError()
                if self.headers.get_content_type() != 'application/x-www-form-urlencoded':
                    raise ValueError()
                fields = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'), max_num_fields=1)
                cred = callback_credentials(fields.get('callback_url', [''])[0], host, path)
            except (TaskError, ValueError, UnicodeError):
                self.send_error(400)
                return
            if not captured:
                captured.append(cred)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write('已接收回调，请回终端查看最终核验结果。'.encode('utf-8'))

        def log_message(self, *args):
            pass

    class BoundedServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(3)
            return connection, address

        def handle_error(self, *args):
            log('⚠️ 本地回调处理失败（详情已脱敏）')

    server = None
    for port in range(18080, 18100):
        try:
            server = BoundedServer(('127.0.0.1', port), CallbackHandler)
            break
        except OSError:
            continue
    if server is None:
        raise TaskError('本地回调端口 18080 至 18099 均不可用')
    server.timeout = 0.5
    host = '127.0.0.1:%d' % server.server_address[1]
    params = {'client_id': ClientID, 'auth_from': 'solo', 'login_channel': 'native_ide',
              'plugin_version': '2.3.62834', 'auth_callback_url': 'http://' + host + path,
              'x_app_version': '0.1.52', 'x_app_type': 'stable',
              'device_id': device_id, 'machine_id': machine_id}
    auth_url = 'https://www.trae.cn/authorization?' + urllib.parse.urlencode(params)
    log('请在运行脚本的电脑浏览器打开 http://' + host + '/login ，完成官方授权。')
    log('如需手动粘贴，请打开 http://' + host + '/paste 的隐藏输入表单；请勿分享回调或凭据文件。')
    deadline = time.monotonic() + timeout
    next_report = time.monotonic() + 30
    try:
        while time.monotonic() < deadline and not captured:
            server.handle_request()
            if time.monotonic() >= next_report:
                log('等待官方授权回调，剩余 %d 秒' % max(0, deadline - time.monotonic()))
                next_report = time.monotonic() + 30
        if not captured:
            raise TaskError('交互登录超时，未取得有效回调')
    finally:
        server.server_close()
    acc = captured[0]
    acc.update(deviceId=device_id, claimDeviceId=device_id, machineId=machine_id,
               fingerprint={'brand': os.getenv('TRAE_DEVICE_BRAND', '').strip(),
                            'type': platform.system(), 'os': platform.version()})
    # 文件名不采用未经验证的用户输入，避免目录穿越。
    filename = 'auth-' + hashlib.sha256((acc['uid'] or secrets.token_hex(16)).encode()).hexdigest()[:24] + '.json'
    destination = Path(os.getenv('TRAE_AUTH_DIR') or str(Path(__file__).parent / 'auths')) / filename
    acc['_key'] = hashlib.sha256(('uid:' + acc['uid'] if acc['uid'] else 'credential:authPath:' + str(destination)).encode()).hexdigest()
    # 原始回调不是业务成功证据；使用现有带设备证明的续期链验证并立即缓存轮换值。
    cache_path = Path(os.getenv('TRAE_TOKEN_CACHE') or str(Path(__file__).parent / '.trae_token_cache.json'))
    cache = read_json(cache_path)
    exchange(acc, cache, cache_path)
    identity({'uid': acc['uid'], 'displayName': acc['screenName']})
    saved = {key: value for key, value in acc.items() if not key.startswith('_')}
    write_json(destination, saved)
    log('✅ 登录成功：已通过续期接口核验，凭据已按 0600 权限保存；后续显式配置 authPath 或 TRAE_AUTH_DIR')
    return 'success'


def run_login(run):
    def validate():
        device_id = os.getenv('TRAE_DEVICE_ID', '').strip()
        if not is_valid_device_id(device_id):
            raise TaskError('交互登录请配置 TRAE_DEVICE_ID：同账号官方客户端真实设备号')
        return device_id, integer_env('TRAE_LOGIN_TIMEOUT', 300, 30, 900)
    device_id, timeout = run.stage('登录配置核验', validate)
    if DRY:
        run.stage('断网预演', lambda: log('DRY_RUN_OK：交互登录计划有效；未打开浏览器、监听端口、读取或写入凭据、发送请求'))
        return 'dry-run'
    return run.stage('交互授权、续期核验及安全保存', lambda: interactive_login(device_id, timeout))


def main():
    started = time.monotonic()
    start_time = stamp()
    results = []
    account_count = 0
    config_error = False
    log('========== Trae 每日签到与积分查询 ==========')
    log('开始时间：' + start_time)
    log('运行模式：' + ('断网预演' if DRY else '正式'))
    try:
        args = sys.argv[1:]
        session_override = None
        if '--session' in args:
            i = args.index('--session')
            if i + 1 >= len(args) or not args[i + 1].strip():
                raise TaskError('--session 缺少 Cookie Value')
            session_override = args[i + 1].strip()
            SECRETS.append(session_override)
            if os.getenv('TRAE_ACCOUNTS', '').strip() or os.getenv('TRAE_ACCESS_TOKEN') or os.getenv('TRAE_REFRESH_TOKEN'):
                raise TaskError('--session 不得与其他账号配置混用；请统一使用 TRAE_ACCOUNTS')
            del args[i:i + 2]
        if len(args) > 1:
            raise TaskError('用法：python candidate.py [checkin|credits|login]')
        task = (args[0] if args else os.getenv('TRAE_TASK', 'checkin')).strip().lower()
        if task not in ('checkin', 'credits', 'login'):
            raise TaskError('任务动作只能为 checkin、credits 或 login')
        accounts = [{'_index': 1, '_key': 'login'}] if task == 'login' else parse_accounts(session_override)
        account_count = len(accounts)
        log('账号数量：%d' % account_count)
        log('任务动作：' + {'checkin': '每日签到与余额', 'credits': '只查积分余额', 'login': '显式交互登录'}[task])
        peak = datetime.datetime.now(BJ).hour in parse_hours(os.getenv('TRAE_PEAK_HOURS', '0'))
        options = {'cooldown': integer_env('TRAE_PEAK_COOLDOWN_MIN' if peak else 'TRAE_COOLDOWN_MIN', 12 if peak else 55, 1, 1440),
                   'tries': integer_env('CLAIM_TRIES', 1, 1, 5), 'seen': {}}
        raw_batch = os.getenv('TRAE_BATCH', 'all').strip().lower()
        size = len(accounts) if raw_batch in ('', 'all', '0') else integer_env('TRAE_BATCH', len(accounts), 1, 9999)
        cache_path = Path(os.getenv('TRAE_TOKEN_CACHE') or str(Path(__file__).parent / '.trae_token_cache.json'))
        state_path = Path(os.getenv('TRAE_STATE_FILE') or str(Path(__file__).parent / '.trae_checkin_state.json'))
        # 预演完全不接触缓存和凭据文件。
        cache = {} if DRY or task == 'login' else read_json(cache_path)
        state = {} if DRY or task == 'login' else read_json(state_path)
        date = stamp()[:10]
        if state.get('date') != date:
            state = {'date': date, 'done': {}, 'cooldown': {}}
        if not isinstance(state.get('done'), dict) or not isinstance(state.get('cooldown'), dict):
            raise TaskError('当天状态文件结构错误')
        pending = [a for a in accounts if state['done'].get(a['_key']) is not True]
        if not DRY and task == 'checkin' and not peak and size < len(pending):
            offset = datetime.datetime.now(BJ).hour % len(pending)
            selected = {a['_index'] for a in (pending[offset:] + pending[:offset])[:size]}
        else:
            selected = {a['_index'] for a in accounts}
        if not DRY and task == 'checkin' and os.getenv('TRAE_JITTER', '1').lower() not in DISABLED:
            wait = random.randint(0, integer_env('TRAE_JITTER_MAX', 20, 0, 86400))
            log('启动错峰等待 %d 秒' % wait)
            time.sleep(wait)
        circuit = False
        previous_claimed = False
        for acc in accounts:
            run = AccountRun(acc['_index'])
            log('---------- 账号%d ----------' % acc['_index'])
            try:
                if task == 'login':
                    status = run_login(run)
                elif circuit or (acc['_index'] not in selected and state['done'].get(acc['_key']) is not True):
                    run.counts['skipped'] += 1
                    status = 'skipped'
                    log('⏭️ 显式轮签或熔断设置：本轮未处理，该账号尚未核验成功')
                else:
                    if previous_claimed and not DRY:
                        gap = random.randint(12, 25)
                        log('账号间错峰等待 %d 秒' % gap)
                        time.sleep(gap)
                    status = run_account(acc, run, task, cache, cache_path, state, state_path, options)
            except TaskError as error:
                status = 'failure'
                if run.counts['failure'] == 0:
                    run.counts['failure'] += 1
                log('❌ 账号%d：%s' % (acc['_index'], error))
            except Exception:
                status = 'failure'
                if run.counts['failure'] == 0:
                    run.counts['failure'] += 1
                log('❌ 账号%d：处理异常（详情已脱敏）' % acc['_index'])
            elapsed = round(time.monotonic() - run.started, 2)
            results.append({'account': acc['_index'], 'status': status, 'tasks': run.counts, 'elapsedSeconds': elapsed, 'duplicateOf': acc.get('_duplicateOf'), 'credentialError': bool(acc.get('_credentialError'))})
            log('账号%d统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒' %
                (acc['_index'], sum(run.counts.values()), run.counts['success'], run.counts['alreadyComplete'],
                 run.counts['skipped'], run.counts['failure'], elapsed))
            previous_claimed = run.claimed
            if not DRY and os.getenv('TRAE_CIRCUIT', '0') == '1' and state['cooldown'].get(acc['_key'], 0) > time.time():
                circuit = True
    except TaskError as error:
        config_error = True
        log('账号数量：%d（配置核验未完成）' % account_count)
        log('❌ 配置错误：' + str(error))
    except Exception:
        config_error = True
        log('账号数量：%d（初始化未完成）' % account_count)
        log('❌ 初始化异常（详情已脱敏）')
    good = sum(r['status'] in ('success', 'already-complete', 'dry-run') for r in results)
    skipped = sum(r['status'] == 'skipped' for r in results)
    failed = sum(r['status'] == 'failure' for r in results)
    duplicates = sum(r.get('duplicateOf') is not None for r in results)
    credential_errors = sum(bool(r.get('credentialError')) for r in results)
    exit_code = 1 if config_error or failed or skipped or good != account_count else 0
    final_status = 'configuration-error' if config_error else ('partial-failure' if exit_code and good else 'failure' if exit_code else 'dry-run' if DRY else 'success')
    body = 'Trae 任务：%s；账号总数 %d，成功 %d，失败 %d，跳过 %d。' % (final_status, account_count, good, failed, skipped)
    body += '其中重复配置 %d，需更新凭据 %d。' % (duplicates, credential_errors)
    if config_error:
        body += '配置核验失败。'
    log('通知摘要：' + body)
    notify_status = notification(body)
    direct_push(body)
    task_counts = {key: sum(r['tasks'][key] for r in results) for key in ('success', 'alreadyComplete', 'skipped', 'failure')}
    finished = stamp()
    elapsed = round(time.monotonic() - started, 2)
    log('----------------------------------------')
    log('任务统计：账号总数 %d，成功 %d，失败 %d，跳过 %d；总耗时 %.2f 秒' % (account_count, good, failed, skipped, elapsed))
    log('重复配置统计：%d（已独立核验，不算作新增领取）' % duplicates)
    log('需更新凭据账号：%d' % credential_errors)
    log('子任务统计：' + json.dumps(task_counts, ensure_ascii=False))
    log('通知状态：' + notify_status)
    log('完成时间：' + finished + '；最终状态：' + final_status)
    summary = {'applicationKey': 'trae', 'mode': 'dry-run' if DRY else 'live', 'status': final_status,
               'accountCount': account_count, 'success': good, 'failure': failed, 'skipped': skipped,
               'configurationError': config_error, 'duplicateAccounts': duplicates, 'credentialErrors': credential_errors, 'accounts': results, 'tasks': task_counts,
               'startTime': start_time, 'finishTime': finished, 'elapsedSeconds': elapsed,
               'notification': notify_status, 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
