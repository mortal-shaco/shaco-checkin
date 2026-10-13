#!/usr/bin/env python3
# name: 网易云游戏每日签到
# cron: 0 8 * * *
# SPDX-License-Identifier: Apache-2.0
# Upstream: Riku1998/cg163-autocheckin (Apache-2.0)
# Original attribution retained: GamerNoTitle https://bili33.top
# https://github.com/GamerNoTitle/wyycg-autocheckin
"""网易云游戏每日签到，Python 3 标准库独立运行。

登录 https://cg.163.com/，在浏览器开发者工具网络面板中查看
n.cg.163.com 的 client-settings/@current 或 sign-today 请求，复制完整
Authorization 请求头值（不是整串 Cookie）。CG163_ACCOUNTS 每行一个值；
旧变量 wyycg_cookies 作为兼容别名，同样使用换行，不再用 # 分隔账号。
可选 PPKEY 从 PushPlus 个人中心获取。QINGLONG_NOTIFY=0 关闭所有通知。
CG163_DRY_RUN=1 完全断网模拟；每天 08:00 为建议时间，原源码没有 cron。
仅明确业务成功响应计为成功；未知响应失败闭合，不打印响应正文。
"""
import datetime
import importlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

TITLE = '网易云游戏每日签到'
BASE = 'https://n.cg.163.com/api/v2/'
DISABLED = {'0', 'false', 'no', 'off'}


def enabled(value):
    return str(value).strip().lower() not in DISABLED


def stamp():
    return datetime.datetime.now().strftime('%H:%M:%S')


def log(message):
    print(f'[{stamp()}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 防止 Authorization 在跳转时被送到其他域名。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('服务器返回重定向，已阻止凭据转发')


def request(url, method='GET', credential=None, payload=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0',
               'Origin': 'https://cg.163.com', 'Referer': 'https://cg.163.com/',
               'X-Platform': '0'}
    if credential is not None:
        headers['Authorization'] = credential
    data = b'' if method == 'POST' else None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as resp:
            body = resp.read(65537)
            if resp.status != 200:
                raise TaskError(f'HTTP 状态 {resp.status}，未确认成功')
            if len(body) > 65536:
                raise TaskError('响应超出大小限制')
        result = json.loads(body)
        if not isinstance(result, dict):
            raise TaskError('响应结构未知，未确认成功')
        return result
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 状态 {exc.code}，请检查凭据或服务状态') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络或超时错误') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON，未确认成功') from None


def business_ok(result):
    # 若接口带失败标志或错误码，绝不被其他成功字段覆盖。
    if result.get('success') is False or result.get('error'):
        return False
    for key in ('code', 'statusCode'):
        if key in result and (isinstance(result[key], bool) or result[key] not in (0, 200, '0', '200')):
            return False
    return result.get('success') is True or any(
        key in result and not isinstance(result[key], bool) and result[key] in (0, 200, '0', '200')
        for key in ('code', 'statusCode'))


def identity(result, credential):
    # 只读取官方身份字段；不输出会话、手机号、设备字段或其他响应。
    objects = [result]
    for key in ('data', 'user', 'userInfo', 'profile'):
        if isinstance(result.get(key), dict):
            objects.append(result[key])
    for obj in list(objects):
        for key in ('user', 'userInfo', 'profile'):
            if isinstance(obj.get(key), dict):
                objects.append(obj[key])
    for obj in objects:
        for key in ('nickname', 'username', 'displayName', 'uid'):
            value = obj.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                value = str(value)
                # 防止凭据回显、日志注入以及手机号被当作用户名显示。
                if credential in value or any(ord(c) < 32 for c in value):
                    continue
                if key != 'uid' and value.lstrip('+').isdigit() and len(value.lstrip('+')) >= 11:
                    continue
                return value
    return None


def notify(body, dry):
    if not enabled(os.getenv('QINGLONG_NOTIFY', '1')):
        log('通知：已由 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    if dry:
        log('通知：断网预演已模拟青龙通知与可选 PushPlus 推送')
        return 'dry-run'
    delivered = False
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
        if module is None:
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None:
            log('通知：未找到青龙 notify.py，业务退出码保持不变')
        else:
            module.send(TITLE, body)
            delivered = True
            log('通知：青龙通知已提交')
    except Exception:
        log('通知：青龙通知失败，业务退出码保持不变')
    if os.getenv('PPKEY', '').strip():
        try:
            reply = request('https://www.pushplus.plus/send', 'POST', payload={
                'token': os.environ['PPKEY'].strip(), 'title': TITLE,
                'content': body, 'template': 'txt'})
            if reply.get('code') != 200:
                raise TaskError('推送未确认成功')
            log('通知：PushPlus 推送成功')
        except Exception:
            log('通知：PushPlus 推送失败，业务退出码保持不变')
    return 'submitted' if delivered else 'unavailable-or-failed'


def main():
    started = time.monotonic()
    dry = os.getenv('CG163_DRY_RUN', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    raw = os.getenv('CG163_ACCOUNTS', '').strip() or os.getenv('wyycg_cookies', '').strip()
    accounts = [line.strip() for line in raw.splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式执行"}；账号数：{len(accounts)}')
    totals = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    succeeded = failed = 0
    if not accounts:
        log('❌ 配置错误：请设置 CG163_ACCOUNTS，每行一个 Authorization 值')
    for number, credential in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {'total': 2, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
        log(f'账号 {number} 开始')
        for stage, label, endpoint, method in ((1, '账号验证', 'client-settings/@current', 'GET'),
                                                (2, '每日签到', 'sign-today', 'POST')):
            stage_start = time.monotonic()
            log(f'账号 {number} 阶段 {stage}/2：{label}')
            try:
                if any(ord(c) < 32 or ord(c) == 127 for c in credential):
                    raise TaskError('凭据包含非法控制字符')
                if dry:
                    log(f'⏭️ 账号 {number}：预演 {method} {endpoint}，未发送请求')
                    stats['skipped'] += 1
                else:
                    result = request(BASE + endpoint, method, credential)
                    if not business_ok(result):
                        raise TaskError('缺少明确业务成功标志或业务拒绝，请核对接口契约')
                    if stage == 1:
                        name = identity(result, credential)
                        if name is not None:
                            log(f'账号 {number} 官方身份：{name}')
                    log(f'✅ 账号 {number}：{label}成功（已验证业务状态）')
                    stats['success'] += 1
            except Exception:
                # 异常正文可能含敏感值，不输出异常对象。
                log(f'❌ 账号 {number}：{label}失败，网络、凭据或业务响应未通过核验')
                stats['failed'] += 1
                if stage == 1:
                    stats['skipped'] += 1
                    log(f'账号 {number} 阶段 2/2：每日签到已跳过（账号验证失败）')
                break
            finally:
                log(f'账号 {number} 阶段 {stage} 耗时：{time.monotonic() - stage_start:.2f} 秒')
        if stats['failed']:
            failed += 1
        elif not dry:
            succeeded += 1
        for key in totals:
            totals[key] += stats[key]
        log(f'账号 {number} 统计：任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic() - account_start:.2f} 秒')
    code = 1 if failed or not accounts else 0
    status = 'configuration-error' if not accounts else ('partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(accounts)}；成功：{succeeded}；失败：{failed}；预演：{len(accounts) if dry else 0}；最终状态：{status}'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：{json.dumps(totals, ensure_ascii=False)}')
    log(f'总耗时：{time.monotonic() - started:.2f} 秒；完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；通知状态：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'applicationKey': 'cg163', 'status': status,
          'accounts': len(accounts), 'success': succeeded, 'failed': failed,
          'dryRun': dry, 'tasks': totals, 'notification': notification,
          'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
