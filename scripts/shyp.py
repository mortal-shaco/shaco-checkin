#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 上海云媒体积分任务
# cron: 49 9 * * *
"""上海云媒体积分任务，独立维护版。
来源: comeonbabyy1/qiandao-jiaob script/shyp/main.py 与 api.py
原始说明: 上海云媒体积分任务自动化脚本 / 上海云媒体 API Interface
Author: Assistant
Date: 2025-11-06

SHYP_ACCOUNTS: 每个非空行一个 JSON 对象，含 token、device_id；可选
site_id（默认310110）、user_agent、account_name。登录上海云媒体客户端，
在本人授权的网络调试中读取 app.ypmedia.cn 请求头 token、deviceid、siteid、
User-Agent；不要使用商城 Authorization 代替 token。沿用原配置字段，
原 config/token.json 中 shyp.accounts 的每个对象改为一行，无需任何私有文件。
SHYP_TASKS 默认 read,video；可选 query,read,video,favor,comment,share。
query 仅查询；favor/comment/share 必须主动加入；SHYP_UNFAVOR=1 才在本次
收藏成功后取消收藏（可能改变既有收藏状态）。未启用的任务明确跳过。
SHYP_DRY_RUN=1 完全断网演练，通知仅演练；不假称业务完成。
来源未声明定时计划；顶部 cron 是每日一次的建议计划。

License: MIT (effectiveLicense supplied by source catalog).
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
        _ql_notify_identities = ('c8112572b797324b', 'scripts/shyp.py', 'shyp.py', 'shyp')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

TITLE = '上海云媒体积分任务'
CATALOG = 'c8112572b797324b'
PREFIX = '/media-basic-port/api/app/'
JOBS = {'read': ('002', '阅读'), 'video': ('003', '视频'),
        'favor': ('005', '收藏'), 'comment': ('006', '评论'), 'share': ('007', '分享')}
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = []


class Failure(Exception):
    pass


def log(message):
    # 不记录异常原文、接口消息、凭据、文章正文或原始响应。
    text = str(message)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    print(f'[{datetime.now():%H:%M:%S}] {text}', flush=True)


def flag(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value not in TRUE | FALSE:
        raise Failure(f'{name} 仅支持布尔值')
    return value in TRUE


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure('接口重定向已拒绝')


def http_json(url, headers=None, body=None, timeout=30, limit=1048576):
    # 每次独立 opener；随机文本请求不会继承账号头或会话。
    request = urllib.request.Request(url, data=None if body is None else
                                    json.dumps(body).encode('utf-8'), headers=headers or {},
                                    method='GET' if body is None else 'POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise Failure('HTTP 状态异常')
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise Failure('响应超长')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise Failure('响应结构异常')
        return result
    except Failure:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise Failure('网络、超时或响应解析失败') from None


def normalized(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def public_text(dry):
    local = normalized(os.getenv('SHYP_LOCAL_TEXT', '感谢分享，学习了。'))
    if not local or len(local) > 280:
        local = '感谢分享，学习了。'
    if dry:
        return local
    try:
        result = http_json('https://v1.hitokoto.cn/?encode=json', timeout=8, limit=16384)
        text = normalized(result.get('hitokoto'))
        author = normalized(result.get('from_who'))
        source = normalized(result.get('from'))
        if not text:
            raise Failure('缺少文本')
        if author and source:
            text += f' —— {author}《{source}》'
        elif source:
            text += f' ——《{source}》'
        elif author:
            text += f' —— {author}'
        if len(text) > 280:
            raise Failure('文本超长')
        log('评论文本：一言文本与署名已就绪')
        return text
    except Exception:
        log('⚠️ 一言不可用，采用本地文本')
        return local


class API:
    def __init__(self, account, dry):
        self.dry = dry
        self.site = account.get('site_id', '310110')
        self.headers = {'User-Agent': account.get('user_agent', 'okhttp/4.10.0'),
                        'Content-Type': 'application/json; charset=UTF-8',
                        'log-header': 'I am the log request header.',
                        'deviceid': account['device_id'], 'siteid': self.site,
                        'token': account['token']}

    def common(self, **extra):
        return dict(orderBy='release_desc', requestType='1', siteId=self.site, **extra)

    def call(self, endpoint, body):
        if self.dry:
            raise Failure('预演禁止调用业务网络')
        result = http_json('https://app.ypmedia.cn' + PREFIX + endpoint, self.headers, body)
        if type(result.get('code')) is not int or result['code'] != 0:
            raise Failure('业务码未确认成功（未输出服务端消息）')
        log('接口结果：HTTP 200，业务码 0')
        return result.get('data')

    def score(self):
        data = self.call('personal/score/info', dict(self.common(), requestType='2'))
        if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
            raise Failure('积分任务结构缺失')
        if not all(isinstance(j, dict) for j in data['jobs']):
            raise Failure('任务结构异常')
        return data

    def articles(self, video=False, page=1, size=10):
        channel = 'd7036c2839e047b48fe64bc36987650c' if video else 'a978f44b3e284e5e86777f9d4e3be7bb'
        data = self.call('news/content/list', self.common(channel={'id': channel}, pageNo=page, pageSize=size))
        if not isinstance(data, dict) or not isinstance(data.get('records'), list):
            raise Failure('内容列表结构异常')
        return data['records']


def score_log(data):
    # 只显示白名单非敏感身份字段，原值保留，不输出自填备注。
    for key in ('nickname', 'nickName', 'username', 'displayName', 'uid'):
        value = data.get(key)
        if isinstance(value, (str, int)) and value != '':
            log(f'官方身份 {key}：{value}')
    for key in ('totalScore', 'todayPoint', 'todayIncreasePoint'):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            log(f'积分 {key}：{value}')
    signs = data.get('signs')
    if isinstance(signs, list):
        signed = sum(isinstance(s, dict) and s.get('status') == 'signed' for s in signs)
        log(f'签到记录：已签 {signed} 项（仅查询，不自动签到）')
    for name, (job_id, label) in JOBS.items():
        job = next((j for j in data['jobs'] if str(j.get('id')) == job_id), None)
        if job:
            progress, total = progress_of(job)
            log(f'{label}进度 {progress}/{total}；状态：' + ('已完成' if complete(job) else '未完成'))


def complete(job):
    return str(job.get('status')) == '1'


def progress_of(job):
    try:
        progress, total = int(job['progress']), int(job['totalProgress'])
        if progress < 0 or total < 0 or total > 100:
            raise ValueError()
        return progress, total
    except (KeyError, ValueError, TypeError):
        raise Failure('任务进度字段缺失或异常') from None


def action(api, name, job, unfavor):
    progress, total = progress_of(job)
    remaining = max(0, total - progress)
    if not remaining:
        raise Failure('任务状态与进度不一致')
    rows = api.articles(video=name == 'video', size=10 if name == 'comment' else remaining)
    if name == 'comment':
        time.sleep(random.uniform(1, 2))
        rows += api.articles(page=2, size=10)
        random.shuffle(rows)
    seen = set()
    rows = [r for r in rows if isinstance(r, dict) and r.get('id')]
    selected = []
    for row in rows:
        key = str(row['id'])
        if key not in seen:
            seen.add(key)
            selected.append(row)
    if len(selected) < remaining:
        raise Failure('可用内容不足，停止本阶段以避免重复操作')
    errors = 0
    delays = {'read': (2, 4), 'video': (10, 15), 'favor': (15, 20),
              'comment': (30, 35), 'share': (5, 10)}
    for index, row in enumerate(selected[:remaining], 1):
        try:
            content_id = row['id']
            if name in ('read', 'share'):
                api.call('common/count/usage/inc', api.common(id=content_id, countType='contentRead'))
                api.call(f'points/{name}/add', api.common())
            elif name == 'video':
                api.call('multimedia/drama/get', api.common(id=content_id))
                api.call('points/video/add', api.common())
            elif name == 'favor':
                api.call('news/content/favor', {'id': content_id})
                if unfavor:
                    time.sleep(random.uniform(1, 2))
                    api.call('news/content/disfavor', {'id': content_id})
            elif name == 'comment':
                api.call('common/comment/add', {'displayResources': [], 'content': public_text(False),
                                               'targetType': 'content', 'targetId': content_id})
            log(f'✅ {JOBS[name][1]}操作 {index}/{remaining} 接口确认成功')
        except Failure as exc:
            errors += 1
            log(f'❌ {JOBS[name][1]}操作 {index}/{remaining}：{exc}')
        if index < remaining:
            time.sleep(random.uniform(*delays[name]))
    if errors:
        raise Failure('部分操作失败，未自动重试变更请求')


def parse_account(line):
    try:
        account = json.loads(line)
        if not isinstance(account, dict):
            raise ValueError()
        for key in ('token', 'device_id'):
            value = account.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError()
            SECRETS.append(value)
        for key in ('token', 'device_id', 'site_id', 'user_agent'):
            if key in account and (not isinstance(account[key], str) or
                                   not account[key] or any(ord(c) < 32 or ord(c) > 126 for c in account[key])):
                raise ValueError()
        return account
    except (TypeError, ValueError):
        raise Failure('账号 JSON 或必填 token/device_id 字段无效') from None


def run_account(line, number, tasks, dry, unfavor):
    start = time.monotonic()
    stats = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
    log(f'账号 {number} 开始')
    def stage(index, title, function):
        begin = time.monotonic()
        log(f'账号 {number} 阶段 {index}：{title}')
        try:
            result = function()
            log(f'✅ 阶段 {index} 结束，耗时 {time.monotonic()-begin:.2f}秒')
            return result
        except Exception:
            log(f'❌ 阶段 {index} 失败，耗时 {time.monotonic()-begin:.2f}秒')
            raise
    try:
        account = stage(1, '校验配置', lambda: parse_account(line))
        stats['success'] += 1
        api = API(account, dry)
        if dry:
            log('阶段 2：DRY_RUN_OK 配置通过；业务接口、一言和通知网络均未调用；耗时 0秒')
            for index, (name, (_, label)) in enumerate(JOBS.items(), 3):
                log(f'阶段 {index}：{label} ' + ('计划执行，未发请求' if name in tasks else '未启用') + '；耗时 0秒')
            log('阶段 8：最终状态核验仅列入计划，未查询业务；耗时 0秒')
            stats['skipped'] += 7
        else:
            before = stage(2, '查询积分、签到与任务', api.score)
            score_log(before)
            stats['success'] += 1
            attempted = []
            for index, (name, (job_id, label)) in enumerate(JOBS.items(), 3):
                job = next((j for j in before['jobs'] if str(j.get('id')) == job_id), None)
                if name not in tasks:
                    stats['skipped'] += 1
                    log(f'阶段 {index}：{label} ⏭️ 未启用；耗时 0秒')
                elif job and complete(job):
                    stats['alreadyComplete'] += 1
                    log(f'阶段 {index}：{label} ☑️ 已完成；耗时 0秒')
                elif job is None:
                    stats['failure'] += 1
                    log(f'阶段 {index}：{label} ❌ 未返回目标任务；耗时 0秒')
                else:
                    try:
                        stage(index, label, lambda: action(api, name, job, unfavor))
                        attempted.append((name, job_id))
                    except Exception:
                        stats['failure'] += 1
                        log(f'❌ {label}未确认成功；继续其余阶段')
                    time.sleep(random.uniform(5, 10))
            after = stage(8, '刷新积分与核验任务完成状态', api.score)
            score_log(after)
            stats['success'] += 1
            for name, job_id in attempted:
                job = next((j for j in after['jobs'] if str(j.get('id')) == job_id), None)
                if job and complete(job):
                    stats['success'] += 1
                    log(f'✅ {JOBS[name][1]}：最终任务状态确认完成')
                else:
                    stats['failure'] += 1
                    log(f'❌ {JOBS[name][1]}：最终任务状态未完成')
    except Exception:
        stats['failure'] += 1
        log(f'❌ 账号 {number} 配置、网络或业务契约异常（已隐藏异常细节）')
    stats['total'] = sum(stats.values())
    stats['duration'] = round(time.monotonic() - start, 2)
    log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，'
        f'已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {stats["duration"]}秒')
    return stats


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '通知开关无效，未发送'
    if switch == 'auto':
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', ''))
        identities = [CATALOG, 'script/shyp/main.py', 'scripts/candidate.py', 'candidate.py', Path(__file__).name, TITLE]
        for root in (Path('/ql/data/scripts'), Path('/ql/scripts'), Path.cwd()):
            try:
                identities.append(str(Path(__file__).resolve().relative_to(root.resolve())))
            except ValueError:
                pass
        if not any(fnmatch.fnmatchcase(identity, selector) for selector in selectors if selector for identity in identities):
            return '未在通知名单'
    if dry:
        return '预演通知摘要已生成，未调用通知模块或网络'
    body = (f'状态：{summary["status"]}；账号总数：{summary["accounts"]}；'
            f'成功：{summary["success"]}；失败：{summary["failure"]}；耗时：{summary["duration"]}秒')
    # 通知模块在隔离子进程中执行；不传账号变量，不打印其输出。
    env = {k: v for k, v in os.environ.items() if not k.startswith('SHYP_')}
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    paths += [Path('/ql/data/scripts'), Path('/ql/scripts')]
    python_code = ('import importlib.util,sys; p=sys.argv[1]; '
                   's=importlib.util.spec_from_file_location("ql_notify",p); '
                   'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                   'm.send(sys.argv[2],sys.argv[3])')
    commands = [[sys.executable, '-c', 'import notify,sys; notify.send(sys.argv[1],sys.argv[2])', TITLE, body]]
    for directory in paths:
        if (directory / 'notify.py').is_file():
            commands.append([sys.executable, '-c', python_code, str(directory / 'notify.py'), TITLE, body])
        if (directory / 'sendNotify.js').is_file():
            commands.append(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(directory / 'sendNotify.js'), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, env=env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=25, check=False)
            if result.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '通知不可用或发送失败，保留业务退出码'


def main():
    start = time.monotonic()
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}')
    lines = [line.strip() for line in os.getenv('SHYP_ACCOUNTS', '').splitlines() if line.strip()]
    # 即使某账号配置错误也预先登记所有可识别凭据，避免后续身份字段回显凭据。
    for line in lines:
        try:
            parse_account(line)
        except Failure:
            pass
    dry = os.getenv('SHYP_DRY_RUN', '0').lower() in TRUE
    log(f'运行模式：{"断网预演" if dry else "正式"}；账号数量：{len(lines)}')
    results = []
    configuration_error = False
    try:
        dry = flag('SHYP_DRY_RUN')
        unfavor = flag('SHYP_UNFAVOR')
        tasks = {x.strip() for x in os.getenv('SHYP_TASKS', 'read,video').split(',') if x.strip()}
        if not tasks or tasks - (set(JOBS) | {'query'}) or ('query' in tasks and len(tasks) > 1):
            raise Failure('任务开关无效；query 必须单独使用')
        if unfavor and 'favor' not in tasks:
            raise Failure('取消收藏须同时显式启用 favor')
        if not lines:
            raise Failure('缺少 SHYP_ACCOUNTS，每个非空行一个账号 JSON')
        for index, line in enumerate(lines, 1):
            results.append(run_account(line, index, tasks, dry, unfavor))
            if not dry and index < len(lines):
                time.sleep(random.uniform(5, 10))
    except (Failure, KeyboardInterrupt):
        configuration_error = True
        log('❌ 配置错误或运行中断，请检查环境变量及运行状态')
    failed = sum(r['failure'] > 0 for r in results) + max(0, len(lines) - len(results))
    success = sum(r['failure'] == 0 for r in results)
    code = 1 if configuration_error or failed else 0
    status = ('configuration-error' if configuration_error else 'partial-failure' if failed and success
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(status=status, accounts=len(lines), success=success, failure=failed,
                   duration=round(time.monotonic()-start, 2), dryRun=dry,
                   subtasks={key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')})
    try:
        notification = notify(summary, dry)
    except Exception:
        notification = '通知失败，保留业务退出码'
    summary['notification'] = notification
    log('--------------------------------------------------')
    log(f'最终任务统计：账号 {len(lines)}，成功 {success}，失败 {failed}；子任务 {summary["subtasks"]}')
    log(f'通知状态：{notification}')
    log(f'总耗时：{time.monotonic()-start:.2f}秒；完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
