#!/usr/bin/env python3
# name: 小米运动账号验证与步数上传
# cron: 46 0 * * *
# 上游：Sitoi/dailycheckin dailycheckin/mimotion/main.py，MIT。
# 上游未声明 cron；此处建议每天 20:00，默认只验证登录。
# MIT License
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
"""独立维护版本；无需 dailycheckin 或 config.json。
MIMOTION_ACCOUNTS：每个非空行一个 手机号或邮箱|密码，仅在第一个 | 分割。
也可每行使用 JSON 对象，保留 phone/password/min_step/max_step 字段。
手机号或邮箱及密码在 Zepp Life 中注册、绑定或设置；不是小米账号密码。
MIMOTION_ACTION=login（默认）只验证登录；upload 显式允许修改当天步数。
上传账号必须使用 JSON 行并包含 data_json（本人的当天运动数据数组或其
JSON 字符串）、last_deviceid（本人的设备标识）。从本人 Zepp Life 同步请求的
表单中取得这些字段，URL 编码的 data_json 须先解码；不要分享抓包或凭据。
不提供、不合成固定心率/睡眠/设备数据；保留本人提供的其它字段。
min_step/max_step 默认 10000/19999，均可逐账号覆盖；必须保证其为本人
授权的数据修改范围。只有 summary.stp.ttl 被替换，不伪称真实运动结果。
MIMOTION_DRY_RUN=1 全程断网；QINGLONG_NOTIFY=0 关闭通知。
兼容 MIMOTION 环境变量的原始账号对象数组，不读取私有配置文件。
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

TITLE = '小米运动账号验证与步数上传'
FALSE_VALUES = {'0', 'false', 'no', 'off'}
HEADERS = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
           'User-Agent': 'MiFit/6.12.0 (MCE16; Android 16; Density/1.5)',
           'app_name': 'com.xiaomi.hm.health'}
TIMEOUT = 15
MAX_BYTES = 1048576


class TaskError(Exception):
    pass


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def enabled(name, default='0'):
    return os.environ.get(name, default).strip().lower() not in FALSE_VALUES | {''}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把凭据转发给重定向目标。
        return None


def request_json(url, fields=None, headers=None):
    if enabled('MIMOTION_DRY_RUN'):
        raise TaskError('预演禁止网络请求')
    data = None if fields is None else urllib.parse.urlencode(fields).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers=headers or HEADERS)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise TaskError('接口响应过大')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError('接口响应结构异常')
        return result
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise TaskError('请求限流，请稍后重试') from None
        raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
    except (urllib.error.URLError, OSError, ValueError):
        raise TaskError('网络、超时或响应解析失败') from None


def ensure_no_error(result):
    for key in ('code', 'error_code', 'result'):
        if key in result and result[key] not in (0, '0', 'ok', 'success'):
            raise TaskError('接口返回业务失败')
    if result.get('error'):
        raise TaskError('接口返回业务错误')


def identity(result, secrets):
    # 仅展示明确的官方非敏感身份字段，不打印整个响应。
    for obj in (result, result.get('user_info'), result.get('token_info')):
        if not isinstance(obj, dict):
            continue
        for key in ('nickname', 'username', 'display_name', 'user_id'):
            value = obj.get(key)
            if isinstance(value, (str, int)) and str(value):
                text = str(value)
                if any(secret and secret in text for secret in secrets):
                    continue
                if re.search(r'(?:\+?86)?1\d{10}', text):
                    continue
                log(f'官方账号身份 {key}: {json.dumps(text, ensure_ascii=False)}')


def login(account):
    phone = account['phone']
    user = '+86' + phone if re.fullmatch(r'1\d{10}', phone) else phone
    third = 'huami_phone' if user != phone else 'huami'
    first = request_json('https://api-user.zepp.com/registrations/' +
                         urllib.parse.quote(user, safe='') + '/tokens', {
        'client_id': 'HuaMi', 'country_code': 'CN', 'json_response': 'true',
        'name': user, 'password': account['password'],
        'redirect_uri': 'https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html',
        'state': 'REDIRECTION', 'token': 'access'})
    ensure_no_error(first)
    access = first.get('access')
    if not isinstance(access, str) or not access:
        raise TaskError('登录未返回有效授权凭据')
    second = request_json('https://account.zepp.com/v2/client/login', {
        'app_name': 'com.xiaomi.hm.health', 'country_code': 'CN', 'code': access,
        'device_id': str(uuid.uuid4()), 'device_model': 'android_phone',
        'app_version': '6.12.0', 'grant_type': 'access_token',
        'allow_registration': 'false',
        'dn': 'account.zepp.com,api-user.zepp.com,api-mifit.zepp.com,api-watch.zepp.com,app-analytics.zepp.com,api-analytics.huami.com,auth.zepp.com',
        'source': 'com.xiaomi.hm.health', 'third_name': third})
    ensure_no_error(second)
    token = second.get('token_info')
    if not isinstance(token, dict) or any(not token.get(k) for k in
                                          ('login_token', 'user_id', 'app_token')):
        raise TaskError('登录未返回完整账号凭据')
    if not isinstance(token['app_token'], str):
        raise TaskError('登录凭据类型异常')
    identity(second, [phone, account['password'], access,
                      str(token['login_token']), token['app_token']])
    return token


def get_time():
    try:
        value = request_json('https://acs.m.taobao.com/gw/mtop.common.getTimestamp/')['data']['t']
        if not str(value).isdigit():
            raise ValueError()
        log('时间服务获取成功')
        return str(value)
    except (TaskError, KeyError, TypeError, ValueError):
        log('⚠️ 时间服务不可用，使用本地毫秒时间')
        return str(int(time.time() * 1000))


def parse_account(raw):
    if isinstance(raw, dict):
        account = dict(raw)
    elif isinstance(raw, str) and raw.lstrip().startswith('{'):
        try:
            account = json.loads(raw)
        except ValueError:
            raise TaskError('账号 JSON 格式错误') from None
    elif isinstance(raw, str) and '|' in raw:
        phone, password = raw.split('|', 1)
        account = {'phone': phone.strip(), 'password': password}
    else:
        raise TaskError('账号应为手机号或邮箱|密码，或单行 JSON 对象')
    if not isinstance(account, dict) or any(not isinstance(account.get(k), str)
                                          or not account[k].strip()
                                          for k in ('phone', 'password')):
        raise TaskError('缺少有效 phone/password 凭据')
    return account


def prepare_upload(account):
    try:
        low = int(account.get('min_step', os.environ.get('MIMOTION_MIN_STEP', '10000')))
        high = int(account.get('max_step', os.environ.get('MIMOTION_MAX_STEP', '19999')))
        if not 0 <= low <= high <= 100000:
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise TaskError('步数范围无效，应满足 0≤最小值≤最大值≤100000') from None
    device = account.get('last_deviceid')
    payload = account.get('data_json')
    if not isinstance(device, str) or not device.strip():
        raise TaskError('上传须提供本人 last_deviceid，禁止使用上游固定设备标识')
    try:
        if isinstance(payload, str):
            payload = json.loads(payload)
        # 复制输入；仅允许一个当天记录，防止把其它日期一并上传。
        payload = json.loads(json.dumps(payload))
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError()
        record = payload[0]
        if record['date'] != time.strftime('%Y-%m-%d'):
            raise ValueError()
        if not isinstance(record.get('data'), list) or not record['data']:
            raise ValueError()
        summary = record['summary']
        was_string = isinstance(summary, str)
        if was_string:
            summary = json.loads(summary)
        if not isinstance(summary['stp']['ttl'], int):
            raise ValueError()
        step = random.randint(low, high)
        summary['stp']['ttl'] = step
        record['summary'] = json.dumps(summary, separators=(',', ':')) if was_string else summary
        encoded = json.dumps(payload, separators=(',', ':'))
        if len(encoded.encode('utf-8')) > MAX_BYTES:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise TaskError('data_json 须为本人当天的一条完整运动记录，含 data 和 summary.stp.ttl') from None
    return encoded, device, step


def upload(token, prepared):
    payload, device, step = prepared
    result = request_json('https://api-mifit-cn.huami.com/v1/data/band_data.json?&t=' + get_time(), {
        'userid': token['user_id'], 'last_sync_data_time': '1628256960',
        'device_type': '0', 'last_deviceid': device, 'data_json': payload},
        {'apptoken': token['app_token'], 'Content-Type': 'application/x-www-form-urlencoded'})
    # HTTP 成功不代表业务成功；绝不直接打印接口 message。
    if type(result.get('code')) not in (int, str) or result['code'] not in (0, '0') or result.get('message') != 'success':
        raise TaskError('运动上传未返回 code=0 且 message=success，未确认成功')
    log(f'✅ 服务端确认上传成功，提交步数 {step}（不代表真实运动核验）')


def notify_worker(dry):
    if dry:
        def deny(*args, **kwargs):
            raise OSError('dry-run network disabled')
        socket.socket = deny
        socket.create_connection = deny
        socket.getaddrinfo = deny
    # 通知库输出完全捕获，防止推送配置或请求响应泄漏。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            try:
                import notify
            except ImportError:
                paths = []
                if os.environ.get('QINGLONG_NOTIFY_DIR'):
                    paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
                paths += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
                path = next((p for p in paths if p.is_file()), None)
                if path is None:
                    return 3
                spec = importlib.util.spec_from_file_location('notify', path)
                notify = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(notify)
            notify.send(TITLE, sys.stdin.read())
            return 0
        except Exception:
            return 4


def send_notification(body, dry):
    if not enabled('QINGLONG_NOTIFY', '1'):
        return '已关闭'
    child_env = {k: v for k, v in os.environ.items() if k != 'MIMOTION' and not k.startswith('MIMOTION_')}
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 '--notify-worker', 'dry' if dry else 'live'],
                                input=body, text=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20, env=child_env)
        if result.returncode == 0:
            return '已调用通知模块（预演网络已禁用）' if dry else '已调用通知模块'
        if result.returncode == 3:
            return '通知模块不可用，已保留业务退出码'
        return '预演通知网络受限或发送失败，已保留业务退出码' if dry else '通知发送失败，已保留业务退出码'
    except (OSError, subprocess.TimeoutExpired):
        return '通知不可用或超时，已保留业务退出码'


def main():
    started, start_text = time.monotonic(), stamp()
    dry = enabled('MIMOTION_DRY_RUN')
    action = os.environ.get('MIMOTION_ACTION', 'login').strip().lower()
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{start_text}；模式：{"断网预演" if dry else "正式"}；动作：{action if action in ("login", "upload") else "无效"}')
    results, errors, rows = [], [], []
    raw = os.environ.get('MIMOTION_ACCOUNTS', '')
    if raw.strip():
        rows = [line for line in raw.splitlines() if line.strip()]
    elif os.environ.get('MIMOTION', '').strip():
        try:
            rows = json.loads(os.environ['MIMOTION'])
            if not isinstance(rows, list):
                raise ValueError()
        except ValueError:
            rows = []
            errors.append('兼容 MIMOTION 必须为账号对象数组')
    if not rows:
        errors.append('未配置账号：请设置 MIMOTION_ACCOUNTS')
    if action not in ('login', 'upload'):
        errors.append('MIMOTION_ACTION 仅支持 login 或 upload')
    log(f'账号总数：{len(rows)}')
    for error in errors:
        log(f'❌ 配置错误：{error}')
    for index, row in enumerate(rows, 1):
        begin = time.monotonic()
        stages = []
        names = ['参数检查', '登录验证'] + (['运动上传'] if action == 'upload' else [])
        log(f'----- 账号 {index} -----')
        account, token, prepared = None, None, None
        failed = False
        for number, name in enumerate(names, 1):
            stage_start = time.monotonic()
            status = 'skipped'
            if failed or errors:
                log(f'阶段 {number}/{len(names)} {name}：⏭️ 前置条件失败，跳过；耗时 0.00秒')
            else:
                log(f'阶段 {number}/{len(names)} {name}：开始')
                try:
                    if number == 1:
                        account = parse_account(row)
                        if action == 'upload':
                            prepared = prepare_upload(account)
                    elif dry:
                        log('断网预演：仅验证执行计划，不调用业务接口')
                    elif name == '登录验证':
                        token = login(account)
                    else:
                        upload(token, prepared)
                    status = 'success'
                    log(f'阶段 {number} {name}：✅ {"预演检查通过" if dry else "成功"}；耗时 {time.monotonic()-stage_start:.2f}秒')
                except TaskError as exc:
                    failed, status = True, 'failure'
                    log(f'阶段 {number} {name}：❌ {exc}；耗时 {time.monotonic()-stage_start:.2f}秒')
                except Exception:
                    failed, status = True, 'failure'
                    log(f'阶段 {number} {name}：❌ 未预期的处理错误（详情已脱敏）；耗时 {time.monotonic()-stage_start:.2f}秒')
            stages.append(status)
        counts = {key: stages.count(key) for key in ('success', 'failure', 'skipped')}
        result = {'account': index, 'status': 'failure' if failed or errors else 'success',
                  'tasks': len(stages), **counts, 'alreadyComplete': 0,
                  'durationSeconds': round(time.monotonic()-begin, 3)}
        results.append(result)
        log(f'账号 {index} 统计：总任务 {len(stages)}，成功 {counts["success"]}，已完成 0，跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {result["durationSeconds"]}秒')
    success = sum(item['status'] == 'success' for item in results)
    failure = len(results) - success
    code = 1 if errors or failure else 0
    status = 'configuration-error' if errors else ('partial-failure' if failure and success else 'failure' if failure else 'dry-run' if dry else 'success')
    body = f'状态：{status}；账号总数 {len(rows)}；成功 {success}；失败 {failure}；配置错误 {len(errors)}。'
    if dry:
        body += '断网预演通过不代表业务成功。'
    notification = send_notification(body, dry)
    finish = stamp()
    log('----------------------------------------')
    log(body)
    totals = {key: sum(item[key] for item in results) for key in ('tasks', 'success', 'failure', 'skipped', 'alreadyComplete')}
    log(f'子任务统计：总数 {totals["tasks"]}，成功 {totals["success"]}，已完成 0，跳过 {totals["skipped"]}，失败 {totals["failure"]}')
    log(f'通知状态：{notification}')
    log(f'完成时间：{finish}；总耗时 {time.monotonic()-started:.2f}秒；最终状态：{status}')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(rows), 'success': success, 'failure': failure,
               'configurationErrors': len(errors), 'accountResults': results,
               'taskStatistics': totals, 'startTime': start_text, 'finishTime': finish,
               'notification': notification, 'exitCode': code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--notify-worker':
        sys.exit(notify_worker(sys.argv[2] == 'dry'))
    sys.exit(main())
