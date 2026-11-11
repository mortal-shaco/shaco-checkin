#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: BreezeBlue 每日积分签到
# cron: 2 11 * * *
# SPDX-License-Identifier: MIT
"""BreezeBlue 每日积分签到（青龙独立维护版，MIT）。
来源：MeowAndy/auto-breezeblue，bb_checkin.py、bb_web.py。
上游文件未附独立版权声明；保留原署名与 MIT 许可。

BB_ACCOUNTS：每个非空行一个账号；支持原始 Cookie、Cookie: 请求头、
单行 Copy as cURL、邮箱|密码（仅按第一个 | 分割），或单行 JSON 对象：
cookie、email、password、enabled、reward_tier。JSON 可同时提供 Cookie
和邮箱密码，用于会话过期后仅重登一次；密码只在内存使用。
获取 Cookie：浏览器登录 https://breezeblue.ai → 开发者工具 Network →
刷新 → 本站 /api/me 请求 → Request Headers → 复制 Cookie。
邮箱密码使用已注册的邮箱账号；Google 注册账号请用 Cookie。
遇到人机验证请在浏览器完成后改用 Cookie，不注册账号、不伪造验证码。
可显式设置 BB_CONFIG 读取旧版 config.json（只读、不迁移、不回写）；
BB_ACCOUNTS 存在时优先，格式错误不会回退。run 默认签到；test 只查
登录态和余额；list/status 只显示脱敏配置。BB_ACTION 与命令行同名。
青龙采用北京时间 cron 5 8 * * *；UTC 面板改为 5 0 * * *。
不安装系统任务、不启动后台进程、不存储凭据；由青龙负责调度。
BB_DRY_RUN=1 完全断网演练；通知仅预览，不调用可能联网的通知模块。
"""
from __future__ import annotations
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
        _ql_notify_identities = ('42f0a79c5da31311', 'scripts/bb_checkin.py', 'bb_checkin.py', 'bb_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid
import http.cookiejar
import urllib.error
import urllib.request
from datetime import datetime

TITLE = 'BreezeBlue 每日积分签到'
BASE = 'https://breezeblue.ai'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def cookie_value(value):
    if not isinstance(value, str) or not value.strip():
        raise TaskError('Cookie 不能为空')
    value = value.strip()
    m = re.search(r'(?:-b|--cookie)\s+[\'\"]([^\'\"]+)[\'\"]', value)
    if not m:
        m = re.search(r'[\'\"]?cookie[\'\"]?\s*:\s*[\'\"]?([^\r\n\'\"]+)', value, re.I)
    if m:
        value = m.group(1).strip()
    if '\r' in value or '\n' in value or '=' not in value:
        raise TaskError('Cookie 格式错误，请复制请求头的完整值')
    return value


def normalize(account):
    if not isinstance(account, dict):
        raise TaskError('账号必须是对象')
    a = {}
    for k in ('email', 'password', 'cookie', 'reward_tier'):
        v = account.get(k, '')
        if not isinstance(v, str):
            raise TaskError('账号凭据字段必须是文本')
        a[k] = v
    a['email'] = a['email'].strip()
    if not isinstance(account.get('enabled', True), bool):
        raise TaskError('enabled 必须为布尔值')
    a['enabled'] = account.get('enabled', True)
    if a['cookie']:
        a['cookie'] = cookie_value(a['cookie'])
    if bool(a['email']) != bool(a['password']):
        raise TaskError('邮箱与密码必须成对提供')
    if not a['cookie'] and not a['email']:
        raise TaskError('缺少 Cookie 或邮箱密码')
    if a['reward_tier'] not in ('', 'standard', 'discord'):
        raise TaskError('reward_tier 仅支持 standard 或 discord')
    return a


def load_accounts():
    if 'BB_ACCOUNTS' in os.environ:
        rows = [s.strip() for s in os.environ['BB_ACCOUNTS'].splitlines() if s.strip()]
        def parse(row):
            if row.startswith('{'):
                return json.loads(row)
            if '|' in row and '@' in row.split('|', 1)[0] and '=' not in row.split('|', 1)[0]:
                email, password = row.split('|', 1)
                return {'email': email, 'password': password}
            return {'cookie': row}
    elif os.environ.get('BB_CONFIG'):
        try:
            cfg = json.loads(Path(os.environ['BB_CONFIG']).read_text(encoding='utf-8'))
            if not isinstance(cfg, dict):
                raise ValueError
            rows = cfg.get('accounts', [cfg])
            if not isinstance(rows, list):
                raise ValueError
        except (OSError, ValueError):
            raise TaskError('BB_CONFIG 无法读取或配置格式错误') from None
        parse = lambda row: row
    else:
        raise TaskError('请设置 BB_ACCOUNTS，每个非空行一个账号')
    if not rows:
        raise TaskError('未配置账号')
    accounts = []
    for row in rows:
        try:
            accounts.append(normalize(parse(row)))
        except (TaskError, ValueError, TypeError):
            accounts.append({'invalid': True})
    return accounts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 防止凭据随重定向发送到其它地址


class Client:
    def __init__(self, account, dry):
        self.account = account
        self.dry = dry
        self.cookie = account['cookie']
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))
        self.relogged = False

    def request(self, method, path, payload=None):
        if self.dry:
            raise TaskError('断网预演禁止 HTTP 请求')
        headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0',
                   'Origin': BASE, 'Referer': BASE + '/app/home',
                   'x-breeze-client-request-id': 'cfr_' + uuid.uuid4().hex}
        if self.cookie:
            headers['Cookie'] = self.cookie
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(BASE + '/api' + path, data=data, headers=headers, method=method)
        try:
            try:
                response = self.opener.open(req, timeout=25)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(262145)
        except (OSError, urllib.error.URLError, TimeoutError):
            raise TaskError('网络请求失败或超时，未输出响应内容') from None
        if len(raw) > 262144:
            raise TaskError('响应超过大小限制')
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError(f'HTTP {status}，响应不是有效 JSON') from None
        if not isinstance(body, dict):
            raise TaskError(f'HTTP {status}，响应结构不符')
        return status, body

    def login(self):
        a = self.account
        if not a['email'] or not a['password']:
            raise TaskError('登录态失效，请重新获取 Cookie')
        self.cookie = ''
        self.jar.clear()
        status, body = self.request('POST', '/auth/email/continue', {
            'email': a['email'], 'password': a['password'], 'locale': 'zh', 'next_path': '/app/home'})
        if status != 200 or body.get('ok') is False or not any(self.jar):
            raise TaskError(f'登录未通过（HTTP {status}），请在浏览器确认账号及人机验证')
        log('登录接口成功，临时会话仅保留在内存')

    def authenticated(self, method, path, payload=None):
        if not self.cookie and not any(self.jar):
            self.login()
            self.relogged = True
        status, body = self.request(method, path, payload)
        if (status == 401 or body.get('code') in ('AUTH_REQUIRED', 'UNAUTHORIZED')) and not self.relogged:
            self.relogged = True
            log('会话失效，使用已配置的邮箱密码重登一次')
            self.login()
            status, body = self.request(method, path, payload)
        if body.get('ok') is False or body.get('success') is False:
            raise TaskError(f'接口明确报告失败（HTTP {status}）')
        return status, body


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def identity(body):
    # 只展示官方明确的非凭据身份；不使用邮箱、手机号或原始响应兜底。
    for key in ('display_name', 'nickname', 'username', 'public_uid'):
        v = body.get(key)
        if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v):
            text = str(v)
            if '@' in text or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
                continue
            return ''.join(c for c in text if c.isprintable())
    return None


def run_account(a, index, action, dry):
    counts = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
    started = time.monotonic()
    def stage(title, operation):
        counts['total'] += 1
        t = time.monotonic()
        log(f'账号 {index} 阶段 {counts["total"]}：{title}')
        try:
            result, message = operation()
            counts[result] += 1
            log(f'账号 {index}：{message}；耗时 {time.monotonic()-t:.2f} 秒')
            return True
        except Exception as e:
            counts['failure'] += 1
            message = str(e) if isinstance(e, TaskError) else '执行异常，已隐藏异常详情'
            log(f'账号 {index}：❌ {message}；耗时 {time.monotonic()-t:.2f} 秒')
            return False
    if a.get('invalid'):
        def invalid():
            raise TaskError('账号格式错误，请检查本账号配置')
        stage('配置检查', invalid)
    elif not a['enabled']:
        stage('配置检查', lambda: ('skipped', '⏭️ 账号已停用'))
    elif dry:
        for title in ('配置检查', '身份及登录态验证', '每日积分领取' if action == 'run' else '只读模式', '积分余额查询'):
            stage(title, lambda: ('skipped', 'DRY_RUN_OK：配置有效，未发送请求、未修改状态'))
    elif action in ('list', 'status'):
        stage('配置概况', lambda: ('success', f'Cookie：{"已配置" if a["cookie"] else "未配置"}；邮箱密码：{"已配置" if a["email"] else "未配置"}'))
    else:
        client = Client(a, dry)
        def me():
            status, body = client.authenticated('GET', '/me')
            if status != 200 or not any(body.get(k) for k in ('id', 'uid', 'email', 'display_name', 'username', 'nickname', 'public_uid')):
                raise TaskError(f'登录态验证未通过（HTTP {status}）')
            who = identity(body)
            return 'success', '✅ 登录态有效' + (f'；官方身份：{who}' if who else '')
        def claim():
            payload = {'reward_tier': a['reward_tier']} if a['reward_tier'] else None
            status, body = client.authenticated('POST', '/credits/daily-claim', payload)
            if status in (200, 409) and (body.get('already_claimed') is True or body.get('claimed_today') is True):
                return 'alreadyComplete', '☑️ 今天已签到，无需重复'
            if status == 200 and body.get('claimed') is True:
                msg = '✅ 签到成功'
                for k, label in (('credits_issued', '领取积分'), ('balance', '余额')):
                    if number(body.get(k)):
                        msg += f'；{label} {body[k]:g}'
                return 'success', msg
            raise TaskError(f'未得到明确领取成功或已签到凭据（HTTP {status}），不自动重试')
        def balance():
            status, body = client.authenticated('GET', '/credits/summary')
            if status != 200 or not number(body.get('balance')):
                raise TaskError(f'积分余额查询未通过（HTTP {status}）')
            msg = f'✅ 余额 {body["balance"]:g}'
            flag = body.get('daily_claim_claimed_today')
            if isinstance(flag, bool):
                msg += f'；今日已签：{"是" if flag else "否"}'
            tier = body.get('daily_claim_reward_tier')
            if tier in ('standard', 'discord'):
                msg += f'；档位 {tier}'
            reset = body.get('daily_claim_next_reset_at')
            if isinstance(reset, str):
                try:
                    msg += '；下次重置 ' + datetime.fromisoformat(reset.replace('Z', '+00:00')).isoformat()
                except ValueError:
                    pass
            return 'success', msg
        if stage('身份及登录态验证', me):
            if action == 'run':
                stage('每日积分领取', claim)
            stage('积分余额查询', balance)
    counts['seconds'] = round(time.monotonic() - started, 3)
    log(f'账号 {index} 统计：总任务 {counts["total"]}，成功 {counts["success"]}，已完成 {counts["alreadyComplete"]}，跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {counts["seconds"]} 秒')
    return {'account': index, 'ok': counts['failure'] == 0, 'kind': 'error' if counts['failure'] else ('dry-run' if dry else 'completed'), 'statistics': counts}


def notification_selected():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if 'QINGLONG_NOTIFY_SCRIPTS' not in os.environ:
        return False  # listed-only，本脚本没有默认入选名单
    selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
    paths = ('42f0a79c5da31311', 'fcdf36a7475913e5', Path(__file__).name, 'checkin/' + Path(__file__).name)
    return any(fnmatch.fnmatch(p, s) for p in paths for s in selectors if s)


def notify(body, dry):
    if dry:
        log('通知预览（断网预演不调用通知模块）：' + body)
        return 'dry-run-preview'
    if not notification_selected():
        log('通知：未入选或全局开关关闭')
        return 'disabled'
    # 通知在独立 Python 进程执行，限制耗时并隐藏通知器的全部输出。
    import subprocess
    helper = """
import importlib, importlib.util, os
from pathlib import Path
try:
    module = importlib.import_module('notify')
except ImportError:
    module = None
    for root in (os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts'):
        path = Path(root) / 'notify.py'
        if root and path.is_file():
            spec = importlib.util.spec_from_file_location('ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
if module is None or not callable(getattr(module, 'send', None)):
    raise RuntimeError('通知不可用')
module.send(os.environ['BB_NOTICE_TITLE'], os.environ['BB_NOTICE_BODY'])
"""
    try:
        env = dict(os.environ, BB_NOTICE_TITLE=TITLE, BB_NOTICE_BODY=body)
        result = subprocess.run([sys.executable, '-c', helper], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
        if result.returncode:
            raise RuntimeError
        log('通知：已调用青龙 notify.send')
        return 'sent'
    except Exception:
        log('通知：不可用或发送失败，保留业务退出码')
        return 'unavailable-or-failed'



def main():
    start = time.monotonic()
    dry = os.environ.get('BB_DRY_RUN', '').lower() in TRUE
    action = sys.argv[1] if len(sys.argv) == 2 else os.environ.get('BB_ACTION', 'run')
    log('=' * 48)
    log(TITLE + f'；开始时间 {datetime.now().isoformat(timespec="seconds")}')
    log(f'运行模式：{"断网预演" if dry else "正式"}；动作：' + (action if action in ('run', 'test', 'list', 'status') else '无效'))
    results, accounts, config_error = [], [], False
    try:
        if len(sys.argv) > 2 or action not in ('run', 'test', 'list', 'status'):
            raise TaskError('动作仅支持 run/test/list/status；计划任务请在青龙管理')
        accounts = load_accounts()
        log(f'账号数量：{len(accounts)}')
        for i, a in enumerate(accounts, 1):
            results.append(run_account(a, i, action, dry))
    except TaskError as error:
        config_error = True
        log(f'账号数量：{len(accounts)}；❌ 配置错误：{error}')
    if accounts and not any(a.get('enabled', True) for a in accounts):
        config_error = True
        log('❌ 没有启用的账号，无法确认业务成功')
    failed = sum(not r['ok'] for r in results)
    success = sum(r['ok'] and r['statistics']['success'] + r['statistics']['alreadyComplete'] > 0 for r in results)
    skipped = len(results) - failed - success
    code = 1 if config_error or failed else 0
    status = 'configuration-error' if config_error else ('partial-failure' if failed and success else 'failure') if failed else 'dry-run' if dry else 'success'
    summary = {'ok': code == 0, 'kind': 'summary', 'status': status, 'dryRun': dry, 'accounts': len(accounts),
               'success': success, 'failure': failed, 'skipped': skipped, 'results': results}
    counts = {k: sum(r['statistics'][k] for r in results) for k in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    log('-' * 48)
    body = f'状态 {status}；账号总数 {len(accounts)}，成功 {success}，失败 {failed}，跳过/预演 {skipped}；配置错误 {int(config_error)}'
    log(body)
    log('子任务统计：' + json.dumps(counts, ensure_ascii=False))
    summary['notification'] = notify(body, dry)
    summary['seconds'] = round(time.monotonic() - start, 3)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log(f'完成时间 {summary["finishedAt"]}；总耗时 {summary["seconds"]} 秒；最终状态 {status}；退出码 {code}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
