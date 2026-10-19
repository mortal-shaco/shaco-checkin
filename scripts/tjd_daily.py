#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 塔吉多每日任务
# cron: 24 2 * * *
# 来源：SkyBlue997/tjd-daily，tjd_daily.py、tjd_login.py；MIT 许可。
# 输入源码没有额外版权声明；保留原作者归属，以下协议实现沿用上游。
# MIT License: Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""每行一个 TJD_ACCOUNTS JSON 对象（token、deviceid 必填）。
旧 TJD_TOKEN/TJD_DEVICEID 等变量也使用换行对齐；不再使用 & 分隔。
密码重登仅在提供 phone/password 时启用，不打印或写回凭据。
点赞、分享需显式指定 TJD_TASKS 或 --only；分享仅上报帖子回调，不发布文字。
云异环是不同应用，不在此任务执行。TJD_DRY_RUN=1 完全断网预演。
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
        _ql_notify_identities = ('e096ba77bcda7172', 'scripts/tjd_daily.py', 'tjd_daily.py', 'tjd_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import hashlib
import importlib.util
import json
import os
import random
import re
import string
import sys
import time
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None


def _require_aes():
    if AES is None:
        raise TaskError('密码重登需要公开依赖 pycryptodome')

LAOHU_HOST = 'https://user.laohu.com'
BBS_HOST   = 'https://bbs-api.tajiduo.com'
APP_ID     = '10551'
BID        = 'com.pwrd.htassistant'
CHANNEL_ID = '2'
SDK_VER    = '4.131.0'
APP_VER    = '1.2.2'
LH_SECRET  = '5fd254cc0c8740d7a57376415ce40ede'   # 32-char laohu sign secret (用于 user.laohu.com)
AES_KEY    = b'a57376415ce40ede'                  # AES-128-ECB key (LH_SECRET 后 16 字符 ASCII)
BBS_SECRET = 'pUds3dfMkl'                         # bbs-api ds 签名密钥 (Hermes jsbundle 取出)
UA_LH      = 'HTAssistant/1.2.2 (iPhone; iOS 26.1; Scale/3.00)'
UA_BBS     = 'HTAssistant/106 CFNetwork/3860.200.71 Darwin/25.1.0'
ALPH       = string.ascii_letters + string.digits


def laohu_sign(params: dict) -> str:
    """MD5(concat values, alphabetical key order, URL-decoded + LH_SECRET)."""
    concat = ''.join(params[k] for k in sorted(params))
    return hashlib.md5((concat + LH_SECRET).encode('utf-8')).hexdigest()


def make_ds() -> str:
    """bbs-api ds 头: '<ts>,<nonce>,<md5(ts+nonce+APP_VER+BBS_SECRET)>'"""
    ts = str(int(time.time()))
    nonce = ''.join(random.choice(ALPH) for _ in range(8))
    sig = hashlib.md5(f'{ts}{nonce}{APP_VER}{BBS_SECRET}'.encode()).hexdigest()
    return f'{ts},{nonce},{sig}'


def laohu_encrypt(plaintext: str) -> str:
    """AES-128-ECB + PKCS7 + base64."""
    _require_aes()
    raw = plaintext.encode('utf-8')
    pad = 16 - (len(raw) % 16)
    raw += bytes([pad]) * pad
    return base64.b64encode(AES.new(AES_KEY, AES.MODE_ECB).encrypt(raw)).decode()


def base_params(deviceid, openudid, vendorid, *, t_ms=False):
    return {
        'adid':         deviceid,
        'adm':          '',
        'appId':        APP_ID,
        'bid':          BID,
        'channelId':    CHANNEL_ID,
        'deviceId':     deviceid,
        'iOSAppOnMac':  '0',
        'mac':          deviceid,
        'openudid':     openudid,
        'osType':       '1',
        'sdkVersion':   SDK_VER,
        't':            str(int(time.time() * (1000 if t_ms else 1))),
        'vendorid':     vendorid,
        'version':      APP_VER,
    }


# ─── 三步登录 ─────────────────────────────────────────────────────────

def step2_password_login(username, password, deviceid, openudid, vendorid):
    """账号密码登录 (POST /openApi/secureLogin). 比短信路径少一步发短信."""
    p = base_params(deviceid, openudid, vendorid, t_ms=True)
    p.update({
        'deviceModel':  'iPhone',
        'deviceName':   'iPhone',
        'deviceSys':    '26.1',
        'deviceType':   'iPhone17,2',
        'idfa':         '00000000-0000-0000-0000-000000000000',
        'username':     laohu_encrypt(username),
        'password':     laohu_encrypt(password),
    })
    return laohu_post('/openApi/secureLogin', p)



OFF = {'0', 'false', 'no', 'off'}
TASK_KEYS = {'signin': 'signin_c', 'browse': 'browse_post_c',
             'like': 'like_post_c', 'share': 'share'}
DRY = os.getenv('TJD_DRY_RUN', '0').lower() not in OFF
SECRETS = []


class TaskError(Exception):
    pass


def log(message, official_identity=False):
    message = str(message)
    for secret in SECRETS:
        if secret:
            message = message.replace(str(secret), '[凭据已隐藏]')
    if not official_identity:
        message = re.sub(r'(?<!\d)1\d{10}(?!\d)', '[手机号已隐藏]', message)
    print(time.strftime('[%H:%M:%S] ') + message.replace('\n', ' ').replace('\r', ' '), flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，避免凭据被转发')


def http(url, method='GET', headers=None, body=None):
    if DRY:
        raise TaskError('预演禁止网络请求')
    data = urllib.parse.urlencode(body).encode() if body is not None else None
    hdr = dict(headers or {})
    if data is not None:
        hdr['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=data, method=method, headers=hdr)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as r:
            code = r.status
            raw = r.read(1048577)
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read(1048577)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    if len(raw) > 1048576:
        raise TaskError('接口响应超过大小限制')
    try:
        j = json.loads(raw)
    except (ValueError, UnicodeError):
        raise TaskError('接口未返回有效 JSON') from None
    if not isinstance(j, dict):
        raise TaskError('接口响应结构不符')
    return code, j


def laohu_post(path, params):
    body = dict(params)
    body['sign'] = laohu_sign(body)
    return http(LAOHU_HOST + path, 'POST', {'User-Agent': UA_LH}, body)


def ok(code, j):
    return 200 <= code < 300 and j.get('ok') is True and j.get('code') == 0


def ensure(code, j):
    if not ok(code, j):
        raise TaskError('接口业务失败（HTTP状态或业务成功标志不符）')
    return j.get('data')


def identity(data):
    if isinstance(data, dict):
        for key in ('nickname', 'username', 'displayName', 'uid'):
            if data.get(key) is not None:
                log(f'官方账号身份 {key}={data[key]}', official_identity=True)


class Client:
    def __init__(self, account):
        self.a = account
        self.relogged = False

    def headers(self, h5=False):
        if h5:
            return {'Accept': 'application/json, text/plain, */*',
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
                    'Authorization': self.a['token'], 'Origin': 'https://webstatic.tajiduo.com',
                    'Referer': 'https://webstatic.tajiduo.com/'}
        return {'Accept': 'application/json, text/plain, */*', 'User-Agent': UA_BBS,
                'Authorization': self.a['token'], 'appversion': APP_VER, 'platform': 'ios',
                'uid': str(self.a.get('uid', '0')), 'deviceid': self.a['deviceid'], 'ds': make_ds()}

    def relogin(self):
        self.relogged = True
        a = self.a
        if not a.get('phone') or not a.get('password'):
            raise TaskError('凭据失效，请在 App 登录后重新获取 Authorization')
        code, j = step2_password_login(a['phone'], a['password'], a['deviceid'],
                                      a.get('openudid', ''), a.get('vendorid', ''))
        if not (200 <= code < 300 and j.get('code') == 0 and isinstance(j.get('result'), dict)):
            raise TaskError('密码登录失败')
        result = j['result']
        if not result.get('token') or result.get('userId') is None:
            raise TaskError('密码登录响应缺少凭据字段')
        SECRETS.append(result['token'])
        identity({k: result[k] for k in ('nickname', 'username', 'displayName') if k in result})
        hdr = self.headers()
        hdr.update({'Authorization': '', 'uid': '0'})
        code, j = http(BBS_HOST + '/usercenter/api/login', 'POST', hdr,
                       {'token': result['token'], 'userIdentity': str(result['userId']), 'appId': APP_ID})
        data = ensure(code, j)
        if not isinstance(data, dict) or not data.get('accessToken'):
            raise TaskError('登录响应缺少 accessToken')
        a['token'] = data['accessToken']
        SECRETS.append(a['token'])
        identity(data)
        log('密码重登成功，仅在内存更新凭据')

    def request(self, method, path, body=None, query=None, h5=False):
        url = BBS_HOST + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        code, j = http(url, method, self.headers(h5), body)
        if (code in (401, 402) or j.get('code') in (401, 402, 4011)) and not self.relogged:
            self.relogin()
            code, j = http(url, method, self.headers(h5), body)
        return code, j

    def data(self, method, path, **kwargs):
        code, j = self.request(method, path, **kwargs)
        data = ensure(code, j)
        identity(data)
        return data

    def tasks(self):
        data = self.data('GET', '/apihub/api/getUserTasks', query={'gid': '1'})
        if not isinstance(data, dict) or not isinstance(data.get('task_list1'), list):
            raise TaskError('任务列表响应结构不符')
        return data

    def cards(self, tasks):
        uid = self.a.get('account_uid')
        for key in ('task_list1', 'task_list2'):
            for t in tasks.get(key, []):
                if t.get('uid'):
                    uid = str(t['uid'])
                    log(f'官方账号身份 uid={uid}', official_identity=True)
                    break
            if uid:
                break
        if not uid:
            raise TaskError('无法从任务列表获取公开 UID')
        data = self.data('GET', '/apihub/api/getGameRecordCard', query={'uid': uid})
        if not isinstance(data, list):
            raise TaskError('角色卡响应结构不符')
        for card in data:
            role = card.get('bindRoleInfo') or {}
            log(f"角色 {card.get('gameName', '未知游戏')}：{role.get('roleName', '未绑定')}；等级 {role.get('lev', '-')}；服务器 {role.get('serverName', '-')}")
        return data

    def posts(self):
        data = self.data('GET', '/bbs/api/getRecommendPostList',
                         query={'communityId': '2', 'count': '20', 'page': '1'})
        if not isinstance(data, dict) or not isinstance(data.get('posts'), list):
            raise TaskError('推荐帖子响应结构不符')
        return data['posts']

    def run(self, action):
        if action in TASK_KEYS:
            key = TASK_KEYS[action]
            tasks = {t['taskKey']: t for t in self.tasks()['task_list1']}
            if key not in tasks:
                raise TaskError('服务端未提供所选任务，停止该任务')
            t = tasks[key]
            n = max(0, int(t['limitTimes']) - int(t['completeTimes']))
            log(f'任务进度 {t["completeTimes"]}/{t["limitTimes"]}，剩余 {n}')
            if n == 0:
                return 'already'
            if action == 'signin':
                self.data('POST', '/apihub/api/signin', body={'communityId': '2'})
                log('社区签到接口验证成功')
            else:
                posts = self.posts()
                if action == 'like':
                    posts = [p for p in posts if not (p.get('selfOperation') or {}).get('liked')]
                if len(posts) < n:
                    raise TaskError('可用帖子不足，未执行不完整批次')
                for p in posts[:n]:
                    pid = str(p['postId'])
                    if action == 'browse':
                        self.data('GET', '/bbs/api/getPostFull', query={'postId': pid})
                    elif action == 'like':
                        self.data('POST', '/bbs/api/post/like', body={'postId': pid})
                    else:
                        self.data('POST', '/bbs/api/post/share',
                                  body={'platform': os.getenv('TJD_SHARE_PLATFORM', 'qq'), 'postId': pid})
                    log(f'{action} 帖子 {pid}：业务成功')
                    time.sleep(random.uniform(0.7, 1.5))
            final = {t['taskKey']: t for t in self.tasks()['task_list1']}
            if key not in final or int(final[key]['completeTimes']) < int(final[key]['limitTimes']):
                raise TaskError('执行后任务进度未达到完成标准')
            return 'success'
        tasks = self.tasks()
        cards = self.cards(tasks)
        if action == 'status':
            for t in tasks['task_list1']:
                log(f"任务 {t.get('taskKey')}：{t.get('completeTimes')}/{t.get('limitTimes')}")
            coin = self.data('GET', '/apihub/api/getUserCoinTaskState')
            if not isinstance(coin, dict):
                raise TaskError('金币状态响应结构不符')
            log(f"金币 今日 {coin.get('todayGet')}/{coin.get('todayTotal')}，累计 {coin.get('total')}")
        bound = 0
        for card in cards:
            gid = str(card['gameId'])
            role = card.get('bindRoleInfo') or {}
            rid = role.get('roleId')
            if not rid:
                log('⏭️ 游戏未绑定角色')
                continue
            bound += 1
            state = self.data('GET', '/apihub/awapi/signin/state', query={'gameId': gid}, h5=True)
            if not isinstance(state, dict) or not isinstance(state.get('todaySign'), (bool, int)):
                raise TaskError('游戏签到状态响应结构不符')
            log(f"游戏 {card.get('gameName', gid)}：今日已签={state['todaySign']}；本月 {state.get('days', 0)} 天")
            if action == 'gamesign' and not state['todaySign']:
                code, j = self.request('POST', '/apihub/awapi/sign',
                                       body={'gameId': gid, 'roleId': str(rid)}, h5=True)
                if not ok(code, j) and not (200 <= code < 300 and j.get('code') == 5052):
                    raise TaskError('游戏签到业务失败')
                state = self.data('GET', '/apihub/awapi/signin/state', query={'gameId': gid}, h5=True)
                if not isinstance(state, dict) or not state.get('todaySign'):
                    raise TaskError('游戏签到未通过状态复核')
                log('游戏签到已通过状态复核')
        return 'skipped' if action == 'gamesign' and not bound else 'success'


def load_accounts(config):
    raw = os.getenv('TJD_ACCOUNTS', '').strip()
    if raw:
        # 每行一个 JSON 对象；保留旧单对象和 JSON 数组兼容。
        try:
            parsed = json.loads(raw)
            accounts = parsed if isinstance(parsed, list) else [parsed]
        except ValueError:
            accounts = []
            for line in raw.splitlines():
                if line.strip():
                    try:
                        accounts.append(json.loads(line))
                    except ValueError:
                        accounts.append(None)
    elif os.getenv('TJD_TOKEN'):
        tokens = [s.strip() for s in os.environ['TJD_TOKEN'].splitlines() if s.strip()]
        mapping = {'deviceid': 'TJD_DEVICEID', 'uid': 'TJD_UID', 'name': 'TJD_NAME',
                   'phone': 'TJD_PHONE', 'password': 'TJD_PASSWORD',
                   'openudid': 'TJD_OPENUDID', 'vendorid': 'TJD_VENDORID'}
        values = {k: os.getenv(v, '').splitlines() for k, v in mapping.items()}
        accounts = []
        for i, token in enumerate(tokens):
            a = {'token': token}
            for key, lines in values.items():
                a[key] = lines[i] if i < len(lines) else ''
            accounts.append(a)
    else:
        try:
            with open(config, encoding='utf-8') as f:
                raw = json.load(f)
            accounts = raw.get('accounts', [raw]) if isinstance(raw, dict) else raw
        except (OSError, ValueError):
            raise TaskError('缺少有效账号配置：设置 TJD_ACCOUNTS，或兼容 TJD_TOKEN/TJD_DEVICEID') from None
    if not isinstance(accounts, list) or not accounts:
        raise TaskError('账号配置为空或结构不符')
    return accounts


def notify(summary, disabled):
    if disabled or os.getenv('QINGLONG_NOTIFY', '1').lower() in OFF:
        return 'disabled'
    if DRY:
        log('预演通知：已生成脱敏总结，不调用外部通知渠道')
        return 'dry-run'
    body = f"账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；状态 {summary['status']}"
    try:
        try:
            import notify as notifier
        except ImportError:
            notifier = None
            paths = [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('ql_notify', path)
                    notifier = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(notifier)
                    break
        if notifier is None:
            log('⚠️ 通知组件不可用，保留业务退出码')
            return 'unavailable'
        notifier.send('塔吉多每日任务', body)
        return 'sent'
    except (Exception, SystemExit):
        log('⚠️ 通知失败，保留业务退出码')
        return 'failed'


def main():
    started = time.monotonic()
    log('========== 塔吉多每日任务 ==========')
    log('开始时间 ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('断网预演' if DRY else '正式执行'))
    summary = {'accounts': 0, 'success': 0, 'failed': 0, 'tasks': 0,
               'taskSuccess': 0, 'already': 0, 'skipped': 0, 'taskFailed': 0}
    disabled = False
    interval = 0
    config_error = False
    try:
        ap = argparse.ArgumentParser(description=__doc__)
        ap.add_argument('--only', choices=['status', 'signin', 'gamesign', 'browse', 'like', 'share'])
        ap.add_argument('--config', default=str(Path(__file__).with_name('tjd_config.json')))
        ap.add_argument('--account')
        ap.add_argument('--no-notify', action='store_true')
        ap.add_argument('--loop', type=int, default=0, metavar='SECONDS', help='常驻循环间隔；预演仅运行一轮')
        args = ap.parse_args()
        disabled = args.no_notify
        interval = max(0, args.loop)
        actions = [args.only] if args.only else os.getenv('TJD_TASKS', 'signin,gamesign,browse').split(',')
        actions = list(dict.fromkeys(a.strip() for a in actions if a.strip()))
        if not actions or any(a not in ['status', 'signin', 'gamesign', 'browse', 'like', 'share'] for a in actions):
            raise TaskError('TJD_TASKS 包含不支持的动作')
        if os.getenv('TJD_SHARE_PLATFORM', 'qq') not in ('qq', 'wechat', 'timeline', 'wb'):
            raise TaskError('TJD_SHARE_PLATFORM 必须是 qq、wechat、timeline 或 wb')
        accounts = load_accounts(args.config)
        if args.account:
            accounts = [a for a in accounts if isinstance(a, dict) and a.get('name') == args.account]
            if not accounts:
                raise TaskError('指定账号不存在')
        summary['accounts'] = len(accounts)
        for a in accounts:
            if isinstance(a, dict):
                for k in ('token', 'phone', 'password', 'deviceid', 'openudid', 'vendorid'):
                    if a.get(k):
                        SECRETS.append(str(a[k]))
        log(f'账号数量：{len(accounts)}')
        for index, a in enumerate(accounts, 1):
            begin = time.monotonic()
            stats = {'success': 0, 'already': 0, 'skipped': 0, 'failed': 0}
            log(f'账号 {index} 开始')
            if not isinstance(a, dict) or any(not isinstance(a.get(k), str) or not a[k].strip() for k in ('token', 'deviceid')):
                stats['failed'] = 1
                summary['tasks'] += 1
                summary['taskFailed'] += 1
                log('❌ 账号配置缺少 token/deviceid 字符串')
            else:
                a['uid'] = a.get('uid') or '0'
                client = Client(a)
                for num, action in enumerate(actions, 1):
                    stage = time.monotonic()
                    summary['tasks'] += 1
                    log(f'账号 {index} 阶段 {num}/{len(actions)}：{action}')
                    try:
                        if DRY:
                            log('DRY_RUN_OK：参数验证通过；模拟任务与业务核验，不发送请求')
                            outcome = 'success'
                        else:
                            outcome = client.run(action)
                        stats[outcome] += 1
                        summary[{'success': 'taskSuccess', 'already': 'already', 'skipped': 'skipped'}[outcome]] += 1
                        log(f'✅ 阶段结果 {outcome}，耗时 {time.monotonic()-stage:.2f} 秒')
                    except Exception as e:
                        stats['failed'] += 1
                        summary['taskFailed'] += 1
                        # 仅打印本程序固定错误文本；不打印第三方异常或响应。
                        log('❌ ' + (str(e) if isinstance(e, TaskError) else '响应结构或运行依赖异常') + f'，耗时 {time.monotonic()-stage:.2f} 秒')
                if not DRY and stats['success'] + stats['already'] == 0:
                    if stats['failed'] == 0:
                        stats['failed'] += 1
                        summary['taskFailed'] += 1
                        log('❌ 没有可核验的成功任务')
            summary['failed' if stats['failed'] else 'success'] += 1
            log(f"账号 {index} 统计：总任务 {sum(stats.values())}，成功 {stats['success']}，已完成 {stats['already']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {time.monotonic()-begin:.2f} 秒")
    except (TaskError, SystemExit, KeyboardInterrupt) as e:
        config_error = True
        log('❌ ' + (str(e) if isinstance(e, TaskError) else '参数错误或任务中止'))
    except Exception:
        config_error = True
        log('❌ 配置或运行异常')
    status = 'configuration-error' if config_error else ('partial-failure' if summary['failed'] and summary['success'] else 'failure' if summary['failed'] else 'dry-run' if DRY else 'success')
    summary['status'] = status
    summary['exitCode'] = 1 if config_error or summary['failed'] else 0
    summary['notification'] = notify(summary, disabled)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishedAt'] = time.strftime('%Y-%m-%d %H:%M:%S')
    log('----------------------------------------')
    log(f"任务统计：账号 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；子任务 {summary['tasks']}，成功 {summary['taskSuccess']}，已完成 {summary['already']}，跳过 {summary['skipped']}，失败 {summary['taskFailed']}")
    log(f"总耗时 {summary['elapsedSeconds']} 秒；完成时间 {summary['finishedAt']}；通知 {summary['notification']}；最终状态 {status}")
    return summary, (0 if DRY or config_error else interval)


if __name__ == '__main__':
    failed = False
    final_summary = None
    try:
        while True:
            final_summary, interval = main()
            failed = failed or bool(final_summary['exitCode'])
            if not interval:
                break
            log(f'常驻循环等待 {interval} 秒')
            time.sleep(interval)
    except KeyboardInterrupt:
        failed = True
        log('用户中止常驻循环')
    if final_summary is None:
        final_summary = {'status': 'failure', 'exitCode': 1}
    if failed:
        final_summary['exitCode'] = 1
        if final_summary['status'] in ('success', 'dry-run'):
            final_summary['status'] = 'failure'
    print('TASK_SUMMARY=' + json.dumps(final_summary, ensure_ascii=False, separators=(',', ':')))
    sys.exit(final_summary['exitCode'])
