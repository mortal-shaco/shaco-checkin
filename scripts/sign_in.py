#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 看雪论坛签到
# cron: 1 1 1 1 1
"""看雪论坛签到，Author: ZaiZaiCat，原始日期: 2025-01-20。
来源: Cat-zaizai/ZaiZaiCat-Checkin，script/kanxue/sign_in.py、api.py。

KANXUE_ACCOUNTS 每个非空行为一个 JSON 对象，包含 cookie、csrf_token，
可选 user_agent、account_name。登录 https://bbs.kanxue.com 后，在浏览器
开发者工具网络面板查看签到请求：复制 Cookie 请求头、csrf_token 表单值，
必要时复制 User-Agent。请勿公开这些值；手动签到抓取当天可能已完成。
兼容 KANXUE_CONFIG 指定的旧 token.json 中 kanxue.accounts 或
kanxue.kanxue.accounts；仅在未设置 KANXUE_ACCOUNTS 时读取。
KANXUE_DRY_RUN=1 完全离线预演，通知仅模拟；QINGLONG_NOTIFY=0 关闭通知。

MIT License
Copyright (c) ZaiZaiCat
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

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib import request, parse, error

TITLE = '看雪论坛签到'
URL = 'https://bbs.kanxue.com/user-signin.htm'
DEFAULT_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36')
FALSE = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in FALSE | {''}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def load_accounts():
    value = os.getenv('KANXUE_ACCOUNTS', '')
    if value.strip():
        # Parse each line later so one malformed account cannot block others.
        return [line.strip() for line in value.splitlines() if line.strip()]
    path = os.getenv('KANXUE_CONFIG', '').strip()
    if not path:
        raise ValueError('请设置 KANXUE_ACCOUNTS，或显式指定 KANXUE_CONFIG')
    with open(path, encoding='utf-8') as source:
        config = json.load(source)
    group = config['kanxue']
    if 'kanxue' in group:
        group = group['kanxue']
    accounts = group['accounts']
    if not isinstance(accounts, list) or not accounts:
        raise ValueError('配置文件必须包含非空账号列表')
    return accounts


def validate_account(value):
    account = json.loads(value) if isinstance(value, str) else value
    if not isinstance(account, dict):
        raise ValueError('账号必须是 JSON 对象')
    for key in ('cookie', 'csrf_token'):
        if not isinstance(account.get(key), str) or not account[key].strip():
            raise ValueError('账号缺少 Cookie 或 CSRF token')
        if '\r' in account[key] or '\n' in account[key]:
            raise ValueError('凭据不能包含换行')
    ua = account.get('user_agent') or DEFAULT_UA
    if not isinstance(ua, str) or '\r' in ua or '\n' in ua:
        raise ValueError('User-Agent 格式错误')
    return dict(account, user_agent=ua)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a credential-bearing request to login or another host.
        return None


def sign_in(account):
    headers = {
        'User-Agent': account['user_agent'],
        'Accept': 'text/plain, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Language': 'zh-CN,zh;q=0.6',
        'Origin': 'https://bbs.kanxue.com',
        'Referer': 'https://bbs.kanxue.com/',
        'Cookie': account['cookie'],
    }
    body = parse.urlencode({'csrf_token': account['csrf_token']}).encode('utf-8')
    req = request.Request(URL, data=body, headers=headers, method='POST')
    opener = request.build_opener(NoRedirect())
    with opener.open(req, timeout=30) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常')
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('响应超出大小限制')
    result = json.loads(raw.decode('utf-8'))
    if not isinstance(result, dict):
        raise ValueError('业务响应格式错误')
    code = result.get('code')
    # The supplied sign_in.py explicitly identifies code "0" as success.
    if isinstance(code, bool) or code not in (0, '0'):
        raise ValueError('业务未确认签到成功，请检查登录凭据或接口契约')
    return result


def show_identity(result, account):
    containers = [result]
    if isinstance(result.get('data'), dict):
        containers.append(result['data'])
    for data in containers:
        for key in ('nickname', 'username', 'display_name', 'uid'):
            value = data.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                # Suppress credentials and phone numbers even in identity fields.
                if any(ord(character) < 32 or ord(character) == 127 for character in text):
                    continue
                if any(account[k] in text for k in ('cookie', 'csrf_token')):
                    continue
                if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                    continue
                print(f'官方账号身份（{key}）: {text}', flush=True)
                return


def notify(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    if dry:
        log('⏭️ 离线通知模拟：' + body)
        return '离线模拟'
    # Isolate notification errors/output from business status and credentials.
    code = '''import importlib.util, os, sys
try:
    import notify
except ImportError:
    notify = None
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(os.path.join(os.environ['QINGLONG_NOTIFY_DIR'], 'notify.py'))
    paths += ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
    for path in paths:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            notify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify)
            break
if notify is None or not callable(getattr(notify, 'send', None)):
    sys.exit(3)
notify.send(sys.argv[1], sys.stdin.read())
'''
    env = os.environ.copy()
    for key in ('KANXUE_ACCOUNTS', 'KANXUE_CONFIG'):
        env.pop(key, None)
    try:
        run = subprocess.run([sys.executable, '-c', code, TITLE], input=body,
                             text=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=30, env=env)
        return '已发送' if run.returncode == 0 else '不可用或发送失败'
    except Exception:
        return '发送失败'


def main():
    start = time.monotonic()
    dry = enabled('KANXUE_DRY_RUN')
    log('=' * 56)
    log(TITLE + f' | 开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}')
    log('模式：' + ('离线预演' if dry else '正式签到'))
    results = []
    config_error = False
    try:
        accounts = load_accounts()
    except Exception:
        accounts = []
        config_error = True
        log('❌ 阶段 1 参数加载失败：请检查账号变量或旧配置结构；耗时 %.2f 秒' % (time.monotonic() - start))
    log(f'账号总数：{len(accounts)}')
    for index, value in enumerate(accounts, 1):
        began = time.monotonic()
        stats = {'account': index, 'total': 1, 'success': 0,
                 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
        log(f'--- 账号 {index}/{len(accounts)} ---')
        try:
            stage = time.monotonic()
            account = validate_account(value)
            log(f'阶段 1 参数检查 ✅ Cookie、CSRF token、User-Agent 格式有效；耗时 {time.monotonic()-stage:.2f} 秒')
            stage = time.monotonic()
            if dry:
                log('阶段 2 签到 ⏭️ DRY_RUN_OK：参数检查通过，未请求接口；耗时 0.00 秒')
                stats['skipped'] = 1
            else:
                result = sign_in(account)
                show_identity(result, account)
                log(f'阶段 2 签到 ✅ 业务码 0，签到成功；耗时 {time.monotonic()-stage:.2f} 秒')
                # Only numeric rewards are safe to render from upstream message.
                reward = result.get('message')
                if isinstance(reward, (str, int)) and re.fullmatch(r'\d{1,8}', str(reward)):
                    log(f'获得积分：{reward}')
                stats['success'] = 1
        except (ValueError, TypeError, KeyError):
            stats['failed'] = 1
            log(f'❌ 参数或业务响应未通过核验；阶段耗时 {time.monotonic()-stage:.2f} 秒')
        except error.HTTPError as exc:
            stats['failed'] = 1
            log(f'❌ 签到 HTTP 状态 {exc.code}；阶段耗时 {time.monotonic()-stage:.2f} 秒')
        except Exception:
            stats['failed'] = 1
            log(f'❌ 网络、超时或响应解析失败；阶段耗时 {time.monotonic()-stage:.2f} 秒')
        stats['durationSeconds'] = round(time.monotonic() - began, 3)
        results.append(stats)
        log(f"账号 {index} 统计：任务 1，成功 {stats['success']}，已完成 0，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {stats['durationSeconds']:.2f} 秒")
    failed = sum(r['failed'] for r in results)
    passed = len(results) - failed
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and passed else
              'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if config_error or (failed and not passed) else 2 if failed else 0
    body = f'状态：{status}；账号总数：{len(results)}；成功数：{0 if dry else passed}；失败数：{failed}；预演通过：{passed if dry else 0}'
    notification = notify(body, dry)
    log('-' * 56)
    log(body)
    log(f"子任务统计：成功 {sum(r['success'] for r in results)}，已完成 0，跳过 {sum(r['skipped'] for r in results)}，失败 {failed}")
    log(f'通知状态：{notification}；总耗时：{time.monotonic()-start:.2f} 秒')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({
        'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
        'accounts': len(results), 'success': sum(r['success'] for r in results),
        'failed': failed, 'skipped': sum(r['skipped'] for r in results),
        'configurationError': config_error, 'results': results,
        'notification': notification, 'exitCode': exit_code,
    }, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
