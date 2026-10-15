#!/usr/bin/env python3
# name: 精易论坛签到
# cron: 2 2 * * *
# 上游未声明 cron；维护版建议每日北京时间 08:00 执行。
# 来源：CSDN2024/QianDaoMZH，JingYiLunTan-sign.py
# 上游提交：b99c67e46d1e74d2fd3a0bff7cac3f83e5ee6903
# SPDX-License-Identifier: GPL-3.0
# 本维护版沿用上游 GPL-3.0 许可。上游文件没有其他版权声明。
"""精易论坛每日签到；JYLT_Cookie 每个非空行一个已登录账号的完整 Cookie。
浏览器登录 https://bbs.125.la 后，从开发者工具网络面板本站请求头复制 Cookie。
JYLT_RATE=1 显式开启热门帖评分（每帖 score4=+1，可能消耗评分额度）。
JYLT_DRY_RUN=1 完全断网预演，包括模拟通知；不验证登录或业务成功。
评分附言首先读取一言，失败使用 JYLT_LOCAL_TEXT 或内置本地文字。
"""
import datetime
import html
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://bbs.125.la/'
TITLE = '精易论坛签到'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


def log(message):
    print('[{}] {}'.format(datetime.datetime.now().strftime('%H:%M:%S'), message), flush=True)


class TaskError(Exception):
    pass


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hashes, self.threads, self.rate, self.identity = [], [], [], None
        self.identity_depth = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('name') == 'formhash':
            self.hashes.append(a.get('value', ''))
        if tag == 'a':
            href = a.get('href', '')
            if 'action=logout' in href:
                self.hashes.extend(urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get('formhash', []))
            if re.fullmatch(r'/?thread-\d+-\d+-\d+\.html', href):
                self.threads.append(urllib.parse.urljoin(BASE, href))
            if a.get('class') == 'vwmy' or ('vwmy' in a.get('class', '').split()):
                self.identity_depth = 1
        if a.get('id') == 'ak_rate':
            self.rate.append(a.get('onclick', ''))

    def handle_endtag(self, tag):
        if tag == 'a':
            self.identity_depth = 0

    def handle_data(self, data):
        if self.identity_depth and data.strip():
            self.identity = (self.identity or '') + data.strip()

    def formhash(self):
        for value in self.hashes:
            if re.fullmatch(r'[a-zA-Z0-9]{6,32}', value):
                return value
        raise TaskError('未取得有效表单令牌，请更新登录 Cookie')


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urljoin(req.full_url, newurl)
        if urllib.parse.urlsplit(url).scheme != 'https' or urllib.parse.urlsplit(url).netloc != 'bbs.125.la':
            raise TaskError('拒绝向外站或非 HTTPS 地址转发登录请求')
        return super().redirect_request(req, fp, code, msg, headers, url)


class Client:
    def __init__(self, cookie):
        self.cookie = cookie
        self.opener = urllib.request.build_opener(SameHostRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, url, data=None, referer=None):
        if urllib.parse.urlsplit(url).netloc != 'bbs.125.la':
            raise TaskError('拒绝非本站业务请求')
        headers = {'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0', 'Referer': referer or BASE}
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskError('业务响应超过大小限制')
                return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
        except TaskError:
            raise
        except Exception:
            raise TaskError('业务网络请求失败或超时') from None


def clean(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def public_text():
    # 独立请求，不携带 Cookie 或其他账号信息。
    fallback = clean(os.getenv('JYLT_LOCAL_TEXT', '感谢分享，很给力！~'))
    if not fallback or len(fallback) > 280 or any(ord(c) < 32 for c in fallback):
        fallback = '感谢分享，很给力！~'
    try:
        req = urllib.request.Request('https://v1.hitokoto.cn/?encode=json', headers={'User-Agent': 'Qinglong-JYLT'})
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError()
        obj = json.loads(raw)
        text, author, source = [clean(obj.get(key)) for key in ('hitokoto', 'from_who', 'from')]
        if not text:
            raise ValueError()
        if author and source:
            text += ' —— {}《{}》'.format(author, source)
        elif source:
            text += ' ——《{}》'.format(source)
        elif author:
            text += ' —— ' + author
        if len(text) > 280:
            raise ValueError()
        log('评分附言：一言内容及出处已取得（不输出正文）')
        return text
    except Exception:
        log('⚠️ 评分附言：提供方不可用或内容不合规，使用本地文字')
        return fallback


def sign_result(text):
    # 兼容 JSON 与 Discuz XML/HTML 包装；仅识别明确业务信息。
    match = re.search(r'\{\s*"status"\s*:\s*-?\d+\s*,\s*"msg"\s*:\s*"(?:[^"\\]|\\.)*"\s*\}', text)
    if not match:
        raise TaskError('签到响应结构无法确认')
    obj = json.loads(match.group())
    message = obj.get('msg', '')
    if any(s in message for s in ('已经签到', '已签到', '已经签过', '今日已签')):
        return 'already'
    if obj.get('status') == 0 and any(s in message for s in ('签到成功', '签到了', '签到完成')):
        return 'success'
    raise TaskError('签到未返回明确成功标志，请检查登录状态和论坛提示')


def run_account(cookie, index, dry, rate):
    stats = dict(total=0, success=0, already=0, skipped=0, failed=0)
    started = time.monotonic()
    def stage(number, name, action):
        before = time.monotonic()
        stats['total'] += 1
        log('账号 {} 阶段 {}：{}'.format(index, number, name))
        try:
            result = action()
            stats[result] += 1
            log('账号 {} 阶段 {}：{}，耗时 {:.2f} 秒'.format(index, number, {'success': '✅ 成功', 'already': '☑️ 已完成', 'skipped': '⏭️ 预演或未开启'}[result], time.monotonic() - before))
            return True
        except Exception as exc:
            stats['failed'] += 1
            message = str(exc) if isinstance(exc, TaskError) else '响应解析或本地处理失败'
            log('账号 {} 阶段 {}：❌ {}，耗时 {:.2f} 秒'.format(index, number, message, time.monotonic() - before))
            return False
    if dry:
        stage(1, '模拟登录页面与令牌读取（无网络）', lambda: 'skipped')
        stage(2, '模拟每日签到（无状态变更）', lambda: 'skipped')
        stage(3, '模拟热门帖评分' if rate else '热门帖评分未开启', lambda: 'skipped')
    else:
        client = Client(cookie)
        state = {}
        def login():
            page = Page(client.request(BASE + 'plugin.php?id=dsu_paulsign:sign'))
            state['hash'] = page.formhash()
            state['threads'] = list(dict.fromkeys(page.threads))
            if page.identity:
                # 输出官方昵称，不输出登录令牌或原始页面。
                identity = clean(page.identity)
                if cookie not in identity and not re.search(r'1[3-9]\d{9}', identity):
                    log('账号 {} 官方昵称：{}'.format(index, identity))
            return 'success'
        if stage(1, '获取登录页面、表单令牌与热门帖', login):
            stage(2, '每日签到', lambda: sign_result(client.request(BASE + 'plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1', {'formhash': state['hash'], 'submit': '1', 'targerurl': '', 'todaysay': '', 'qdxq': 'kx'})))
            if rate:
                reason = public_text()
                if not state['threads']:
                    stage(3, '热门帖评分', lambda: (_ for _ in ()).throw(TaskError('页面没有可评分热门帖，无法确认完成')))
                for n, url in enumerate(state['threads'], 3):
                    def rating(url=url):
                        text = client.request(url)
                        page = Page(text)
                        points = re.search(r'class=["\']showmenu["\']>积分:\s*(\d+)', text)
                        if points:
                            log('账号 {} 积分：{}'.format(index, points.group(1)))
                        params = {}
                        for onclick in page.rate:
                            for key in ('tid', 'pid'):
                                match = re.search(r'(?:[?&])' + key + r'=(\d+)', onclick)
                                if match:
                                    params[key] = match.group(1)
                        if set(params) != {'tid', 'pid'}:
                            raise TaskError('未取得评分帖子参数')
                        params.update(formhash=page.formhash(), referer=url, handlekey='rate', score4='+1', reason=reason)
                        result = client.request(BASE + 'forum.php?mod=misc&action=rate&ratesubmit=yes&infloat=yes&inajax=1', params, url)
                        visible = html.unescape(re.sub(r'<[^>]+>', ' ', result))
                        if '超过限制' in visible:
                            raise TaskError('评分次数超过限制，停止评分')
                        if not any(s in visible for s in ('评分成功', '评分完成')):
                            raise TaskError('评分响应没有明确成功标志')
                        return 'success'
                    if not stage(n, '热门帖评分 +1', rating):
                        break
                    time.sleep(2)
            else:
                stage(3, '热门帖评分未开启', lambda: 'skipped')
    log('账号 {} 统计：总任务 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}；耗时 {elapsed:.2f} 秒'.format(index, elapsed=time.monotonic()-started, **stats))
    return stats


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in FALSE:
        return '已关闭'
    if dry:
        log('⏭️ 断网预演通知：' + body)
        return '已模拟（无网络）'
    # 通知模块为可选集成，子进程限制耗时且不回显模块输出。
    code = """import importlib.util, os, pathlib, sys
try:
    import notify
except ImportError:
    notify = None
if notify is None:
    roots = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for root in roots:
        if not root: continue
        p = pathlib.Path(root) / 'notify.py'
        if p.is_file():
            spec = importlib.util.spec_from_file_location('notify', p)
            notify = importlib.util.module_from_spec(spec)
            sys.path.insert(0, root)
            spec.loader.exec_module(notify)
            break
if notify is None: sys.exit(3)
notify.send(sys.argv[1], sys.argv[2])
"""
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, body], capture_output=True, timeout=30)
        if result.returncode == 0:
            return '已发送'
        if result.returncode == 3:
            for root in [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']:
                if root and (Path(root) / 'sendNotify.js').is_file():
                    js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
                    result = subprocess.run(['node', '-e', js, str(Path(root)/'sendNotify.js'), TITLE, body], capture_output=True, timeout=30)
                    return '已发送' if result.returncode == 0 else '发送失败'
        return '不可用或发送失败'
    except Exception:
        return '不可用或发送失败'


def main():
    started = time.monotonic()
    dry = os.getenv('JYLT_DRY_RUN', '').lower() in TRUE
    rate = os.getenv('JYLT_RATE', '0').lower() in TRUE
    accounts = [line.strip() for line in os.getenv('JYLT_Cookie', '').splitlines() if line.strip()]
    log('========== 精易论坛签到 ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('运行模式：{}；账号数：{}'.format('断网预演' if dry else '正式', len(accounts)))
    results = []
    config_error = not accounts or any(any(ord(c) < 32 or ord(c) > 255 for c in cookie) for cookie in accounts)
    if config_error:
        log('❌ 配置错误：请设置 JYLT_Cookie，每个非空行一个有效 HTTP Cookie，不含控制字符')
    else:
        for index, cookie in enumerate(accounts, 1):
            results.append(run_account(cookie, index, dry, rate))
    failed = len(accounts) if config_error else sum(s['failed'] > 0 for s in results)
    passed = 0 if config_error else len(results) - failed
    status = 'configuration-error' if config_error else ('partial-failure' if failed and passed else 'failure' if failed else 'dry-run' if dry else 'success')
    body = '状态：{}；账号总数：{}；成功数：{}；失败数：{}{}'.format(status, len(accounts), passed, failed, '；预演未验证业务' if dry else '')
    notification = notify(body, dry)
    totals = {key: sum(s[key] for s in results) for key in ('total', 'success', 'already', 'skipped', 'failed')}
    log('----------------------------------------')
    log(body)
    log('子任务统计：总任务 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}'.format(**totals))
    log('总耗时：{:.2f} 秒；通知：{}'.format(time.monotonic()-started, notification))
    log('完成时间：{}；最终状态：{}'.format(datetime.datetime.now().isoformat(timespec='seconds'), status))
    print('TASK_SUMMARY=' + json.dumps(dict(status=status, mode='dry-run' if dry else 'live', accounts=len(accounts), successfulAccounts=passed, failedAccounts=failed, tasks=totals, notification=notification), ensure_ascii=False, separators=(',', ':')))
    if not config_error and not failed:
        print('DRY_RUN_OK' if dry else '精易论坛任务成功')
    print('执行完毕~')
    return 1 if config_error or failed else 0


if __name__ == '__main__':
    sys.exit(main())
