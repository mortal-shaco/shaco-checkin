# -*- coding: utf-8 -*-
# name: NodeSeek 签到与收益统计
# cron: 10 1 * * *
# publish-path: scripts/lizhixu_nodeseek_attendance_credit_7990614346ba82e0.py
# 发布使用上述产品专属路径；不得覆盖 scripts/nodeseek_checkin.py。
# 路径冲突修复：导入器必须将 output/candidate.py 映射至 publish-path，
# 不得从上游 originalPath 推导部署路径。PUBLISH_PATH 仅记录目标，不自行部署。
# 来源: lizhixu/ql-script-hub, nodeseek_checkin.py
# 原始提交: ac591a320092dcaeaf236b7c2b6acfd28981e589
# 许可: MIT（上游未提供独立版权声明；保留来源署名）
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""每行一个 NODESEEK_COOKIE；浏览器登录 NodeSeek 后从签到请求复制完整 Cookie。
获取方式：登录 https://www.nodeseek.com，打开开发者工具的网络面板，
找到本站 /api/attendance 或 /api/account/credit/ 请求，在请求标头复制 Cookie。
仅复制 Cookie 的值，不包括 Cookie: 前缀；不同账号用换行分隔，Cookie 内的 & 保留。
保留 NS_RANDOM=true、RANDOM_SIGNIN=true、MAX_RANDOM_DELAY=3600。
NODESEEK_DRY_RUN=1 完全断网且不等待、不签到、通知器在禁止网络传输的环境中尝试发送摘要。
依赖：公开 PyPI 包 curl_cffi，使用其内置 HTTP 客户端及浏览器指纹。
QINGLONG_NOTIFY 默认开启；通知组件缺失或失败不影响业务退出码。
"""
import json
from pathlib import Path
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

TITLE = 'NodeSeek 签到与收益统计'
PUBLISH_PATH = 'scripts/lizhixu_nodeseek_attendance_credit_7990614346ba82e0.py'
TZ = timezone(timedelta(hours=8))
BASE = 'https://www.nodeseek.com'
FALSE = {'0', 'false', 'no', 'off'}
TRUE = {'1', 'true', 'yes', 'on'}


def stamp():
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')


def log(message):
    print(f'[{stamp()[11:]}] {message}', flush=True)


class TaskError(Exception):
    pass


def boolean(name, default):
    value = os.getenv(name, default).strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f'{name} 必须为布尔值')
    return value in TRUE


def request(client, cookie, method, path):
    # Refuse HTTP even if a dry-run caller reaches this helper.
    if os.getenv('NODESEEK_DRY_RUN', '0').strip().lower() not in FALSE:
        raise TaskError('DRY_RUN: HTTP disabled')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
               'origin': BASE, 'referer': BASE + '/board', 'Cookie': cookie,
               'Content-Type': 'application/json'}
    try:
        response = client.request(method, BASE + path, headers=headers,
                                  impersonate='chrome110', timeout=20,
                                  allow_redirects=False)
        if response.status_code != 200:
            raise TaskError(f'HTTP 状态 {response.status_code}')
        if len(response.content) > 2 * 1024 * 1024:
            raise TaskError('响应过大')
        data = response.json()
        if not isinstance(data, dict):
            raise TaskError('响应结构不符')
        return data
    except TaskError:
        raise
    except Exception:
        raise TaskError('请求失败或响应无法解析（详情已脱敏）') from None


def identity(data, cookie):
    containers = [data]
    for key in ('user', 'data', 'account'):
        if isinstance(data.get(key), dict):
            containers.append(data[key])
    for container in containers:
        for key in ('nickname', 'username', 'displayName', 'uid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                # 身份字段按原值显示；拒绝控制字符、手机号或被误放入身份字段的凭据。
                secrets = [cookie] + [v.split('=', 1)[-1].strip() for v in cookie.split(';') if len(v.split('=', 1)[-1].strip()) >= 4]
                if text and len(text) <= 120 and not any(ord(c) < 32 for c in text) and not any(s in text for s in secrets) and not (key != 'uid' and text.isdigit() and len(text) == 11):
                    log(f'官方账号身份: {text}')


def attendance(client, cookie, reward_random):
    data = request(client, cookie, 'POST', '/api/attendance?random=' + str(reward_random).lower())
    identity(data, cookie)
    message = data.get('message', '')
    if data.get('success') is True:
        return 'success'
    if isinstance(message, str) and ('已完成签到' in message or '今日已签到' in message):
        return 'already'
    # 不再仅凭“鸡腿”二字认定签到成功；不输出服务端原文。
    raise TaskError('签到业务未确认成功，请检查 Cookie 或接口状态')


def stats(client, cookie, days=30):
    start = datetime.now(TZ) - timedelta(days=days)
    amounts = []
    for page in range(1, 11):
        data = request(client, cookie, 'GET', f'/api/account/credit/page-{page}')
        identity(data, cookie)
        if data.get('success') is not True or not isinstance(data.get('data'), list):
            raise TaskError('收益查询业务失败或记录结构不符')
        records = data['data']
        log(f'收益分页 {page}: 返回 {len(records)} 条记录')
        if not records:
            break
        reached = False
        for record in records:
            if not isinstance(record, (list, tuple)) or len(record) != 4:
                raise TaskError('收益记录结构不符')
            amount, balance, description, timestamp = record
            try:
                when = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if when.tzinfo is None:
                    raise ValueError()
                if not isinstance(description, str):
                    raise ValueError()
                if when < start:
                    reached = True
                elif '签到收益' in description and '鸡腿' in description:
                    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
                        raise ValueError()
                    amounts.append(amount)
            except (TypeError, ValueError, AttributeError):
                raise TaskError('收益字段无法核验') from None
        if reached:
            break
        if page == 10:
            raise TaskError('已查询十页但未覆盖近30天，无法确认完整统计')
        time.sleep(0.5)
    total = sum(amounts)
    if not math.isfinite(total):
        raise TaskError('收益总额无法核验')
    return {'days_count': len(amounts), 'total_amount': total,
            'average': round(total / len(amounts), 2) if amounts else 0}


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE:
        log('通知: 全局开关已关闭')
        return 'disabled'
    # 在子进程执行可选通知器，限制耗时并屏蔽通知器输出，避免泄漏配置。
    runner = '''import importlib.util, os, sys
sys.path.insert(0, sys.argv[4])
if sys.argv[3] == "1":
    # 在导入通知器前阻断常见网络通道，预演通知失败保留业务退出码。
    import socket, subprocess, importlib.abc
    def offline(*args, **kwargs):
        raise RuntimeError("dry-run network disabled")
    def deny_network(event, args):
        if (event.startswith("socket.") or event.startswith("ctypes.")
                or event.startswith("os.exec") or event.startswith("os.spawn")
                or event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}):
            offline()
    sys.addaudithook(deny_network)
    class OfflineImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"curl_cffi", "pycurl", "ctypes", "cffi"}:
                offline()
            return None
    sys.meta_path.insert(0, OfflineImports())
    socket.socket = offline
    socket.create_connection = offline
    socket.getaddrinfo = offline
    subprocess.Popen = offline
    os.system = offline
    os.popen = offline
try:
    from notify import send
except ImportError:
    paths = []
    if os.getenv("QINGLONG_NOTIFY_DIR"):
        paths.append(os.path.join(os.environ["QINGLONG_NOTIFY_DIR"], "notify.py"))
    paths += ["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"]
    send = None
    for path in paths:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("ql_notify", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            send = module.send
            break
    if send is None:
        sys.exit(2)
if send(sys.argv[1], sys.argv[2]) is False:
    sys.exit(3)
'''
    # Optional notification modules do not need the account Cookie.
    notify_env = os.environ.copy()
    notify_env.pop('NODESEEK_COOKIE', None)
    try:
        result = subprocess.run([sys.executable, '-c', runner, TITLE, body, '1' if dry else '0', str(Path(__file__).resolve().parent)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=notify_env, timeout=30, check=False)
        state = 'sent' if result.returncode == 0 else 'unavailable-or-failed'
    except Exception:
        state = 'unavailable-or-failed'
    log('通知: ' + ('已交付通知器' if state == 'sent' else '组件不可用、断网预演限制或投递失败，保留业务退出码'))
    return state


def main():
    begin = time.monotonic()
    dry_value = os.getenv('NODESEEK_DRY_RUN', '0').strip().lower()
    # 无效预演开关按断网处理通知，配置检查随后返回非零。
    dry = dry_value not in FALSE
    cookies = [line.strip() for line in os.getenv('NODESEEK_COOKIE', '').splitlines() if line.strip()]
    log(f'========== {TITLE} ==========')
    log(f'开始时间: {stamp()}；模式: {"断网预演" if dry else "正式运行"}；账号数: {len(cookies)}')
    outcomes = []
    configuration_error = None
    try:
        config_start = time.monotonic()
        log('阶段 1 参数检查')
        dry = boolean('NODESEEK_DRY_RUN', '0')
        reward_random = boolean('NS_RANDOM', 'true')
        scheduled_random = boolean('RANDOM_SIGNIN', 'true')
        try:
            delay = int(os.getenv('MAX_RANDOM_DELAY', '3600'))
        except ValueError:
            raise TaskError('MAX_RANDOM_DELAY 必须为非负整数') from None
        if delay < 0:
            raise TaskError('MAX_RANDOM_DELAY 必须为非负整数')
        if not cookies:
            raise TaskError('缺少 NODESEEK_COOKIE，每行填写一个账号的完整 Cookie')
        if not dry:
            try:
                from curl_cffi import requests as client
            except ImportError:
                raise TaskError('缺少公开依赖 curl_cffi，请通过青龙依赖管理安装') from None
        else:
            client = None
        log(f'参数检查成功；随机奖励: {reward_random}；随机时间窗口: {delay if scheduled_random else 0} 秒')
        log(f'阶段 1 耗时: {time.monotonic() - config_start:.2f} 秒')
        schedule_start = time.monotonic()
        schedule = [(random.randint(0, delay) if scheduled_random else 0, i, c) for i, c in enumerate(cookies, 1)]
        scheduled_at = datetime.now(TZ)
        for seconds, index, _ in sorted(schedule):
            planned = (scheduled_at + timedelta(seconds=seconds)).strftime('%H:%M:%S')
            log(f'账号{index} 签到时间表: 延时 {seconds} 秒，预计 {planned} 执行')
        for seconds, index, cookie in sorted(schedule):
            wait_start = time.monotonic()
            log(f'账号{index} 阶段 2 调度: 计划延时 {seconds} 秒')
            if not dry:
                remaining = seconds - (time.monotonic() - schedule_start)
                while remaining > 0:
                    log(f'账号{index} 等待: 剩余 {int(remaining) + 1} 秒')
                    time.sleep(min(10, remaining))
                    remaining = seconds - (time.monotonic() - schedule_start)
            log(f'账号{index} 阶段 2 耗时: {time.monotonic() - wait_start:.2f} 秒')
            account_start = time.monotonic()
            counts = {'total': 2, 'success': 0, 'already': 0, 'skipped': 0, 'failed': 0}
            account_stats = None
            for stage, label in ((3, '签到'), (4, '近30天收益统计')):
                step_start = time.monotonic()
                log(f'账号{index} 阶段 {stage} {label}')
                try:
                    if any(ord(char) < 32 or ord(char) == 127 for char in cookie):
                        raise TaskError('本账号 Cookie 含控制字符，请复制完整请求标头值')
                    if dry:
                        counts['skipped'] += 1
                        log(f'账号{index} {label}: DRY_RUN_OK，无网络请求、无业务副作用')
                    elif stage == 3:
                        result = attendance(client, cookie, reward_random)
                        counts[result] += 1
                        log(f'账号{index} 签到: {"✅ 已确认成功" if result == "success" else "☑️ 已完成签到"}')
                    else:
                        values = stats(client, cookie)
                        account_stats = values
                        counts['success'] += 1
                        log(f'账号{index} 近30天签到天数: {values["days_count"]}；总鸡腿: {values["total_amount"]}；平均每日鸡腿: {values["average"]}')
                except TaskError as exc:
                    counts['failed'] += 1
                    log(f'账号{index} {label}: ❌ {exc}')
                except Exception:
                    counts['failed'] += 1
                    log(f'账号{index} {label}: ❌ 未预期错误（详情已脱敏）')
                log(f'账号{index} 阶段 {stage} 耗时: {time.monotonic() - step_start:.2f} 秒')
            counts.update(account=index, durationSeconds=round(time.monotonic() - account_start, 2))
            if account_stats is not None:
                counts['statistics'] = account_stats
            outcomes.append(counts)
            log(f'账号{index} 统计: 总任务 {counts["total"]}，成功 {counts["success"]}，已完成 {counts["already"]}，跳过 {counts["skipped"]}，失败 {counts["failed"]}，耗时 {counts["durationSeconds"]} 秒')
    except TaskError as exc:
        configuration_error = str(exc)
        log(f'❌ 配置错误: {exc}')
    except Exception:
        configuration_error = '初始化错误（详情已脱敏）'
        log(f'❌ {configuration_error}')
    failed = len(cookies) if configuration_error else sum(x['failed'] > 0 for x in outcomes)
    successful = 0 if configuration_error else len(outcomes) - failed
    status = 'configuration-error' if configuration_error else ('partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = 1 if failed or configuration_error else 0
    totals = {key: sum(x[key] for x in outcomes) for key in ('total', 'success', 'already', 'skipped', 'failed')}
    body = f'模式: {"断网预演" if dry else "正式运行"}；账号总数 {len(cookies)}，成功数 {successful}，失败数 {failed}；状态 {status}；子任务 {json.dumps(totals, ensure_ascii=False)}'
    for account in outcomes:
        body += (f'\n账号{account["account"]}: 成功 {account["success"]}，'
                 f'已完成 {account["already"]}，跳过 {account["skipped"]}，失败 {account["failed"]}')
        if 'statistics' in account:
            values = account['statistics']
            body += (f'；近30天签到 {values["days_count"]} 天，'
                     f'共 {values["total_amount"]} 个鸡腿，平均 {values["average"]} 个/天')
    if configuration_error:
        body += '\n' + configuration_error
    notify_start = time.monotonic()
    log('阶段 5 汇总通知')
    notification = notify(body, dry)
    log(f'阶段 5 耗时: {time.monotonic() - notify_start:.2f} 秒')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(cookies), 'successfulAccounts': successful, 'failedAccounts': failed,
               'subtasks': totals, 'accountResults': outcomes, 'notification': notification,
               'durationSeconds': round(time.monotonic() - begin, 2), 'finishTime': stamp(), 'exitCode': exit_code}
    log('----------------------------------------')
    log(f'账号统计: 总数 {len(cookies)}，成功 {successful}，失败 {failed}')
    log(f'子任务统计: 总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["already"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}')
    log(f'总耗时: {summary["durationSeconds"]} 秒；完成时间: {summary["finishTime"]}；通知状态: {notification}；最终状态: {status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
