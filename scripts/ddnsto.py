#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: DDNSTO七天免费续费
# cron: 32 2 * * *
# SPDX-License-Identifier: MIT
# 上游署名：cloudcranes/some_scripts，原文件 ddnsto.py
# 来源提交：f62b50fe0a961ea8a8707682723b080c0a5d1142
# 上游元数据：cron "30 9 * * *"；new Env('DDNSTO七天免费续费')
"""DDNSTO 七天免费套餐续费（Python 3，仅标准库）。

DDNSTO_ACCOUNTS：每个非空行为 路由器ID|完整Cookie，只在首个 | 分隔。
登录 https://www.ddnsto.com/app/#/devices，在开发者工具网络面板获取
www.ddnsto.com 请求中的完整 Cookie（必须含 csrftoken）。先在官网申请
一次七天免费套餐，从 /api/user/routers/<路由器ID>/ 请求路径获取路由器ID；
它不是登录用户ID。不要公开 Cookie 或路由器ID。
兼容单账号 ddns_userid + ddns_cookie；配置 DDNSTO_ACCOUNTS 时优先使用它。
DDNSTO_DRY_RUN=1：仅校验配置和演示流程，禁止 HTTP 和通知网络连接。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭。可指定 QINGLONG_NOTIFY_DIR。
只请求上游 product_id=2，不支付订单，不修改服务器设置。接口变化失败闭合。
"""
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

TITLE = 'DDNSTO七天免费续费'
BASE = 'https://www.ddnsto.com'
TIMEOUT = 20
MAX_BYTES = 1024 * 1024
FALSE_VALUES = {'0', 'false', 'no', 'off'}
TRUE_VALUES = {'1', 'true', 'yes', 'on'}


class TaskError(Exception):
    pass


class WeeklyLimit(TaskError):
    pass


def now():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def expiry(data):
    try:
        value = data['active_plan']['product_expired_at']
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except (KeyError, TypeError, ValueError, AttributeError):
        raise TaskError('接口未返回可验证的套餐到期时间') from None


def identity(data, cookie):
    # uid 属于路由器，不能作为公开用户身份输出。
    for key in ('nickname', 'username', 'display_name'):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        secrets = [part.split('=', 1)[1].strip() for part in cookie.split(';') if '=' in part]
        if any(secret and secret in value for secret in secrets):
            continue
        if re.search(r'\d{11,}', value) or any(ord(c) < 32 for c in value):
            continue
        log(f'官方账号身份：{value}')
        return


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口发生重定向，已停止以保护凭据')


class Client:
    def __init__(self, cookie, csrf, dry):
        self.dry = dry
        self.opener = urllib.request.build_opener(NoRedirect())
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Cookie': cookie, 'X-CSRFToken': csrf,
            'Referer': BASE + '/app/', 'Origin': BASE,
            'User-Agent': 'DDNSTO-Qinglong-Maintained/1.0',
        }

    def request(self, method, path, fields=None):
        if self.dry:
            raise TaskError('预演禁止网络请求')
        body = urllib.parse.urlencode(fields, doseq=True).encode() if fields is not None else None
        headers = dict(self.headers)
        if body is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=TIMEOUT) as response:
                if not 200 <= response.status < 300:
                    raise TaskError('HTTP 状态异常')
                raw = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise TaskError(f'HTTP {exc.code}，请检查登录状态或接口契约') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络请求失败或超时') from None
        if len(raw) > MAX_BYTES:
            raise TaskError('接口响应过大')
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError('接口返回非 JSON 数据') from None
        if not isinstance(result, dict):
            raise TaskError('接口返回结构不符合契约')
        error = result.get('application-error')
        if error == '超出本周免费套餐购买次数':
            raise WeeklyLimit('超出本周免费套餐购买次数')
        if error:
            raise TaskError('接口返回业务错误（已隐藏原始内容）')
        return result


def accounts_from_env():
    value = os.environ.get('DDNSTO_ACCOUNTS', '')
    if value.strip():
        return [line.strip() for line in value.splitlines() if line.strip()]
    router = os.environ.get('ddns_userid', '').strip()
    cookie = os.environ.get('ddns_cookie', '').strip()
    if router or cookie:
        if '\n' in router or '\n' in cookie or '\r' in router or '\r' in cookie:
            raise TaskError('旧变量仅支持单账号；多账号请使用 DDNSTO_ACCOUNTS')
        return [router + '|' + cookie]
    raise TaskError('未配置 DDNSTO_ACCOUNTS 或兼容单账号变量')


def parse_account(line):
    router, sep, cookie = line.partition('|')
    router, cookie = router.strip(), cookie.strip()
    if not sep or not re.fullmatch(r'[A-Za-z0-9_-]+', router) or not cookie:
        raise TaskError('账号配置应为 路由器ID|完整Cookie')
    if any(ord(c) < 32 or ord(c) > 126 for c in cookie):
        raise TaskError('Cookie 含非法字符')
    tokens = [part.strip().split('=', 1)[1] for part in cookie.split(';')
              if part.strip().startswith('csrftoken=')]
    if len(tokens) != 1 or not tokens[0]:
        raise TaskError('Cookie 必须含唯一且非空的 csrftoken')
    return router, cookie, tokens[0]


def stage(number, label, action):
    start = time.monotonic()
    log(f'阶段 {number}：{label}')
    try:
        result = action()
    except Exception:
        log(f'❌ 阶段 {number} 失败，耗时 {time.monotonic() - start:.2f} 秒')
        raise
    log(f'✅ 阶段 {number} 完成，耗时 {time.monotonic() - start:.2f} 秒')
    return result


def run_account(line, dry):
    router, cookie, csrf = stage(1, '校验账号配置', lambda: parse_account(line))
    if dry:
        for number, label in enumerate(('读取现有套餐', '申请免费套餐 product_id=2', '查询订单', '绑定套餐并核对到期时间'), 2):
            stage(number, label, lambda: log('⏭️ DRY_RUN：模拟阶段，不发送请求、不修改账号'))
        return 'dry-run'
    client = Client(cookie, csrf, dry)
    path = '/api/user/routers/' + router + '/'
    before = stage(2, '读取现有套餐', lambda: client.request('GET', path))
    identity(before, cookie)
    previous_expiry = expiry(before)
    try:
        order = stage(3, '申请七天免费套餐', lambda: client.request(
            'POST', '/api/user/product/orders/', {'product_id': '2', 'uuid_from_client': uuid.uuid4().hex}))
    except WeeklyLimit:
        if previous_expiry <= dt.datetime.now(dt.timezone.utc):
            raise TaskError('本周申请次数已用完，但现有套餐已过期') from None
        log('☑️ 超出本周免费套餐购买次数；已验证现有套餐仍有效')
        log('到期时间（北京时间）：' + previous_expiry.astimezone(dt.timezone(dt.timedelta(hours=8))).isoformat())
        return 'already-complete'
    order_id = order.get('id')
    if isinstance(order_id, bool) or not isinstance(order_id, (str, int)) or not re.fullmatch(r'[A-Za-z0-9_-]+', str(order_id)):
        raise TaskError('申请订单未返回有效订单编号')
    detail = stage(4, '查询订单', lambda: client.request('GET', '/api/user/product/orders/' + str(order_id) + '/'))
    if str(detail.get('id')) != str(order_id):
        raise TaskError('查询订单编号不匹配')
    for item in (order, detail):
        if 'product_id' in item and str(item['product_id']) != '2':
            raise TaskError('订单产品不是指定免费套餐，停止绑定')
    stage(5, '绑定套餐（保留原服务器设置）', lambda: client.request('PATCH', path, {'plan_ids_to_add': [str(order_id)]}))
    after = stage(6, '重新读取并核对套餐', lambda: client.request('GET', path))
    final_expiry = expiry(after)
    if final_expiry <= previous_expiry or final_expiry <= dt.datetime.now(dt.timezone.utc):
        raise TaskError('套餐到期时间未延长，不能确认续费成功')
    identity(after, cookie)
    log('✅ ****白嫖成功*****')
    log('到期时间（北京时间）：' + final_expiry.astimezone(dt.timezone(dt.timedelta(hours=8))).isoformat())
    return 'success'


# 隔离通知输出，通知错误不影响业务退出码。预演仍尝试通知，但封锁 socket。
NOTIFY_WORKER = r'''
import contextlib, importlib.util, io, os, socket, sys
if sys.argv[1] == 'dry':
    def blocked(*args, **kwargs):
        raise RuntimeError('dry-run network disabled')
    socket.socket = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import notify
    notify.send(sys.argv[2], sys.argv[3])
'''


def notify_summary(body, dry):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower().strip() in FALSE_VALUES:
        log('⏭️ 通知已由 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    paths = []
    custom = os.environ.get('QINGLONG_NOTIFY_DIR')
    if custom:
        paths.append(Path(custom) / 'notify.py')
    paths.extend([Path(__file__).resolve().parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.insert(0, Path(spec.origin))
    except (ImportError, ValueError, AttributeError):
        pass
    helper = next((path for path in paths if path.is_file()), None)
    if not helper:
        log('⚠️ 通知不可用：未找到青龙 notify.py；业务退出码保持不变')
        return 'unavailable'
    worker = 'import sys\nsys.path.insert(0, sys.argv[4])\n' + NOTIFY_WORKER
    try:
        result = subprocess.run([sys.executable, '-c', worker, 'dry' if dry else 'live', TITLE, body, str(helper.parent)],
                                capture_output=True, timeout=20, check=False,
                                env={key: value for key, value in os.environ.items()
                                     if key not in {'DDNSTO_ACCOUNTS', 'ddns_cookie', 'ddns_userid'}})
        if result.returncode:
            log('⚠️ 通知未送达' + ('（预演已封锁网络）' if dry else '') + '；业务退出码保持不变')
            return 'failed'
        log('✅ 通知调用完成')
        return 'sent'
    except (OSError, subprocess.TimeoutExpired):
        log('⚠️ 通知调用失败或超时；业务退出码保持不变')
        return 'failed'


def main():
    started = time.monotonic()
    dry_value = os.environ.get('DDNSTO_DRY_RUN', '0').lower().strip()
    dry = dry_value in TRUE_VALUES
    log('========== ' + TITLE + ' ==========')
    start_time = now()
    log('开始时间：' + start_time)
    log('运行模式：' + ('无网络预演' if dry else '真实续费'))
    results = []
    configuration_error = False
    try:
        if dry_value not in TRUE_VALUES | FALSE_VALUES:
            raise TaskError('DDNSTO_DRY_RUN 只接受 1/0、true/false、yes/no、on/off')
        lines = accounts_from_env()
    except TaskError as exc:
        lines = []
        configuration_error = True
        log('❌ 配置错误：' + str(exc))
    log(f'账号总数：{len(lines)}')
    for index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        log(f'---------- 账号 {index} ----------')
        try:
            outcome = run_account(line, dry)
        except TaskError as exc:
            outcome = 'failure'
            log('❌ ' + str(exc))
        except Exception:
            outcome = 'failure'
            log('❌ 未预期的执行错误，原始异常已隐藏')
        counts = {'success': int(outcome == 'success'), 'alreadyComplete': int(outcome == 'already-complete'),
                  'skipped': int(outcome == 'dry-run'), 'failure': int(outcome == 'failure')}
        results.append({'account': index, 'status': outcome, **counts})
        log(f'账号 {index} 统计：总任务 1，成功 {counts["success"]}，已完成 {counts["alreadyComplete"]}，跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {time.monotonic() - account_start:.2f} 秒')
    failed = sum(r['failure'] for r in results)
    success = sum(r['success'] + r['alreadyComplete'] for r in results)
    code = 1 if configuration_error or failed else 0
    status = 'configuration-error' if configuration_error else ('partial-failure' if failed and success else 'failure') if failed else 'dry-run' if dry else 'success'
    log('----------------------------------------')
    log(f'账号统计：总数 {len(lines)}，成功 {success}，失败 {failed}，预演 {sum(r["skipped"] for r in results)}')
    log(f'子任务统计：总任务 {len(results)}，成功 {sum(r["success"] for r in results)}，已完成 {sum(r["alreadyComplete"] for r in results)}，跳过 {sum(r["skipped"] for r in results)}，失败 {failed}')
    body = f'状态：{status}；账号总数：{len(lines)}；成功数：{success}；失败数：{failed}；预演数：{sum(r["skipped"] for r in results)}'
    notification = notify_summary(body, dry)
    finished = now()
    log(f'总耗时：{time.monotonic() - started:.2f} 秒；完成时间：{finished}；通知状态：{notification}')
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'accounts': len(lines), 'success': success,
          'failure': failed, 'configurationError': configuration_error, 'results': results, 'notification': notification,
          'startedAt': start_time, 'finishedAt': finished, 'durationSeconds': round(time.monotonic() - started, 3), 'exitCode': code}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
