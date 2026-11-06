# -*- coding: utf-8 -*-
# name: 芯幻签到
# cron: 5 10 * * *
# new Env('芯幻签到');
# 来源 zephyr-xiao/qinglong-script，作者 zephyr_xiao
# 原路径 xhcyv_checkin/xhcyv_checkin.py
# 上游提交 faba139086e3fc0c3f86b0cc9281b126947353e3
# SPDX-License-Identifier: MIT
"""芯幻每日签到。Python 3，青龙 Python 依赖 requests，验证码可选 ddddocr。

XHCYV_ACCOUNTS 必填，每个非空行一个账号。账号#密码，也兼容账号:密码、
账号&密码，按最早出现的字段分隔符只切一次，后续密码原样保留。
也可每行直接填写 x_bbs_token（JWT，以 eyJ 开头）。登录 https://xhcyv.com，
在浏览器开发者工具 Application/Cookies 复制本站 x_bbs_token，勿分享凭据。
账号密码来自本人注册信息。验证码或两步验证无法自动完成时可改用 Cookie 凭证。
兼容 XHCYV_TOKEN（每行一个，不再用 & 分账号）、XHCYV_ACCOUNT/XHCYV_PASSWORD。
兼容变量与主变量同时存在时保留上游的追加语义，建议只使用主变量避免重复执行。

XHCYV_DRY_RUN=1 完全断网预演，--check 在线查询凭证和签到状态，不提交签到。
XHCYV_TIMEOUT 默认30秒，XHCYV_PROXY 可配置代理（或标准 HTTPS_PROXY/HTTP_PROXY）。
XHCYV_DEBUG=1 只输出脱敏请求步骤，不输出响应、签名、凭据或验证码。
XHCYV_CACHE=1 显式启用脚本同目录 xhcyv_token.json 缓存，默认不读写磁盘凭据。
XHCYV_NOTIFY 默认 true，XHCYV_NOTIFY_ONLY_FAIL 默认 false，保留失败通知筛选。
QINGLONG_NOTIFY=auto 默认列入通知；0 关闭，1 开启。QINGLONG_NOTIFY_SCRIPTS
设置后替换默认选择，支持目录相对路径、文件名、glob、目录编号及 *。
QINGLONG_NOTIFY_DIR 可指定青龙 notify.py/sendNotify.js 所在目录。
断网预演只模拟通知，不加载或执行外部通知模块。

MIT License
Copyright (c) zephyr_xiao

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('40d0b5035381a2e2', 'scripts/xhcyv_checkin.py', 'xhcyv_checkin.py', 'xhcyv_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import base64
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

TITLE = '芯幻签到'
CATALOG = '40d0b5035381a2e2'
SITE = 'https://xhcyv.com'
API = 'https://api.xhcyv.com/api/v1'
CACHE = Path(__file__).resolve().with_name('xhcyv_token.json')
requests = None  # 延迟导入，断网预演仅用标准库
SECRETS = []


def enabled(name, default=False):
    value = os.getenv(name, '').strip().lower()
    return default if not value else value in ('1', 'true', 'yes', 'on', 'y')


def clean(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'\b(?:\+?86[- ]?)?1[3-9]\d{9}\b', '[手机号已隐藏]', text)
    return ''.join(c if c.isprintable() else ' ' for c in text)


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {clean(text)}', flush=True)


class TaskError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def parse_accounts():
    entries = []
    raw = os.getenv('XHCYV_ACCOUNTS', '')
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('eyJ') and line.count('.') == 2:
            entries.append({'token': line})
            SECRETS.append(line)
            continue
        delimiters = [(line.index(s), s) for s in ('#', ':', '&') if s in line]
        if not delimiters:
            entries.append({'error': '账号行缺少账号与密码分隔符'})
            SECRETS.append(line)
            continue
        _, delimiter = min(delimiters)
        account, password = line.split(delimiter, 1)
        account = account.strip()
        SECRETS.extend([password, line])
        entries.append({'account': account, 'password': password} if account and password
                       else {'error': '账号或密码为空'})
    single = os.getenv('XHCYV_ACCOUNT', '').strip()
    password = os.getenv('XHCYV_PASSWORD', '')
    if single or password:
        SECRETS.append(password)
        entries.insert(0, {'account': single, 'password': password} if single and password
                       else {'error': '兼容单账号变量缺少账号或密码'})
    tokens = []
    for line in os.getenv('XHCYV_TOKEN', '').splitlines():
        token = line.strip()
        if token:
            SECRETS.append(token)
            tokens.append({'token': token} if '&' not in token else
                          {'error': 'XHCYV_TOKEN 必须每行一个凭据，不能用 & 分账号'})
    return tokens + entries


def token_exp(token):
    try:
        part = token.split('.')[1]
        return int(json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))).get('exp', 0))
    except (ValueError, TypeError, IndexError, UnicodeError):
        return 0


def read_cache():
    if not enabled('XHCYV_CACHE'):
        return {}
    try:
        data = json.loads(CACHE.read_text(encoding='utf-8')).get('accounts', {})
        if isinstance(data, dict):
            for entry in data.values():
                if isinstance(entry, dict) and isinstance(entry.get('token'), str):
                    SECRETS.append(entry['token'])
            return data
    except FileNotFoundError:
        pass
    except Exception:
        log('⚠️ 凭据缓存不可读，将重新登录')
    return {}


def save_cache(cache, key, token):
    if token:
        cache[key] = {'token': token, 'exp': token_exp(token)}
    else:
        cache.pop(key, None)
    if not enabled('XHCYV_CACHE'):
        return
    temp_path = None
    try:
        # 锁定跨进程读改写，避免覆盖其他账号最近写入的缓存。
        import fcntl
        lock_fd = os.open(str(CACHE) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            merged = read_cache()
            if token:
                merged[key] = cache[key]
            else:
                merged.pop(key, None)
            fd, temp_path = tempfile.mkstemp(prefix='.xhcyv_token.', dir=str(CACHE.parent))
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump({'accounts': merged}, handle, ensure_ascii=False)
            os.replace(temp_path, CACHE)
            temp_path = None
    except Exception:
        log('⚠️ 凭据缓存保存失败，本次业务结果保留')
    finally:
        if temp_path:
            os.unlink(temp_path)


class Client:
    def __init__(self, timeout):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json', 'Content-Type': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9', 'Origin': SITE, 'Referer': SITE + '/',
        })
        for name in ('XHCYV_PROXY', 'HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'):
            proxy = os.getenv(name, '').strip()
            if proxy:
                SECRETS.append(proxy)
                self.session.proxies.update({'http': proxy, 'https': proxy})
                break

    def call(self, method, url, token='', body=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        attempts = 3 if method == 'GET' else 1
        for attempt in range(attempts):
            start = time.monotonic()
            if enabled('XHCYV_DEBUG'):
                log(f'请求 {method} {url}')
            try:
                with self.session.request(method, url, headers=headers, json=body,
                                          timeout=self.timeout, allow_redirects=False,
                                          stream=True) as response:
                    if response.status_code == 401:
                        raise TaskError('凭据失效，请更新本站 x_bbs_token', 10002)
                    http_status = response.status_code
                    if http_status >= 500 or 300 <= http_status < 400:
                        raise TaskError(f'HTTP 请求失败（{http_status}）')
                    raw = bytearray()
                    for chunk in response.iter_content(8192):
                        raw.extend(chunk)
                        if len(raw) > 2 * 1024 * 1024:
                            raise TaskError('接口响应超过大小限制')
                    try:
                        payload = json.loads(raw)
                    except (ValueError, UnicodeError):
                        raise TaskError('接口未返回有效 JSON') from None
                break
            except requests.RequestException:
                if attempt + 1 == attempts:
                    raise TaskError('网络、代理或 TLS 请求失败，请检查连接配置') from None
                log(f'⚠️ 读取请求连接失败，等待 {3 * (attempt + 1)} 秒后重试')
                time.sleep(3 * (attempt + 1))
            finally:
                log(f'请求 {method} 完成，耗时 {time.monotonic() - start:.2f} 秒')
        if not isinstance(payload, dict) or type(payload.get('code')) is not int:
            raise TaskError('接口缺少有效业务码')
        code = payload['code']
        if code != 0:
            messages = {10002: '凭据失效', 10006: '请求频繁，请稍后重试',
                        10007: '需要图形验证码', 10008: '图形验证码错误',
                        10009: '站点维护中', 11003: '账号或密码错误',
                        11004: '账号被封禁', 11006: '今日已签到', 11008: '邮箱未验证'}
            raise TaskError(messages.get(code, '接口返回未成功的业务码'), code)
        if not 200 <= http_status < 300:
            raise TaskError(f'HTTP 请求失败（{http_status}）')
        data = payload.get('data')
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise TaskError('接口数据结构异常')
        return data

    def login(self, account, password):
        captcha = {}
        for attempt in range(2):
            try:
                data = self.call('POST', SITE + '/api/session/login',
                                 body={'account': account, 'password': password, **captcha})
            except TaskError as error:
                if error.code not in (10007, 10008) or attempt:
                    raise
                log('站点要求验证码，尝试 ddddocr 识别')
                captcha = self.captcha()
                continue
            if data.get('two_factor_required'):
                raise TaskError('账号要求两步验证，请改用登录后的 x_bbs_token')
            tokens = [c.value for c in self.session.cookies if c.name == 'x_bbs_token']
            if len(set(tokens)) != 1 or not tokens[0]:
                raise TaskError('登录未返回唯一的 x_bbs_token Cookie')
            token = tokens[0]
            SECRETS.append(token)
            return token, data.get('user') or {}
        raise TaskError('验证码登录失败')

    def captcha(self):
        data = self.call('GET', API + '/captcha')
        if not isinstance(data.get('id'), (str, int)) or not isinstance(data.get('image'), str):
            raise TaskError('验证码接口缺少 id/image')
        try:
            import ddddocr
            image = data['image'].split(',', 1)[-1]
            answer = ddddocr.DdddOcr(show_ad=False).classification(base64.b64decode(image))
            if not answer or not answer.strip():
                raise ValueError()
        except ImportError:
            raise TaskError('需要验证码，请安装公开依赖 ddddocr 或改用 x_bbs_token') from None
        except Exception:
            raise TaskError('验证码识别失败，请改用 x_bbs_token') from None
        return {'captcha_id': data['id'], 'captcha_code': answer.strip()}


def show_identity(user):
    if not isinstance(user, dict):
        return
    for key in ('nickname', 'username', 'display_name', 'uid'):
        value = user.get(key)
        if isinstance(value, (str, int)) and str(value):
            log(f'官方身份 {key} {value}')
    details = []
    for key, label in (('points', '当前积分'), ('level_name', '等级')):
        value = user.get(key)
        if key == 'level_name' and isinstance(value, str):
            details.append(f'{label} {value}')
        elif type(value) in (int, float):
            details.append(f'{label} {value}')
    if details:
        log('，'.join(details))


def show_reward(data):
    for key, label in (('points', '签到积分'), ('day_order', '今日名次'), ('streak', '连签天数'),
                       ('bonus', '连签奖励'), ('member_bonus', '会员加成')):
        value = data.get(key)
        if type(value) in (int, float):
            log(f'{label} {value}')


@contextmanager
def stage(stats, number, title):
    start = time.monotonic()
    log(f'阶段 {number} {title} 开始')
    stats['total'] += 1
    completed_before = stats['alreadyComplete'] + stats['skipped']
    try:
        yield
    except Exception:
        stats['failed'] += 1
        log(f'❌ 阶段 {number} {title} 失败，耗时 {time.monotonic() - start:.2f} 秒')
        raise
    else:
        if stats['alreadyComplete'] + stats['skipped'] == completed_before:
            stats['success'] += 1
        log(f'✅ 阶段 {number} {title} 完成，耗时 {time.monotonic() - start:.2f} 秒')


def run_account(entry, cache, timeout, dry, check, stats):
    with stage(stats, 1, '配置检查'):
        if 'error' in entry:
            raise TaskError(entry['error'])
    if dry:
        for number, title in ((2, '认证与验证码'), (3, '签到状态查询'), (4, '签到提交与积分查询')):
            log(f'⏭️ 阶段 {number} {title} 断网预演跳过，耗时 0.00 秒')
            stats['total'] += 1
            stats['skipped'] += 1
        log('DRY_RUN_OK 配置预演通过，未验证真实业务')
        return 'dry-run'
    client = Client(timeout)
    try:
        with stage(stats, 2, '认证与签到状态查询'):
            key = entry.get('account', '')
            cached = cache.get(key, {})
            token = entry.get('token', '')
            if not token and isinstance(cached, dict):
                token = cached.get('token', '')
                if not isinstance(token, str):
                    token = ''
                expiry = token_exp(token)
                if expiry and expiry < time.time() + 3600:
                    token = ''
            status = None
            if token:
                try:
                    status = client.call('GET', API + '/users/me/signin', token)
                except TaskError as error:
                    if error.code != 10002 or not key:
                        raise
                    save_cache(cache, key, '')
                    token = ''
                    log('凭据失效，重新登录')
            if not token:
                token, user = client.login(entry['account'], entry['password'])
                show_identity(user)
                save_cache(cache, key, token)
                status = client.call('GET', API + '/users/me/signin', token)
            if type(status.get('signed')) is not bool:
                raise TaskError('签到状态缺少布尔字段 signed，停止提交')
            if status['signed']:
                log('☑️ 今日已签到')
                record = status.get('record')
                show_reward(record if isinstance(record, dict) else status)
                stats['alreadyComplete'] += 1
        with stage(stats, 3, '签到处理'):
            if status['signed'] or check:
                log('⏭️ 跳过签到提交' if check else '☑️ 今日已签到，无需重复提交')
                stats['skipped'] += 1
            else:
                try:
                    result = client.call('POST', API + '/users/me/signin', token)
                    log('✅ 签到成功（业务码 0）')
                    show_reward(result)
                except TaskError as error:
                    if error.code != 11006:
                        if error.code == 10002 and key:
                            save_cache(cache, key, '')
                        raise
                    log('☑️ 今日已签到（业务码 11006）')
                    stats['alreadyComplete'] += 1
        with stage(stats, 4, '账号身份与积分查询'):
            try:
                user = client.call('GET', API + '/users/me', token)
                show_identity(user)
            except TaskError:
                stats['skipped'] += 1
                log('⚠️ 附加身份与积分查询失败，已验证的签到或自检结果保留')
        log('✅ 自检通过' if check else '✅ 账号签到流程完成')
        return 'success'
    finally:
        client.session.close()


def notification(body, dry, failed):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in ('0', 'false', 'no', 'off') or not enabled('XHCYV_NOTIFY', True):
        return 'disabled'
    if enabled('XHCYV_NOTIFY_ONLY_FAIL') and not failed:
        return 'success-filtered'
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selection is not None:
        patterns = re.split(r'[,;\s]+', selection.strip())
        selectors = (CATALOG, Path(__file__).name, 'xhcyv_checkin/xhcyv_checkin.py',
                     'xhcyv_checkin.py', 'checkin/xhcyv_checkin.py', 'output/candidate.py')
        if not any(fnmatch.fnmatch(s, p) for p in patterns if p for s in selectors):
            return 'not-selected'
    if dry:
        log('📨 断网预演模拟通知，未调用通知模块')
        return 'dry-run-simulated'
    # 子进程隔离通知输出和超时，通知异常不会覆盖业务退出码。
    python_sender = '''import importlib.util, sys
from pathlib import Path
body = sys.stdin.read()
try:
    from notify import send
except ImportError:
    send = None
    for directory in sys.argv[1:]:
        path = Path(directory) / 'notify.py'
        if path.is_file():
            sys.path.insert(0, str(path.parent))
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
            break
if send is None:
    sys.exit(3)
send('芯幻签到', body)
'''
    dirs = [p for p in (os.getenv('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts') if p]
    try:
        result = subprocess.run([sys.executable, '-c', python_sender, *dirs], input=body,
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        if result.returncode == 0:
            return 'sent'
        if result.returncode != 3:
            return 'failed'
        for directory in dirs:
            path = Path(directory) / 'sendNotify.js'
            if path.is_file():
                js = "let b='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>b+=x);process.stdin.on('end',async()=>{try{await require(process.argv[1]).sendNotify('芯幻签到',b)}catch(e){process.exitCode=1}})"
                result = subprocess.run(['node', '-e', js, str(path)], input=body, text=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=30, check=False)
                return 'sent' if result.returncode == 0 else 'failed'
        return 'unavailable'
    except Exception:
        return 'failed'


def main():
    global requests
    start = time.monotonic()
    dry = enabled('XHCYV_DRY_RUN')
    check = '--check' in sys.argv[1:]
    entries = parse_accounts()
    log('=' * 60)
    log(f'🚀 {TITLE} 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式 {"断网预演" if dry else "在线自检" if check else "正式签到"}，账号数 {len(entries)}')
    error = None
    try:
        if any(arg != '--check' for arg in sys.argv[1:]):
            raise TaskError('仅支持 --check 参数')
        timeout = int(os.getenv('XHCYV_TIMEOUT', '30'))
        if not 1 <= timeout <= 300:
            raise TaskError('XHCYV_TIMEOUT 必须为 1 至 300 秒')
        if not entries:
            raise TaskError('未配置账号，请设置 XHCYV_ACCOUNTS，每行一个账号#密码或本站凭据')
        if not dry:
            try:
                import requests as requests_module
                requests = requests_module
            except ImportError:
                raise TaskError('缺少公开依赖 requests，请在青龙 Python 依赖管理中安装') from None
    except TaskError as exc:
        error = str(exc)
    except ValueError:
        error = 'XHCYV_TIMEOUT 必须为整数秒'
    results = []
    if error:
        log(f'❌ 配置错误 {error}')
    else:
        cache = {} if dry else read_cache()
        for index, entry in enumerate(entries, 1):
            begin = time.monotonic()
            stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
            log(f'账号 {index}/{len(entries)} 开始')
            try:
                result = run_account(entry, cache, timeout, dry, check, stats)
            except TaskError as exc:
                result = 'failure'
                log(f'❌ 账号 {index} {exc}')
            except Exception:
                result = 'failure'
                log(f'❌ 账号 {index} 发生异常，详细内容已隐藏')
            elapsed = round(time.monotonic() - begin, 2)
            log(f'账号 {index} 统计 总任务 {stats["total"]}，成功 {stats["success"]}，'
                f'已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，'
                f'失败 {stats["failed"]}，耗时 {elapsed} 秒，状态 {result}')
            results.append({'account': index, 'status': result, 'tasks': stats, 'seconds': elapsed})
            if not dry and index < len(entries):
                time.sleep(1)
    success = sum(r['status'] == 'success' for r in results)
    simulated = sum(r['status'] == 'dry-run' for r in results)
    failed = len(entries) - success - simulated
    code = 1 if error or failed else 0
    status = ('configuration-error' if error else 'partial-failure' if failed and (success or simulated)
              else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'{TITLE}，状态 {status}，账号总数 {len(entries)}，成功 {success}，失败 {failed}，预演通过 {simulated}'
    notify_status = notification(clean(body), dry, bool(code))
    totals = {key: sum(r['tasks'][key] for r in results)
              for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('-' * 60)
    log(body)
    log(f'子任务统计 {json.dumps(totals, ensure_ascii=False)}')
    log(f'通知状态 {notify_status}，总耗时 {time.monotonic() - start:.2f} 秒')
    log(f'完成时间 {datetime.now():%Y-%m-%d %H:%M:%S}，最终状态 {status}')
    summary = dict(status=status, accounts=len(entries), success=success, failed=failed,
                   dryRunPassed=simulated, tasks=totals, results=results,
                   notification=notify_status, exitCode=code)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
