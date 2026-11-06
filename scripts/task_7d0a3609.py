#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AnyRouter 自动签到
# cron: 42 9 * * *
# 来源: 0006s/anyrouter_auto_qiandao, checkin.py
# 上游提交: 6ef57a022d22cfbd869a9cb3220739f25aefe7e9
# License: MIT (effectiveLicense)
"""
AnyRouter 独立签到维护版。每日 08:00 为新增建议时间，上游未指定 cron。
ANYROUTER_COOKIES: 每个非空行一个完整 Cookie，不以 & 或 @ 拆分账号。
ANYROUTER_BASE_URL: 从本人登录站点地址栏获取可信 HTTPS 根地址；不默认使用代理。
Cookie 获取: 登录该站点，开发者工具 Network 中找到本人 /api/user/sign_in
请求，复制 Request Headers 的 Cookie 值；不包含 Cookie: 前缀。过期后重新获取。
支持原 config.json 的 accounts[{name,cookie}]、base_url 和 email 配置，
或用 ANYROUTER_CONFIG 指定 JSON 路径；环境变量优先。邮箱仍需显式 enabled。
ANYROUTER_DRY_RUN=1 完全断网，只检查配置并模拟签到；不发送邮件。
QINGLONG_NOTIFY 支持 auto/1/0 和常见布尔值；auto 仅通知选中脚本。
QINGLONG_NOTIFY_SCRIPTS 支持目录路径、文件名、glob、catalog-id，逗号/分号/空白分隔。
启用 dry-run 通知时在禁用网络和子进程的通知进程中调用 notify.send。
不启动或安装浏览器；cloudscraper 如已通过公共注册表安装则优先使用，
否则使用 requests；无法处理的挑战按失败处理，不跳过 TLS 或伪造成功。

MIT License
Copyright (c) 0006s
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
        _ql_notify_identities = ('7d0a3609cba86c80', 'scripts/task_7d0a3609.py', 'task_7d0a3609.py', 'task_7d0a3609')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import subprocess
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from urllib.parse import urlsplit

TITLE = 'AnyRouter 自动签到'
CATALOG_ID = '7d0a3609cba86c80'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
MAX_RESPONSE = 1024 * 1024
DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)


def stamp():
    return datetime.now().isoformat(timespec='seconds')


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def enabled(value):
    return str(value).strip().lower() in TRUE


def load_config():
    explicit = os.getenv('ANYROUTER_CONFIG')
    path = Path(explicit) if explicit else Path(__file__).with_name('config.json')
    if not path.exists() and not explicit:
        return {}
    try:
        with path.open(encoding='utf-8') as handle:
            config = json.load(handle)
        if not isinstance(config, dict):
            raise ValueError()
        return config
    except (OSError, ValueError):
        raise ValueError('配置文件不可读或不是有效 JSON 对象') from None


def account_list(config):
    if 'ANYROUTER_COOKIES' in os.environ:
        return [{'cookie': line.strip()} for line in os.environ['ANYROUTER_COOKIES'].splitlines() if line.strip()]
    accounts = config.get('accounts', [])
    if not isinstance(accounts, list):
        raise ValueError('accounts 必须是账号数组')
    return accounts


def validate_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('缺少可信 HTTPS 根地址 ANYROUTER_BASE_URL 或 base_url')
    value = value.strip().rstrip('/')
    try:
        parts = urlsplit(value)
        valid = (parts.scheme == 'https' and parts.hostname and not parts.username
                 and not parts.password and not parts.query and not parts.fragment
                 and not parts.path and not re.search(r'[\s\\]', value))
        _ = parts.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('服务地址必须是无账号、查询或路径的 HTTPS 根地址')
    return value


def validate_cookie(account):
    if not isinstance(account, dict):
        raise ValueError('账号配置必须是对象')
    cookie = account.get('cookie', '')
    if not isinstance(cookie, str) or not cookie.strip():
        raise ValueError('Cookie 为空')
    cookie = cookie.strip()
    if any(ord(c) < 32 or ord(c) > 126 for c in cookie):
        raise ValueError('Cookie 包含非法字符')
    if cookie.lower().startswith('cookie:') or '=' not in cookie:
        raise ValueError('请填写完整 Cookie 值，不含 Cookie: 前缀')
    return cookie


def identity(data, cookie):
    """仅显示明确的公开身份，不输出任意服务端消息。"""
    records = [data]
    if isinstance(data.get('data'), dict):
        records.append(data['data'])
        if isinstance(data['data'].get('user'), dict):
            records.append(data['data']['user'])
    if isinstance(data.get('user'), dict):
        records.append(data['user'])
    secrets = [cookie] + [p.split('=', 1)[1].strip() for p in cookie.split(';') if '=' in p]
    for record in records:
        for field in ('nickname', 'username', 'display_name', 'displayName', 'uid', 'id'):
            value = record.get(field)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if not value or len(value) > 200:
                continue
            if any(secret and (secret == value or (len(secret) >= 6 and secret in value)) for secret in secrets):
                continue
            if re.search(r'(?i)cookie|token|session|authorization|device|[\r\n\x00-\x1f\x7f]', value):
                continue
            if field not in ('uid', 'id') and re.search(r'\+?\d[\d ()-]{9,}\d', value):
                continue
            return value
    return None


def sign_in(base_url, cookie):
    # 会话按账号隔离，不接受环境代理，不跟随重定向泄露 Cookie。
    try:
        import requests
        try:
            import cloudscraper
        except ImportError:
            cloudscraper = None
        session = cloudscraper.create_scraper() if cloudscraper else requests.Session()
        session.trust_env = False
        with session:
            with session.post(base_url + '/api/user/sign_in',
                              headers={'Cookie': cookie, 'User-Agent': DEFAULT_USER_AGENT,
                                       'Accept': 'application/json'},
                              timeout=(10, 30), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    return False, f'HTTP {response.status_code}，请检查服务地址或更新 Cookie', None
                payload = bytearray()
                for chunk in response.iter_content(8192):
                    payload.extend(chunk)
                    if len(payload) > MAX_RESPONSE:
                        return False, '响应超过安全大小限制', None
                try:
                    data = json.loads(payload)
                except (ValueError, UnicodeError):
                    return False, '响应不是有效 JSON，可能遇到挑战页', None
                if not isinstance(data, dict):
                    return False, '响应不是业务对象，未确认签到成功', None
                who = identity(data, cookie)
                if data.get('success') is True:
                    return True, '签到成功（接口 success=true）', who
                return False, '接口未明确确认成功，请检查 Cookie、签到状态或接口契约', who
    except ImportError:
        return False, '缺少 requests，请通过公共 Python 注册表安装', None
    except Exception:
        # 异常常含请求头、URL、响应体；不得输出异常文本。
        return False, '请求失败或超时，未确认签到成功', None


def notify_selected():
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if mode in FALSE:
        return False
    if mode in TRUE:
        return True
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS', '')
    names = [CATALOG_ID, Path(__file__).name, 'checkin.py', 'scripts/checkin.py', str(Path(__file__))]
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in re.split(r'[,;\s]+', selectors.strip()) if pattern
               for name in names)


# 通知在独立进程中运行，隔离输出并设超时，不影响业务退出码。
NOTIFY_RUNNER = r'''
import contextlib, importlib, importlib.util, os, pathlib, sys
if sys.argv[1] == 'dry':
    import socket, subprocess
    def denied(*args, **kwargs):
        raise OSError('dry-run: network disabled')
    socket.socket = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
    subprocess.Popen = denied
payload = __import__('json').loads(sys.stdin.read())
with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
    module = None
    try:
        module = importlib.import_module('notify')
        if not callable(getattr(module, 'send', None)):
            module = None
    except Exception:
        pass
    if module is None:
        paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            paths.append(pathlib.Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths += [pathlib.Path('/ql/data/scripts/notify.py'), pathlib.Path('/ql/scripts/notify.py')]
        for path in paths:
            if not path.is_file():
                continue
            try:
                sys.path.insert(0, str(path.parent))
                spec = importlib.util.spec_from_file_location('ql_notify', path)
                candidate = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(candidate)
                if callable(getattr(candidate, 'send', None)):
                    module = candidate
                    break
            except Exception:
                continue
    if module is None:
        sys.exit(2)
    result = module.send(payload['title'], payload['body'])
    if result is False:
        sys.exit(3)
'''


def send_notification(body, dry_run):
    if not notify_selected():
        return '未选中或已关闭'
    try:
        result = subprocess.run([sys.executable, '-c', NOTIFY_RUNNER, 'dry' if dry_run else 'live'],
                                input=json.dumps({'title': TITLE, 'body': body}), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if result.returncode == 0:
            return '预演通知已调用（禁网）' if dry_run else '通知调用完成'
        return '通知不可用或失败，业务退出码保持不变'
    except Exception:
        return '通知失败或超时，业务退出码保持不变'


def send_email(config, body, dry_run):
    email = config.get('email', {})
    if not isinstance(email, dict) or not email.get('enabled', False):
        return '邮件未启用'
    if dry_run:
        return '预演跳过邮件（禁网）'
    if not all(isinstance(email.get(k), str) and email[k].strip()
               for k in ('smtp_user', 'smtp_pass', 'recipient')):
        return '邮件配置不完整'
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = TITLE + '报告'
        msg['From'] = email['smtp_user']
        msg['To'] = email['recipient']
        with smtplib.SMTP_SSL(email.get('smtp_server', 'smtp.qq.com'),
                              int(email.get('smtp_port', 465)), timeout=15,
                              context=ssl.create_default_context()) as server:
            server.login(email['smtp_user'], email['smtp_pass'])
            server.sendmail(email['smtp_user'], [email['recipient']], msg.as_string())
        return '邮件发送完成'
    except Exception:
        return '邮件发送失败，业务退出码保持不变'


def main():
    start = time.monotonic()
    started = stamp()
    dry_run = enabled(os.getenv('ANYROUTER_DRY_RUN', '0'))
    log('=' * 48)
    log(f'{TITLE} | 开始时间 {started}')
    log('模式：' + ('断网预演' if dry_run else '正式签到'))
    config, accounts, records = {}, [], []
    config_error = False
    try:
        config = load_config()
        accounts = account_list(config)
        log(f'账号数量：{len(accounts)}')
        if not accounts:
            raise ValueError('未配置账号，请填写 ANYROUTER_COOKIES 或 accounts')
        base_url = validate_url(os.getenv('ANYROUTER_BASE_URL', config.get('base_url')))
    except ValueError as error:
        config_error = True
        log(f'❌ 阶段 1 配置检查：{error}；耗时 {time.monotonic() - start:.2f}s')
        log(f'账号数量：{len(accounts)}')
    if not config_error:
        for index, account in enumerate(accounts, 1):
            account_start = time.monotonic()
            stage = time.monotonic()
            log(f'账号 {index}/{len(accounts)} | 阶段 1/2：凭据检查')
            ok, message, who, skipped = False, '', None, False
            try:
                cookie = validate_cookie(account)
                log(f'凭据格式通过；耗时 {time.monotonic() - stage:.2f}s')
                stage = time.monotonic()
                log(f'账号 {index} | 阶段 2/2：' + ('模拟签到' if dry_run else '提交签到'))
                if dry_run:
                    ok, skipped = True, True
                    message = 'DRY_RUN_OK：配置通过，未发出网络请求或执行签到'
                else:
                    ok, message, who = sign_in(base_url, cookie)
            except ValueError as error:
                message = str(error)
            except Exception:
                message = '账号处理失败，详情已脱敏'
            if who is not None:
                log(f'账号 {index} 官方公开身份：{who}')
            log(f'{"✅" if ok else "❌"} 账号 {index}：{message}；阶段耗时 {time.monotonic() - stage:.2f}s')
            record = {'account': index, 'total': 1, 'success': int(ok and not skipped),
                      'alreadyComplete': 0, 'skipped': int(skipped), 'failed': int(not ok),
                      'ok': ok, 'seconds': round(time.monotonic() - account_start, 2)}
            records.append(record)
            log(f'账号 {index} 统计：总任务 1，成功 {record["success"]}，已完成 0，'
                f'跳过 {record["skipped"]}，失败 {record["failed"]}，耗时 {record["seconds"]}s')
    else:
        for index in range(1, len(accounts) + 1):
            records.append({'account': index, 'total': 1, 'success': 0, 'alreadyComplete': 0,
                            'skipped': 0, 'failed': 1, 'ok': False, 'seconds': 0})
            log(f'账号 {index} 统计：总任务 1，成功 0，已完成 0，跳过 0，失败 1（配置错误），耗时 0s')
    passed = sum(r['ok'] for r in records)
    failed = len(accounts) - passed
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'dry-run' if dry_run and not failed
              else 'success' if not failed else 'partial-failure' if passed else 'failure')
    body = (f'状态：{status}；账号总数 {len(accounts)}，成功 {passed}，失败 {failed}。'
            + ('预演只代表配置通过，业务签到未执行。' if dry_run else '成功仅依据接口 success=true。'))
    log('阶段 3：通知汇总')
    stage = time.monotonic()
    notification = send_notification(body, dry_run)
    mail = send_email(config, body, dry_run)
    log(f'{notification}；{mail}；耗时 {time.monotonic() - stage:.2f}s')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry_run else 'live', 'status': status,
               'accounts': len(accounts), 'successfulAccounts': passed, 'failedAccounts': failed,
               'tasks': {'total': len(records), 'success': sum(r['success'] for r in records),
                         'alreadyComplete': 0, 'skipped': sum(r['skipped'] for r in records),
                         'failed': sum(r['failed'] for r in records)},
               'results': records, 'configurationError': config_error,
               'notification': notification, 'email': mail, 'startedAt': started,
               'finishedAt': stamp(), 'seconds': round(time.monotonic() - start, 2),
               'exitCode': exit_code}
    log('-' * 48)
    log(f'任务统计：账号总数 {len(accounts)}，通过 {passed}，失败 {failed}；子任务 {summary["tasks"]}')
    log(f'结束时间 {summary["finishedAt"]} | 总耗时 {summary["seconds"]}s | 最终状态 {status} | 退出码 {exit_code}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
