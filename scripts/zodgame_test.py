#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Zodgame签到与广告任务
# cron: 35 2 * * *
"""Zodgame 自动签到 + 广告任务（独立 HTTP 维护版）。
改造自 miaonai/zodgame-ql 的 zodgame-test.py、zodgame.py，原始说明：
 - zodgame.py (青龙签到脚本)
 - zodgame_checkin (GitHub Actions 版，含 Bux 广告任务)
纯 HTTP 实现，无需浏览器依赖。
ZODGAME_COOKIE：浏览器登录 https://zodgame.xyz 后，从开发者工具网络请求
复制该站请求的完整 Cookie 请求头值；每个非空行一个账号，不含 Cookie: 前缀。
ZODGAME_TASKS：all（默认）、sign 或 bux；保留每天 08:00 的签到和广告流程。
ZODGAME_DEBUG：兼容旧变量，仅输出脱敏诊断，绝不输出响应、URL 或 formhash。
ZODGAME_DRY_RUN=1：完全断网预演，通知仅生成摘要，不调用通知传输。
QINGLONG_NOTIFY=0：关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。

MIT License
Upstream attribution: miaonai/zodgame-ql (MIT).
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
import datetime
import contextlib
import io
import multiprocessing
import html
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.cookiejar import Cookie, CookieJar
from pathlib import Path

BASE = 'https://zodgame.xyz'
TITLE = 'Zodgame签到与广告任务'
TIMEOUT = 30
LIMIT = 2 * 1024 * 1024
OFF = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.inputs, self.links, self.refresh = {}, [], []
        self.anchor = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('name'):
            self.inputs[a['name']] = a.get('value', '')
        if tag == 'strong' and 'vwmy' in a.get('class', '').split():
            self.own_name = True
        if tag == 'a':
            if getattr(self, 'own_name', False):
                a['class'] = a.get('class', '') + ' vwmy'
            self.anchor = [a, '']
        if tag == 'meta' and a.get('http-equiv', '').lower() == 'refresh':
            self.refresh.append(a.get('content', ''))

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor[1] += data

    def handle_endtag(self, tag):
        if tag == 'strong':
            self.own_name = False
        if tag == 'a' and self.anchor is not None:
            self.links.append(self.anchor)
            self.anchor = None


def safe_url(path, base=BASE + '/'):
    url = urllib.parse.urljoin(base, html.unescape(path))
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'zodgame.xyz' or p.port not in (None, 443) or p.username or p.password:
        raise TaskError('拒绝非本站 HTTPS 地址，防止凭据外发')
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_cookie(line):
    values = {}
    for part in line.split(';'):
        part = part.strip()
        if not part:
            continue
        key, sep, value = part.partition('=')
        if not sep or not re.fullmatch(r'[!#$%&\'*+\-.^_`|~0-9a-zA-Z]+', key.strip()) or not value.strip():
            raise TaskError('Cookie 格式错误，请复制完整请求头值')
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise TaskError('Cookie 含非法控制字符')
        values[key.strip()] = value.strip()
    if not values:
        raise TaskError('Cookie 为空')
    return values


class Client:
    def __init__(self, cookies):
        jar = CookieJar()
        for name, value in cookies.items():
            jar.set_cookie(Cookie(0, name, value, None, False, 'zodgame.xyz', False,
                                 False, '/', True, True, None, True, None, None, {}))
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), Redirect())

    def request(self, path, data=None, referer=None):
        if os.getenv('ZODGAME_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}:
            raise TaskError('断网预演禁止 HTTP')
        url = safe_url(path)
        headers = {'User-Agent': 'Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36',
                   'Accept': 'text/html,application/xhtml+xml,*/*', 'Accept-Language': 'zh-CN,zh;q=0.9'}
        if referer:
            headers['Referer'] = safe_url(referer)
        payload = None
        if data is not None:
            headers.update({'Content-Type': 'application/x-www-form-urlencoded', 'Origin': BASE})
            payload = urllib.parse.urlencode(data).encode()
        try:
            with self.opener.open(urllib.request.Request(url, payload, headers), timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise TaskError(f'HTTP 状态异常：{response.status}')
                raw = response.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise TaskError('页面超过大小限制')
                charset = response.headers.get_content_charset() or 'utf-8'
                text = raw.decode(charset, errors='replace')
        except TaskError:
            raise
        except (urllib.error.URLError, OSError, ValueError, LookupError):
            raise TaskError('HTTP 请求失败或超时（已隐藏请求细节）') from None
        if any(s in text for s in ('Just a moment', 'cf-browser-verify', 'cf-challenge')):
            raise TaskError('Cloudflare 验证阻止访问')
        return text


def identity(page):
    for attrs, text in Page(page).links:
        href = attrs.get('href', '')
        if ('mod=space' in href and re.search(r'(?:[?&])uid=\d+', href)
                and ('vwmy' in attrs.get('class', '').split())):
            uid = re.search(r'(?:[?&])uid=(\d+)', href)[1]
            log('官方公开 UID：' + uid)
            name = text.strip()
            if name and not re.search(r'\d{11}', name) and not any(ord(c) < 32 for c in name):
                log('官方用户名：' + name)
            return


def sign(client, formhash):
    text = client.request('/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1',
                          {'formhash': formhash, 'qdxq': 'shuai'})
    if '恭喜你签到成功' in text:
        return 'success', '签到成功'
    if '您今日已经签到，请明天再来' in text:
        return 'alreadyComplete', '今日已签到'
    raise TaskError('签到未返回已知业务成功提示')


def balance(text):
    for pattern in (r'点币[：:]\s*(\d+)', r'<li[^>]*>[^<]*点币[^<]*(\d+)', r'点币[：:][^<]*?(\d+)'):
        match = re.search(pattern, text)
        if match:
            log('当前点币余额：' + match[1])
            return
    log('⚠️ 页面未提供可识别的点币余额')


def bux_page(client):
    text = client.request('/plugin.php?id=jnbux')
    if not any(x in text for x in ('BUX广告点击赚积分', 'jnbux', '点币')):
        raise TaskError('广告页面不符合上游契约，不能判定已完成')
    return text


def advertisement(client, text, onclick):
    function = re.search(r'(openNewWindow[^\s(]*)\s*\(\s*\)', onclick)
    check = re.search(r"showWindow\(\s*['\"]check['\"]\s*,\s*(['\"])(.*?)\1\s*\)", onclick)
    if not function or not check:
        raise TaskError('广告任务动作结构变化')
    ad = re.search(r'function\s+' + re.escape(function[1]) +
                   r'\s*\(\s*\)\s*\{[^}]*?window\.open\(\s*([\'"])(.*?)\1', text, re.S)
    if not ad:
        raise TaskError('广告跳转地址解析失败')
    ad_url, check_url = safe_url(ad[2]), safe_url(check[2])
    page = client.request(ad_url, referer=BASE + '/plugin.php?id=jnbux')
    refresh = Page(page).refresh
    parsed = next((re.match(r'\s*(\d+)\s*;\s*url\s*=\s*(.+)', x, re.I) for x in refresh), None)
    if not parsed:
        raise TaskError('广告缺少观看完成更新地址')
    delay = int(parsed[1])
    if delay > 120:
        raise TaskError('广告等待时间异常')
    update = safe_url(parsed[2].strip().strip('\'"'), ad_url)
    log('广告页已加载，按服务端读秒等待')
    time.sleep(max(3, delay))
    client.request(update, referer=ad_url)
    log('观看完成更新请求已通过 HTTP 检查，等待奖励核验')
    time.sleep(2)
    for attempt in range(2):
        if attempt:
            time.sleep(3)
            log('重试领取结果核验 1/1')
        try:
            result = client.request(check_url, referer=ad_url)
        except TaskError:
            if not attempt:
                continue
            raise
        if '检查成功' in result or '积分已经加入' in result:
            time.sleep(2)
            return 'success', '广告领取成功'
        if 'BUX广告点击赚积分' not in result:
            break
    raise TaskError('广告奖励未返回已知到账提示')


def deliver_notification(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in OFF:
        return '已关闭'
    body = f"模式：{summary['mode']}；账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failed']}；状态：{summary['status']}"
    if dry:
        log('断网预演通知摘要：' + body)
        return '断网预演已生成摘要，未传输'
    try:
        try:
            import notify as module
        except ImportError:
            paths = [Path(os.getenv('QINGLONG_NOTIFY_DIR', '/ql/data/scripts')) / 'notify.py',
                     Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                return '通知模块不可用'
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.send(TITLE, body)
        return '已发送'
    except Exception:
        return '通知发送失败（业务退出码保持不变）'


def notification_worker(summary, queue):
    # 通知模块自身日志也不进入业务日志，避免第三方模块输出凭据。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        queue.put(deliver_notification(summary, False))


def notify(summary, dry):
    if dry or os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in OFF:
        return deliver_notification(summary, dry)
    process = None
    try:
        context = multiprocessing.get_context('spawn')
        queue = context.Queue()
        process = context.Process(target=notification_worker, args=(summary, queue))
        process.start()
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(2)
            return '通知超时（业务退出码保持不变）'
        try:
            return queue.get(timeout=1)
        except Exception:
            return '通知进程失败（业务退出码保持不变）'
    except Exception:
        if process is not None and process.is_alive():
            process.terminate()
        return '通知不可用（业务退出码保持不变）'


def main():
    started = time.monotonic()
    dry = os.getenv('ZODGAME_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    lines = [s.strip() for s in os.getenv('ZODGAME_COOKIE', '').splitlines() if s.strip()]
    selection = os.getenv('ZODGAME_TASKS', 'all').strip().lower()
    log('=' * 48)
    log(TITLE + f' | 开始时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式：{"断网预演" if dry else "正式执行"}；账号数：{len(lines)}')
    summary = {'mode': 'dry-run' if dry else 'live', 'accounts': len(lines), 'success': 0,
               'failed': 0, 'steps': dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)}
    configuration_error = not lines or selection not in {'all', 'sign', 'bux'}
    if configuration_error:
        log('❌ 配置错误：需要 ZODGAME_COOKIE，且 ZODGAME_TASKS 必须为 all/sign/bux')
    for index, line in enumerate(lines if not configuration_error else [], 1):
        acc_start = time.monotonic()
        counts = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
        stage_no = 0
        def stage(label, action):
            nonlocal stage_no
            stage_no += 1
            counts['total'] += 1
            start = time.monotonic()
            log(f'账号 {index} | 阶段 {stage_no}：{label}')
            try:
                status, message = action()
                counts[status] += 1
                log(f'{"☑️" if status == "alreadyComplete" else "✅"} {message}；阶段耗时 {time.monotonic()-start:.2f}s')
                return True
            except Exception as exc:
                counts['failure'] += 1
                message = str(exc) if isinstance(exc, TaskError) else '内部处理失败（已隐藏异常细节）'
                log(f'❌ {message}；阶段耗时 {time.monotonic()-start:.2f}s')
                return False
        client, formhash = None, None
        def prepare():
            nonlocal client, formhash
            cookies = parse_cookie(line)
            if dry:
                return 'success', 'DRY_RUN_OK 参数解析通过，未访问网络'
            client = Client(cookies)
            text = client.request('/')
            identity(text)
            formhash = Page(text).inputs.get('formhash')
            if not formhash:
                raise TaskError('未获取 formhash，请重新登录更新 Cookie')
            return 'success', '会话页面与表单参数获取成功（不输出令牌）'
        ready = stage('参数与会话检查', prepare)
        if ready:
            if selection in {'all', 'sign'}:
                stage('每日签到', lambda: ('success', 'DRY_RUN_OK 签到流程预演，未提交') if dry else sign(client, formhash))
            if selection in {'all', 'bux'}:
                if dry:
                    stage('Bux 加入、观看、更新及领取', lambda: ('success', 'DRY_RUN_OK 广告流程预演，未改变账号状态'))
                    stage('点币余额查询', lambda: ('success', 'DRY_RUN_OK 余额查询预演'))
                else:
                    state = {}
                    def prepare_bux():
                        text = bux_page(client)
                        if '开始参与任务' in text:
                            client.request('/plugin.php?id=jnbux:jnbux&do=join&formhash=' + urllib.parse.quote(formhash), referer=BASE + '/plugin.php?id=jnbux')
                            time.sleep(1)
                            text = bux_page(client)
                            if '开始参与任务' in text:
                                raise TaskError('加入广告任务未得到页面确认')
                            log('首次加入广告任务已确认')
                        tasks = [attrs.get('onclick', '') for attrs, label in Page(text).links if label.strip() == '参与任务']
                        if '参与任务' in text and not tasks:
                            raise TaskError('页面存在任务但结构无法识别，不能判定全部完成')
                        if any(not task for task in tasks):
                            raise TaskError('广告动作缺失，不能判定全部完成')
                        state.update(text=text, tasks=tasks)
                        return ('success', f'发现 {len(tasks)} 个待完成广告任务') if tasks else ('alreadyComplete', '所有广告任务均已完成（有效广告页面无待办）')
                    if stage('Bux 页面及加入状态检查', prepare_bux):
                        for number, onclick in enumerate(state['tasks'], 1):
                            stage(f'广告 {number}/{len(state["tasks"])} 观看与领取', lambda onclick=onclick: advertisement(client, state['text'], onclick))
                    def read_balance():
                        balance(bux_page(client))
                        return 'success', '余额页面查询完成'
                    stage('点币余额查询', read_balance)
        else:
            counts['skipped'] += (2 if selection == 'all' else 1)
            counts['total'] += counts['skipped']
            log('⏭️ 会话准备失败，后续业务阶段跳过')
        failed = counts['failure'] > 0
        summary['failed' if failed else 'success'] += 1
        for key in counts:
            summary['steps'][key] += counts[key]
        log(f'账号 {index} 统计：总任务 {counts["total"]}，成功 {counts["success"]}，已完成 {counts["alreadyComplete"]}，跳过 {counts["skipped"]}，失败 {counts["failure"]}；耗时 {time.monotonic()-acc_start:.2f}s')
    exit_code = 1 if configuration_error or summary['failed'] else 0
    summary['status'] = 'configuration-error' if configuration_error else ('partial-failure' if summary['failed'] and summary['success'] else 'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['finishTime'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('-' * 48)
    log(f'最终任务统计：账号总数 {summary["accounts"]}，成功 {summary["success"]}，失败 {summary["failed"]}；子任务统计：{json.dumps(summary["steps"], ensure_ascii=False)}')
    log(f'完成时间：{summary["finishTime"]}；总耗时：{summary["elapsedSeconds"]}s；通知状态：{summary["notification"]}；最终状态：{summary["status"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
