# -*- coding: utf-8 -*-
# name: 奶昔论坛签到
# cron: 37 10 * * *
# SPDX-License-Identifier: GPL-3.0
# Derived from icebergOcean/clockin, naixi_qinglong.py
# Upstream commit: 459a86bf5f8929559e57f527471eaddf089bda06
"""奶昔论坛每日签到。登录 https://forum.naixi.net 后，在浏览器开发者工具
网络面板复制本站已登录请求的完整 Cookie 请求头值，写入 NAIXI_COOKIE。
每个非空行一个账号，Cookie 内分号和等号原样保留，不使用 @ 或 & 分账号。
兼容 NAIXI_COOKIE1、NAIXI_COOKIE2 等编号变量（连续编号优先）。
依赖 curl_cffi，可从公共 PyPI 安装。NAIXI_DRY_RUN=1 完全断网预演。
CLOCKIN_RANDOM_DELAY 默认启用，CLOCKIN_RANDOM_DELAY_MAX 默认 3600 秒。
QINGLONG_NOTIFY 支持 auto、1、0，auto 默认选中本任务，可由
QINGLONG_NOTIFY_SCRIPTS 替换选择列表。预演仅记录通知摘要，禁止通知联网。
CLOCKIN_NOTIFY_ONLY_FAILURE 作为旧配置保留说明，通知时机由统一策略接管。
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
        _ql_notify_identities = ('53811af369a269c5', 'scripts/naixi_qinglong.py', 'naixi_qinglong.py', 'naixi_qinglong')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import html
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser

BASE_URL = 'https://forum.naixi.net'
SIGN_PAGE_URL = BASE_URL + '/plugin.php?id=k_misign:sign'
SIGN_API = SIGN_PAGE_URL + '&operation=qiandao&format=empty&inajax=1&ajaxtarget=JD_sign'
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CATALOG_ID = '53811af369a269c5'
TITLE = '奶昔论坛签到'


class TaskError(Exception):
    pass


TRUE_VALUES = {'1', 'true', 'yes', 'y', 'on'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def collect_cookies():
    cookies = []
    index = 1
    while os.getenv(f'NAIXI_COOKIE{index}', '').strip():
        cookies.extend(os.environ[f'NAIXI_COOKIE{index}'].replace('\\n', '\n').splitlines())
        index += 1
    if not cookies:
        cookies = os.getenv('NAIXI_COOKIE', '').replace('\\n', '\n').splitlines()
    return [value.strip() for value in cookies if value.strip()]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}
        self.text = []
        self.identity = ''
        self.in_user = False
        self.in_anchor = False
        self.user_text = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.ignored += 1
        attrs = dict(attrs)
        if tag == 'input':
            key = attrs.get('id') or attrs.get('name')
            self.fields[key] = attrs.get('value', '').strip()
        if tag == 'strong' and 'vwmy' in attrs.get('class', '').split():
            self.in_user = True
        if self.in_user and tag == 'a':
            self.in_anchor = True
            self.user_text = []

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.ignored = max(0, self.ignored - 1)
        if tag == 'a' and self.in_anchor:
            self.identity = ''.join(self.user_text).strip()
            self.in_anchor = False
        if tag == 'strong':
            self.in_user = False

    def handle_data(self, data):
        if self.ignored:
            return
        self.text.append(data)
        if self.in_anchor:
            self.user_text.append(data)


def parse_page(content):
    parser = PageParser()
    parser.feed(content)
    return parser


def safe_identity(value, cookies):
    # 身份保留官方显示值，仅清除日志控制字符及敏感字段。
    value = ''.join(char for char in value if char.isprintable())
    for cookie in cookies:
        value = value.replace(cookie, '[已隐藏]')
        for item in cookie.split(';'):
            if '=' in item:
                secret = item.split('=', 1)[1].strip()
                if secret:
                    value = value.replace(secret, '[已隐藏]')
    value = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', value)
    if re.search(r'(?i)(cookie|token|session|device|authorization)\s*[:=]', value):
        return '[敏感身份字段已隐藏]'
    return value


def stats_from(page):
    parts = []
    for key, label in [('lxdays', '连续签到天数'), ('lxtdays', '累计签到天数'),
                       ('lxreward', '今日奖励')]:
        value = page.fields.get(key, '')
        if re.fullmatch(r'\d+(?:\.\d+)?', value):
            parts.append(f'{label} {value}')
    return '，'.join(parts)


def fetch(session, cookie, url, ajax=False):
    headers = {
        'Accept': '*/*' if ajax else 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': SIGN_PAGE_URL,
        'Cookie': cookie,
    }
    if ajax:
        headers['X-Requested-With'] = 'XMLHttpRequest'
    response = session.get(url, headers=headers, timeout=TIMEOUT_SECONDS,
                           allow_redirects=False)
    if response.status_code != 200:
        raise TaskError(f'HTTP {response.status_code}，请求未通过')
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise TaskError('响应体过大，停止处理')
    return response.text


def confirmed(page):
    text = ''.join(page.text)
    return '今日已签' in text and not re.search(r'今日(?:还|尚)?未签', text)


def stage(index, name, action):
    start = time.monotonic()
    log(f'阶段 {index} · {name} 开始')
    try:
        result = action()
    except Exception:
        log(f'阶段 {index} · {name} ❌ 失败，耗时 {time.monotonic() - start:.2f} 秒')
        raise
    log(f'阶段 {index} · {name} ✅ 完成，耗时 {time.monotonic() - start:.2f} 秒')
    return result


def sign(cookie, cookies, session):
    page_html = stage(1, '获取签到页', lambda: fetch(session, cookie, SIGN_PAGE_URL))
    page = parse_page(page_html)
    if page.identity:
        log('官方账号身份 ' + safe_identity(page.identity, cookies))
    if confirmed(page):
        log('☑️ 今日已签到 ' + stats_from(page))
        return 'already-complete'
    formhash = page.fields.get('formhash', '')
    if not re.fullmatch(r'[a-fA-F0-9]{8,}', formhash):
        match = re.search(r'formhash=([a-fA-F0-9]{8,})', html.unescape(page_html))
        formhash = match.group(1) if match else ''
    if not formhash:
        raise TaskError('未找到有效 formhash，请检查登录 Cookie 或页面结构')
    # 保留上游协议，空 CDATA 也必须复查页面，不输出服务端原始消息。
    stage(2, '提交每日签到', lambda: fetch(session, cookie, SIGN_API + '&formhash=' + formhash, True))
    verification = stage(3, '复查签到状态', lambda: fetch(session, cookie, SIGN_PAGE_URL))
    verified = parse_page(verification)
    if verified.identity and verified.identity != page.identity:
        log('官方账号身份 ' + safe_identity(verified.identity, cookies))
    if not confirmed(verified):
        raise TaskError('签到后页面未确认今日已签到')
    log('✅ 签到成功 ' + stats_from(verified))
    return 'success'


def random_delay():
    if os.getenv('CLOCKIN_RANDOM_DELAY', '1').lower().strip() not in TRUE_VALUES:
        log('随机延迟已关闭')
        return
    raw = os.getenv('CLOCKIN_RANDOM_DELAY_MAX', '3600').strip()
    try:
        maximum = max(0, int(raw))
    except ValueError:
        maximum = 3600
        log('CLOCKIN_RANDOM_DELAY_MAX 格式无效，采用默认 3600 秒')
    delay = random.randint(0, maximum)
    log(f'随机延迟 {delay} 秒')
    while delay:
        step = min(delay, 60)
        time.sleep(step)
        delay -= step
        if delay:
            log(f'随机延迟剩余 {delay} 秒')


def notify(summary, dry_run):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in {'0', 'false', 'no', 'off'}:
        return 'disabled'
    if switch not in TRUE_VALUES | {'auto'}:
        log('⚠️ QINGLONG_NOTIFY 无效，通知跳过')
        return 'invalid-setting'
    if switch == 'auto':
        selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
        names = [CATALOG_ID, Path(__file__).name, str(Path(__file__)), 'naixi_qinglong.py',
                 'clockin/naixi_qinglong.py', 'scripts/naixi_qinglong.py']
        if selection is not None and not any(
            fnmatch.fnmatch(name, pattern) for pattern in re.split(r'[,;\s]+', selection.strip())
            if pattern for name in names
        ):
            return 'not-selected'
    if dry_run:
        log('⏭️ 断网预演通知摘要 ' + summary)
        return 'dry-run-simulated'
    # 在独立进程中调用青龙通知，限制耗时并丢弃通知模块输出。
    code = '''import importlib.util, json, sys
kind, target, title, body = json.loads(sys.stdin.read())
if kind == 'module':
    from notify import send
else:
    spec = importlib.util.spec_from_file_location('qinglong_notification', target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send = module.send
send(title, body)
'''
    locations = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        locations.append(Path(directory))
    locations.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    options = [('module', '')]
    options.extend(('file', str(path / 'notify.py')) for path in locations if (path / 'notify.py').is_file())
    for kind, target in options:
        try:
            result = subprocess.run([sys.executable, '-c', code],
                                    input=json.dumps([kind, target, TITLE, summary]),
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    for directory in locations:
        path = directory / 'sendNotify.js'
        if not path.is_file():
            continue
        javascript = 'let s="";process.stdin.on("data",d=>s+=d);process.stdin.on("end",async()=>{try{const p=JSON.parse(s);await require(p[0]).sendNotify(p[1],p[2]);}catch(e){process.exitCode=1;}});'
        try:
            result = subprocess.run(['node', '-e', javascript],
                                    input=json.dumps([str(path), TITLE, summary]), text=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 青龙通知不可用或发送失败，保留业务退出码')
    return 'unavailable-or-failed'


def main():
    started = time.monotonic()
    dry_run = os.getenv('NAIXI_DRY_RUN', '0').lower().strip() in TRUE_VALUES
    cookies = collect_cookies()
    log('========== 奶昔论坛签到 ==========')
    log(f'开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'运行模式 {"断网预演" if dry_run else "正式执行"}，账号数 {len(cookies)}')
    results = []
    config_start = time.monotonic()
    log('阶段 0 · 配置检查 开始')
    failure_reason = ''
    session_class = None
    if not cookies:
        failure_reason = '未找到 Cookie，请配置 NAIXI_COOKIE，每行一个账号'
    elif not dry_run:
        try:
            from curl_cffi import Session
            session_class = Session
        except ImportError:
            failure_reason = '缺少 curl_cffi，请通过青龙依赖管理从公共 PyPI 安装'
    if failure_reason:
        log('❌ ' + failure_reason)
    config_status = '❌ 失败' if failure_reason else '✅ 完成'
    log(f'阶段 0 · 配置检查 {config_status}，耗时 {time.monotonic() - config_start:.2f} 秒')
    if cookies and not failure_reason and not dry_run:
        stage(0, '随机延迟', random_delay)
    for index, cookie in enumerate(cookies, 1):
        account_start = time.monotonic()
        log(f'---- 账号 {index} ----')
        status = 'failure'
        try:
            if '\r' in cookie or any(ord(char) < 32 for char in cookie) or '=' not in cookie:
                raise TaskError('Cookie 格式无效，应填写完整 Cookie 请求头值')
            if failure_reason:
                raise TaskError(failure_reason)
            if dry_run:
                stage(1, '预演参数检查', lambda: None)
                log('⏭️ DRY_RUN_OK 已验证账号配置，签到、等待和网络请求均跳过')
                status = 'dry-run'
            else:
                with session_class(impersonate='chrome') as session:
                    status = sign(cookie, cookies, session)
        except TaskError as exc:
            # 只输出本脚本构造的固定诊断，第三方异常禁止直接输出。
            log('❌ ' + str(exc))
        except Exception:
            log('❌ 请求或解析异常，未确认签到成功，请检查网络、依赖及服务状态')
        record = {'account': index, 'status': status, 'total': 1,
                  'success': int(status == 'success'),
                  'alreadyComplete': int(status == 'already-complete'),
                  'skipped': int(status == 'dry-run'), 'failed': int(status == 'failure'),
                  'seconds': round(time.monotonic() - account_start, 2)}
        results.append(record)
        log(f'账号 {index} 统计 总任务 1，成功 {record["success"]}，已完成 {record["alreadyComplete"]}，跳过 {record["skipped"]}，失败 {record["failed"]}，耗时 {record["seconds"]} 秒')
        if not dry_run and index < len(cookies) and not failure_reason:
            time.sleep(random.randint(3, 8))
    failed = sum(item['failed'] for item in results)
    successful = sum(item['status'] in {'success', 'already-complete', 'dry-run'} for item in results)
    exit_code = int(bool(failure_reason or failed))
    status = 'configuration-error' if failure_reason else ('partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry_run else 'success')
    body = f'状态 {status}，账号总数 {len(cookies)}，成功数 {successful}，失败数 {failed}，预演数 {sum(item["skipped"] for item in results)}'
    notification = notify(body, dry_run)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(item[key] for item in results) for key in ['total', 'success', 'alreadyComplete', 'skipped', 'failed']}
    log(f'子任务统计 总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    elapsed = round(time.monotonic() - started, 2)
    log(f'完成时间 {datetime.now():%Y-%m-%d %H:%M:%S}，总耗时 {elapsed} 秒，通知状态 {notification}，最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'dryRun': dry_run,
          'accounts': len(cookies), 'successful': successful, 'failed': failed,
          'subtasks': totals, 'results': results, 'notification': notification,
          'seconds': elapsed, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
