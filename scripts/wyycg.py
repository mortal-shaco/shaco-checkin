#!/usr/bin/env python3
# name: 网易云游戏自动签到
# cron: 42 1 * * *
# SPDX-License-Identifier: Apache-2.0
# 原作者：GamerNoTitle https://bili33.top
# 来源：https://github.com/GamerNoTitle/wyycg-autocheckin
# 原始 main.py 与 qinglong/qinglong.py；保留 Apache-2.0 授权及作者署名。
# 关联来源：OreosLab/checkinpanel 的 ck_game163.py（MIT，提交 911402e4b2e559ffd62c4949a971ddd6834edd7d）；
# 关联来源：Riku1998/cg163-autocheckin 的 cg163-autocheckin.py（Apache-2.0，提交 d509ef623787ef39cef475a4b76405145e50997c）。
"""网易云游戏每日签到，Python 3 标准库独立运行。
WYYCG_ACCOUNTS：登录 https://cg.163.com 后在浏览器开发者工具的网络面板，
查找 n.cg.163.com 请求，复制 Authorization 请求头完整值（不是 Cookie）。
每个非空行一个账号；兼容 CG163_ACCOUNTS、GAME163_AUTHORIZATION、
GAME163 旧 JSON 账号数组、wyycg_cookies 或第一个位置参数。
可选位置参数依次是 Telegram 接收者、机器人令牌、ServerChan 密钥、QQ 密钥、
PushPlus 令牌；也可使用契约中的对应环境变量。PPKEY 保留旧 PushPlus 推送。
本项目规范计划每日 01:42；旧 cg163、game163 计划分别为每日 01:34、01:21，可改为调用此脚本。
WYYCG_DRY_RUN=1（兼容 CG163_DRY_RUN、GAME163_DRY_RUN）完全断网，
只检查配置与模拟流程，包括不调用通知模块。
签到可能领取云游戏时长；不执行消费、发帖或修改账户的其他动作。

关联实现 OreosLab/checkinpanel 的 MIT 授权声明：
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
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('a414f4add19cb6a5', 'scripts/wyycg.py', 'wyycg.py', 'wyycg', '97b71fc6fc5c5c72', 'scripts/cg163_autocheckin.py', 'cg163_autocheckin.py', 'cg163_autocheckin', '86bf0d1d9f07edf8', 'scripts/ck_game163.py', 'ck_game163.py', 'ck_game163')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '网易云游戏自动签到'
BASE = 'https://n.cg.163.com/api/v2/'
FALSE_VALUES = {'0', 'false', 'no', 'off'}
SUCCESS_TEXT = {'签到成功', '今日签到成功', '今日已签到', '今天已签到', '已签到', '今日已签过'}
ALREADY_TEXT = {'今日已签到', '今天已签到', '已签到', '今日已签过'}
NOTIFICATION_IDENTITIES = (
    'a414f4add19cb6a5', 'scripts/wyycg.py', 'wyycg.py', 'wyycg',
    '97b71fc6fc5c5c72', 'scripts/cg163_autocheckin.py',
    'cg163_autocheckin.py', 'cg163_autocheckin',
    '86bf0d1d9f07edf8', 'scripts/ck_game163.py',
    'ck_game163.py', 'ck_game163',
)


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in FALSE_VALUES | {''}


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向重定向目标转发 Authorization 或推送凭据。
        return None


def http_json(url, method='GET', headers=None, body=None, allow_text=False):
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(262145)
            if len(raw) > 262144:
                raise TaskError('响应超过大小限制')
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP {exc.code}，请检查凭据或服务状态') from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise TaskError('网络请求失败或超时') from None
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        if allow_text:
            try:
                # game163 旧接口契约允许极少数明确的纯文本签到结果。
                return raw.decode('utf-8', errors='strict')
            except UnicodeError:
                pass
        raise TaskError('响应不是有效 JSON，无法确认业务结果') from None


def business_result(payload, profile='standard'):
    """分别保持三版的明确成功契约；共享旧变量取可核验判定的并集。"""
    if isinstance(payload, dict):
        for key in ('msg', 'message', 'detail'):
            message = payload.get(key)
            if isinstance(message, str) and any(
                    marker in message.lower() for marker in
                    ('失败', '错误', '未登录', '失效', '拒绝', 'failed', 'failure', 'error', 'invalid', 'denied')):
                return False, False
    if profile == 'standard':
        if payload is True:
            return True, False
        if not isinstance(payload, dict):
            return False, False
        if payload.get('success') is False or payload.get('ok') is False or payload.get('error'):
            return False, False
        if 'code' in payload and (
                isinstance(payload['code'], bool) or payload['code'] not in (0, 200, '0', '200')):
            return False, False
        return payload.get('success') is True or payload.get('ok') is True, False
    if profile in ('cg163', 'shared'):
        if not isinstance(payload, dict):
            return False, False
        if (payload.get('success') is False or payload.get('ok') is False or
                payload.get('error') not in (None, False, '', 0)):
            return False, False
        for key in ('code', 'statusCode'):
            if key in payload:
                value = payload[key]
                if isinstance(value, bool) or value not in (0, 200, '0', '200'):
                    return False, False
        code_success = any(key in payload for key in ('code', 'statusCode'))
        success = (payload.get('success') is True or
                   (profile == 'shared' and payload.get('ok') is True) or
                   code_success)
        return success, False
    if profile != 'game163':
        return False, False
    if isinstance(payload, str):
        message = payload.strip().rstrip('。！!.')
        return message in SUCCESS_TEXT, message in ALREADY_TEXT
    if not isinstance(payload, dict):
        return False, False
    if (payload.get('success') is False or payload.get('ok') is False or
            payload.get('error') not in (None, False, '', 0)):
        return False, False
    for key in ('code', 'status', 'retcode'):
        value = payload.get(key)
        if value is False:
            return False, False
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value not in (0, 200):
            return False, False
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ('error', 'failed', 'failure'):
                return False, False
            if normalized.lstrip('-').isdigit() and normalized not in ('0', '200'):
                return False, False
    message = next((payload[key].strip().rstrip('。！!.')
                    for key in ('msg', 'message', 'detail')
                    if isinstance(payload.get(key), str)), '')
    return message in SUCCESS_TEXT, message in ALREADY_TEXT


def confirmed(payload):
    return business_result(payload)[0]


def load_accounts():
    """Preserve each old credential input without exposing it in diagnostics."""
    sources = (
        ('WYYCG_ACCOUNTS', 'standard'),
        ('CG163_ACCOUNTS', 'cg163'),
        ('GAME163_AUTHORIZATION', 'game163'),
        ('GAME163', 'game163'),
        ('wyycg_cookies', 'shared'),
    )
    for name, profile in sources:
        raw = os.getenv(name, '')
        if not raw.strip():
            continue
        if name == 'GAME163' and raw.lstrip().startswith('['):
            try:
                items = json.loads(raw)
            except (ValueError, UnicodeError):
                raise TaskError('GAME163 旧账号数组不是有效 JSON') from None
            if not isinstance(items, list) or not items:
                raise TaskError('GAME163 旧账号数组必须非空')
            return [item.get('authorization') if isinstance(item, dict) else None
                    for item in items], profile
        return [line.strip() for line in raw.splitlines() if line.strip()], profile
    raw = sys.argv[1] if len(sys.argv) > 1 else ''
    return [line.strip() for line in raw.splitlines() if line.strip()], 'standard'


def notification_enabled():
    switch = os.getenv('QINGLONG_NOTIFY')
    if switch is not None:
        return switch.strip().lower() not in FALSE_VALUES | {''}
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is None:
        return True
    entries = [item.lower() for item in re.split(r'[,;\s]+', selectors.strip()) if item]
    return any(fnmatch.fnmatch(identity, selector)
               for selector in entries for identity in NOTIFICATION_IDENTITIES)


def identity(payload, secrets):
    if not isinstance(payload, dict):
        return ''
    nodes = [payload]
    for key in ('data', 'user', 'account', 'profile'):
        if isinstance(payload.get(key), dict):
            nodes.append(payload[key])
    for node in list(nodes):
        for key in ('user', 'account', 'profile'):
            if isinstance(node.get(key), dict):
                nodes.append(node[key])
    for node in nodes:
        for key in ('nickname', 'username', 'displayName', 'publicUid', 'uid'):
            value = node.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            # 官方非敏感身份原样显示；疑似手机号或含凭据内容禁止输出。
            if (value and len(value) <= 200
                    and not any(secret and secret in value for secret in secrets)
                    and not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value)
                    and not re.search(r'(?i)(bearer\s|token\s*[=:]|cookie\s*[=:]|session\s*[=:])', value)):
                if not any(ord(char) < 32 for char in value):
                    return value
    return ''


def account_task(number, credential, dry, secrets, profile):
    actions = (('每日签到', 'sign-today', 'POST'),) if profile == 'game163' else (
        ('验证凭据', 'client-settings/@current', 'GET'),
        ('每日签到', 'sign-today', 'POST'),
    )
    stats = dict(total=len(actions), success=0, alreadyComplete=0, skipped=0, failed=0)
    began = time.monotonic()
    headers = {'Authorization': credential, 'Accept': 'application/json, text/plain, */*',
               'Origin': 'https://cg.163.com', 'Referer': 'https://cg.163.com/',
               'User-Agent': ('Mozilla/5.0 (Linux; Android 10; Redmi K30 Build/QKQ1.190825.002; wv) '
                              'AppleWebKit/537.36 Chrome/85.0.4183.127 Mobile Safari/537.36')
               if profile == 'game163' else 'Mozilla/5.0', 'X-Platform': '0'}
    failure = False
    for stage, (label, path, method) in enumerate(actions, 1):
        started = time.monotonic()
        log(f'账号 {number} · 阶段 {stage}/{len(actions)} · {label} 开始')
        if failure:
            stats['skipped'] += 1
            log(f'⏭️ 账号 {number} · {label} 跳过：前序验证失败；耗时 0.00 秒')
            continue
        try:
            if (not isinstance(credential, str) or not credential or
                    any(not 32 <= ord(c) <= 126 for c in credential)):
                raise TaskError('凭据含非法字符或账号格式无效')
            if dry:
                stats['skipped'] += 1
                log(f'⏭️ 账号 {number} · {label}：断网预演，未发送请求；耗时 {time.monotonic()-started:.2f} 秒')
                continue
            payload = http_json(BASE + path, method, headers,
                                b'' if method == 'POST' else None,
                                allow_text=method == 'POST' and profile == 'game163')
            if method == 'GET':
                # GET 200 且为无错误的配置 JSON，仅验证可访问性，不代表签到成功。
                if not isinstance(payload, dict) or not payload or payload.get('error') or payload.get('success') is False or payload.get('ok') is False:
                    raise TaskError('账户配置响应异常')
                if 'code' in payload and payload['code'] not in (0, 200, '0', '200'):
                    raise TaskError('账户配置包含业务错误码')
                if profile == 'cg163' and not business_result(payload, profile)[0]:
                    raise TaskError('账户配置缺少明确业务成功标志')
            else:
                success, already = business_result(payload, profile)
                if not success:
                    raise TaskError('未收到明确业务成功标志，签到结果待核验')
            name = identity(payload, secrets)
            if name:
                log(f'账号 {number} · 官方身份：{name}')
            if method == 'POST' and already:
                stats['alreadyComplete'] += 1
                log(f'☑️ 账号 {number} · {label}已完成；耗时 {time.monotonic()-started:.2f} 秒')
            else:
                stats['success'] += 1
                log(f'✅ 账号 {number} · {label}成功；耗时 {time.monotonic()-started:.2f} 秒')
        except TaskError as exc:
            stats['failed'] += 1
            failure = True
            log(f'❌ 账号 {number} · {label}失败：{exc}；耗时 {time.monotonic()-started:.2f} 秒')
        except Exception:
            stats['failed'] += 1
            failure = True
            log(f'❌ 账号 {number} · {label}处理异常；耗时 {time.monotonic()-started:.2f} 秒')
    stats.update(account=number, status='failure' if failure else ('dry-run' if dry else 'success'), seconds=round(time.monotonic()-began, 2))
    log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒')
    return stats


def qinglong_notify(body):
    try:
        module = importlib.import_module('notify')
        if callable(getattr(module, 'send', None)):
            module.send(TITLE, body)
            return True
    except Exception:
        pass
    directories = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for directory in directories:
        if not directory:
            continue
        path = Path(directory) / 'notify.py'
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location('_qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(TITLE, body)
            return True
        except Exception:
            continue
    return False


def optional_pushes(settings, body):
    receiver, telegram, serverchan, qq, pushplus = settings
    requests = []
    if receiver and telegram:
        requests.append(('Telegram', f'https://api.telegram.org/bot{urllib.parse.quote(telegram, safe="")}/sendMessage', {'chat_id': receiver, 'text': body}, False))
    if serverchan:
        requests.append(('ServerChan', f'https://sctapi.ftqq.com/{urllib.parse.quote(serverchan, safe="")}.send', {'title': TITLE, 'desp': body}, False))
    if qq:
        requests.append(('QQ', f'https://push.xuthus.cc/send/{urllib.parse.quote(qq, safe="")}', {'c': TITLE + '\n' + body}, False))
    if pushplus:
        requests.append(('PushPlus', 'https://pushplus.hxtrip.com/send', {'token': pushplus, 'title': TITLE, 'content': body, 'template': 'txt'}, False))
    old_pushplus = os.getenv('PPKEY', '').strip()
    if old_pushplus and old_pushplus != pushplus:
        requests.append(('PushPlus 兼容', 'https://www.pushplus.plus/send',
                         {'token': old_pushplus, 'title': TITLE, 'content': body, 'template': 'txt'}, True))
    for name, url, data, json_body in requests:
        try:
            if json_body:
                headers = {'Content-Type': 'application/json'}
                payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
            else:
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                payload = urllib.parse.urlencode(data).encode()
            result = http_json(url, 'POST', headers, payload)
            ok = confirmed(result) or (isinstance(result, dict) and result.get('code') in (0, 200) and result.get('success') is not False)
            log(f'{name} 推送：' + ('已确认' if ok else '未确认投递'))
        except Exception:
            log(f'⚠️ {name} 推送不可用；业务退出码保持不变')


def main():
    started = time.monotonic()
    account_error = None
    try:
        accounts, profile = load_accounts()
    except TaskError as exc:
        accounts, profile, account_error = [], 'standard', str(exc)
    dry = any(enabled(name) for name in ('WYYCG_DRY_RUN', 'CG163_DRY_RUN', 'GAME163_DRY_RUN'))
    names = ['WYYCG_TELEGRAM_ID', 'WYYCG_TELEGRAM_TOKEN', 'WYYCG_SERVERCHAN_KEY', 'WYYCG_QQ_KEY', 'WYYCG_PUSHPLUS_TOKEN']
    settings = [os.getenv(name) or (sys.argv[i+2] if len(sys.argv) > i+2 else '') for i, name in enumerate(names)]
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "真实执行"}；账号总数：{len(accounts)}')
    results = []
    if account_error:
        log(f'❌ 配置错误：{account_error}')
    elif not accounts:
        log('❌ 配置错误：请设置 WYYCG_ACCOUNTS 或兼容凭据变量，每个非空行一个 Authorization 值')
    for number, credential in enumerate(accounts, 1):
        results.append(account_task(number, credential, dry,
                                    accounts + settings + [os.getenv('PPKEY', '')], profile))
    failed = sum(r['status'] == 'failure' for r in results)
    success = sum(r['status'] == 'success' for r in results)
    exit_code = 1 if failed or not accounts else 0
    status = 'configuration-error' if not accounts else ('partial-failure' if failed and failed < len(accounts) else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(accounts)}，成功数：{success}，失败数：{failed}，预演数：{sum(r["status"] == "dry-run" for r in results)}；最终状态：{status}'
    if not notification_enabled():
        notification = '已关闭'
    elif dry:
        notification = '断网预演：模拟发送脱敏通知'
    else:
        notification = '已发送' if qinglong_notify(body) else '通知不可用，保留业务退出码'
        optional_pushes(settings, body)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log(f'子任务统计：总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'通知状态：{notification}')
    log(f'完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；总耗时：{time.monotonic()-started:.2f} 秒；最终状态：{status}')
    summary = dict(task=TITLE, mode='dry-run' if dry else 'live', status=status, accountCount=len(accounts), successCount=success, failureCount=failed, accounts=results, stages=totals, notification=notification, exitCode=exit_code)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
