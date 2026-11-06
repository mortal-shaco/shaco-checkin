# -*- coding: utf-8 -*-
# name: 今日校园广东海洋大学签到
# cron: 58 9 * * *
# SPDX-License-Identifier: GPL-3.0
# Derived from OrionAAAA/cpdaily_auto_signin, master 22684ef9dcfa43d0713185f01645ae967baaf1d1
# Sources: Fcpdaily-2.0.py, login.py, imageRec.py, creatExtention.py
# 本脚本仅供学习交流，否则后果自负
"""独立维护版本。CPDAILY_ACCOUNTS 每个非空行为一个 JSON 账号对象。
字段沿用 username/password/longitude/latitude/abnormalReason/position。
可选 cookie 使用本人官方会话跳过登录。默认只查询，CPDAILY_SUBMIT=1 才提交。
填写本人真实位置和异常原因。无原始 cron，建议每天 8 点并按学校签到窗口调整。
仅在登录需要验证码时加载 ddddocr，使用公共发行包自带模型，不下载模型。
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
        _ql_notify_identities = ('7f49669014a1d273', 'scripts/fcpdaily_2_0.py', 'fcpdaily_2_0.py', 'fcpdaily_2_0')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import configparser
import contextlib
import datetime
import fnmatch
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from html.parser import HTMLParser
from urllib.parse import urlparse

TITLE = '今日校园广东海洋大学签到'
BASE = 'https://gdou.cpdaily.com'
AUTH = 'https://authserver.gdou.edu.cn'
LOGIN = AUTH + '/authserver/login?service=https%3A%2F%2Fgdou.cpdaily.com%2Fportal%2Flogin'
PREFIX = BASE + '/wec-counselor-sign-apps/stu/sign/'
TENANT = '1018762497675547'
UA = ('Mozilla/5.0 (Linux; Android 4.4.4; vivo xplay6 Build/KTU84P) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 '
      'Safari/537.36 yiban/8.1.11 cpdaily/8.1.11 wisedu/8.1.11')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(text):
    print('[' + datetime.datetime.now().strftime('%H:%M:%S') + '] ' + text, flush=True)


def switch(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower().strip() in TRUE:
        return True
    if value.lower().strip() in FALSE:
        return False
    raise TaskError(name + ' 必须使用布尔开关值')


def accounts_from_env():
    raw = os.environ.get('CPDAILY_ACCOUNTS', '')
    if raw.strip():
        return [line.strip() for line in raw.splitlines() if line.strip()]
    legacy = os.environ.get('CPDAILY_CONFIG')
    if legacy:
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open(legacy, encoding='utf-8') as handle:
                config.read_file(handle)
            return [json.dumps(dict(config[section]), ensure_ascii=False)
                    for section in reversed(config.sections())]
        except Exception:
            raise TaskError('旧版配置文件无法读取或格式错误') from None
    raise TaskError('请配置 CPDAILY_ACCOUNTS，每行一个 JSON 账号对象')


def parse_account(line, submit):
    try:
        account = json.loads(line)
        if not isinstance(account, dict):
            raise ValueError()
        for field in ('username',):
            if not isinstance(account.get(field), str) or not account[field].strip():
                raise ValueError()
        if not account.get('cookie') and not account.get('password'):
            raise ValueError()
        for field in ('password', 'cookie'):
            if field in account and (not isinstance(account[field], str)
                                     or '\n' in account[field] or '\r' in account[field]):
                raise ValueError()
        if submit:
            for field, limit in (('longitude', 180), ('latitude', 90)):
                number = float(account[field])
                if not math.isfinite(number) or abs(number) > limit:
                    raise ValueError()
                account[field] = number
            if not isinstance(account.get('position'), str) or not account['position'].strip():
                raise ValueError()
            # 不再默认为所有账号提交“位置异常”。显式确认本人实际位置状态。
            value = account.get('isMalposition')
            if isinstance(value, str) and value in ('0', '1'):
                value = int(value)
            if type(value) is not int or value not in (0, 1):
                raise ValueError()
            account['isMalposition'] = value
            reason = account.get('abnormalReason', account.get('abnormalreason', ''))
            if not isinstance(reason, str) or (value == 1 and not reason.strip()):
                raise ValueError()
            account['abnormalReason'] = reason
        return account
    except (ValueError, TypeError, KeyError, OverflowError):
        raise TaskError('账号配置不完整或格式错误，请核对凭据及提交所需定位字段') from None


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') in ('lt', 'execution', '_eventId', 'rmShown'):
            self.fields[attrs['name']] = attrs.get('value', '')


def request(session, method, url, **kwargs):
    """禁止跨站凭据转发，允许 CAS 登录产生的可信双站点重定向。"""
    from requests import RequestException
    allowed = {'gdou.cpdaily.com', 'authserver.gdou.edu.cn'}
    try:
        for _ in range(8):
            parts = urlparse(url)
            if parts.scheme != 'https' or parts.hostname not in allowed or parts.port not in (None, 443):
                raise TaskError('拒绝不可信请求地址或重定向')
            response = session.request(method, url, timeout=(10, 25),
                                       allow_redirects=False, **kwargs)
            if response.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                target = urljoin(url, response.headers.get('Location', ''))
                if kwargs.get('headers') and urlparse(target).hostname != parts.hostname:
                    raise TaskError('拒绝将业务扩展头转发到其他站点')
                if method.upper() != 'GET':
                    if response.status_code in (307, 308):
                        raise TaskError('拒绝重定向重发凭据或签到正文')
                    method = 'GET'
                    kwargs.pop('data', None)
                    kwargs.pop('json', None)
                url = target
                continue
            response.raise_for_status()
            return response
        raise TaskError('重定向次数超限')
    except RequestException:
        raise TaskError('网络请求失败、超时或 HTTP 状态异常') from None


def authenticate(session, account):
    if account.get('cookie'):
        # Cookie 仅送往今日校园，不送往认证服务。
        for item in account['cookie'].split(';'):
            key, sep, value = item.strip().partition('=')
            if sep and key:
                session.cookies.set(key, value, domain='gdou.cpdaily.com', path='/')
        log('凭据阶段：已载入本人会话，待业务接口验证')
        return
    try:
        # 不使用外部 Tesseract 程序，也不生成验证码本地文件。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
    except Exception:
        raise TaskError('验证码识别依赖不可用，请安装公共发行包 ddddocr') from None
    # 最多三次，每次重新获取登录表单和验证码，避免过期 lt 和无限重试。
    for attempt in range(1, 4):
        form = LoginForm()
        form.feed(request(session, 'GET', LOGIN).text)
        if not form.fields.get('lt'):
            raise TaskError('登录表单缺少 lt，接口契约可能变化')
        picture = request(session, 'GET', AUTH + '/authserver/captcha.html').content
        if not picture or len(picture) > 2 * 1024 * 1024:
            raise TaskError('验证码响应为空或过大')
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                captcha = re.sub(r'\W+', '', ocr.classification(picture)).strip()
        except Exception:
            raise TaskError('验证码识别失败') from None
        if not captcha:
            log('登录尝试 ' + str(attempt) + '/3：未识别出验证码')
            continue
        body = dict(form.fields)
        body.update(username=account['username'], password=account['password'],
                    captchaResponse=captcha, _eventId='submit', rmShown='1')
        body.setdefault('execution', 'e1s1')
        response = request(session, 'POST', LOGIN, data=body)
        if any(c.name == 'MOD_AUTH_CAS' and c.value and
               c.domain.lstrip('.') == 'gdou.cpdaily.com' for c in session.cookies):
            log('登录尝试 ' + str(attempt) + '/3：取得业务会话，待查询验证')
            session.cookies.set('clientType', 'cpdaily_student', domain='gdou.cpdaily.com')
            session.cookies.set('tenantId', TENANT, domain='gdou.cpdaily.com')
            return
        if '您提供的用户名或者密码有误' in response.text:
            raise TaskError('用户名或密码错误')
        log('登录尝试 ' + str(attempt) + '/3：尚未取得业务会话')
    raise TaskError('登录未成功，已达到重试上限')


def extension(account):
    try:
        from pyDes import des, CBC, PAD_PKCS5
    except ImportError:
        raise TaskError('缺少 pyDes 依赖') from None
    payload = {'systemName': 'android', 'systemVersion': '8.1.0', 'model': '16th',
               'deviceId': str(uuid.uuid4()), 'appVersion': '8.1.11',
               'lon': account['longitude'], 'lat': account['latitude'],
               'userId': account['username']}
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    # 上游协议固定 DES 密钥及 IV，不是账号凭据。
    encrypted = des('ST83=@XV', CBC, bytes(range(1, 9)), pad=None,
                    padmode=PAD_PKCS5).encrypt(data)
    return base64.b64encode(encrypted).decode('ascii')


def business(session, action, body, headers=None):
    response = request(session, 'POST', PREFIX + action, json=body, headers=headers or {})
    try:
        result = response.json()
    except ValueError:
        raise TaskError('业务接口未返回 JSON，可能会话失效') from None
    # 仅接受参考源码明确使用的 SUCCESS 标志，不将 HTTP 200 当作业务成功。
    if not isinstance(result, dict) or result.get('message') != 'SUCCESS':
        raise TaskError('业务接口未确认 SUCCESS，请核对会话、签到时间或接口契约')
    return result


def show_identity(data, account):
    # 只输出官方明确的非秘密身份字段，不输出响应对象或输入用户名。
    for key in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'publicUid', 'uid'):
        value = data.get(key)
        if not isinstance(value, (str, int)) or not str(value):
            continue
        text = str(value)
        secrets = [account.get(k) for k in ('password', 'cookie')]
        if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text) or any(s and s in text for s in secrets):
            continue
        log('官方账号身份 ' + key + ' ' + json.dumps(text, ensure_ascii=False))


def stage(number, name, call):
    start = time.monotonic()
    log(str(number) + '. ' + name + ' 开始')
    try:
        result = call()
    except Exception:
        log(str(number) + '. ' + name + ' ❌ 失败，耗时 %.2f 秒' % (time.monotonic() - start))
        raise
    log(str(number) + '. ' + name + ' ✅ 完成，耗时 %.2f 秒' % (time.monotonic() - start))
    return result


def run_account(account, dry, submit, stats):
    if dry:
        stage(1, '配置与执行计划预演', lambda: None)
        stats['success'] += 1
        log('DRY_RUN_OK：配置有效；跳过登录、验证码、查询及签到请求')
        stats['skipped'] += 2
        return
    try:
        import requests
    except ImportError:
        raise TaskError('缺少 requests 依赖') from None
    with requests.Session() as session:
        session.headers.update({'User-Agent': UA, 'Accept': 'application/json, text/plain, */*',
                                'Origin': BASE, 'X-Requested-With': 'XMLHttpRequest',
                                'Referer': BASE + '/wec-counselor-sign-apps/stu/mobile/index.html'})
        stage(1, '获取业务会话', lambda: authenticate(session, account))
        stats['success'] += 1
        result = stage(2, '查询当日待签到任务',
                       lambda: business(session, 'getStuSignInfosInOneDay', {}))
        data = result.get('datas')
        if not isinstance(data, dict) or not isinstance(data.get('unSignedTasks'), list):
            raise TaskError('查询响应缺少待签到任务列表')
        show_identity(data, account)
        show_identity(result, account)
        pending = data['unSignedTasks']
        stats['success'] += 1
        log('查询成功，待签到任务数 ' + str(len(pending)))
        if not pending:
            log('☑️ 当前没有待签到任务，不推断为已经签到')
            stats['alreadyComplete'] += 1
            return
        if not submit:
            log('⏭️ 只读模式，未提交签到；设置 CPDAILY_SUBMIT=1 并确认本人真实定位后提交')
            stats['skipped'] += 1
            return
        first = pending[0]
        if not isinstance(first, dict) or not first.get('signInstanceWid'):
            raise TaskError('首个待签到任务缺少标识')
        body = {key: account[key] for key in ('longitude', 'latitude', 'isMalposition',
                                             'abnormalReason', 'position')}
        body.update(signInstanceWid=first['signInstanceWid'], signPhotoUrl='')
        headers = {'tenantId': TENANT, 'CpdailyStandAlone': '0', 'extension': '1',
                   'Cpdaily-Extension': extension(account)}
        stage(3, '提交首个待签到任务', lambda: business(session, 'submitSign', body, headers))
        stats['success'] += 1
        log('签到成功：业务接口已确认 SUCCESS')


def notification(body, dry):
    mode = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    if mode in FALSE:
        return '已关闭'
    if mode not in TRUE and mode != 'auto':
        log('⚠️ 通知开关无效，保持业务退出码')
        return '配置无效'
    selection = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    script = Path(__file__).resolve()
    selectors = ['7f49669014a1d273', script.name, 'Fcpdaily-2.0.py', TITLE,
                 'checkin/' + script.name, 'scripts/' + script.name]
    try:
        selectors.append(script.relative_to(Path.cwd()).as_posix())
    except ValueError:
        pass
    if 'scripts' in script.parts:
        index = script.parts.index('scripts')
        selectors.append('/'.join(script.parts[index + 1:]))
    if selection is not None:
        patterns = [p for p in re.split(r'[,;\s]+', selection) if p]
        selected = any(fnmatch.fnmatch(s, p) for s in selectors for p in patterns)
    else:
        selected = False  # listed-only，未提供默认订阅清单。
    if mode == 'auto' and not selected:
        return '未列入通知选择'
    if dry:
        log('⏭️ dry-run 已生成脱敏通知摘要，禁止调用可能联网的通知模块')
        return '预演已生成，未投递'
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    paths.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    # 子进程隔离通知的异常、输出及退出行为，避免更改业务结果或泄漏日志。
    code = ('import sys,importlib.util; p=sys.argv[3]; '
            's=importlib.util.spec_from_file_location("notify",p) if p else None; '
            'm=importlib.util.module_from_spec(s) if s else __import__("notify"); '
            's.loader.exec_module(m) if s else None; m.send(sys.argv[1],sys.argv[2])')
    commands = [[sys.executable, '-c', code, TITLE, body, '']]
    for path in paths:
        if (path / 'notify.py').is_file():
            commands.append([sys.executable, '-c', code, TITLE, body, str(path / 'notify.py')])
        if (path / 'sendNotify.js').is_file():
            commands.append(['node', '-e',
                             'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',
                             str(path / 'sendNotify.js'), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return '已投递'
        except (OSError, subprocess.TimeoutExpired):
            continue
    log('⚠️ 通知模块不可用或投递失败，保持业务退出码')
    return '投递不可用'


def main():
    start = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log('开始时间 ' + datetime.datetime.now().isoformat(timespec='seconds'))
    dry = os.environ.get('CPDAILY_DRY_RUN', '').strip().lower() in TRUE
    rows = []
    successes = failures = 0
    totals = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    config_error = False
    try:
        dry = switch('CPDAILY_DRY_RUN')
        submit = switch('CPDAILY_SUBMIT')
        rows = accounts_from_env()
        if not rows:
            raise TaskError('账号列表为空')
        log('运行模式 ' + ('断网预演' if dry else ('提交签到' if submit else '只读查询')))
        log('账号数 ' + str(len(rows)))
        for index, row in enumerate(rows, 1):
            account_start = time.monotonic()
            stats = dict.fromkeys(totals, 0)
            log('---------- 账号 ' + str(index) + ' ----------')
            try:
                account = parse_account(row, submit)
                run_account(account, dry, submit, stats)
                successes += 1
            except TaskError as exc:
                failures += 1
                stats['failed'] += 1
                log('❌ ' + str(exc))
            except Exception:
                failures += 1
                stats['failed'] += 1
                log('❌ 运行异常，已隐藏异常正文及账号数据')
            for key in totals:
                totals[key] += stats[key]
            log('账号 %d 统计：总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒' %
                (index, sum(stats.values()), stats['success'], stats['alreadyComplete'],
                 stats['skipped'], stats['failed'], time.monotonic() - account_start))
    except TaskError as exc:
        config_error = True
        log('❌ 配置错误：' + str(exc))
        log('运行模式 ' + ('断网预演' if dry else '配置检查') + '，账号数 ' + str(len(rows)))
    status = ('configuration-error' if config_error else
              'partial-failure' if failures and successes else
              'failure' if failures else 'dry-run' if dry else 'success')
    exit_code = int(config_error or failures > 0)
    summary = {'status': status, 'accounts': len(rows), 'success': successes, 'failed': failures,
               'configurationError': config_error, 'steps': totals, 'exitCode': exit_code}
    body = ('账号总数 %d，成功 %d，失败 %d；状态 %s；配置错误 %s' %
            (len(rows), successes, failures, status, '是' if config_error else '否'))
    try:
        notice = notification(body, dry)
    except Exception:
        notice = '投递失败'
    log('========================================')
    log(body)
    log('子任务统计 ' + json.dumps(totals, ensure_ascii=False))
    log('总耗时 %.2f 秒；通知状态 %s' % (time.monotonic() - start, notice))
    log('完成时间 ' + datetime.datetime.now().isoformat(timespec='seconds') + '；最终状态 ' + status)
    summary['notification'] = notice
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
