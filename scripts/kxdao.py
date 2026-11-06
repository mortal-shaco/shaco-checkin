#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 科学刀论坛打卡签到
# cron: 55 6 * * *
# SPDX-License-Identifier: Apache-2.0
# 来源: HeiDaotu/WFRobertQL, kxdao.py；维护版本保留作者及原始说明。
# Licensed under the Apache License, Version 2.0:
# https://www.apache.org/licenses/LICENSE-2.0
# Distributed on an AS IS BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
"""
File: kxdao.py
Author: WFRobert
Date: 2023/9/1 2:49
cron: 55 6 * * *
new Env('科学刀论坛打卡签到');
Description: 科学刀论坛打卡签到
Update: 2023/9/1 更新cron

维护说明：KXDAO_COOKIE 每个非空行填写一个账号的完整 Cookie，不以 & 分账号。
浏览器登录 https://www.kxdao.net/ 后，在开发者工具网络面板中查看本站请求的
Cookie 请求头；只复制该值。Cookie 过期后重新登录获取，切勿分享。
KXDAO_DRY_RUN=1 完全断网预演，不签到、不调用通知服务。
实跑仅执行论坛签到；动态读取同源页面的 formhash，不执行页面脚本。
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
        _ql_notify_identities = ('0ad17018f1f68b77', 'scripts/kxdao.py', 'kxdao.py', 'kxdao')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
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

TITLE = '科学刀论坛打卡签到'
BASE = 'https://www.kxdao.net'
LANDING = BASE + '/plugin.php?id=dsu_amupper'
CATALOG = '0ad17018f1f68b77'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
MAX_BYTES = 2 * 1024 * 1024


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (parsed.scheme, parsed.netloc) != ('https', 'www.kxdao.net'):
            raise TaskError('拒绝跨站或非 HTTPS 重定向')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formhash = None
        self.username = ''
        self.identity_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('name') == 'formhash':
            self.formhash = a.get('value', '')
        if tag == 'a' and 'vwmy' in a.get('class', '').split():
            self.identity_depth = 1
            self.parts = []

    def handle_data(self, data):
        if self.identity_depth:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.identity_depth:
            self.username = ''.join(self.parts).strip()
            self.identity_depth = 0


def read_page(opener, url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; Qinglong-Kxdao/1.0)',
        'Referer': LANDING, 'Accept': 'text/html,application/xml;q=0.9,*/*;q=0.8',
    })
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200:
                raise TaskError('论坛 HTTP 状态异常')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise TaskError('论坛响应超过安全大小限制')
            charset = response.headers.get_content_charset() or 'utf-8'
            return body.decode(charset, errors='replace')
    except TaskError:
        raise
    except Exception:
        raise TaskError('论坛请求失败或超时，未确认业务成功') from None


def make_opener(cookie):
    jar = http.cookiejar.CookieJar()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cookie):
        raise TaskError('Cookie 格式错误：包含控制字符')
    for field in cookie.split(';'):
        field = field.strip()
        if not field:
            continue
        key, sep, value = field.partition('=')
        if not sep or not re.fullmatch(r'[!#$%&\x27*+.^_`|~0-9A-Za-z-]+', key):
            raise TaskError('Cookie 格式错误：需填写完整 Cookie 请求头值')
        jar.set_cookie(http.cookiejar.Cookie(
            0, key, value, None, False, 'www.kxdao.net', False, False,
            '/', True, True, None, True, None, None, {}, False))
    if not list(jar):
        raise TaskError('Cookie 不能为空')
    return urllib.request.build_opener(SameOriginRedirect(), urllib.request.HTTPCookieProcessor(jar))


def business_result(text):
    # 只识别明确的本次签到结果；不把 HTTP 200、回调名称或普通“成功”当作成功。
    text = html.unescape(text)
    messages = re.findall(r"(?:errorhandle|succeedhandle)_dsu_amupper\s*\(\s*'((?:\\.|[^'\\])*)'", text)
    if not messages:
        messages = re.findall(r'(?:errorhandle|succeedhandle)_dsu_amupper\s*\(\s*"((?:\\.|[^"\\])*)"', text)
    if not messages:
        raise TaskError('未识别到签到业务回调，未确认成功')
    text = ' '.join(messages)
    if re.search(r'(?:今天|今日|本日)(?:您)?(?:已经|已)(?:签到|打过卡|打卡)|您今天已经打过卡', text):
        return 'already'
    if re.search(r'(?:签到|打卡)成功', text):
        # 否定、错误文本不能形成成功结果。
        if not re.search(r'(?:未|不|没有|无法)(?:能)?(?:签到|打卡)成功', text):
            return 'success'
    raise TaskError('未识别到明确签到成功或今日已签到结果；请检查登录状态与论坛接口')


def show_identity(page, cookie):
    name = page.username
    # 官方非敏感用户名原样展示；防止控制字符及意外回显凭据/手机号。
    if name and not re.search(r'[\x00-\x1f\x7f]|1[3-9]\d{9}', name):
        values = [part.partition('=')[2].strip() for part in cookie.split(';') if '=' in part]
        if not any(value and value in name for value in values):
            log('官方用户名：' + name)


def account_task(cookie, dry):
    stage = time.monotonic()
    log('阶段 1/2：检查配置' if dry else '阶段 1/2：读取签到页面和动态 formhash')
    opener = make_opener(cookie)
    if dry:
        log(f'✅ 配置解析通过（{time.monotonic() - stage:.2f} 秒），未发送网络请求')
        log('阶段 2/2：⏭️ 跳过实际签到（0.00 秒）')
        return 'skipped'
    source = read_page(opener, LANDING)
    page = Page()
    page.feed(source)
    show_identity(page, cookie)
    token = page.formhash
    if not token:
        match = re.search(r'\bformhash\s*[:=]\s*[\x27\"]([a-fA-F0-9]{8})[\x27\"]', source)
        token = match.group(1) if match else None
    if not token or not re.fullmatch('[a-fA-F0-9]{8}', token):
        raise TaskError('无法获取动态 formhash，未提交签到；请重新登录检查 Cookie')
    log(f'✅ 已获取动态 formhash（{time.monotonic() - stage:.2f} 秒）')
    stage = time.monotonic()
    log('阶段 2/2：提交签到并核验业务结果')
    params = {'id': 'dsu_amupper', 'ppersubmit': 'true', 'formhash': token,
              'infloat': 'yes', 'handlekey': 'dsu_amupper', 'inajax': '1',
              'ajaxtarget': 'fwin_content_dsu_amupper'}
    result = business_result(read_page(opener, BASE + '/plugin.php?' + urllib.parse.urlencode(params)))
    log(f'{"☑️ 今日已签到" if result == "already" else "✅ 签到成功"}（{time.monotonic() - stage:.2f} 秒）')
    return result


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    path = Path(__file__)
    identifiers = {CATALOG, path.name, 'kxdao.py', 'candidate.py', 'scripts/kxdao.py', 'scripts/' + path.name}
    identifiers.update('/'.join(path.parts[i:]) for i in range(len(path.parts)))
    selected = any(fnmatch.fnmatchcase(item, selector) for selector in selectors if selector for item in identifiers)
    # listed-only 默认无预置启用项；显式全局开关优先。
    enabled = switch in TRUE or (switch not in FALSE and selected)
    if not enabled:
        return '已禁用或未选中'
    if dry:
        return '断网预演，已生成脱敏通知摘要，未发送'
    body = (f'账号总数 {summary["accounts"]}，成功 {summary["succeeded"]}，'
            f'失败 {summary["failed"]}，状态 {summary["status"]}')
    # 隔离通知模块的输出与异常，防止第三方模块影响业务退出码或泄露配置。
    runner = '''import importlib.util,sys
kind,path,title,body=sys.argv[1:]
if kind=="module":
 import notify
else:
 spec=importlib.util.spec_from_file_location("notify",path)
 notify=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(notify)
notify.send(title,body)
'''
    candidates = [('module', '')]
    roots = ([os.getenv('QINGLONG_NOTIFY_DIR')] if os.getenv('QINGLONG_NOTIFY_DIR') else []) + ['/ql/data/scripts', '/ql/scripts']
    candidates.extend(('file', str(Path(root) / 'notify.py')) for root in roots if (Path(root) / 'notify.py').is_file())
    for kind, location in candidates:
        try:
            done = subprocess.run([sys.executable, '-c', runner, kind, location, TITLE, body],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if done.returncode == 0:
                return '已发送'
        except Exception:
            pass
    for root in roots:
        js = Path(root) / 'sendNotify.js'
        if not js.is_file():
            continue
        try:
            done = subprocess.run(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',
                                   str(js), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if done.returncode == 0:
                return '已发送'
        except Exception:
            pass
    return '通知不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    dry = os.getenv('KXDAO_DRY_RUN', '').strip().lower() in TRUE
    cookies = [line.strip() for line in os.getenv('KXDAO_COOKIE', '').splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "实际签到"}；账号数：{len(cookies)}')
    totals = dict(success=0, already=0, skipped=0, failed=0)
    passed = 0
    if not cookies:
        log('❌ 配置错误：请填写 KXDAO_COOKIE，每个非空行一个账号')
    for index, cookie in enumerate(cookies, 1):
        tick = time.monotonic()
        log(f'账号 {index}/{len(cookies)} 开始')
        try:
            result = account_task(cookie, dry)
            passed += 1
        except TaskError as exc:
            result = 'failed'
            log('❌ ' + str(exc))
        except Exception:
            result = 'failed'
            log('❌ 处理异常，未确认成功（已隐藏异常详情）')
        totals[result] += 1
        log(f'账号 {index} 统计：总任务 1，成功 {int(result == "success")}，已完成 {int(result == "already")}，跳过 {int(result == "skipped")}，失败 {int(result == "failed")}，耗时 {time.monotonic() - tick:.2f} 秒')
    code = 0 if cookies and passed == len(cookies) else 1
    status = ('dry-run' if dry else 'success') if code == 0 else ('configuration-error' if not cookies else 'partial-failure' if passed else 'failure')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(cookies),
               'succeeded': passed, 'failed': len(cookies) - passed, 'tasks': totals,
               'status': status, 'exitCode': code}
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        summary['notification'] = '通知不可用（保留业务退出码）'
    log('----------------------------------------')
    log(f'账号统计：总计 {len(cookies)}，通过 {passed}，失败 {len(cookies) - passed}')
    log(f'子任务统计：成功 {totals["success"]}，已完成 {totals["already"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'通知状态：{summary["notification"]}')
    log(f'总耗时：{time.monotonic() - started:.2f} 秒；完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
