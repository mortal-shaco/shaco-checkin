#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# name: 微博超话签到
# cron: 51 10 * * *
# 原作未指定 cron；以上为维护版建议每日计划。
'''
@author: 'FenG'
@date: 2018/7/7 17:27
@file: $NAME.py
来源：Feeeenng/weibo_auto_sign / weibo_sign.py，MIT。

配置：WEIBO_ACCOUNTS 每个非空行填写 登录账号|登录密码，只在首个 | 分割。
账号密码来自本人微博登录凭据；不输出它们。登录遇到验证码或风控时，
请在官方客户端处理后重试；本脚本不绕过验证。原 Config 私有模块不再需要。
WEIBO_DRY_RUN=1 完全断网预演（包括不发送外部通知）。
QINGLONG_NOTIFY=auto 默认仅对 QINGLONG_NOTIFY_SCRIPTS 匹配项发送；
设为 1 启用，0 禁用。可用目录 QINGLONG_NOTIFY_DIR 指向青龙通知文件。
脚本仅执行关注超话签到，不发布、评论、关注或修改账号资料。

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
'''
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
        _ql_notify_identities = ('4e0d6792d68f2033', 'scripts/weibo_sign.py', 'weibo_sign.py', 'weibo_sign')
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
import importlib
import importlib.util
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

TITLE = '微博超话签到'
CATALOG_ID = '4e0d6792d68f2033'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
TIMEOUT = 15
MAX_BYTES = 1048576
SECRETS = []


class TaskError(Exception):
    pass


def clean(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[敏感信息]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号]', text)
    return ' '.join(text.split())[:240]


def log(message):
    print('[{}] {}'.format(time.strftime('%H:%M:%S'), message), flush=True)


def allowed_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and any(host == domain or host.endswith('.' + domain)
                    for domain in ('weibo.cn', 'weibo.com', 'sina.com.cn')))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.get_method() != 'GET' or not allowed_url(newurl):
            raise TaskError('登录重定向或接口地址不符合安全约束，请检查官方登录状态')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Weibo:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), SafeRedirect())

    def request(self, url, data=None, referer=None, as_json=True):
        if not allowed_url(url):
            raise TaskError('接口地址不符合 HTTPS 官方域名约束')
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        if referer:
            headers['Referer'] = referer
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data is not None else None,
                                     headers=headers)
        try:
            with self.opener.open(req, timeout=TIMEOUT) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise TaskError('接口响应超过大小限制')
                if not as_json:
                    return None
                result = json.loads(body.decode('utf-8'))
                if not isinstance(result, dict):
                    raise TaskError('接口响应结构异常')
                return result
        except urllib.error.HTTPError as exc:
            raise TaskError('接口 HTTP 状态异常：{}'.format(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('接口连接失败或超时') from None
        except (ValueError, UnicodeError):
            raise TaskError('接口响应不是有效 JSON') from None

    def login(self, username, password):
        result = self.request('https://passport.weibo.cn/sso/login',
                              {'username': username, 'password': password},
                              'https://passport.weibo.cn/signin/login?entry=mweibo&r=http%3A%2F%2Fm.weibo.cn')
        if str(result.get('retcode')) != '20000000':
            raise TaskError('登录未获业务成功确认，请核对账号密码并在官方客户端处理风控或验证码')
        data = result.get('data')
        if not isinstance(data, dict):
            raise TaskError('登录成功响应缺少账号数据')
        for key in ('screen_name', 'nickname', 'username', 'uid'):
            if data.get(key):
                log('官方账号身份 {}：{}'.format(key, clean(data[key])))
        # 若官方登录响应提供跨域同步地址，使用 CookieJar 按域同步，绝不手工传递 Set-Cookie。
        cross = data.get('crossdomainlist', {})
        urls = list(cross.values()) if isinstance(cross, dict) else cross
        if not isinstance(urls, list):
            raise TaskError('登录跨域同步字段结构异常')
        for url in urls:
            if not isinstance(url, str) or not allowed_url(url):
                raise TaskError('官方登录返回的跨域地址不符合安全约束')
            self.request(url, as_json=False)

    def topics(self):
        url = 'https://m.weibo.cn/api/container/getIndex?containerid=100803_-_page_my_follow_super'
        result, topics, seen_pages = None, [], set()
        # 原作仅取首组 [1:-1]，会漏掉实际超话；遍历卡组并跟随官方 since_id。
        for _ in range(100):
            result = self.request(url)
            if str(result.get('ok')) != '1':
                raise TaskError('关注超话列表未获业务成功确认')
            data = result.get('data')
            if not isinstance(data, dict) or not isinstance(data.get('cards'), list):
                raise TaskError('关注超话列表结构异常')
            found = []

            def walk(cards):
                for card in cards:
                    if not isinstance(card, dict):
                        raise TaskError('超话卡片结构异常')
                    if isinstance(card.get('card_group'), list):
                        walk(card['card_group'])
                    if card.get('title_sub') and card.get('scheme'):
                        query = urllib.parse.parse_qs(urllib.parse.urlsplit(card['scheme']).query)
                        ids = query.get('containerid', [])
                        if not ids or not ids[0].startswith('100808'):
                            raise TaskError('超话卡片缺少可识别的超话编号，停止以免漏签或误签')
                        found.append((ids[0], card['title_sub'], card.get('desc1', '未提供等级')))
            walk(data['cards'])
            if data['cards'] and not found and not topics:
                # 无证据确认「无关注」时，禁止把未知响应当作签到成功。
                raise TaskError('列表含卡片但没有可识别超话，请核对关注列表或接口结构')
            known = {item[0] for item in topics}
            topics.extend(item for item in found if item[0] not in known and not known.add(item[0]))
            info = data.get('pageInfo', {})
            since = info.get('since_id') if isinstance(info, dict) else None
            if not since:
                return topics
            since = str(since)
            if since in seen_pages:
                raise TaskError('超话列表分页游标重复，无法确认完整列表')
            seen_pages.add(since)
            url = ('https://m.weibo.cn/api/container/getIndex?' + urllib.parse.urlencode({
                'containerid': '100803_-_page_my_follow_super', 'since_id': since}))
        raise TaskError('超话列表超过分页安全上限')

    def sign(self, topic_id):
        # api 为上游接口约定的路由参数；客户端实际请求始终使用 HTTPS。
        url = 'https://weibo.com/p/aj/general/button?' + urllib.parse.urlencode({
            'api': 'http://i.huati.weibo.com/aj/super/checkin', 'id': topic_id})
        result = self.request(url)
        if str(result.get('code')) != '100000':
            raise TaskError('超话签到未获业务成功确认（仅认可上游明确成功码 100000）')


def notify(summary, dry):
    body = '{}：账号总数 {}，成功 {}，失败 {}；状态 {}。'.format(
        TITLE, summary['accounts'], summary['success'], summary['failed'], summary['status'])
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').lower().strip()
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    path = Path(__file__).resolve()
    relative = str(path).split('/scripts/', 1)[-1]
    names = {CATALOG_ID, path.name, relative, 'weibo_sign.py', 'checkin/weibo_sign.py'}
    selected = (any(fnmatch.fnmatch(name, selector)
                    for selector in re.split(r'[,;\s]+', selectors.strip()) if selector
                    for name in names) if selectors is not None else switch in TRUE)
    if switch in FALSE or not selected:
        log('通知：已按全局开关或脚本选择关闭')
        return 'disabled'
    if dry:
        log('通知：断网演练已生成脱敏摘要，不调用通知网络：' + body)
        return 'dry-run'
    # 通知模块输出不进入任务日志，防止通道配置或异常泄露凭据。
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                module = None
            if module is not None and callable(getattr(module, 'send', None)):
                module.send(TITLE, body)
                return 'sent'
            dirs = ([Path(os.environ['QINGLONG_NOTIFY_DIR'])] if os.getenv('QINGLONG_NOTIFY_DIR') else [])
            dirs += [Path('/ql/data/scripts'), Path('/ql/scripts')]
            for directory in dirs:
                file = directory / 'notify.py'
                if file.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.send(TITLE, body)
                    return 'sent'
            for directory in dirs:
                file = directory / 'sendNotify.js'
                if file.is_file():
                    subprocess.run(['node', '-e',
                                    'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',
                                    str(file), TITLE, body], stdout=sink, stderr=sink, timeout=30, check=True)
                    return 'sent'
        log('通知：青龙通知模块不可用，保留业务退出码')
        return 'unavailable'
    except Exception:
        log('通知：发送失败，保留业务退出码')
        return 'failed'


def run():
    started = time.monotonic()
    dry = os.getenv('WEIBO_DRY_RUN', '').lower() in TRUE
    lines = [line.strip() for line in os.getenv('WEIBO_ACCOUNTS', '').splitlines() if line.strip()]
    for line in lines:
        SECRETS.extend(line.split('|', 1))
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines),
               'success': 0, 'failed': 0, 'tasks': {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}}
    log('========== 微博超话签到 ==========')
    log('开始时间：{}；模式：{}；账号数：{}'.format(time.strftime('%Y-%m-%d %H:%M:%S'), summary['mode'], len(lines)))
    config_error = not lines
    if not lines:
        log('❌ 配置错误：请设置 WEIBO_ACCOUNTS，每行填写 登录账号|登录密码')
    for index, line in enumerate(lines, 1):
        tick = time.monotonic()
        stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        failed = False
        log('---- 账号 {} ----'.format(index))
        try:
            stage = time.monotonic()
            log('阶段 1/3：检查账号配置')
            pair = line.split('|', 1)
            if len(pair) != 2 or not all(pair):
                config_error = True
                raise TaskError('配置格式无效，需要 登录账号|登录密码，仅在首个 | 分割')
            log('✅ 阶段 1/3 完成，耗时 {:.2f} 秒'.format(time.monotonic() - stage))
            if dry:
                log('阶段 2/3：断网演练，已验证凭据结构，跳过登录与超话查询；耗时 0.00 秒')
                log('阶段 3/3：断网演练，跳过签到；耗时 0.00 秒；未验证真实业务')
                stats.update(total=2, skipped=2)
            else:
                stage = time.monotonic()
                log('阶段 2/3：登录并读取关注超话')
                client = Weibo()
                client.login(*pair)
                log('✅ 登录已获业务成功确认')
                topics = client.topics()
                log('✅ 阶段 2/3 完成，超话数 {}，耗时 {:.2f} 秒'.format(len(topics), time.monotonic() - stage))
                stage = time.monotonic()
                log('阶段 3/3：逐个超话签到')
                for number, (topic_id, title, level) in enumerate(topics, 1):
                    step = time.monotonic()
                    stats['total'] += 1
                    try:
                        client.sign(topic_id)
                        stats['success'] += 1
                        log('✅ 超话 {}/{} {}；等级 {}：签到成功；耗时 {:.2f} 秒'.format(number, len(topics), clean(title), clean(level), time.monotonic() - step))
                    except TaskError as exc:
                        failed = True
                        stats['failed'] += 1
                        log('❌ 超话 {}/{} {}：{}；耗时 {:.2f} 秒'.format(number, len(topics), clean(title), exc, time.monotonic() - step))
                if not topics:
                    log('☑️ 官方列表为空，无关注超话可签到')
                log('阶段 3/3 完成，耗时 {:.2f} 秒'.format(time.monotonic() - stage))
        except Exception as exc:
            failed = True
            stats['total'] += 1
            stats['failed'] += 1
            log('❌ {}'.format(str(exc) if isinstance(exc, TaskError) else '处理异常，已隐藏异常详情'))
        summary['failed' if failed else 'success'] += 1
        for key in stats:
            summary['tasks'][key] += stats[key]
        log('账号 {} 统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failed}；耗时 {elapsed:.2f} 秒'.format(index, elapsed=time.monotonic() - tick, **stats))
    code = 1 if config_error or summary['failed'] else 0
    summary['status'] = ('configuration-error' if config_error else
                         'partial-failure' if summary['failed'] and summary['success'] else
                         'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    log('----------------------------------------')
    log('账号总数 {accounts}，成功 {success}，失败 {failed}'.format(**summary))
    log('子任务：' + json.dumps(summary['tasks'], ensure_ascii=False))
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishTime'] = time.strftime('%Y-%m-%d %H:%M:%S')
    log('总耗时 {} 秒；完成时间 {}；通知状态 {}；最终状态 {}'.format(summary['elapsedSeconds'], summary['finishTime'], summary['notification'], summary['status']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(run())
