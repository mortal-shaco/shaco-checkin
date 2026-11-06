#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: ArityFlow 独立子站签到
# cron: 9 10 * * *
"""ArityFlow 独立子站签到；Python 3.9+。

来源: yan470777-commits/checkin / arityflow_checkin.py，MIT。
原脚本无版权声明，保留来源署名；本维护版本适用 MIT：
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

AF_ACCOUNTS 每行：HTTPS子站地址|JSON对象，例中字段名为 username、password，
可选 code（站点签到码）、cf_token（当次同源 Turnstile 令牌）。只按首个 | 分隔，
JSON 字符串可包含任意分隔符；多账号只能换行。地址从主站 /api/status 的
checkin_url 或官方签到入口获取；用户名和密码使用独立签到子站注册账号，
不应填写主站 API Key。签到码从官方活动说明获取。cf_token 从本人在该
子站完成验证后的浏览器开发者工具 /api/checkin 请求体获取，短时且通常单次
有效；需人机验证却未提供时失败退出，不依赖私有求解器或浏览器程序。

兼容原命令行：python candidate.py <子站地址> <用户名> <密码> [签到码]
优先使用环境变量，避免进程参数暴露密码。AF_PROXY 可指定本人可信的 HTTPS
API 转发根地址（将接收凭据）；严格验证 TLS，不再跳过证书校验。
AF_REMOTE 已禁用，避免把整个任务与凭据委托给外部执行器。
依赖 requests；需要图形验证码时另装公开包 ddddocr。无自动安装行为。
原脚本未声明 cron，本版默认每天 09:00，可在青龙调整。
AF_DRY_RUN=1 完全断网，QINGLONG_NOTIFY=0 可关闭通知。
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
        _ql_notify_identities = ('5acc9f86bbf1003a', 'scripts/arityflow_checkin.py', 'arityflow_checkin.py', 'arityflow_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import contextlib
import datetime as dt
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

TITLE = 'ArityFlow 独立子站签到'
CATALOG = '5acc9f86bbf1003a'
UA = 'ArityFlowCheckin/1.0'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
TIMEOUT = (10, 30)
MAX_BYTES = 4 * 1024 * 1024
_OCR = None


class TaskError(Exception):
    pass


def log(message):
    print(f'[{dt.datetime.now():%H:%M:%S}] {message}', flush=True)


def https_url(value):
    try:
        p = urlsplit(value)
        if (p.scheme != 'https' or not p.hostname or p.username or p.password
                or p.query or p.fragment or p.port == 0):
            raise ValueError
    except (ValueError, TypeError):
        raise TaskError('地址必须为不含凭据、查询参数或片段的 HTTPS 地址') from None
    return value.rstrip('/')


def read_accounts():
    raw = os.getenv('AF_ACCOUNTS', '')
    if raw.strip():
        entries = [line.strip() for line in raw.splitlines() if line.strip()]
    elif len(sys.argv) in (4, 5):
        entries = [sys.argv[1] + '|' + json.dumps(dict(
            username=sys.argv[2], password=sys.argv[3],
            code=sys.argv[4] if len(sys.argv) == 5 else ''))]
    else:
        raise TaskError('请配置 AF_ACCOUNTS，每行一个子站地址与账号对象')
    accounts = []
    for line in entries:
        try:
            base, data = line.split('|', 1)
            a = json.loads(data)
            if not isinstance(a, dict):
                raise ValueError
            for field in ('username', 'password'):
                if not isinstance(a.get(field), str) or not a[field].strip():
                    raise ValueError
            for field in ('code', 'cf_token'):
                if not isinstance(a.get(field, ''), str):
                    raise ValueError
            a['base'] = https_url(base.strip())
            accounts.append((a, None))
        except (ValueError, TypeError, TaskError):
            accounts.append((None, '账号配置无效，请检查 HTTPS 地址和账号 JSON 字段'))
    return accounts


def request_bytes(method, url, *, token=None, payload=None, proxy=False, image=False):
    # 每次独立请求，第三方图片不会收到授权头、Cookie 或 Referer。
    import requests
    headers = {'User-Agent': UA, 'Accept': 'image/*' if image else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if proxy:
        headers['X-Af-Proxy'] = '1'
    try:
        with requests.request(method, url, headers=headers, json=payload,
                              timeout=TIMEOUT, verify=True, allow_redirects=False,
                              stream=True) as response:
            chunks = bytearray()
            for chunk in response.iter_content(65536):
                chunks.extend(chunk)
                if len(chunks) > MAX_BYTES:
                    raise TaskError('接口响应超出安全大小限制')
            return response.status_code, bytes(chunks)
    except requests.RequestException:
        raise TaskError('网络请求失败或超时（连接详情已隐藏）') from None


def api(base, path, token=None, payload=None, proxy=False):
    status, raw = request_bytes('POST' if payload is not None else 'GET',
                                base + path, token=token, payload=payload, proxy=proxy)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise TaskError(f'接口返回非 JSON 数据（HTTP {status}）') from None
    if not isinstance(body, dict):
        raise TaskError('接口数据结构异常')
    return status, body


def status_of(base, token, proxy):
    http, body = api(base, '/api/checkin/status', token, proxy=proxy)
    if http != 200 or body.get('success') is False or type(body.get('checked_today')) is not bool:
        raise TaskError('状态查询失败或缺少明确的 checked_today 状态')
    return body


def identity(user, account):
    if not isinstance(user, dict):
        return
    for key in ('nickname', 'username', 'display_name', 'public_uid', 'uid'):
        value = user.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            value = str(value)
            # 只展示官方身份字段；若混入凭据或手机号则抑制。
            secrets = [account.get(k, '') for k in ('password', 'cf_token', 'code')]
            if any(s and s in value for s in secrets) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                continue
            log('官方账号身份：' + json.dumps(value, ensure_ascii=False))
            return


def solve_captcha(base, token, proxy):
    http, cap = api(base, '/api/captcha', token, proxy=proxy)
    # 只有接口明确表示未启用或不存在才允许不携带验证码；其余错误失败闭合。
    if http in (404, 410) or (http == 200 and cap.get('enabled') is False):
        return '', ''
    if http != 200 or cap.get('success') is False:
        raise TaskError('验证码获取失败')
    cid = cap.get('captcha_id')
    if not isinstance(cid, str) or not cid:
        raise TaskError('验证码缺少标识')
    if cap.get('image_url'):
        url = cap['image_url']
        try:
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError
        except (TypeError, ValueError):
            raise TaskError('验证码图片地址不安全') from None
        http, image = request_bytes('GET', url, image=True)
        if http != 200:
            raise TaskError('验证码图片下载失败')
    else:
        value = cap.get('image_base64') or cap.get('image')
        if not isinstance(value, str):
            raise TaskError('验证码缺少图片')
        try:
            image = base64.b64decode(value.split(',', 1)[-1], validate=True)
        except (ValueError, TypeError):
            raise TaskError('验证码图片解码失败') from None
    if not image:
        raise TaskError('验证码图片为空')
    global _OCR
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if _OCR is None:
                import ddddocr
                _OCR = ddddocr.DdddOcr(show_ad=False)
            answer = (_OCR.classification(image) or '').strip()
    except ImportError:
        raise TaskError('图形验证码需要公开依赖 ddddocr，请通过包管理器安装') from None
    except Exception:
        raise TaskError('图形验证码识别失败') from None
    return cid, answer


def run_account(a, proxy):
    base = proxy or a['base']
    started = time.monotonic()
    log('阶段 1/3：登录')
    http, body = api(base, '/api/auth/login', payload={
        'username': a['username'], 'password': a['password']}, proxy=bool(proxy))
    data = body.get('data') if isinstance(body.get('data'), dict) else {}
    token = body.get('token') or data.get('token')
    if http != 200 or body.get('success') is False or not isinstance(token, str) or not token:
        raise TaskError('登录失败，检查子站账号与密码')
    identity(body.get('user') or data.get('user'), a)
    log(f'✅ 登录完成，耗时 {time.monotonic() - started:.2f} 秒')
    started = time.monotonic()
    log('阶段 2/3：查询今日签到状态')
    state = status_of(base, token, bool(proxy))
    log(f'✅ 状态查询完成，耗时 {time.monotonic() - started:.2f} 秒')
    if state['checked_today']:
        log('阶段 3/3：☑️ 今日已签到，跳过提交，耗时 0.00 秒')
        return {'success': True, 'already': True, 'message': '今日已签到',
                'checkin_date': None, 'quota_awarded': None}
    verify = state.get('verify') if isinstance(state.get('verify'), dict) else {}
    if verify.get('enabled') and not a.get('cf_token'):
        raise TaskError('子站要求人机验证，请提供本人当次同源 cf_token 或到官方网页签到')
    if state.get('code_enabled') and not a.get('code'):
        raise TaskError('子站要求签到码，请从官方活动说明获取 code')
    started = time.monotonic()
    log('阶段 3/3：识别验证码并提交签到（最多四次）')
    for attempt in range(1, 5):
        cid, answer = solve_captcha(base, token, bool(proxy))
        if cid and not answer:
            log(f'⚠️ 第 {attempt}/4 次识别为空，换图重试')
            continue
        uncertain = False
        try:
            http, result = api(base, '/api/checkin', token, payload={
                'code': a.get('code', ''), 'captcha_id': cid,
                'captcha_answer': answer, 'cf_token': a.get('cf_token', '')}, proxy=bool(proxy))
        except TaskError:
            uncertain, http, result = True, 0, {}
        # 无论提交响应是否声称成功，均以只读状态确认入账；不把空 JSON 当成功。
        try:
            confirmed = status_of(base, token, bool(proxy))['checked_today']
        except TaskError:
            raise TaskError('提交后无法核实签到结果，请到官方网页核对，停止重复提交') from None
        if confirmed:
            log(f'✅ 提交后复查确认今日已签到，耗时 {time.monotonic() - started:.2f} 秒')
            data = result.get('data') if isinstance(result.get('data'), dict) else result
            reward = next((data[k] for k in ('reward', 'quota_awarded', 'amount', 'silver', 'credits')
                           if data.get(k) is not None), None)
            try:
                reward = int(float(reward)) if reward is not None else None
            except (ValueError, TypeError, OverflowError):
                reward = None
            date = data.get('date') or data.get('checkin_date')
            if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                date = None
            if reward is not None:
                log(f'签到奖励：{reward}')
            if date:
                log(f'签到日期：{date}')
            return {'success': True, 'already': False, 'message': '复查确认签到成功',
                    'checkin_date': date, 'quota_awarded': reward}
        if uncertain:
            raise TaskError('签到请求异常，复查仍未签到，停止重复提交')
        message = str(result.get('message') or result.get('detail') or '').lower()
        if any(key in message for key in ('turnstile', 'cf_token', '人机', 'verify')):
            raise TaskError('人机验证未通过，请重新取得本人当次令牌')
        if 'captcha' in message or '验证码' in message or http == 422:
            log(f'⚠️ 第 {attempt}/4 次验证码未通过，换图重试')
            continue
        raise TaskError('签到未获状态确认，停止提交（接口详情已隐藏）')
    raise TaskError('验证码重试次数已用完，未确认签到成功')


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE and switch != 'auto':
        return '通知开关无效，未发送'
    if switch == 'auto':
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
        names = [CATALOG, 'arityflow_checkin.py', 'candidate.py', Path(__file__).name]
        path = Path(__file__).as_posix()
        if '/scripts/' in path:
            names.append(path.split('/scripts/', 1)[1])
        if not any(s and any(fnmatch.fnmatchcase(n, s) for n in names) for s in selectors):
            return '未在通知名单中'
    body = (f"模式：{'断网预演' if dry else '正式'}；状态：{summary['status']}；"
            f"账号总数：{summary['accounts']}；成功：{summary['success']}；"
            f"失败：{summary['failure']}；跳过：{summary['skipped']}")
    # 青龙通知为可选集成，不承担业务 HTTP；子进程限时且不输出通知库原始日志。
    worker = r'''
import importlib.util, os, socket, sys
if sys.argv[1] == '1':
    def denied(*a, **kw):
        raise OSError('dry-run: network disabled')
    socket.socket = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
paths = []
if os.getenv('QINGLONG_NOTIFY_DIR'):
    paths.append(os.path.join(os.environ['QINGLONG_NOTIFY_DIR'], 'notify.py'))
paths += ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
try:
    import notify
except ImportError:
    notify = None
    for path in paths:
        if os.path.isfile(path):
            sys.path.insert(0, os.path.dirname(path))
            spec = importlib.util.spec_from_file_location('notify', path)
            notify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify)
            break
if notify is None or not callable(getattr(notify, 'send', None)):
    sys.exit(3)
notify.send(sys.argv[2], sys.argv[3])
'''
    try:
        result = subprocess.run([sys.executable, '-c', worker, '1' if dry else '0', TITLE, body],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=20, check=False)
        if dry:
            return '已执行断网通知尝试，未发送网络请求'
        return '通知调用完成' if result.returncode == 0 else '通知不可用或调用失败'
    except Exception:
        return '通知不可用或超时'


def main():
    started = time.monotonic()
    dry = os.getenv('AF_DRY_RUN', '').strip().lower() in TRUE
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；模式：' + ('断网预演' if dry else '正式'))
    stats = dict(accounts=0, success=0, failure=0, already=0, skipped=0)
    config_error = False
    try:
        accounts = read_accounts()
        stats['accounts'] = len(accounts)
        log(f'账号数：{len(accounts)}')
        if os.getenv('AF_REMOTE', '').strip():
            raise TaskError('AF_REMOTE 不受支持，请清除此变量并使用直接 HTTP 签到')
        proxy = https_url(os.environ['AF_PROXY'].strip()) if os.getenv('AF_PROXY', '').strip() else ''
        for index, (a, error) in enumerate(accounts, 1):
            before = time.monotonic()
            log(f'账号 {index}/{len(accounts)} 开始')
            result = 'failure'
            already = False
            try:
                if error:
                    config_error = True
                    raise TaskError(error)
                if dry:
                    log('阶段 1/3：✅ 参数检查通过，耗时 0.00 秒')
                    log('阶段 2/3：⏭️ 跳过登录与状态查询，耗时 0.00 秒')
                    log('阶段 3/3：⏭️ 跳过验证码、人机验证及签到，耗时 0.00 秒')
                    result = 'skipped'
                else:
                    account_result = run_account(a, proxy)
                    already = account_result['already']
                    print(account_result)
                    result = 'success'
            except TaskError as exc:
                log(f'❌ {exc}')
            except Exception:
                log('❌ 运行失败，请检查依赖或接口兼容性（异常详情已隐藏）')
            stats[result] += 1
            stats['already'] += int(already)
            log(f'账号 {index} 统计：总任务 1；成功 {int(result == "success" and not already)}；'
                f'已完成 {int(already)}；跳过 {int(result == "skipped")}；'
                f'失败 {int(result == "failure")}；耗时 {time.monotonic() - before:.2f} 秒')
    except TaskError as exc:
        config_error = True
        stats['failure'] = max(stats['failure'], stats['accounts'], 1)
        log(f'❌ 配置错误：{exc}')
    status = ('configuration-error' if config_error else
              'partial-failure' if stats['failure'] and stats['success'] else
              'failure' if stats['failure'] else 'dry-run' if dry else 'success')
    summary = dict(stats, status=status, dryRun=dry)
    notification = notify(summary, dry)
    log('----------------------------------------')
    log(f'任务统计：账号总数 {stats["accounts"]}；成功 {stats["success"]}；'
        f'已完成 {stats["already"]}；跳过 {stats["skipped"]}；失败 {stats["failure"]}')
    log(f'子任务统计：总数 {stats["accounts"]}；成功 {stats["success"] - stats["already"]}；'
        f'已完成 {stats["already"]}；跳过 {stats["skipped"]}；失败 {stats["failure"]}')
    log(f'通知状态：{notification}')
    log(f'完成时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic() - started:.2f} 秒；最终状态：{status}')
    # 保留上游命令行结果字典字段，另附唯一的结构化汇总。
    print(dict(success=not stats['failure'] and not dry, message='断网预演完成' if dry else status,
               checkin_date=None, quota_awarded=None))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return 2 if config_error else 1 if stats['failure'] else 0


if __name__ == '__main__':
    sys.exit(main())
