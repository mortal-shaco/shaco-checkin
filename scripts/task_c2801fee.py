#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 掘金签到与可选抽奖
# cron: 40 10 * * *
"""独立维护版本；原源码未指定周期，建议每天 08:00 运行。
来源: cy920820/juejin-sign-in-action / signin.py
https://github.com/cy920820/juejin-sign-in-action
上游提交: 21ef8a34eb2d230f3c52c82ee15a55952ec21e55
许可证: MIT（任务提供的 effectiveLicense）；输入源码没有额外版权声明。

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

参数：JJ_COOKIE 必填，每个非空行一个账号，整行是该账号完整 Cookie。
浏览器登录掘金，在开发者工具 Network 中选择 api.juejin.cn 的已登录请求，
复制 Request Headers 的 Cookie 值（不含 Cookie: 前缀）。Cookie 属于凭据。
JJ_LOTTERY 默认 0；设为 1 才在签到成功后抽奖一次，可能消耗积分。
JJ_DRY_RUN=1 完全断网，仅预演和通知预览；不会验证凭据有效性。
SERVER_KEY 可选，兼容原 Server 酱 SendKey；从自己的 Server 酱账户获取。
QINGLONG_NOTIFY=auto|1|0 控制青龙通知；auto 默认通知本脚本。
QINGLONG_NOTIFY_SCRIPTS 如设置则用逗号、分号或空白分隔的选择器筛选；
支持目录相对路径、文件名、文件名通配符、目录编号及 *，空值禁用全部。
QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。通知失败不改变业务退出码。
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
        _ql_notify_identities = ('c2801fee6b1b75bf', 'scripts/task_c2801fee.py', 'task_c2801fee.py', 'task_c2801fee')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
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

TITLE = '掘金签到与可选抽奖'
CATALOG_ID = 'c2801fee6b1b75bf'
BASE = 'https://api.juejin.cn/'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
TIMEOUT = 15
LIMIT = 262144


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把凭据转发到重定向目的地。
        return None


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def log(message):
    print('[{}] {}'.format(time.strftime('%H:%M:%S'), message), flush=True)


def flag(name, default='0'):
    value = os.environ.get(name, default).strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError('{} 必须为 1 或 0（也支持 true/false、yes/no、on/off）'.format(name))
    return value in TRUE


def http_json(url, cookie=None, form=None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    if cookie is not None:
        headers['Cookie'] = cookie
    data = None
    if cookie is not None:
        data = b''  # 保留上游 POST 方法及空请求体。
    if form is not None:
        data = urllib.parse.urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise TaskError('响应超过大小上限')
        result = json.loads(raw.decode('utf-8'))
    except TaskError:
        raise
    except urllib.error.HTTPError:
        raise TaskError('HTTP 请求失败（详情已脱敏）') from None
    except (OSError, ValueError, urllib.error.URLError):
        raise TaskError('网络、超时或响应解析失败（详情已脱敏）') from None
    if not isinstance(result, dict):
        raise TaskError('响应格式不是对象')
    return result


def identity(data, secrets):
    if not isinstance(data, dict):
        return None
    for key in ('nickname', 'user_name', 'username', 'display_name', 'user_id', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 不遮蔽公开昵称或 UID；拒绝凭据回显、控制字符和手机号。
            if (not value or any(secret and secret in value for secret in secrets)
                    or re.search(r'[\x00-\x1f\x7f]|(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', value)
                    or re.search(r'cookie|token|session|device[_-]?id', value, re.I)):
                continue
            return value
    for key in ('user_info', 'user'):
        nested = identity(data.get(key), secrets)
        if nested:
            return nested
    return None


def action(path, cookie, secrets):
    result = http_json(BASE + path, cookie=cookie)
    code = result.get('err_no')
    # 未知/缺失业务码、布尔值和非零业务码一律不当作成功。
    if type(code) is not int or code != 0:
        raise TaskError('业务未确认成功；请检查登录状态、接口或任务状态（不输出原始响应）')
    return identity(result.get('data'), secrets)


def notification_enabled():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch not in TRUE | {'auto'}:
        raise TaskError('QINGLONG_NOTIFY 配置无效')
    selectors = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is None:
        return True
    path = Path(__file__)
    names = {CATALOG_ID, path.name, path.as_posix().lstrip('/')}
    parts = path.parts
    for index in range(len(parts)):
        names.add('/'.join(parts[index:]))
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in re.split(r'[,;\s]+', selectors.strip()) if pattern
               for name in names)


def notify(summary, dry_run, enabled):
    body = '状态：{}；账号总数：{}；成功：{}；失败：{}；预演：{}'.format(
        summary['status'], summary['accounts'], summary['success'], summary['failed'], summary['dryRunAccounts'])
    if dry_run:
        log('通知预览（断网模式，不调用通知模块）：' + body)
        return 'dry-run'
    outcomes = []
    if enabled:
        # 在独立子进程加载青龙助手，限制耗时并隐藏第三方日志/异常。
        helper = '''import importlib, importlib.util, sys
kind, path, title, body = sys.argv[1:]
if kind == 'module':
    mod = importlib.import_module('notify')
else:
    spec = importlib.util.spec_from_file_location('ql_notify', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
mod.send(title, body)
'''
        candidates = [[sys.executable, '-c', helper, 'module', '', TITLE, body]]
        directories = [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
        for directory in directories:
            if not directory:
                continue
            module = Path(directory) / 'notify.py'
            if module.is_file():
                candidates.append([sys.executable, '-c', helper, 'file', str(module), TITLE, body])
        delivered = False
        for command in candidates:
            try:
                proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
                if proc.returncode == 0:
                    delivered = True
                    break
            except (OSError, subprocess.TimeoutExpired):
                # 超时可能已经投递，不重复投递同一通知。
                break
        if not delivered:
            for directory in directories:
                module = Path(directory) / 'sendNotify.js' if directory else None
                if module is None or not module.is_file():
                    continue
                try:
                    command = ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(module), TITLE, body]
                    proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
                    delivered = proc.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    break
                if delivered:
                    break
        outcomes.append('青龙通知' + ('成功' if delivered else '不可用或失败'))
    key = os.environ.get('SERVER_KEY', '').strip()
    if key:
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
                raise TaskError('SendKey 格式不合法')
            result = http_json('https://sctapi.ftqq.com/' + key + '.send', form={'text': TITLE, 'desp': body})
            if type(result.get('code')) is not int or result['code'] != 0:
                raise TaskError('通知未确认成功')
            outcomes.append('Server 酱通知成功')
        except Exception:
            outcomes.append('Server 酱通知失败（详情已脱敏）')
    status = '；'.join(outcomes) if outcomes else '通知已关闭'
    log(status)
    return status


def main():
    started = time.monotonic()
    started_at = now()
    cookies = [line.strip() for line in os.environ.get('JJ_COOKIE', '').splitlines() if line.strip()]
    # 先识别断网意图；任何配置错误仍不能触发网络通知。
    raw_dry = os.environ.get('JJ_DRY_RUN', '0').strip().lower()
    dry_run = raw_dry not in FALSE
    summary = {'task': TITLE, 'mode': 'dry-run' if dry_run else 'live', 'accounts': len(cookies),
               'success': 0, 'failed': 0, 'dryRunAccounts': 0, 'tasks': {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0},
               'status': 'failure', 'startedAt': started_at}
    log('========== ' + TITLE + ' ==========')
    log('开始时间：{}；模式：{}；账号数：{}'.format(started_at, summary['mode'], len(cookies)))
    enabled = True
    exit_code = 1
    try:
        dry_run = flag('JJ_DRY_RUN')
        lottery = flag('JJ_LOTTERY')
        enabled = notification_enabled()
        if not cookies:
            raise TaskError('缺少 JJ_COOKIE：每个非空行填写一个账号完整 Cookie')
        # 记录全部秘密片段，身份输出时避免意外反射。
        secrets = [os.environ.get('SERVER_KEY', '')] + cookies
        for cookie in cookies:
            secrets.extend(part.split('=', 1)[1].strip() for part in cookie.split(';') if '=' in part)
        for index, cookie in enumerate(cookies, 1):
            account_started = time.monotonic()
            stats = {'total': 2, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            signed = False
            for stage, label, path in ((1, '签到', 'growth_api/v1/check_in'), (2, '抽奖', 'growth_api/v1/lottery/draw')):
                tick = time.monotonic()
                log('账号 {} · 阶段 {}/2 · {}'.format(index, stage, label))
                try:
                    if stage == 2 and (not lottery or not signed):
                        stats['skipped'] += 1
                        log('⏭️ {}：{}'.format(label, '未显式启用 JJ_LOTTERY' if not lottery else '签到未成功，停止后续副作用'))
                        continue
                    if not cookie.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in cookie) or '=' not in cookie:
                        raise TaskError('Cookie 格式无效，应提供请求头中的完整 Cookie 值')
                    if dry_run:
                        stats['skipped'] += 1
                        log('⏭️ DRY_RUN_OK：已检查配置，将执行{}，未发出请求'.format(label))
                    else:
                        name = action(path, cookie, secrets)
                        stats['success'] += 1
                        log('✅ {}业务码 err_no=0{}'.format(label, '；账号身份：' + name if name else ''))
                    if stage == 1:
                        signed = True
                except TaskError as error:
                    stats['failed'] += 1
                    log('❌ {}：{}'.format(label, error))
                except Exception:
                    stats['failed'] += 1
                    log('❌ {}：执行异常（详情已脱敏）'.format(label))
                finally:
                    log('账号 {} · 阶段 {} 耗时 {:.2f} 秒'.format(index, stage, time.monotonic() - tick))
            for key in stats:
                summary['tasks'][key] += stats[key]
            if stats['failed']:
                summary['failed'] += 1
            elif dry_run:
                summary['dryRunAccounts'] += 1
            else:
                summary['success'] += 1
            log('账号 {} 统计：总任务 {total}；成功 {success}；已完成 {alreadyComplete}；跳过 {skipped}；失败 {failed}；耗时 {elapsed:.2f} 秒'.format(index, elapsed=time.monotonic() - account_started, **stats))
        exit_code = 1 if summary['failed'] else 0
        summary['status'] = ('partial-failure' if summary['success'] else 'failure') if exit_code else ('dry-run' if dry_run else 'success')
    except TaskError as error:
        summary['status'] = 'configuration-error'
        log('❌ 配置错误：' + str(error))
    except Exception:
        summary['status'] = 'failure'
        log('❌ 执行异常（详情已脱敏）')
    try:
        summary['notification'] = notify(summary, dry_run, enabled)
    except Exception:
        summary['notification'] = '通知失败（详情已脱敏）'
        log(summary['notification'])
    summary['finishedAt'] = now()
    summary['elapsedSeconds'] = round(time.monotonic() - started, 2)
    summary['exitCode'] = exit_code
    log('----------------------------------------')
    log('账号统计：总数 {accounts}；成功 {success}；失败 {failed}；预演 {dryRunAccounts}'.format(**summary))
    log('子任务统计：' + json.dumps(summary['tasks'], ensure_ascii=False))
    log('通知状态：' + summary['notification'])
    log('完成时间：{}；总耗时：{} 秒；最终状态：{}'.format(summary['finishedAt'], summary['elapsedSeconds'], summary['status']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
