# -*- coding: utf-8 -*-
# name: 司机社签到
# cron: 49 9,20 * * *
# new Env('司机社签到');
# 上游作者: zephyr_xiao
# 来源: zephyr-xiao/qinglong-script / xsijishe_checkin/xsijishe_checkin.py
# MIT License
# Copyright (c) zephyr_xiao
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
"""
司机社签到，Python 3.10+，依赖 requests，验证码出现时另需 ddddocr。
SIJISHE_ACCOUNTS 必填，每个非空行一个账号，可混用以下格式。
邮箱&密码（仅在第一个 & 处分割，密码中的 &、=、; 均保留），或浏览器完整 Cookie。
从司机社登录页面取得自己的注册邮箱和密码，或登录后在开发者工具网络面板
查看本人站内请求的 Cookie 请求头。禁止分享凭据。
SIJISHE_HOST 可锁定经本人核实的镜像裸域名。默认依次尝试内置镜像，全部失败后
以独立无凭据 HTTP 请求读取发布页 47447.net 的普通链接。无法解析挑战页时失败，
请从发布页人工核实后设置 SIJISHE_HOST。脚本不安装或调用浏览器。
SIJISHE_PROXY 可设置 HTTP(S) 代理。TLS 始终校验，禁止跨域重定向传递凭据。
SIJISHE_DRY_RUN=1 完全断网，仅校验参数、打印计划，不读写 Cookie 缓存。
缓存默认使用脚本旁 xsijishe_cookie.json，兼容原缓存格式，权限 0600、锁定及原子更新。
SIJISHE_CACHE_FILE 可调整缓存位置。该文件含凭据，请存放于私人目录。
SIJISHE_DEBUG=true 仅增加脱敏统计。保留 SIJISHE_NOTIFY 和
SIJISHE_NOTIFY_ONLY_FAIL 开关。QINGLONG_NOTIFY 显式开关优先，auto 按
QINGLONG_NOTIFY_SCRIPTS 清单选择；未设置清单时沿用本脚本默认通知。
通知器不可用不会改变业务退出码。预演仅准备通知摘要，保证不联网。
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
        _ql_notify_identities = ('43434889ab5f9361', 'scripts/xsijishe_checkin.py', 'xsijishe_checkin.py', 'xsijishe_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from html import unescape
from urllib.parse import urlsplit, urljoin

TITLE = '司机社签到'
CATALOG_ID = '43434889ab5f9361'
KNOWN_HOSTS = ['xsijishe.net', 'dlsjs.net', 'sjs96.com', 'dlsjs.com',
               'sjs66.net', 'xsijishe.com', 'sjs66.com']
GUIDE_URL = 'https://47447.net/'
LOGIN_PAGE = '/member.php?mod=logging&action=login&infloat=yes&frommessage&inajax=1&ajaxtarget=messagelogin'
SIGN_PAGE = '/k_misign-sign.html'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
TRUE = {'1', 'true', 'yes', 'y', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class SafeError(Exception):
    """仅携带可公开的固定错误信息。"""


class MirrorError(SafeError):
    pass


class LoginError(SafeError):
    pass


def enabled(name, default=False):
    value = os.getenv(name, '').strip().lower()
    return default if not value else value in TRUE


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def parse_accounts(raw):
    accounts = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        # 邮箱字段在首个 & 之前。先识别邮箱，避免密码含 = 或 ; 时误判为 Cookie。
        first, sep, rest = line.partition('&')
        if sep and re.fullmatch(r'[^\s@=;]+@[^\s@=;]+', first.strip()):
            accounts.append({'type': 'credential', 'email': first.strip(),
                             'password': rest, 'valid': bool(rest)})
        else:
            cookie = line.strip()
            pieces = [part.strip() for part in cookie.split(';') if part.strip()]
            valid = bool(pieces) and all(re.fullmatch(r'[^\s=;]+=[^\r\n]*', p) for p in pieces)
            accounts.append({'type': 'cookie', 'cookie': cookie, 'valid': valid})
    return accounts


def host_name(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value) or '.' not in value:
        raise SafeError('域名格式错误，请填写裸域名')
    if any(not label or label.startswith('-') or label.endswith('-') for label in value.split('.')):
        raise SafeError('域名格式错误')
    return value


def http(session, host, path, method='GET', **kwargs):
    """自有 HTTP 实现，限制响应大小、超时和重定向，凭据仅发送到当前镜像。"""
    url = f'https://{host}{path}'
    for _ in range(4):
        try:
            with session.request(method, url, timeout=(10, 15), allow_redirects=False,
                                 stream=True, **kwargs) as response:
                if response.is_redirect:
                    target = urljoin(url, response.headers.get('Location', ''))
                    parsed = urlsplit(target)
                    if parsed.scheme != 'https' or parsed.netloc != host:
                        raise MirrorError('拒绝跨域或非 HTTPS 重定向')
                    if method != 'GET':
                        raise MirrorError('登录提交重定向未获确认')
                    url = target
                    continue
                if not 200 <= response.status_code < 300:
                    raise MirrorError(f'接口 HTTP {response.status_code}')
                content = bytearray()
                for chunk in response.iter_content(16384):
                    content.extend(chunk)
                    if len(content) > 2 * 1024 * 1024:
                        raise MirrorError('响应超出安全大小限制')
                encoding = response.encoding or 'utf-8'
                if encoding.lower() == 'iso-8859-1':
                    encoding = 'utf-8'
                return bytes(content), bytes(content).decode(encoding, errors='replace')
        except SafeError:
            raise
        except Exception:
            raise MirrorError('网络请求失败，请检查网络、代理或站点证书') from None
    raise MirrorError('重定向次数超限')


def session_for(host, proxy):
    import requests
    session = requests.Session()
    session.trust_env = False
    session.verify = True
    session.headers.update({'User-Agent': UA, 'Referer': f'https://{host}/',
                            'X-Requested-With': 'XMLHttpRequest'})
    if proxy:
        session.proxies.update({'http': proxy, 'https': proxy})
    return session


def apply_cookies(session, cookie, host):
    session.cookies.clear()
    for part in cookie.split(';'):
        if '=' in part:
            key, value = part.strip().split('=', 1)
            session.cookies.set(key, value, domain=host, path='/', secure=True)


def cache_path():
    return Path(os.getenv('SIJISHE_CACHE_FILE') or Path(__file__).with_name('xsijishe_cookie.json'))


@contextmanager
def cache_locked():
    # 青龙为 Linux。使用系统文件锁避免不同定时实例覆盖缓存。
    import fcntl
    path = cache_path()
    if path.is_symlink():
        raise SafeError('缓存路径不能为符号链接')
    fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SafeError('缓存锁等待超时')
                time.sleep(0.1)
        try:
            data = {'accounts': {}}
            if path.exists():
                os.chmod(path, 0o600)
                data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('accounts'), dict):
                raise SafeError('缓存格式错误')
            yield path, data
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def cached_cookie(email):
    try:
        with cache_locked() as (_, data):
            entry = data['accounts'].get(email, {})
            return entry.get('cookies', '') if isinstance(entry, dict) else ''
    except Exception:
        log('⚠️ 缓存读取不可用，将使用邮箱密码登录')
        return ''


def update_cache(email, cookie):
    try:
        with cache_locked() as (path, data):
            if cookie:
                data['accounts'][email] = {'cookies': cookie, 'update_time': datetime.now().isoformat()}
            else:
                data['accounts'].pop(email, None)
            data.update(site='司机社', update_time=datetime.now().isoformat())
            fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.sijishe-')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(data, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        log('Cookie 缓存已安全更新')
    except Exception:
        log('⚠️ 缓存更新失败，本次业务结果保持不变')


def extract(pattern, text):
    match = re.search(pattern, text, re.S | re.I)
    return match.group(1) if match else None


def show_identity(text):
    # 只提取上游确认的欢迎语身份或 Discuz 用户链接，绝不回显响应片段。
    name = extract(r'欢迎您回来[，,]\s*(?:<font[^>]*>.*?</font>\s*)?([^<，,\r\n]+)', text)
    if not name:
        name = extract(r'<a\b[^>]*href=["\'][^"\']*(?:home\.php\?mod=space&amp;uid=\d+|space-uid-\d+)[^"\']*["\'][^>]*>([^<>]+)</a>', text)
    if name:
        name = unescape(name).strip()
        # 手机号、邮箱和会话值不能作为身份打印。
        if name and not re.search(r'\d{11}|@|[\x00-\x1f]|(?:token|cookie|session)\s*[=:]', name, re.I):
            log(f'站点身份 {name}')


def is_authenticated(text):
    if '请先登录' in text or '欢迎您回来' not in text and not re.search(r'(?:退出|退出登录|action=logout)', text):
        return False
    show_identity(text)
    return True


def login(session, host, account):
    _, page = http(session, host, LOGIN_PAGE)
    formhash = extract(r'name=["\']formhash["\']\s+value=["\']([a-z0-9]{8})', page)
    formhash = formhash or extract(r'formhash["\']?\s*[=:]\s*["\']?([a-z0-9]{8})', page)
    loginhash = extract(r'main_messaqge_([a-z0-9]{5})', page)
    loginhash = loginhash or extract(r'loginhash["\']?\s*[=:]\s*["\']?([a-z0-9]{5,8})', page)
    if not formhash or not loginhash:
        raise MirrorError('登录页缺少必要参数，可能为挑战页')
    seccode = extract(r'seccode_([a-z0-9]{5,8})', page)
    payload = {'formhash': formhash, 'referer': f'https://{host}/home.php?mod=spacecp&ac=credit&showcredit=1',
               'loginfield': 'email', 'username': account['email'], 'password': account['password'],
               'questionid': '0', 'answer': '', 'cookietime': '2592000'}
    if seccode:
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(old=False, show_ad=False)
        except Exception:
            raise SafeError('需要本地验证码识别，请安装可用的 ddddocr 依赖') from None
        for attempt in range(1, 4):
            log(f'验证码识别与验证 第 {attempt}/3 次')
            image, _ = http(session, host, '/misc.php', params={'mod': 'seccode', 'update': random.randint(10000, 99999), 'idhash': seccode})
            try:
                captcha = ocr.classification(image).strip()
            except Exception:
                captcha = ''
            if not captcha:
                continue
            _, check = http(session, host, '/misc.php', params={'mod': 'seccode', 'action': 'check',
                           'inajax': '1', 'modid': 'member::logging', 'idhash': seccode, 'secverify': captcha})
            if re.search(r'<!\[CDATA\[\s*succeed\s*\]\]>', check):
                payload.update(seccodehash=seccode, seccodemodid='member::logging', seccodeverify=captcha)
                break
            time.sleep(random.uniform(2, 4))
        else:
            raise LoginError('验证码验证失败')
    _, text = http(session, host, f'/member.php?mod=logging&action=login&loginsubmit=yes&loginhash={loginhash}&inajax=1',
                   method='POST', data=payload)
    if '欢迎您回来' not in text:
        raise LoginError('登录未获明确成功，请核对凭据或验证码')
    show_identity(text)
    log('✅ 登录成功')
    cookies = '; '.join(f'{c.name}={c.value}' for c in session.cookies if host == c.domain.lstrip('.') or host.endswith(c.domain))
    if cookies:
        update_cache(account['email'], cookies)


def signin(session, host):
    _, text = http(session, host, SIGN_PAGE)
    if '请先登录' in text:
        raise SafeError('签到页提示未登录，请更新凭据')
    formhash = extract(r'formhash=([a-z0-9]{8})', text)
    if not formhash:
        raise MirrorError('签到页缺少 formhash，可能为挑战页')
    _, response = http(session, host, SIGN_PAGE, params={'operation': 'qiandao', 'format': 'button',
                      'formhash': formhash, 'inajax': '1', 'ajaxtarget': 'midaben_sign'})
    # 仅保留上游已有明确业务标记。未知响应失败闭合，不将 HTTP 200 当成成功。
    inner = extract(r'<!\[CDATA\[(.*?)\]\]>', response) or response
    if '签到成功' in inner and not re.search(r'(?:未|没有|尚未)签到成功', inner):
        status = 'success'
        log('✅ 签到成功')
        reward = re.search(r'获得随机奖励\s*(\d+)\s*车票\s*和\s*(\d+)\s*([^<。\s]{1,8})', inner)
        if reward:
            log(f'奖励 车票 {reward.group(1)}，附加奖励 {reward.group(2)}')
    elif '今日已签' in inner:
        status = 'already'
        log('☑️ 今日已签到')
    else:
        raise SafeError('签到接口未返回已知成功标记，需人工核对站点响应协议')
    try:
        _, stats = http(session, host, SIGN_PAGE)
        for field, label in [('lxdays', '连续天数'), ('lxlevel', '签到等级'),
                             ('lxreward', '积分奖励'), ('lxtdays', '累计天数')]:
            value = extract(r'id=["\']' + field + r'["\']\s+value=["\'](\d+)', stats)
            if value:
                log(f'{label} {value}')
    except SafeError:
        log('⚠️ 附加签到统计暂不可用')
    return status


class Stages:
    def __init__(self):
        self.counts = dict(total=0, success=0, already=0, skipped=0, failed=0)

    def run(self, title, action):
        self.counts['total'] += 1
        number = self.counts['total']
        start = time.monotonic()
        log(f'阶段 {number} 开始 {title}')
        try:
            result = action()
        except Exception:
            self.counts['failed'] += 1
            log(f'阶段 {number} ❌ 失败，耗时 {time.monotonic() - start:.2f} 秒')
            raise
        outcome = result if result in ('already', 'skipped') else 'success'
        self.counts[outcome] += 1
        log(f'阶段 {number} {outcome}，耗时 {time.monotonic() - start:.2f} 秒')
        return result


def discover_hosts(proxy):
    log('内置镜像全部失败，尝试无凭据 HTTP 发布页发现')
    try:
        with session_for('47447.net', proxy) as session:
            _, text = http(session, '47447.net', '/')
        found = []
        for link in re.findall(r'href=["\'](https://[^"\']+)["\']', text, re.I):
            parsed = urlsplit(unescape(link))
            host = host_name(parsed.netloc)
            # 仅接受上游已知同产品域名，避免发布页外链收到账号凭据。
            if host in KNOWN_HOSTS and host not in found:
                found.append(host)
        return found
    except Exception:
        log('⚠️ 发布页无法通过 HTTP 验证，请人工核实 SIJISHE_HOST')
        return []


def run_account(account, hosts, state, proxy, stages):
    if not account['valid']:
        raise SafeError('账号格式无效，请使用邮箱&密码或完整 Cookie')
    failures = 0
    cached = cached_cookie(account['email']) if account['type'] == 'credential' else account['cookie']
    ordered = list(hosts)
    preferred = state.get('preferred')
    if preferred in ordered:
        ordered.remove(preferred)
        ordered.insert(0, preferred)
    index = 0
    while index < len(ordered):
        host = ordered[index]
        index += 1
        log(f'尝试镜像 {host}')
        try:
            with session_for(host, proxy) as session:
                if cached:
                    apply_cookies(session, cached, host)
                    def validate():
                        _, text = http(session, host, '/home.php?mod=space')
                        return is_authenticated(text)
                    authenticated = stages.run('检查 Cookie 登录状态', validate)
                    log('Cookie 身份已确认' if authenticated else 'Cookie 身份未获确认')
                    if not authenticated:
                        if account['type'] == 'cookie':
                            raise SafeError('Cookie 失效或身份未获确认，请重新获取')
                        cached = ''
                        update_cache(account['email'], '')
                        session.cookies.clear()
                else:
                    authenticated = False
                if not authenticated:
                    stages.run('邮箱密码登录及可选 OCR', lambda: login(session, host, account))
                status = stages.run('签到并读取统计', lambda: signin(session, host))
                state['preferred'] = host
                return status
        except LoginError as error:
            failures += 1
            log(str(error))
            if failures >= 2:
                raise SafeError('连续两次登录失败，停止该账号以减少锁号风险') from None
        except MirrorError as error:
            log(f'⚠️ {error}，尝试下一镜像')
        if index == len(ordered) and not state['manual'] and not state.get('discovered'):
            state['discovered'] = True
            ordered.extend(h for h in discover_hosts(proxy) if h not in ordered)
    raise SafeError('全部镜像均未完成签到')


def notify_summary(body, dry, failed):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '全局关闭'
    selected = enabled('SIJISHE_NOTIFY', True)
    listing = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if listing is not None:
        selectors = re.split(r'[,;\s]+', listing.strip())
        names = [CATALOG_ID, Path(__file__).name, 'xsijishe_checkin.py',
                 'xsijishe_checkin/xsijishe_checkin.py', 'scripts/checkin/xsijishe_checkin.py']
        selected = any(fnmatch.fnmatch(name, selector) for selector in selectors if selector for name in names)
    if switch in TRUE:
        selected = True
    if not selected:
        return '未选中或脚本关闭'
    if switch not in TRUE and enabled('SIJISHE_NOTIFY_ONLY_FAIL') and not failed and not dry:
        return '仅失败通知，成功静默'
    if dry:
        log('通知摘要已准备，预演模式禁止网络投递')
        return '预演摘要已准备'
    # 子进程隔离通知器日志与异常，限制通知耗时，不改变业务结果。
    code = '''import importlib.util, os, sys
sys.path.insert(0, sys.argv[2])
try:
 from notify import send
except Exception:
 send = None
 for folder in [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]:
  path = os.path.join(folder, "notify.py") if folder else ""
  if path and os.path.isfile(path):
   spec = importlib.util.spec_from_file_location("ql_notify", path)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   send = module.send
   break
if send is None:
 sys.exit(2)
send(sys.argv[1], sys.stdin.read())
'''
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, str(Path(__file__).resolve().parent)], input=body, text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return '已发送' if result.returncode == 0 else '通知不可用或失败'
    except Exception:
        return '通知失败或超时'


def main():
    start = time.monotonic()
    dry = enabled('SIJISHE_DRY_RUN')
    log('=' * 50)
    log(f'{TITLE} 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log('运行模式 ' + ('断网预演' if dry else '正式执行'))
    accounts = parse_accounts(os.getenv('SIJISHE_ACCOUNTS', ''))
    log(f'账号总数 {len(accounts)}')
    results = []
    config_error = False
    totals = dict(total=0, success=0, already=0, skipped=0, failed=0)
    config_start = time.monotonic()
    log('阶段 0 开始 运行配置与依赖检查')
    try:
        if not accounts:
            raise SafeError('未配置必填变量 SIJISHE_ACCOUNTS')
        manual = os.getenv('SIJISHE_HOST', '').strip()
        hosts = [host_name(manual)] if manual else list(KNOWN_HOSTS)
        proxy = os.getenv('SIJISHE_PROXY', '').strip()
        if proxy and urlsplit(proxy).scheme not in ('http', 'https'):
            raise SafeError('SIJISHE_PROXY 需为 HTTP 或 HTTPS 代理地址')
        if not dry:
            try:
                import requests
            except ImportError:
                raise SafeError('缺少 requests，请在青龙 Python 依赖中安装') from None
        log(f'阶段 0 配置检查通过，耗时 {time.monotonic() - config_start:.2f} 秒')
        state = {'manual': bool(manual), 'discovered': False}
        for index, account in enumerate(accounts, 1):
            before = time.monotonic()
            stages = Stages()
            log(f'--- 账号 {index} 开始，类型 {account["type"]} ---')
            try:
                if dry:
                    def preview():
                        if not account['valid']:
                            raise SafeError('账号格式无效')
                        log('参数校验通过，计划检查身份、按需登录、签到和读取统计；预演不发请求、不写缓存')
                        return 'skipped'
                    stages.run('断网参数与执行计划检查', preview)
                    status = 'dry-run'
                else:
                    status = run_account(account, hosts, state, proxy, stages)
                results.append({'account': index, 'status': status, 'success': True})
            except Exception as error:
                message = str(error) if isinstance(error, SafeError) else '执行异常，已隐藏可能含凭据的错误详情'
                log(f'❌ 账号 {index} {message}')
                results.append({'account': index, 'status': 'failure', 'success': False})
            for key in totals:
                totals[key] += stages.counts[key]
            log(f'账号 {index} 统计 {json.dumps(stages.counts, ensure_ascii=False)}，耗时 {time.monotonic() - before:.2f} 秒')
            if not dry and index < len(accounts):
                time.sleep(random.uniform(2, 6))
    except Exception as error:
        config_error = True
        log(f'阶段 0 ❌ 配置检查失败，耗时 {time.monotonic() - config_start:.2f} 秒')
        log(str(error) if isinstance(error, SafeError) else '配置检查失败，详情已脱敏')
    success = sum(r['success'] for r in results)
    failed = len(accounts) - success
    if config_error:
        status = 'configuration-error'
    elif failed:
        status = 'partial-failure' if success else 'failure'
    else:
        status = 'dry-run' if dry else 'success'
    body = f'{TITLE}\n状态 {status}\n账号总数 {len(accounts)}，成功 {success}，失败 {failed}\n预演 {dry}'
    notification = notify_summary(body, dry, config_error or bool(failed))
    log('-' * 50)
    log(body.replace('\n', ' | '))
    log(f'子任务统计 {json.dumps(totals, ensure_ascii=False)}')
    log(f'通知状态 {notification}')
    log(f'完成时间 {datetime.now():%Y-%m-%d %H:%M:%S}，总耗时 {time.monotonic() - start:.2f} 秒，最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'dryRun': dry,
          'accounts': len(accounts), 'success': success, 'failed': failed,
          'configurationError': config_error, 'results': results, 'steps': totals,
          'notification': notification}, ensure_ascii=False, separators=(',', ':')))
    return 1 if config_error or failed else 0


if __name__ == '__main__':
    sys.exit(main())
