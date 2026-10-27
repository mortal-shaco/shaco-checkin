#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: NewAPI 自动签到
# cron: 18 8 * * *
"""独立 NewAPI 签到（Python 3.9+，仅标准库）。

来源：Jasonliu-0/Newapi-checkin，checkin.py；MIT License。
参考同仓库 cf_bypass.py 的挑战检测、config_helper.py 的认证字段说明。
上游文件未附加版权声明；保留来源与许可，完整 MIT 许可见下文。

NEWAPI_ACCOUNTS：每个非空行一个 JSON 对象，url 为 HTTPS 站点根地址；
session、access_token 至少一个，或同时配置 login_username、login_password。
可选 user_id、cf_clearance、name。旧 JSON 数组仍兼容，但不使用逗号分隔账号。
也接受 URL#SESSION 或 URL#SESSION#ACCESS_TOKEN；使用 JSON 可无歧义保存 #。
在浏览器登录目标站点，从开发者工具 Application/Cookies 取得 session 值，
从个人设置生成系统访问令牌；user_id 从本人 /api/user/self 的 data.id 或
该请求的 new-api-user 头取得，不能从用户名猜测。cf_clearance 从本站 Cookie
读取，必须与获取它时的出口及 User-Agent 相符，不能保证绕过浏览器指纹验证。
NEWAPI_USER_AGENT 可设置获取 Cookie 时的 User-Agent。
CONFIG_URL/CONFIG_AUTH 兼容 HTTPS WebDAV 配置：数组或含 accounts 的对象；
认证为 token:令牌 或 用户名:密码。云端不可用时回退本地 NEWAPI_ACCOUNTS。
不读取/回写私有仓库文件，不导入上游模块，不安装或启动浏览器。
NEWAPI_TASKS=checkin,history（默认），也可只选择其中一项。
NEWAPI_DRY_RUN=1：只核对配置、打印执行计划，不发出任何网络请求，包括通知。
QINGLONG_NOTIFY=auto：默认仅显式列入 QINGLONG_NOTIFY_SCRIPTS 的脚本推送；
全局 1 强制开启，0 关闭。预演只生成脱敏通知，不调用通知模块。

安全范围：不执行 lanxiu 抽奖或 vsllm 翻卡（缺少接口证据且有额外状态变更），
不从云端覆盖通知配置，不输出原始响应。遇到必须浏览器求解的 CF/Turnstile
明确失败，请通过站点正常验证后更新凭据；不降级 TLS 或假定验证已通过。
原源码未带 cron；上述每天 08:17 为建议时间。

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
        _ql_notify_identities = ('241e7ff85e417257', 'scripts/newapi.py', 'newapi.py', 'newapi')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import contextlib
import fnmatch
import hashlib
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

TITLE = 'NewAPI 自动签到'
CATALOG = '241e7ff85e417257'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = set()


class TaskError(Exception):
    """只承载预先定义的脱敏错误。"""


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def valid_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise TaskError('地址格式错误，请配置 HTTPS 站点根地址')
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        raise TaskError('地址格式错误') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        raise TaskError('地址必须使用 HTTPS 且不能包含凭据、查询参数或片段')
    return value.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向其他地址转发认证头或 Cookie。


class HTTP:
    def __init__(self, dry=False):
        self.dry = dry
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, url, method='GET', headers=None, body=None):
        if self.dry:
            raise TaskError('预演禁止网络请求')
        valid_url(url.split('?', 1)[0])
        payload = None if body is None else json.dumps(body).encode('utf-8')
        request = urllib.request.Request(url, data=payload, method=method, headers=headers or {})
        try:
            try:
                response = self.opener.open(request, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超过 1 MiB 安全上限')
            text = raw.decode('utf-8', errors='replace')
            lower = text.lower()
            if ('just a moment' in lower or 'cf-challenge' in lower
                    or 'challenge-platform' in lower
                    or (status in (403, 503) and 'cloudflare' in lower)):
                raise TaskError('Cloudflare 验证拦截；请在站点完成正常验证并更新 Cookie，未签到成功')
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                raise TaskError(f'HTTP {status} 返回非 JSON；未输出原始内容') from None
            return status, data
        except TaskError:
            raise
        except Exception:
            raise TaskError('网络、TLS 或超时错误；请核对站点与网络，不自动重试状态变更请求') from None


def parse_accounts(raw):
    if not raw.strip():
        raise TaskError('缺少 NEWAPI_ACCOUNTS；请按说明配置凭据')
    if raw.lstrip().startswith('['):
        try:
            values = json.loads(raw)
        except ValueError:
            raise TaskError('旧账号数组不是有效 JSON') from None
        if not isinstance(values, list) or not values:
            raise TaskError('账号数组不能为空')
        return values
    values = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if line.startswith('{'):
                values.append(json.loads(line))
            else:
                url, credentials = line.split('#', 1)
                # 旧三字段格式；只拆开首个字段边界，令牌剩余文本保持原样。
                session, marker, token = credentials.partition('#')
                values.append({'url': url, 'session': session,
                               'access_token': token if marker else ''})
        except (ValueError, TypeError):
            values.append(None)  # 无效账号独立失败，不阻止后续账号。
    return values


def validate_account(account):
    if not isinstance(account, dict):
        raise TaskError('账号行不是有效 JSON 对象或旧式单账号配置')
    result = dict(account)
    result['url'] = valid_url(result.get('url'))
    fields = ('session', 'access_token', 'cf_clearance', 'login_username', 'login_password')
    for key in fields:
        value = result.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, str) or '\r' in value or '\n' in value:
            raise TaskError('凭据字段必须为不含换行的字符串')
        result[key] = value
        if value and key != 'login_username':
            SECRETS.add(value)
    if bool(result['login_username']) != bool(result['login_password']):
        raise TaskError('登录用户名与密码必须配套配置')
    if not (result['session'] or result['access_token'] or result['login_username']):
        raise TaskError('账号缺少 session、access_token 或配套登录凭据')
    uid = result.get('user_id')
    if uid is not None and (isinstance(uid, bool) or not str(uid).isdigit()):
        raise TaskError('user_id 必须为本人公开数字 UID，不可从用户名推测')
    return result


def load_accounts(dry):
    local = os.environ.get('NEWAPI_ACCOUNTS', '')
    config_url = os.environ.get('CONFIG_URL', '').strip()
    if config_url and dry:
        log('云端配置：预演跳过下载，仅核对本地占位账号')
    elif config_url:
        try:
            config_url = valid_url(config_url)
            auth = os.environ.get('CONFIG_AUTH', '')
            headers = {'Accept': 'application/json'}
            if auth.startswith('token:'):
                headers['Authorization'] = 'Bearer ' + auth[6:]
            elif ':' in auth:
                import base64
                headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
            elif auth:
                raise TaskError('CONFIG_AUTH 格式错误')
            status, data = HTTP().request(config_url, headers=headers)
            if status != 200:
                raise TaskError(f'云端配置 HTTP {status}')
            if isinstance(data, dict):
                data = data.get('accounts')
            if not isinstance(data, list) or not data:
                raise TaskError('云端配置缺少非空 accounts 数组')
            log('云端配置读取成功；忽略云端通知与执行选项')
            return data
        except TaskError as error:
            log(f'云端配置失败：{error}；尝试本地账号')
            if not local.strip():
                raise
    return parse_accounts(local)


def payload_ok(status, data):
    return status == 200 and isinstance(data, dict) and data.get('success') is True


class NewAPICheckin:
    def __init__(self, account):
        self.account = account
        self.base_url = account['url']
        self.http = HTTP()
        self.headers = {
            'Accept': 'application/json', 'Content-Type': 'application/json',
            'User-Agent': os.environ.get('NEWAPI_USER_AGENT') or
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cache-Control': 'no-store',
        }
        if account['access_token']:
            self.headers['Authorization'] = account['access_token']  # 保留令牌原始格式。
        if account.get('user_id') is not None:
            self.headers['new-api-user'] = str(account['user_id'])
        for name in ('session', 'cf_clearance'):
            if account[name]:
                host = urllib.parse.urlsplit(self.base_url).hostname
                self.http.cookies.set_cookie(http.cookiejar.Cookie(
                    0, name, account[name], None, False, host, False, False,
                    '/', True, True, None, True, None, None, {}, False))
        self.logged_in = False

    def login(self):
        if self.logged_in or not self.account['login_username']:
            raise TaskError('认证失败；请更新会话／令牌，或配置配套登录凭据')
        self.logged_in = True
        for cookie in list(self.http.cookies):
            if cookie.name in ('session', 'session_id'):
                self.http.cookies.clear(cookie.domain, cookie.path, cookie.name)
        status, data = self.http.request(self.base_url + '/api/user/login', 'POST', self.headers,
                                         {'username': self.account['login_username'],
                                          'password': self.account['login_password']})
        if not payload_ok(status, data) or not any(
                c.name in ('session', 'session_id') and c.value for c in self.http.cookies):
            raise TaskError('登录未获业务成功及有效会话；可能需要人工验证')
        info = data.get('data')
        if isinstance(info, dict) and str(info.get('id', '')).isdigit():
            self.headers['new-api-user'] = str(info['id'])
        # 登录续期后优先使用新会话，避免旧令牌继续覆盖有效会话。
        self.headers.pop('Authorization', None)
        log('登录续期成功；新会话仅保存在本次进程内')

    def request(self, path, method='GET'):
        status, data = self.http.request(self.base_url + path, method, self.headers)
        if status == 401:
            self.login()
            status, data = self.http.request(self.base_url + path, method, self.headers)
        if status != 200 or not isinstance(data, dict):
            raise TaskError(f'接口 HTTP {status} 或响应结构错误')
        return data

    def get_user_info(self):
        if not self.account['session'] and not self.account['access_token']:
            self.login()
        data = self.request('/api/user/self')
        if data.get('success') is not True or not isinstance(data.get('data'), dict):
            raise TaskError('用户信息业务校验失败；请核对凭据与 user_id')
        user = data['data']
        if str(user.get('id', '')).isdigit():
            self.headers['new-api-user'] = str(user['id'])
        return user

    def get_checkin_history(self):
        month = datetime.now().strftime('%Y-%m')
        data = self.request('/api/user/checkin?' + urllib.parse.urlencode({'month': month}))
        if data.get('success') is not True or not isinstance(data.get('data'), dict):
            raise TaskError('月度签到记录业务校验失败')
        return data['data']

    @staticmethod
    def solve_pow(prefix, difficulty):
        if (not isinstance(prefix, str) or len(prefix) > 4096
                or type(difficulty) is not int or not 0 <= difficulty <= 24):
            raise TaskError('PoW 挑战参数无效或超过安全计算上限 24 位')
        started = time.monotonic()
        for counter in range(0x100000000):
            if counter % 4096 == 0 and time.monotonic() - started > 20:
                raise TaskError('PoW 解算超过 20 秒安全预算')
            nonce = f'{counter:08x}'
            digest = hashlib.sha256((prefix + nonce).encode()).digest()
            if int.from_bytes(digest, 'big') >> (256 - difficulty) == 0:
                return nonce
        raise TaskError('PoW 解算未完成')

    def checkin(self):
        data = self.request('/api/user/checkin', 'POST')
        message = data.get('message', '')
        message = message.lower() if isinstance(message, str) else ''
        if data.get('success') is not True and 'pow' in message:
            challenge = self.request('/api/user/pow/challenge?action=checkin')
            ch = challenge.get('data')
            if challenge.get('success') is not True or not isinstance(ch, dict):
                raise TaskError('PoW 挑战业务校验失败')
            if not isinstance(ch.get('challenge_id'), str) or not ch['challenge_id']:
                raise TaskError('PoW 挑战缺少有效标识')
            nonce = self.solve_pow(ch.get('prefix'), ch.get('difficulty'))
            log('PoW 解算完成；不输出挑战、签名或 nonce')
            query = urllib.parse.urlencode({'pow_challenge': ch['challenge_id'], 'pow_nonce': nonce})
            data = self.request('/api/user/checkin?' + query, 'POST')
            message = data.get('message', '')
            message = message.lower() if isinstance(message, str) else ''
        if data.get('success') is True:
            return 'success', data.get('data') if isinstance(data.get('data'), dict) else {}
        if 'turnstile' in message:
            raise TaskError('站点要求 Turnstile 人工验证；独立 HTTP 任务无法解浏览器挑战')
        if any(k in message for k in ('已签到', '已经签到', '重复签到', 'already checked in', 'already signed in')):
            history = self.get_checkin_history()
            stats = history.get('stats')
            if isinstance(stats, dict) and stats.get('checked_in_today') is True:
                return 'alreadyComplete', {}
            raise TaskError('响应称已签到，但未取得今日已签记录，不能确认成功')
        raise TaskError('签到业务失败；请核对站点签到开关、凭据和验证要求')


def print_identity(user):
    parts = []
    for key in ('nickname', 'username', 'display_name', 'id'):
        value = user.get(key)
        if not isinstance(value, (str, int)) or isinstance(value, bool) or str(value) == '':
            continue
        value = str(value)
        # 官方公开身份按原值显示；控制字符转义，明确的手机号或凭据不输出。
        if any(secret in value for secret in SECRETS) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
            continue
        parts.append(f'{key}={json.dumps(value, ensure_ascii=False)}')
    log('官方账号身份：' + ('；'.join(parts) if parts else '未提供可公开身份，使用账号序号'))


def notify_enabled():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    selected = os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '')
    names = (CATALOG, Path(__file__).name, 'scripts/' + Path(__file__).name, TITLE)
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in re.split(r'[,;\s]+', selected) if pattern for name in names)


def notification_worker():
    """独立子进程限制通知时间、捕获第三方输出，失败不影响业务。"""
    try:
        message = json.load(sys.stdin)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                module = None
            if module is not None and callable(getattr(module, 'send', None)):
                return 1 if module.send(TITLE, message['body']) is False else 0
            locations = []
            directory = os.environ.get('QINGLONG_NOTIFY_DIR')
            if directory:
                locations.append(Path(directory) / 'notify.py')
            locations.extend((Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')))
            for path in locations:
                if not path.is_file():
                    continue
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if callable(getattr(module, 'send', None)):
                    return 1 if module.send(TITLE, message['body']) is False else 0
        return 1
    except BaseException:
        return 1


def notify(summary, dry):
    if not notify_enabled():
        return '已按全局开关或脚本选择策略关闭'
    body = (f"账号总数 {summary['accounts']}，成功 {summary['success']}，"
            f"失败 {summary['failed']}；状态 {summary['status']}；"
            f"任务成功 {summary['tasks']['success']}，已完成 {summary['tasks']['alreadyComplete']}，"
            f"跳过 {summary['tasks']['skipped']}，失败 {summary['tasks']['failure']}")
    if dry:
        log('脱敏通知预演：' + body)
        return '预演已生成；禁止网络，未投递'
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--notify-worker'],
                                input=json.dumps({'body': body}), text=True, capture_output=True,
                                timeout=20, check=False)
        return '已调用青龙通知' if result.returncode == 0 else '通知不可用或发送失败；保留业务退出码'
    except Exception:
        return '通知异常或超时；保留业务退出码'


def main():
    started = time.monotonic()
    dry = os.environ.get('NEWAPI_DRY_RUN', '').strip().lower() in TRUE
    log('=' * 48)
    log(TITLE + f' | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log('运行模式：' + ('断网预演（不证明真实签到成功）' if dry else '正式执行'))
    results = []
    config_error = False
    tasks = []
    configuration_start = time.monotonic()
    log('[1/1] 全局阶段：读取并核对任务配置')
    try:
        tasks = list(dict.fromkeys(x.strip() for x in os.environ.get(
            'NEWAPI_TASKS', 'checkin,history').split(',') if x.strip()))
        if not tasks or any(x not in ('checkin', 'history') for x in tasks):
            raise TaskError('NEWAPI_TASKS 仅允许 checkin、history，至少选择一项')
        accounts = load_accounts(dry)
    except TaskError as error:
        log('❌ 配置错误：' + str(error))
        accounts = []
        config_error = True
    log(f'账号数量：{len(accounts)}')
    log(f'[1/1] 全局配置阶段结束；耗时 {time.monotonic()-configuration_start:.2f}s')
    for raw in accounts:
        if isinstance(raw, dict):
            for key in ('session', 'access_token', 'cf_clearance', 'login_password'):
                if isinstance(raw.get(key), str) and raw[key]:
                    SECRETS.add(raw[key])
    for index, raw in enumerate(accounts, 1):
        begin = time.monotonic()
        counts = {'total': len(tasks), 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
        log(f'----- 账号 {index}/{len(accounts)} -----')
        stage = time.monotonic()
        try:
            account = validate_account(raw)
            log(f'[1/{len(tasks)+1}] 参数核对通过；耗时 {time.monotonic()-stage:.2f}s')
        except TaskError as error:
            log(f'[1/{len(tasks)+1}] ❌ 参数错误：{error}；耗时 {time.monotonic()-stage:.2f}s')
            counts['failure'] = len(tasks)
            config_error = True
            account = None
        client = None
        if account is not None and not dry:
            client = NewAPICheckin(account)
            info_start = time.monotonic()
            try:
                print_identity(client.get_user_info())
                log(f'用户信息读取成功；耗时 {time.monotonic()-info_start:.2f}s')
            except TaskError as error:
                log(f'⚠️ 用户信息读取失败：{error}；继续独立校验签到；耗时 {time.monotonic()-info_start:.2f}s')
        if account is not None:
            for number, task in enumerate(tasks, 2):
                stage = time.monotonic()
                log(f'[{number}/{len(tasks)+1}] 阶段 {task} 开始')
                try:
                    if dry:
                        counts['skipped'] += 1
                        log(f'⏭️ DRY_RUN_OK：已核对 {task} 执行计划；未发送请求')
                    elif task == 'checkin':
                        state, data = client.checkin()
                        counts[state] += 1
                        log('✅ 签到业务成功' if state == 'success' else '☑️ 今日已签到（已核对记录）')
                        reward = data.get('quota_awarded')
                        date = data.get('checkin_date')
                        if isinstance(reward, (int, float)) and not isinstance(reward, bool):
                            log(f'签到奖励额度：{reward}')
                        if isinstance(date, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                            log(f'签到日期：{date}')
                    else:
                        history = client.get_checkin_history()
                        stats = history.get('stats')
                        if not isinstance(stats, dict):
                            raise TaskError('月度记录缺少 stats 字段')
                        safe_stats = {key: stats[key] for key in ('checkin_count', 'total_quota', 'checked_in_today')
                                      if key in stats and isinstance(stats[key], (int, float, bool))}
                        log('✅ 月度统计读取成功：' + json.dumps(safe_stats, ensure_ascii=False))
                        counts['success'] += 1
                except TaskError as error:
                    counts['failure'] += 1
                    log(f'❌ {error}')
                except Exception:
                    counts['failure'] += 1
                    log('❌ 未预期响应或执行异常；不输出原始响应和异常详情')
                log(f'[{number}/{len(tasks)+1}] 阶段 {task} 结束；耗时 {time.monotonic()-stage:.2f}s')
        elapsed = round(time.monotonic() - begin, 2)
        results.append({'account': index, 'ok': counts['failure'] == 0, 'tasks': counts, 'seconds': elapsed})
        log(f"账号 {index} 统计：总任务 {counts['total']}，成功 {counts['success']}，"
            f"已完成 {counts['alreadyComplete']}，跳过 {counts['skipped']}，失败 {counts['failure']}；耗时 {elapsed}s")
    failed = sum(not result['ok'] for result in results)
    code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and failed < len(results)
              else 'failure' if failed else 'dry-run' if dry else 'success')
    aggregate = {key: sum(result['tasks'][key] for result in results)
                 for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    summary = {'applicationKey': 'newapi', 'status': status, 'dryRun': dry, 'accounts': len(results),
               'success': sum(result['ok'] for result in results) if not dry else 0,
               'failed': failed, 'dryRunAccounts': sum(result['ok'] for result in results) if dry else 0,
               'tasks': aggregate, 'results': results, 'exitCode': code}
    summary['notification'] = notify(summary, dry)
    summary['seconds'] = round(time.monotonic() - started, 2)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    log('-' * 48)
    log(f"账号结果：总数 {len(results)}，成功 {summary['success']}，失败 {failed}，预演通过 {summary['dryRunAccounts']}")
    log('子任务统计：' + json.dumps(aggregate, ensure_ascii=False))
    log(f"通知状态：{summary['notification']}")
    log(f"总耗时 {summary['seconds']}s；完成时间 {summary['finishTime']}；最终状态 {status}")
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    if sys.argv[1:] == ['--notify-worker']:
        sys.exit(notification_worker())
    sys.exit(main())
