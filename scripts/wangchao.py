#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 望潮阅读有礼
# cron: 11 2 * * *
# author: qingfeng
# 上游：Rookie-wb-WH/ql_scripts，wangchao.py
# 上游版本：08e5c06461c4a0112ea3735f48fe671734bb7707；有效许可证：MIT
# MIT License
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
# 原始更新说明：2025.01.02 删除失效活动；2024.09.30 修复错误；
# 2024.09.29 修复抽奖失败问题、添加新活动；2024.08.22 更新阅读参数；
# 2024.07.16 采用随机UA、修复错误。
"""望潮每日阅读有礼（Python 3.9+）。

参数获取：在官方望潮 App 注册、设置登录密码。进入首页“阅读有礼”，
按官方页面要求点击右下角抽奖并绑定本人支付宝账号；本脚本不绑定或修改支付资料。
WangChao：每个非空行一个“登录手机号#密码”，只按第一个 # 切分，密码后续字符保留。
旧版 && 多账号格式已迁移为换行；不得把 &&、@ 用作账号分隔符。
WANGCHAO_DRY_RUN=1：完全断网预演，不登录、不读取远程内容、不修改账号。
WANGCHAO_LOTTERY=1：明确启用每日一次抽奖（消耗次数），默认 0。
WANGCHAO_BONUS=1：明确启用活动入口浏览，默认 0；不重放随机文章阅读来虚增次数。
QINGLONG_NOTIFY 默认 1；可设 0/false/no/off 关闭。可选 QINGLONG_NOTIFY_DIR 指向
青龙通知模块目录。通知缺失或失败不改变业务退出码；预演通知也禁止网络。
实时运行依赖青龙 Python 依赖管理中安装公共包 pycryptodome、gmssl；不自动安装。
保留登录、进入 App、每日阅读、阅读进度确认、可选活动入口浏览、可选抽奖、
最近十条抽奖记录。上游停用的“诗韵望潮”答题/红包活动不自动复活。
接口均依据此上游快照恢复，断网验证不能确认当前活动可用或真实业务成功。
"""

import base64
import contextlib
import datetime as dt
import hashlib
import hmac
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = '望潮阅读有礼'
APP = 'https://vapp.taizhou.com.cn'
PASSPORT = 'https://passport.tmuyun.com'
READ = 'https://xmt.taizhou.com.cn'
DRAW = 'https://srv-app.taizhou.com.cn'
READ_REF = READ + '/readingLuck-v3/'
DRAW_REF = DRAW + '/luckdraw-ra-1/'
RSA_KEY = ('MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQD6XO7e9YeAOs+cFqwa7ETJ+'
           'WXizPqQeXv68i5vqw9pFREsrqiBTRcg7wB0RIp3rJkDpaeVJLsZqYm5TW7FWx/i'
           'OiXFc+zCPvaKZric2dXCw27EvlH5rq+zwIPDAJHGAfnn1nmQH7wR3PCatEIb8pz5'
           'GFlTHMlluw4ZYmnOwg+thwIDAQAB')
SM2_KEY = ('A50803A27F000D6B310607EBA2A1C899E82872C0B538CA41DB6F0183B4C7E164'
           'DAFC6946ABF93C8AF1C0AD96D0E770D29264EF9F907DDBAE97A2A0BB1036D4AC')
REWARDS = dict(zip(('234', '233', '232', '231', '230', '229', '227', '228',
                        '226', '225', '224', '223', '442'),
                       ('66.66元', '100元', '50元', '20元', '16.66元', '8.88元',
                        '6.66元', '3.66元', '1.66元', '谢谢参与', '0.66元', '0.33元', '0.16元')))
OFF = {'0', 'false', 'no', 'off'}
SECRETS = set()


class TaskError(Exception):
    pass


def block_network():
    def denied(*args, **kwargs):
        raise TaskError('预演模式禁止网络')
    socket.socket = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied


def flag(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value not in OFF | {'1', 'true', 'yes', 'on'}:
        raise TaskError(name + ' 仅支持 1/0、true/false、yes/no、on/off')
    return value not in OFF


def clean(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已脱敏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已脱敏]', text)
    return ''.join(ch if ch.isprintable() else '\\u%04x' % ord(ch) for ch in text)


def log(message):
    print('[' + dt.datetime.now().strftime('%H:%M:%S') + '] ' + clean(message), flush=True)


def required(value):
    if value is None or value == '' or isinstance(value, bool):
        raise TaskError('响应缺少必要字段')
    return value


def obj(value):
    if not isinstance(value, dict):
        raise TaskError('响应对象结构不符合上游契约')
    return value


def seq(value):
    if not isinstance(value, list):
        raise TaskError('响应列表结构不符合上游契约')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向被拒绝，未向其他地址发送凭据')


class Client:
    def __init__(self, phone, password):
        self.phone, self.password = phone, password
        self.session = ''
        self.account_id = ''
        self.identity = ''
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))
        self.device = str(uuid.uuid4())
        model = random.choice(('M1903F2A', 'M2001J2E', 'M2001J2C', 'M2001J1E', 'M2001J1C',
            'M2002J9E', 'M2011K2C', 'M2102K1C', 'M2101K9C', '2107119DC', '2201123C',
            '2112123AC', '2201122C', '2211133C', '2210132C', '2304FPN6DC', '23127PN0CC',
            '24031PN0DC', '23090RA98C', '2312DRA50C', '2312CRAD3C', '2312DRAABC',
            '22101316UCP', '22101316C'))
        android = random.choice((11, 12, 13, 14))
        self.ua = f'ANDROID;{android};10019;6.0.2;1.0;null;{model}'
        self.common_ua = f'6.0.2;{self.device};Xiaomi {model};Android;{android};xiaomi;6.10.0'
        self.read_ua = (f'Mozilla/5.0 (Linux; Android {android}; {model} Build/RP1A.200720.011; wv) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.85 Mobile '
            'Safari/537.36;xsb_wangchao;xsb_wangchao;6.0.2;native_app;6.10.0')
        SECRETS.update((phone, password, self.device))

    def request(self, base, path, code, method='GET', params=None, body=None, headers=None):
        if base not in (APP, PASSPORT, READ, DRAW) or not path.startswith('/'):
            raise TaskError('接口地址不在固定服务范围内')
        url = base + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        data = None if body is None else urllib.parse.urlencode(body).encode('utf-8')
        if method == 'POST' and data is None:
            data = b''
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        req.add_header('Accept', 'application/json')
        req.add_header('Accept-Encoding', 'identity')
        if method == 'POST':
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态不符合契约')
                payload = response.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise TaskError('接口响应过大')
            result = obj(json.loads(payload.decode('utf-8')))
        except urllib.error.HTTPError as exc:
            raise TaskError('HTTP 请求失败，状态码 ' + str(exc.code)) from None
        except (urllib.error.URLError, OSError, ValueError):
            raise TaskError('网络、超时或响应解析失败；未输出响应内容') from None
        if type(result.get('code')) is not int or result['code'] != code:
            raise TaskError('业务码未确认成功；请在官方 App 核对凭据、活动或接口状态')
        for cookie in self.jar:
            SECRETS.add(cookie.value)
        log('接口 ' + path.split('?')[0] + '：HTTP 200，业务码 ' + str(code) + ' 已确认')
        return result.get('data')

    def app(self, path, method='GET', params=None, body=None):
        request_id, timestamp = str(uuid.uuid4()), str(int(time.time() * 1000))
        signature = hashlib.sha256(
            f'{path}&&{self.session}&&{request_id}&&{timestamp}&&FR*r!isE5W&&64'.encode()).hexdigest()
        headers = {'X-SESSION-ID': self.session, 'X-REQUEST-ID': request_id,
            'X-TIMESTAMP': timestamp, 'X-SIGNATURE': signature, 'X-TENANT-ID': '64',
            'User-Agent': self.common_ua}
        if self.account_id != '':
            headers.update({'X-ACCOUNT-ID': str(self.account_id), 'Referer': READ_REF})
        return self.request(APP, path, 0, method, params, body, headers)

    def web_headers(self, draw=False):
        return {'User-Agent': self.read_ua, 'X-Requested-With': 'com.shangc.tiennews.taizhou',
                'Referer': DRAW_REF if draw else READ_REF,
                **({'Origin': DRAW} if draw else {})}

    def cookie_check(self, base):
        host = urllib.parse.urlparse(base).hostname
        if not any(c.name == 'JSESSIONID' and c.value and
                   (c.domain.lstrip('.') == host or host.endswith('.' + c.domain.lstrip('.')))
                   for c in self.jar):
            raise TaskError('登录响应没有对应服务的会话 Cookie')

    def login(self):
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Cipher import PKCS1_v1_5
            from gmssl.sm2 import CryptSM2
            from gmssl import func
        except ImportError:
            raise TaskError('缺少公共依赖，请在青龙 Python 依赖管理安装 pycryptodome、gmssl') from None
        cipher = CryptSM2(private_key='', public_key=SM2_KEY, mode=1)
        def encrypt_read(data):
            # gmssl 默认随机数源改为系统安全随机数，不更改密文协议。
            original_random = func.random_hex
            try:
                func.random_hex = lambda length: ''.join(secrets.choice('0123456789abcdef') for _ in range(length))
                return cipher.encrypt(data)
            finally:
                func.random_hex = original_random
        self.encrypt_read = encrypt_read
        init = obj(self.request(PASSPORT, '/web/init', 0, params={'client_id': '10019'},
            headers={'User-Agent': self.common_ua, 'X-REQUEST-ID': str(uuid.uuid4()),
                     'Cache-Control': 'no-cache'}))
        key = str(required(obj(init.get('client')).get('signature_key')))
        SECRETS.add(key)
        initialized = obj(self.app('/api/account/init', 'POST'))
        self.session = str(required(obj(initialized.get('session')).get('id')))
        SECRETS.add(self.session)
        encrypted = base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(RSA_KEY))).encrypt(
            self.password.encode('utf-8'))).decode('ascii')
        request_id = str(uuid.uuid4())
        body = {'client_id': '10019', 'password': encrypted, 'phone_number': self.phone}
        message = f'post%%/web/oauth/credential_auth?client_id=10019&password={encrypted}&phone_number={self.phone}%%{request_id}%%'
        signature = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
        time.sleep(random.uniform(1, 3))
        auth = obj(self.request(PASSPORT, '/web/oauth/credential_auth', 0, 'POST', body=body,
            headers={'User-Agent': self.ua, 'X-REQUEST-ID': request_id, 'X-SIGNATURE': signature}))
        authorization = required(obj(auth.get('authorization_code')).get('code'))
        SECRETS.add(str(authorization))
        logged = obj(self.app('/api/zbtxz/login', 'POST', body={'check_token': '',
            'code': authorization, 'token': '', 'type': -1, 'union_id': ''}))
        account = obj(logged.get('account'))
        self.account_id = required(account.get('id'))
        self.session = str(required(obj(logged.get('session')).get('id')))
        SECRETS.add(self.session)
        for field in ('nick_name', 'nickname', 'username', 'display_name', 'uid', 'id'):
            if account.get(field) is not None and account[field] != '':
                self.identity = clean(account[field])
                log('官方账号身份：' + self.identity)
                break
        return '登录成功，会话已验证'

    def reading_login(self):
        self.request(READ, '/prod-api/user-read/app/login', 200,
            params={'id': self.account_id, 'sessionId': self.session, 'deviceId': self.device},
            headers=self.web_headers())
        self.cookie_check(READ)
        return '阅读会话已验证'

    def reading_list(self):
        date = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%d')
        data = obj(self.request(READ, '/prod-api/user-read/list/' + date, 200,
            headers=self.web_headers()))
        articles = seq(data.get('articleIsReadList'))
        total, done = data.get('sum'), data.get('completedCount')
        if type(total) is not int or type(done) is not int or not 0 <= done <= total:
            raise TaskError('阅读统计字段不符合契约')
        for article in articles:
            obj(article)
            if type(article.get('isRead')) not in (bool, int) or article['isRead'] not in (0, 1):
                raise TaskError('阅读状态字段不符合契约')
        return articles, total, done

    def mark_read(self, article):
        payload = {'timestamp': str(int(time.time() * 1000)),
            'articleId': str(required(article.get('id'))), 'accountId': self.account_id}
        # JS JSON.stringify + SM2 doEncrypt(..., 1): C1(无04前缀) || C3 || C2。
        encrypted = self.encrypt_read(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode())
        if not encrypted:
            raise TaskError('阅读加密失败，未发送请求')
        self.request(READ, '/prod-api/already-read/article/new', 200,
            params={'signature': encrypted.hex()}, headers=self.web_headers())

    def bonus(self):
        focus = seq(obj(self.app('/api/app_nav/list')).get('focus'))
        recommendation = next((obj(x).get('nav_parameter') for x in focus
                               if obj(x).get('name') == '推荐'), None)
        required(recommendation)
        channel = obj(self.app('/api/article/channel_list', params={'channel_id': recommendation,
            'isDiFangHao': 'false', 'is_new': 'true', 'list_count': '0', 'size': '20'}))
        groups = seq(channel.get('article_list'))
        found = {}
        for group in groups:
            for entry in seq(obj(group).get('column_news_list', [])):
                entry = obj(entry)
                if entry.get('list_title') in ('阅读有礼', '诗韵望潮'):
                    match = re.search(r'[?&]id=(\d+)', str(entry.get('url', '')))
                    if match:
                        found[entry['list_title']] = match.group(1)
        if not found:
            raise TaskError('未找到上游活动入口；未猜测活动参数')
        for name, article_id in found.items():
            obj(self.app('/api/article/detail', params={'id': article_id}))
            log('活动入口 ' + name + '：浏览已确认，不重放阅读记录')
        return '活动入口浏览完成；未虚增次数'

    def draw_login(self):
        self.request(DRAW, '/tzrb/user/loginWC', 200,
            params={'accountId': self.account_id, 'sessionId': self.session}, headers=self.web_headers(True))
        self.cookie_check(DRAW)
        return '抽奖服务会话已验证'

    def eligibility(self):
        date = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%d')
        return self.request(READ, '/prod-api/user-read-count/count/' + date, 200,
                            headers=self.web_headers())

    def lottery(self):
        eligible = self.eligibility()
        if type(eligible) is not int or eligible != 1:
            raise TaskError('接口未确认当前具备抽奖资格，未消耗次数')
        time.sleep(random.uniform(3, 5))
        prize = self.request(DRAW, '/tzrb/userAwardRecordUpgrade/saveUpdate', 200, 'POST',
            params={'activityId': '67', 'sessionId': 'undefined', 'sig': 'undefined', 'token': 'undefined'},
            headers=self.web_headers(True))
        if type(prize) not in (int, str) or str(prize) not in REWARDS:
            raise TaskError('抽奖响应奖品字段不符合上游契约；不重试，避免重复消耗次数')
        return '抽奖成功，本次获得：' + REWARDS[str(prize)]

    def history(self):
        time.sleep(random.uniform(3, 5))
        data = obj(self.request(DRAW, '/tzrb/userAwardRecordUpgrade/pageList', 200,
            params={'pageSize': 10, 'pageNum': 1, 'activityId': 67}, headers=self.web_headers(True)))
        records = seq(data.get('records'))
        for item in records[:10]:
            item = obj(item)
            log('抽奖记录：' + clean(required(item.get('createTime'))) + ' ' +
                clean(required(item.get('awardName'))))
        return '最近十条抽奖记录查询成功，共 ' + str(min(len(records), 10)) + ' 条'


class AccountRun:
    def __init__(self, number, dry):
        self.number, self.dry = number, dry
        self.started = time.monotonic()
        self.counts = dict.fromkeys(('success', 'alreadyComplete', 'skipped', 'failure'), 0)
        self.steps = []

    def stage(self, name, action=None, skip=None, preflight=False):
        index = len(self.steps) + 1
        begin = time.monotonic()
        log(f'账号 {self.number} 阶段 {index}：{name} 开始')
        state, detail = 'success', ''
        try:
            if skip:
                state, detail = 'skipped', skip
            elif self.dry and not preflight:
                state, detail = 'skipped', '断网预演：已检查执行计划，未执行业务请求'
            else:
                returned = action()
                if isinstance(returned, tuple):
                    state, detail = returned
                else:
                    detail = returned or '业务操作已验证'
        except TaskError as exc:
            state, detail = 'failure', str(exc)
        except Exception:
            state, detail = 'failure', '本地处理或响应契约异常，已隐藏异常详情'
        elapsed = round(time.monotonic() - begin, 3)
        self.counts[state] += 1
        self.steps.append({'stage': index, 'name': name, 'status': state, 'seconds': elapsed,
                           'detail': clean(detail)})
        icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️', 'failure': '❌'}[state]
        log(f'账号 {self.number} 阶段 {index}：{name} {icon} {detail}（耗时 {elapsed:.3f} 秒）')
        return state != 'failure' and not skip

    def finish(self):
        seconds = round(time.monotonic() - self.started, 3)
        log(f'账号 {self.number} 统计：总任务 {len(self.steps)}，成功 {self.counts["success"]}，'
            f'已完成 {self.counts["alreadyComplete"]}，跳过 {self.counts["skipped"]}，'
            f'失败 {self.counts["failure"]}，耗时 {seconds:.3f} 秒')
        return {'account': self.number, 'status': 'failure' if self.counts['failure'] else
                ('dry-run' if self.dry else 'success'), 'statistics': self.counts,
                'seconds': seconds, 'steps': self.steps}


def run_account(number, line, dry, bonus, lottery):
    run = AccountRun(number, dry)
    phone, delimiter, password = line.partition('#')
    phone = phone.strip()
    SECRETS.update((phone, password))
    valid = bool(delimiter and re.fullmatch(r'1[3-9]\d{9}', phone) and password and
                 len(password.encode('utf-8')) <= 117)
    if not valid:
        run.stage('账号参数检查', lambda: (_ for _ in ()).throw(
            TaskError('每行必须为登录手机号#非空密码，密码 UTF-8 不超过 117 字节')),
            preflight=True)
        return run.finish()
    client = None if dry else Client(phone, password)
    logged = run.stage('账号登录', None if dry else client.login)
    run.stage('进入 App', None if dry else lambda: (client.app('/api/app_feature_switch/list'),
              '进入 App 成功')[1], skip=None if logged else '登录失败，跳过依赖步骤')
    reading = run.stage('阅读服务登录', None if dry else client.reading_login,
                        skip=None if logged else '登录失败，跳过依赖步骤')
    articles = []
    complete = False
    if reading and not dry:
        def fetch_tasks():
            nonlocal articles, complete
            articles, total, done = client.reading_list()
            complete = done == total
            return f'今日已阅读 {done} 篇，共 {total} 篇'
        reading = run.stage('获取每日阅读任务', fetch_tasks)
    else:
        run.stage('获取每日阅读任务', skip=None if reading else '阅读登录失败')
    if dry:
        run.stage('浏览文章并提交阅读记录')
    elif reading:
        for index, article in enumerate(articles, 1):
            if article['isRead']:
                run.stage(f'阅读文章 {index}', lambda: ('alreadyComplete', '接口确认已读'))
                continue
            def read_one(item=article):
                data = obj(client.app('/api/article/detail', params={'id': str(required(item.get('newsId')))}))
                obj(data.get('article'))
                client.mark_read(item)
                return '文章浏览及阅读记录已确认'
            run.stage(f'阅读文章 {index}', read_one)
            time.sleep(random.uniform(0.3, 0.8))
        complete = False
        def verify():
            nonlocal complete
            _, total, done = client.reading_list()
            if done != total:
                raise TaskError(f'阅读未全部完成：{done}/{total}')
            complete = True
            return '阅读任务全部完成，进度已复查'
        run.stage('核验每日阅读进度', verify)
    else:
        run.stage('浏览及核验阅读任务', skip='缺少阅读任务或会话')
    run.stage('活动入口浏览', None if dry else client.bonus,
        skip='WANGCHAO_BONUS 默认关闭' if not bonus else (None if logged else '登录失败'))
    draw = run.stage('抽奖服务登录', None if dry else client.draw_login,
                     skip=None if logged else '登录失败')
    run.stage('每日一次抽奖', None if dry else client.lottery,
        skip='WANGCHAO_LOTTERY 默认关闭，不消耗次数' if not lottery else
             (None if draw and (dry or complete) else '会话或阅读进度未通过核验'))
    if lottery and not dry and (not draw or not complete) and not run.counts['failure']:
        run.stage('抽奖前置条件', lambda: (_ for _ in ()).throw(TaskError('抽奖前置条件未确认')))
    run.stage('最近十条抽奖记录', None if dry else client.history, skip=None if draw else '抽奖服务登录失败')
    return run.finish()


def notify_worker():
    if os.getenv('WANGCHAO_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}:
        block_network()
        # 不允许通知模块在预演期间间接启动网络命令。
        def audit(event, args):
            if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec') or event.startswith('socket.'):
                raise TaskError('预演通知禁止网络及外部程序')
        sys.addaudithook(audit)
    payload = json.loads(sys.stdin.read())
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            module = importlib.import_module('notify')
            module.send(TITLE, payload['body'])
            return 0
        except ImportError:
            pass
        except Exception:
            return 1
        paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths.extend((Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')))
        for path in paths:
            if path.is_file():
                try:
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.send(TITLE, payload['body'])
                    return 0
                except Exception:
                    return 1
    return 1


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in OFF:
        log('通知：已按 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    # 独立进程限制通知耗时，隔离模块输出；不把账号凭据传入通知进程。
    env = {key: value for key, value in os.environ.items()
           if key.startswith(('QINGLONG_', 'PUSH_', 'BARK_', 'TG_', 'DD_', 'QYWX_', 'SMTP_',
                              'GOTIFY_', 'PUSHDEER_', 'WX_', 'FS_', 'NTFY_', 'SERVERCHAN_'))
           or key in ('PATH', 'PYTHONPATH', 'LANG', 'HOME', 'SENDKEY', 'PUSH_KEY', 'SCKEY')}
    env['WANGCHAO_DRY_RUN'] = '1' if dry else '0'
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--notify'],
            input=json.dumps({'body': body}, ensure_ascii=False), text=True, capture_output=True,
            timeout=25, env=env, check=False)
        if result.returncode == 0:
            log('通知：脱敏总结已交给青龙 notify.send' + ('（断网预演）' if dry else ''))
            return 'delivered'
    except (OSError, subprocess.TimeoutExpired):
        pass
    log('⚠️ 通知模块不可用、发送失败或预演网络被阻止；保留业务退出码')
    return 'unavailable-or-failed'


def main():
    started, begin = dt.datetime.now().isoformat(timespec='seconds'), time.monotonic()
    # 最先读取预演开关，错误开关也不得意外联网。
    dry = os.getenv('WANGCHAO_DRY_RUN', '0').strip().lower() not in OFF
    if dry:
        block_network()
    lines = [line for line in os.getenv('WangChao', '').splitlines() if line.strip()]
    for line in lines:
        phone, _, password = line.partition('#')
        SECRETS.update((phone.strip(), password))
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + started)
    log('运行模式：' + ('断网预演' if dry else '实时运行'))
    log('账号数量：' + str(len(lines)))
    results, configuration_error = [], False
    try:
        dry = flag('WANGCHAO_DRY_RUN')
        bonus, lottery = flag('WANGCHAO_BONUS'), flag('WANGCHAO_LOTTERY')
        if not lines:
            raise TaskError('未配置 WangChao；请填写每行一个登录手机号#密码')
        for number, line in enumerate(lines, 1):
            try:
                results.append(run_account(number, line, dry, bonus, lottery))
            except Exception:
                failure = AccountRun(number, dry)
                failure.stage('账号处理异常', lambda: (_ for _ in ()).throw(
                    TaskError('账号处理发生本地异常，详情已隐藏，继续其他账号')), preflight=True)
                results.append(failure.finish())
    except TaskError as exc:
        configuration_error = True
        log('❌ 配置错误：' + str(exc))
    except Exception:
        configuration_error = True
        log('❌ 配置或执行异常，详情已隐藏')
    failed = sum(r['status'] == 'failure' for r in results)
    passed = len(results) - failed
    status = 'configuration-error' if configuration_error else (
        'partial-failure' if failed and passed else 'failure' if failed else 'dry-run' if dry else 'success')
    counts = {name: sum(r['statistics'][name] for r in results)
              for name in ('success', 'alreadyComplete', 'skipped', 'failure')}
    exit_code = 1 if configuration_error or failed else 0
    log('----------------------------------------')
    log(f'账号统计：总数 {len(lines)}，成功 {passed if not dry else 0}，预演通过 {passed if dry else 0}，失败 {failed}')
    log('子任务统计：' + '，'.join(f'{key}={value}' for key, value in counts.items()))
    body = (f'{TITLE}：状态 {status}；账号总数 {len(lines)}，成功数 {passed if not dry else 0}，'
            f'预演通过数 {passed if dry else 0}，失败数 {failed}；配置错误 {int(configuration_error)}。'
            + ('预演未执行任何业务请求，不代表真实业务成功。' if dry else ''))
    notification = notify_summary(body, dry)
    finished, seconds = dt.datetime.now().isoformat(timespec='seconds'), round(time.monotonic() - begin, 3)
    log('总耗时：' + str(seconds) + ' 秒；完成时间：' + finished)
    log('最终状态：' + status + '；业务退出码：' + str(exit_code))
    if dry and not exit_code:
        log('DRY_RUN_OK：断网预演通过')
    elif not exit_code:
        log('望潮任务成功：所有启用的业务步骤已验证')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'dryRun': dry,
        'accountCount': len(lines), 'successCount': passed if not dry else 0,
        'dryRunCount': passed if dry else 0, 'failureCount': failed,
        'configurationError': configuration_error, 'statistics': counts, 'accounts': results,
        'startedAt': started, 'finishedAt': finished, 'seconds': seconds,
        'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    if sys.argv[1:] == ['--notify']:
        try:
            sys.exit(notify_worker())
        except Exception:
            sys.exit(1)
    sys.exit(main())
