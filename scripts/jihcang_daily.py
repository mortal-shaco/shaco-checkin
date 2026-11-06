#!/usr/bin/env python3
# name: ikuuu 每日签到
# cron: 45 9 * * *
# Upstream: Yun-Xn/jihcang_dailycheckin, main.py
# Source commit: 5fb092f554b4153116f63678d51facaea5ded112
# License: MIT (effectiveLicense supplied by source catalog).
# The upstream input contains no additional copyright/license notices.
#
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""独立签到脚本；安装依赖：pip install requests。

青龙变量 IKUUU_ACCOUNTS：每行 邮箱|密码，只按第一个 | 分隔；密码中可含 |。
邮箱和密码在本人 ikuuu 注册/登录页面取得。无须提供 Cookie 或设备标识。
未设置账号变量时兼容同目录 config.json：accounts=[{email,password}]，
urls.login/checkin/info、proxy.enabled/http/https、settings.timeout/user_agent、
push.sckey/token；info 保留兼容但与上游一致不请求资料页。
IKUUU_LOGIN_URL / IKUUU_CHECKIN_URL 可覆盖旧网址；仅接受同源 HTTPS，
请从本人已核实的官方站点登录和签到请求取得，禁止跟随重定向泄漏凭据。
默认仍为 https://ikuuu.de/auth/login 与 /user/checkin，未联网验证域名现状。
IKUUU_DRY_RUN=1 仅校验配置和演练两个阶段，不调用任何网络或通知后端。
QINGLONG_NOTIFY 默认 auto，仅名单选中时推送；显式 1 强制开启，0 关闭。
名单 QINGLONG_NOTIFY_SCRIPTS 支持目录相对路径、文件名、glob、目录 ID 或 *。
旧推送配置仅在实跑且 QINGLONG_NOTIFY 未关闭时使用，Server酱优先。
每天 08:00 是新增建议排期；上游未指定 cron。签到是唯一账户业务写操作。
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
        _ql_notify_identities = ('ae5775497353fb56', 'scripts/jihcang_daily.py', 'jihcang_daily.py', 'jihcang_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

TITLE = 'ikuuu 每日签到'
CATALOG = 'ae5775497353fb56'
YES = {'1', 'true', 'yes', 'on'}
NO = {'0', 'false', 'no', 'off'}
DEFAULT_LOGIN = 'https://ikuuu.de/auth/login'
DEFAULT_CHECK = 'https://ikuuu.de/user/checkin'


class TaskError(Exception):
    pass


def log(message):
    print(time.strftime('[%H:%M:%S] ') + message, flush=True)


def secure_url(value):
    try:
        p = urlsplit(value)
        if (p.scheme != 'https' or not p.hostname or p.username or p.password
                or p.query or p.fragment or p.port not in (None, 443)):
            raise ValueError
    except (ValueError, TypeError):
        raise TaskError('接口地址必须为无凭据、无查询参数的 HTTPS 地址') from None
    return value


def load_settings():
    cfg = {}
    path = Path(__file__).with_name('config.json')
    # 显式账号变量优先；旧文件仅作为可选兼容输入，不是运行依赖。
    if path.is_file():
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(cfg, dict):
                raise ValueError
        except (OSError, ValueError):
            raise TaskError('旧 config.json 无法读取或格式错误') from None
    for key in ('urls', 'proxy', 'settings', 'push'):
        if not isinstance(cfg.get(key, {}), dict):
            raise TaskError('旧配置中的设置分组必须为对象')
    raw = os.environ.get('IKUUU_ACCOUNTS')
    accounts = []
    if raw is not None:
        for line in raw.splitlines():
            if not line.strip():
                continue
            email, sep, password = line.partition('|')
            email = email.strip()
            accounts.append((email, password) if sep else ('', ''))
    else:
        rows = cfg.get('accounts', [])
        if not isinstance(rows, list):
            raise TaskError('旧配置 accounts 必须为数组')
        for row in rows:
            if not isinstance(row, dict):
                accounts.append(('', ''))
            else:
                accounts.append((row.get('email', ''), row.get('password', '')))
    urls = cfg.get('urls', {})
    login = secure_url(os.environ.get('IKUUU_LOGIN_URL', urls.get('login', DEFAULT_LOGIN)))
    check = secure_url(os.environ.get('IKUUU_CHECKIN_URL', urls.get('checkin', DEFAULT_CHECK)))
    if urlsplit(login).netloc.lower() != urlsplit(check).netloc.lower():
        raise TaskError('登录与签到地址必须同源')
    settings = cfg.get('settings', {})
    try:
        timeout = float(settings.get('timeout', 10))
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError
    except (TypeError, ValueError):
        raise TaskError('settings.timeout 必须大于 0 且不超过 120 秒') from None
    agent = settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36')
    if not isinstance(agent, str) or '\r' in agent or '\n' in agent:
        raise TaskError('settings.user_agent 格式错误')
    proxy = cfg.get('proxy', {})
    if not isinstance(proxy.get('enabled', False), bool):
        raise TaskError('proxy.enabled 必须为布尔值')
    return accounts, login, check, timeout, agent, proxy, cfg.get('push', {})


def http_json(session, url, timeout, **kwargs):
    """无重试、禁止跳转、有界读取；不输出响应/异常/请求头。"""
    try:
        with session.post(url, timeout=timeout, allow_redirects=False, stream=True, **kwargs) as response:
            if response.status_code != 200:
                raise TaskError('HTTP 状态异常（%d）；请核实官方地址、访问限制或服务状态' % response.status_code)
            body = bytearray()
            started = time.monotonic()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > 262144 or time.monotonic() - started > timeout:
                    raise TaskError('响应过大或读取超时')
            data = json.loads(body)
            if not isinstance(data, dict):
                raise TaskError('接口响应结构错误')
            return data
    except TaskError:
        raise
    except Exception as exc:
        # 仅输出类别，不输出可能含密码、Cookie、URL、代理和会话值的异常文本。
        kind = type(exc).__name__
        hints = {'SSLError': 'TLS 证书校验失败；检查系统时间与根证书',
                 'ProxyError': '代理连接失败；检查旧配置 proxy 的地址和端口',
                 'ConnectionError': '连接失败；检查官方域名、DNS、网络与防火墙',
                 'Timeout': '网络超时；检查网络或稍后重试',
                 'ReadTimeout': '响应超时；稍后重试',
                 'ConnectTimeout': '连接超时；检查网络',
                 'JSONDecodeError': '接口未返回有效 JSON；核实官方接口'}
        raise TaskError(hints.get(kind, '请求或响应处理失败，请检查配置及接口契约')) from None


def business_ok(data):
    # SSPanel 的明确 ret 成功标志；绝不把 HTTP 200 或任意 msg 当作成功。
    value = data.get('ret')
    return type(value) in (int, str) and value in (1, '1')


def already_done(data):
    msg = data.get('msg')
    return (type(data.get('ret')) in (int, str) and data.get('ret') in (0, '0') and isinstance(msg, str)
            and bool(re.fullmatch(r'\s*(?:您)?(?:今天|今日)?(?:已经|已)签到(?:过)?(?:了)?[！!。.]?\s*', msg)))


def print_identity(data, secrets):
    containers = [data]
    for key in ('data', 'user'):
        if isinstance(data.get(key), dict):
            containers.append(data[key])
    for container in containers:
        for key in ('nickname', 'username', 'display_name', 'public_uid'):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (not value or len(value) > 128 or any(ord(c) < 32 for c in value)
                    or any(s and s in value for s in secrets)
                    or re.search(r'@|(?i:cookie|token|session|bearer)', value)
                    or (key != 'public_uid' and re.search(r'(?:\+?\d[\s-]?){7,}', value))):
                continue
            log('官方账号身份：' + value)
            return


def run_account(index, credentials, settings, dry):
    started = time.monotonic()
    result = {'account': index, 'total': 2, 'success': 0, 'alreadyComplete': 0,
              'skipped': 0, 'failed': 0, 'status': 'failure'}
    email, password = credentials
    log('--- 账号 %d ---' % index)
    session = None
    stage = 1
    tick = time.monotonic()
    try:
        log('阶段 1/2 登录：开始')
        if (not isinstance(email, str) or not isinstance(password, str)
                or not re.fullmatch(r'[^\s@|]+@[^\s@|]+', email) or not password):
            raise TaskError('账号配置不完整；每行须为 邮箱|密码')
        if dry:
            log('阶段 1/2 登录：DRY_RUN 配置通过，未发送请求（%.2f 秒）' % (time.monotonic() - tick))
            stage = 2
            tick = time.monotonic()
            log('阶段 2/2 签到：DRY_RUN 跳过写操作（%.2f 秒）' % (time.monotonic() - tick))
            result.update(skipped=2, status='dry-run')
        else:
            import requests
            _, login, check, timeout, agent, proxy, _ = settings
            session = requests.Session()
            session.trust_env = False
            if proxy.get('enabled', False):
                session.proxies.update({k: proxy.get(k, 'http://127.0.0.1:7890') for k in ('http', 'https')})
                log('代理模式：启用（地址已隐藏）')
            else:
                log('代理模式：直连')
            origin = 'https://' + urlsplit(login).netloc
            headers = {'origin': origin, 'user-agent': agent}
            data = http_json(session, login, timeout, headers=headers, data={'email': email, 'passwd': password})
            if not business_ok(data):
                raise TaskError('登录业务未成功或响应契约未知；未发送签到请求')
            print_identity(data, (email, password))
            result['success'] += 1
            log('阶段 1/2 登录：✅ 业务验证通过（%.2f 秒）' % (time.monotonic() - tick))
            stage = 2
            tick = time.monotonic()
            log('阶段 2/2 签到：开始')
            data = http_json(session, check, timeout, headers=headers)
            print_identity(data, (email, password))
            if business_ok(data):
                result['success'] += 1
                log('阶段 2/2 签到：✅ ret=1，签到成功（%.2f 秒）' % (time.monotonic() - tick))
            elif already_done(data):
                result['alreadyComplete'] += 1
                log('阶段 2/2 签到：☑️ 官方明确返回已经签到（%.2f 秒）' % (time.monotonic() - tick))
            else:
                raise TaskError('签到业务未成功或响应契约未知')
            result['status'] = 'success'
    except Exception as exc:
        result['failed'] = 1
        result['skipped'] = 2 - result['success'] - result['alreadyComplete'] - 1
        message = str(exc) if isinstance(exc, TaskError) else '运行错误，请检查依赖及配置'
        log('阶段 %d/2：❌ %s（%.2f 秒）' % (stage, message, time.monotonic() - tick))
    finally:
        if session is not None:
            session.close()
    result['seconds'] = round(time.monotonic() - started, 3)
    log('账号 %(account)d 统计：总任务 %(total)d，成功 %(success)d，已完成 %(alreadyComplete)d，跳过 %(skipped)d，失败 %(failed)d，耗时 %(seconds).3f 秒' % result)
    return result


def selected_for_notification():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in NO:
        return False
    if switch in YES:
        return True
    selectors = re.split(r'[,;\s]+', os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    path = Path(__file__)
    names = [CATALOG, path.name]
    for parent in path.parents:
        if parent.name == 'scripts':
            names.append(path.relative_to(parent).as_posix())
    return any(s and any(fnmatch.fnmatchcase(n, s) for n in names) for s in selectors)


def notify(summary, dry, push):
    body = ('账号总数 {accounts}，成功 {success}，失败 {failed}；状态 {status}。'
            '子任务成功 {stepsSuccess}，已完成 {stepsAlreadyComplete}，跳过 {stepsSkipped}，失败 {stepsFailed}。').format(**summary)
    if dry:
        log('通知：断网预演，已生成脱敏摘要，不调用推送后端；' + body)
        return 'dry-run-no-network'
    states = []
    if selected_for_notification():
        directories = [Path(__file__).parent]
        if os.environ.get('QINGLONG_NOTIFY_DIR'):
            directories.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
        directories.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
        found = False
        for directory in dict.fromkeys(directories):
            py = directory / 'notify.py'
            js = directory / 'sendNotify.js'
            if py.is_file():
                command = [sys.executable, '-c',
                           'import importlib.util,sys; s=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])',
                           str(py), TITLE, body]
            elif js.is_file():
                command = ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(js), TITLE, body]
            else:
                continue
            found = True
            try:
                proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
                states.append('sent' if proc.returncode == 0 else 'failed')
                if proc.returncode == 0:
                    break
            except Exception:
                states.append('failed')
        if not found:
            # 支持通过 Python 搜索路径安装的青龙 notify 模块。
            try:
                if importlib.util.find_spec('notify'):
                    proc = subprocess.run([sys.executable, '-c', 'from notify import send; import sys; send(sys.argv[1],sys.argv[2])', TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
                    states.append('sent' if proc.returncode == 0 else 'failed')
                else:
                    states.append('unavailable')
            except Exception:
                states.append('failed')
    # 保留显式配置的旧推送功能，统一 HTTPS、有界请求、不打印后端响应。
    if os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip() not in NO:
        sckey, token = push.get('sckey', '1'), push.get('token', '1')
        try:
            if sckey != '1' or token != '1':
                import requests
                with requests.Session() as session:
                    session.trust_env = False
                    if sckey != '1':
                        if not isinstance(sckey, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', sckey):
                            raise TaskError('推送密钥格式错误')
                        response = http_json(session, 'https://sctapi.ftqq.com/' + sckey + '.send', 10, data={'title': TITLE, 'desp': body})
                        ok = type(response.get('code')) is int and response['code'] == 0
                    else:
                        response = http_json(session, 'https://www.pushplus.plus/send', 10, json={'token': token, 'title': TITLE, 'content': body, 'template': 'json'})
                        ok = type(response.get('code')) is int and response['code'] == 200
                    states.append('legacy-sent' if ok else 'legacy-failed')
        except Exception:
            states.append('legacy-failed')
    status = ','.join(states) if states else 'disabled'
    log('通知状态：' + status + '（不改变业务退出码）')
    return status


def main():
    start = time.monotonic()
    dry = os.environ.get('IKUUU_DRY_RUN', '').strip().lower() in YES
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S %z'))
    log('运行模式：' + ('DRY_RUN（完全断网）' if dry else '实跑'))
    results, push = [], {}
    config_error = False
    try:
        settings = load_settings()
        accounts, *_, push = settings
        log('账号数量：%d' % len(accounts))
        if not accounts:
            raise TaskError('未配置账号；请设置 IKUUU_ACCOUNTS 或旧 config.json 的 accounts')
        for index, account in enumerate(accounts, 1):
            results.append(run_account(index, account, settings, dry))
    except Exception as exc:
        config_error = True
        log('配置错误：' + (str(exc) if isinstance(exc, TaskError) else '无法解析配置'))
        log('账号数量：0（配置未通过）')
    failed = sum(r['status'] == 'failure' for r in results)
    succeeded = sum(r['status'] == 'success' for r in results)
    status = ('configuration-error' if config_error else 'partial-failure' if failed and len(results) > failed
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'accounts': len(results), 'success': succeeded, 'failed': failed,
               'dryRunAccounts': sum(r['status'] == 'dry-run' for r in results), 'status': status,
               'stepsSuccess': sum(r['success'] for r in results),
               'stepsAlreadyComplete': sum(r['alreadyComplete'] for r in results),
               'stepsSkipped': sum(r['skipped'] for r in results),
               'stepsFailed': sum(r['failed'] for r in results), 'results': results}
    exit_code = 1 if config_error or failed else 0
    try:
        summary['notification'] = notify(summary, dry, push)
    except Exception:
        summary['notification'] = 'failed'
        log('通知失败，保留业务退出码')
    summary['seconds'] = round(time.monotonic() - start, 3)
    summary['finishedAt'] = time.strftime('%Y-%m-%d %H:%M:%S %z')
    log('----------------------------------------')
    log('任务统计：账号总数 %(accounts)d，成功 %(success)d，失败 %(failed)d，预演 %(dryRunAccounts)d' % summary)
    log('子任务统计：成功 %(stepsSuccess)d，已完成 %(stepsAlreadyComplete)d，跳过 %(stepsSkipped)d，失败 %(stepsFailed)d' % summary)
    log('总耗时：%.3f 秒；完成时间：%s' % (summary['seconds'], summary['finishedAt']))
    log('最终状态：%s；通知：%s' % (status, summary['notification']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
