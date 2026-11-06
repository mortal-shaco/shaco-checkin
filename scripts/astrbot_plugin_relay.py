#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 中转站每日签到
# cron: 39 9 * * *
# Upstream: WFCrush/astrbot_plugin_relay_checkin, main.py, v2.0.0
# License: MIT (upstream attribution retained).
"""独立维护版。RELAY_ACCOUNTS 每个非空行一个 JSON 对象：
{"url":"https://站点域名","mode":"token","token":"访问令牌占位符","uid":"本站用户ID"}
也支持 mode=cookie（cookie 字段）及 mode=password（username/password 字段）。
令牌从本站个人设置→安全设置获取系统访问令牌，不是 sk- API 密钥；
uid 从同一站个人资料查看。Cookie 在浏览器登录并自行完成人机校验后，
从本站请求头复制完整 Cookie。密码为本站登录密码，不支持绕过验证码。
JSON 字符串中的分隔符原样保留。可选 name、enabled、sched；禁止存入公开仓库。
兼容上游旧行式：名称|https://域名|token=令牌|uid=编号；复杂凭据请用 JSON。
RELAY_ACTION=checkin（默认）或 query/verify（只读验证，不签到）。
青龙每天 08:30 调度；默认确定性延迟 0–20 分钟，失败最多重试 3 次，
每次间隔 30 分钟，不跨天重试；鉴权、人机校验、已签到和未启用不重试。
RELAY_DRY_RUN=1 完全不联网，不等待、不导入通知模块、不写任何账号数据。
RELAY_SELECT 可按原始账号序号或名称选一个账号；空值处理全部启用且 sched 的账号。
QINGLONG_NOTIFY=auto 默认按 QINGLONG_NOTIFY_SCRIPTS 选择通知；未配置列表不发送。

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
        _ql_notify_identities = ('c7b19578064eea37', 'scripts/astrbot_plugin_relay.py', 'astrbot_plugin_relay.py', 'astrbot_plugin_relay')
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
import math
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

TITLE = '中转站每日签到'
CATALOG = 'c7b19578064eea37'
PATHS = ('/api/user/check_in', '/api/user/checkin', '/api/user/clock_in', '/api/user/sign_in')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
ALREADY = re.compile(r'今[日天].{0,4}(已|签过)|已(经)?签到|already|duplicate', re.I)
CF = re.compile(r'cloudflare|cf-chl|just a moment|challenge-platform|turnstile|captcha|人机|验证码', re.I)
AUTH = re.compile(r'未登录|无权|token.*无效|invalid.*token|unauthor|登录已过期|请先登录|未提供\s*\S*-?User|与登录用户不匹配|格式错误', re.I)
DISABLED = re.compile(r'签到.{0,6}(未|没).{0,4}(启用|开启)|未启用|not enabled', re.I)


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class Failure(Exception):
    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向其他地址重发带凭据请求


def number(name, default, minimum, maximum):
    try:
        n = int(os.environ.get(name, str(default)))
        if not minimum <= n <= maximum:
            raise ValueError
        return n
    except ValueError:
        raise Failure(f'{name} 必须为 {minimum}–{maximum} 的整数')


def parse_account(line):
    if line.startswith('{'):
        d = json.loads(line)
    else:
        # 保留上游简单行式；只在第一个等号或冒号处分割字段。
        parts = re.split('[|｜]', line)
        d, positional = {}, []
        aliases = {'base': 'url', 'key': 'token', 'id': 'uid', 'user': 'username', 'pass': 'password', 'cf': 'cloudflare'}
        for p in parts:
            p = p.strip()
            m = re.match(r'^(name|url|base|token|key|uid|id|user|username|pass|password|cookie|cf|cloudflare)\s*[=:]\s*(.*)$', p, re.I)
            if m:
                k = m[1].lower()
                d[aliases.get(k, k)] = m[2]
            elif p:
                positional.append(p)
        for i, p in enumerate(positional):
            if p.startswith(('https://', 'http://')) or re.match(r'^[\w.-]+\.[a-z]{2,}(/|$)', p, re.I):
                d.setdefault('url', p)
                if i:
                    d.setdefault('name', positional.pop(0))
                positional.remove(p)
                break
        for p in positional:
            if p.isdigit() and not d.get('uid'):
                d['uid'] = p
            elif p.lower().startswith('session=') or '; ' in p:
                d.setdefault('cookie', p)
            elif ':' in p and '/' not in p and not d.get('username'):
                d['username'], d['password'] = p.split(':', 1)
            else:
                d.setdefault('token', p)
    if not isinstance(d, dict):
        raise Failure('每行必须是账号 JSON 对象或旧行式配置')
    d = dict(d)
    for old, new in [('base', 'url'), ('user', 'username'), ('pass', 'password'), ('id', 'uid')]:
        if new not in d and old in d:
            d[new] = d[old]
    for key in ('url', 'mode', 'token', 'cookie', 'username', 'password', 'name'):
        if key in d and not isinstance(d[key], str):
            raise Failure('账号文本字段类型错误')
    base = d.get('url', '').strip().rstrip('#').rstrip('/')
    base = re.sub(r'/(profile|console|panel|dashboard|token|setting)s?/?$', '', base, flags=re.I)
    if base and '://' not in base:
        base = 'https://' + base
    u = urlsplit(base)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise Failure('站点须为无内嵌凭据、查询或片段的 HTTPS 地址')
    d['url'] = base.rstrip('/')
    mode = d.get('mode') or ('token' if d.get('token') else 'cookie' if d.get('cookie') else 'password')
    required = {'token': ('token',), 'cookie': ('cookie',), 'password': ('username', 'password')}
    if mode not in required or any(not d.get(k) for k in required[mode]):
        raise Failure('缺少对应模式凭据；令牌需系统访问令牌，密码需 username/password，Cookie 需完整 cookie')
    d['mode'] = mode
    d['uid'] = str(d.get('uid') or '')
    if d['uid'] and not d['uid'].isdigit():
        raise Failure('uid 必须为本站数字用户 ID')
    for k in ('enabled', 'sched'):
        if k in d and not isinstance(d[k], bool):
            raise Failure('enabled 和 sched 必须为 JSON 布尔值')
    if any('\r' in d.get(k, '') or '\n' in d.get(k, '') for k in ('token', 'cookie')):
        raise Failure('请求头凭据不能含换行')
    return d


class Client:
    def __init__(self, account, timeout):
        self.a = account
        self.timeout = timeout
        self.opener = build_opener(NoRedirect(), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, path, payload=None):
        headers = {'Accept': 'application/json', 'User-Agent': 'RelayCheckin/2.0', 'Referer': self.a['url'] + '/'}
        if self.a.get('token'):
            headers['Authorization'] = self.a['token']
        if self.a.get('cookie'):
            headers['Cookie'] = self.a['cookie']
        if self.a['uid']:
            for k in ('New-Api-User', 'Veloera-User', 'VoApi-User'):
                headers[k] = self.a['uid']
        body = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(payload).encode()
        req = Request(self.a['url'] + path, data=body, headers=headers, method=method)
        try:
            try:
                resp = self.opener.open(req, timeout=self.timeout)
            except HTTPError as e:
                resp = e
            with resp:
                status = resp.code
                raw = resp.read(1048577)
            if len(raw) > 1048576:
                raise Failure('响应过大，停止处理')
            text = raw.decode('utf-8', errors='replace')
            if CF.search(text) and (status in (403, 429, 503) or '<html' in text.lower()):
                raise Failure('人机校验拦截；请在网页手动签到或重新获取 Cookie')
            try:
                data = json.loads(text)
            except ValueError:
                data = None
            return status, data if isinstance(data, dict) else None, '<html' in text.lower() or '<!doctype html' in text.lower()
        except (URLError, TimeoutError, OSError):
            # 变更请求可能已经到达服务端，不立刻切换接口重复执行。
            raise Failure('请求超时或网络错误，未确认业务成功', retry=True)

    @staticmethod
    def check(status, data):
        msg = str((data or {}).get('message') or '')
        if CF.search(msg):
            raise Failure('接口需要人机校验；请在网页手动操作或改用 Cookie')
        if AUTH.search(msg) or status in (401, 403):
            raise Failure('凭据或本站用户 ID 无效；请从同一站个人资料重新获取')
        if not 200 <= status < 300 or not data or data.get('success') is not True:
            raise Failure(f'接口未确认业务成功（HTTP {status}）', retry=status == 429 or status >= 500)
        return data.get('data')

    def info(self):
        status, data, _ = self.request('GET', '/api/user/self')
        info = self.check(status, data)
        if not isinstance(info, dict):
            raise Failure('账号信息响应结构无效')
        if not self.a['uid'] and info.get('id') is not None:
            uid = str(info['id'])
            if not uid.isdigit():
                raise Failure('服务端用户 ID 格式无效')
            self.a['uid'] = uid
        return info

    def sign(self):
        for path in PATHS:
            status, data, html = self.request('POST', path, {})
            if status in (404, 405) or (status == 200 and data is None and html):
                log(f'  接口 {path} 不适用，探测下一个接口')
                continue
            msg = str((data or {}).get('message') or '')
            if 200 <= status < 300 and data and data.get('success') is False and ALREADY.search(msg) and not CF.search(msg) and not AUTH.search(msg):
                return 'already', None
            if DISABLED.search(msg):
                raise Failure('本站未启用签到，未获得签到成功确认')
            reward = self.check(status, data)
            gained = None
            if isinstance(reward, dict):
                gained = next((reward[k] for k in ('quota_awarded', 'quota', 'reward', 'awarded_quota') if reward.get(k) is not None), None)
            return 'ok', gained
        raise Failure('四个已知签到接口均不可用')


def amount(value, unit):
    try:
        n = float(value) / unit
        if math.isfinite(n):
            return f'${n:.4f}' if 0 < abs(n) < .1 else f'${n:.2f}'
    except (TypeError, ValueError, OverflowError):
        pass
    return '未知'


def identity(info, a):
    value = next((str(info[k]) for k in ('display_name', 'username', 'nickname', 'id') if info.get(k) is not None and str(info[k])), '')
    # 仅公开身份可以展示，删除控制字符和意外返回的凭据/手机号。
    for key in ('token', 'cookie', 'password'):
        if a.get(key):
            value = value.replace(a[key], '[凭据已隐藏]')
    value = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', value)
    return ''.join(c for c in value if c.isprintable())


def stage(n, title, fn):
    start = time.monotonic()
    log(f'阶段 {n}：{title}')
    try:
        result = fn()
    except Exception:
        log(f'阶段 {n}：❌ {title}失败（耗时 {time.monotonic()-start:.2f} 秒）')
        raise
    log(f'阶段 {n}：✅ {title}（耗时 {time.monotonic()-start:.2f} 秒）')
    return result


def run_account(a, action, timeout):
    c = Client(a, timeout)
    if a['mode'] == 'password':
        def login():
            st, data, _ = c.request('POST', '/api/user/login', {'username': a['username'], 'password': a['password']})
            c.check(st, data)
        stage(1, '登录取得本次会话', login)
    before = stage(2, '验证账号并查询余额', c.info)
    who = identity(before, a)
    if who:
        log('官方账号身份：' + who)
    unit = 500000.0
    try:
        st, data, _ = c.request('GET', '/api/status')
        d = c.check(st, data)
        v = float(d.get('quota_per_unit', 0)) if isinstance(d, dict) else 0
        if math.isfinite(v) and v > 0:
            unit = v
        else:
            log('⚠️ 额度单位缺失，采用上游默认 500000 quota/美元')
    except (Failure, TypeError, ValueError):
        log('⚠️ 无法读取额度单位，采用上游默认 500000 quota/美元')
    log('当前余额：' + amount(before.get('quota'), unit) + '；已用额度：' + amount(before.get('used_quota'), unit))
    if action != 'checkin':
        log('只读验证成功，未发送签到请求')
        return 'ok'
    state, gained = stage(3, '执行签到或确认今日已签到', c.sign)
    try:
        after = stage(4, '查询签到后余额', c.info)
        if gained is None and state == 'ok':
            delta = float(after.get('quota')) - float(before.get('quota'))
            gained = delta if delta > 0 else None
        log('签到后余额：' + amount(after.get('quota'), unit))
    except (Failure, ValueError, TypeError):
        log('⚠️ 签到已有明确业务确认；签到后余额查询失败')
    log(('☑️ 今日已签到' if state == 'already' else '✅ 签到成功') + '；奖励：' + amount(gained, unit))
    return state


def notify(summary, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    selected = False
    if switch in TRUE:
        selected = True
    elif switch not in FALSE:
        selectors = re.split(r'[,;\s]+', os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '').strip())
        script = Path(__file__).resolve()
        names = [CATALOG, script.name, str(script), 'output/candidate.py']
        for root in ('/ql/data/scripts', '/ql/scripts'):
            try:
                names.append(str(script.relative_to(root)))
            except ValueError:
                pass
        selected = any(fnmatch.fnmatch(name, selector) for selector in selectors if selector for name in names)
    if dry:
        log('通知：断网预演，仅生成本地脱敏总结，不调用通知模块')
        return 'dry-run'
    if not selected:
        log('通知：未选中或已由全局开关关闭')
        return 'disabled'
    body = f"状态：{summary['status']}；账号总数：{summary['accounts']}；成功：{summary['success']}；失败：{summary['failure']}；跳过：{summary['skipped']}"
    # 子进程隔离通知输出，限时且不改变业务退出码；通知为可选集成，无外部运行依赖。
    code = '''import importlib.util,sys
from pathlib import Path
root,title,body=sys.argv[1:]
if root:
 p=Path(root)/'notify.py'
 spec=importlib.util.spec_from_file_location('ql_notify',p)
 mod=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(mod)
else:
 import notify as mod
mod.send(title,body)
'''
    roots = [None] + [p for p in (os.environ.get('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts') if p]
    for root in roots:
        if root and not (Path(root)/'notify.py').is_file():
            continue
        try:
            r = subprocess.run([sys.executable, '-c', code, root or '', TITLE, body], timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                log('通知：✅ 已发送')
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    for root in roots[1:]:
        path = Path(root)/'sendNotify.js'
        if not path.is_file():
            continue
        try:
            r = subprocess.run(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(path), TITLE, body], timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                log('通知：✅ 已发送')
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('通知：⚠️ 通知模块不可用或发送失败，保留业务退出码')
    return 'unavailable'


def main():
    start = time.monotonic()
    dry = os.environ.get('RELAY_DRY_RUN', '').lower() in TRUE
    lines = [s.strip() for s in os.environ.get('RELAY_ACCOUNTS', '').splitlines() if s.strip()]
    log('='*40 + '\n' + TITLE)
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "正式"}；账号数：{len(lines)}')
    counts = {'accounts': len(lines), 'success': 0, 'failure': 0, 'already': 0, 'skipped': 0}
    config_error = False
    try:
        action = os.environ.get('RELAY_ACTION', 'checkin')
        if action not in ('checkin', 'query', 'verify'):
            raise Failure('RELAY_ACTION 仅允许 checkin/query/verify')
        timeout = number('RELAY_TIMEOUT', 20, 5, 120)
        jitter = number('RELAY_RANDOM_DELAY_MINUTES', 20, 0, 60)
        retries = number('RELAY_RETRY_TIMES', 3, 0, 3)
        interval = number('RELAY_RETRY_INTERVAL_MINUTES', 30, 1, 60)
        if not lines:
            raise Failure('RELAY_ACCOUNTS 不能为空；每行一个账号 JSON 对象')
    except Failure as e:
        log('❌ 配置错误：' + str(e))
        config_error = True
        counts['failure'] = len(lines)
    select = os.environ.get('RELAY_SELECT', '')
    selected = 0
    day = datetime.now().date()
    if not config_error and not dry and action == 'checkin' and jitter:
        delay = random.Random(f'astrbot_plugin_relay_checkin:{day.isoformat()}:8:30').randint(0, jitter)*60
        log(f'阶段 0：调度延迟 {delay} 秒')
        time.sleep(delay)
    if not config_error:
        for i, line in enumerate(lines, 1):
            t = time.monotonic()
            state = 'fail'
            log(f'--- 账号 {i} ---')
            try:
                a = parse_account(line)
                if select and select not in (str(i), a.get('name')):
                    state = 'skipped'
                elif not a.get('enabled', True) or (not select and not a.get('sched', True)):
                    state = 'skipped'
                else:
                    selected += 1
                    if dry:
                        log('阶段 1：✅ 配置检查通过；阶段 2–4：⏭️ 断网预演，不执行登录、查询、签到或通知')
                        log('DRY_RUN_OK')
                        state = 'dry-run'
                    else:
                        for attempt in range(retries + 1):
                            try:
                                state = run_account(a, action, timeout)
                                break
                            except Failure as e:
                                if not e.retry or attempt == retries:
                                    raise
                                log(f'⚠️ 暂时失败，等待 {interval} 分钟后重试 {attempt+1}/{retries}')
                                time.sleep(interval*60)
                                if datetime.now().date() != day:
                                    raise Failure('已跨天，停止本轮重试')
            except Failure as e:
                log('❌ ' + str(e))
            except Exception:
                log('❌ 账号格式或执行异常，详细数据已隐藏')
            counts['skipped' if state == 'skipped' else 'failure' if state == 'fail' else 'success'] += 1
            counts['already'] += int(state == 'already')
            log(f'账号 {i} 统计：总任务 1；成功 {int(state in ("ok", "dry-run"))}；已完成 {int(state == "already")}；跳过 {int(state == "skipped")}；失败 {int(state == "fail")}；耗时 {time.monotonic()-t:.2f} 秒')
    if not config_error and not selected and counts['failure'] == 0:
        log('❌ 没有可执行账号，请检查选择器和 enabled/sched 设置')
        config_error = True
    status = 'configuration-error' if config_error else 'partial-failure' if counts['failure'] and counts['success'] else 'failure' if counts['failure'] else 'dry-run' if dry else 'success'
    code = int(config_error or counts['failure'] > 0)
    summary = dict(counts, status=status, dryRun=dry, exitCode=code)
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        log('通知：⚠️ 通知配置异常，保留业务退出码')
        summary['notification'] = 'unavailable'
    summary['durationSeconds'] = round(time.monotonic()-start, 3)
    log('-'*48)
    log(f'最终状态：{status}；账号统计：{json.dumps(counts, ensure_ascii=False)}；子任务总数：{len(lines)}；总耗时：{summary["durationSeconds"]} 秒')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；通知状态：{summary["notification"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
