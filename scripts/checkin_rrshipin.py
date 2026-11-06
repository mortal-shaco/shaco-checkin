#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 人人视频日常
# cron: 14 10 * * *
# SPDX-License-Identifier: GPL-3.0-only
# Original author: BNDou, BNDou/Auto_Check_In/checkIn_RRShiPin.py
# Date: 2024-06-05 01:56:28; LastEditTime: 2024-08-03 20:56:45
# Upstream commit: 3355d65c62a1d09643092de61d0e6d5175b2323f
"""人人视频日常，Python 标准库独立实现，沿用 GPL-3.0-only。

抓包：登录人人视频，打开签到页，找到
https://api.qwdjapp.com/activity/index/integral 请求头。将 clientVersion、
clientType、token、aliId、st 五个字段写入 COOKIE_RRShiPin：
clientVersion=<版本>; clientType=<类型>; token=<令牌>; aliId=<设备字段>; st=<会话字段>;
每行一个账号，不支持 && 或 @ 分隔账号；字段以分号分隔，仅在第一个等号处分割。
不打印凭据、设备标识和原始响应。不要分享抓包文件。
默认查询昵称、积分、签到和任务列表；不会自动激活任意任务。
如已核实具体任务的用途及风险，可设置 RRSHIPIN_TASK_IDS 为逗号分隔的任务编号，
只对当前列表内的这些任务依次激活、领取奖励。失败不重试写入请求。
RRSHIPIN_DRY_RUN=1 完全断网预演，包含通知模拟，不能证明真实业务成功。
通知：QINGLONG_NOTIFY=1 启用，0 禁用，auto 按 QINGLONG_NOTIFY_SCRIPTS 选择；
未提供默认名单，auto 未选择时跳过。选择器支持目录路径、文件名、通配符或目录编号。
可用 QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。通知失败保留业务退出码。
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
        _ql_notify_identities = ('64eaa3a0cf186a0f', 'scripts/checkin_rrshipin.py', 'checkin_rrshipin.py', 'checkin_rrshipin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end

import datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '人人视频日常'
CATALOG_ID = '64eaa3a0cf186a0f'
BASE = 'https://api.qwdjapp.com'
FIELDS = ('clientVersion', 'clientType', 'token', 'aliId', 'st')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def parse_account(line):
    result = {}
    if '&&' in line:
        raise TaskError('账号只能用换行分隔，不能使用 &&')
    for part in line.split(';'):
        if not part.strip():
            continue
        key, sep, value = part.strip().partition('=')
        key, value = key.strip(), value.strip()
        if not sep or key not in FIELDS or key in result or not value:
            raise TaskError('凭据格式错误：需要五个唯一的请求头字段')
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
            raise TaskError('请求头字段含无效字符')
        result[key] = value
    if set(result) != set(FIELDS):
        raise TaskError('缺少必要请求头字段')
    return result


def task_ids():
    raw = os.getenv('RRSHIPIN_TASK_IDS', '').strip()
    if not raw:
        return []
    values = [x.strip() for x in raw.split(',')]
    if any(not re.fullmatch(r'[0-9]+', x) for x in values):
        raise TaskError('RRSHIPIN_TASK_IDS 必须是逗号分隔的数字编号')
    return list(dict.fromkeys(values))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向重定向目标转发凭据，也不重放写入请求。
        return None


class Client:
    def __init__(self, headers):
        self.headers = headers
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, data=None, query=None):
        url = BASE + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        body = None if data is None else urllib.parse.urlencode(data).encode('ascii')
        headers = dict(self.headers)
        headers['Accept'] = 'application/json'
        if body is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request = urllib.request.Request(url, data=body, headers=headers,
                                         method='GET' if body is None else 'POST')
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                payload = response.read(1024 * 1024 + 1)
                if len(payload) > 1024 * 1024:
                    raise TaskError('响应超过大小限制')
            result = json.loads(payload)
        except (urllib.error.URLError, OSError, ValueError, UnicodeError):
            raise TaskError('请求失败或响应无法解析（详情已脱敏）') from None
        if not isinstance(result, dict) or result.get('code') != '0000':
            raise TaskError('业务未返回成功码 0000（原始响应已隐藏）')
        return result.get('data')


def identity(data, credentials):
    if not isinstance(data, dict) or not isinstance(data.get('user'), dict):
        raise TaskError('账号信息缺少 user 对象')
    name = data['user'].get('nickName')
    if not isinstance(name, str) or not name.strip():
        raise TaskError('账号信息缺少昵称')
    # 官方昵称保持原文；防止异常接口将凭据或手机号嵌入昵称输出。
    if (any(credentials[key] in name for key in ('token', 'aliId', 'st'))
            or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', name)
            or any(ord(c) < 32 for c in name)):
        return '账号昵称含敏感内容，已隐藏'
    return name


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            raise TaskError('数值字段缺失或格式变化')
    if str(value) in {'nan', 'inf', '-inf'}:
        raise TaskError('数值字段无效')
    return str(value)


def integral(data):
    if not isinstance(data, dict):
        raise TaskError('积分响应格式变化')
    return '积分：' + number(data.get('integral'))


def sign_result(data):
    if data is None:
        return 'already', '今日签到奖励已领取'
    if not isinstance(data, dict):
        raise TaskError('签到响应格式变化')
    return 'success', '签到奖励：' + number(data.get('value'))


def daily_tasks(data):
    if not isinstance(data, dict) or not isinstance(data.get('dailyTaskDto'), list):
        raise TaskError('任务列表缺少 dailyTaskDto，不能视为空列表成功')
    tasks = {}
    for item in data['dailyTaskDto']:
        if not isinstance(item, dict):
            raise TaskError('任务列表格式变化')
        ident = str(item.get('id', ''))
        if not re.fullmatch(r'[0-9]+', ident) or ident in tasks:
            raise TaskError('任务编号无效或重复')
        tasks[ident] = item
    return tasks


def run_account(index, line, dry, selected):
    started = time.monotonic()
    stats = dict(total=0, success=0, already=0, skipped=0, failed=0)
    stages = 0

    def stage(title, action):
        nonlocal stages
        stages += 1
        stats['total'] += 1
        before = time.monotonic()
        log(f'账号 {index} 阶段 {stages}：{title}')
        try:
            state, detail, value = action()
            stats[state] += 1
            log(f'账号 {index} 阶段 {stages}：{detail}；耗时 {time.monotonic()-before:.2f} 秒')
            return True, value
        except TaskError as exc:
            stats['failed'] += 1
            log(f'❌ 账号 {index} 阶段 {stages}：{exc}；耗时 {time.monotonic()-before:.2f} 秒')
            return False, None
        except Exception:
            stats['failed'] += 1
            log(f'❌ 账号 {index} 阶段 {stages}：执行异常（详情已脱敏）；耗时 {time.monotonic()-before:.2f} 秒')
            return False, None

    valid, headers = stage('检查账号配置', lambda: ('success', '五个凭据字段齐全', parse_account(line)))
    if valid and dry:
        for title in ['查询账号昵称', '查询初始积分', '每日签到', '查询任务列表']:
            stage(title, lambda: ('skipped', '断网预演：未发送 HTTP 请求', None))
        for ident in selected:
            stage(f'激活并领取任务 {ident}', lambda: ('skipped', '断网预演：未修改任务状态', None))
        stage('查询最终积分', lambda: ('skipped', '断网预演：未发送 HTTP 请求', None))
    elif valid:
        client = Client(headers)
        authenticated, _ = stage('查询账号昵称', lambda: (
            'success', '登录账号：' + identity(client.request('/user/personal/information',
                query={'token': headers['token']}), headers), None))
        if authenticated:
            stage('查询初始积分', lambda: ('success', integral(client.request('/activity/index/integral')), None))

            def sign():
                state, detail = sign_result(client.request('/activity/sign', {'sectionId': '0'}))
                return state, detail, None

            stage('每日签到', sign)

            def listing():
                tasks = daily_tasks(client.request('/activity/index/list'))
                # 不输出服务端任务文案，避免未知响应内容进入日志。
                return 'success', f'取得 {len(tasks)} 项任务；编号：' + ','.join(sorted(tasks, key=int)), tasks

            listed, tasks = stage('查询任务列表', listing)
            if not selected:
                stage('额外任务安全开关', lambda: ('skipped', '未配置任务白名单，跳过激活和奖励领取', None))
            for ident in selected:
                if not listed or ident not in tasks:
                    def missing():
                        raise TaskError('白名单任务不在已验证列表中，未发送写入请求')
                    stage(f'任务 {ident}', missing)
                    continue
                activated, _ = stage(f'激活任务 {ident}', lambda ident=ident: (
                    'success', '激活成功（业务码 0000）',
                    client.request('/activity/task/status/receive', {'taskId': ident})))
                if activated:
                    stage(f'领取任务 {ident} 奖励', lambda ident=ident: (
                        'success', '奖励领取成功（业务码 0000）',
                        client.request('/activity/task/status/complete', {'taskId': ident})))
            stage('查询最终积分', lambda: ('success', integral(client.request('/activity/index/integral')), None))
        else:
            stage('后续账号任务', lambda: ('skipped', '身份验证失败，停止此账号后续请求', None))
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["already"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic()-started:.2f} 秒')
    return stats


def notify_selected():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    if switch != 'auto':
        return False
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    names = {CATALOG_ID, Path(__file__).name, 'candidate.py', 'checkIn_RRShiPin.py',
             'checkin/checkIn_RRShiPin.py', 'checkin/candidate.py'}
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in selectors if pattern for name in names)


def notify(body, dry):
    if not notify_selected():
        return '未选择或已禁用'
    if dry:
        return '断网预演：通知已模拟，未调用发送模块'
    # 通知子进程只接收脱敏统计，捕获模块输出，超时或失败不影响业务退出码。
    dirs = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    runner = '''import contextlib, importlib.util, io, json, sys
payload=json.load(sys.stdin)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    path=payload.get('path')
    if path:
        sys.path.insert(0, str(__import__('pathlib').Path(path).parent))
        spec=importlib.util.spec_from_file_location('notify', path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        import notify as module
    module.send(payload['title'], payload['body'])
'''
    candidates = [None] + [str(Path(d) / 'notify.py') for d in dirs if d and (Path(d) / 'notify.py').is_file()]
    for path in candidates:
        try:
            result = subprocess.run([sys.executable, '-c', runner],
                input=json.dumps({'path': path, 'title': TITLE, 'body': body}),
                text=True, capture_output=True, timeout=45)
            if result.returncode == 0:
                return '发送完成'
            # 已找到模块但发送失败时不尝试其他入口，避免重复通知。
            if path or 'ModuleNotFoundError' not in result.stderr:
                return '发送失败（不影响业务退出码）'
        except (OSError, subprocess.TimeoutExpired):
            return '发送异常或超时（不影响业务退出码）'
    for directory in dirs:
        if not directory:
            continue
        path = Path(directory) / 'sendNotify.js'
        if not path.is_file():
            continue
        js = "let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',async()=>{try{const p=JSON.parse(s);await require(p.path).sendNotify(p.title,p.body)}catch(e){process.exitCode=1}})"
        try:
            result = subprocess.run(['node', '-e', js], input=json.dumps({
                'path': str(path.resolve()), 'title': TITLE, 'body': body}),
                text=True, capture_output=True, timeout=45)
            return '发送完成' if result.returncode == 0 else '发送失败（不影响业务退出码）'
        except (OSError, subprocess.TimeoutExpired):
            return '发送异常或超时（不影响业务退出码）'
    return '通知模块不可用（不影响业务退出码）'


def main():
    started = time.monotonic()
    start_time = stamp()
    dry = os.getenv('RRSHIPIN_DRY_RUN', '0').strip().lower() in TRUE
    lines = [x.strip() for x in os.getenv('COOKIE_RRShiPin', '').splitlines() if x.strip()]
    log('========== 人人视频日常 ==========')
    log(f'开始时间：{start_time}；模式：' + ('断网预演' if dry else '真实执行') + f'；账号数：{len(lines)}')
    results = []
    config_error = False
    log('阶段 1：检查运行配置')
    try:
        selected = task_ids()
        if not lines:
            raise TaskError('未配置 COOKIE_RRShiPin，请按说明填写账号请求头')
    except TaskError as exc:
        log(f'❌ 阶段 1：配置检查失败：{exc}')
        config_error = True
    if not config_error:
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, dry, selected))
    failed = sum(r['failed'] > 0 for r in results)
    passed = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and passed else 'failure' if failed else
              'dry-run' if dry else 'success')
    totals = {key: sum(r[key] for r in results) for key in ('total', 'success', 'already', 'skipped', 'failed')}
    body = f'状态：{status}；账号总数：{len(lines)}；成功：{passed}；失败：{failed}；配置错误：{int(config_error)}；子任务统计：{json.dumps(totals, ensure_ascii=False)}'
    log('阶段 2：发送脱敏任务通知')
    notification = notify(body, dry)
    finish = stamp()
    elapsed = round(time.monotonic() - started, 2)
    log('----------------------------------------')
    log(body)
    log(f'总耗时：{elapsed} 秒；完成时间：{finish}；通知状态：{notification}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(task=TITLE, status=status, dryRun=dry,
        accounts=len(lines), success=passed, failed=failed, configurationError=config_error,
        steps=totals, startedAt=start_time, finishedAt=finish, elapsedSeconds=elapsed,
        notification=notification, exitCode=exit_code), ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
