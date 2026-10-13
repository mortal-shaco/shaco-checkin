#!/usr/bin/env python3
# name: 网易云游戏自动签到
# cron: 0 8 * * *
# SPDX-License-Identifier: Apache-2.0
# 原作者：GamerNoTitle https://bili33.top
# 来源：https://github.com/GamerNoTitle/wyycg-autocheckin
# 原始 main.py 与 qinglong/qinglong.py；保留 Apache-2.0 授权及作者署名。
"""网易云游戏每日签到，Python 3 标准库独立运行。
WYYCG_ACCOUNTS：登录 https://cg.163.com 后在浏览器开发者工具的网络面板，
查找 n.cg.163.com 请求，复制 Authorization 请求头完整值（不是 Cookie）。
每个非空行一个账号；兼容 wyycg_cookies 或第一个位置参数，均使用换行。
可选位置参数依次是 Telegram 接收者、机器人令牌、ServerChan 密钥、QQ 密钥、
PushPlus 令牌；也可使用契约中的对应环境变量。推荐青龙统一通知。
上游未声明 cron，本版本建议每日北京时间 08:00，青龙时区由运行环境决定。
WYYCG_DRY_RUN=1 完全断网，只检查配置与模拟流程，包括不调用通知模块。
签到可能领取云游戏时长；不执行消费、发帖或修改账户的其他动作。
"""
import datetime
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


def http_json(url, method='GET', headers=None, body=None):
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
        raise TaskError('响应不是有效 JSON，无法确认业务结果') from None


def confirmed(payload):
    """保守接受明确业务成功标志；不猜测未提供样本的数字业务码。"""
    if payload is True:
        return True
    if not isinstance(payload, dict):
        return False
    # 矛盾标志不能被另一个成功字段覆盖。
    if payload.get('success') is False or payload.get('ok') is False or payload.get('error'):
        return False
    if 'code' in payload and payload['code'] not in (0, 200, '0', '200'):
        return False
    return payload.get('success') is True or payload.get('ok') is True


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
            if value and not any(secret and secret in value for secret in secrets) and not re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                if not any(ord(char) < 32 for char in value):
                    return value
    return ''


def account_task(number, credential, dry, secrets):
    stats = dict(total=2, success=0, alreadyComplete=0, skipped=0, failed=0)
    began = time.monotonic()
    headers = {'Authorization': credential, 'Accept': 'application/json, text/plain, */*',
               'Origin': 'https://cg.163.com', 'Referer': 'https://cg.163.com/',
               'User-Agent': 'Mozilla/5.0', 'X-Platform': '0'}
    failure = False
    for stage, label, path, method in (
        (1, '验证凭据', 'client-settings/@current', 'GET'),
        (2, '每日签到', 'sign-today', 'POST'),
    ):
        started = time.monotonic()
        log(f'账号 {number} · 阶段 {stage}/2 · {label} 开始')
        if failure:
            stats['skipped'] += 1
            log(f'⏭️ 账号 {number} · {label} 跳过：前序验证失败；耗时 0.00 秒')
            continue
        try:
            if '\r' in credential or any(ord(c) < 32 for c in credential):
                raise TaskError('凭据含非法控制字符')
            if dry:
                stats['skipped'] += 1
                log(f'⏭️ 账号 {number} · {label}：断网预演，未发送请求；耗时 {time.monotonic()-started:.2f} 秒')
                continue
            payload = http_json(BASE + path, method, headers, b'' if method == 'POST' else None)
            if stage == 1:
                # GET 200 且为无错误的配置 JSON，仅验证可访问性，不代表签到成功。
                if not isinstance(payload, dict) or not payload or payload.get('error') or payload.get('success') is False or payload.get('ok') is False:
                    raise TaskError('账户配置响应异常')
                if 'code' in payload and payload['code'] not in (0, 200, '0', '200'):
                    raise TaskError('账户配置包含业务错误码')
            elif not confirmed(payload):
                raise TaskError('未收到明确业务成功标志，签到结果待核验')
            name = identity(payload, secrets)
            if name:
                log(f'账号 {number} · 官方身份：{name}')
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
    log(f'账号 {number} 统计：总任务 2，成功 {stats["success"]}，已完成 0，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒')
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
        requests.append(('Telegram', f'https://api.telegram.org/bot{urllib.parse.quote(telegram, safe="")}/sendMessage', {'chat_id': receiver, 'text': body}))
    if serverchan:
        requests.append(('ServerChan', f'https://sctapi.ftqq.com/{urllib.parse.quote(serverchan, safe="")}.send', {'title': TITLE, 'desp': body}))
    if qq:
        requests.append(('QQ', f'https://push.xuthus.cc/send/{urllib.parse.quote(qq, safe="")}', {'c': TITLE + '\n' + body}))
    if pushplus:
        requests.append(('PushPlus', 'https://pushplus.hxtrip.com/send', {'token': pushplus, 'title': TITLE, 'content': body, 'template': 'txt'}))
    for name, url, data in requests:
        try:
            result = http_json(url, 'POST', {'Content-Type': 'application/x-www-form-urlencoded'}, urllib.parse.urlencode(data).encode())
            ok = confirmed(result) or (isinstance(result, dict) and result.get('code') in (0, 200) and result.get('success') is not False)
            log(f'{name} 推送：' + ('已确认' if ok else '未确认投递'))
        except Exception:
            log(f'⚠️ {name} 推送不可用；业务退出码保持不变')


def main():
    started = time.monotonic()
    dry = enabled('WYYCG_DRY_RUN')
    raw = os.getenv('WYYCG_ACCOUNTS') or os.getenv('wyycg_cookies') or (sys.argv[1] if len(sys.argv) > 1 else '')
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    names = ['WYYCG_TELEGRAM_ID', 'WYYCG_TELEGRAM_TOKEN', 'WYYCG_SERVERCHAN_KEY', 'WYYCG_QQ_KEY', 'WYYCG_PUSHPLUS_TOKEN']
    settings = [os.getenv(name) or (sys.argv[i+2] if len(sys.argv) > i+2 else '') for i, name in enumerate(names)]
    log(f'===== {TITLE} =====')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "真实执行"}；账号总数：{len(accounts)}')
    results = []
    if not accounts:
        log('❌ 配置错误：请设置 WYYCG_ACCOUNTS，每个非空行一个 Authorization 值')
    for number, credential in enumerate(accounts, 1):
        results.append(account_task(number, credential, dry, accounts + settings))
    failed = sum(r['status'] == 'failure' for r in results)
    success = sum(r['status'] == 'success' for r in results)
    exit_code = 1 if failed or not accounts else 0
    status = 'configuration-error' if not accounts else ('partial-failure' if failed and failed < len(accounts) else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(accounts)}，成功数：{success}，失败数：{failed}，预演数：{sum(r["status"] == "dry-run" for r in results)}；最终状态：{status}'
    if not enabled('QINGLONG_NOTIFY', '1'):
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
