#!/usr/bin/env python3
# coding: utf-8
# name: WPS打卡活动信息
# cron: 43 1 * * *
# 原作：cloudcranes/some_scripts，invalid/wps_clock_in.py
# 原始功能声明：功能：WPS打卡活动；new Env('WPS打卡活动信息');
# 上游与维护版本许可：MIT
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
"""WPS活动查询，每日09:10。wps_ck：每个非空行一个wps_sid值。
在WPS主页或微信小程序【我的WPS超级会员】登录后，从本人授权的
*.wps.cn请求Cookie中取得wps_sid的值（不要填整个Cookie）。
不支持用&或@分隔账号。不提交打卡，不把奖励列表当作打卡成功证据。
WPS_DRY_RUN=1完全断网预演；QINGLONG_NOTIFY=0关闭通知。
只依赖Python标准库；notify.py为可选青龙通知集成，不影响业务退出码。
"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

TITLE = 'WPS打卡活动信息'
AUTH_URL = 'https://account.wps.cn/p/auth/check'
INFO_URL = 'https://personal-bus.wps.cn/activity/clock_in/v1/info?client_type=1&page_index=0&page_size=2'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.47(0x18002f28) NetType/WIFI Language/zh_CN'
SECRETS = []


def safe(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())[:200]


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口发生重定向，已拒绝传递凭据')


def request_json(url, method, sid):
    headers = {'Cookie': f'wps_sid={sid};csrf=1234567890',
               'X-CSRFToken': '1234567890', 'User-Agent': UA}
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP状态不符合成功要求')
            raw = response.read(262145)
        if len(raw) > 262144:
            raise TaskError('接口响应超过大小限制')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError('接口响应结构异常')
        # 未知业务结构不猜测成功；不以HTTP 200作为业务成功。
        markers = []
        if 'code' in result:
            markers.append(type(result['code']) is int and result['code'] == 0)
        if 'result' in result:
            markers.append(result['result'] == 'ok')
        if not markers or not all(markers):
            raise TaskError('业务成功标志缺失或表示失败，请核对接口与凭据')
        return result
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP请求失败（状态{exc.code}）') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('接口未返回有效JSON') from None


def notify(body, dry_run):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in {'0', 'false', 'no', 'off'}:
        log('⏭️ 通知：全局开关已关闭')
        return 'disabled'
    if dry_run:
        log('⏭️ 通知：断网预演，模拟发送脱敏总结：' + body)
        return 'dry-run'
    try:
        try:
            import notify as module
        except ImportError:
            paths = []
            directory = os.getenv('QINGLONG_NOTIFY_DIR')
            if directory:
                paths.append(Path(directory) / 'notify.py')
            paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
            path = next((p for p in paths if p.is_file()), None)
            if path is None:
                log('⚠️ 通知：未找到青龙notify.py，保留业务退出码')
                return 'unavailable'
            spec = importlib.util.spec_from_file_location('qinglong_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # 通知库的输出不属于本脚本业务日志，防止其回显配置或凭据。
        import contextlib
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module.send(TITLE, body)
        log('✅ 通知：脱敏总结已交付青龙通知模块')
        return 'sent'
    except Exception:
        log('⚠️ 通知：发送失败，保留业务退出码')
        return 'failed'


def main():
    started = time.monotonic()
    dry = os.getenv('WPS_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    accounts = [line.strip() for line in os.getenv('wps_ck', '').splitlines() if line.strip()]
    SECRETS.extend(accounts)
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}；模式：' + ('断网预演' if dry else '活动查询'))
    log(f'账号总数：{len(accounts)}；不提交打卡')
    results = []
    config_error = not accounts
    if config_error:
        log('❌ 配置错误：请设置wps_ck，每个非空行填写一个wps_sid值')
    for index, sid in enumerate(accounts, 1):
        account_started = time.monotonic()
        stats = {'total': 2, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
        failed = False
        log(f'账号{index} 开始')
        for stage, label in [(1, '账号身份查询'), (2, '活动奖励与连续天数查询')]:
            stage_started = time.monotonic()
            log(f'账号{index} 阶段{stage}/2：{label}')
            try:
                if failed:
                    stats['skipped'] += 1
                    log('⏭️ 身份验证失败，跳过活动请求')
                    continue
                if not re.fullmatch(r'[\x21-\x7e]+', sid) or any(c in sid for c in ';,\"\\'):
                    config_error = True
                    raise TaskError('账号参数格式错误，请仅填写wps_sid值，不使用账号分隔符或完整Cookie')
                if dry:
                    log(f'✅ DRY_RUN_OK 账号{index}：参数已检查，模拟{label}，未发送请求')
                elif stage == 1:
                    data = request_json(AUTH_URL, 'POST', sid)
                    nickname = data.get('nickname')
                    if not isinstance(nickname, str) or not nickname.strip():
                        raise TaskError('账号接口缺少有效昵称，无法确认身份')
                    log('✅ 身份查询成功，昵称：' + safe(nickname))
                else:
                    response = request_json(INFO_URL, 'GET', sid)
                    data = response.get('data')
                    if not isinstance(data, dict):
                        raise TaskError('活动数据缺失')
                    days = data.get('continuous_days')
                    reward = data.get('reward_list')
                    rewards = reward.get('list') if isinstance(reward, dict) else None
                    if type(days) is not int or days < 0 or not isinstance(rewards, list):
                        raise TaskError('连续天数或奖励列表结构异常')
                    log(f'✅ 活动信息查询成功，持续打卡天数：{days}')
                    if rewards:
                        item = rewards[0]
                        if not isinstance(item, dict):
                            raise TaskError('奖励条目结构异常')
                        name = item.get('sku_name') or item.get('mb_name')
                        if not isinstance(name, str) or not name.strip():
                            raise TaskError('奖励名称缺失')
                        log('奖励名称：' + safe(name))
                    else:
                        log('奖励列表为空；不能据此确认今日打卡成功')
                stats['success'] += 1
            except TaskError as exc:
                failed = True
                stats['failed'] += 1
                log('❌ ' + str(exc))
            except Exception:
                failed = True
                stats['failed'] += 1
                log('❌ 执行异常，未确认业务成功')
            finally:
                log(f'账号{index} 阶段{stage}耗时：{time.monotonic() - stage_started:.2f}秒')
        results.append({'account': index, 'status': 'failure' if failed else ('dry-run' if dry else 'success'), **stats})
        log(f'账号{index}统计：总任务{stats["total"]}，成功{stats["success"]}，已完成0，跳过{stats["skipped"]}，失败{stats["failed"]}；耗时{time.monotonic() - account_started:.2f}秒')
    failures = sum(r['status'] == 'failure' for r in results)
    successes = len(results) - failures
    status = ('configuration-error' if config_error else 'partial-failure' if failures and successes else 'failure' if failures else 'dry-run' if dry else 'success')
    code = 1 if config_error or failures else 0
    body = f'状态：{status}；账号总数：{len(accounts)}；成功数：{successes}；失败数：{failures}。仅查询活动信息，未提交或确认今日打卡。'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(r[key] for r in results) for key in ['total', 'success', 'alreadyComplete', 'skipped', 'failed']}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；总耗时：{time.monotonic() - started:.2f}秒；通知状态：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(accounts), 'success': successes, 'failed': failures, 'configurationError': config_error, 'tasks': totals, 'results': results, 'notification': notification, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
