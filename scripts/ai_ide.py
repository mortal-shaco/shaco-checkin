#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AI IDE 每日签到
# cron: 0 11 * * *
# SPDX-License-Identifier: MIT
# Upstream: LiSeafood/ai-ide-checkin (MIT)
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""WorkBuddy、Trae CN、Qoder 每日签到（上游既有任务集合）。
来源: LiSeafood/ai-ide-checkin/checkin.py，MIT；保留 trae-mate 的设备头算法署名。
仅使用标准库，直接实现 HTTP；不扫描客户端，不导出凭据，不调用设备程序。

AI_IDE_ACCOUNTS: 每个非空行一个 JSON 对象：service 为 workbuddy/trae/qoder，
token 为相应官方客户端请求头中的 Bearer 或 Cloud-IDE-JWT 后的值。
Trae 还需 uid（同账号 userId），region 默认 CN。Qoder 需 machine_id 和
 device 对象（machineToken、machineCode、machineType），从同账号官方签到
请求的 Cosy-* 请求头复制，不由本脚本生成设备证明。
可选 excluded=true 停领，channel 为本地渠道标签，不发送给服务端。
传统 WORKBUDDY_ACCESS_TOKEN、WORKBUDDY_UID、TRAE_TOKEN、TRAE_USER_ID、
TRAE_REGION 保持兼容，每行一个 token；配套 uid 也逐行对应。
使用 --no-trae / --no-qoder 保留原跳过方式；--services 可明确选择产品。
无凭据产品不运行；已配置账号失败使整体非零退出，空配置也失败。

默认只签到。需要续期时显式设 CHECKIN_REFRESH=1、CHECKIN_STATE_FILE 为
自行管理的凭据缓存路径，并提供 refresh_token；脚本以 0600 保存轮换结果。
缓存不得与客户端登录态共用；优先使用缓存中的新令牌。WorkBuddy 无公开续期协议，
到期需在客户端重新登录并更新环境变量。TRAE 24 小时、Qoder 72 小时内续期。
缓存为本脚本可选状态，不依赖任何预装应用。--export 禁用以避免凭据泄漏；
停领和渠道请直接修改账号 JSON。CHECKIN_DRY_RUN=1 完全断网且不读写缓存。
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
        _ql_notify_identities = ('81e41cede93b9ced', 'scripts/ai_ide.py', 'ai_ide.py', 'ai_ide')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import contextlib
import fnmatch
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import re
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = 'AI IDE 每日签到'
CATALOG = '81e41cede93b9ced'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
DRY = os.environ.get('CHECKIN_DRY_RUN', '').lower() in TRUE
TRAE_BASE = 'https://api.trae.cn'
QODER_BASE = 'https://openapi.qoder.com.cn'
TRAE_CLIENT_ID = 'en1oxy7wnw8j9n'

class Failure(Exception):
    pass


def log(text):
    print(f'[{time.strftime("%H:%M:%S")}] {text}', flush=True)


def positive(name, default, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
        if not 1 <= value <= maximum:
            raise ValueError
        return value
    except ValueError:
        raise Failure(f'{name} 必须为 1 至 {maximum} 的整数') from None


def jwt(token):
    try:
        part = token.split('.')[1]
        data = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def expiry(acc):
    value = jwt(acc['token']).get('exp')
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    try:
        from datetime import datetime
        return datetime.fromisoformat(acc.get('expires_at', '').replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError):
        return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 防止认证头被重定向到其他主机


def request(url, headers, payload=None, attempts=1):
    if DRY:
        raise Failure('预演禁止网络调用')
    allowed = {'www.codebuddy.cn', 'api.trae.cn', 'api.trae.com.cn', 'openapi.qoder.com.cn'}
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed:
        raise Failure('拒绝非官方 HTTPS 接口')
    timeout = positive('CHECKIN_HTTP_TIMEOUT', 30, 120)
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(1, attempts + 1):
        h = dict(headers)
        h['Accept-Encoding'] = 'identity'
        data = None
        if payload is not None:
            h['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=h, method='POST' if data is not None else 'GET')
        try:
            with opener.open(req, timeout=timeout) as response:
                status = response.status
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise Failure('接口响应超过大小限制')
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise Failure('接口响应结构异常')
            transient = body.get('code') in (9074, 9004, '9074', '9004')
            if not transient:
                if status != 200:
                    raise Failure(f'HTTP {status}')
                show_identity(body)
                return body
        except urllib.error.HTTPError as exc:
            transient = exc.code in (429, 500, 502, 503, 504)
            if not transient:
                raise Failure(f'HTTP {exc.code}，请检查凭据及接口权限') from None
        except (OSError, ValueError):
            transient = True
        if attempt == attempts:
            raise Failure('网络、响应解析或服务限流失败，重试已耗尽')
        low = positive('CHECKIN_RETRY_WAIT_MIN', 15, 300)
        high = positive('CHECKIN_RETRY_WAIT_MAX', 30, 300)
        if low > high:
            raise Failure('重试等待下限不能超过上限')
        log(f'⚠️ 请求暂未成功，重试 {attempt}/{attempts}（不输出响应）')
        time.sleep(random.randint(low, high))
    raise Failure('请求未完成')


def show_identity(body):
    # 只读取官方响应明确的公开身份，不把 token 内声明当作已认证身份。
    nodes = [(body, False)]
    for key in ('data', 'user', 'user_info', 'Result'):
        if isinstance(body.get(key), dict):
            nodes.append((body[key], key in ('user', 'user_info')))
    for node, _ in list(nodes):
        if isinstance(node.get('user'), dict):
            nodes.append((node['user'], True))
    for node, is_user in nodes:
        fields = ('nickname', 'username', 'display_name', 'displayName', 'public_uid', 'uid')
        if is_user:
            fields += ('name', 'id')
        for key in fields:
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value):
                # 名称字段可能被服务端填入手机号；公开 UID 不按电话处理。
                if key not in ('uid', 'id', 'public_uid') and re.search(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', str(value)):
                    continue
                log(f'官方账号身份 {key}: {json.dumps(value, ensure_ascii=False)}')
                return


def business_ok(body):
    return (type(body.get('code')) in (int, str) and body['code'] in (0, 200, '0', '200')
            or body.get('success') is True or body.get('status') == 'success')


def already(body):
    return '已签到' in str(body.get('message') or body.get('msg') or '')


def state_envelope_ok(body):
    """允许上游无信封的状态对象，但不覆盖任何显式业务错误。"""
    return (('code' not in body or business_ok(body))
            and body.get('success') is not False and body.get('status') not in ('error', 'failed'))


def _seeded_stream(seed: str, salt: str, nbytes: int) -> bytes:
    """确定性字节流: SHA256(f"{salt}:{seed}" || counter_be32) 连续拼接。"""
    data = f"{salt}:{seed}".encode("utf-8")
    out = b""
    i = 0
    while len(out) < nbytes:
        out += hashlib.sha256(data + struct.pack(">I", i)).digest()
        i += 1
    return out[:nbytes]


def _trae_device_digits(n: int, seed: str) -> str:
    return "".join(str(b % 10) for b in _seeded_stream(seed, "devid", n + 1)[:n])


def _trae_device_hex(n: int, seed: str) -> str:
    return _seeded_stream(seed, "sess", (n + 1) // 2).hex()[:n]


def _trae_market_uuid(seed: str) -> str:
    bs = bytearray(_seeded_stream(seed, "market", 16))
    bs[6] = (bs[6] & 0x0F) | 0x40   # UUID v4 版本位
    bs[8] = (bs[8] & 0x3F) | 0x80   # RFC 4122 variant 位
    h = bs.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def trae_device_identity(user_id: str) -> dict:
    """按 user_id 确定性派生一套稳定的伪设备身份(trae-mate gen 2 算法)。

    同一 user_id 永远得到同一套标识,服务端按设备维度记账也保持稳定。
    测试向量(user_id="1234567890123456"): device_id=413174708280782,
    session_id=fbabf7aa1e173b90385c623e1ec49157860cc07a4b01f53f7ca141b17d876eae,
    market_user_id=746608f9-7f37-4960-b4c7-8553cec6d366。
    """
    return {
        "device_id": _trae_device_digits(15, user_id),
        "market_user_id": _trae_market_uuid(user_id),
        "session_id": _trae_device_hex(64, user_id),
    }


def build_trae_headers(token: str, user_id: str) -> dict:
    """Trae 签到接口的完整请求头(逆向自 trae-mate checkin.rs)。

    旧版只带 x-device-id 等零星头,领取接口常返回 9074 限流;
    完整的客户端伪装头 + 稳定伪设备身份是稳定领取的关键。
    x-request-id / x-tt-trace-id 每次请求刷新。
    """
    dev = trae_device_identity(user_id or "")
    return {
        "authorization": f"Cloud-IDE-JWT {token}",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate",
        "accept-language": "zh-CN",
        "content-type": "application/json",
        "user-agent": "VSCode 1.107.1 (TRAE SOLO CN)",
        "x-market-client-id": "VSCode 1.107.1",
        "x-market-user-id": dev["market_user_id"],
        "x-user-region": "CN",
        "x-device-id": dev["device_id"],
        "x-lgw-req-sdk-type": "3",
        "package-type": "stable_cn",
        "x-lscbd-aid": "787976",
        "x-lscbd-platform": "windows",
        "app-version": "0.1.45",
        "x-tt-trace-id": "00-" + uuid.uuid4().hex[:16] + "-01",
        "vscode-sessionid": dev["session_id"],
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "none",
        "x-request-id": str(uuid.uuid4()),
    }



def headers(acc):
    if acc['service'] == 'trae':
        h = build_trae_headers(acc['token'], acc['uid'])
        h['x-user-region'] = acc.get('region', 'CN')
        return h
    h = {'Authorization': 'Bearer ' + acc['token'], 'Accept': 'application/json'}
    if acc['service'] == 'qoder':
        h.update({'User-Agent': 'Qoder/claim', 'Cosy-ClientType': '10',
                  'Cosy-MachineOS': 'x86_64_windows', 'Cosy-MachineHostname': 'pc',
                  'Cosy-MachineId': acc['machine_id']})
        for key in ('machineToken', 'machineCode', 'machineType'):
            h['Cosy-' + key[0].upper() + key[1:]] = acc['device'][key]
    return h


def credits(acc):
    try:
        body = request(TRAE_BASE + '/trae/api/v2/pay/ide_user_ent_usage', headers(acc),
                       {'require_usage': True, 'req_source': 2})
        packs = body.get('user_entitlement_pack_list')
        if not isinstance(packs, list):
            raise Failure('积分列表未返回')
        total, expires = 0.0, []
        for pack in packs:
            limit = pack.get('entitlement_base_info', {}).get('quota', {}).get('credits_limit')
            if limit is None:
                continue
            total += max(0, float(limit) - float(pack.get('usage', {}).get('credits_amount') or 0))
            exp = pack.get('expire_time')
            if isinstance(exp, (int, float)) and exp > time.time():
                expires.append(exp)
        suffix = '，最早到期 ' + time.strftime('%Y-%m-%d', time.localtime(min(expires))) if expires else ''
        log(f'剩余积分 {total:g}{suffix}')
    except Exception:
        log('⚠️ 可选积分查询未完成，不改变已验证签到结果')


def checkin(acc):
    service = acc['service']
    h = headers(acc)
    retry = positive('CHECKIN_MAX_RETRY', 14, 20)
    if service == 'workbuddy':
        base = 'https://www.codebuddy.cn/v2/billing/meter/'
        body = request(base + 'checkin-status', h, {}, retry)
        if not state_envelope_ok(body) or not isinstance(body.get('data'), dict):
            raise Failure('签到状态业务校验失败')
        if body['data'].get('today_checked_in') is True:
            return 'already'
        if body['data'].get('today_checked_in') is not False:
            raise Failure('签到状态字段缺失或无效')
        body = request(base + 'daily-checkin', h, {}, retry)
        if body.get('code') in (10001, '10001') or already(body):
            return 'already'
        if type(body.get('code')) is int and body['code'] == 0:
            log('✅ WorkBuddy 签到领取成功')
            return 'success'
        raise Failure('领取签到业务校验失败')
    if service == 'trae':
        base = TRAE_BASE + '/trae/api/v2/ug/checkin_credits/'
        body = request(base + 'status', h, {}, 3)
        if not state_envelope_ok(body):
            raise Failure('Trae 状态接口返回业务错误')
        if body.get('checked_in') is True:
            credits(acc)
            return 'already'
        if body.get('enable') is False:
            log('⏭️ 官方确认签到活动未开启')
            return 'skipped'
        # 未获得明确可签到状态时失败闭合，不盲目发起领取。
        if body.get('checked_in') is not False and not business_ok(body):
            raise Failure('签到状态无法确认')
        body = request(base + 'claim', h, {}, positive('CHECKIN_TRAE_MAX_RETRY', 4, 20))
        if business_ok(body) or already(body):
            credits(acc)
            return 'already' if already(body) else 'success'
        raise Failure('Trae 领取业务校验失败')
    body = request(QODER_BASE + '/sash/api/v1/me/campaigns', h, attempts=3)
    if not state_envelope_ok(body):
        raise Failure('Qoder 活动接口返回业务错误')
    campaigns = body.get('campaigns')
    if not isinstance(campaigns, list):
        raise Failure('Qoder 活动列表无效')
    benefits = [c for c in campaigns if isinstance(c, dict) and c.get('actionType') == 'CLAIM_BENEFIT'
                and isinstance(c.get('benefit'), dict) and c['benefit'].get('kind') == 'CREDITS']
    claimable = [c for c in benefits if c.get('claimStatus') == 'CLAIMABLE']
    if not claimable:
        if any(c.get('claimStatus') == 'CLAIMED' for c in benefits):
            return 'already'
        raise Failure('官方未下发可领取的积分签到活动')
    failures = 0
    for number, campaign in enumerate(claimable, 1):
        try:
            cid = campaign.get('campaignId')
            if not isinstance(cid, (str, int)) or not str(cid):
                raise Failure('活动编号缺失')
            path = '/sash/api/v1/me/campaigns/' + urllib.parse.quote(str(cid), safe='') + '/claim'
            result = request(QODER_BASE + path, h, {})
            data = result.get('data', result)
            if not isinstance(data, dict) or not (data.get('status') == 'CLAIMED' or data.get('replayed') is True):
                raise Failure('领取结果未确认')
            log(f'✅ 积分活动 {number}/{len(claimable)} 已确认领取')
        except Failure:
            failures += 1
            log(f'❌ 积分活动 {number}/{len(claimable)} 未完成')
    if failures:
        raise Failure(f'积分活动部分失败 {failures}/{len(claimable)}')
    return 'success'


def cache_key(acc):
    # 不记录凭据，配置 token 变化后自动重新导入，避免沿用旧账号缓存。
    return hashlib.sha256((acc['service'] + '\0' + acc['token']).encode()).hexdigest()


def save_cache(path, cache):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.checkin-', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(cache, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def refresh(acc, cache, key, state_path, force=False):
    if acc['service'] == 'workbuddy' or not acc.get('refresh_token'):
        return
    limit = 86400 if acc['service'] == 'trae' else 3 * 86400
    exp = expiry(acc)
    if not force and exp and exp - time.time() > limit:
        return
    if os.environ.get('CHECKIN_REFRESH', '').lower() not in TRUE:
        log('⏭️ 续期未启用，保持当前令牌')
        return
    if not state_path:
        raise Failure('续期必须指定 CHECKIN_STATE_FILE 保存轮换凭据')
    # 先验证缓存可安全保存，避免成功换新后才发现目录不可写。
    save_cache(state_path, cache)
    if acc['service'] == 'trae':
        body = request('https://api.trae.com.cn/cloudide/api/v3/trae/oauth/ExchangeToken',
                       {'Accept': 'application/json'}, {'ClientID': TRAE_CLIENT_ID,
                       'RefreshToken': acc['refresh_token'], 'ClientSecret': '-', 'UserID': ''})
        result, data = body.get('Result') or {}, body.get('data') or {}
        tok = result.get('Token') or data.get('access_token') or data.get('token')
        rt = result.get('RefreshToken') or data.get('refresh_token') or acc['refresh_token']
        new_uid = str((jwt(tok or '').get('data') or {}).get('id') or '')
        if new_uid and new_uid != acc['uid']:
            raise Failure('续期账号不一致')
    else:
        h = headers(acc)
        h.pop('Authorization', None)
        body = request(QODER_BASE + '/api/v1/deviceToken/refresh', h, {'refresh_token': acc['refresh_token']})
        data = body.get('data', body)
        tok = data.get('device_token') or data.get('token') or data.get('accessToken') or data.get('access_token')
        rt = data.get('refresh_token') or data.get('refreshToken') or acc['refresh_token']
        acc['expires_at'] = data.get('expires_at') or data.get('expiresAt') or ''
    if not isinstance(tok, str) or not tok or not isinstance(rt, str):
        raise Failure('续期响应未返回有效令牌')
    acc.update(token=tok, refresh_token=rt)
    cache[key] = {k: acc[k] for k in ('token', 'refresh_token', 'expires_at') if k in acc}
    save_cache(state_path, cache)
    log('✅ 续期完成并安全保存，不写入客户端文件')


def parse_account(line):
    acc = json.loads(line)
    if not isinstance(acc, dict):
        raise Failure('账号必须为 JSON 对象')
    if acc.get('service') not in ('workbuddy', 'trae', 'qoder'):
        raise Failure('账号 service 无效')
    if not isinstance(acc.get('token'), str) or not acc['token'].strip():
        raise Failure('账号 token 缺失')
    for key in ('token', 'uid', 'region', 'machine_id', 'refresh_token'):
        if key in acc and (not isinstance(acc[key], str) or any(c in acc[key] for c in '\r\n\x00')):
            raise Failure('账号字段类型或字符无效')
    if acc['service'] == 'trae':
        acc.setdefault('region', 'CN')
        acc.setdefault('uid', str((jwt(acc['token']).get('data') or {}).get('id') or ''))
        if not acc['uid']:
            raise Failure('Trae 需要同账号 uid')
    if acc['service'] == 'qoder':
        if not acc.get('machine_id') or not isinstance(acc.get('device'), dict):
            raise Failure('Qoder 需要同账号设备请求头字段')
        for key in ('machineToken', 'machineCode', 'machineType'):
            value = acc['device'].get(key)
            if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00'):
                raise Failure('Qoder 设备请求头字段缺失或无效')
    if 'excluded' in acc and not isinstance(acc['excluded'], bool):
        raise Failure('excluded 必须为布尔值')
    return acc


def account_lines():
    lines = [s.strip() for s in os.environ.get('AI_IDE_ACCOUNTS', '').splitlines() if s.strip()]
    if lines:
        return lines
    for service, token_env, uid_env in (
        ('workbuddy', 'WORKBUDDY_ACCESS_TOKEN', 'WORKBUDDY_UID'),
        ('trae', 'TRAE_TOKEN', 'TRAE_USER_ID')):
        tokens = [s.strip() for s in os.environ.get(token_env, '').splitlines() if s.strip()]
        uids = os.environ.get(uid_env, '').splitlines()
        if uids and len(uids) != len(tokens):
            raise Failure(f'{uid_env} 行数须与令牌一致')
        for index, token in enumerate(tokens):
            acc = {'service': service, 'token': token}
            if uids:
                acc['uid'] = uids[index].strip()
            if service == 'trae':
                acc['region'] = os.environ.get('TRAE_REGION', 'CN')
            lines.append(json.dumps(acc))
    return lines


def notify_summary(summary):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    selectors = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    names = [CATALOG, Path(__file__).name, 'scripts/' + Path(__file__).name]
    selected = selectors is not None and any(fnmatch.fnmatch(n, p) for p in re.split(r'[,;\s]+', selectors) if p for n in names)
    enabled = switch in TRUE or (switch == 'auto' and selected)
    if switch in FALSE or not enabled:
        return '已按全局开关或脚本选择策略关闭'
    if DRY:
        return '预演已生成通知摘要，断网模式不调用通知通道'
    text = (f"模式：{summary['mode']}；账号总数 {summary['accounts']}，成功 {summary['success']}，"
            f"失败 {summary['failed']}，跳过 {summary['skipped']}；状态 {summary['status']}")
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend((Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                from notify import send
            except ImportError:
                path = next((p for p in paths if p.is_file()), None)
                if path is None:
                    return '通知模块不可用，保留业务退出码'
                spec = importlib.util.spec_from_file_location('_qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                send = module.send
            send(TITLE, text)
        return '通知已提交'
    except Exception:
        return '通知失败，保留业务退出码'


def main():
    start = time.monotonic()
    log('=' * 50)
    log(TITLE + ' | 开始时间 ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('模式：' + ('断网预演' if DRY else '正式执行'))
    summary = {'mode': 'dry-run' if DRY else 'live', 'accounts': 0, 'success': 0,
               'failed': 0, 'skipped': 0, 'already': 0, 'results': []}
    configuration_error = False
    try:
        args = sys.argv[1:]
        allowed = {'--no-trae', '--no-qoder', '--help', '-h'}
        services = {'workbuddy', 'trae', 'qoder'}
        for arg in args:
            if arg.startswith('--services='):
                services = set(arg.split('=', 1)[1].split(','))
                if not services or not services <= {'workbuddy', 'trae', 'qoder'}:
                    raise Failure('services 参数无效')
            elif arg not in allowed:
                raise Failure('不支持该参数；停领及渠道用账号 JSON 设置，凭据导出已禁用')
        if '--no-trae' in args:
            services.discard('trae')
        if '--no-qoder' in args:
            services.discard('qoder')
        if '--help' in args or '-h' in args:
            print(__doc__)
            return 0
        if os.environ.get('WORKBUDDY_DOMAIN', 'www.codebuddy.cn') != 'www.codebuddy.cn':
            raise Failure('WORKBUDDY_DOMAIN 仅允许官方 www.codebuddy.cn，防止凭据外发')
        for name, default, maximum in [('CHECKIN_MAX_RETRY', 14, 20), ('CHECKIN_TRAE_MAX_RETRY', 4, 20),
                                       ('CHECKIN_HTTP_TIMEOUT', 30, 120), ('CHECKIN_RETRY_WAIT_MIN', 15, 300),
                                       ('CHECKIN_RETRY_WAIT_MAX', 30, 300)]:
            positive(name, default, maximum)
        if positive('CHECKIN_RETRY_WAIT_MIN', 15, 300) > positive('CHECKIN_RETRY_WAIT_MAX', 30, 300):
            raise Failure('重试等待下限不能超过上限')
        lines = account_lines()
        summary['accounts'] = len(lines)
        log(f'账号数量：{len(lines)}')
        if not lines:
            raise Failure('未配置 AI_IDE_ACCOUNTS 或兼容令牌变量')
        cache, state_path = {}, os.environ.get('CHECKIN_STATE_FILE', '')
        if not DRY and state_path and Path(state_path).exists():
            if Path(state_path).stat().st_mode & 0o077:
                raise Failure('凭据缓存权限须为 0600')
            cache = json.loads(Path(state_path).read_text())
            if not isinstance(cache, dict):
                raise Failure('凭据缓存格式无效')
        for index, line in enumerate(lines, 1):
            began = time.monotonic()
            result = 'failed'
            stage_start = time.monotonic()
            log(f'账号 {index} | 阶段 1：参数校验')
            try:
                acc = parse_account(line)
                key = cache_key(acc)
                if not DRY and key in cache:
                    acc.update(cache[key])
                    acc = parse_account(json.dumps(acc))
                log(f'账号 {index} | 阶段 1 完成，耗时 {time.monotonic()-stage_start:.2f} 秒')
                if acc.get('excluded') or acc['service'] not in services:
                    result = 'skipped'
                    log(f'⏭️ 账号 {index} 已停领或产品未选择')
                elif DRY:
                    result = 'success'
                    log(f'账号 {index} | 阶段 2：{acc["service"]} 续期策略预演，无读写')
                    log(f'账号 {index} | 阶段 3：签到状态、领取、积分检查预演，无网络')
                    log('DRY_RUN_OK：仅参数与执行计划通过，不代表真实业务成功')
                else:
                    stage_start = time.monotonic()
                    log(f'账号 {index} | 阶段 2：令牌有效期及可选续期')
                    refresh(acc, cache, key, state_path)
                    exp = expiry(acc)
                    if exp:
                        log(f'令牌剩余天数 {(exp-time.time())/86400:.1f}')
                        if exp <= time.time():
                            raise Failure('令牌已过期，需重新登录或配置续期')
                    log(f'阶段 2 完成，耗时 {time.monotonic()-stage_start:.2f} 秒')
                    stage_start = time.monotonic()
                    log(f'账号 {index} | 阶段 3：{acc["service"]} 查询及签到')
                    result = checkin(acc)
                    log(f'阶段 3 完成，耗时 {time.monotonic()-stage_start:.2f} 秒')
                    log('☑️ 今日已签到' if result == 'already' else '✅ 账号执行完成')
            except Failure as exc:
                log('❌ ' + str(exc))  # Failure 仅包含脚本自有固定描述，无服务器原文
            except Exception:
                log('❌ 配置格式、缓存或执行异常，不输出敏感详情')
            summary['results'].append({'account': index, 'status': result})
            if result in ('success', 'already'):
                summary['success'] += 1
                summary['already'] += int(result == 'already')
            else:
                summary[result] += 1
            log(f'账号 {index} 统计：任务 1，成功 {int(result=="success")}，已完成 {int(result=="already")}，'
                f'跳过 {int(result=="skipped")}，失败 {int(result=="failed")}，耗时 {time.monotonic()-began:.2f} 秒')
    except Failure as exc:
        configuration_error = True
        log('❌ 配置错误：' + str(exc))
    except Exception:
        configuration_error = True
        log('❌ 配置或缓存读取失败，不输出敏感详情')
    code = 1 if configuration_error or summary['failed'] else 0
    summary['status'] = ('configuration-error' if configuration_error else
                         'partial-failure' if summary['failed'] and summary['success'] else
                         'failure' if summary['failed'] else 'dry-run' if DRY else 'success')
    summary['elapsedSeconds'] = round(time.monotonic() - start, 3)
    summary['notification'] = notify_summary(summary)
    log('-' * 50)
    log(f'账号总数 {summary["accounts"]}，成功 {summary["success"]}，失败 {summary["failed"]}，跳过 {summary["skipped"]}')
    log(f'子任务统计：总数 {len(summary["results"])}，已完成 {summary["already"]}；总耗时 {summary["elapsedSeconds"]} 秒')
    log('通知状态：' + summary['notification'])
    log('结束时间 ' + time.strftime('%Y-%m-%d %H:%M:%S') + ' | 最终状态 ' + summary['status'])
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
