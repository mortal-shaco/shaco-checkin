# -*- coding: utf-8 -*-
# name: 赛马娘官网每日签到
# cron: 8 10 * * *
# @File     : uma.py
# @Time     : 2026/07/14 14:30
# @Author   : Jckling
# Source: jckling/Daily-Bonus, checkin/uma.py
# License: MIT
# Copyright (c) Jckling
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
"""赛马娘官网签到（Python 3，仅标准库）。

登录 https://uma.komoejoy.com/ 的签到活动页，用浏览器开发者工具的
网络面板查看该站签到请求的 Cookie 请求头。将完整值写入 UMA_COOKIES，
每个账号占一行；仅提取 site、joy_jct、DedeUserID、SESSDATA。
不使用 &、@ 分隔账号，不记录 Cookie。保留原单账号格式。
UMA_DRY_RUN=1 时只检查配置并展示计划，不进行任何网络调用或通知投递。
每日 08:00 为独立版建议周期；上游文件未声明 cron。
只自动执行每日签到；不抽奖、不消费积分、不发布内容。
QINGLONG_NOTIFY=auto 默认仅为显式选择的脚本投递通知；可设 1 强制开启，
0 关闭。QINGLONG_NOTIFY_SCRIPTS 支持目录路径、文件名、glob 和目录编号，
以逗号、分号或空白分隔，* 表示全部，空值表示全部关闭。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('792bd50268357a67', 'scripts/uma.py', 'uma.py', 'uma')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys
import time
from datetime import datetime
from urllib import request, parse, error

TITLE = '赛马娘官网每日签到'
CATALOG_ID = '792bd50268357a67'
BASE_URL = 'https://l11-activity-web-hk.komoejoy.com'
ACTIVITY_GROUP_ID = '1755595320481626'
ACTIVITY_ID = '10000244'
DRAW_ACTIVITY_ID = '10000385'
APP_ID = '6829'
APPKEY = '7200bfa761c94eae9ceb168bf4b129d0'
SECRET = '+RIq/MaHJf9h23eOdjyXB6lkXL0LjcTGuPiNRyTtZX4='
NEEDED_KEYS = ('site', 'joy_jct', 'DedeUserID', 'SESSDATA')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
TIMEOUT = 15
MAX_BYTES = 1024 * 1024
REDACTIONS = []


class TaskError(Exception):
    pass


def clean(value):
    text = str(value)
    for secret in sorted(set(REDACTIONS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?i)(cookie|token|sessdata|joy_jct|session|sign)\s*[:=]\s*[^\s;]+', r'\1=[已隐藏]', text)
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(ch if ch.isprintable() else ' ' for ch in text)


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {clean(text)}', flush=True)


def parse_cookie(line):
    if any(ord(c) < 32 or ord(c) > 126 for c in line):
        raise TaskError('Cookie 必须为无控制字符的请求头文本')
    values = {}
    for part in line.split(';'):
        key, sep, value = part.strip().partition('=')
        if sep and key in NEEDED_KEYS:
            values[key] = value
    if not values or not any(values.values()):
        raise TaskError('Cookie 中缺少有效的站点字段，请重新从签到请求获取')
    # 上游未证明全部四个字段对所有登录方式均为必填，交由状态接口验证。
    return '; '.join(f'{k}={v}' for k, v in values.items())


def build_params(extra=None):
    ts = int(time.time() * 1000)
    nonce = str(ts) + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    params = dict(activity_group_id=ACTIVITY_GROUP_ID, activity_id=ACTIVITY_ID,
                  lang='zh', app_id=APP_ID, nonce=nonce, ts=ts, appkey=APPKEY)
    params.update(extra or {})
    raw = '&'.join(f'{k}={params[k]}' for k in sorted(params) if params[k] or params[k] == 0)
    params['sign'] = hashlib.md5((raw + '&secret=' + SECRET).encode()).hexdigest()
    return params


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Cookie 与签名绝不转发至跳转地址，也不自动重放写入请求。
        return None


class Client:
    def __init__(self, cookie, dry=False):
        self.cookie, self.dry = cookie, dry
        self.opener = request.build_opener(NoRedirect())
        self.identities = set()

    def call(self, path, extra=None, method='GET'):
        if self.dry:
            raise TaskError('预演禁止网络请求')
        params = parse.urlencode(build_params(extra)).encode('ascii')
        headers = {'accept': 'application/json, text/plain, */*',
                   'cookie': self.cookie, 'origin': 'https://uma.komoejoy.com',
                   'referer': 'https://uma.komoejoy.com/',
                   'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'}
        url = BASE_URL + path
        data = None
        if method == 'GET':
            url += '?' + params.decode('ascii')
        else:
            data = params
            headers['content-type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        try:
            with self.opener.open(request.Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise TaskError('响应超过大小限制')
            obj = json.loads(payload)
        except TaskError:
            raise
        except error.HTTPError as exc:
            raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
        except Exception:
            raise TaskError('网络超时、连接失败或响应不是有效 JSON') from None
        if not isinstance(obj, dict) or type(obj.get('code')) is not int or obj['code'] != 0:
            raise TaskError('业务未成功（需要 code=0），请检查活动与登录状态')
        self.show_identity(obj)
        return obj.get('data')

    def show_identity(self, obj):
        # 仅打印官方明确命名的公开身份字段，绝不遍历 Cookie 或设备字段。
        if not isinstance(obj, dict):
            return
        for key in ('nickname', 'nickName', 'username', 'displayName', 'uid', 'publicUid'):
            value = obj.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                item = (key, str(value))
                if item not in self.identities:
                    self.identities.add(item)
                    # UID 为公开身份，不按手机号规则处理。
                    safe = str(value)
                    for credential in REDACTIONS:
                        if credential:
                            safe = safe.replace(credential, '[已隐藏]')
                    safe = ''.join(c if c.isprintable() else ' ' for c in safe)
                    print(f'[{datetime.now():%H:%M:%S}] 官方身份 {key}: {safe}', flush=True)
        for key in ('data', 'user', 'profile', 'account'):
            if isinstance(obj.get(key), dict):
                self.show_identity(obj[key])


def month_range(now=None):
    now = now or datetime.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000) - 1


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 and value < float('inf')


def run_account(index, line, dry):
    started = time.monotonic()
    stats = dict(total=5, success=0, alreadyComplete=0, skipped=0, failed=0)
    log(f'账号 {index} 开始')
    try:
        cookie = parse_cookie(line)
    except TaskError as exc:
        log(f'账号 {index} 配置错误：{exc}')
        stats.update(failed=1, skipped=4)
        stats['configurationError'] = True
        stats['seconds'] = round(time.monotonic() - started, 3)
        log(f'账号 {index} 统计：总任务 5，成功 0，已完成 0，跳过 4，失败 1，耗时 {stats["seconds"]} 秒')
        return stats
    client = Client(cookie, dry)
    signed = False
    record_total = None

    def stage(number, name, action):
        begin = time.monotonic()
        log(f'账号 {index} 阶段 {number}/5 {name} 开始')
        try:
            result = action()
            status, detail = result
            stats[status] += 1
            log(f'账号 {index} 阶段 {number}/5 {name}：{detail}；耗时 {time.monotonic()-begin:.3f} 秒')
        except Exception as exc:
            stats['failed'] += 1
            detail = str(exc) if isinstance(exc, TaskError) else '响应结构异常或本地处理失败'
            log(f'账号 {index} 阶段 {number}/5 {name} 失败：{detail}；耗时 {time.monotonic()-begin:.3f} 秒')

    def sign():
        nonlocal signed
        status = client.call('/activity/sign/v2/status')
        if type(status) is not int or status not in (0, 1):
            raise TaskError('签到状态未知，停止签到写入')
        if status == 1:
            signed = True
            return 'alreadyComplete', '今日已签到'
        client.call('/activity/sign/v2/in', method='POST')
        confirmed = client.call('/activity/sign/v2/status')
        if type(confirmed) is not int or confirmed != 1:
            raise TaskError('写入后未确认签到状态，不重试写入')
        signed = True
        return 'success', '签到成功'

    def records():
        nonlocal record_total
        start, end = month_range()
        data = client.call('/activity/sign/v2/record', dict(start_time=str(start), end_time=str(end), page_num='1', page_size='31'))
        if not isinstance(data, dict) or type(data.get('total')) is not int or data['total'] < 0 or not isinstance(data.get('data'), list):
            raise TaskError('签到记录字段不完整')
        record_total = data['total']
        dates = [r.get('signDateTimeString') for r in data['data'] if isinstance(r, dict) and isinstance(r.get('signDateTimeString'), str)]
        return 'success', f'本月签到: 已签到 {record_total} 天；最近签到时间: {max(dates) if dates else "无记录"}'

    def rewards():
        data = client.call('/activity/uma/sign/config')
        if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ('daily_sign_prize_list', 'total_sign_prize_list')):
            raise TaskError('奖励配置字段不完整')
        if not signed or record_total is None:
            raise TaskError('奖励配置已读取，但缺少已确认签到与本月次数，无法判断今日奖励')
        key = str(record_total) if record_total else str(datetime.now().day)
        parts = []
        for field, title in [('daily_sign_prize_list', '今日奖励'), ('total_sign_prize_list', '累计签到奖励')]:
            reward = data[field].get(key)
            if reward is None:
                parts.append(f'{title}: 无对应奖励')
            elif isinstance(reward, dict):
                name = reward.get('prize_name') or ''
                num, point = reward.get('prize_num', 0), reward.get('add_point', 0)
                if not isinstance(name, str) or not numeric(num) or not numeric(point):
                    raise TaskError('奖励数据格式异常')
                parts.append(f'{title}: {name.strip()} x{num} + {point} 积分')
            else:
                raise TaskError('奖励项格式异常')
        return 'success', '；'.join(parts)

    def points():
        data = client.call('/activity/uma/sign/draw_assert', {'activity_id': DRAW_ACTIVITY_ID})
        if not isinstance(data, dict) or not all(numeric(data.get(k)) for k in ('available', 'total')):
            raise TaskError('积分余额字段不完整')
        text = f'积分余额: 可用 {data["available"]}，总计 {data["total"]}'
        for key, title in [('used', '已用'), ('expiring', '即将到期')]:
            if key in data:
                if not numeric(data[key]):
                    raise TaskError('积分明细格式异常')
                text += f'，{title} {data[key]}'
        return 'success', text

    stage(1, '凭据检查', lambda: ('success', 'Cookie 格式已检查，未输出凭据'))
    for n, name, action in [(2, '每日签到', sign), (3, '当月记录', records), (4, '每日与累计奖励', rewards), (5, '积分余额', points)]:
        stage(n, name, (lambda: ('skipped', 'DRY_RUN：已检查执行计划，未发送请求')) if dry else action)
    stats['seconds'] = round(time.monotonic() - started, 3)
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒')
    return stats


def notify(summary, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    selected = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    names = [CATALOG_ID, 'checkin/uma.py', 'uma.py', 'candidate.py', Path(__file__).name, str(Path(__file__))]
    listed = selected is not None and any(fnmatch.fnmatch(name, pattern) for pattern in re.split(r'[,;\s]+', selected.strip()) if pattern for name in names)
    enabled = switch in TRUE or (switch == 'auto' and listed)
    if switch in FALSE or not enabled:
        return '已关闭或未被选择'
    if dry:
        return '预演摘要已记录，断网模式不投递通知'
    body = f'状态 {summary["status"]}；账号总数 {summary["accounts"]}，成功 {summary["success"]}，失败 {summary["failed"]}；子任务失败 {summary["tasks"]["failed"]}'
    # 隔离通知库的输出和异常，防止通知模块打印配置；超时不影响业务退出码。
    child = '''import importlib.util, sys
from pathlib import Path
kind, target, title, body = sys.argv[1:]
if kind == 'module':
    from notify import send
else:
    spec = importlib.util.spec_from_file_location('ql_notify', target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    send = module.send
send(title, body)
'''
    candidates = [('module', '')]
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
    for directory in directories:
        if directory:
            path = Path(directory) / 'notify.py'
            if path.is_file():
                candidates.append(('file', str(path)))
    for kind, target in candidates:
        try:
            result = subprocess.run([sys.executable, '-c', child, kind, target, TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                return '已投递'
        except Exception:
            pass
    for directory in directories:
        if directory and (Path(directory) / 'sendNotify.js').is_file():
            try:
                result = subprocess.run(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(Path(directory) / 'sendNotify.js'), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                if result.returncode == 0:
                    return '已投递'
            except Exception:
                pass
    return '不可用或投递失败（保留业务退出码）'


def main():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec='seconds')
    lines = [line.strip() for line in os.environ.get('UMA_COOKIES', '').splitlines() if line.strip()]
    for line in lines:
        REDACTIONS.append(line)
        for part in line.split(';'):
            key, sep, value = part.strip().partition('=')
            if sep and key in NEEDED_KEYS and value:
                REDACTIONS.append(value)
    raw_mode = os.environ.get('UMA_DRY_RUN', '0').strip().lower()
    dry = raw_mode in TRUE
    invalid_mode = raw_mode not in TRUE | FALSE
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{start_time}；运行模式：{"断网预演" if dry else "正式"}；账号数量：{len(lines)}')
    results = []
    if invalid_mode:
        log('配置错误：UMA_DRY_RUN 必须为 1/0、true/false、yes/no 或 on/off')
    elif not lines:
        log('配置错误：缺少 UMA_COOKIES，请按每行一个账号填写')
    else:
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, dry))
    failed = sum(r['failed'] > 0 for r in results)
    config_error = invalid_mode or not lines or any(r.get('configurationError') for r in results)
    exit_code = int(bool(failed or config_error))
    status = 'configuration-error' if config_error else ('partial-failure' if 0 < failed < len(lines) else 'failure') if failed else 'dry-run' if dry else 'success'
    tasks = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    summary = dict(status=status, mode='dry-run' if dry else 'live', accounts=len(lines), success=len(results)-failed, failed=failed, tasks=tasks, startTime=start_time, exitCode=exit_code)
    summary['notification'] = notify(summary, dry or invalid_mode)
    summary['seconds'] = round(time.monotonic() - started, 3)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    log('------------------------------------------------------------')
    log(f'任务统计：账号总数 {len(lines)}，成功 {summary["success"]}，失败 {failed}；子任务 {json.dumps(tasks, ensure_ascii=False)}')
    log(f'通知状态：{summary["notification"]}；总耗时 {summary["seconds"]} 秒')
    log(f'完成时间：{summary["finishTime"]}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
