#!/usr/bin/env python3
# name: 森空岛双游戏签到
# cron: 18 2 * * *
# SPDX-License-Identifier: GPL-3.0
# Derived from nuthx/auto-sign, skland/skland-demo.py and skland/SecuritySm.py.
# Upstream GPL-3.0 attribution retained; original source comments retained below.
"""森空岛独立维护版。参数、登录获取说明与功能清单见 contract.json。
不会读写 TOKEN.txt；TOKEN 兼容输入也使用每行一个账号。
"""
import base64
import gzip
import hashlib
import hmac
import importlib.util
import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path
from urllib import request, error, parse

TITLE = '森空岛双游戏签到'
USER_AGENT = 'Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Safari/537.36; SKLand/1.52.1'
DISABLED = {'0', 'false', 'no', 'off'}
DRY = False
SECRETS = []

class TaskError(Exception):
    pass

def clean(value):
    text = str(value).replace('\n', ' ').replace('\r', ' ')
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已脱敏]')
    import re
    return re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已脱敏]', text)[:400]

def log(text):
    print('[' + time.strftime('%H:%M:%S') + '] ' + clean(text), flush=True)

def require_code(resp, field='code', expected=0):
    if not isinstance(resp, dict) or type(resp.get(field)) is not int or resp[field] != expected:
        raise TaskError('业务校验失败（未返回预期成功码）')
    return resp

def http_json(url, method='GET', body=None, headers=None, serialized=None):
    if DRY:
        raise TaskError('预演禁止网络请求')
    raw = serialized if serialized is not None else (json.dumps(body) if body is not None else None)
    h = {'User-Agent': USER_AGENT, 'X-Requested-With': 'com.hypergryph.skland', 'Connection': 'close'}
    if raw is not None:
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    req = request.Request(url, data=raw.encode() if raw is not None else None, headers=h, method=method)
    try:
        # 禁止重定向，避免凭据被转发至其他主机。
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise TaskError('响应超过大小限制')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise TaskError('响应结构异常')
        return result
    except TaskError:
        raise
    except Exception:
        raise TaskError('网络请求或响应解析失败') from None

# 查询dId请求头
devices_info_url = "https://fp-it.portal101.cn/deviceprofile/v4"

# 数美配置
SM_CONFIG = {
    "organization": "UWXspnCCJN4sfYlNfqps",
    "appId": "default",
    "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCmxMNr7n8ZeT0tE1R9j/mPixoinPkeM+k4VGIn/s0k7N5rJAfnZ0eMER+QhwFvshzo0LNmeUkpR8uIlU/GEVr8mN28sKmwd2gpygqj0ePnBmOW4v0ZVwbSYK+izkhVFk2V/doLoMbWy6b+UnA8mkjvg0iYWRByfRsK2gdl7llqCwIDAQAB",
    "protocol": "https",
    "apiHost": "fp-it.portal101.cn"
}



DES_RULE = {
    "appId": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "uy7mzc4h",
        "obfuscated_name": "xx"
    },
    "box": {
        "is_encrypt": 0,
        "obfuscated_name": "jf"
    },
    "canvas": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "snrn887t",
        "obfuscated_name": "yk"
    },
    "clientSize": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "cpmjjgsu",
        "obfuscated_name": "zx"
    },
    "organization": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "78moqjfc",
        "obfuscated_name": "dp"
    },
    "os": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "je6vk6t4",
        "obfuscated_name": "pj"
    },
    "platform": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "pakxhcd2",
        "obfuscated_name": "gm"
    },
    "plugins": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "v51m3pzl",
        "obfuscated_name": "kq"
    },
    "pmf": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "2mdeslu3",
        "obfuscated_name": "vw"
    },
    "protocol": {
        "is_encrypt": 0,
        "obfuscated_name": "protocol"
    },
    "referer": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "y7bmrjlc",
        "obfuscated_name": "ab"
    },
    "res": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "whxqm2a7",
        "obfuscated_name": "hf"
    },
    "rtype": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "x8o2h2bl",
        "obfuscated_name": "lo"
    },
    "sdkver": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "9q3dcxp2",
        "obfuscated_name": "sc"
    },
    "status": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "2jbrxxw4",
        "obfuscated_name": "an"
    },
    "subVersion": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "eo3i2puh",
        "obfuscated_name": "ns"
    },
    "svm": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "fzj3kaeh",
        "obfuscated_name": "qr"
    },
    "time": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "q2t3odsk",
        "obfuscated_name": "nb"
    },
    "timezone": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "1uv05lj5",
        "obfuscated_name": "as"
    },
    "tn": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "x9nzj1bp",
        "obfuscated_name": "py"
    },
    "trees": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "acfs0xo4",
        "obfuscated_name": "pi"
    },
    "ua": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "k92crp1t",
        "obfuscated_name": "bj"
    },
    "url": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "y95hjkoo",
        "obfuscated_name": "cf"
    },
    "version": {
        "is_encrypt": 0,
        "obfuscated_name": "version"
    },
    "vpw": {
        "cipher": "DES",
        "is_encrypt": 1,
        "key": "r9924ab5",
        "obfuscated_name": "ca"
    }
}

BROWSER_ENV = {
    'plugins': 'MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,MicrosoftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1',
    'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
    'canvas': '259ffe69',  # 基于浏览器的canvas获得的值，不知道复用行不行
    'timezone': -480,  # 时区，应该是固定值吧
    'platform': 'Win32',
    'url': 'https://www.skland.com/',  # 固定值
    'referer': '',
    'res': '1920_1080_24_1.25',  # 屏幕宽度_高度_色深_window.devicePixelRatio
    'clientSize': '0_0_1080_1920_1920_1080_1920_1080',
    'status': '0011',  # 不知道在干啥
}


# // 将浏览器环境对象的key全部排序，然后对其所有的值及其子对象的值加入数字并字符串相加。若值为数字，则乘以10000(0x2710)再将其转成字符串存入数组,最后再做md5,存入tn变量（tn变量要做加密）
# //把这个对象用加密规则进行加密，然后对结果做GZIP压缩（结果是对象，应该有序列化），最后做AES加密（加密细节目前不清除），密钥为变量priId
# //加密规则：新对象的key使用相对应加解密规则的obfuscated_name值，value为字符串化后进行进行DES加密，再进行btoa加密

# 通过测试
def _DES(o: dict):
    result = {}
    for i in o.keys():
        if i in DES_RULE.keys():
            rule = DES_RULE[i]
            res = o[i]
            if rule['is_encrypt'] == 1:
                c = Cipher(TripleDES(rule['key'].encode('utf-8')), ECB())
                data = str(res).encode('utf-8')
                # 补足字节
                data += b'\x00' * (8 - len(data) % 8)
                res = base64.b64encode(c.encryptor().update(data)).decode('utf-8')
            result[rule['obfuscated_name']] = res
        else:
            result[i] = o[i]
    return result


# 通过测试
def _AES(v: bytes, k: bytes):
    iv = '0102030405060708'
    key = AES(k)
    c = Cipher(key, CBC(iv.encode('utf-8')))
    c.encryptor()
    # 填充明文
    v += b'\x00'
    while len(v) % 16 != 0:
        v += b'\x00'
    return c.encryptor().update(v).hex()


def GZIP(o: dict):
    # 这个压缩结果似乎和前台不太一样,不清楚是否会影响
    json_str = json.dumps(o, ensure_ascii=False)
    stream = gzip.compress(json_str.encode('utf-8'), 2, mtime=0)
    return base64.b64encode(stream)


# 获得tn的值,后续做DES加密用
# 通过测试
def get_tn(o: dict):
    sorted_keys = sorted(o.keys())

    result_list = []

    for i in sorted_keys:
        v = o[i]
        if isinstance(v, (int, float)):
            v = str(v * 10000)
        elif isinstance(v, dict):
            v = get_tn(v)
        result_list.append(v)
    return ''.join(result_list)


def get_smid():
    t = time.localtime()
    _time = '{}{:0>2d}{:0>2d}{:0>2d}{:0>2d}{:0>2d}'.format(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min,
                                                           t.tm_sec)
    uid = str(uuid.uuid4())
    v = _time + hashlib.md5(uid.encode('utf-8')).hexdigest() + '00'
    smsk_web = hashlib.md5(('smsk_web_' + v).encode('utf-8')).hexdigest()[0:14]
    return v + smsk_web + '0'


def get_d_id():
    # storageName = '.thumbcache_' + md5(SM_CONFIG['organization']) // 用于从本地存储获得值
    # uid = uuid()
    # priId=md5(uid)[0:16]
    # ep=rsa(uid,publicKey)
    # SMID = localStorage.get(storageName);// 获得本地存储存的值
    # _0x30b2eb为递归md5

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    global Cipher, TripleDES, AES, CBC, ECB
    from cryptography.hazmat.primitives.ciphers.base import Cipher
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    from cryptography.hazmat.primitives.ciphers.algorithms import AES
    from cryptography.hazmat.primitives.ciphers.modes import CBC, ECB
    PK = serialization.load_der_public_key(base64.b64decode(SM_CONFIG['publicKey']))
    uid = str(uuid.uuid4()).encode('utf-8')
    priId = hashlib.md5(uid).hexdigest()[0:16]
    # ep不一定对，先走走看
    ep = PK.encrypt(uid, padding.PKCS1v15())
    ep = base64.b64encode(ep).decode('utf-8')

    browser = BROWSER_ENV.copy()
    current_time = int(time.time() * 1000)
    browser.update({
        'vpw': str(uuid.uuid4()),
        'svm': current_time,
        'trees': str(uuid.uuid4()),
        'pmf': current_time
    })

    des_target = {
        **browser,
        'protocol': 102,
        'organization': SM_CONFIG['organization'],
        'appId': SM_CONFIG['appId'],
        'os': 'web',
        'version': '3.0.0',
        'sdkver': '3.0.0',
        'box': '',  # 似乎是个SMID，但是第一次的时候是空,不过不影响结果
        'rtype': 'all',
        'smid': get_smid(),
        'subVersion': '1.0.0',
        'time': 0
    }
    des_target['tn'] = hashlib.md5(get_tn(des_target).encode()).hexdigest()

    des_result = _AES(GZIP(_DES(des_target)), priId.encode('utf-8'))

    resp = http_json(devices_info_url, 'POST', {
        'appId': 'default', 'compress': 2, 'data': des_result, 'encode': 5,
        'ep': ep, 'organization': SM_CONFIG['organization'], 'os': 'web'
    })
    require_code(resp, 'code', 1100)
    if not isinstance(resp.get('detail'), dict) or not resp['detail'].get('deviceId'):
        raise TaskError('设备接口缺少必需字段')
    # 开头必须是B
    return 'B' + resp['detail']['deviceId']

AUTH = 'https://as.hypergryph.com'
API = 'https://zonai.skland.com'

def accounts_from_env():
    raw = os.environ.get('SKLAND_ACCOUNTS') or os.environ.get('TOKEN', '')
    if not raw.strip():
        raise TaskError('必须设置 SKLAND_ACCOUNTS；兼容 TOKEN，每行一个账号')
    accounts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        SECRETS.append(line)
        try:
            value = json.loads(line) if line.startswith('{') else {'token': line}
            if not isinstance(value, dict):
                raise ValueError()
            if isinstance(value.get('data'), dict) and 'content' in value['data']:
                value = {'token': value['data']['content']}
            for key in ('token', 'password', 'phone', 'code', 'did'):
                if isinstance(value.get(key), str):
                    SECRETS.append(value[key])
            accounts.append(value)
        except Exception:
            accounts.append({'invalid': True})
    if not accounts:
        raise TaskError('账号列表为空')
    return accounts

class Client:
    def __init__(self, did):
        self.did = did
        self.cred = ''
        self.token = ''

    def login_request(self, url, body):
        return http_json(url, 'POST', body, {'dId': self.did})

    def login(self, account):
        token = account.get('token')
        if not token:
            phone = account['phone']
            if account.get('password'):
                resp = self.login_request(AUTH + '/user/auth/v1/token_by_phone_password',
                                          {'phone': phone, 'password': account['password']})
            else:
                resp = self.login_request(AUTH + '/user/auth/v2/token_by_phone_code',
                                          {'phone': phone, 'code': account['code']})
            require_code(resp, 'status')
            token = resp['data']['token']
        SECRETS.append(token)
        grant = self.login_request(AUTH + '/user/oauth2/v2/grant',
                                  {'appCode': '4ca99fa6b56cc2ba', 'token': token, 'type': 0})
        require_code(grant, 'status')
        code = grant['data']['code']
        SECRETS.append(code)
        resp = self.login_request(API + '/web/v1/user/auth/generate_cred_by_code', {'code': code, 'kind': 1})
        require_code(resp)
        self.cred = resp['data']['cred']
        self.token = resp['data']['token']
        if not all(isinstance(v, str) and v for v in (self.cred, self.token)):
            raise TaskError('登录凭据字段缺失')
        SECRETS.extend([self.cred, self.token])

    def signed(self, path, body=None, extra=None):
        timestamp = str(int(time.time()) - 2)
        signing_headers = {'platform': '3', 'timestamp': timestamp, 'dId': self.did, 'vName': '1.0.0'}
        serialized = json.dumps(body) if body is not None else ''
        message = path + serialized + timestamp + json.dumps(signing_headers, separators=(',', ':'))
        digest = hmac.new(self.token.encode(), message.encode(), hashlib.sha256).hexdigest()
        headers = dict(signing_headers, cred=self.cred, sign=hashlib.md5(digest.encode()).hexdigest())
        headers.update(extra or {})
        method = 'GET' if path.endswith('/binding') or path.endswith('/refresh') else 'POST'
        resp = http_json(API + path, method, headers=headers,
                         serialized=serialized if body is not None else None)
        require_code(resp)
        return resp

    def refresh(self):
        # 保留上游刷新能力，默认不额外调用。
        resp = self.signed('/web/v1/auth/refresh')
        self.token = resp['data']['token']
        if not isinstance(self.token, str) or not self.token:
            raise TaskError('刷新凭据字段缺失')
        SECRETS.append(self.token)


def validate_account(account, action):
    def present(key):
        return isinstance(account.get(key), str) and bool(account[key].strip())
    if action == 'send-code':
        valid = present('phone')
    else:
        valid = present('token') or (present('phone') and (present('password') or present('code')))
    if not valid or account.get('invalid'):
        raise TaskError('账号格式错误：需要通行证，或同一行 JSON 中的手机号及密码/验证码')
    if 'did' in account and not present('did'):
        raise TaskError('did 必须为非空字符串')


def notify(summary):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    body = ('模式：{mode}；账号总数：{accounts}；成功：{success}；失败：{failed}；'
            '状态：{status}；子任务成功：{steps_success}；子任务失败：{steps_failed}').format(**summary)
    try:
        try:
            from notify import send
        except ImportError:
            paths = []
            if os.environ.get('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                raise TaskError('未发现通知模块')
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
        send(TITLE, clean(body))
        return '已发送'
    except Exception:
        log('⚠️ 通知不可用或发送失败，保留业务退出码' + ('；预演网络已禁用' if DRY else ''))
        return '不可用或失败'


def run():
    global DRY
    DRY = os.environ.get('SKLAND_DRY_RUN', '0').lower() not in DISABLED
    if DRY:
        def forbidden(*args, **kwargs):
            raise TaskError('预演禁止网络连接')
        socket.socket = forbidden
        socket.create_connection = forbidden
        socket.getaddrinfo = forbidden
    start = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('断网预演' if DRY else '实际签到'))
    summary = {'mode': 'dry-run' if DRY else 'live', 'accounts': 0, 'success': 0, 'failed': 0,
               'steps_success': 0, 'steps_failed': 0, 'alreadyComplete': 0, 'skipped': 0}
    config_error = False
    action = os.environ.get('SKLAND_ACTION', os.environ.get('SKYLAND_TYPE', 'sign')) or 'sign'
    try:
        if action not in ('sign', 'send-code'):
            raise TaskError('仅支持 sign 或 send-code；已移除凭据文件写入的 add_account 模式')
        games = os.environ.get('SKLAND_GAMES', 'arknights,endfield').split(',')
        if not games or any(g not in ('arknights', 'endfield') for g in games):
            raise TaskError('SKLAND_GAMES 仅支持 arknights,endfield')
        accounts = accounts_from_env()
        summary['accounts'] = len(accounts)
        log('账号数量：' + str(len(accounts)))
    except TaskError as exc:
        log('❌ 配置错误：' + str(exc))
        accounts = []
        config_error = True
        log('账号数量：0')
    for index, account in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        stage_number = 0
        def stage(name, operation):
            nonlocal stage_number
            stage_number += 1
            tick = time.monotonic()
            log(f'账号 {index} 阶段 {stage_number}：{name}')
            try:
                result = operation()
                stats['success'] += 1
                log(f'✅ {name}完成；耗时 {time.monotonic() - tick:.2f} 秒')
                return result
            except Exception as exc:
                stats['failed'] += 1
                message = str(exc) if isinstance(exc, TaskError) else '必需字段缺失、依赖缺失或响应结构异常'
                log(f'❌ {name}失败：{message}；耗时 {time.monotonic() - tick:.2f} 秒')
                raise TaskError('阶段失败') from None
        try:
            stage('参数校验', lambda: validate_account(account, action))
            if DRY:
                stage('断网流程预演', lambda: log('DRY_RUN_OK：参数有效；设备计算、登录、角色读取、签到和短信发送均不联网'))
                stats['skipped'] += 1
            else:
                did = stage('获取设备标识', lambda: account.get('did') or get_d_id())
                SECRETS.append(did)
                client = Client(did)
                if action == 'send-code':
                    stage('显式发送短信验证码', lambda: require_code(client.login_request(
                        AUTH + '/general/v1/send_phone_code', {'phone': account['phone'], 'type': 2}), 'status'))
                else:
                    stage('登录认证', lambda: client.login(account))
                    if os.environ.get('SKLAND_REFRESH', '0').lower() not in DISABLED:
                        stage('刷新签名令牌', client.refresh)
                    resp = stage('读取绑定角色', lambda: client.signed('/api/v1/game/player/binding'))
                    bindings = resp.get('data', {}).get('list')
                    if not isinstance(bindings, list):
                        raise TaskError('角色列表结构异常')
                    tasks = []
                    for game in bindings:
                        if game.get('appCode') not in games:
                            continue
                        if not isinstance(game.get('bindingList'), list):
                            raise TaskError('绑定角色结构异常')
                        for binding in game['bindingList']:
                            if game['appCode'] == 'arknights':
                                tasks.append(('arknights', binding))
                            else:
                                roles = binding.get('roles')
                                if not isinstance(roles, list):
                                    raise TaskError('终末地角色结构异常')
                                tasks.extend(('endfield', role) for role in roles)
                    if not tasks:
                        raise TaskError('没有可签到的绑定角色，不能确认业务成功')
                    for game, role in tasks:
                        identity = role.get('nickName') or role.get('nickname') or role.get('uid') or f'账号 {index}'
                        log('官方角色：' + str(identity))
                        def attendance(game=game, role=role):
                            if game == 'arknights':
                                if not role.get('gameId') or not role.get('uid'):
                                    raise TaskError('明日方舟签到参数缺失')
                                result = client.signed('/api/v1/game/attendance',
                                                       {'gameId': role['gameId'], 'uid': role['uid']})
                                awards = result['data']['awards']
                                reward = [str(a['resource']['name']) + '×' + str(a.get('count') or 1) for a in awards]
                            else:
                                if not role.get('roleId') or not role.get('serverId'):
                                    raise TaskError('终末地签到参数缺失')
                                result = client.signed('/web/v1/game/endfield/attendance', extra={
                                    'Content-Type': 'application/json', 'sk-game-role': f"3_{role['roleId']}_{role['serverId']}",
                                    'referer': 'https://game.skland.com/', 'origin': 'https://game.skland.com/'})
                                data = result['data']
                                reward = [str(data['resourceInfoMap'][a['id']]['name']) + '×' +
                                          str(data['resourceInfoMap'][a['id']]['count']) for a in data['awardIds']]
                            log('签到奖励：' + ('，'.join(reward) or '接口确认成功，无奖励明细'))
                        try:
                            stage(('明日方舟' if game == 'arknights' else '终末地') + '角色签到', attendance)
                        except TaskError:
                            continue
        except Exception as exc:
            if not isinstance(exc, TaskError) or str(exc) != '阶段失败':
                stats['failed'] += 1
                log('❌ 账号处理失败：' + (str(exc) if isinstance(exc, TaskError) else '响应结构异常'))
        ok = stats['failed'] == 0
        summary['success' if ok else 'failed'] += 1
        summary['steps_success'] += stats['success']
        summary['steps_failed'] += stats['failed']
        summary['skipped'] += stats['skipped']
        log(f"账号 {index} 统计：总任务 {sum(stats.values())}，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {time.monotonic() - account_start:.2f} 秒")
    summary['status'] = ('configuration-error' if config_error else
                         'partial-failure' if summary['failed'] and summary['success'] else
                         'failure' if summary['failed'] else 'dry-run' if DRY else 'success')
    summary['notification'] = notify(summary)
    summary['elapsedSeconds'] = round(time.monotonic() - start, 2)
    summary['finishTime'] = time.strftime('%Y-%m-%d %H:%M:%S')
    log('----------------------------------------')
    log(f"任务统计：账号 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；子任务成功 {summary['steps_success']}，已完成 0，跳过 {summary['skipped']}，失败 {summary['steps_failed']}")
    log(f"总耗时：{summary['elapsedSeconds']} 秒；完成时间：{summary['finishTime']}；通知：{summary['notification']}")
    log('最终状态：' + summary['status'])
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return 1 if config_error or summary['failed'] else 0

if __name__ == '__main__':
    sys.exit(run())
