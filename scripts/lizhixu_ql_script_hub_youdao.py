#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 有道云笔记签到
# cron: 56 1 * * *
# publish-path: scripts/youdao_cloud_note_checkin.py
# filename: youdao_cloud_note_checkin.py
# application-key: lizhixu/ql-script-hub::youdao
# canonical-product: 有道云笔记（非其他有道产品）
# 发布路径冲突修复：契约 publishPath 与本文件 PUBLISH_PATH 必须一致。
# Source: lizhixu/ql-script-hub, youdao.py
# Source commit: ac591a320092dcaeaf236b7c2b6acfd28981e589
# License: MIT (effective upstream license)
"""
cron: 56 1 * * *
new Env('有道云笔记签到')
青龙脚本：有道云笔记签到
变量名：YOUDAO_COOKIE
原版说明：支持多个账号，使用 & 或换行分隔
维护版：仅使用换行分隔账号，Cookie 内的 & 保持原样。

功能清单：刷新会话、同步奖励、每日签到、三次广告空间奖励。
获取参数：浏览器登录 https://note.youdao.com，在开发者工具 Network 中
选择已登录的 note.youdao.com 请求，复制 Request Headers 的 Cookie 值。
每行放一个账号的完整 Cookie，包含 YNOTE_PERS；不要复制 Cookie: 前缀。
YOUDAO_DRY_RUN=1 为完全断网预演；不验证 Cookie 有效性。
预演生成脱敏通知摘要并记录在 TASK_SUMMARY 中，不调用可能联网的通知模块。
唯一产品发布路径：scripts/youdao_cloud_note_checkin.py。交付文件 candidate.py
仅是修复工件名，发布时必须使用上述产品专属文件名，不能发布为 scripts/youdao.py。
可选 YOUDAO_AD_REWARDS=0 关闭广告奖励，默认 1 保留原有三次奖励。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 指向青龙通知模块目录。
通知兼容 notify.py 和 sendNotify.js；通知不可用或超时不改变业务退出码。
本脚本不会输出 Cookie 或从 Cookie 提取的身份。只显示官方 JSON 身份字段。

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
import datetime
import importlib
import importlib.util
import json
import math
import os
import re
import sys
import subprocess
import time
from pathlib import Path

TITLE = '有道云笔记签到'
PUBLISH_FILENAME = 'youdao_cloud_note_checkin.py'
PUBLISH_PATH = 'scripts/' + PUBLISH_FILENAME
DISABLED = {'0', 'false', 'no', 'off'}
BASE = 'https://note.youdao.com'


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


def enabled(name, default='1'):
    value = os.getenv(name, default).strip().lower()
    if value not in DISABLED | {'1', 'true', 'yes', 'on'}:
        raise ValueError(f'{name} 必须为 1 或 0（也支持 true/false、yes/no、on/off）')
    return value not in DISABLED


def parse_cookie(line):
    cookies = {}
    for item in line.split(';'):
        if not item.strip():
            continue
        key, sep, value = item.strip().partition('=')
        if not sep or not re.fullmatch(r'[A-Za-z0-9_!#$%*+.^`|~-]+', key) or not value.strip():
            raise ValueError('Cookie 格式错误，请复制完整请求 Cookie 值')
        if re.search(r'[\x00-\x1f\x7f]', value):
            raise ValueError('Cookie 含非法控制字符')
        cookies[key] = value.strip()
    if not cookies.get('YNOTE_PERS'):
        raise ValueError('Cookie 缺少 YNOTE_PERS，请重新获取已登录请求 Cookie')
    return cookies


def identity(data, credential_values=()):
    # Do not infer an identity from authentication/session cookies.
    for key in ('nickname', 'displayName', 'username', 'userName', 'publicUid', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            text = str(value)
            # Never display an identity field that echoes an account credential.
            if any(secret and (text == secret or (len(secret) >= 8 and secret in text))
                   for secret in credential_values):
                continue
            # Suppress credential-shaped fields, phones and log-control characters.
            if re.search(r'[\x00-\x1f\x7f]|(?:cookie|token|session)\s*[:=]|\|\|', text, re.I):
                continue
            if key not in ('publicUid', 'uid') and re.search(r'(?:\+?86)?1[3-9]\d{9}', text):
                continue
            log(f'官方账号身份（{key}）：{text}')


def request(session, method, path, field=None):
    try:
        with session.request(method, BASE + path, timeout=(10, 15),
                             allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f'HTTP 状态 {response.status_code}，未确认成功')
            raw = bytearray()
            for chunk in response.iter_content(8192):
                raw.extend(chunk)
                if len(raw) > 262144:
                    raise ValueError('响应过大，未确认成功')
            if field is None:
                # The session-refresh endpoint has no documented reward contract.
                return None
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ValueError('接口未返回有效 JSON，可能需要重新登录') from None
            if not isinstance(data, dict):
                raise ValueError('接口响应结构不符')
            if any(data.get(k) not in (None, '', False, 0, '0') for k in ('error', 'errorCode')):
                raise ValueError('接口返回业务错误，请检查 Cookie 或接口契约')
            for key in ('code', 'statusCode'):
                if key in data and data[key] not in (0, '0', 200, '200'):
                    raise ValueError('接口业务状态未确认成功')
            if data.get('success') is False:
                raise ValueError('接口明确返回失败')
            amount = data.get(field)
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError(f'缺少有效 {field} 奖励字段，未确认成功')
            identity(data, tuple(cookie.value for cookie in session.cookies))
            return amount
    except ValueError:
        raise
    except Exception:
        # Exception strings can embed URLs, cookie headers or server payloads.
        raise ValueError('网络请求失败或超时，未确认成功') from None


def account(index, line, dry, ads):
    start = time.monotonic()
    stats = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
    result = {'account': index, 'status': 'failed', 'spaceBytes': 0, 'tasks': stats}
    log(f'====== 账号 {index} ======')
    session = None
    try:
        log('阶段 0：账号参数检查')
        cookies = parse_cookie(line)
        log(f'✅ Cookie 必需字段和格式检查通过；耗时 {time.monotonic() - start:.2f} 秒；有效性由正式接口核验')
        if not dry:
            try:
                import requests
            except ImportError:
                raise ValueError('缺少 requests，请通过青龙依赖管理安装 requests') from None
            session = requests.Session()
            session.cookies.update(cookies)
        stages = [('刷新会话', 'GET', '/login/acc/pe/getsess?product=YNOTE', None),
                  ('同步奖励', 'POST', '/yws/api/daupromotion?method=sync', 'rewardSpace'),
                  ('每日签到', 'POST', '/yws/mapi/user?method=checkin', 'space')]
        stages += [(f'广告空间奖励 {n}', 'POST', '/yws/mapi/user?method=adRandomPrompt', 'space') for n in range(1, 4)]
        auth_failed = False
        for number, (name, method, path, field) in enumerate(stages, 1):
            stage_start = time.monotonic()
            stats['total'] += 1
            log(f'阶段 {number}/{len(stages)}：{name}')
            if (number > 3 and not ads) or auth_failed:
                stats['skipped'] += 1
                log(f'⏭️ 跳过：{ "广告奖励已关闭" if not auth_failed else "会话刷新失败" }；耗时 0.00 秒')
                continue
            if dry:
                stats['skipped'] += 1
                log('⏭️ 断网预演：请求未发送，业务结果未验证；耗时 0.00 秒')
                continue
            try:
                amount = request(session, method, path, field)
                stats['success'] += 1
                if amount is not None:
                    result['spaceBytes'] += amount
                    log(f'✅ 奖励字段已确认：{amount / 1048576:g}M；耗时 {time.monotonic() - stage_start:.2f} 秒')
                else:
                    log(f'✅ HTTPS 会话刷新请求完成；耗时 {time.monotonic() - stage_start:.2f} 秒')
            except ValueError as exc:
                stats['failed'] += 1
                log(f'❌ {exc}；耗时 {time.monotonic() - stage_start:.2f} 秒')
                auth_failed = number == 1
        result['status'] = 'dry-run' if dry else ('failed' if stats['failed'] else 'success')
    except ValueError as exc:
        stats['total'] += 1
        stats['failed'] += 1
        result['status'] = 'configuration-error'
        log(f'❌ 参数检查：{exc}')
    except Exception:
        # Keep unexpected runtime failures isolated and never echo credentials.
        stats['total'] += 1
        stats['failed'] += 1
        result['status'] = 'failed'
        log('❌ 账号执行发生运行异常，未确认成功')
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                # Cleanup must not prevent the next account or final notification.
                log('⚠️ 会话资源关闭异常，保留已记录业务结果')
    result['durationSeconds'] = round(time.monotonic() - start, 3)
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {result["durationSeconds"]:.2f} 秒；状态 {result["status"]}')
    log(f'获取空间: +{result["spaceBytes"] / 1048576:g}M（仅累计已验证奖励）')
    return result


def notification_body(summary):
    return (f'状态：{summary["status"]}\n账号总数：{summary["accountCount"]}'
            f'\n成功数：{summary["successCount"]}\n失败数：{summary["failedCount"]}'
            f'\n预演数：{summary["dryRunCount"]}'
            f'\n全局配置错误数：{int(bool(summary.get("configurationError")))}')


def _notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('⏭️ 通知已关闭')
        return 'disabled'
    if dry:
        log('⏭️ 断网预演：已生成脱敏通知摘要，未调用通知模块')
        return 'dry-run'
    body = notification_body(summary)
    try:
        module = None
        try:
            module = importlib.import_module('notify')
        except ImportError:
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
            paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, 'send', None)):
            paths = []
            if os.getenv('QINGLONG_NOTIFY_DIR'):
                paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'sendNotify.js')
            paths += [Path('/ql/data/scripts/sendNotify.js'), Path('/ql/scripts/sendNotify.js')]
            for path in paths:
                if path.is_file():
                    # Only the optional Qinglong notification helper uses Node;
                    # account HTTP behavior remains implemented in this script.
                    worker = ("const fs=require('fs');"
                              "const p=JSON.parse(fs.readFileSync(0,'utf8'));"
                              "Promise.resolve().then(()=>require(process.argv[1]).sendNotify(p.title,p.body))"
                              ".then(()=>process.exit(0)).catch(()=>process.exit(1));")
                    delivery = subprocess.run(
                        ['node', '-e', worker, str(path.resolve())],
                        input=json.dumps({'title': TITLE, 'body': body}, ensure_ascii=False),
                        text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=20, check=False)
                    return 'sent' if delivery.returncode == 0 else 'failed'
            log('⚠️ 通知模块不可用，保留业务退出码')
            return 'unavailable'
        # Notification helpers may echo their configuration or provider responses.
        import contextlib
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module.send(TITLE, body)
        log('✅ 脱敏摘要已提交通知模块')
        return 'sent'
    except Exception:
        log('⚠️ 通知发送失败，保留业务退出码')
        return 'failed'


def notify(summary, dry):
    body = notification_body(summary)
    # The offline summary is also the exact body supplied for live notification.
    summary['notificationSummary'] = body
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        result = 'disabled'
    elif dry:
        # Never import notification modules during an offline rehearsal.
        result = 'dry-run'
    else:
        worker = ("import json,runpy,sys; "
                  "m=runpy.run_path(sys.argv[1],run_name='qinglong_notification_worker'); "
                  "r=m['_notify'](json.loads(sys.stdin.read()),False); "
                  "sys.exit({'sent':0,'unavailable':2,'failed':3,'disabled':4}.get(r,3))")
        try:
            completed = subprocess.run(
                [sys.executable, '-c', worker, str(Path(__file__).resolve())],
                input=json.dumps(summary, ensure_ascii=False), text=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30, check=False)
            result = {0: 'sent', 2: 'unavailable', 4: 'disabled'}.get(completed.returncode, 'failed')
        except (OSError, subprocess.TimeoutExpired):
            result = 'failed'
    messages = {
        'disabled': '⏭️ 通知已关闭',
        'dry-run': '⏭️ 断网预演：脱敏通知摘要已生成，未调用联网通知模块',
        'unavailable': '⚠️ 通知模块不可用，保留业务退出码',
        'failed': '⚠️ 通知发送失败或超过 30 秒，保留业务退出码',
        'sent': '✅ 脱敏摘要已提交通知模块',
    }
    log(messages[result])
    return result


def main():
    start = time.monotonic()
    start_time = datetime.datetime.now().isoformat(timespec='seconds')
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{start_time}')
    log(f'产品专属发布路径：{PUBLISH_PATH}')
    # Detect dry-run before validating other options so configuration errors stay offline.
    dry = os.getenv('YOUDAO_DRY_RUN', '0').strip().lower() not in DISABLED
    lines = [line.strip() for line in os.getenv('YOUDAO_COOKIE', '').splitlines() if line.strip()]
    log(f'运行模式：{"断网预演" if dry else "正式运行"}；账号数量：{len(lines)}')
    results = []
    config_error = False
    try:
        dry = enabled('YOUDAO_DRY_RUN', '0')
        ads = enabled('YOUDAO_AD_REWARDS')
        if not lines:
            raise ValueError('必须设置 YOUDAO_COOKIE，每行一个已登录账号 Cookie')
        for index, line in enumerate(lines, 1):
            results.append(account(index, line, dry, ads))
    except ValueError as exc:
        config_error = True
        log(f'❌ 配置错误：{exc}')
    failed = sum(r['status'] in ('failed', 'configuration-error') for r in results)
    success = sum(r['status'] == 'success' for r in results)
    status = 'configuration-error' if config_error else ('partial-failure' if failed and (success or len(results) > failed) else 'failure' if failed else 'dry-run' if dry else 'success')
    code = int(config_error or failed > 0)
    summary = dict(publishPath=PUBLISH_PATH, filename=PUBLISH_FILENAME, startTime=start_time, status=status, mode='dry-run' if dry else 'live', accountCount=len(lines),
                   successCount=success, failedCount=failed, dryRunCount=sum(r['status'] == 'dry-run' for r in results),
                   configurationError=config_error, accounts=results, exitCode=code)
    summary['notification'] = notify(summary, dry)
    summary['durationSeconds'] = round(time.monotonic() - start, 3)
    summary['finishTime'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log(f'最终任务统计：账号 {len(lines)}，成功 {success}，失败 {failed}，预演 {summary["dryRunCount"]}；配置错误 {config_error}')
    totals = {key: sum(r['tasks'][key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    summary['tasks'] = totals
    log(f'子任务统计：总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'总耗时：{summary["durationSeconds"]:.2f} 秒；完成时间：{summary["finishTime"]}；通知状态：{summary["notification"]}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
