# -*- coding: utf-8 -*-
# name: 安徽工业大学晚寝考勤
# cron: 26 21 * * *
# 上游未声明定时；建议每天北京时间 21:25，由实际校园签到窗口决定。
# @Author：Spance
# @Email: wqqd@spance.xyz
# @Version：v1.9（独立维护版）
# @Desc:安徽工业大学考勤系统自动签到
# 来源：UnthinkingBrain/-_ahut_wqqd main.py
# License: MIT
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
"""配置说明见 contract.json。仅依赖 Python 标准库，不导入 config_loader。
AHUT_ACCOUNTS 每行 学号|密码，按第一个 | 分割；复杂配置每行一个 JSON 对象。
JSON 字段兼容 student_Id/password/is_encrypted，签到还须提供本人真实
latitude/longitude/locationAccuracy。不要用宿舍坐标代替实际位置。
默认 AHUT_ACTION=query；显式 sign 才会登记访问记录和提交签到。
-f/--file 支持 JSON 用户数组或 {"users": [...]}；未设置环境变量时兼容
同目录 users.json。不交互、不保存密码、不内置默认密码。
AHUT_DRY_RUN=1 完全断网，包括不调用可能联网的通知模块。
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
        _ql_notify_identities = ('ffb00b6d41f1e89f', 'scripts/task_ffb00b6d.py', 'task_ffb00b6d.py', 'task_ffb00b6d')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
from datetime import datetime, timezone, timedelta
import fnmatch
import hashlib
import http.cookiejar
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '安徽工业大学晚寝考勤'
CATALOG = 'ffb00b6d41f1e89f'
BASE = 'https://xskq.ahut.edu.cn/api'
TZ = timezone(timedelta(hours=8))
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
# 上游公开 OAuth 客户端标识；不是账号凭据。
CLIENT_AUTH = 'Basic Zmx5c291cmNlX3dpc2VfYXBwOkRBNzg4YXNkVURqbmFzZF9mbHlzb3VyY2VfZHNkYWREQUlVaXV3cWU='


def now():
    return datetime.now(TZ)


def log(text):
    print(f'[{now():%H:%M:%S}] {text}', flush=True)


class TaskError(Exception):
    pass


class AuthError(TaskError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def digest(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def generate_sign(url, token):
    timestamp = str(int(time.time() * 1000))
    value = digest(urllib.parse.urlparse(url).path + '?sign=' + digest(timestamp + token))
    return value + '1.' + base64.b64encode(timestamp.encode()).decode()


def generate_signCode(timestamp_ms):
    dt = datetime.fromtimestamp(timestamp_ms / 1000, TZ)
    weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][dt.weekday()]
    month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][dt.month - 1]
    return digest(f'{weekday} {month} {dt.day:02d} {dt.year} {dt:%H:%M:%S} GMT+0800 (中国标准时间)')


def generate_stuTaskId(lat, lng, acc, date, taskId, fileId=''):
    return digest(json.dumps(dict(latitude=str(lat), longitude=str(lng),
                                 locationAccuracy=str(acc), signDate=date,
                                 taskId=taskId, fileId=fileId), separators=(',', ':')))


def checked(response):
    if response.get('code') == 200 and response.get('success') is not False and response.get('data') is not False:
        return response.get('data')
    msg = response.get('msg')
    if response.get('code') in (401, '401') or any(x in str(msg) for x in ('请求未授权', '缺失身份信息', '鉴权失败')):
        raise AuthError('登录状态失效')
    raise TaskError('接口未确认业务成功（响应详情已隐藏）')


class Client:
    def __init__(self, account, dry):
        self.account = account
        self.dry = dry
        self.token = ''
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, path, params=None, body=None):
        if self.dry:
            raise TaskError('断网预演禁止 HTTP 请求')
        url = BASE + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Mobile Safari/537.36 MicroMessenger/8.0.61',
            'authorization': CLIENT_AUTH, 'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-With': 'com.tencent.mm', 'Origin': 'https://xskq.ahut.edu.cn',
            'Referer': 'https://xskq.ahut.edu.cn/wise/pages/ssgl/dormsign?&userId=' + self.account['student_Id']}
        if self.token:
            headers.update({'flysource-auth': 'bearer ' + self.token,
                            'flysource-sign': generate_sign(url, self.token)})
        request = urllib.request.Request(url, headers=headers, method=method,
                                         data=json.dumps(body).encode() if body is not None else None)
        # 仅只读请求重试；提交响应不明时绝不盲目重复签到。
        for attempt in range(4 if method == 'GET' else 1):
            try:
                with self.opener.open(request, timeout=20) as response:
                    if response.status != 200:
                        raise TaskError('HTTP 状态异常')
                    payload = response.read(1024 * 1024 + 1)
                if len(payload) > 1024 * 1024:
                    raise TaskError('响应超过大小限制')
                result = json.loads(payload)
                if not isinstance(result, dict):
                    raise TaskError('接口响应结构异常')
                return result
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    raise AuthError('登录状态失效') from None
                if method != 'GET' or exc.code < 500 or attempt == 3:
                    raise TaskError('HTTP 请求失败（详情已隐藏）') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if method != 'GET' or attempt == 3:
                    raise TaskError('网络失败或超时；写入结果可能不明，请人工核对') from None
            except (ValueError, UnicodeError):
                raise TaskError('接口未返回有效 JSON') from None
            time.sleep(1 + attempt)

    def login(self):
        a = self.account
        result = self.request('POST', '/flySource-auth/oauth/token', params={
            'tenantId': '000000', 'username': a['student_Id'],
            'password': a['password'] if a['is_encrypted'] else digest(a['password']),
            'type': 'account', 'grant_type': 'password', 'scope': 'all'})
        # 保留上游 refresh_token 契约；没有接口变更证据，不猜测新令牌字段。
        token = result.get('refresh_token')
        if not isinstance(token, str) or not token or result.get('error'):
            raise TaskError('登录失败：请核对学号、密码和加密标志')
        self.token = token
        identity = result.get('userName')
        if isinstance(identity, str) and identity:
            # 身份按官方值显示；避免凭据字段、手机号被误标为昵称。
            if (identity not in (a['student_Id'], a['password'], token)
                    and not re.search(r'(?<!\d)1\d{10}(?!\d)', identity)):
                log('官方账号姓名：' + identity.replace('\r', ' ').replace('\n', ' '))

    def business(self, method, path, params=None, body=None, sign=False):
        for attempt in range(4):
            try:
                response = self.request(method, path, params, body)
                if sign and '您今天已完成签到' in str(response.get('msg', '')):
                    return 'already'
                data = checked(response)
                if sign and data is False:
                    raise TaskError('签到接口明确返回失败')
                return data
            except AuthError:
                if attempt == 3:
                    raise
                log('登录过期，重新登录后恢复当前阶段')
                self.login()


def load_accounts(file):
    if file:
        path = Path(file)
    elif os.environ.get('AHUT_ACCOUNTS', '').strip():
        return [line for line in os.environ['AHUT_ACCOUNTS'].splitlines() if line.strip()]
    else:
        path = Path(__file__).with_name('users.json')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise TaskError('未提供有效账号配置；设置 AHUT_ACCOUNTS 或使用 -f JSON文件') from None
    if isinstance(data, dict):
        data = data.get('users')
    if not isinstance(data, list) or not data:
        raise TaskError('配置文件必须包含非空账号数组')
    return data


def parse_account(raw, action):
    try:
        if isinstance(raw, str):
            if raw.lstrip().startswith('{'):
                raw = json.loads(raw)
            else:
                student, password = raw.split('|', 1)
                raw = dict(student_Id=student.strip(), password=password)
        if not isinstance(raw, dict):
            raise ValueError()
        a = dict(raw)
        a['student_Id'] = str(a['student_Id']).strip()
        if not a['student_Id'].isdigit() or not isinstance(a['password'], str) or not a['password']:
            raise ValueError()
        if a.get('is_encrypted', 0) not in (0, 1, False, True):
            raise ValueError()
        a['is_encrypted'] = bool(a.get('is_encrypted', 0))
        if a['is_encrypted'] and not re.fullmatch('[a-fA-F0-9]{32}', a['password']):
            raise ValueError()
        if action == 'sign':
            for key, low, high in [('latitude', -90, 90), ('longitude', -180, 180), ('locationAccuracy', 0, 10000)]:
                a[key] = float(a[key])
                if not math.isfinite(a[key]) or not low <= a[key] <= high:
                    raise ValueError()
        return a
    except (KeyError, ValueError, TypeError, OverflowError):
        raise TaskError('账号配置无效；签到需提供真实经纬度与定位精度，MD5 密码需设置 is_encrypted=1') from None


def run_account(raw, index, action, dry):
    start = time.monotonic()
    stats = dict(total=6, success=0, alreadyComplete=0, skipped=0, failed=0)
    log(f'账号 {index} 开始')
    stage = 0
    try:
        a = parse_account(raw, action)
        if not dry and action == 'sign' and now().strftime('%H:%M:%S') < '21:20:00':
            raise TaskError('北京时间未到 21:20，禁止提交签到')
        client = Client(a, dry)
        task_id = None
        room = None
        for stage, name in enumerate(['密码登录', '获取签到任务', '检查微信配置', '登记签到访问窗口', '读取宿舍信息', '提交晚寝签到'], 1):
            tick = time.monotonic()
            log(f'账号 {index} 阶段 {stage}/6 {name}')
            if action == 'query' and stage in (4, 6):
                stats['skipped'] += 1
                log('⏭️ 查询模式跳过写入，耗时 0.00 秒')
                continue
            if dry:
                stats['skipped'] += 1
                log('⏭️ 断网预演：配置检查通过，不发送请求，耗时 0.00 秒')
                continue
            if stage == 1:
                client.login()
            elif stage == 2:
                data = client.business('GET', '/flySource-yxgl/dormSignTask/getStudentTaskPage',
                                       dict(userDataType='student', current=1, size=15))
                records = data.get('records') if isinstance(data, dict) else None
                if not isinstance(records, list) or not records or not isinstance(records[0], dict) or not records[0].get('taskId'):
                    raise TaskError('未发现有效签到任务')
                task_id = records[0]['taskId']
            elif stage == 3:
                config_url = f'https://xskq.ahut.edu.cn/wise/pages/ssgl/dormsign?taskId={task_id}'
                client.business('GET', '/flySource-base/wechat/getWechatMpConfig',
                                dict(configUrl=config_url, autoSign=1, scanSign=0, userId=a['student_Id']))
            elif stage == 4:
                client.business('POST', '/flySource-base/apiLog/save', {'menuTitle': '晚寝签到'})
            elif stage == 5:
                data = client.business('GET', '/flySource-yxgl/dormSignTask/getTaskByIdForApp',
                                       dict(taskId=task_id, signDate=now().strftime('%Y-%m-%d')))
                dorm = data.get('dormitoryRegisterVO') if isinstance(data, dict) else None
                if not isinstance(dorm, dict) or not dorm.get('roomId'):
                    raise TaskError('宿舍信息缺失，禁止继续签到')
                room = dorm['roomId']
            else:
                # 不使用上游随机位置偏移；仅提交用户提供的真实定位。
                time.sleep(4)
                lat, lng, acc = a['latitude'], a['longitude'], a['locationAccuracy']
                result = client.business('POST', '/flySource-yxgl/dormSignRecord/stuSign', body={
                    'signType': 0, 'taskId': task_id, 'signLat': lat, 'signLng': lng,
                    'locationAccuracy': acc, 'stuTaskId': generate_stuTaskId(lat, lng, acc, now().strftime('%Y-%m-%d'), task_id),
                    'scanCode': '', 'scanType': '', 'roomId': room, 'signKey': room,
                    # 上游错误地传入秒，修正为函数契约要求的毫秒。
                    'signCode': generate_signCode(int(time.time() * 1000))}, sign=True)
                if result == 'already':
                    stats['alreadyComplete'] += 1
                    log(f'☑️ 官方确认今天已完成签到，耗时 {time.monotonic() - tick:.2f} 秒')
                    continue
            stats['success'] += 1
            log(f'✅ 阶段完成，耗时 {time.monotonic() - tick:.2f} 秒')
        ok = True
    except Exception as exc:
        ok = False
        stats['failed'] += 1
        stats['skipped'] = stats['total'] - stats['success'] - stats['alreadyComplete'] - stats['failed']
        # 未知异常不输出异常文本，避免 urllib 将账号查询串写入日志。
        detail = str(exc) if isinstance(exc, TaskError) else '响应结构或执行异常（详情已隐藏）'
        log(f'❌ 账号 {index} 阶段 {stage}/6 失败：{detail}，耗时 {time.monotonic() - (tick if stage else start):.2f} 秒')
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic() - start:.2f} 秒')
    return dict(account=index, success=ok, statistics=stats)


def notify(summary, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | FALSE | {'auto'}:
        log('⚠️ 通知开关无效，保持业务退出码')
        return '配置无效'
    if switch == 'auto' and 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        script = Path(__file__).resolve()
        relative = script.name
        if 'scripts' in script.parts:
            position = len(script.parts) - 1 - list(reversed(script.parts)).index('scripts')
            relative = '/'.join(script.parts[position + 1:])
        names = (CATALOG, script.name, str(script), relative, 'scripts/' + relative)
        if not any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in selectors if pattern):
            return '未选中'
    body = f'账号总数 {summary["accounts"]}，成功 {summary["success"]}，失败 {summary["failed"]}；状态 {summary["status"]}'
    if dry:
        log('通知预演：' + body + '（断网模式不调用通知模块）')
        return '断网预演'
    # 在子进程中调用青龙通知，限制耗时并抑制第三方输出，保持业务退出码。
    python_code = '''import importlib.util, sys
p, title, body = sys.argv[1:]
if p:
    spec = importlib.util.spec_from_file_location("notify", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(title, body)
'''
    candidates = [None]
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        candidates.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    candidates += [Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')]
    for path in candidates:
        if path is not None and not path.is_file():
            continue
        try:
            proc = subprocess.run([sys.executable, '-c', python_code, str(path) if path else '', TITLE, body],
                                  timeout=25, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 青龙通知不可用或发送失败；业务退出码保持不变')
    return '不可用或失败'


def main():
    start = time.monotonic()
    dry = os.environ.get('AHUT_DRY_RUN', '0').lower() in TRUE
    action = os.environ.get('AHUT_ACTION', 'query').lower()
    log('=' * 48)
    log(TITLE + f' | 开始时间 {now():%Y-%m-%d %H:%M:%S %z}')
    log(f'运行模式：{"断网预演" if dry else "正式"} / {action if action in ("query", "sign") else "无效动作"}')
    results = []
    configuration_error = False
    accounts = []
    try:
        parser = argparse.ArgumentParser(description=TITLE)
        parser.add_argument('-f', '--file', help='用户 JSON 配置文件路径')
        args, unknown = parser.parse_known_args()
        if unknown or action not in ('query', 'sign') or os.environ.get('AHUT_DRY_RUN', '0').lower() not in TRUE | FALSE:
            raise TaskError('参数无效；AHUT_ACTION 仅支持 query 或 sign，AHUT_DRY_RUN 仅支持布尔开关')
        accounts = load_accounts(args.file)
        log(f'账号数量：{len(accounts)}')
        for index, account in enumerate(accounts, 1):
            results.append(run_account(account, index, action, dry))
    except TaskError as exc:
        configuration_error = True
        log(f'账号数量：{len(accounts)}；❌ 配置错误：{exc}')
    succeeded = sum(r['success'] for r in results)
    failed = len(results) - succeeded
    status = ('configuration-error' if configuration_error else 'partial-failure' if failed and succeeded
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(status=status, mode='dry-run' if dry else action,
                   accounts=len(accounts), success=succeeded, failed=failed,
                   configurationErrors=int(configuration_error), results=results)
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic() - start, 2)
    log('-' * 48)
    log(f'任务统计：账号总数 {len(accounts)}，成功 {succeeded}，失败 {failed}，配置错误 {int(configuration_error)}')
    totals = {k: sum(r['statistics'][k] for r in results) for k in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'总耗时 {summary["elapsedSeconds"]:.2f} 秒；通知状态：{summary["notification"]}')
    log(f'完成时间 {now():%Y-%m-%d %H:%M:%S %z}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return 1 if configuration_error or failed else 0


if __name__ == '__main__':
    sys.exit(main())
