#!/usr/bin/env python3
# name: 塔斯汀汉堡签到
# cron: 19 1 * * *
"""塔斯汀汉堡签到，Python 3 标准库实现。
来源：agluo/ql-script-hub/tsthb_checkin.py；原始署名来源 https://raw.githubusercontent.com/linbailo/zyqinglong
上游许可：MIT。
在微信塔斯汀小程序登录后，用本人授权的抓包工具读取
sss-web.tastientech.com 请求头 user-token，填入 tsthbck，每个非空行一个账号。
不要填整个请求头，不使用 & 或 @ 分隔账号。Token 过期后重新获取。
TSTHB_DRY_RUN=1 完全断网预演（通知只展示脱敏摘要，不调用通知模块）。
RANDOM_SIGNIN 默认 true；MAX_RANDOM_DELAY 默认 3600 秒；QINGLONG_NOTIFY 未设置时按上架状态。
限时执行或验证时设置 RANDOM_SIGNIN=false，跳过随机等待；每日调度保持不变。
每次 HTTP 请求最多 20 秒（包含解析），不自动重试签到，避免重复提交。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('82616d06df4e5f53', 'scripts/tsthb_checkin.py', 'tsthb_checkin.py', 'tsthb_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import json
import multiprocessing
import os
import random
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

TITLE = '塔斯汀汉堡签到'
BASE = 'https://sss-web.tastientech.com'
DISABLED = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_once(token, path, data=None):
    headers = {'user-token': token, 'version': '1.46.8', 'channel': '1',
               'Content-Type': 'application/json'}
    body = None if data is None else json.dumps(data).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=body, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超过大小限制')
            payload = json.loads(raw)
    except TaskError:
        raise
    except Exception:
        raise TaskError('HTTP、网络或响应解析失败（详细响应已隐藏）') from None
    if not isinstance(payload, dict) or type(payload.get('code')) is not int or payload['code'] != 200:
        raise TaskError('接口未返回可验证的业务成功码 200')
    return payload.get('result')


def _request_worker(connection, token, path, data):
    """HTTP 在独立进程执行，让 DNS、慢速响应及解析也受整体时限约束。"""
    try:
        connection.send((True, _request_once(token, path, data)))
    except TaskError as exc:
        connection.send((False, str(exc)))
    except Exception:
        connection.send((False, 'HTTP 请求失败（详细异常已隐藏）'))
    finally:
        connection.close()


def request(token, path, data=None):
    context = multiprocessing.get_context('spawn')
    # HTTP 完成后才通过管道回传结果；响应读取大小限制为 1 MiB。
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_request_worker, args=(sender, token, path, data))
    try:
        process.start()
        sender.close()
        if not receiver.poll(20):
            raise TaskError('HTTP 请求超过 20 秒整体时限；未自动重试，请稍后核对签到状态')
        try:
            ok, result = receiver.recv()
        except (EOFError, OSError):
            raise TaskError('HTTP 工作进程未返回有效结果') from None
        if not ok:
            raise TaskError(result)
        return result
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()


def safe(value, secrets):
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())[:300]


def activity(token):
    result = request(token, '/api/minic/shop/intelligence/banner/c/list',
                     {'shopId': '', 'birthday': '', 'gender': 0, 'nickName': None, 'phone': ''})
    if not isinstance(result, list):
        raise TaskError('活动列表格式不正确')
    matches = [x for x in result if isinstance(x, dict) and '签到' in str(x.get('bannerName', ''))]
    matches.sort(key=lambda x: '每日签到' not in str(x.get('bannerName', '')))
    for item in matches:
        try:
            para = item['jumpPara']
            para = json.loads(para) if isinstance(para, str) else para
            value = para['activityId']
            if type(value) in (str, int) and str(value).strip():
                return value
        except (ValueError, KeyError, TypeError):
            continue
    raise TaskError('未发现有效签到活动，停止签到，不猜测活动编号')


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    if dry:
        log('通知预演：' + body)
        return '预演已展示（未联网）'
    # 使用子进程隔离通知输出及异常，防止通知模块打印配置中的凭据。
    code = '''import importlib.util, os, sys
try:
    from notify import send
except ImportError:
    send = None
    roots = [os.getenv("QINGLONG_NOTIFY_DIR", ""), "/ql/data/scripts", "/ql/scripts"]
    for root in roots:
        path = os.path.join(root, "notify.py") if root else ""
        if path and os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, root)
            spec.loader.exec_module(mod)
            send = mod.send
            break
if send is None:
    sys.exit(2)
send(sys.argv[1], sys.argv[2])
'''
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return '已发送' if result.returncode == 0 else '不可用或发送失败'
    except Exception:
        return '不可用或发送失败'


def main():
    started = time.monotonic()
    dry = os.getenv('TSTHB_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    tokens = [line.strip() for line in os.getenv('tsthbck', '').splitlines() if line.strip()]
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.now().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式"}；账号数：{len(tokens)}')
    config_error = False
    try:
        delay_max = int(os.getenv('MAX_RANDOM_DELAY', '3600'))
        if delay_max < 0:
            raise ValueError
        if not tokens:
            raise ValueError
    except ValueError:
        config_error = True
        log('❌ 配置错误：需要非空 tsthbck，MAX_RANDOM_DELAY 必须为非负整数')
    successes = failures = 0
    totals = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    if not config_error:
        delay = random.randint(0, delay_max) if os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true' else 0
        log(f'阶段 0 随机延迟：{"预演跳过" if dry else str(delay) + " 秒"}')
        remaining = delay if not dry else 0
        while remaining:
            log(f'等待倒计时：{remaining} 秒')
            step = min(60, remaining)
            time.sleep(step)
            remaining -= step
        for number, token in enumerate(tokens, 1):
            account_start = time.monotonic()
            stats = {'total': 3, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            secrets = tokens[:]
            failed = False
            for stage, label in enumerate(['查询当前签到活动', '校验账号身份', '提交每日签到并读取奖励'], 1):
                step_start = time.monotonic()
                log(f'账号 {number} 阶段 {stage}/3：{label}')
                try:
                    if failed or dry:
                        stats['skipped'] += 1
                        log('⏭️ ' + ('断网预演：未发出请求' if dry else '前置阶段失败，跳过'))
                    elif stage == 1:
                        activity_id = activity(token)
                        stats['success'] += 1
                        log('✅ 已从官方活动列表确认签到活动')
                    elif stage == 2:
                        member = request(token, '/api/intelligence/member/getMemberDetail')
                        if not isinstance(member, dict) or not isinstance(member.get('phone'), str) or not member['phone']:
                            raise TaskError('账号资料缺少签到所需手机号')
                        phone = member['phone']
                        secrets.append(phone)
                        for field in ('nickName', 'nickname', 'userName', 'username', 'displayName', 'uid'):
                            if member.get(field) is not None:
                                log(f'账号身份 {field}：{safe(member[field], secrets)}')
                        stats['success'] += 1
                        log('✅ 账号校验成功（手机号已隐藏）')
                    else:
                        reward = request(token, '/api/sign/member/signV2',
                                         {'activityId': activity_id, 'memberName': '', 'memberPhone': phone})
                        stats['success'] += 1
                        log('✅ 签到成功：业务码 200')
                        rewards = reward.get('rewardInfoList', []) if isinstance(reward, dict) else []
                        if isinstance(rewards, list):
                            for item in rewards:
                                if isinstance(item, dict):
                                    name = item.get('rewardName')
                                    if isinstance(name, str) and name:
                                        log('奖励：' + safe(name, secrets))
                                    elif type(item.get('point')) in (int, float):
                                        log(f'奖励积分：{item["point"]}')
                except TaskError as exc:
                    failed = True
                    stats['failed'] += 1
                    log('❌ ' + str(exc))
                except Exception:
                    failed = True
                    stats['failed'] += 1
                    log('❌ 阶段处理失败，异常详情已隐藏')
                log(f'阶段 {stage} 耗时：{time.monotonic() - step_start:.2f} 秒')
            failures += int(failed)
            successes += int(not failed)
            for key in totals:
                totals[key] += stats[key]
            log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 0，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic()-account_start:.2f} 秒')
    exit_code = int(config_error or failures > 0)
    status = 'configuration-error' if config_error else ('partial-failure' if failures and successes else 'failure' if failures else 'dry-run' if dry else 'success')
    body = f'账号总数：{len(tokens)}；成功数：{successes}；失败数：{failures}；状态：{status}'
    notification = notify(body, dry)
    log('--------------------')
    log(body + ('（预演成功不代表真实签到）' if dry else ''))
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'总耗时：{time.monotonic()-started:.2f} 秒；完成时间：{datetime.now().isoformat(timespec="seconds")}；通知：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'accounts': len(tokens), 'success': successes, 'failed': failures, 'configurationError': config_error, 'steps': totals, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
