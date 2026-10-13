#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Trae Work 签到
# cron: 0 8,20 * * *
# MIT License; derived from xz0609/trae-work-checkin-ql/trae_work_checkin.py
# MIT License (effectiveLicense from task.json; original attribution retained above)
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
# Upstream commit: 54ce4564ae714d9aa3140defa06308acce12942e
# 设备指纹接口说明原作者引用 rockswang/workbuddy-wild。
"""
Trae Work（字节，trae.cn 国内版）每日积分自动签到，单文件，Python 标准库。
免责声明：本脚本为第三方逆向脚本，与官方无关，接口随时可能失效，仅供个人学习研究。

默认/checkin：刷新凭据 -> 查询状态 -> 领取 -> 查询积分；status：仅查询状态和积分。
TRAE_ACCOUNTS：每个非空行一个 JSON 对象，包含 accessToken、claimDeviceId（兼容
 deviceId）、fingerprint（brand/type/os）；可选 refreshToken、expiresAt（秒或毫秒）、
 userId、screenName。登录本人官方国内版客户端，在本人授权请求中取得
 Authorization 的 Cloud-IDE-JWT 后的值和 x-device-id/x-device-brand/x-device-type/
 x-os-version；刷新凭据来自本人 OAuth 登录，不能用随机设备替代真实注册设备。
 多账号使用不同的真实注册设备；禁止把 & 或 @ 当作账号分隔符。
旧版 auths/auth-*.json 在没有 TRAE_ACCOUNTS 时兼容读取，运行不要求这些文件。
TRAE_DRY_RUN=1 完全断网，不刷新、不领取、不延时、不写文件、不执行通知模块。
RANDOM_SIGNIN 默认 true，MAX_RANDOM_DELAY 默认 3600 秒，保留上游随机延时。
TRAE_SAVE_CREDENTIALS=1 才允许签到后保存刷新凭据（默认禁止写入）。
login：显式交互登录，尝试打开官方授权页；可用保密输入粘贴本人回调 URL。
登录成功仅以权限 0600 保存 auths/auth-*.json，不打印凭据；登录后需补入本人
真实 claimDeviceId 与 fingerprint。未配置真实设备时不能执行签到。
QINGLONG_NOTIFY 默认 1；通知失败不改变业务退出码；断网预演只模拟通知。
"""
import base64
import getpass
import importlib.util
import json
import math
import os
import random
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BASE = 'https://api.trae.cn'
AUTH_BASE = 'https://api.trae.com.cn'
CLIENT_ID = 'en1oxy7wnw8j9n'
IDE_VERSION = '0.1.52'
AUTH_DIR = Path(__file__).resolve().parent / 'auths'
TITLE = 'Trae Work 签到'
DISABLED = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in DISABLED | {''}


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 禁止重定向转发 Authorization 到其他站点。
        return None


def http_request(method, url, headers, body=None, timeout=30):
    if enabled('TRAE_DRY_RUN'):
        raise TaskError('断网预演禁止 HTTP 请求')
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise TaskError('仅允许 HTTPS 请求')
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as resp:
            raw = resp.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超过大小上限')
            result = json.loads(raw.decode('utf-8'))
            if not isinstance(result, dict):
                raise TaskError('响应结构不符合契约')
            return result
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 请求失败，状态码 {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON 对象') from None


def payload(token):
    try:
        part = token.split('.')[1]
        value = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def object_data(r):
    data = r.get('data') or r.get('Result') or {}
    return data if isinstance(data, dict) else {}


def code_of(r):
    value = r.get('code', r.get('Code'))
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def business_ok(r):
    code = code_of(r)
    if code is not None and code not in (0, 200):
        return False
    if r.get('success') is False or object_data(r).get('success') is False:
        return False
    return code in (0, 200) or r.get('success') is True or object_data(r).get('success') is True


def claim_outcome(r):
    code = code_of(r)
    # 9074 指纹/限流和 9095 设备占用不能证明本账号已领取。
    if code in (9074, 9095, 1001):
        raise TaskError(f'领取失败，业务码 {code}；请检查凭据及账号绑定设备')
    if business_ok(r):
        return 'success'
    msg = r.get('message') or r.get('Message') or ''
    # 仅解析业务消息，不扫描或打印整个响应；排除否定语义。
    if isinstance(msg, str) and not any(x in msg.lower() for x in ('not ', '未', '失败', 'error')):
        if any(x in msg.lower() for x in ('已签到', '已领取', 'already checked in', 'already claimed')):
            return 'alreadyComplete'
    raise TaskError('领取响应未能明确证明成功')


def finite_number(value):
    if isinstance(value, bool):
        raise TaskError('积分字段类型错误')
    try:
        v = float(value)
    except (ValueError, TypeError):
        raise TaskError('积分字段类型错误') from None
    if not math.isfinite(v):
        raise TaskError('积分字段不是有限数值')
    return v


def credits_text(r):
    if code_of(r) not in (None, 0, 200) or r.get('success') is False or object_data(r).get('success') is False:
        raise TaskError('积分查询业务失败')
    # 保留上游总额减消耗、权益包以及多种余额字段的解析链。
    roots = [r, object_data(r)]
    for root in roots:
        summary = root.get('usage_summary')
        if isinstance(summary, dict) and 'total_amount' in summary and 'consumed_amount' in summary:
            total = finite_number(summary['total_amount'])
            used = finite_number(summary['consumed_amount'])
            return f'当前积分: {total-used:g} (总额 {total:g} / 已用 {used:g})'
        packs = root.get('user_entitlement_pack_list')
        if isinstance(packs, list):
            balances = []
            for pk in packs:
                if not isinstance(pk, dict):
                    continue
                quota = (pk.get('entitlement_base_info') or {}).get('quota') or pk.get('quota') or {}
                if 'credits_limit' in quota:
                    balances.append(finite_number(quota['credits_limit']) - finite_number((pk.get('usage') or {}).get('credits_amount', 0)))
            if balances:
                return f'当前积分: {sum(balances):g}（权益包 {len(balances)} 个）'
        for key in ('credits', 'balance', 'totalCredits', 'workCredits'):
            if root.get(key) is not None:
                return f"当前积分: {finite_number(root[key]):g}"
    raise TaskError('积分响应缺少可验证的余额字段')


def validate(cred):
    if not isinstance(cred, dict):
        raise TaskError('账号行必须为 JSON 对象')
    for key in ('accessToken',):
        if not isinstance(cred.get(key), str) or not cred[key].strip():
            raise TaskError(f'缺少 {key}')
    device = cred.get('claimDeviceId') or cred.get('deviceId')
    fp = cred.get('fingerprint')
    if not isinstance(device, str) or not device.strip():
        raise TaskError('缺少本人真实注册设备标识')
    if not isinstance(fp, dict) or any(not isinstance(fp.get(k), str) or not fp[k].strip() for k in ('brand', 'type', 'os')):
        raise TaskError('缺少与设备匹配的 fingerprint.brand/type/os')
    values = [cred['accessToken'], device, *[fp[k] for k in ('brand', 'type', 'os')]]
    if any('\n' in v or '\r' in v for v in values):
        raise TaskError('凭据及请求头禁止包含换行')
    if cred.get('refreshToken') is not None and not isinstance(cred['refreshToken'], str):
        raise TaskError('refreshToken 必须为字符串')
    if cred.get('expiresAt') is not None:
        finite_number(cred['expiresAt'])
    return dict(cred)


def load_accounts():
    raw = os.getenv('TRAE_ACCOUNTS', '')
    if raw.strip():
        entries = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                entries.append(None)  # 一个坏账号不阻止其他账号。
        return entries
    entries = []
    for path in sorted(AUTH_DIR.glob('auth-*.json')):
        try:
            entries.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            entries.append(None)
    return entries


def save_cred(cred):
    AUTH_DIR.mkdir(mode=0o700, exist_ok=True)
    # 不以服务端 UID 构造路径，避免路径穿越；文件名不透露账户/设备标识。
    import hashlib
    key = str(cred.get('userId') or cred.get('claimDeviceId') or cred.get('deviceId') or 'login')
    path = AUTH_DIR / ('auth-' + hashlib.sha256(key.encode()).hexdigest()[:24] + '.json')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(cred, stream, ensure_ascii=False, indent=2)


class Trae:
    def __init__(self, cred):
        self.cred = cred

    def refresh(self):
        c = self.cred
        if not c.get('refreshToken'):
            raise TaskError('需要刷新，但缺少 refreshToken；请重新登录')
        response = http_request('POST', AUTH_BASE + '/cloudide/api/v3/trae/oauth/ExchangeToken',
                                {'Content-Type': 'application/json'}, {'ClientID': CLIENT_ID,
                                'RefreshToken': c['refreshToken'], 'ClientSecret': '-', 'UserID': c.get('userId', '')})
        result = object_data(response)
        if code_of(response) not in (None, 0, 200) or response.get('success') is False:
            raise TaskError('凭据刷新业务失败')
        token = result.get('Token') or result.get('AccessToken') or result.get('access_token')
        if not isinstance(token, str) or not token:
            raise TaskError('刷新响应未返回有效凭据')
        c['accessToken'] = token
        c['refreshToken'] = result.get('RefreshToken') or result.get('refresh_token') or c['refreshToken']
        expiry = result.get('TokenExpireAt') or result.get('expiresAt')
        c['expiresAt'] = finite_number(expiry) if expiry else time.time() + 3600
        validate(c)

    def request(self, endpoint):
        c = self.cred
        fp = c['fingerprint']
        headers = {'Content-Type': 'application/json', 'Authorization': 'Cloud-IDE-JWT ' + c['accessToken'],
                   'x-device-id': c.get('claimDeviceId') or c['deviceId'], 'X-User-Region': 'CN',
                   'x-device-brand': fp['brand'], 'x-device-type': fp['type'], 'x-os-version': fp['os'],
                   'x-app-version': IDE_VERSION, 'User-Agent': 'Trae/' + IDE_VERSION}
        r = http_request('POST', API_BASE + endpoint, headers, {})
        if code_of(r) == 1001:
            self.refresh()
            headers['Authorization'] = 'Cloud-IDE-JWT ' + c['accessToken']
            r = http_request('POST', API_BASE + endpoint, headers, {})
        return r

    def identity(self, r):
        # 只展示官方响应中明确身份字段，不展示配置里的任意文本。
        for root in (object_data(r), r):
            for key in ('screenName', 'ScreenName', 'screen_name', 'nickname', 'username', 'displayName', 'userId', 'UserID'):
                v = root.get(key)
                if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v):
                    log(f'官方账号身份：{v}')
                    return


def notification(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        log('通知：断网预演，已模拟脱敏汇总投递')
        return '预演'
    try:
        import notify
        sender = notify.send
    except Exception:
        sender = None
        paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
        for path in paths:
            if not path.is_file():
                continue
            try:
                spec = importlib.util.spec_from_file_location('_qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = module.send
                break
            except Exception:
                continue
    if sender is None:
        log('⚠️ 通知不可用，业务退出码保持不变')
        return '不可用'
    try:
        sender(TITLE, body)
        log('通知已发送')
        return '已发送'
    except Exception:
        log('⚠️ 通知发送失败，业务退出码保持不变')
        return '失败'


def stage(stats, index, name, action):
    started = time.monotonic()
    log(f'阶段 {index}：{name} 开始')
    try:
        outcome, message = action()
        stats[outcome] += 1
        log(f'阶段 {index}：{message}；耗时 {time.monotonic()-started:.2f} 秒')
        return outcome
    except Exception as exc:
        stats['failure'] += 1
        # 第三方/解析异常绝不直接打印，防止异常字符串携带响应或凭据。
        message = str(exc) if isinstance(exc, TaskError) else '处理失败，返回格式或参数异常'
        log(f'❌ 阶段 {index}：{message}；耗时 {time.monotonic()-started:.2f} 秒')
        return 'failure'


def delay(max_delay):
    seconds = random.randint(0, max_delay)
    log(f'随机延时 {seconds} 秒')
    while seconds:
        step = min(10, seconds)
        time.sleep(step)
        seconds -= step
        log(f'随机延时剩余 {seconds} 秒')


def run_account(cred, number, command, dry, max_delay):
    start = time.monotonic()
    stats = dict.fromkeys(('success', 'alreadyComplete', 'skipped', 'failure'), 0)
    log(f'账号 {number} 开始')
    try:
        cred = validate(cred)
        client = Trae(cred)
    except Exception as exc:
        stats['failure'] = 1
        log(f'❌ 账号 {number} 配置错误：{exc if isinstance(exc, TaskError) else "账号参数格式错误"}')
    else:
        if dry:
            for i, name in enumerate(('凭据刷新', '签到状态查询', '积分领取' if command == 'checkin' else '领取跳过', '积分余额查询'), 1):
                stage(stats, i, name, lambda: ('skipped', 'DRY_RUN_OK：参数已验证，未发送请求或写文件'))
        else:
            if enabled('RANDOM_SIGNIN', 'true') and max_delay > 0:
                delay(max_delay)
            def refresh():
                expiry = finite_number(cred.get('expiresAt', payload(cred['accessToken']).get('exp', 0)))
                if expiry > 1e12:
                    expiry /= 1000
                if expiry and expiry - time.time() >= 24 * 3600:
                    return 'skipped', '凭据未到刷新窗口'
                if not expiry and not cred.get('refreshToken'):
                    return 'skipped', '未提供到期时间，以业务认证响应验证凭据'
                client.refresh()
                return 'success', '凭据刷新成功（仅内存更新）'
            def status():
                r = client.request('/trae/api/v2/ug/checkin_credits/status')
                if not business_ok(r):
                    raise TaskError('签到状态查询未通过业务验证')
                client.identity(r)
                return 'success', '签到状态查询成功'
            def claim():
                for attempt in range(1, 4):
                    r = client.request('/trae/api/v2/ug/checkin_credits/claim')
                    if code_of(r) == 9074 and attempt < 3:
                        log(f'领取业务码 9074，第 {attempt}/3 次；不切换设备，等待后重试')
                        time.sleep(20 * attempt)
                        continue
                    result = claim_outcome(r)
                    client.identity(r)
                    return result, '领取成功' if result == 'success' else '今日已领取'
                raise TaskError('领取重试失败')
            def balance():
                r = client.request('/trae/api/v2/pay/ide_user_ent_usage')
                message = credits_text(r)
                client.identity(r)
                return 'success', message
            stage(stats, 1, '凭据刷新', refresh)
            if stats['failure'] == 0:
                stage(stats, 2, '签到状态查询', status)
            else:
                stage(stats, 2, '签到状态查询', lambda: ('skipped', '刷新失败，跳过'))
            if command == 'checkin' and stats['failure'] == 0:
                stage(stats, 3, '积分领取', claim)
            else:
                stage(stats, 3, '积分领取', lambda: ('skipped', '只读模式或前置检查失败，跳过领取'))
            if stats['failure'] == 0 or stats['success']:
                stage(stats, 4, '积分余额查询', balance)
            else:
                stage(stats, 4, '积分余额查询', lambda: ('skipped', '凭据不可用，跳过查询'))
            if enabled('TRAE_SAVE_CREDENTIALS'):
                stage(stats, 5, '显式凭据保存', lambda: (save_cred(cred) or 'success', '凭据已安全保存'))
    log(f"账号 {number} 统计：总任务 {sum(stats.values())}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failure']}，耗时 {time.monotonic()-start:.2f} 秒")
    return stats


class Callback(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != '/authorize' or len(self.path) > 65536:
            self.send_error(404)
            return
        query = urllib.parse.parse_qs(parsed.query)
        captured = {k: v[0] for k, v in query.items() if v}
        if not any(captured.get(k) for k in ('refreshToken', 'refresh_token', 'data')):
            self.send_error(400)
            return
        self.server.captured = captured
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write('已收到登录回调，请查看终端确认结果。'.encode())

    def log_message(self, *args):
        pass


def login():
    """显式本地 OAuth；不扫描其他应用设备文件，不打印授权 URL 或回调。"""
    import webbrowser
    server = None
    for port in range(18080, 18100):
        try:
            server = HTTPServer(('127.0.0.1', port), Callback)
            break
        except OSError:
            continue
    if server is None:
        raise TaskError('登录回调端口不可用')
    device_id, machine_id = secrets.token_hex(16), secrets.token_hex(16)
    params = {'client_id': CLIENT_ID, 'auth_from': 'solo', 'login_channel': 'native_ide',
              'plugin_version': '2.3.62834', 'auth_callback_url': f'http://127.0.0.1:{port}/authorize',
              'x_app_version': IDE_VERSION, 'x_app_type': 'stable', 'device_id': device_id, 'machine_id': machine_id}
    url = 'https://www.trae.cn/authorization?' + urllib.parse.urlencode(params)
    try:
        server.captured = None
        server.timeout = 1
        try:
            opened = webbrowser.open(url)
        except Exception:
            opened = False
        if opened:
            log('阶段 1：请在已打开的官方页面登录，等待回调（最多 300 秒）')
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline and server.captured is None:
                server.handle_request()
            captured = server.captured
        else:
            log('阶段 1：未找到浏览器；支持粘贴本人已有 OAuth 回调，不要求安装客户端或浏览器')
            answer = getpass.getpass('保密输入本人完整登录回调地址：')
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(answer).query)
            captured = {k: v[0] for k, v in query.items() if v}
    finally:
        server.server_close()
    if not captured:
        raise TaskError('未收到有效登录回调')
    refresh_token = captured.get('refreshToken') or captured.get('refresh_token') or captured.get('data')
    if not refresh_token:
        raise TaskError('登录回调缺少刷新凭据')
    def param(key):
        try:
            v = json.loads(urllib.parse.unquote(captured.get(key, '{}')))
            return v if isinstance(v, dict) else {}
        except ValueError:
            return {}
    user, jwt = param('userInfo'), param('userJwt')
    uid = user.get('UserID') or jwt.get('UserID') or ''
    token = jwt.get('Token') or jwt.get('token') or jwt.get('AccessToken')
    expiry = jwt.get('TokenExpireAt')
    if not token:
        log('阶段 2：使用登录回调交换凭据')
        r = http_request('POST', AUTH_BASE + '/cloudide/api/v3/trae/oauth/ExchangeToken',
                         {'Content-Type': 'application/json'}, {'ClientID': CLIENT_ID,
                         'RefreshToken': refresh_token, 'ClientSecret': '-', 'UserID': uid})
        result = object_data(r)
        if code_of(r) not in (None, 0, 200) or r.get('success') is False:
            raise TaskError('登录凭据交换业务失败')
        token = result.get('Token') or result.get('AccessToken')
        refresh_token = result.get('RefreshToken') or refresh_token
        expiry = result.get('TokenExpireAt')
    if not isinstance(token, str) or not token:
        raise TaskError('登录接口没有返回有效凭据')
    identity = payload(token).get('data', {})
    if isinstance(identity, str):
        try:
            identity = json.loads(identity)
        except ValueError:
            identity = {}
    if not isinstance(identity, dict):
        identity = {}
    uid = uid or identity.get('id') or identity.get('UserID') or identity.get('uid') or ''
    name = user.get('ScreenName') or user.get('screenName') or identity.get('screen_name') or identity.get('ScreenName') or ''
    # 随机 OAuth device_id 不是可领取设备，绝不能把它用作 claimDeviceId。
    cred = {'userId': uid, 'screenName': name, 'accessToken': token,
            'refreshToken': refresh_token, 'expiresAt': finite_number(expiry) if expiry else time.time() + 3600,
            'claimDeviceId': '', 'fingerprint': {'brand': '', 'type': '', 'os': ''}}
    save_cred(cred)
    if name or uid:
        log(f'官方账号身份：{name or uid}')
    log('阶段 3：登录成功，凭据已保密保存；执行签到前需补充真实领取设备及指纹')


def main():
    started = time.monotonic()
    dry = enabled('TRAE_DRY_RUN')
    command = sys.argv[1] if len(sys.argv) == 2 else 'checkin' if len(sys.argv) == 1 else 'invalid'
    log('========== Trae Work 签到 ==========')
    log(f"开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；模式：{'断网预演' if dry else '正式执行'}；任务：{command if command in ('checkin', 'status', 'login') else '无效参数'}")
    entries = []
    results = []
    config_error = False
    try:
        entries = load_accounts() if command != 'login' else [None]
        log(f'账号总数：{len(entries)}')
        if command not in ('checkin', 'status', 'login'):
            raise TaskError('用法：python candidate.py [checkin|status|login]')
        if not entries:
            raise TaskError('未配置 TRAE_ACCOUNTS，也没有可用旧版凭据文件')
        try:
            max_delay = int(os.getenv('MAX_RANDOM_DELAY', '3600'))
        except ValueError:
            raise TaskError('MAX_RANDOM_DELAY 必须为整数') from None
        if not 0 <= max_delay <= 86400:
            raise TaskError('MAX_RANDOM_DELAY 必须在 0 到 86400 秒之间')
        if command == 'login':
            stats = dict.fromkeys(('success', 'alreadyComplete', 'skipped', 'failure'), 0)
            stage(stats, 1, '交互登录', lambda: ('skipped', 'DRY_RUN_OK：未启动浏览器、回调服务、网络或写文件') if dry else (login() or 'success', '登录成功'))
            results.append(stats)
            log(f"账号 1 统计：总任务 1，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failure']}")
        else:
            for number, cred in enumerate(entries, 1):
                results.append(run_account(cred, number, command, dry, max_delay))
    except TaskError as exc:
        config_error = True
        log(f'❌ 配置错误：{exc}')
    except Exception:
        config_error = True
        log('❌ 配置读取或执行失败，未输出敏感异常信息')
    failed = sum(r['failure'] > 0 for r in results)
    successful = len(results) - failed
    if config_error:
        failed = max(1, len(entries))
    exit_code = 1 if config_error else 2 if failed else 0
    status = 'configuration-error' if config_error else 'partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry else 'success'
    totals = {key: sum(r[key] for r in results) for key in ('success', 'alreadyComplete', 'skipped', 'failure')}
    log('----------------------------------------')
    log(f'账号统计：总数 {len(entries)}，成功 {successful}，失败 {failed}')
    log(f"子任务统计：成功 {totals['success']}，已完成 {totals['alreadyComplete']}，跳过 {totals['skipped']}，失败 {totals['failure']}")
    body = f'账号总数：{len(entries)}\n成功数：{successful}\n失败数：{failed}\n状态：{status}\n预演仅验证参数，不代表真实业务成功。' if dry else f'账号总数：{len(entries)}\n成功数：{successful}\n失败数：{failed}\n状态：{status}'
    notify_status = notification(body, dry)
    log(f'通知状态：{notify_status}')
    log(f"完成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}；总耗时 {time.monotonic()-started:.2f} 秒；最终状态：{status}")
    print('TASK_SUMMARY=' + json.dumps({'applicationKey': 'trae-work', 'mode': 'dry-run' if dry else 'live',
          'accounts': len(entries), 'success': successful, 'failed': failed, 'tasks': totals,
          'status': status, 'notification': notify_status, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
