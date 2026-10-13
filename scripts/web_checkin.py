#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Trae CN 每日签到
# cron: 30 8 * * *
"""独立维护版，来源 Cat-zaizai/ZaiZaiCat-Checkin script/trae。
上游 main.py: Author: Assistant; Date: 2026-09-07。
网页认证思路参考 star620/TRAE-Automatic-sign-in；接口参考 cockpit-tools PR #2179。

TRAE_ACCOUNTS：每个非空行一个 JSON 对象，字段 device_id 和至少一个
session/sessionid/access_token；可同时配置三种凭据供续期和回退。
浏览器登录 https://www.trae.cn 后在开发者工具→应用→Cookie 复制
X-Cloudide-Session 的 Value 为 session、sessionid 的 Value 为 sessionid。
不要解码百分号，不要复制整段 Cookie。桌面令牌可从本人官方请求的
Authorization: Cloud-IDE-JWT 后取得；device_id 从同账号官方签到请求的
x-device-id 取得（16 位数字，必须属于该账号），无需读取客户端私有文件。
expires_at 可选，为桌面令牌到期的秒级时间戳。不得共用或伪造设备。
兼容 TRAE_SESSION（每行一个会话）及 --session；此时单账号另配
TRAE_DEVICE_ID 或 --device-id。多个账号请统一使用 TRAE_ACCOUNTS。
TRAE_ACTION=checkin（默认）或 status（只查询）；TRAE_DRY_RUN=1 完全断网。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
预演仅验证配置与执行计划，不代表真实认证或签到成功。

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
import argparse
import contextlib
import importlib.util
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie

BASE = 'https://api.trae.cn'
UA = 'VSCode 1.107.1 (TRAE SOLO CN)'
AUTH = {401, 1001, 1002, 1003, 10085}


class Failure(Exception):
    def __init__(self, message, auth=False):
        super().__init__(message)
        self.auth = auth


def log(message):
    print(time.strftime('[%H:%M:%S] ') + message, flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向重定向目的地传递凭据


def post(path, headers, body=b'{}', dry=False):
    if dry:
        raise Failure('预演禁止网络请求')
    h = {'User-Agent': UA, 'Accept': 'application/json, text/plain, */*'}
    h.update(headers)
    req = urllib.request.Request(BASE + path, data=body, headers=h, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise Failure('响应超过大小限制')
            return response.status, response.headers, raw
    except urllib.error.HTTPError as exc:
        raise Failure('HTTP 请求失败（状态 %d）' % exc.code, exc.code == 401) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Failure('网络连接失败或超时') from None


def obj(raw):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise Failure('响应不是有效 JSON') from None
    if not isinstance(value, dict):
        raise Failure('响应不是 JSON 对象')
    return value


def web_headers(cookie):
    return {'Cookie': cookie, 'Referer': 'https://www.trae.cn/', 'Origin': 'https://www.trae.cn'}


def token_for(session):
    _, _, raw = post('/cloudide/api/v3/common/GetUserToken',
                     web_headers('X-Cloudide-Session=' + session))
    data = obj(raw)
    result = data.get('Result')
    metadata = data.get('ResponseMetadata')
    if isinstance(metadata, dict) and metadata.get('Error'):
        raise Failure('会话认证失败，请更新 Cookie', True)
    if not isinstance(result, dict) or not isinstance(result.get('Token'), str) or not result['Token']:
        raise Failure('会话未返回有效令牌，请更新 Cookie', True)
    return result['Token'], result.get('UserID')


def refresh(sessionid):
    _, headers, _ = post('/cloudide/api/v3/trae/Login',
                         dict(web_headers('sessionid=' + sessionid), **{'Content-Type': 'application/json'}))
    for value in headers.get_all('Set-Cookie', []):
        cookie = SimpleCookie()
        cookie.load(value)
        if 'X-Cloudide-Session' in cookie and cookie['X-Cloudide-Session'].value:
            return cookie['X-Cloudide-Session'].value
    raise Failure('续期未返回会话 Cookie，请更新 sessionid', True)


def api(path, token, device):
    _, _, raw = post('/trae/api/v2/ug/checkin_credits/' + path,
                     {'Authorization': 'Cloud-IDE-JWT ' + token, 'X-User-Region': 'cn',
                      'x-device-id': device, 'Content-Type': 'application/json'})
    data = obj(raw)
    code = data.get('code')
    if type(code) is not int or code != 0:
        hint = '业务响应未确认成功'
        if code in (9074, 9095):
            hint = '设备校验拒绝，请核对账号自己的注册设备；不自动换设备重试'
        elif type(code) is int and code in AUTH:
            hint = '凭据失效，请更新该账号凭据'
        raise Failure(hint, type(code) is int and code in AUTH)
    return data


def validate(account):
    if not isinstance(account, dict):
        raise Failure('账号行必须是 JSON 对象')
    device = account.get('device_id')
    if not isinstance(device, str) or not re.fullmatch(r'[0-9]{16}', device):
        raise Failure('缺少账号自己的 16 位 device_id')
    if not any(account.get(k) for k in ('session', 'sessionid', 'access_token')):
        raise Failure('缺少 session、sessionid 或 access_token')
    for key in ('session', 'sessionid', 'access_token'):
        value = account.get(key, '')
        if not isinstance(value, str) or any(c in value for c in '\r\n;'):
            raise Failure('凭据字段格式错误，请复制单独的值')
    if 'expires_at' in account:
        try:
            valid = not isinstance(account['expires_at'], bool) and math.isfinite(float(account['expires_at']))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise Failure('expires_at 必须是秒级时间戳')
    return account


def desktop(account):
    if not account.get('access_token'):
        raise Failure('无可用桌面令牌，请更新网页凭据')
    if 'expires_at' in account and time.time() >= float(account['expires_at']):
        raise Failure('桌面令牌已过期，请更新凭据')
    return account['access_token']


def process(account, dry, action, seen, stage):
    validate(account)
    if dry:
        for name in ('认证计划', '查询签到状态计划', '领取计划' if action == 'checkin' else '仅查询计划'):
            stage(name, lambda: log('⏭️ 配置有效，预演未执行网络请求或领取'))
        return 'dry-run'
    session = account.get('session', '')
    if account.get('sessionid'):
        try:
            session = stage('长效 Cookie 续期', lambda: refresh(account['sessionid']))
        except Failure:
            log('⚠️ 续期失败，尝试本账号已有会话或桌面令牌')
    token, uid = None, None
    if session:
        try:
            token, uid = stage('网页会话换令牌', lambda: token_for(session))
        except Failure:
            log('⚠️ 网页认证失败，尝试本账号桌面令牌')
    if token is None:
        token = stage('桌面凭据预检', lambda: desktop(account))
        session = ''
    if isinstance(uid, (str, int)) and not isinstance(uid, bool) and str(uid):
        # 仅显示官方返回的公开 UserID，完整显示，不截取尾号。
        log('官方 UserID：' + str(uid))
        if str(uid) in seen:
            log('☑️ 官方身份与前面已验证成功账号重复，跳过领取')
            return 'duplicate'

    def request(path):
        nonlocal token
        try:
            return api(path, token, account['device_id'])
        except Failure as exc:
            if not exc.auth or not session:
                raise
            log('⚠️ 网页令牌失效，重新换取一次；仍失效则回退桌面令牌')
            try:
                token, _ = token_for(session)
                return api(path, token, account['device_id'])
            except Failure as retry:
                if not retry.auth:
                    raise
                token = desktop(account)
                return api(path, token, account['device_id'])

    status = stage('查询签到状态', lambda: request('status'))
    if type(status.get('checked_in')) is not bool:
        raise Failure('签到状态缺少布尔 checked_in，停止领取')
    if 'enable' in status and type(status['enable']) is not bool:
        raise Failure('活动状态 enable 格式异常，停止领取')
    if status['checked_in']:
        result = 'already'
        log('☑️ 今日已签到（业务码 0，checked_in=true）')
    elif status.get('enable') is False:
        raise Failure('活动未开启，未完成签到')
    elif action == 'status':
        result = 'success'
        log('✅ 状态查询成功，今日未签到；仅查询模式不领取')
    else:
        try:
            claim = stage('领取签到积分', lambda: request('claim'))
        except Failure:
            log('⚠️ 领取未确认成功，复查账号状态')
            latest = stage('复查签到状态', lambda: request('status'))
            if latest.get('checked_in') is not True:
                raise Failure('领取失败且复查未确认已签到')
            result = 'already'
            log('☑️ 复查确认今日已签到')
        else:
            result = 'success'
            data = claim.get('data')
            points = (data.get('points', data.get('credits')) if isinstance(data, dict) else None)
            if points is None:
                points = claim.get('credits')
            reward = str(points) if type(points) in (int, float) and math.isfinite(points) else '未提供'
            log('✅ 签到成功（业务码 0），本次奖励积分：' + reward)
    if uid is not None:
        seen.add(str(uid))
    return result


def notify_worker(body, dry, queue):
    # 青龙通知为可选集成；预演调用通知入口但从进程层阻止网络与子进程。
    import subprocess
    def blocked(*args, **kwargs):
        raise RuntimeError('预演禁止外部调用')
    if dry:
        socket.socket = blocked
        socket.create_connection = blocked
        subprocess.Popen = blocked
        os.system = blocked
    paths = []
    directory = os.environ.get('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths.extend([Path(__file__).resolve().parent / 'notify.py',
                  Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for path in paths:
                if path.is_file():
                    sys.path.insert(0, str(path.parent))
                    spec = importlib.util.spec_from_file_location('notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.send('Trae CN 每日签到', body)
                    queue.put('已调用青龙通知入口' if not dry else '预演通知入口已调用（网络禁用）')
                    return
        queue.put('未找到青龙 notify.py，业务退出码不变')
    except Exception:
        queue.put('通知不可用或发送失败，业务退出码不变')


def notify(body, dry):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower() in ('0', 'false', 'no', 'off'):
        return '全局开关已关闭'
    try:
        ctx = multiprocessing.get_context('fork')
        queue = ctx.Queue()
        worker = ctx.Process(target=notify_worker, args=(body, dry, queue))
        worker.start()
        worker.join(15)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            return '通知超时，业务退出码不变'
        return queue.get(timeout=1)
    except Exception:
        return '通知不可用，业务退出码不变'


def main():
    start = time.monotonic()
    dry = os.environ.get('TRAE_DRY_RUN', '').lower() in ('1', 'true', 'yes', 'on') or '--dry-run' in sys.argv
    action = os.environ.get('TRAE_ACTION', 'checkin')
    log('========== Trae CN 每日签到 ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('完全断网预演' if dry else '正式执行') + '；动作：' + (action if action in ('status', 'checkin') else '无效'))
    lines = []
    configuration_error = False
    results = []
    totals = dict(total=0, success=0, already=0, skipped=0, failed=0)
    try:
        parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
        parser.add_argument('--session')
        parser.add_argument('--device-id')
        parser.add_argument('--dry-run', action='store_true')
        args, unknown = parser.parse_known_args()
        if unknown or action not in ('checkin', 'status'):
            raise Failure('参数错误，仅支持 --session、--device-id、--dry-run 和 TRAE_ACTION=status/checkin')
        raw = os.environ.get('TRAE_ACCOUNTS', '')
        if raw.strip() and args.session:
            raise Failure('TRAE_ACCOUNTS 与 --session 不可同时使用')
        legacy = not raw.strip()
        if legacy:
            raw = args.session if args.session is not None else os.environ.get('TRAE_SESSION', '')
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            raise Failure('未配置账号，请设置 TRAE_ACCOUNTS 或 TRAE_SESSION')
        if legacy and len(lines) > 1:
            raise Failure('多账号请使用 TRAE_ACCOUNTS，每行合并本账号凭据与设备')
        log('账号总数：%d' % len(lines))
        seen = set()
        for index, line in enumerate(lines, 1):
            began = time.monotonic()
            stats = dict(total=0, success=0, already=0, skipped=0, failed=0)
            def stage(name, fn):
                stats['total'] += 1
                timer = time.monotonic()
                log('账号 %d | 阶段 %d：%s' % (index, stats['total'], name))
                try:
                    value = fn()
                except Failure:
                    stats['failed'] += 1
                    log('❌ 阶段未成功，耗时 %.2f 秒' % (time.monotonic() - timer))
                    raise
                stats['skipped' if dry else 'success'] += 1
                log('阶段完成，耗时 %.2f 秒' % (time.monotonic() - timer))
                return value
            log('---------- 账号 %d ----------' % index)
            try:
                account = ({'session': line, 'device_id': args.device_id or os.environ.get('TRAE_DEVICE_ID', '')}
                           if legacy else json.loads(line))
                result = process(account, dry, action, seen, stage)
            except (ValueError, TypeError):
                result = 'failed'
                log('❌ 账号行 JSON 或参数格式错误（内容已隐藏）')
            except Failure as exc:
                result = 'failed'
                log('❌ ' + str(exc))
            except Exception:
                result = 'failed'
                log('❌ 未预期执行异常（详情已隐藏），继续下一账号')
            if result == 'failed' and stats['failed'] == 0:
                stats['total'] += 1
                stats['failed'] += 1
            stats['already'] += int(result == 'already')
            stats['skipped'] += int(result == 'duplicate')
            for key in totals:
                totals[key] += stats[key]
            results.append(result)
            log('账号 %d 结果：%s；总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d；耗时 %.2f 秒' %
                (index, result, stats['total'], stats['success'], int(result == 'already'), stats['skipped'], stats['failed'], time.monotonic() - began))
    except (Failure, argparse.ArgumentError):
        configuration_error = True
        log('❌ 配置错误，请按脚本顶部说明设置账号与参数')
        log('账号总数：%d' % len(lines))
    failed = results.count('failed')
    ok = len(results) - failed
    exit_code = int(configuration_error or failed > 0)
    status = ('configuration-error' if configuration_error else 'partial-failure' if failed and ok else
              'failure' if failed else 'dry-run' if dry else 'success')
    log('----------------------------------------')
    body = '状态：%s；账号总数 %d，成功 %d，失败 %d；已签到 %d，重复跳过 %d。%s' % (
        status, len(lines), ok, failed, results.count('already'), results.count('duplicate'),
        '预演只验证配置，不代表真实业务成功。' if dry else '')
    log(body)
    notification = notify(body, dry)
    log('通知状态：' + notification)
    elapsed = round(time.monotonic() - start, 2)
    finish = time.strftime('%Y-%m-%d %H:%M:%S')
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log('总耗时 %.2f 秒；完成时间：%s；最终状态：%s' % (elapsed, finish, status))
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(lines), 'success': ok, 'failed': failed, 'configuration_error': configuration_error,
          'already': results.count('already'), 'duplicate': results.count('duplicate'), 'stages': totals,
          'elapsed_seconds': elapsed, 'finish_time': finish, 'notification': notification,
          'exit_code': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
