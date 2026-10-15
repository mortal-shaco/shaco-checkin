#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 顺丰快递积分任务
# cron: 16 1 1 1 1
"""顺丰快递积分任务，独立维护版本。

上游：Cat-zaizai/ZaiZaiCat-Checkin，script/sf/main.py、api.py、code.js。
Author: ZaiZaiCat
Date: 2025-01-20
许可证：MIT。原输入未提供其他版权声明。

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

SF_ACCOUNTS：每个非空行一个 JSON 对象，sign、channel、device_id 必填，
user_agent、account_name 可选。抓取自己顺丰 App 积分页面的分享登录请求
sign 查询参数及后续积分请求的 channel、deviceid 请求头；不要提供他人凭据。
可用 SF_CONFIG 指定自己的旧 token.json（sf.accounts 结构），无默认文件路径。
SF_TASK_CODES：逗号分隔的已审核日常任务代码，默认空，仅签到和查询；
不允许花费积分、下单、改资料或发布内容任务，不推测未知代码的作用。
SF_DRY_RUN=1：只验证配置、签名和任务代码解析，不联网、不变更账号。
原调度 1 1 1 1 1 保留（不是每日调度），可在青龙中自行调整。
"""
import base64
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

TITLE = '顺丰快递积分任务'
BASE = 'https://mcs-mimp-web.sf-express.com'
SYS_CODE = 'MCS-MIMP-CORE'
WEB_UA = 'Mozilla/5.0 (iPod; U; CPU iPhone OS 3_1 like Mac OS X; sq-AL) AppleWebKit/533.18.3 (KHTML, like Gecko) Version/4.0.5 Mobile/8B119 Safari/6533.18.3'
LOGIN_UA = 'SFMainland_Store_Pro/9.86.0.5 CFNetwork/3860.200.71 Darwin/25.1.0'
PATHS = {
    'sign': '/mcs-mimp/commonPost/~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage',
    'tasks': '/mcs-mimp/commonPost/~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES',
    'finish': '/mcs-mimp/commonPost/~memberEs~taskRecord~finishTask',
    'reward': '/mcs-mimp/commonNoLoginPost/~memberNonactivity~integralTaskStrategyService~fetchTasksReward',
    'info': '/mcs-mimp/commonPost/~memberIntegral~userInfoService~personalInfoNew',
}
SECRETS = []


def log(text):
    text = str(text)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    print(f'[{datetime.now():%H:%M:%S}] {text}', flush=True)


def enabled(name, default='0'):
    return os.getenv(name, default).strip().lower() not in ('', '0', 'false', 'no', 'off')


def sw8(path):
    def b64(value):
        return base64.b64encode(value.encode()).decode()
    # 对照 code.js ft：保留原 key、web 和 pathname，不依赖 JS 引擎。
    return '-'.join(['1', b64(str(uuid.uuid4())), b64(str(uuid.uuid4())), '0',
                     b64('fb40817085be4e398e0b6f4b08177746'), b64('web'),
                     b64('/n/ryqq/toplist/4'), b64(path)])


def signature(timestamp):
    value = f'wwesldfs29aniversaryvdld29&timestamp={timestamp}&sysCode={SYS_CODE}'
    return hashlib.md5(value.encode()).hexdigest()


class Failure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把 Cookie 或登录参数交给重定向目标。
        return None


class API:
    def __init__(self, account):
        self.account = account
        self.cookies = CookieJar()
        self.http = build_opener(NoRedirect(), HTTPCookieProcessor(self.cookies))
        self.uid = ''

    def request(self, path, body=None, headers=None):
        if enabled('SF_DRY_RUN'):
            raise Failure('预演禁止网络请求')
        req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                      headers=headers or {}, method='GET' if body is None else 'POST')
        try:
            with self.http.open(req, timeout=30) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise Failure('响应过大')
                data = json.loads(raw)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise Failure('HTTP 或网络请求失败（详情已脱敏）') from None
        except (ValueError, UnicodeError):
            raise Failure('响应不是有效 JSON') from None
        if not isinstance(data, dict) or data.get('success') is not True:
            raise Failure('接口未确认业务成功（不输出原始响应）')
        return data

    def login(self):
        query = urlencode({'bizCode': '622', 'source': 'SFAPP',
                           'sign': unquote(self.account['sign'].strip())})
        data = self.request('/mcs-mimp/share/app/shareLogin?' + query,
                            headers={'User-Agent': self.account.get('user_agent') or LOGIN_UA,
                                     'Content-Type': 'application/json', 'priority': 'u=3, i',
                                     'accept-language': 'zh-CN,zh-Hans;q=0.9'})
        obj = data.get('obj')
        if not isinstance(obj, dict) or not obj.get('userId') or not list(self.cookies):
            raise Failure('登录缺少用户信息或会话 Cookie')
        self.uid = str(obj['userId'])
        for cookie in self.cookies:
            SECRETS.append(cookie.value)
        if obj.get('token'):
            SECRETS.append(str(obj['token']))
        show_identity(obj)
        return '分享登录业务成功'

    def post(self, kind, body):
        path = PATHS[kind]
        timestamp = str(int(time.time() * 1000))
        referer = BASE + '/superWelfare?citycode=&cityname=&tab=0'
        if kind == 'finish':
            referer = BASE + '/home?from=qqjrwzx515&WC_AC_ID=111&WC_REPORT=111'
        elif kind == 'sign':
            referer = BASE + '/superWelfare?' + urlencode({'userId': self.uid, 'path': '/superWelfare',
                       'supportShare': 'YES', 'from': 'appIndex', 'tab': '1'})
        elif kind == 'info':
            referer = BASE + '/home?' + urlencode({'redirectUri': '/myPoints', 'userId': self.uid,
                                                  'from': 'appqiandao'})
        headers = {'User-Agent': self.account.get('user_agent') or WEB_UA,
                   'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*',
                   'timestamp': timestamp, 'signature': signature(timestamp), 'sw8': sw8(path),
                   'channel': 'appqiandao' if kind == 'info' else self.account['channel'],
                   'syscode': SYS_CODE, 'platform': 'SFAPP', 'Origin': BASE, 'Referer': referer,
                   'pragma': 'no-cache', 'cache-control': 'no-cache', 'sec-gpc': '1',
                   'accept-language': 'zh-CN,zh-Hans;q=0.9', 'priority': 'u=3, i'}
        if kind in ('sign', 'info'):
            headers['deviceid'] = self.account['device_id']
        return self.request(path, body, headers)


def show_identity(obj):
    for key in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'userId'):
        value = obj.get(key)
        if isinstance(value, (str, int)) and value != '':
            log(f'官方账号身份 {key}: {value}')


def extract_task_code(task):
    if task.get('taskCode'):
        return str(task['taskCode'])
    redirect = task.get('buttonRedirect', '')
    for candidate in (redirect, unquote(redirect)):
        params = parse_qs(urlparse(candidate).query)
        value = params.get('_ug_view_param', [''])[0]
        if not value and '_ug_view_param=' in candidate:
            value = candidate.split('_ug_view_param=', 1)[1]
        try:
            data = json.loads(unquote(value))
            if isinstance(data, dict) and data.get('taskId'):
                return str(data['taskId'])
        except (ValueError, TypeError):
            match = re.search(r'"taskId"\s*:\s*"([^"\n]+)"', unquote(value))
            if match:
                return match.group(1)
    return ''


def accounts_input():
    raw = os.getenv('SF_ACCOUNTS', '')
    if raw.strip():
        return [line for line in raw.splitlines() if line.strip()]
    config = os.getenv('SF_CONFIG', '').strip()
    if config:
        try:
            data = json.loads(Path(config).read_text(encoding='utf-8'))
            accounts = data['sf']['accounts']
            if not isinstance(accounts, list):
                raise ValueError()
            return accounts
        except (OSError, ValueError, KeyError, TypeError):
            raise Failure('SF_CONFIG 文件无法读取或结构错误') from None
    raise Failure('缺少 SF_ACCOUNTS，或显式指定的兼容配置 SF_CONFIG')


def validate_account(raw):
    try:
        account = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        raise Failure('账号行不是有效 JSON') from None
    if not isinstance(account, dict):
        raise Failure('账号必须是 JSON 对象')
    for key in ('sign', 'channel', 'device_id'):
        if not isinstance(account.get(key), str) or not account[key].strip():
            raise Failure(f'缺少必填字段 {key}')
    for key in ('sign', 'channel', 'device_id', 'user_agent'):
        value = account.get(key, '')
        if not isinstance(value, str) or '\n' in value or '\r' in value:
            raise Failure(f'字段 {key} 格式错误')
        if value:
            SECRETS.append(value)
    return account


def run_account(raw, index, dry, allow_codes):
    started = time.monotonic()
    stats = {'account': index, 'total': 0, 'success': 0, 'alreadyComplete': 0,
             'skipped': 0, 'failed': 0, 'points': 0, 'available_points': None}

    def stage(name, action):
        stats['total'] += 1
        step_start = time.monotonic()
        log(f'账号 {index} 阶段 {stats["total"]}：{name}')
        try:
            detail = action()
            stats['success'] += 1
            log(f'✅ {detail}；耗时 {time.monotonic() - step_start:.2f} 秒')
            return True
        except Exception as exc:
            stats['failed'] += 1
            log(f'❌ {str(exc) if isinstance(exc, Failure) else "响应结构或执行异常（详情已脱敏）"}；耗时 {time.monotonic() - step_start:.2f} 秒')
            return False

    holder = {}
    def config():
        holder['account'] = validate_account(raw)
        return '账号参数校验通过'
    try:
        if not stage('参数校验', config):
            return stats
        if dry:
            def preview():
                assert len(signature('1')) == 32
                assert len(sw8(PATHS['tasks']).split('-')) == 8
                assert extract_task_code({'buttonRedirect': 'https://example.invalid/?_ug_view_param=%7B%22taskId%22%3A%22preview%22%7D'}) == 'preview'
                return 'DRY_RUN_OK：仅本地校验；登录、签到、任务、奖励和积分查询均未联网'
            stage('断网预演', preview)
            return stats
        api = API(holder['account'])
        if not stage('分享登录', api.login):
            return stats
        def sign():
            obj = api.post('sign', {'comeFrom': 'vioin', 'channelFrom': 'SFAPP'}).get('obj')
            if not isinstance(obj, dict):
                raise Failure('签到响应结构错误')
            packages = obj.get('integralTaskSignPackageVOList', [])
            if not isinstance(packages, list):
                raise Failure('礼包响应结构错误')
            for package in packages:
                if not isinstance(package, dict):
                    raise Failure('礼包条目结构错误')
                name = package.get('commodityName', '未提供名称')
                expiry = package.get('invalidDate', '未提供有效期')
                if isinstance(name, str) and isinstance(expiry, str):
                    log(f'签到礼包：{name}；有效期至 {expiry}')
            if obj.get('hasFinishSign') == 1:
                stats['alreadyComplete'] += 1
                stats['success'] -= 1
            return f'签到已确认；连续天数 {safe_number(obj.get("countDay", 0))}；礼包数量 {len(packages)}'
        stage('签到领取礼包', sign)
        time.sleep(random.uniform(2, 5))
        tasks_holder = {}
        def tasks_query():
            obj = api.post('tasks', {'channelType': '1', 'deviceId': api.account['device_id']}).get('obj')
            if not isinstance(obj, dict) or not isinstance(obj.get('taskTitleLevels'), list):
                raise Failure('日常任务列表结构错误')
            tasks_holder['tasks'] = obj['taskTitleLevels']
            return f'任务列表业务成功；数量 {len(tasks_holder["tasks"])}'
        if stage('获取任务列表', tasks_query):
            for task in tasks_holder['tasks']:
                if not isinstance(task, dict):
                    stage('任务格式校验', lambda: (_ for _ in ()).throw(Failure('任务格式错误')))
                    continue
                code = extract_task_code(task)
                if task.get('taskPeriod') != 'D' or task.get('status') == 3 or code not in allow_codes:
                    stats['total'] += 1
                    if task.get('taskPeriod') == 'D' and task.get('status') == 3:
                        stats['alreadyComplete'] += 1
                        log(f'账号 {index} 阶段 {stats["total"]}：☑️ 日常任务已完成；耗时 0 秒')
                    else:
                        stats['skipped'] += 1
                        log(f'账号 {index} 阶段 {stats["total"]}：⏭️ 非日常任务或未列入安全允许清单；耗时 0 秒')
                    continue
                time.sleep(random.uniform(10, 15))
                def finish():
                    api.post('finish', {'taskCode': code})
                    return '日常任务完成接口确认成功'
                if stage('执行允许的日常任务', finish):
                    def reward():
                        obj = api.post('reward', {'channelType': '1', 'deviceId': api.account['device_id']}).get('obj')
                        if not isinstance(obj, list) or any(not isinstance(item, dict) for item in obj):
                            raise Failure('奖励响应结构错误')
                        points = sum(safe_number(item.get('point', 0)) for item in obj)
                        stats['points'] += points
                        return f'奖励领取业务成功；获得积分 {points}'
                    stage('领取任务奖励', reward)
        def info():
            obj = api.post('info', {}).get('obj')
            if not isinstance(obj, dict) or 'availablePoints' not in obj:
                raise Failure('积分响应缺少当前积分')
            show_identity(obj)
            stats['available_points'] = safe_number(obj['availablePoints'])
            return f'当前积分查询成功；积分 {stats["available_points"]}'
        stage('查询当前积分', info)
        return stats
    finally:
        stats['durationSeconds'] = round(time.monotonic() - started, 2)
        log(f'账号 {index} 统计：总阶段 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["durationSeconds"]} 秒')


def safe_number(value):
    if isinstance(value, bool):
        raise Failure('积分或天数不是有效数字')
    try:
        number = int(value)
        if number < 0 or str(number) != str(value):
            raise ValueError()
        return number
    except (ValueError, TypeError, OverflowError):
        raise Failure('积分或天数不是有效数字') from None


def notify(summary, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        log('通知：全局开关已关闭')
        return 'disabled'
    if dry:
        log('通知：断网预演，脱敏汇总仅写入日志，不调用可能联网的通知模块')
        return 'dry-run-local'
    body = f'状态：{summary["status"]}\n账号总数：{summary["accounts"]}\n成功数：{summary["successfulAccounts"]}\n失败数：{summary["failedAccounts"]}'
    try:
        # 通知是可选青龙运行集成，不属于业务依赖。
        import importlib
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
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
            log('⚠️ 通知不可用：未发现 notify.py；保持业务退出码')
            return 'unavailable'
        module.send(TITLE, body)
        log('通知：脱敏汇总已提交')
        return 'sent'
    except Exception:
        log('⚠️ 通知发送失败；保持业务退出码')
        return 'failed'


def main():
    start = time.monotonic()
    dry = enabled('SF_DRY_RUN')
    log('=' * 56)
    log(f'{TITLE}；开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}；模式 {"断网预演" if dry else "正式执行"}')
    results = []
    config_error = False
    try:
        accounts = accounts_input()
        if not accounts:
            raise Failure('账号列表为空')
        log(f'账号数量：{len(accounts)}')
        allow_codes = {code.strip() for code in os.getenv('SF_TASK_CODES', '').split(',') if code.strip()}
        for index, raw in enumerate(accounts, 1):
            results.append(run_account(raw, index, dry, allow_codes))
            if not dry and index < len(accounts):
                time.sleep(random.uniform(3, 8))
    except Exception as exc:
        config_error = True
        log(f'❌ 配置错误：{str(exc) if isinstance(exc, Failure) else "配置处理失败（详情已脱敏）"}')
    failed = sum(result['failed'] > 0 for result in results)
    successful = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = 'configuration-error' if config_error else ('partial-failure' if failed and successful else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(results),
               'successfulAccounts': successful, 'failedAccounts': failed, 'configurationError': config_error,
               'exitCode': exit_code, 'results': results}
    log('-' * 56)
    log(f'任务统计：账号总数 {len(results)}，成功 {successful}，失败 {failed}；子任务总数 {sum(r["total"] for r in results)}，成功 {sum(r["success"] for r in results)}，已完成 {sum(r["alreadyComplete"] for r in results)}，跳过 {sum(r["skipped"] for r in results)}，失败 {sum(r["failed"] for r in results)}')
    summary['notification'] = notify(summary, dry)
    summary['durationSeconds'] = round(time.monotonic() - start, 2)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log(f'结束时间 {summary["finishedAt"]}；总耗时 {summary["durationSeconds"]} 秒；最终状态 {status}；通知状态 {summary["notification"]}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
