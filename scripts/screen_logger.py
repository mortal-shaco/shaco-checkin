#!/usr/bin/env python3
# name: ActivityWatch 屏幕时长记录
# cron: 49 * * * *
# 来源: michelledaviest/daily-checkin-bot, scripts/screen_logger.py
# 上游提交: d86334d5924df2bd47084c7a55d4628c93ddbd0a
# License: MIT (effectiveLicense); upstream input contains no copyright notice.
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
"""每小时读取 ActivityWatch HTTP 服务，按日期更新 Google 表格。

Python >=3.10；安装公开依赖 google-auth>=2,<3。无须其他仓库或应用可执行文件。
ActivityWatch 必须提供可访问的 HTTP 数据服务；默认 localhost:5600，青龙容器
应通过 AW_SERVER 指向数据所在服务，不能用容器自身替代电脑数据源。

SCREEN_ACCOUNTS 每个非空行是一个 JSON 对象，字段 sheet_id 和 service_account
必填；service_account 为 Google Cloud 服务账号 JSON 密钥对象。先启用 Sheets
API、创建服务账号密钥，并将目标表格共享给 client_email（编辑权限）。从表格 URL
/d/<ID>/ 获取 sheet_id；提前创建 screen_time 工作表及 local_date 和指标表头。
每行可覆盖 aw_server、laptop_bucket、phone_bucket、screen_time_tab、timezone、
break_min_seconds。JSON 字符串中的换行使用转义形式，不能用 & 或 @ 分隔账号。

兼容单账号 SHEET_ID + GSA_KEY_JSON（或显式 GSA_KEY_PATH），不再隐式读取
~/.config/checkin-bot/.env 或默认密钥文件。全局参数保留 TIMEZONE（默认
America/New_York）、SCREEN_TIME_TAB（screen_time）、AW_SERVER、LAPTOP_BUCKET
（aw-watcher-afk_<hostname>）、PHONE_BUCKET（空即仅电脑）、BREAK_MIN_SECONDS
（300）。SHEET_TAB 原说明未实际使用，仍使用 SCREEN_TIME_TAB。

必需表头：local_date, laptop_screen_hours, laptop_breaks_count,
laptop_longest_focus_block_min；启用手机时还需 phone_screen_hours,
phone_breaks_count, phone_longest_focus_block_min。仅更新指标列，其他列保持原样。
SCREEN_DRY_RUN=1 完全断网，仅校验配置并用本地事件验证计算及更新计划，不读密钥文件，
不认证、不通知、不写表。预演允许占位 service_account 对象，不能证明真实业务成功。
QINGLONG_NOTIFY=auto 默认仅匹配 QINGLONG_NOTIFY_SCRIPTS 的任务通知；1 强制启用，
0 禁用。选择器支持目录路径、文件名、通配符和 catalogId，逗号/分号/空白分隔。
通知模块不可用不会改变业务退出码；预演只记录通知摘要。
"""
from __future__ import annotations
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
        _ql_notify_identities = ('f5dda6d90f455cf3', 'scripts/screen_logger.py', 'screen_logger.py', 'screen_logger')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import fnmatch
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

TITLE = 'ActivityWatch 屏幕时长记录'
CATALOG = 'f5dda6d90f455cf3'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
LAPTOP = ['laptop_screen_hours', 'laptop_breaks_count', 'laptop_longest_focus_block_min']
PHONE = ['phone_screen_hours', 'phone_breaks_count', 'phone_longest_focus_block_min']


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝 HTTP 重定向')


def http(url, method='GET', headers=None, data=None):
    # No credentials or raw response data are ever included in error messages.
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers or {}, method=method), timeout=15) as response:
            raw = response.read(10 * 1024 * 1024 + 1)
            if len(raw) > 10 * 1024 * 1024:
                raise TaskError('HTTP 响应超过大小限制')
            return response.status, dict(response.headers), raw
    except TaskError:
        raise
    except Exception:
        raise TaskError('HTTP 请求失败或超时（详情已脱敏）') from None


def api(url, method='GET', headers=None, payload=None):
    hdr = dict(headers or {})
    data = None
    if payload is not None:
        hdr['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode()
    status, _, raw = http(url, method, hdr, data)
    try:
        result = json.loads(raw)
    except Exception:
        raise TaskError('接口返回无效 JSON') from None
    if not 200 <= status < 300 or isinstance(result, dict) and 'error' in result:
        raise TaskError('接口未确认业务成功')
    return result


def parse_accounts():
    raw = os.environ.get('SCREEN_ACCOUNTS', '')
    if raw.strip():
        return [line for line in raw.splitlines() if line.strip()]
    # Legacy values are kept as one account, not split on credential content.
    if os.environ.get('SHEET_ID', '').strip():
        return [None]
    raise TaskError('缺少 SCREEN_ACCOUNTS；兼容单账号可使用 SHEET_ID 配套密钥')


def config(line, dry):
    try:
        item = json.loads(line) if line is not None else {}
        if not isinstance(item, dict):
            raise ValueError()
        def value(key, env, default):
            return item.get(key, os.environ.get(env, default))
        sheet = value('sheet_id', 'SHEET_ID', '')
        if not isinstance(sheet, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', sheet):
            raise TaskError('sheet_id 缺失或格式错误')
        info = item.get('service_account')
        if info is None and os.environ.get('GSA_KEY_JSON', '').strip():
            info = json.loads(os.environ['GSA_KEY_JSON'])
        if info is None and os.environ.get('GSA_KEY_PATH'):
            if dry:
                info = {'dry_run_placeholder': True}
            else:
                with open(os.path.expanduser(os.environ['GSA_KEY_PATH']), encoding='utf-8') as stream:
                    info = json.load(stream)
        if not isinstance(info, dict) or not info:
            raise TaskError('缺少 service_account 密钥对象')
        if not dry and (not info.get('client_email') or not info.get('private_key')):
            raise TaskError('服务账号缺少 client_email 或 private_key')
        # Prevent an untrusted token_uri from receiving a signed assertion.
        if info.get('token_uri', 'https://oauth2.googleapis.com/token') != 'https://oauth2.googleapis.com/token':
            raise TaskError('服务账号 token_uri 必须使用 Google 官方地址')
        server = value('aw_server', 'AW_SERVER', 'http://localhost:5600').rstrip('/')
        parts = urlsplit(server)
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise TaskError('AW_SERVER 必须是无凭据、无查询参数的 HTTP 服务地址')
        tz = ZoneInfo(value('timezone', 'TIMEZONE', 'America/New_York'))
        threshold = int(value('break_min_seconds', 'BREAK_MIN_SECONDS', '300'))
        if threshold <= 0:
            raise TaskError('BREAK_MIN_SECONDS 必须为正整数')
        tab = value('screen_time_tab', 'SCREEN_TIME_TAB', 'screen_time')
        laptop = value('laptop_bucket', 'LAPTOP_BUCKET', '') or f'aw-watcher-afk_{socket.gethostname()}'
        phone = value('phone_bucket', 'PHONE_BUCKET', '') or None
        if not isinstance(tab, str) or not tab.strip() or not isinstance(laptop, str) or (phone is not None and not isinstance(phone, str)):
            raise TaskError('工作表或数据桶配置格式错误')
        return dict(sheet=sheet, info=info, server=server, tz=tz, threshold=threshold, tab=tab, laptop=laptop, phone=phone)
    except TaskError:
        raise
    except Exception:
        raise TaskError('账号 JSON、密钥、时区或数值配置无效（详情已脱敏）') from None


def bounds(date, tz):
    start = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def validate_events(events, phone=False):
    if not isinstance(events, list):
        raise TaskError('事件响应不是列表')
    try:
        for event in events:
            duration = event['duration']
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise ValueError()
            stamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError()
            if not phone and event['data'].get('status') not in {'afk', 'not-afk'}:
                raise ValueError()
    except Exception:
        raise TaskError('事件字段、时间戳或时长无效') from None
    return sorted(events, key=lambda e: datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')))


def metrics(events, threshold, phone=False):
    events = validate_events(events, phone)
    if not events:
        return {}
    active = 0
    breaks = 0
    longest = current = 0
    previous_end = None
    for event in events:
        duration = event['duration']
        if phone:
            start = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            if previous_end is not None and (start - previous_end).total_seconds() >= threshold:
                breaks += 1
                current = 0
            current += duration
            active += duration
            longest = max(longest, current)
            previous_end = start + timedelta(seconds=duration)
        elif event['data']['status'] == 'not-afk':
            active += duration
            current += duration
            longest = max(longest, current)
        elif duration >= threshold:
            breaks += 1
            current = 0
    keys = PHONE if phone else LAPTOP
    return dict(zip(keys, (round(active / 3600, 2), breaks, int(longest // 60))))


def fetch(cfg, bucket, date):
    start, end = bounds(date, cfg['tz'])
    query = urlencode({'start': start.isoformat().replace('+00:00', 'Z'), 'end': end.isoformat().replace('+00:00', 'Z'), 'limit': -1})
    return api(f"{cfg['server']}/api/0/buckets/{quote(bucket, safe='')}/events?{query}")


def token(info):
    try:
        from google.oauth2.service_account import Credentials
        from google.auth.transport import Request as AuthRequest, Response
        class AuthResponse(Response):
            def __init__(self, status, headers, data):
                self._status, self._headers, self._data = status, headers, data
            @property
            def status(self): return self._status
            @property
            def headers(self): return self._headers
            @property
            def data(self): return self._data
        class Transport(AuthRequest):
            def __call__(self, url, method='GET', body=None, headers=None, timeout=None, **kwargs):
                if url != 'https://oauth2.googleapis.com/token':
                    raise TaskError('拒绝非官方认证地址')
                return AuthResponse(*http(url, method, headers, body))
        info = dict(info, token_uri='https://oauth2.googleapis.com/token')
        credentials = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        credentials.refresh(Transport())
        if not credentials.token:
            raise TaskError('未获取有效认证令牌')
        return credentials.token
    except Exception:
        raise TaskError('Google 服务账号认证失败或缺少 google-auth 依赖（详情已脱敏）') from None


def column(number):
    label = ''
    while number:
        number, rest = divmod(number - 1, 26)
        label = chr(65 + rest) + label
    return label


def plan(rows, date, fields):
    if not rows or not isinstance(rows[0], list):
        raise TaskError('工作表缺少表头')
    headers = rows[0]
    required = ['local_date', *fields]
    if any(headers.count(key) != 1 for key in required):
        raise TaskError('工作表必需表头缺失或重复，拒绝静默丢弃指标')
    date_index = headers.index('local_date')
    matches = [i for i, row in enumerate(rows[1:], 2) if len(row) > date_index and str(row[date_index]).lstrip("'") == date]
    if len(matches) > 1:
        raise TaskError('工作表存在重复日期，拒绝不明确更新')
    if matches:
        return 'update', [{'range': f'{column(headers.index(key)+1)}{matches[0]}', 'values': [[val]]} for key, val in fields.items()]
    row = [''] * len(headers)
    row[date_index] = date
    for key, val in fields.items():
        row[headers.index(key)] = val
    return 'append', row


def write_sheet(cfg, date, fields):
    headers = {'Authorization': 'Bearer ' + token(cfg['info'])}
    root = f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['sheet']}"
    tab = "'" + cfg['tab'].replace("'", "''") + "'"
    data = api(root + '/values/' + quote(tab, safe=''), headers=headers)
    if not isinstance(data, dict) or not isinstance(data.get('values'), list):
        raise TaskError('Google 表格读取结果无效')
    action, values = plan(data['values'], date, fields)
    if action == 'update':
        for update in values:
            update['range'] = tab + '!' + update['range']
        result = api(root + '/values:batchUpdate', 'POST', headers, {'valueInputOption': 'RAW', 'data': values})
        if result.get('totalUpdatedCells') != len(fields):
            raise TaskError('Google 表格未确认全部单元格更新')
    else:
        url = root + '/values/' + quote(tab + '!A1', safe='') + ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS'
        result = api(url, 'POST', headers, {'values': [values]})
        if result.get('updates', {}).get('updatedRows') != 1 or result.get('updates', {}).get('updatedCells', 0) < len(fields) + 1:
            raise TaskError('Google 表格未确认新增行')
    return action


def notification(body, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in FALSE:
        return '已关闭'
    selectors = re.split(r'[,;\s]+', os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    identities = [CATALOG, Path(__file__).name, 'screen_logger.py', 'scripts/screen_logger.py']
    if switch not in TRUE and not any(fnmatch.fnmatchcase(name, pattern) for name in identities for pattern in selectors if pattern):
        return '未选中'
    if dry:
        return '预演：已生成脱敏摘要，未投递'
    # Execute notification integration in a subprocess so hangs and errors cannot
    # alter the business result, and suppress untrusted notifier output.
    python_code = '''import importlib.util,sys\np=sys.argv[1]\nif p:\n s=importlib.util.spec_from_file_location("notify",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nelse:\n import notify as m\nm.send(sys.argv[2],sys.argv[3])'''
    candidates = [['python', '']]
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    for directory in directories:
        if directory:
            for filename in ('notify.py', 'sendNotify.js'):
                path = Path(directory) / filename
                if path.is_file():
                    candidates.append(['python' if filename.endswith('.py') else 'node', str(path)])
    for kind, path in candidates:
        cmd = [sys.executable, '-c', python_code, path, TITLE, body] if kind == 'python' else ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', path, TITLE, body]
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                return '已投递'
        except Exception:
            pass
    return '不可用或失败（保留业务退出码）'


def run():
    started = time.monotonic()
    dry = os.environ.get('SCREEN_DRY_RUN', '').lower().strip() in TRUE
    log(f'=== {TITLE} ===')
    log(f'开始时间：{datetime.now().astimezone().isoformat(timespec="seconds")}；模式：{"断网预演" if dry else "正式执行"}')
    results = []
    configuration_error = False
    try:
        lines = parse_accounts()
    except TaskError as error:
        lines = []
        configuration_error = True
        log(f'❌ 配置错误：{error}')
    log(f'账号总数：{len(lines)}')
    for number, line in enumerate(lines, 1):
        begin = time.monotonic()
        counters = dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)
        failed = False
        def stage(index, title, operation):
            nonlocal failed
            tick = time.monotonic()
            counters['total'] += 1
            log(f'账号 {number} · 阶段 {index} {title} 开始')
            try:
                value = operation()
                counters['success'] += 1
                log(f'✅ 账号 {number} · 阶段 {index} {title} 完成，耗时 {time.monotonic()-tick:.2f} 秒')
                return True, value
            except Exception as error:
                failed = True
                counters['failed'] += 1
                message = str(error) if isinstance(error, TaskError) else '处理失败（详情已脱敏）'
                log(f'❌ 账号 {number} · 阶段 {index} {title}：{message}，耗时 {time.monotonic()-tick:.2f} 秒')
                return False, None
        ok, cfg = stage(1, '校验配置', lambda: config(line, dry))
        if ok:
            date = datetime.now(cfg['tz']).strftime('%Y-%m-%d')
            fields = {}
            fixture = [{'timestamp': '2026-01-01T00:00:00Z', 'duration': 3600, 'data': {'status': 'not-afk'}}]
            ok_laptop, laptop = stage(2, '电脑事件及统计', lambda: metrics(fixture if dry else fetch(cfg, cfg['laptop'], date), cfg['threshold']))
            if ok_laptop:
                fields.update(laptop)
            ok_phone = True
            if cfg['phone']:
                ok_phone, phone = stage(3, '手机事件及统计', lambda: metrics(fixture if dry else fetch(cfg, cfg['phone'], date), cfg['threshold'], True))
                if ok_phone:
                    fields.update(phone)
            else:
                counters['total'] += 1
                counters['skipped'] += 1
                log(f'⏭️ 账号 {number} · 阶段 3 手机统计未配置，跳过；耗时 0.00 秒')
            # As upstream, preserve available laptop data when optional phone fails.
            # Never write phone-only values after required laptop fetch failure.
            if ok_laptop and fields:
                if dry:
                    def preview():
                        bounds(date, cfg['tz'])
                        plan([['local_date', *fields]], date, fields)
                        plan([['local_date', *fields], [date]], date, fields)
                    stage(4, '本地新增及更新计划校验（不写表）', preview)
                else:
                    written, _ = stage(4, '更新 Google 表格并核验响应', lambda: write_sheet(cfg, date, fields))
                # Keep upstream metric output format without exposing config.
                if dry or written:
                    print(f'[{date}] {"dry-run" if dry else "wrote"}: ' + ', '.join(f'{k}={v}' for k, v in sorted(fields.items())))
            else:
                counters['total'] += 1
                counters['skipped'] += 1
                log(f'⏭️ 账号 {number} · 阶段 4 无事件或电脑读取失败，未写表；耗时 0.00 秒')
        else:
            configuration_error = True
        counters.update(account=number, status='failure' if failed else ('dry-run' if dry else 'success'), elapsed=round(time.monotonic()-begin, 2))
        results.append(counters)
        log(f'账号 {number} 统计：总任务 {counters["total"]}，成功 {counters["success"]}，已完成 {counters["alreadyComplete"]}，跳过 {counters["skipped"]}，失败 {counters["failed"]}，耗时 {counters["elapsed"]} 秒')
    failures = sum(item['status'] == 'failure' for item in results)
    successes = len(results) - failures
    code = 1 if failures or configuration_error else 0
    status = 'configuration-error' if configuration_error else ('partial-failure' if failures and successes else 'failure' if failures else 'dry-run' if dry else 'success')
    body = f'账号总数 {len(results)}，成功 {successes}，失败 {failures}；状态 {status}。' + ('预演未认证、未访问网络、未写表。' if dry else '')
    try:
        notified = notification(body, dry)
    except Exception:
        notified = '通知失败（保留业务退出码）'
    log('----------------------------------------')
    log(body)
    totals = {key: sum(item[key] for item in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    finished = datetime.now().astimezone().isoformat(timespec='seconds')
    elapsed = round(time.monotonic()-started, 2)
    log(f'完成时间：{finished}；总耗时 {elapsed} 秒；通知：{notified}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(status=status, mode='dry-run' if dry else 'live', accounts=len(results), success=successes, failed=failures, configurationError=configuration_error, tasks=totals, results=results, notification=notified, finishedAt=finished, elapsed=elapsed, exitCode=code), ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(run())
