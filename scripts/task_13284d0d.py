#!/usr/bin/env python3
# name: NSSCTF 自动登录签到
# cron: 39 10 * * *
# SPDX-License-Identifier: MIT
# Upstream: Marven11/NSSCTFAutoLogin, main.py
# Source commit: 80809b70095b2d4ada61a74d2919ad81bf372dd0
"""NSSCTF 登录、签到、查询硬币；仅依赖 Python 3 标准库。

NSSCTF_ACCOUNTS：每行 用户名|密码，只在第一个 | 分割，密码可含 |。
用户名、密码使用自己在 https://www.nssctf.cn/ 注册的账号资料。
未配置新变量时兼容 NSSCTF_USERNAME 与 NSSCTF_PASSWORD（单账号）。
NSSCTF_DRY_RUN=1 完全断网预演，不验证凭据、不签到、不实际发送通知。
默认每天 08:10 运行（上游未提供 cron，此处补充建议周期）。
QINGLONG_NOTIFY=1 强制尝试通知，0 禁用，auto 仅匹配名单时通知；
QINGLONG_NOTIFY_SCRIPTS 支持目录相对路径、文件名、通配符、catalogId，
以逗号、分号或空白分隔；空名单禁用。QINGLONG_NOTIFY_DIR 可指定通知目录。

原始输入未包含单独的版权声明；保留上游归属，按任务声明的 MIT 许可维护。
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
        _ql_notify_identities = ('13284d0dbe0aac03', 'scripts/task_13284d0d.py', 'task_13284d0d.py', 'task_13284d0d')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import http.cookiejar
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
from datetime import datetime

TITLE = 'NSSCTF 自动登录签到'
CATALOG_ID = '13284d0dbe0aac03'
BASE = 'https://www.nssctf.cn'
USER_AGENT = ('Mozilla/5.0 (Linux; Android 10; Pixel 3) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
MAX_RESPONSE = 1024 * 1024


def log(message):
    print('[{}] {}'.format(datetime.now().strftime('%H:%M:%S'), message), flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，未向其他地址转发凭据')


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
        self.token = None

    def request(self, method, path, fields=None):
        data = None if fields is None else urllib.parse.urlencode(fields).encode('utf-8')
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
        if self.token:
            headers['Cookie'] = 'token=' + self.token
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise TaskError('响应超过大小限制')
            payload = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise TaskError('HTTP 请求失败（状态 {}）'.format(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络连接失败或超时') from None
        except (ValueError, UnicodeError):
            raise TaskError('响应不是有效 JSON') from None
        if not isinstance(payload, dict):
            raise TaskError('响应结构异常')
        if type(payload.get('code')) is not int or payload['code'] != 200:
            raise TaskError('业务未确认成功（要求 code=200）')
        return payload.get('data')

    def login(self, username, password):
        data = self.request('POST', '/api/user/login/',
                            {'username': username, 'password': password})
        token = data.get('token') if isinstance(data, dict) else None
        if not isinstance(token, str) or not token or not re.fullmatch(r'[\x21-\x7e]+', token) or ';' in token:
            raise TaskError('登录未返回有效 token')
        self.token = token
        return data

    def signin(self):
        self.request('POST', '/api/user/clockin/')

    def balance(self):
        data = self.request('GET', '/api/user/info/opt/setting/')
        coin = data.get('coin') if isinstance(data, dict) else None
        if isinstance(coin, bool) or not (isinstance(coin, int) or
                isinstance(coin, str) and re.fullmatch(r'\d+', coin)):
            raise TaskError('硬币查询未返回有效 coin')
        return coin, data


def accounts_from_env():
    if 'NSSCTF_ACCOUNTS' in os.environ:
        rows = [row for row in os.environ['NSSCTF_ACCOUNTS'].splitlines() if row.strip()]
        accounts = []
        for row in rows:
            username, sep, password = row.partition('|')
            accounts.append((username.strip(), password) if sep and username.strip() and password
                            else None)
        return accounts
    username = os.getenv('NSSCTF_USERNAME', '')
    password = os.getenv('NSSCTF_PASSWORD', '')
    if username or password:
        return [(username, password) if username and password else None]
    return []


def print_identity(data, credentials, token):
    if not isinstance(data, dict):
        return
    # 只读取官方身份白名单；不输出任意服务端错误消息或原始响应。
    for key in ('nickname', 'username', 'display_name', 'displayName', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 手机号或本身就是登录凭据的字段不作为公开身份输出。
            if not value or value in (credentials[1], token) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                continue
            log('官方身份 {}：{}'.format(key, json.dumps(value, ensure_ascii=False)))


def notification_selected():
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').lower().strip()
    if mode in FALSE:
        return False
    if mode not in TRUE | {'auto'}:
        raise TaskError('QINGLONG_NOTIFY 应为 auto、1 或 0')
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selection is None:
        return mode in TRUE
    patterns = [s for s in re.split(r'[,;\s]+', selection) if s]
    path = Path(__file__)
    names = {CATALOG_ID, path.name, path.as_posix()}
    for root in (Path('/ql/data/scripts'), Path('/ql/scripts')):
        try:
            names.add(path.resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    return any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in patterns)


def deliver_notification(body, dry_run, selected):
    if dry_run:
        log('通知预演（不发送）：' + body)
        return 'dry-run'
    if not selected:
        log('⏭️ 通知关闭或未列入通知名单')
        return 'disabled'
    # 通知异常输出也可能泄露本地配置：子进程静默执行，仅返回通知状态。
    worker = r'''
import importlib, importlib.util, pathlib, sys
try:
    if sys.argv[1] == 'import':
        module = importlib.import_module('notify')
    else:
        spec = importlib.util.spec_from_file_location('ql_notify', sys.argv[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.send(sys.argv[2], sys.argv[3])
except BaseException:
    sys.exit(1)
'''
    dirs = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        dirs.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    dirs.extend((Path('/ql/data/scripts'), Path('/ql/scripts')))
    commands = [[sys.executable, '-c', worker, 'import', TITLE, body]]
    for directory in dirs:
        py = directory / 'notify.py'
        js = directory / 'sendNotify.js'
        if py.is_file():
            commands.append([sys.executable, '-c', worker, str(py), TITLE, body])
        if js.is_file():
            commands.append(['node', '-e',
                             'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3]))'
                             '.catch(()=>process.exit(1))', str(js), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                log('✅ 脱敏通知已提交')
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            continue
    log('⚠️ 通知不可用或发送失败，保留业务退出码')
    return 'unavailable'


def run_account(index, credentials, dry_run):
    started = time.monotonic()
    stats = {'account': index, 'total': 3, 'success': 0, 'alreadyComplete': 0,
             'skipped': 0, 'failed': 0}
    logged_in = False
    client = None if dry_run else Client()
    for number, name in enumerate(('登录', '签到', '查询硬币'), 1):
        step = time.monotonic()
        log('账号 {} 阶段 {}/3：{}'.format(index, number, name))
        if credentials is None:
            if number == 1:
                stats['failed'] += 1
                log('❌ 账号格式错误，需 用户名|密码（不回显输入）')
            else:
                stats['skipped'] += 1
                log('⏭️ 凭据格式错误，跳过')
        elif dry_run:
            stats['skipped'] += 1
            log('⏭️ DRY_RUN：参数格式通过，预演{}，未请求接口'.format(name))
        elif number > 1 and not logged_in:
            stats['skipped'] += 1
            log('⏭️ 登录失败，跳过依赖步骤')
        else:
            try:
                if number == 1:
                    data = client.login(*credentials)
                    logged_in = True
                    print_identity(data, credentials, client.token)
                elif number == 2:
                    client.signin()
                else:
                    coin, data = client.balance()
                    print_identity(data, credentials, client.token)
                    log('硬币余额：{}'.format(coin))
                    print(coin, flush=True)  # 保留上游独立数字输出。
                stats['success'] += 1
                log('✅ {}成功，业务 code=200'.format(name))
            except TaskError as exc:
                stats['failed'] += 1
                log('❌ {}失败：{}'.format(name, exc))
            except Exception:
                stats['failed'] += 1
                log('❌ {}失败：处理异常（已隐藏异常内容）'.format(name))
        log('账号 {} 阶段 {} 耗时 {:.2f} 秒'.format(index, number, time.monotonic() - step))
    stats['elapsedSeconds'] = round(time.monotonic() - started, 3)
    stats['status'] = 'failure' if stats['failed'] else ('dry-run' if dry_run else 'success')
    log('账号 {account} 统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，'
        '跳过 {skipped}，失败 {failed}，耗时 {elapsedSeconds} 秒'.format(**stats))
    return stats


def main():
    started = time.monotonic()
    start_time = datetime.now().astimezone().isoformat(timespec='seconds')
    value = os.getenv('NSSCTF_DRY_RUN', '0').strip().lower()
    dry_run = value in TRUE
    accounts = accounts_from_env()
    log('========== {} =========='.format(TITLE))
    log('开始时间：{}；模式：{}；账号数：{}'.format(start_time, '断网预演' if dry_run else '正式', len(accounts)))
    config_error = None
    selected = False
    try:
        if value not in TRUE | FALSE:
            raise TaskError('NSSCTF_DRY_RUN 必须为 1 或 0 等布尔值')
        selected = notification_selected()
        if not accounts:
            raise TaskError('未配置 NSSCTF_ACCOUNTS；也可使用旧版用户名和密码变量')
    except TaskError as exc:
        config_error = str(exc)
        log('❌ 配置错误：' + config_error)
    results = [] if config_error else [run_account(i, credentials, dry_run)
                                      for i, credentials in enumerate(accounts, 1)]
    failed = sum(r['status'] == 'failure' for r in results)
    passed = sum(r['status'] in ('success', 'dry-run') for r in results)
    code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and passed else 'failure' if failed else
              'dry-run' if dry_run else 'success')
    body = '状态：{}；账号总数：{}；成功数：{}；失败数：{}；预演数：{}'.format(
        status, len(accounts), 0 if dry_run else passed, failed, passed if dry_run else 0)
    notification = deliver_notification(body, dry_run, selected)
    finish = datetime.now().astimezone().isoformat(timespec='seconds')
    totals = {key: sum(r[key] for r in results)
              for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('----------------------------------------')
    log(body)
    log('子任务统计：总任务 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failed}'.format(**totals))
    elapsed = round(time.monotonic() - started, 3)
    log('总耗时：{} 秒；完成时间：{}；最终状态：{}；通知：{}'.format(elapsed, finish, status, notification))
    print('TASK_SUMMARY=' + json.dumps({
        'applicationKey': 'marven11/nssctfautologin::main', 'status': status,
        'mode': 'dry-run' if dry_run else 'live', 'accountCount': len(accounts),
        'successCount': 0 if dry_run else passed, 'failedCount': failed,
        'dryRunCount': passed if dry_run else 0, 'configurationError': config_error,
        'tasks': totals, 'accounts': results, 'notification': notification,
        'startTime': start_time, 'finishTime': finish, 'elapsedSeconds': elapsed,
        'exitCode': code}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
