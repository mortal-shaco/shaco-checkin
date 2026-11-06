#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 菜鸟图库图币签到
# cron: 27 10 * * *
# 来源 Jim6699/Python_scripts，菜鸟图库图币签到/cainiao.py
# 上游提交 3b17c42aac3604cc842c6c94821603699f0bd071，按 MIT 许可维护。
# MIT License
# Copyright (c) Jim6699
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
"""菜鸟图库每日图币签到，Python 3.9+，仅使用标准库。

CAINIAO_COOKIE 为必填项，每个非空行填一个账号的完整 Cookie。
在 https://www.sucai999.com 登录自己的账号，在浏览器开发者工具的网络
面板查看本站已登录请求的请求头，复制 Cookie 的值。请勿复制 Cookie: 前缀，
不要分享凭据。Cookie 可能过期，失败后应重新登录获取。
CAINIAO_ACCOUNT_NAMES 可选，每行一个本地标签，与账号顺序对应。
CAINIAO_DRY_RUN=1 完全断网预演，含通知预演，不代表实际签到成功。
PUSHPLUS_TOKEN 可选，从 PushPlus 个人中心取得，仅用于 HTTPS 脱敏汇总推送。
QINGLONG_NOTIFY 控制通知，auto 默认仅选择列表匹配时启用，1 强制启用，
0 关闭。QINGLONG_NOTIFY_SCRIPTS 支持目录相对路径、文件名、通配符和目录编号，
使用逗号、分号或空白分隔，设为空关闭 auto 模式通知。
QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
上游无定时信息，维护版建议每天 09:00 执行一次，采用青龙本地时区。
签到沿用上游 HTTPS GET。只认可明确的中文签到成功或已签到 JSON 消息，
未识别响应失败闭合，不打印原始响应，不自动重试有副作用的签到。
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
        _ql_notify_identities = ('1abfc0b939e55837', 'scripts/cainiao.py', 'cainiao.py', 'cainiao')
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
import subprocess
import sys
import time
from datetime import datetime
from urllib import error, request

TITLE = '菜鸟图库图币签到'
CATALOG_ID = '1abfc0b939e55837'
SIGN_URL = 'https://www.sucai999.com/default/qiandao/qd'
TRUE_VALUES = {'1', 'true', 'yes', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'off'}
SECRETS = []


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def safe_identity(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value)
    if any(secret and secret in text for secret in SECRETS):
        return None
    if re.search(r'1[3-9]\d{9}|(?:cookie|token|session|device|authorization)\s*[:=]', text, re.I):
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return None
    return text


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 防止 Cookie 随重定向发送到其他域名，也避免登录页被当作成功。
        return None


def http_json(url, headers=None, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=data, headers=headers or {},
                          method='GET' if data is None else 'POST')
    opener = request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=15) as response:
            if response.status != 200:
                raise ValueError('HTTP 状态异常')
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError('响应超过大小限制')
            result = json.loads(body.decode('utf-8-sig'))
    except error.HTTPError as exc:
        raise ValueError(f'HTTP 状态异常（{exc.code}）') from None
    except (error.URLError, TimeoutError, OSError):
        raise ValueError('网络或超时错误') from None
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('响应不是有效 JSON') from None
    if not isinstance(result, dict):
        raise ValueError('响应结构无法核验')
    return result


def classify(result):
    # 上游未提供业务码样本，不将某个数字状态或 HTTP 200 推断为成功。
    if result.get('success') is False or result.get('status') is False or result.get('error'):
        raise ValueError('接口报告业务失败')
    message = result.get('msg', result.get('message'))
    if not isinstance(message, str):
        raise ValueError('响应缺少可验证的签到消息')
    message = message.strip().rstrip('!！。.')
    if message in {'签到成功', '今日签到成功', '签到成功，图币已到账'}:
        return 'success'
    if message in {'已签到', '今日已签到', '今天已签到', '您今天已经签到过了',
                   '您今日已签到', '今天已经签到过了', '今天已经签到了'}:
        return 'already_complete'
    raise ValueError('业务结果未确认，请检查登录状态或接口契约')


def account_task(index, cookie, label, dry_run):
    started = time.monotonic()
    stats = dict(total=1, success=0, already_complete=0, skipped=0, failed=0)
    log(f'账号 {index} 开始' + (f'（{label}）' if label else ''))
    stage = time.monotonic()
    try:
        log(f'账号 {index} 阶段 1/2 检查 Cookie 配置')
        if not cookie or '=' not in cookie or cookie.lower().startswith('cookie:'):
            raise ValueError('Cookie 格式错误，请填写完整请求头值')
        cookie.encode('latin-1')
        if any(ord(char) < 32 or ord(char) == 127 for char in cookie):
            raise ValueError('Cookie 含非法控制字符')
        log(f'账号 {index} 阶段 1/2 完成，耗时 {time.monotonic() - stage:.2f} 秒')
        stage = time.monotonic()
        log(f'账号 {index} 阶段 2/2 图币签到')
        if dry_run:
            stats['skipped'] = 1
            status = 'dry-run'
            log(f'账号 {index} ⏭️ 断网预演通过，未发送签到或通知请求')
        else:
            result = http_json(SIGN_URL, {
                'Cookie': cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
                'Accept': 'application/json',
            })
            identity_data = result.get('data')
            for container in (result, identity_data):
                if isinstance(container, dict):
                    for key in ('nickname', 'username', 'displayName', 'uid'):
                        identity = safe_identity(container.get(key))
                        if identity:
                            log(f'账号 {index} 官方身份 {identity}')
            status = classify(result)
            stats[status] = 1
            log(f'账号 {index} ' + ('✅ 签到成功' if status == 'success' else '☑️ 今日已签到'))
    except ValueError as exc:
        stats['failed'] = 1
        status = 'failed'
        # 仅输出本地定义的错误，凭据编码异常也不直接输出。
        message = 'Cookie 必须使用浏览器请求头的原始编码' if isinstance(exc, UnicodeError) else str(exc)
        log(f'账号 {index} ❌ {message}')
    except Exception:
        stats['failed'] = 1
        status = 'failed'
        log(f'账号 {index} ❌ 执行异常，详细响应已抑制')
    elapsed = round(time.monotonic() - started, 3)
    log(f'账号 {index} 阶段结束，阶段耗时 {time.monotonic() - stage:.2f} 秒')
    log(f'账号 {index} 统计 总任务 1，成功 {stats["success"]}，已完成 {stats["already_complete"]}，'
        f'跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {elapsed:.2f} 秒')
    return dict(account=index, status=status, tasks=stats, elapsedSeconds=elapsed)


def notification_enabled():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE_VALUES:
        return False
    if switch in TRUE_VALUES:
        return True
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    path = Path(__file__)
    names = {CATALOG_ID, path.name, 'cainiao.py', path.as_posix()}
    if 'scripts' in path.parts:
        names.add('/'.join(path.parts[path.parts.index('scripts') + 1:]))
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in selectors if pattern for name in names)


def notify(body, dry_run):
    if dry_run:
        log('通知 断网预演，未调用通知模块或 PushPlus')
        return 'dry-run'
    if not notification_enabled():
        log('通知 已按 QINGLONG_NOTIFY 或脚本选择列表关闭')
        return 'disabled'
    delivered = False
    # 子进程隔离通知异常和输出，避免影响业务码或输出原始响应。
    python_sender = '''import importlib, importlib.util, sys
path, title, body = sys.argv[1:]
if path:
    spec = importlib.util.spec_from_file_location("ql_notification", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    module = importlib.import_module("notify")
result = module.send(title, body)
if result is False:
    raise SystemExit(1)
'''
    roots = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        roots.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    roots.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    commands = [[sys.executable, '-c', python_sender, '', TITLE, body]]
    for root in roots:
        if (root / 'notify.py').is_file():
            commands.append([sys.executable, '-c', python_sender, str(root / 'notify.py'), TITLE, body])
        if (root / 'sendNotify.js').is_file():
            commands.append(['node', '-e',
                             'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).then(r=>{if(r===false)process.exitCode=1}).catch(()=>{process.exitCode=1})',
                             str(root / 'sendNotify.js'), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                delivered = True
                log('通知 青龙通知模块已完成调用')
                break
        except (OSError, subprocess.TimeoutExpired):
            continue
    push_token = os.getenv('PUSHPLUS_TOKEN', '').strip()
    if push_token:
        try:
            result = http_json('https://www.pushplus.plus/send',
                               {'Content-Type': 'application/json'},
                               {'token': push_token, 'title': TITLE, 'content': body, 'template': 'txt'})
            if result.get('code') != 200:
                raise ValueError('通知未确认')
            log('通知 PushPlus 已确认成功')
            delivered = True
        except Exception:
            log('通知 PushPlus 发送失败，保留业务退出码')
    if not delivered:
        log('通知 ⚠️ 通知模块不可用或发送失败，保留业务退出码')
    return 'sent' if delivered else 'unavailable-or-failed'


def main():
    started = time.monotonic()
    started_at = datetime.now().isoformat(timespec='seconds')
    dry_run = os.getenv('CAINIAO_DRY_RUN', '0').strip().lower() in TRUE_VALUES
    cookies = [line.strip() for line in os.getenv('CAINIAO_COOKIE', '').splitlines() if line.strip()]
    SECRETS[:] = cookies + [os.getenv('PUSHPLUS_TOKEN', '').strip()]
    for cookie in cookies:
        SECRETS.extend(field.split('=', 1)[1].strip() for field in cookie.split(';') if '=' in field)
    labels = [safe_identity(line.strip()) for line in os.getenv('CAINIAO_ACCOUNT_NAMES', '').splitlines()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间 {started_at}，模式 {"断网预演" if dry_run else "实际签到"}，账号数 {len(cookies)}')
    results = []
    if not cookies:
        log('配置错误 缺少 CAINIAO_COOKIE，请每行填写一个账号的完整 Cookie')
    for index, cookie in enumerate(cookies, 1):
        label = labels[index - 1] if index <= len(labels) else None
        results.append(account_task(index, cookie, label, dry_run))
    failed = sum(item['status'] == 'failed' for item in results)
    verified = sum(item['status'] in {'success', 'already_complete'} for item in results)
    exit_code = int(not cookies or failed > 0)
    if not cookies:
        status = 'configuration-error'
    elif failed:
        status = 'partial-failure' if failed < len(cookies) else 'failure'
    else:
        status = 'dry-run' if dry_run else 'success'
    totals = {key: sum(item['tasks'][key] for item in results)
              for key in ('total', 'success', 'already_complete', 'skipped', 'failed')}
    summary = dict(task=TITLE, mode='dry-run' if dry_run else 'live', status=status,
                   accounts=len(cookies), success=verified, failed=failed,
                   dryRunPassed=sum(item['status'] == 'dry-run' for item in results),
                   tasks=totals, results=results, exitCode=exit_code, startedAt=started_at)
    body = (f'{TITLE}\n状态 {status}\n账号总数 {len(cookies)}，成功 {verified}，失败 {failed}\n'
            f'预演通过 {summary["dryRunPassed"]}，配置错误 {int(not cookies)}\n'
            f'子任务 成功 {totals["success"]}，已完成 {totals["already_complete"]}，'
            f'跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    try:
        summary['notification'] = notify(body, dry_run)
    except Exception:
        summary['notification'] = 'unavailable-or-failed'
        log('通知 ⚠️ 通知异常，保留业务退出码')
    summary['elapsedSeconds'] = round(time.monotonic() - started, 3)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    for line in body.splitlines():
        log(line)
    log(f'总耗时 {summary["elapsedSeconds"]:.2f} 秒，完成时间 {summary["finishedAt"]}')
    log(f'通知状态 {summary["notification"]}，最终状态 {status}，退出码 {exit_code}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


def main_handler(event, context):
    return main()


if __name__ == '__main__':
    sys.exit(main())
