# -*- coding: utf-8 -*-
# name: 咔叽网单每日签到
# cron: 16 2 * * *
# publish-path: scripts/littlewuh_qinglongbox_dailycheckin_scripts.py
# SPDX-License-Identifier: MIT
# 来源：LittleWuh/qinglongbox 与 yuxian158/check 的 dailycheckin_scripts/ck_2nzz.py
# 上游提交：02e1c7a0788a62a7434f686118506ca5702fba24；723c834f121ff4eef2dec7afe521071a7efff1a9。
# 两个仓库中的原始任务 SHA-256 相同；保留双方署名及 MIT 许可。
"""咔叽网单每日签到（Python 3，仅标准库）。

NZZ_COOKIE：登录 https://www.2nzz.com 后在浏览器开发者工具的网络面板
复制本站请求的 Cookie 请求头值（不含 Cookie:）。每个非空行为一个账号，
Cookie 内部用分号分隔；值中的等号保留。不支持用 & 或 @ 分隔账号。
NZZ_DRY_RUN=1：仅检查配置和预演，不发送 HTTP 请求或签到。
QINGLONG_NOTIFY=0：关闭通知；默认开启，可用 QINGLONG_NOTIFY_DIR 指定
青龙 notify.py 目录。预演通知在禁止网络和子进程的隔离助手中尝试，无法
离线投递时记录状态，不改变业务退出码。

当前公开入口为 scripts/littlewuh_qinglongbox_dailycheckin_scripts.py。
历史建议路径 scripts/kaji_2nzz_checkin.py 与当前订阅清单不同，以清单为准。
原脚本无 cron；本维护版建议每天 08:30。仅签到，不发布文字或消耗资产。
原路径及签到表单保持一致；为保护 Cookie，仅 HTTPS，证书验证开启，
禁止跨域或降级跳转。HTTPS 能力尚未经联网验证；不支持时失败而不降级。
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
        _ql_notify_identities = ('cb2f4adeccaa95b9', 'scripts/littlewuh_qinglongbox_dailycheckin_scripts.py', 'littlewuh_qinglongbox_dailycheckin_scripts.py', 'littlewuh_qinglongbox_dailycheckin_scripts')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
from html.parser import HTMLParser
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://www.2nzz.com'
TITLE = '咔叽网单'
PUBLISH_PATH = 'scripts/littlewuh_qinglongbox_dailycheckin_scripts.py'
TIMEOUT = 15
LIMIT = 2 * 1024 * 1024
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), message), flush=True)


def no_network(*args, **kwargs):
    raise TaskError('预演禁止网络访问')


class SameSiteRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != 'https' or target.hostname != 'www.2nzz.com'
                or target.port not in (None, 443) or target.username or target.password):
            raise TaskError('拒绝不安全的跳转')
        # 签到 POST 不自动重发，也不把登录页跳转当成功。
        if req.get_method() != 'GET':
            raise TaskError('签到接口发生跳转，结果未确认')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_cookie(value):
    pairs = []
    for part in value.split(';'):
        part = part.strip()
        if not part:
            continue
        if '=' not in part:
            raise TaskError('Cookie 格式错误：应为分号分隔的键值对')
        key, val = part.split('=', 1)
        if not re.fullmatch(r'[A-Za-z0-9_\-]+', key) or not val:
            raise TaskError('Cookie 格式错误：字段名或字段值为空或不合法')
        if any(ord(c) < 32 or ord(c) > 126 for c in val):
            raise TaskError('Cookie 格式错误：含不支持的字符')
        pairs.append((key, val))
    if not pairs:
        raise TaskError('Cookie 不能为空')
    return pairs


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.formhash = None
        self.text = []
        self.hidden = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'input' and attrs.get('name') == 'formhash':
            self.formhash = attrs.get('value')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)

    def visible(self):
        return re.sub(r'\s+', ' ', ' '.join(self.text)).strip()


def identity(text):
    # Discuz 当前登录 UID，不能把任意成员空间链接误认为本账号。
    match = re.search(r'\bdiscuz_uid\s*=\s*[\'\"]?(\d+)', text)
    if match and int(match.group(1)) > 0:
        return match.group(1)
    return None


class Client:
    def __init__(self, pairs):
        jar = http.cookiejar.CookieJar()
        for name, value in pairs:
            jar.set_cookie(http.cookiejar.Cookie(
                0, name, value, None, False, 'www.2nzz.com', False, False,
                '/', True, True, None, True, None, None, {}, False))
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), SameSiteRedirect(),
            urllib.request.HTTPCookieProcessor(jar))

    def request(self, path, fields=None):
        data = None if fields is None else urllib.parse.urlencode(fields).encode('ascii')
        request = urllib.request.Request(BASE + path, data=data, headers={
            'User-Agent': 'Mozilla/5.0', 'Origin': BASE,
            'Referer': BASE + '/index.php', 'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        try:
            with self.opener.open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise TaskError('响应超过安全大小限制')
                charset = response.headers.get_content_charset()
                if not charset:
                    match = re.search(br'charset\s*=\s*[\'\"]?([a-zA-Z0-9_-]+)', raw[:8192])
                    charset = match.group(1).decode('ascii') if match else 'utf-8'
                if charset.lower() in ('gbk', 'gb2312'):
                    charset = 'gb18030'
                return raw.decode(charset, errors='strict')
        except TaskError:
            raise
        except Exception:
            # 异常可能带 URL、请求头或服务端内容，只输出本地固定说明。
            raise TaskError('网络、证书、HTTP 或响应编码错误；未确认成功') from None


def sign_result(text):
    # Discuz AJAX 通常返回 XML CDATA 中的 HTML，先取其内容再解析。
    match = re.search(r'<!\[CDATA\[(.*?)\]\]>', text, re.S)
    message = Page(match.group(1) if match else text).visible()
    if '您今天已经签到过了或者签到时间还未开始' in message:
        raise TaskError('接口返回已签到或时间未开始，无法确认今日完成')
    if any(word in message for word in ('失败', '错误', '未开始', '请先登录', '登录后', '无权')):
        raise TaskError('签到被拒绝；请核对登录状态和签到时间')
    if re.search(r'(?:^|[。！!，,\s])(?:恭喜[，,！! ]*)?(?:您|你)?签到成功(?:[！!，,。\s]|$)', message):
        return 'success', '签到成功'
    if re.search(r'(?:^|[。！!，,\s])(?:(?:您|你)?今天已经签到过了|今日已签到)(?:[！!，,。\s]|$)', message):
        return 'alreadyComplete', '今日已签到'
    raise TaskError('签到响应未包含明确成功标志；未确认成功')


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE:
        return '已关闭'
    # 助手只接收脱敏正文；隐藏通知库输出，异常不影响业务退出码。
    helper = r'''
import contextlib, importlib, importlib.util, io, os, pathlib, socket, subprocess, sys
if sys.argv[1] == '1':
    def denied(*a, **k): raise RuntimeError('offline')
    socket.socket = socket.create_connection = socket.getaddrinfo = denied
    subprocess.Popen = os.system = os.popen = denied
paths = [pathlib.Path(os.environ.get('QINGLONG_NOTIFY_DIR', '')) / 'notify.py'] if os.environ.get('QINGLONG_NOTIFY_DIR') else []
paths += [pathlib.Path('/ql/data/scripts/notify.py'), pathlib.Path('/ql/scripts/notify.py')]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        module = None
        for path in paths:
            if path.is_file():
                sys.path.insert(0, str(path.parent))
                spec = importlib.util.spec_from_file_location('notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                break
        if module is None: module = importlib.import_module('notify')
        result = module.send('咔叽网单', sys.stdin.read())
        if result is False: sys.exit(2)
    except Exception:
        sys.exit(2)
'''
    try:
        helper_env = dict(os.environ)
        helper_env.pop('NZZ_COOKIE', None)
        result = subprocess.run([sys.executable, '-c', helper, '1' if dry else '0'],
                                input=body, text=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20, check=False, env=helper_env)
        if result.returncode == 0:
            return '已调用离线通知助手' if dry else '已调用通知助手'
    except Exception:
        pass
    return '离线通知不可用（保留业务退出码）' if dry else '通知不可用或失败（保留业务退出码）'


def run_account(number, cookie, dry):
    start = time.monotonic()
    counts = dict(total=3, success=0, alreadyComplete=0, skipped=0, failure=0)
    labels = ['配置检查', '登录身份与签到令牌', '每日签到']
    client = None
    token = None
    status = 'failure'
    for index, label in enumerate(labels, 1):
        begin = time.monotonic()
        log('账号 %d · 阶段 %d/3 %s' % (number, index, label))
        try:
            if index == 1:
                pairs = parse_cookie(cookie)
                if not dry:
                    client = Client(pairs)
                detail = 'Cookie 格式检查通过（未显示凭据）'
                result = 'success'
            elif dry:
                detail = '预演跳过网络及账号状态变更'
                result = 'skipped'
            elif index == 2:
                home = client.request('/home.php')
                log('✅ 登录身份页面读取完成（未输出原始响应）')
                uid = identity(home)
                page = client.request('/index.php')
                log('✅ 签到令牌页面读取完成（未输出令牌或原始响应）')
                uid = uid or identity(page)
                if not uid:
                    raise TaskError('未取得当前登录公开 UID；拒绝使用不明身份签到')
                log('账号信息: ' + uid)
                token = Page(page).formhash
                if not token or not re.fullmatch(r'[a-zA-Z0-9]{4,64}', token):
                    raise TaskError('未取得有效签到令牌，Cookie 可能已失效')
                detail, result = '登录 UID 和签到令牌检查通过', 'success'
            else:
                path = '/plugin.php?' + urllib.parse.urlencode({
                    'id': 'dsu_paulsign:sign', 'operation': 'qiandao',
                    'infloat': '1', 'sign_as': '1', 'inajax': '1'})
                result, detail = sign_result(client.request(path, {
                    'formhash': token, 'qdxq': 'kx', 'qdmode': '2',
                    'todaysay': '', 'fastreply': '0'}))
                log('签到信息: ' + detail)
            counts[result] += 1
            log('%s %s；阶段耗时 %.2f 秒' % (
                {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️'}[result],
                detail, time.monotonic() - begin))
        except Exception as error:
            counts['failure'] += 1
            counts['skipped'] += 3 - index
            detail = str(error) if isinstance(error, TaskError) else '内部处理错误；未确认成功'
            log('❌ %s；阶段耗时 %.2f 秒；后续 %d 阶段跳过' % (
                detail, time.monotonic() - begin, 3 - index))
            status = 'configuration-error' if index == 1 else 'failure'
            break
    else:
        status = 'dry-run' if dry else 'success'
    elapsed = round(time.monotonic() - start, 2)
    log('账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒，状态 %s' %
        (number, counts['total'], counts['success'], counts['alreadyComplete'],
         counts['skipped'], counts['failure'], elapsed, status))
    return {'account': number, 'status': status, 'statistics': counts, 'elapsedSeconds': elapsed}


def main():
    start = time.monotonic()
    dry = os.getenv('NZZ_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    if dry:
        socket.socket = socket.create_connection = socket.getaddrinfo = no_network
    cookies = [line.strip() for line in os.getenv('NZZ_COOKIE', '').splitlines() if line.strip()]
    log('========== 咔叽网单每日签到 ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('运行模式：%s；账号总数：%d' % ('断网预演' if dry else '正式签到', len(cookies)))
    accounts = [run_account(i, cookie, dry) for i, cookie in enumerate(cookies, 1)]
    success = sum(a['status'] in ('success', 'dry-run') for a in accounts)
    failed = len(accounts) - success
    if not cookies:
        log('❌ 配置错误：请填写必需环境变量 NZZ_COOKIE，每行一个账号')
        status, code = 'configuration-error', 1
    elif failed:
        status = 'partial-failure' if success else (
            'configuration-error' if all(a['status'] == 'configuration-error' for a in accounts) else 'failure')
        code = 1
    else:
        status, code = ('dry-run' if dry else 'success'), 0
    totals = {key: sum(a['statistics'][key] for a in accounts)
              for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    body = '账号总数：%d；成功数：%d；失败数：%d；状态：%s。%s' % (
        len(cookies), success, failed, status, '仅预演，未验证业务成功。' if dry else '')
    notification = notify_summary(body, dry)
    log('----------------------------------------')
    log(body)
    log('子任务统计：总数 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failure)d' % totals)
    log('通知状态：' + notification)
    log('完成时间：%s；总耗时 %.2f 秒；最终状态：%s' % (
        datetime.datetime.now().isoformat(timespec='seconds'), time.monotonic() - start, status))
    print('TASK_SUMMARY=' + json.dumps({
        'task': TITLE, 'publishPath': PUBLISH_PATH, 'mode': 'dry-run' if dry else 'live', 'status': status,
        'accountCount': len(cookies), 'successCount': success, 'failureCount': failed,
        'accounts': accounts, 'statistics': totals, 'notification': notification,
        'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
