#!/usr/bin/env python3
# name: 沪上阿姨签到
# cron: 0 9,18 * * *
# author: 清风; upstream: Rookie-wb-WH/ql_scripts/hsay.py
# SPDX-License-Identifier: MIT
# MIT License (effectiveLicense: MIT)
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
# 上游更新记录：2024-09-11 增加签到。
"""沪上阿姨微信小程序签到，Python 3.9+，仅使用标准库。
登录自己的小程序，通过本地抓包取得 webapi.qmai.cn 请求头 Qm-User-Token。
hsayCookie 每个非空行填写一个完整 Token；兼容文档中的 HSAYCookie 别名。
不再使用 @ 分隔账号；Token 内容不拆分。HSAY_DRY_RUN=1 完全断网预演。
保留每日 9、18 点计划。实际运行会签到领取奖励，不发帖、不消费积分。
上游的 appid、活动和门店参数原样保留；接口过期时失败退出，不猜测接口。
通知默认开启；QINGLONG_NOTIFY=0 关闭，QINGLONG_NOTIFY_DIR 指定青龙通知目录。
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TITLE = '沪上阿姨签到'
APPID = 'wxd92a2d29f8022f40'
ACTIVITY = '1004435002421583872'
STORE = 201424
BASE = 'https://webapi.qmai.cn/web/'
STAGES = ['用户信息', '积分流水用户标识', '签到详情', '签到领取奖励']
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def clean(value, tokens):
    text = str(value)
    for token in tokens:
        if token:
            text = text.replace(token, '[凭据已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，避免凭据发送至其他接口')


def request(token, path, payload, method='POST'):
    headers = {
        'Content-Type': 'application/json', 'Qm-From': 'wechat',
        'Qm-From-Type': 'catering', 'Qm-User-Token': token,
        'Referer': 'https://servicewechat.com/wxafec6f8422cb357b/186/page-frame.html',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.40(0x18002831) NetType/WIFI Language/zh_CN',
    }
    url = BASE + path
    body = None
    if method == 'GET':
        url += '?' + urllib.parse.urlencode(payload)
    else:
        body = json.dumps(payload).encode('utf-8')
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise TaskError('响应超过大小限制')
        result = json.loads(raw)
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 请求失败，状态码 {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None
    if not isinstance(result, dict) or result.get('status') is not True:
        raise TaskError('接口未明确返回 status=true；请检查登录凭据和活动有效性')
    if not isinstance(result.get('data'), dict):
        raise TaskError('接口数据结构改变')
    return result['data']


def signature(timestamp, uid):
    fields = {'activityId': ACTIVITY, 'sellerId': STORE, 'timestamp': timestamp, 'userId': uid}
    content = '&'.join(f'{k}={v}' for k, v in sorted(fields.items())) + '&key=' + ACTIVITY[::-1]
    return hashlib.md5(content.encode()).hexdigest().upper()


def run_account(index, token, dry, tokens):
    start = time.monotonic()
    counts = dict(total=4, success=0, alreadyComplete=0, skipped=0, failure=0)
    uid = None
    days = None
    ready = True
    log(f'========== 第 {index} 个账号 ==========')
    for number, name in enumerate(STAGES, 1):
        step_start = time.monotonic()
        log(f'账号 {index} 阶段 {number}/4：{name}')
        try:
            if dry:
                counts['skipped'] += 1
                log('⏭️ 断网预演：凭据格式通过，已跳过 HTTP 请求和账号状态变更')
                continue
            if number == 4 and (not ready or uid is None or days is None):
                counts['skipped'] += 1
                log('⏭️ 前置检查失败，跳过签到')
                continue
            if number == 1:
                data = request(token, 'catering2-apiserver/crm/personal-info', {'appid': APPID}, 'GET')
                if not isinstance(data.get('name'), str):
                    raise TaskError('用户信息缺少昵称')
                log('✅ 用户昵称：' + clean(data['name'], tokens))
            elif number == 2:
                data = request(token, 'mall-apiserver/integral/user/page/customer-points-flow', {'pageNo': 1, 'pageSize': 15, 'appid': APPID})
                rows = data.get('data')
                if not isinstance(rows, list):
                    raise TaskError('积分流水结构改变')
                uid = next((r['customerId'] for r in rows if isinstance(r, dict) and isinstance(r.get('customerId'), (str, int)) and not isinstance(r['customerId'], bool) and str(r['customerId']).strip() not in {'', '0'}), None)
                if uid is None:
                    raise TaskError('积分流水中未找到 customerId，不能生成有效签名')
                log('✅ 用户公开 UID：' + clean(uid, tokens))
            elif number == 3:
                data = request(token, 'cmk-center/sign/userSignStatistics', {'activityId': ACTIVITY, 'appid': APPID})
                days = data.get('signDays')
                if type(days) is not int or days < 0:
                    days = None
                    raise TaskError('签到详情缺少有效 signDays')
                log(f'✅ 已连续签到 {days} 天')
            else:
                timestamp = str(int(time.time() * 1000))
                data = request(token, 'cmk-center/sign/takePartInSign', {'activityId': ACTIVITY, 'storeId': STORE, 'timestamp': timestamp, 'appid': APPID, 'signature': signature(timestamp, uid)})
                rewards = data.get('rewardDetailList')
                if not isinstance(rewards, list) or not rewards:
                    raise TaskError('接口已接收签到但缺少可核验奖励，禁止自动重试')
                for reward in rewards:
                    if not isinstance(reward, dict) or not isinstance(reward.get('rewardName'), str) or type(reward.get('sendNum')) not in (int, float) or reward['sendNum'] < 0:
                        raise TaskError('奖励字段变化，不能确认签到结果；禁止自动重试')
                for reward in rewards:
                    log(f'✅ 签到奖励：{clean(reward["rewardName"], tokens)}，数量 {reward["sendNum"]}')
                log(f'✅ 签到成功，连续签到 {days + 1} 天（根据签到前详情计算）')
            counts['success'] += 1
        except TaskError as exc:
            ready = False
            counts['failure'] += 1
            log('❌ ' + str(exc))
        except Exception:
            ready = False
            counts['failure'] += 1
            log('❌ 数据处理异常，已隐藏异常内容')
        finally:
            log(f'阶段 {number} 耗时 {time.monotonic() - step_start:.2f} 秒')
    counts['elapsedSeconds'] = round(time.monotonic() - start, 2)
    counts['account'] = index
    log(f'账号 {index} 统计：总任务 4，成功 {counts["success"]}，已完成 0，跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {counts["elapsedSeconds"]} 秒')
    return counts


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    # 通知子进程隔离输出，避免第三方通知模块打印凭据；预演禁止套接字通信。
    code = '''import sys, os, socket, importlib.util
if sys.argv[1] == '1':
 def deny(*args, **kwargs): raise OSError('dry-run network disabled')
 socket.socket = deny
 socket.create_connection = deny
 socket.getaddrinfo = deny
 socket.gethostbyname = deny
 socket.gethostbyname_ex = deny
paths = [os.path.join(os.environ.get('QINGLONG_NOTIFY_DIR', ''), 'notify.py'), '/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
try:
 import notify
except ImportError:
 notify = None
 for path in paths:
  if os.path.isfile(path):
   spec = importlib.util.spec_from_file_location('notify', path)
   notify = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(notify)
   break
if notify is None: sys.exit(2)
notify.send(sys.argv[2], sys.argv[3])
'''
    try:
        result = subprocess.run([sys.executable, '-c', code, '1' if dry else '0', TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if dry:
            return '预演通知模块已返回（网络禁止）' if result.returncode == 0 else '预演通知不可用或网络投递被阻止'
        return '通知模块已返回' if result.returncode == 0 else '通知不可用或失败'
    except (OSError, subprocess.TimeoutExpired):
        return '通知不可用或超时'


def main():
    started = stamp()
    begin = time.monotonic()
    dry = os.getenv('HSAY_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    raw = os.getenv('hsayCookie') or os.getenv('HSAYCookie', '')
    tokens = [line.strip() for line in raw.splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{started}；模式：{"断网预演" if dry else "实际签到"}；账号数：{len(tokens)}')
    results = []
    config_error = not tokens
    if config_error:
        log('❌ 配置错误：请设置 hsayCookie，每个非空行一个账号 Token')
    for index, token in enumerate(tokens, 1):
        results.append(run_account(index, token, dry, tokens))
    failed = sum(r['failure'] > 0 for r in results)
    successful = len(results) - failed
    status = 'configuration-error' if config_error else 'partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry else 'success'
    exit_code = 1 if config_error or failed else 0
    body = f'状态：{status}；账号总数：{len(tokens)}；成功：{0 if dry else successful}；失败：{failed}；预演通过：{successful if dry else 0}'
    notification = notify(body, dry)
    summary = {'task': TITLE, 'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(tokens), 'success': 0 if dry else successful, 'failure': failed, 'dryRunPassed': successful if dry else 0, 'accountResults': results, 'subtasks': {key: sum(r[key] for r in results) for key in ['total', 'success', 'alreadyComplete', 'skipped', 'failure']}, 'startTime': started, 'finishTime': stamp(), 'elapsedSeconds': round(time.monotonic() - begin, 2), 'notification': notification, 'exitCode': exit_code}
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：{json.dumps(summary["subtasks"], ensure_ascii=False)}')
    log(f'完成时间：{summary["finishTime"]}；总耗时：{summary["elapsedSeconds"]} 秒；通知：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
