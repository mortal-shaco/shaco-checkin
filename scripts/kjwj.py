#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 科技玩家签到
# cron: 41 2 * * *
# 来源: cloudcranes/some_scripts，原文件 kjwj.py
# 原提交: f62b50fe0a961ea8a8707682723b080c0a5d1142
# 上游许可及本维护版本许可: MIT
# MIT License
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
"""科技玩家签到：在官网注册账号，设置 kjwj_info 为邮箱#密码，每行一个账号。
仅首个 # 为分隔符，密码中后续 #、&、@ 原样保留。每天 07:30 执行。
KJWJ_DRY_RUN=1 完全断网预演；QINGLONG_NOTIFY=0 关闭通知。
仅执行登录、查询、必要的签到；不会发布内容或修改资料。
"""
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

HOST = 'https://www.kejiwanjia.net'
TITLE = '科技玩家签到'
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), message), flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 登录密码与令牌不得被重定向到其他地址。
        return None


def request(endpoint, token=None, fields=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
        'Origin': HOST, 'Referer': HOST,
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    if token:
        headers.update({'Authorization': 'Bearer ' + token, 'Cookie': 'b2_token=' + token + ';'})
    data = urllib.parse.urlencode(fields or {}).encode('utf-8')
    req = urllib.request.Request(HOST + endpoint, data=data, headers=headers, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as res:
            if res.status != 200:
                raise TaskError('接口 HTTP 状态异常')
            body = res.read(262145)
        if len(body) > 262144:
            raise TaskError('接口响应过大')
        result = json.loads(body)
    except TaskError:
        raise
    except Exception:
        raise TaskError('接口网络、超时或响应解析失败') from None
    if not isinstance(result, dict):
        raise TaskError('接口响应结构异常')
    if result.get('code') or result.get('error') or result.get('success') is False:
        raise TaskError('接口返回业务错误')
    return result


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TaskError('积分字段无效')
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        raise TaskError('积分字段无效') from None
    if not math.isfinite(n) or n < 0:
        raise TaskError('积分字段无效')
    return n


def mission(result):
    m = result.get('mission')
    if not isinstance(m, dict):
        raise TaskError('缺少签到状态字段')
    return number(m.get('credit')), number(m.get('my_credit'))


def identity(result, username, password, token):
    for key in ('name', 'user_display_name', 'nickname', 'display_name', 'username', 'user_nicename', 'uid'):
        value = result.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 仅显示非秘密官方身份，防止字段错误地包含凭据或手机号。
            if (not value or any(secret and secret in value for secret in (username, password, token))
                    or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value)):
                continue
            log('官方账号身份：' + json.dumps(value, ensure_ascii=False))
            break


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('通知：已关闭')
        return 'disabled'
    if dry:
        log('通知：断网预演，脱敏摘要：' + body)
        return 'dry-run'
    try:
        # 第三方通知导入及发送输出可能包含推送凭据，隔离全部输出。
        import contextlib
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                paths = []
                folder = os.getenv('QINGLONG_NOTIFY_DIR')
                if folder:
                    paths.append(Path(folder) / 'notify.py')
                paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
                path = next((p for p in paths if p.is_file()), None)
                if path is None:
                    raise RuntimeError()
                spec = importlib.util.spec_from_file_location('qinglong_task_notify', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            module.send(TITLE, body)
        log('通知：已提交')
        return 'sent'
    except Exception:
        log('⚠️ 通知不可用或发送失败，保留业务退出码')
        return 'unavailable'


def main():
    started = time.monotonic()
    dry = os.getenv('KJWJ_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    accounts = [line.strip() for line in os.getenv('kjwj_info', '').splitlines() if line.strip()]
    log('========== 科技玩家签到 ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('断网预演' if dry else '正式执行'))
    log('账号总数：%d' % len(accounts))
    results = []
    totals = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    for index, line in enumerate(accounts, 1):
        account_start = time.monotonic()
        stats = {'total': 3, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
        stage = 1
        stage_start = time.monotonic()
        log('账号 %d / 阶段 1：参数校验与登录' % index)
        try:
            if '#' not in line:
                raise TaskError('账号配置需为邮箱#密码，每行一个账号')
            username, password = line.split('#', 1)
            if not username or not password:
                raise TaskError('账号邮箱或密码为空')
            if dry:
                log('✅ 参数格式有效；登录请求已预演，未访问网络')
                token = None
            else:
                response = request('/wp-json/jwt-auth/v1/token', fields={'username': username, 'password': password})
                token = response.get('token')
                if not isinstance(token, str) or not token or any(c.isspace() or ord(c) < 32 for c in token):
                    raise TaskError('登录未返回有效令牌')
                identity(response, username, password, token)
                log('✅ 登录成功')
            stats['success'] += 1
            log('阶段 1 耗时 %.2f 秒' % (time.monotonic() - stage_start))
            stage = 2
            stage_start = time.monotonic()
            log('账号 %d / 阶段 2：查询签到与积分' % index)
            if dry:
                credit, total = 0, 0
                log('⏭️ 状态查询已预演，未访问网络')
                stats['skipped'] += 1
            else:
                credit, total = mission(request('/wp-json/b2/v1/getUserMission', token))
                log('✅ 当日签到积分：%g；总积分：%g' % (credit, total))
                stats['success'] += 1
            log('阶段 2 耗时 %.2f 秒' % (time.monotonic() - stage_start))
            stage = 3
            stage_start = time.monotonic()
            log('账号 %d / 阶段 3：签到' % index)
            if dry:
                stats['skipped'] += 1
                log('⏭️ DRY_RUN_OK：签到已预演，未修改账号状态')
            elif credit > 0:
                stats['alreadyComplete'] += 1
                log('☑️ 今天已经签到；获得 %g 积分；总积分：%g' % (credit, total))
            else:
                signed = request('/wp-json/b2/v1/userMission', token)
                awarded = number(signed.get('credit'))
                signed_mission = signed.get('mission')
                if not isinstance(signed_mission, dict):
                    raise TaskError('签到响应缺少积分状态')
                total = number(signed_mission.get('my_credit'))
                if awarded <= 0:
                    raise TaskError('签到响应未确认获得积分')
                confirmed_credit, total = mission(request('/wp-json/b2/v1/getUserMission', token))
                if confirmed_credit <= 0:
                    raise TaskError('签到后复查未确认完成')
                stats['success'] += 1
                log('✅ 签到成功 获得 %g 积分；总积分：%g' % (awarded, total))
            log('阶段 3 耗时 %.2f 秒' % (time.monotonic() - stage_start))
            status = 'dry-run' if dry else 'success'
        except Exception as exc:
            stats['failed'] += 1
            stats['skipped'] += 3 - stage
            status = 'failure'
            log('❌ 阶段 %d 失败：%s；耗时 %.2f 秒' % (stage, str(exc) if isinstance(exc, TaskError) else '内部处理失败', time.monotonic() - stage_start))
        for key in totals:
            totals[key] += stats[key]
        elapsed = round(time.monotonic() - account_start, 2)
        log('账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d；耗时 %.2f 秒' % (index, stats['total'], stats['success'], stats['alreadyComplete'], stats['skipped'], stats['failed'], elapsed))
        results.append({'account': index, 'status': status, 'statistics': stats, 'elapsedSeconds': elapsed})
    failed = sum(r['status'] == 'failure' for r in results)
    successful = len(results) - failed
    exit_code = 1 if failed or not accounts else 0
    status = 'configuration-error' if not accounts else ('partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry else 'success')
    if not accounts:
        log('❌ 配置错误：请在青龙设置 kjwj_info，邮箱#密码，每行一个账号')
    body = '账号总数：%d；成功数：%d；失败数：%d；最终状态：%s' % (len(accounts), successful, failed, status)
    delivery = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    elapsed = round(time.monotonic() - started, 2)
    log('总耗时：%.2f 秒；完成时间：%s；通知状态：%s' % (elapsed, time.strftime('%Y-%m-%d %H:%M:%S'), delivery))
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status, 'accounts': len(accounts), 'success': successful, 'failed': failed, 'statistics': totals, 'results': results, 'notification': delivery, 'elapsedSeconds': elapsed, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
