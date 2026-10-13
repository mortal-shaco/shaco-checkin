# -*- coding: utf-8 -*-
# name: 机场签到
# cron: 20 10 * * *
# SPDX-License-Identifier: MIT
# Original author: @Icrons; upstream: OreosLab/checkinpanel, ck_airport.py
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
"""每天登录 SSPanel 机场并签到，读取 editXY 用户信息。
AIRPORT_ACCOUNTS：每个非空行一个 JSON 对象，字段 url、email、password。
url 从机场官网地址栏获取（HTTPS），email/password 为该站注册账号凭据。
JSON 字符串中的特殊字符须按 JSON 规则转义；账号以换行分隔。
兼容 AIRPORT：同字段的 JSON 对象数组或逐行对象，不依赖私有配置文件。
AIRPORT_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
预演只检查配置与流程，不代表真实登录或签到成功，不发送网络通知。
"""
import datetime
import html
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import subprocess
import sys
import urllib.parse
import urllib.request

TITLE = '机场签到'
DISABLED = {'0', 'false', 'no', 'off'}
MAX_BYTES = 1024 * 1024


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in DISABLED | {''}


def safe_text(value, secrets):
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'\b1\d{10}\b', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())[:300]


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if origin(req.full_url) != origin(newurl):
            raise ValueError('拒绝跨站重定向')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def origin(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme, p.hostname, p.port or 443


class Client:
    def __init__(self, url):
        self.url = url.rstrip('/')
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            SameOriginRedirect())

    def request(self, path='', data=None, as_json=False):
        headers = {'User-Agent': 'Mozilla/5.0 QinglongAirport/1.0',
                   'Referer': self.url + '/user'}
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        request = urllib.request.Request(self.url + path, data=data, headers=headers)
        with self.opener.open(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError('HTTP 状态异常')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('响应过大')
            text = raw.decode('utf-8')
        if as_json:
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError('业务响应格式异常')
            return obj
        return text


def accounts_from_env():
    raw = os.getenv('AIRPORT_ACCOUNTS') or os.getenv('AIRPORT', '')
    if not raw.strip():
        raise ValueError('缺少 AIRPORT_ACCOUNTS')
    if raw.lstrip().startswith('['):
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError('账号配置须为数组')
        return items
    # 独立解析各行，让一个错误账号不阻止其他账号。
    items = []
    for line in raw.splitlines():
        if line.strip():
            try:
                items.append(json.loads(line))
            except (ValueError, TypeError):
                items.append(None)
    return items


def validate(item):
    if not isinstance(item, dict):
        raise ValueError('账号行须为 JSON 对象')
    for key in ('url', 'email', 'password'):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError('账号缺少 url、email 或 password')
    p = urllib.parse.urlsplit(item['url'])
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('官网地址须为不含凭据、查询参数或片段的 HTTPS 地址')
    _ = p.port
    return item


def identity(obj, secrets):
    # 只显示明确的公开身份字段；不输出原始响应或任意业务消息。
    for container in (obj, obj.get('data'), obj.get('user')):
        if isinstance(container, dict):
            for key in ('nickname', 'username', 'display_name', 'public_uid'):
                value = container.get(key)
                if isinstance(value, (str, int)) and value != '':
                    log('官方账号身份：' + safe_text(value, secrets))


def business_success(obj):
    # SSPanel 原接口 ret=1 为成功；缺失或未知代码不得视为成功。
    return type(obj.get('ret')) in (int, str) and obj['ret'] in (1, '1')


def already_done(obj):
    # 仅识别明确的已签到业务结果，普通失败消息不算成功。
    return obj.get('ret') in (0, '0') and str(obj.get('msg', '')).strip() in {
        '您今天已经签到过了', '您今天已经签到过了。', '您今天已经签到过了...',
        '今天已经签到过了', '今天已经签到过了。', '今日已签到', '今日已签到。'}


def run_account(item, number, dry):
    start = time.monotonic()
    stats = {'total': 4, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    secrets = []
    def stage(n, label, action):
        t = time.monotonic()
        log(f'账号 {number} 阶段 {n}/4：{label}')
        try:
            result = action()
        except Exception:
            log(f'❌ {label}失败（配置、网络或响应异常；详细数据已隐藏），耗时 {time.monotonic()-t:.2f} 秒')
            raise
        log(f'{label}结束，耗时 {time.monotonic()-t:.2f} 秒')
        return result
    try:
        item = stage(1, '配置检查', lambda: validate(item))
        secrets = [item['email'], item['password']]
        stats['success'] += 1
        if dry:
            for n, label in ((2, '登录'), (3, '签到'), (4, '用户信息查询')):
                stage(n, label, lambda: log('⏭️ 预演：未发起网络请求'))
                stats['skipped'] += 1
            status = 'dry-run'
        else:
            client = Client(item['url'])
            def login():
                client.request()
                obj = client.request('/auth/login', urllib.parse.urlencode({
                    'email': item['email'], 'passwd': item['password'], 'code': ''}).encode(), True)
                if not business_success(obj):
                    raise ValueError('登录业务未成功')
                identity(obj, secrets)
                log('✅ 登录已验证成功')
            stage(2, '登录', login)
            stats['success'] += 1
            def checkin():
                obj = client.request('/user/checkin', b'', True)
                identity(obj, secrets)
                if business_success(obj):
                    stats['success'] += 1
                    log('✅ 签到已验证成功')
                elif already_done(obj):
                    stats['alreadyComplete'] += 1
                    log('☑️ 今日签到已完成')
                else:
                    raise ValueError('签到业务未成功')
            stage(3, '签到', checkin)
            def info():
                text = client.request('/user')
                found = 0
                for key, label in (('Class', '用户等级'), ('Class_Expire', '到期时间'), ('Unused_Traffic', '剩余流量')):
                    match = re.search(r'\[\s*"' + key + r'"\s*,\s*"([^"\r\n]*)"\s*\]', text)
                    if match:
                        found += 1
                        log(label + '：' + safe_text(html.unescape(match.group(1)), secrets))
                if found == 3:
                    stats['success'] += 1
                else:
                    stats['skipped'] += 1
                    log('⏭️ 该主题未提供全部 editXY 字段；已展示可用信息')
            stage(4, '用户信息查询', info)
            status = 'success'
    except Exception:
        stats['failed'] += 1
        stats['skipped'] = stats['total'] - stats['success'] - stats['alreadyComplete'] - stats['failed']
        status = 'failure'
    stats['seconds'] = round(time.monotonic() - start, 2)
    log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒；状态 {status}')
    return {'account': number, 'status': status, **stats}


def notify_summary(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        log('通知预演：' + body)
        return '断网预演（未发送）'
    # 青龙通知是可选输出适配器，业务 HTTP 不依赖任何外部应用。
    candidates = [Path(__file__).parent / 'notify.py']
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        candidates.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    candidates += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            candidates.insert(0, Path(spec.origin))
    except (ImportError, ValueError):
        pass
    for path in candidates:
        if path.is_file():
            try:
                # 子进程隔离通知模块，超时和输出均受控，避免泄漏通知配置。
                adapter = ("import importlib.util,json,sys; "
                           "s=importlib.util.spec_from_file_location('notify',sys.argv[1]); "
                           "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                           "v=json.load(sys.stdin); m.send(v['title'],v['body'])")
                subprocess.run([sys.executable, '-c', adapter, str(path)],
                               input=json.dumps({'title': TITLE, 'body': body}), text=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=25, check=True)
                return '已调用青龙通知'
            except (OSError, subprocess.SubprocessError):
                return '通知失败（不改变业务退出码）'
    return '未找到青龙 notify.py（不改变业务退出码）'


def main():
    start = time.monotonic()
    dry = enabled('AIRPORT_DRY_RUN')
    log('========== 机场签到 ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式运行"}')
    results = []
    config_error = False
    try:
        items = accounts_from_env()
        if not items:
            raise ValueError('账号配置为空')
    except Exception:
        items = []
        config_error = True
        log('❌ 配置错误：请设置 AIRPORT_ACCOUNTS，每行一个含 url、email、password 的 JSON 对象')
    log(f'账号总数：{len(items)}')
    for n, item in enumerate(items, 1):
        results.append(run_account(item, n, dry))
    failed = sum(r['status'] == 'failure' for r in results)
    passed = len(results) - failed
    status = ('configuration-error' if config_error else 'partial-failure' if failed and passed
              else 'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if failed or config_error else 0
    body = f'状态：{status}；账号总数：{len(items)}；成功数：{0 if dry else passed}；预演通过数：{passed if dry else 0}；失败数：{failed}；配置错误：{int(config_error)}'
    notification = notify_summary(body, dry)
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(items), 'success': 0 if dry else passed, 'dryRunPassed': passed if dry else 0,
               'failed': failed, 'configurationErrors': int(config_error), 'results': results,
               'notification': notification, 'exitCode': code, 'seconds': round(time.monotonic()-start, 2)}
    log('----------------------------------------')
    log(body)
    for key, label in (('total', '总子任务'), ('success', '成功'), ('alreadyComplete', '已完成'), ('skipped', '跳过'), ('failed', '失败')):
        log(f'{label}：{sum(r[key] for r in results)}')
    log(f'通知状态：{notification}；总耗时：{summary["seconds"]} 秒')
    log(f'完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
