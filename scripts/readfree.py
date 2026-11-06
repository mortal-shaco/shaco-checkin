#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Readfree 每日签到
# cron: 26 10 * * *
# 上游未提供 cron；以上为维护版每日执行一次的建议时间。
# 来源: kinsluck/Readfree-Checkiner, Readfree.py
# https://gitlab.com/kinsluck/Readfree-Checkiner
# SPDX-License-Identifier: MIT
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
"""Readfree 独立签到。
READFREE_ACCOUNTS：每个非空行一个 JSON 对象，含 username 和 cookie。
在浏览器登录 https://readfree.me，个人主页地址取得 username，开发者工具
Network 中同站请求的 Cookie 请求头取得 cookie；仅在青龙私密变量中保存。
可选交互登录：对象改含 username、email、password，同时设置
READFREE_INTERACTIVE_LOGIN=1，并在有终端输入的环境运行。验证码写入临时
图片供自行查看，输入答案后删除；不启动外部查看器，不保存密码和会话。
READFREE_DRY_RUN=1：校验配置并模拟全部步骤，不联网、不读写验证码。
仅签到，不下载书籍、不发布内容、不修改资料。接口沿用上游路径并强制
HTTPS；页面结构或结果不明确时失败，不以 HTTP 200 冒充业务成功。
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
        _ql_notify_identities = ('1aac1845bed1f454', 'scripts/readfree.py', 'readfree.py', 'readfree')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import datetime as dt
import fnmatch
from html.parser import HTMLParser
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib import error, parse, request

TITLE = 'Readfree 每日签到'
CATALOG = '1aac1845bed1f454'
BASE = 'https://readfree.me'
LOGIN = BASE + '/accounts/login/?next=/'
TIMEOUT = 20
LIMIT = 2 * 1024 * 1024
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(text):
    print(f'[{dt.datetime.now():%H:%M:%S}] {text}', flush=True)


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.inputs, self.links, self.images, self.parts = {}, [], [], []
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'input' and attrs.get('name'):
            self.inputs[attrs['name']] = attrs.get('value', '')
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'img' and 'captcha' in attrs.get('class', '').split():
            self.images.append(attrs.get('src', ''))

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    @property
    def text(self):
        return ' '.join(' '.join(self.parts).split())


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, cookie=''):
        self.jar = http.cookiejar.CookieJar()
        # CookieJar keeps the imported browser cookie origin-scoped in memory.
        for item in cookie.split(';'):
            if not item.strip():
                continue
            key, value = item.strip().split('=', 1)
            self.jar.set_cookie(http.cookiejar.Cookie(
                0, key, value, None, False, 'readfree.me', False, False,
                '/', True, True, None, True, None, None, {}, False))
        self.opener = request.build_opener(NoRedirect(), request.HTTPCookieProcessor(self.jar))

    def fetch(self, url, data=None, binary=False):
        for _ in range(5):
            parsed = parse.urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'readfree.me'
                    or parsed.port not in (None, 443) or parsed.username or parsed.password):
                raise TaskError('拒绝向非本站 HTTPS 地址发送请求')
            headers = {'User-Agent': 'Readfree-Checkiner/1.0', 'Referer': LOGIN}
            if data is not None:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            req = request.Request(url, data=data, headers=headers)
            try:
                response = self.opener.open(req, timeout=TIMEOUT)
            except error.HTTPError as exc:
                response = exc
            except (error.URLError, TimeoutError, OSError):
                raise TaskError('网络或 TLS 请求失败（未输出响应及凭据）') from None
            with contextlib.closing(response):
                status = response.code
                if status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if not location:
                        raise TaskError('重定向缺少地址')
                    url = parse.urljoin(url, location)
                    if status == 303 or (status in (301, 302) and data is not None):
                        data = None
                    continue
                if status != 200:
                    raise TaskError(f'HTTP 请求失败，状态码 {status}')
                raw = response.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise TaskError('响应超过大小限制')
                if binary:
                    if not response.headers.get('Content-Type', '').lower().startswith('image/'):
                        raise TaskError('验证码响应不是图片')
                    return raw
                encoding = response.headers.get_content_charset() or 'utf-8'
                try:
                    return Page(raw.decode(encoding, errors='replace'))
                except (LookupError, ValueError):
                    raise TaskError('页面解析失败') from None
        raise TaskError('重定向次数过多')

    def login(self, account):
        if os.getenv('READFREE_INTERACTIVE_LOGIN', '').lower() not in TRUE or not sys.stdin.isatty():
            raise TaskError('密码登录需要显式开启交互开关和终端；定时任务请使用 Cookie')
        page = self.fetch(LOGIN)
        csrf, key = page.inputs.get('csrfmiddlewaretoken'), page.inputs.get('captcha_0')
        if not csrf or not key or not page.images:
            raise TaskError('登录表单缺少 CSRF 或验证码字段')
        image = self.fetch(parse.urljoin(LOGIN, page.images[0]), binary=True)
        with tempfile.TemporaryDirectory(prefix='readfree-captcha-') as folder:
            path = Path(folder) / 'captcha.img'
            path.write_bytes(image)
            path.chmod(0o600)
            log(f'验证码临时图片：{path}；请自行查看，结束后自动删除')
            import getpass
            answer = getpass.getpass('请输入验证码（不回显）：').strip()
        if not answer:
            raise TaskError('未输入验证码')
        self.fetch(LOGIN, parse.urlencode({
            'csrfmiddlewaretoken': csrf, 'email': account['email'],
            'password': account['password'], 'captcha_0': key, 'captcha_1': answer,
        }).encode())

    def profile(self, username):
        path = '/accounts/profile/' + parse.quote(username, safe='') + '/checkin/'
        page = self.fetch(BASE + path)
        authenticated(page)
        # Only display a public identity actually returned in an official profile link.
        for href in page.links:
            url = parse.urlsplit(parse.urljoin(BASE, href))
            match = re.fullmatch(r'/accounts/profile/([^/]+)/(?:checkin/)?', url.path)
            if url.hostname == 'readfree.me' and match:
                identity = parse.unquote(match.group(1))
                if identity == username and safe_identity(identity):
                    log('官方公开用户名：' + identity)
                    break
        return page


def safe_identity(value):
    return (not re.search(r'[\r\n\x00-\x1f]|\d{7,}|@', value)
            and len(value) <= 80)


def authenticated(page):
    if ('password' in page.inputs or 'captcha_0' in page.inputs
            or not any(parse.urlsplit(link).path.rstrip('/') == '/accounts/logout'
                       for link in page.links)):
        raise TaskError('未确认登录状态，Cookie 可能失效或页面结构已改变')


def check_result(page):
    authenticated(page)
    text = page.text
    if re.search(r'签到失败|签到错误|登录失败|请先登录|未签到|尚未签到|签到未成功', text):
        raise TaskError('页面返回失败或未签到状态')
    if re.search(r'(?:今天|今日|本日).{0,8}(?:已经|已)签到|(?:已经|已).{0,4}(?:今天|今日).{0,4}签到', text):
        return 'already'
    if re.search(r'签到成功|成功签到', text):
        return 'success'
    raise TaskError('未发现明确签到成功或今日已签到标记，拒绝仅凭 HTTP 200 报喜')


def accounts_from_env():
    return [line.strip() for line in os.getenv('READFREE_ACCOUNTS', '').splitlines() if line.strip()]


def parse_account(line):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError('账号行必须为 JSON 对象，未输出配置内容') from None
    if not isinstance(account, dict):
        raise TaskError('账号行必须为 JSON 对象')
    for key, value in account.items():
        if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
            raise TaskError('账号字段必须为非空单行字符串')
    if not account.get('username') or any(c in account['username'] for c in '/?#'):
        raise TaskError('缺少有效的公开用户名 username')
    cookie = account.get('cookie')
    if cookie:
        if any('=' not in item or not item.split('=', 1)[0].strip()
               for item in cookie.split(';') if item.strip()):
            raise TaskError('cookie 必须为浏览器 Cookie 请求头格式')
    elif not (account.get('email') and account.get('password')):
        raise TaskError('每个账号需要 cookie，或配套的 email 与 password')
    return account


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    selectors = re.split(r'[,;\s]+', selection.strip()) if selection else []
    names = (CATALOG, 'Readfree.py', 'candidate.py', Path(__file__).name,
             'scripts/Readfree.py', 'scripts/' + Path(__file__).name)
    selected = any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in selectors)
    enabled = switch not in FALSE and ((selected if selection is not None else switch in TRUE))
    if not enabled:
        return '已关闭或未列入通知名单'
    if dry:
        return '预演已模拟通知，未调用通知模块或网络'
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['success']}；失败：{summary['failed']}")
    payload = json.dumps([TITLE, body], ensure_ascii=False)
    # Run adapters in a child process: suppress potentially sensitive adapter output.
    py = ('import sys,json,importlib.util; '
          'p=sys.argv[1]; '
          's=importlib.util.spec_from_file_location("ql_notify",p); '
          'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
          'm.send(*json.load(sys.stdin))')
    commands = [[sys.executable, '-c', 'import notify,json,sys; notify.send(*json.load(sys.stdin))']]
    folders = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        folders.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    folders.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    for folder in folders:
        if (folder / 'notify.py').is_file():
            commands.append([sys.executable, '-c', py, str(folder / 'notify.py')])
        if (folder / 'sendNotify.js').is_file():
            js = 'const fs=require("fs"); const x=JSON.parse(fs.readFileSync(0,"utf8")); Promise.resolve(require(process.argv[1]).sendNotify(...x)).catch(()=>process.exit(1));'
            commands.append(['node', '-e', js, str(folder / 'sendNotify.js')])
    for command in commands:
        try:
            result = subprocess.run(command, input=payload, text=True, timeout=30,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return '通知适配器已调用'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '通知不可用或失败，保留业务退出码'


def main():
    started = time.monotonic()
    dry = os.getenv('READFREE_DRY_RUN', '').strip().lower() in TRUE
    lines = accounts_from_env()
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；模式：' + ('断网预演' if dry else '正式运行'))
    log(f'账号数量：{len(lines)}')
    results = []
    if not lines:
        log('❌ 配置错误：缺少必填 READFREE_ACCOUNTS')
    for index, line in enumerate(lines, 1):
        begin = time.monotonic()
        stats = {'total': 3, 'success': 0, 'already': 0, 'skipped': 0, 'failed': 0}
        failed = False
        account = client = None
        for number, label in enumerate(('账号配置检查', '确认登录状态', '每日签到'), 1):
            step = time.monotonic()
            log(f'账号 {index} · 阶段 {number}/3 {label} 开始')
            try:
                if number == 1:
                    account = parse_account(line)
                    outcome = 'success'
                    detail = '✅ 配置格式有效'
                elif dry:
                    outcome = 'skipped'
                    detail = '⏭️ 断网预演：已模拟步骤，未验证真实业务'
                elif number == 2:
                    client = Client(account.get('cookie', ''))
                    if not account.get('cookie'):
                        client.login(account)
                    client.profile(account['username'])
                    outcome, detail = 'success', '✅ 已确认登录状态'
                else:
                    outcome = check_result(client.fetch(BASE + '/accounts/checkin'))
                    detail = '☑️ 今日已签到' if outcome == 'already' else '✅ 签到成功（明确页面标记）'
                stats[outcome] += 1
                log(f'账号 {index} · 阶段 {number}/3 {detail}；耗时 {time.monotonic()-step:.2f} 秒')
            except Exception as exc:
                # Never render third-party exceptions: they can contain request secrets.
                detail = str(exc) if isinstance(exc, TaskError) else '处理异常，未输出敏感异常详情'
                log(f'账号 {index} · 阶段 {number}/3 ❌ {detail}；耗时 {time.monotonic()-step:.2f} 秒')
                stats['failed'] += 1
                stats['skipped'] += 3 - number
                failed = True
                break
        status = 'failure' if failed else ('dry-run' if dry else 'success')
        results.append({'index': index, 'status': status, **stats})
        log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["already"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {time.monotonic()-begin:.2f} 秒')
    failures = sum(r['status'] == 'failure' for r in results)
    successes = sum(r['status'] == 'success' for r in results)
    code = 1 if failures or not lines else 0
    status = ('configuration-error' if not lines else 'partial-failure' if failures and failures < len(lines)
              else 'failure' if failures else 'dry-run' if dry else 'success')
    summary = {'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines),
               'success': successes, 'failed': failures, 'dryRun': sum(r['status'] == 'dry-run' for r in results),
               'tasks': {key: sum(r[key] for r in results) for key in ('total', 'already', 'skipped')},
               'results': results, 'exitCode': code}
    try:
        notification = notify(summary, dry)
    except Exception:
        notification = '通知异常，保留业务退出码'
    log('----------------------------------------')
    log(f'最终状态：{status}；账号总数 {len(lines)}，成功 {successes}，失败 {failures}，预演 {summary["dryRun"]}')
    log('子任务统计：' + json.dumps({key: sum(r[key] for r in results) for key in ('total', 'success', 'already', 'skipped', 'failed')}, ensure_ascii=False))
    log(f'通知状态：{notification}')
    log(f'总耗时：{time.monotonic()-started:.2f} 秒；完成时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}')
    summary['notification'] = notification
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
