#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 吾爱破解每日签到
# cron: 25 6 * * *
# SPDX-License-Identifier: Apache-2.0
# Source: HeiDaotu/WFRobertQL, 52pojie.py
"""
File: 52pojie.py
Author: WFRobert
Date: 2023/3/9 15:01
cron: 25 6 * * *
new Env('吾爱破解每日签到');
Description: 52pojie自动签到,实现每日自动签到52pojie
Update: 2023/9/1 更新cron

维护版本（Apache-2.0）：独立运行，仅使用 Python 标准库。
功能盘点：原版依次访问会话准备、申请任务 id=2、领取任务 id=2；
输入 PJ52_COOKIE，旧版用 & 分账号；每天 06:25；副作用仅申请及领取签到奖励。
本版改为每个非空行一个账号，保留变量名、时间和业务链；不发表内容。
登录 https://www.52pojie.cn 后，从浏览器开发者工具的网络请求复制 Cookie。
每行必须含 htVC_2132_saltkey 和 htVC_2132_auth，值中的 = 原样保留；
也兼容整段 URL 编码的 Cookie。不要分享 Cookie，不要用 & 或 @ 分账号。
PJ52_DRY_RUN=1：离线验证参数并预演三个步骤，不调用网站或通知网络。
QINGLONG_NOTIFY=auto|1|0；auto 默认选择本脚本，设置
QINGLONG_NOTIFY_SCRIPTS 可替换默认选择（逗号、分号、空白分隔；空值禁用）。
QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。通知失败不改变业务退出码。
原版把“不是进行中的任务”当作签到完成，本版将其视为无法确认，失败退出；
只有明确完成/已完成提示才算成功，避免把尚未申请的任务误报为已签到。
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
        _ql_notify_identities = ('11b4c2ed42746ce1', 'scripts/52pojie.py', '52pojie.py', '52pojie')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
import html.parser
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TITLE = '吾爱破解每日签到'
CATALOG_ID = '11b4c2ed42746ce1'
BASE = 'https://www.52pojie.cn/'
URLS = (
    BASE + 'CSPDREL2hvbWUucGhwP21vZD10YXNrJmRvPWRyYXcmaWQ9Mg==?wzwscspd=MC4wLjAuMA==',
    BASE + 'home.php?mod=task&do=apply&id=2&referer=%2F',
    BASE + 'home.php?mod=task&do=draw&id=2',
)
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


def log(text):
    print('[{}] {}'.format(datetime.datetime.now().strftime('%H:%M:%S'), text), flush=True)


class TaskError(Exception):
    pass


def parse_cookie(line):
    # Decode only an encoded *whole* cookie; never split a credential value at '='.
    if '=' not in line:
        line = urllib.parse.unquote(line)
    if any(ord(c) < 32 or ord(c) > 126 for c in line):
        raise TaskError('Cookie 含非法字符，请重新复制浏览器请求头')
    fields = {}
    for part in line.split(';'):
        key, sep, value = part.strip().partition('=')
        if key in ('htVC_2132_auth', 'htVC_2132_saltkey'):
            if key in fields:
                raise TaskError('Cookie 凭据字段重复，请检查每行是否仅有一个账号')
            fields[key] = value if sep else ''
    if not all(fields.get(k) for k in ('htVC_2132_auth', 'htVC_2132_saltkey')):
        raise TaskError('Cookie 必须同时包含 htVC_2132_auth 和 htVC_2132_saltkey')
    return fields


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.message_parts = []
        self.identity_parts = []
        self.identity = ''
        self.in_identity = False
        self.login = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id') == 'messagetext':
            self.depth = 1
        elif self.depth and tag not in ('br', 'img', 'input', 'meta', 'link', 'hr', 'wbr', 'source'):
            self.depth += 1
        if tag == 'a':
            href = a.get('href', '')
            self.in_identity = ('mod=space' in href and 'uid=' in href
                                and ('avtm' not in a.get('class', '')))
            self.identity_parts = []
        if tag == 'input' and (a.get('name') == 'password' or a.get('type') == 'password'):
            self.login = True

    def handle_endtag(self, tag):
        if self.depth and tag not in ('br', 'img', 'input', 'meta', 'link', 'hr'):
            self.depth -= 1
        if tag == 'a' and self.in_identity:
            value = ''.join(self.identity_parts).strip()
            if value and not self.identity:
                self.identity = value
            self.in_identity = False

    def handle_data(self, data):
        if self.depth:
            self.message_parts.append(data)
        if self.in_identity:
            self.identity_parts.append(data)

    @property
    def message(self):
        return re.sub(r'\s+', ' ', ''.join(self.message_parts)).strip()


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (parsed.scheme != 'https' or parsed.hostname != 'www.52pojie.cn'
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise TaskError('拒绝向站外或非 HTTPS 地址跳转')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, fields):
        jar = http.cookiejar.CookieJar()
        for name, value in fields.items():
            jar.set_cookie(http.cookiejar.Cookie(
                0, name, value, None, False, 'www.52pojie.cn', False, False,
                '/', True, True, None, True, None, None, {}, False))
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), SafeRedirect(),
            urllib.request.HTTPCookieProcessor(jar))

    def get(self, url):
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; Qinglong52Checkin/1.0)',
            'Accept': 'text/html', 'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'identity', 'Referer': BASE,
        })
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskError('响应过大，停止处理')
                charset = response.headers.get_content_charset()
                if not charset:
                    match = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
                    charset = match.group(1).decode('ascii') if match else 'gb18030'
                page = Page()
                page.feed(raw.decode(charset, errors='strict'))
                return page
        except TaskError:
            raise
        except Exception:
            # URLs, headers, cookie jars and raw responses are never logged.
            raise TaskError('请求或响应解析失败（网络、超时、HTTP 或编码异常）') from None


def safe_identity(value, fields):
    # Public identity is printed verbatim unless it contains a secret or phone number.
    if (any(s in value for s in fields.values())
            or any(urllib.parse.unquote(s) in value for s in fields.values())
            or re.search(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', value)
            or re.search(r'(?:cookie|token|session|saltkey|auth)\s*=', value, re.I)
            or any(ord(c) < 32 for c in value)):
        return ''
    return value


def result_status(page):
    msg = page.message
    if page.login or any(x in msg for x in ('您需要先登录', '请先登录', '尚未登录', '登录后')):
        raise TaskError('账号未登录或 Cookie 已失效')
    if any(x in msg for x in ('失败', '错误', '未完成', '未能', '无法', '不能', '尚未')):
        raise TaskError('官方提示任务未完成或无法领取，请在网站核对')
    if any(x in msg for x in ('您已完成', '本期您已完成', '今日已签到', '今天已经签到', '已经领取过', '已领取奖励')):
        return 'alreadyComplete'
    if any(x in msg for x in ('任务已成功完成', '任务完成，您将', '签到成功', '成功领取')):
        return 'success'
    if '不是进行中的任务' in msg:
        raise TaskError('任务不在进行中，无法据此确认今日签到完成')
    raise TaskError('没有收到明确的业务成功提示，请在网站核对签到状态')


def notification(summary, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    names = (CATALOG_ID, '52pojie.py', 'candidate.py', 'output/candidate.py',
             Path(__file__).name, '吾爱破解每日签到')
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        log('⚠️ QINGLONG_NOTIFY 值无效，通知未发送')
        return '配置无效'
    if switch == 'auto' and 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        if not any(fnmatch.fnmatch(n, p) for n in names for p in selectors if p):
            return '未被选择'
    body = ('模式：{}；状态：{}；账号总数：{}；成功数：{}；失败数：{}；跳过数：{}'
            .format(summary['mode'], summary['status'], summary['accounts'],
                    summary['success'], summary['failed'], summary['skipped']))
    if dry:
        log('⏭️ 离线通知预览：' + body)
        return '离线预览（未联网）'
    # Bound helper runtime and suppress helper output, even when a notifier fails.
    helper = r'''
import importlib.util, json, sys
kind, path = sys.argv[1:3]
title, body = json.load(sys.stdin)
if kind == 'module':
    import notify
else:
    sys.path.insert(0, str(__import__('pathlib').Path(path).parent))
    spec = importlib.util.spec_from_file_location('notify', path)
    notify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notify)
notify.send(title, body)
'''
    candidates = []
    try:
        if importlib.util.find_spec('notify'):
            candidates.append(('module', ''))
    except (ImportError, ValueError):
        pass
    directories = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        directories.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    directories.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    for directory in directories:
        if (directory / 'notify.py').is_file():
            candidates.append(('file', str(directory / 'notify.py')))
    payload = json.dumps([TITLE, body], ensure_ascii=False)
    for kind, path in candidates:
        try:
            proc = subprocess.run([sys.executable, '-c', helper, kind, path],
                                  input=payload, text=True, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=30, check=False)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    js = "const [t,b]=JSON.parse(require('fs').readFileSync(0,'utf8'));Promise.resolve(require(process.argv[1]).sendNotify(t,b)).catch(()=>process.exit(1));"
    for directory in directories:
        path = directory / 'sendNotify.js'
        if not path.is_file():
            continue
        try:
            proc = subprocess.run(['node', '-e', js, str(path)], input=payload,
                                  text=True, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=30, check=False)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 青龙通知不可用或发送失败，保留业务退出码')
    return '不可用或失败'


def main():
    started = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    raw_mode = os.environ.get('PJ52_DRY_RUN', '0').strip().lower()
    dry = raw_mode in TRUE
    accounts = [x.strip() for x in os.environ.get('PJ52_COOKIE', '').splitlines() if x.strip()]
    log('运行模式：{}；账号数：{}'.format('离线预演' if dry else '正式签到', len(accounts)))
    totals = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
    results = []
    config_error = not accounts or raw_mode not in TRUE | FALSE
    if config_error:
        log('❌ 配置错误：请设置 PJ52_COOKIE；PJ52_DRY_RUN 仅接受 0/1/true/false/yes/no/on/off')
    else:
        for index, line in enumerate(accounts, 1):
            began = time.monotonic()
            counts = dict(total=3, success=0, alreadyComplete=0, skipped=0, failed=0)
            log('---------- 账号 {} ----------'.format(index))
            stage = 1
            step_start = time.monotonic()
            try:
                fields = parse_cookie(line)
                client = None if dry else Client(fields)
                for stage, (label, url) in enumerate(zip(('会话准备', '申请每日任务', '领取签到奖励'), URLS), 1):
                    step_start = time.monotonic()
                    log('账号 {} 阶段 {}/3：{}'.format(index, stage, label))
                    if dry:
                        counts['skipped'] += 1
                        log('⏭️ 参数有效；离线预演跳过请求；耗时 {:.3f} 秒'.format(time.monotonic() - step_start))
                        continue
                    page = client.get(url)
                    identity = safe_identity(page.identity, fields)
                    if identity:
                        log('账号 {} 身份：{}'.format(index, identity))
                    if page.login or any(x in page.message for x in ('您需要先登录', '请先登录', '尚未登录')):
                        raise TaskError('账号未登录或 Cookie 已失效')
                    status = result_status(page) if stage == 3 else 'success'
                    counts[status] += 1
                    log('{} {}；耗时 {:.3f} 秒'.format(
                        '☑️' if status == 'alreadyComplete' else '✅',
                        '今日已签到' if status == 'alreadyComplete' else ('签到成功' if stage == 3 else '请求完成（等待最终业务确认）'),
                        time.monotonic() - step_start))
                status = 'dry-run' if dry else 'success'
            except Exception as error:
                counts['failed'] += 1
                counts['skipped'] += 3 - stage
                status = 'failure'
                reason = str(error) if isinstance(error, TaskError) else '内部处理异常，已隐藏敏感详情'
                log('❌ 账号 {} 阶段 {}/3：{}；耗时 {:.3f} 秒'.format(index, stage, reason, time.monotonic() - step_start))
            results.append(status)
            for key in totals:
                totals[key] += counts[key]
            log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}；耗时 {:.3f} 秒'.format(
                index, counts['total'], counts['success'], counts['alreadyComplete'],
                counts['skipped'], counts['failed'], time.monotonic() - began))
    failed = results.count('failure')
    successful = results.count('success')
    skipped = results.count('dry-run')
    if config_error:
        status = 'configuration-error'
    elif failed:
        status = 'partial-failure' if successful else 'failure'
    else:
        status = 'dry-run' if dry else 'success'
    summary = dict(task=TITLE, mode='dry-run' if dry else 'live', status=status,
                   accounts=len(accounts), success=successful, failed=failed,
                   skipped=skipped, configurationErrors=int(config_error), stages=totals)
    notify_state = notification(summary, dry or raw_mode not in TRUE | FALSE)
    summary['notification'] = notify_state
    summary['durationSeconds'] = round(time.monotonic() - started, 3)
    summary['finishedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('任务统计：账号 {}，成功 {}，失败 {}，预演 {}；子任务 {}'.format(
        len(accounts), successful, failed, skipped, json.dumps(totals, ensure_ascii=False)))
    log('通知状态：{}；总耗时 {} 秒'.format(notify_state, summary['durationSeconds']))
    log('完成时间：{}；最终状态：{}'.format(summary['finishedAt'], status))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return 1 if failed or config_error else 0


if __name__ == '__main__':
    sys.exit(main())
