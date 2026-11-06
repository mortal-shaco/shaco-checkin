#!/usr/bin/env python3
# name: SouthPlus签到
# cron: 25 10 * * *
# SPDX-License-Identifier: MIT
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# 来源：anchengxiake/ql-checkin，south.py
# 参考: SouthPlusQianDao_WebDriver-main 项目
# 上游说明：使用 DrissionPage 替代 Selenium；维护版改为独立 HTTP 客户端。
"""SouthPlus 日常、周常签到。仅使用站内原有任务接口，不发帖、不消费。

SOUTHPLUS_COOKIE：浏览器登录后在开发者工具的站内请求中复制 Cookie，
每个非空行一个账号。兼容 COOKIE、单行浏览器 Cookie 对象 JSON 数组。
也可用 SOUTHPLUS_ACCOUNTS，每行“用户名|密码”，只在首个 | 分割；
兼容 SOUTHPLUS_USERNAME / SOUTHPLUS_PASSWORD 单账号输入。
Cookie 优先于密码。可选验证码 OCR：pip install ddddocr Pillow。
Cloudflare 挑战不绕过，失败时请在浏览器完成验证后重新获取 Cookie；
需将 SOUTHPLUS_USER_AGENT 设为获取 Cookie 的浏览器 User-Agent。
SOUTHPLUS_DRY_RUN=1 完全断网，含通知；QINGLONG_NOTIFY=0 关闭通知。
原 cron 与 RANDOM_SIGNIN=true、MAX_RANDOM_DELAY=3600 默认值保留。
不保存网页、Cookie 或验证码到文件，不输出原始响应。
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
        _ql_notify_identities = ('c346af04eb70ab9b', 'scripts/south.py', 'south.py', 'south')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import fnmatch
import http.cookiejar
import importlib.util
import io
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

TITLE = 'SouthPlus签到'
CATALOG = 'c346af04eb70ab9b'
DEFAULT_SITE = 'https://www.south-plus.net'
TASK = '/plugin.php?H_name-tasks.html'
ACTIVE = '/plugin.php?H_name-tasks-actions-newtasks.html'
ENDED = '/plugin.php?H_name-tasks-actions-endtasks.html'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def stamp():
    return datetime.now().strftime('%H:%M:%S')


def log(message):
    print(f'[{stamp()}] {message}', flush=True)


def integer(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise TaskError(f'{name} 必须为整数') from None
    if not minimum <= value <= maximum:
        raise TaskError(f'{name} 超出允许范围')
    return value


def flag(name, default=False):
    value = os.getenv(name, 'true' if default else 'false').strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f'{name} 必须使用布尔值')
    return value in TRUE


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.forms, self.links, self.texts = [], [], []
        self.form = self.link = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.form = {'action': a.get('action', ''), 'method': a.get('method', 'get').lower(), 'inputs': {}}
            self.forms.append(self.form)
        if tag == 'input' and self.form is not None and a.get('name'):
            if a.get('type', '').lower() not in ('checkbox', 'radio') or 'checked' in a:
                self.form['inputs'][a['name']] = a.get('value', '')
        if tag == 'a':
            self.link = {'href': a.get('href', ''), 'text': ''}
            self.links.append(self.link)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form = None
        if tag == 'a':
            self.link = None

    def handle_data(self, data):
        self.texts.append(data)
        if self.link is not None:
            self.link['text'] += data


def origin(url):
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise TaskError('站点必须为不含凭据的 HTTPS 地址')
    return u.scheme, u.hostname, u.port or 443


class SameOrigin(HTTPRedirectHandler):
    def __init__(self, site):
        self.site = origin(site)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if origin(newurl) != self.site:
            raise TaskError('拒绝向其他站点重定向，避免凭据泄漏')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, site, ua, cookie, timeout):
        self.site, self.timeout = site, timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = build_opener(SameOrigin(site), HTTPCookieProcessor(self.jar))
        self.ua = ua
        self.verify = ''
        self.encoding = 'utf-8'
        if isinstance(cookie, list):
            pairs = [(c.get('name'), c.get('value')) for c in cookie if isinstance(c, dict)]
        else:
            pairs = [p.strip().split('=', 1) for p in (cookie or '').split(';') if '=' in p]
        for name, value in pairs:
            if not isinstance(name, str) or not isinstance(value, str) or not name or re.search(r'[\s;\r\n]', name) or re.search(r'[\r\n;]', value):
                raise TaskError('Cookie 格式无效')
            host = urlsplit(site).hostname
            self.jar.set_cookie(http.cookiejar.Cookie(0, name.strip(), value.strip(), None, False,
                host, False, False, '/', True, True, None, True, None, None, {}))

    def request(self, path, data=None, ajax=False, binary=False):
        url = urljoin(self.site + '/', path)
        if origin(url) != origin(self.site):
            raise TaskError('拒绝跨站请求')
        headers = {'User-Agent': self.ua, 'Referer': self.site + TASK}
        if ajax:
            headers['X-Requested-With'] = 'XMLHttpRequest'
        body = urlencode(data, encoding=self.encoding).encode() if data is not None else None
        if body is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        try:
            with self.opener.open(Request(url, body, headers), timeout=self.timeout) as r:
                raw = r.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskError('响应超过安全大小上限')
                if binary:
                    return raw
                charset = r.headers.get_content_charset()
                if not charset:
                    m = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
                    charset = m.group(1).decode('ascii') if m else 'utf-8'
                text = raw.decode(charset, errors='replace')
                self.encoding = charset
        except TaskError:
            raise
        except Exception:
            raise TaskError('HTTP 请求失败或超时；未自动重试状态变更请求') from None
        if re.search(r'Just a moment|cf-turnstile-response|cf-challenge|Performing security verification', text, re.I):
            raise TaskError('站点要求浏览器验证，请刷新 Cookie 和 User-Agent 后重试')
        return text

    def authenticated(self, html):
        if any(x in html for x in ('您还没有登录', '请先登录', '还不是论坛会员')):
            raise TaskError('未登录或 Cookie 已过期')
        if not any(x in html for x in ('退出', '用户中心', '个人首页', '我的主题')):
            raise TaskError('无法确认登录状态')
        match = re.search(r'verifyhash\s*=\s*["\x27]([^"\x27]+)', html)
        if match:
            self.verify = match.group(1)
        for link in Page(html).links:
            uid = re.search(r'(?:\?|&)uid(?:=|-)([0-9]+)', link['href'])
            if uid:
                identity = link['text'].strip()
                if identity and not re.search(r'\d{7,}', identity) and not any(x in identity for x in ('个人首页', '用户中心', '资料')):
                    log('官方账号身份：' + identity.replace('\n', ' ').replace('\r', ' '))
                log('官方公开 UID：' + uid.group(1))
                break

    def login(self, username, password):
        attempts = integer('SOUTHPLUS_CAPTCHA_RETRY_LIMIT', 3, 0, 10)
        backoff = integer('SOUTHPLUS_CAPTCHA_RETRY_BACKOFF', 2, 0, 10)
        for attempt in range(max(1, attempts)):
            html = self.request('/login.php')
            form = next((f for f in Page(html).forms if 'pwuser' in f['inputs'] and 'pwpwd' in f['inputs']), None)
            if not form:
                raise TaskError('找不到已知登录表单，请使用 Cookie 模式')
            fields = dict(form['inputs'])
            fields.update(pwuser=username, pwpwd=password)
            if 'gdcode' in fields:
                if not attempts:
                    raise TaskError('已关闭验证码识别，请使用 Cookie 模式')
                # OCR 在内存中执行，模型必须由公开包提供，禁止下载模型或执行安装器。
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        import ddddocr
                        engines = [ddddocr.DdddOcr(show_ad=False), ddddocr.DdddOcr(beta=True, show_ad=False)]
                        raw = self.request('/ck.php?' + str(int(time.time() * 1000)), binary=True)
                        candidates = []
                        for image in captcha_variants(raw):
                            for engine in engines:
                                code = re.sub('[^0-9A-Za-z]', '', engine.classification(image))
                                if 4 <= len(code) <= 6:
                                    candidates.append(code)
                    if not candidates:
                        raise ValueError()
                    fields['gdcode'] = sorted(set(candidates), key=lambda c: (abs(len(c)-5), -len(c), c))[0]
                except Exception:
                    raise TaskError('验证码识别不可用，请安装可选 ddddocr/Pillow 或改用 Cookie') from None
            if form['method'] != 'post':
                raise TaskError('登录表单不使用 POST，拒绝在 URL 中发送密码')
            result = self.request(form['action'] or '/login.php', fields)
            if '认证码不正确' in result or ('验证码' in result and '不正确' in result):
                log('验证码被拒绝，进行有限次重新识别')
                time.sleep(min(backoff * (attempt + 1), 10))
                continue
            if any(x in result for x in ('密码错误', '用户名不存在', '登录失败', '非法请求')):
                raise TaskError('账号密码登录失败')
            self.authenticated(self.request(TASK))
            return
        raise TaskError('验证码重试次数已用尽')

    def action(self, action, cid):
        query = {'H_name': 'tasks', 'action': 'ajax', 'actions': action, 'cid': cid, 'nowtime': int(time.time()*1000)}
        if self.verify:
            query['verify'] = self.verify
        text = self.request('/plugin.php?' + urlencode(query), ajax=True)
        return classify(text, action)


def captcha_variants(raw):
    variants = [raw]
    try:
        from PIL import Image, ImageEnhance, ImageOps
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        for scale in (2, 3):
            gray = ImageOps.grayscale(image).resize((image.width*scale, image.height*scale), Image.Resampling.LANCZOS)
            gray = ImageEnhance.Sharpness(ImageEnhance.Contrast(gray).enhance(2.8)).enhance(2)
            buf = io.BytesIO()
            gray.save(buf, format='PNG')
            variants.append(buf.getvalue())
        for delta in (10, 16, 22):
            mask = Image.new('L', image.size, 255)
            mask.putdata([0 if max(p)>125 and max(p)-min(p)<delta else 255 for p in image.getdata()])
            mask = mask.resize((image.width*3, image.height*3), Image.Resampling.NEAREST)
            buf = io.BytesIO()
            mask.save(buf, format='PNG')
            variants.append(buf.getvalue())
    except ImportError:
        pass
    return variants


def classify(raw, action):
    cdata = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw, re.S)
    text = unescape(cdata.group(1) if cdata else raw).strip()
    if any(x in text for x in ('您还没有登录', '请先登录', '任务不存在', '未申请任务', '没有可领取', '失败', '错误', '非法')):
        raise TaskError('站点拒绝任务操作或任务状态不满足要求')
    # 冷却只对申请有效；未申请和任务不存在不能当成成功。
    if action == 'job' and re.search(r'还没超过\s*\d+\s*小时', text):
        return 'already'
    if action == 'job' and any(x in text for x in ('已经申请', '已经领取', '您已经申请过')):
        return 'success'
    if any(x in text for x in ('已经完成', '已完成', '完成了', '完成!', '完成！')):
        return 'already'
    if '领取完成' in text:
        return 'success'
    if re.fullmatch(r'success(?:\s+[^<>]*)?', text, re.I):
        return 'success'
    raise TaskError('响应未包含可验证的业务成功标记')


def accounts():
    cookie = os.getenv('SOUTHPLUS_COOKIE', '').strip() or os.getenv('COOKIE', '').strip()
    if cookie:
        result = []
        for line in cookie.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line) if line.startswith('[') else line
            except ValueError:
                value = None
            result.append(('cookie', value, None))
        return result
    combined = os.getenv('SOUTHPLUS_ACCOUNTS', '').strip()
    if combined:
        return [('password', *(line.split('|', 1) if '|' in line else (line, None))) for line in combined.splitlines() if line.strip()]
    if os.getenv('SOUTHPLUS_USERNAME') or os.getenv('SOUTHPLUS_PASSWORD'):
        return [('password', os.getenv('SOUTHPLUS_USERNAME'), os.getenv('SOUTHPLUS_PASSWORD'))]
    raise TaskError('缺少 SOUTHPLUS_COOKIE；也可配置兼容密码登录输入')


def notify(body, dry):
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if mode in FALSE:
        return '已关闭'
    if mode not in TRUE | {'auto'}:
        return '通知开关无效，未发送'
    if dry:
        return '断网预演：已生成通知摘要，未调用通知通道'
    if mode == 'auto':
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', ''))
        names = (CATALOG, Path(__file__).name, 'south.py', 'scripts/south.py', 'scripts/' + Path(__file__).name)
        if not any(fnmatch.fnmatchcase(n, s) for s in selectors if s for n in names):
            return '未选中，跳过'
    dirs = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    # 子进程隔离通知模块的输出、异常及超时，保留业务退出码。
    code = ('import importlib.util,sys; s=importlib.util.spec_from_file_location("notify",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])')
    paths = [Path(d)/'notify.py' for d in dirs if d]
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.insert(0, Path(spec.origin))
    except (ImportError, ValueError):
        pass
    for path in paths:
        if path.is_file():
            try:
                p = subprocess.run([sys.executable, '-c', code, str(path), TITLE, body], capture_output=True, timeout=25)
                if p.returncode == 0:
                    return '发送成功'
            except Exception:
                pass
    for directory in dirs:
        path = Path(directory)/'sendNotify.js' if directory else None
        if path and path.is_file():
            try:
                p = subprocess.run(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(path), TITLE, body], capture_output=True, timeout=25)
                if p.returncode == 0:
                    return '发送成功'
            except Exception:
                pass
    return '通知模块不可用或发送失败，保留业务退出码'


def main():
    started = time.monotonic()
    dry = os.getenv('SOUTHPLUS_DRY_RUN', '').lower() in TRUE
    total = good = bad = 0
    totals = dict(total=0, success=0, already=0, skipped=0, failed=0)
    status = 'configuration-error'
    log('========== SouthPlus签到 ==========')
    log('开始时间：' + datetime.now().isoformat(timespec='seconds'))
    log('运行模式：' + ('断网预演' if dry else '真实执行'))
    try:
        dry = flag('SOUTHPLUS_DRY_RUN')
        entries = accounts()
        total = len(entries)
        log(f'账号数量：{total}')
        site = os.getenv('SOUTHPLUS_SITE', DEFAULT_SITE).strip().rstrip('/')
        origin(site)
        u = urlsplit(site)
        if u.path or u.query or u.fragment:
            raise TaskError('SOUTHPLUS_SITE 只允许 HTTPS 站点根地址')
        timeout = integer('SOUTHPLUS_TIMEOUT', 20, 1, 120)
        delay = integer('MAX_RANDOM_DELAY', 3600, 0, 86400)
        random_signin = flag('RANDOM_SIGNIN', True)
        ua = os.getenv('SOUTHPLUS_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36')
        if random_signin and delay and not dry:
            wait = random.randint(0, delay)
            log(f'阶段 1 随机延迟：{wait} 秒')
            time.sleep(wait)
        for index, (kind, credential, password) in enumerate(entries, 1):
            begin = time.monotonic()
            counts = dict(total=0, success=0, already=0, skipped=0, failed=0)
            log(f'账号 {index} 阶段 2：校验凭据')
            try:
                if not credential or (kind == 'password' and not password):
                    raise TaskError('账号凭据不完整或 JSON 格式无效')
                client = Client(site, ua, credential if kind == 'cookie' else None, timeout)
                if kind == 'cookie' and not list(client.jar):
                    raise TaskError('Cookie 中没有有效键值对')
                if dry:
                    counts.update(total=2, skipped=2)
                    log(f'账号 {index} DRY_RUN_OK：登录、日常、周常及奖励请求均未发送；未等待、未调用 OCR')
                else:
                    if kind == 'password':
                        client.login(credential, password)
                    client.authenticated(client.request(TASK))
                    for cid, title in (('15', '日常'), ('14', '周常')):
                        counts['total'] += 1
                        phase = time.monotonic()
                        try:
                            log(f'账号 {index} 阶段 3 {title}申请')
                            applied = client.action('job', cid)
                            if applied == 'already':
                                counts['already'] += 1
                                log(f'☑️ {title}任务处于已完成/冷却状态')
                            else:
                                client.authenticated(client.request(ACTIVE))
                                log(f'账号 {index} 阶段 4 {title}完成及奖励结算')
                                outcome = client.action('job2', cid)
                                # 上游 job2 即完成并结算；不把页面按钮点击当作领取成功。
                                client.authenticated(client.request(ENDED))
                                counts['already' if outcome == 'already' else 'success'] += 1
                                log(f'✅ {title}完成及奖励结算已获站点确认')
                        except TaskError as e:
                            counts['failed'] += 1
                            log(f'❌ {title}：{e}')
                        log(f'{title}阶段耗时 {time.monotonic()-phase:.2f} 秒')
                if counts['failed']:
                    bad += 1
                else:
                    good += 1
            except TaskError as e:
                counts['total'] += 1
                counts['failed'] += 1
                bad += 1
                log(f'❌ 账号 {index}：{e}')
            except Exception:
                counts['total'] += 1
                counts['failed'] += 1
                bad += 1
                log(f'❌ 账号 {index}：处理失败，已隐藏异常细节')
            for key in totals:
                totals[key] += counts[key]
            log(f'账号 {index} 统计：总任务 {counts["total"]}，成功 {counts["success"]}，已完成 {counts["already"]}，跳过 {counts["skipped"]}，失败 {counts["failed"]}，耗时 {time.monotonic()-begin:.2f} 秒')
        status = ('partial-failure' if good else 'failure') if bad else ('dry-run' if dry else 'success')
    except TaskError as e:
        if total == 0:
            log('账号数量：0')
        log(f'❌ 配置错误：{e}')
    except Exception:
        status = 'failure'
        log('❌ 执行异常，已隐藏异常细节')
    exit_code = 0 if status in ('success', 'dry-run') else 1
    body = f'{TITLE}：{status}；账号总数 {total}，成功数 {good}，失败数 {bad}；子任务成功 {totals["success"]}，已完成 {totals["already"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}'
    notice = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log('通知状态：' + notice)
    log(f'总耗时：{time.monotonic()-started:.2f} 秒；完成时间：{datetime.now().isoformat(timespec="seconds")}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(task=TITLE, status=status, accounts=total, success=good, failed=bad, subtasks=totals, notification=notice, exitCode=exit_code), ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
