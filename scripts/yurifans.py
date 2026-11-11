# -*- coding: utf-8 -*-
# name: Yurifans 每日签到
# cron: 32 10 * * *
# @File         : yurifans.py
# @Time         : 2023/04/25 12:17
# @Author       : Cloudac7, Jckling
# @Deprecated   : 站点接入雷池 WAF 人机验证
# Maintained standalone adaptation of jckling/Daily-Bonus checkin/yurifans.py.
# MIT License
# Copyright notices and attribution from the supplied source are retained above.
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
"""独立签到。YURIFANS_ACCOUNTS 每个非空行是一个 JSON 对象，包含
email、password，可选 cookie、user_agent。旧 YURIFANS_EMAIL/PASSWORD 按行配对。
在 https://yuri.website 正常登录并通过人机验证后，可从浏览器开发者工具
Network 中该站请求取得 Cookie 与 User-Agent，填入对应账号。不要公开这些值。
仅显式配置 YURIFANS_COOKIE_CACHE 时读取旧缓存，不写入或删除缓存。
上游未声明 cron，本版选择每日 08:17。YURIFANS_DRY_RUN=1 完全断网。
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
        _ql_notify_identities = ('b1ca5d9bad50645c', 'scripts/yurifans.py', 'yurifans.py', 'yurifans')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
import http.cookiejar
import importlib.util
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

BASE = 'https://yuri.website'
TITLE = 'Yurifans 每日签到'
CATALOG = 'b1ca5d9bad50645c'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


def accounts_from_env():
    raw = os.environ.get('YURIFANS_ACCOUNTS', '')
    if raw.strip():
        result = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                account = json.loads(line)
                valid = isinstance(account, dict) and all(
                    isinstance(account.get(key), str) and account[key].strip()
                    for key in ('email', 'password'))
                valid = valid and all(isinstance(account.get(key, ''), str)
                                      for key in ('cookie', 'user_agent'))
                if not valid:
                    raise ValueError()
                if any(c in account.get('cookie', '') + account.get('user_agent', '')
                       for c in '\r\n'):
                    raise ValueError()
                result.append(account)
            except (ValueError, TypeError):
                result.append(None)
        return result
    emails = [line for line in os.environ.get('YURIFANS_EMAIL', '').splitlines() if line.strip()]
    passwords = [line for line in os.environ.get('YURIFANS_PASSWORD', '').splitlines() if line.strip()]
    if not emails or len(emails) != len(passwords):
        raise TaskError('凭据缺失或旧变量非空行数量不一致，请配置 YURIFANS_ACCOUNTS')
    return [dict(email=email, password=password) for email, password in zip(emails, passwords)]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep credentials and authorization on the original HTTPS origin.
        return None


class Client:
    def __init__(self, account):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': BASE, 'Referer': BASE + '/',
            'User-Agent': account.get('user_agent') or 'Mozilla/5.0 YurifansCheckin/1.0',
        }
        cookie = account.get('cookie', '')
        cache = os.environ.get('YURIFANS_COOKIE_CACHE', '')
        if cache and not cookie:
            try:
                with open(os.path.expanduser(cache), encoding='utf-8') as handle:
                    data = json.load(handle)
                cookies = data.get('cookies') if isinstance(data, dict) else data
                if isinstance(data, dict) and isinstance(data.get('user_agent'), str):
                    self.headers['User-Agent'] = data['user_agent']
                # A shared legacy cache contributes clearance only, never a login session.
                cookie = '; '.join(f"{item['name']}={item['value']}" for item in cookies
                                   if isinstance(item, dict)
                                   and str(item.get('name', '')).startswith('sl-')
                                   and isinstance(item.get('value'), str))
            except (OSError, ValueError, TypeError, KeyError):
                raise TaskError('旧 Cookie 缓存无法读取，请更新或取消 YURIFANS_COOKIE_CACHE') from None
        if cookie:
            from http.cookies import SimpleCookie
            parsed = SimpleCookie()
            try:
                parsed.load(cookie)
                if not parsed:
                    raise ValueError()
                for name, item in parsed.items():
                    self.jar.set_cookie(http.cookiejar.Cookie(
                        0, name, item.value, None, False, 'yuri.website', False,
                        False, '/', True, True, None, True, None, None, {}))
            except Exception:
                raise TaskError('Cookie 格式无效') from None
        if any('\r' in value or '\n' in value for value in self.headers.values()):
            raise TaskError('请求头格式无效')

    def request(self, path, fields=None, token=None, html=False):
        headers = dict(self.headers)
        if token:
            headers['Authorization'] = 'Bearer ' + token
        body = None if fields is None else urllib.parse.urlencode(fields).encode()
        request = urllib.request.Request(BASE + path, data=body, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                payload = response.read(1024 * 1024 + 1)
                if response.status != 200 or len(payload) > 1024 * 1024:
                    raise TaskError('接口状态或响应大小异常')
        except urllib.error.HTTPError as error:
            raise TaskError(f'HTTP {error.code}，请核对凭据及 WAF 通行状态') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络连接失败或请求超时') from None
        if html:
            text = payload.decode('utf-8', errors='replace')
            if 'SafeLineChallenge' in text or 'wp-content' not in text:
                raise TaskError('站点验证未通过，请在浏览器取得有效通行 Cookie')
            return
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeError):
            raise TaskError('接口未返回有效 JSON，可能需要更新通行 Cookie') from None
        if isinstance(data, dict) and (
                data.get('success') is False or data.get('error')
                or ('code' in data and data['code'] not in (0, 200, '0', '200', 'success'))):
            raise TaskError('接口返回业务错误，请核对凭据和接口状态')
        return data


def identity(data):
    for field in ('name', 'nickname', 'display_name', 'username'):
        value = data.get(field)
        if isinstance(value, str) and value:
            # Phone-like and email values are credential/contact data, not public names.
            if '@' not in value and not re.search(r'\+?\d[\d ()-]{6,}\d', value):
                log('官方账号名称 ' + json.dumps(value, ensure_ascii=False))


def mission_data(data):
    if not isinstance(data, dict) or not isinstance(data.get('mission'), dict):
        raise TaskError('签到状态结构异常')
    mission = data['mission']
    if 'date' not in mission or not isinstance(mission['date'], (str, int, float, type(None))):
        raise TaskError('签到日期字段缺失或异常')
    return mission


def print_points(mission):
    for key, label in (('credit', '今日奖励'), ('my_credit', '当前积分')):
        value = mission.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            log(f'{label} {value} 积分')
        elif isinstance(value, str) and re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            log(f'{label} {value} 积分')


def run_account(account, dry, stats):
    client = None
    token = None
    for stage, title in enumerate(('检查站点与通行状态', '登录并验证账号', '查询每日签到', '执行签到并复核'), 1):
        start = time.monotonic()
        log(f'阶段 {stage}/4 {title}')
        try:
            if dry:
                stats['skipped'] += 1
                log(f'⏭️ 断网预演，阶段耗时 {time.monotonic() - start:.2f} 秒')
                continue
            if stage == 1:
                client = Client(account)
                client.request('/', html=True)
            elif stage == 2:
                # Require a fresh login cookie from this login request.
                for cookie in list(client.jar):
                    if cookie.name == 'b2_token':
                        client.jar.clear(cookie.domain, cookie.path, cookie.name)
                data = client.request('/wp-json/jwt-auth/v1/token',
                                      dict(username=account['email'], password=account['password']))
                if not isinstance(data, dict):
                    raise TaskError('登录响应结构异常')
                tokens = [cookie.value for cookie in client.jar if cookie.name == 'b2_token']
                if not tokens:
                    raise TaskError('登录失败，未取得 b2_token')
                token = tokens[-1]
                identity(data)
                user = client.request('/wp-json/b2/v1/getUserInfo', {'ref': 'null'}, token)
                if not isinstance(user, dict) or not user:
                    raise TaskError('登录态校验失败')
                identity(user)
            elif stage == 3:
                mission = mission_data(client.request('/wp-json/b2/v1/getUserMission',
                                                     {'count': 6, 'paged': 1}, token))
                already = bool(mission['date'])
                print_points(mission)
                if already:
                    log('☑️ 今日已签到')
            elif already:
                stats['alreadyComplete'] += 1
                log(f'☑️ 已完成，无需重复签到，阶段耗时 {time.monotonic() - start:.2f} 秒')
                continue
            else:
                client.request('/wp-json/b2/v1/userMission', {}, token)
                confirmed = mission_data(client.request('/wp-json/b2/v1/getUserMission',
                                                       {'count': 6, 'paged': 1}, token))
                if not confirmed['date']:
                    raise TaskError('签到后未能确认已签到状态')
                print_points(confirmed)
                log('✅ 签到成功，已复核签到状态')
            stats['success'] += 1
            log(f'✅ 阶段完成，耗时 {time.monotonic() - start:.2f} 秒')
        except Exception:
            stats['failure'] += 1
            stats['skipped'] += 4 - stage
            log(f'❌ 阶段失败，耗时 {time.monotonic() - start:.2f} 秒')
            raise


def notify(body, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    selection = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    names = (CATALOG, 'yurifans.py', 'candidate.py', 'scripts/yurifans.py', 'scripts/candidate.py')
    selected = selection is not None and any(
        fnmatch.fnmatch(name, pattern)
        for pattern in re.split(r'[,;\s]+', selection.strip()) if pattern for name in names)
    if switch in FALSE or (switch not in TRUE and not selected):
        return '已关闭或未选中'
    if dry:
        return '断网预演，已生成脱敏通知，跳过外部投递'
    locations = []
    configured = os.environ.get('QINGLONG_NOTIFY_DIR')
    if configured:
        locations.append(Path(configured))
    locations.extend((Path(__file__).resolve().parent, Path('/ql/data/scripts'), Path('/ql/scripts')))
    paths = []
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.append(Path(spec.origin))
    except (ImportError, ValueError):
        pass
    paths.extend(folder / 'notify.py' for folder in locations)
    code = ('import importlib.util,json,sys; p,t,b=json.load(sys.stdin); '
            's=importlib.util.spec_from_file_location("ql_notification",p); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(t,b)')
    for path in dict.fromkeys(paths):
        if path.is_file():
            try:
                subprocess.run([sys.executable, '-c', code],
                               input=json.dumps([str(path), TITLE, body]), text=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=30, check=True)
                return '已发送'
            except (OSError, subprocess.SubprocessError):
                continue
    js = 'const fs=require("fs");const [p,t,b]=JSON.parse(fs.readFileSync(0,"utf8"));Promise.resolve(require(p).sendNotify(t,b)).catch(()=>process.exit(1));'
    for folder in locations:
        path = folder / 'sendNotify.js'
        if path.is_file():
            try:
                subprocess.run(['node', '-e', js], input=json.dumps([str(path), TITLE, body]),
                               text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=30, check=True)
                return '已发送'
            except (OSError, subprocess.SubprocessError):
                continue
    return '通知不可用或投递失败，保留业务退出码'


def main():
    started = time.monotonic()
    dry = os.environ.get('YURIFANS_DRY_RUN', '').lower() in TRUE
    summary = dict(total=0, success=0, failure=0, mode='dry-run' if dry else 'live',
                   tasks=dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0))
    log('=' * 48)
    log(TITLE)
    log(f'开始时间 {datetime.datetime.now().isoformat(timespec="seconds")}')
    log('运行模式 ' + ('断网预演' if dry else '正式执行'))
    configuration_error = False
    try:
        accounts = accounts_from_env()
        summary['total'] = len(accounts)
        log(f'账号总数 {len(accounts)}')
        for index, account in enumerate(accounts, 1):
            account_start = time.monotonic()
            stats = dict(total=4, success=0, alreadyComplete=0, skipped=0, failure=0)
            log(f'--- 账号 {index}/{len(accounts)} ---')
            try:
                if account is None:
                    configuration_error = True
                    stats.update(failure=1, skipped=3)
                    raise TaskError('账号配置格式无效，请使用逐行 JSON')
                run_account(account, dry, stats)
                summary['success'] += 1
            except TaskError as error:
                summary['failure'] += 1
                log('❌ ' + str(error))
            except Exception:
                summary['failure'] += 1
                log('❌ 请求或响应处理异常，详情已脱敏')
            for key, value in stats.items():
                summary['tasks'][key] += value
            log(f'账号 {index} 统计 总任务 {stats["total"]} 成功 {stats["success"]} '
                f'已完成 {stats["alreadyComplete"]} 跳过 {stats["skipped"]} '
                f'失败 {stats["failure"]} 耗时 {time.monotonic() - account_start:.2f} 秒')
    except TaskError as error:
        configuration_error = True
        log('账号总数 0')
        log('❌ 配置错误 ' + str(error))
    exit_code = 1 if configuration_error or summary['failure'] else 0
    status = ('configuration-error' if configuration_error else
              'partial-failure' if summary['failure'] and summary['success'] else
              'failure' if summary['failure'] else 'dry-run' if dry else 'success')
    summary.update(status=status, exitCode=exit_code)
    body = (f'状态 {status}\n账号总数 {summary["total"]} 成功 {summary["success"]} '
            f'失败 {summary["failure"]}\n子任务 {json.dumps(summary["tasks"], ensure_ascii=False)}')
    try:
        notification = notify(body, dry)
    except Exception:
        notification = '通知处理失败，保留业务退出码'
    summary.update(notification=notification, durationSeconds=round(time.monotonic() - started, 2),
                   finishTime=datetime.datetime.now().isoformat(timespec='seconds'))
    log('-' * 48)
    log(body)
    log(f'通知状态 {notification}')
    log(f'总耗时 {summary["durationSeconds"]} 秒')
    log(f'完成时间 {summary["finishTime"]} 最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
