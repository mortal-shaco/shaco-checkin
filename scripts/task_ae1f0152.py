#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 天翼云盘签到与抽奖
# cron: 45 10 * * *
# 来源：jemii/tyy checkin.py（提交 70ef55dee1fb8dfbfeace0c529dd4b8fb3844403）
# SPDX-License-Identifier: GPL-3.0
# 保留上游署名；本维护版本同样采用 GPL-3.0。
"""天翼云盘每日签到、签到抽奖、相册任务抽奖。

TY189_ACCOUNTS：每个非空行填写 登录账号|密码，仅在首个 | 分隔，密码中的 | 保留。
账号、密码来自本人天翼云盘账号；可在官方客户端确认密码登录可用。勿提交凭据。
TY189_TASKS：默认 sign,draw,photos；可用逗号选择任务，按默认顺序执行。
photos 仅尝试领取原脚本的相册任务抽奖，不开启备份、不上传文件。
TY189_DRY_RUN=1：完全离线检查配置并演练步骤（包括模拟通知），不代表业务成功。
实时运行依赖公开 PyPI 包 requests、rsa；不自动安装，不依赖其他仓库。
青龙通知支持 QINGLONG_NOTIFY、QINGLONG_NOTIFY_SCRIPTS、QINGLONG_NOTIFY_DIR。
上游无 cron 声明，本版本建议每天 09:00；可按个人需要调整青龙定时。
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
        _ql_notify_identities = ('ae1f0152f66bcc03', 'scripts/task_ae1f0152.py', 'task_ae1f0152.py', 'task_ae1f0152')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlsplit

TITLE = '天翼云盘签到与抽奖'
CATALOG_ID = 'ae1f0152f66bcc03'
TASKS = {'sign': '每日签到', 'draw': '签到抽奖', 'photos': '相册任务抽奖'}
HOSTS = {'cloud.189.cn', 'api.cloud.189.cn', 'm.cloud.189.cn', 'open.e.189.cn'}
UA = 'Mozilla/5.0 Ecloud/8.6.3'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    """只承载可公开展示的固定错误说明。"""


def log(message):
    print('[{}] {}'.format(datetime.now().strftime('%H:%M:%S'), message), flush=True)


def switch(name, default):
    value = os.getenv(name, default).strip().lower()
    if value in TRUE:
        return True
    if value in FALSE:
        return False
    raise TaskError(name + ' 必须填写 1 或 0')


def account_lines():
    return [line for line in os.getenv('TY189_ACCOUNTS', '').splitlines() if line.strip()]


def credentials(line):
    username, separator, password = line.partition('|')
    if not separator or not username.strip() or not password:
        raise TaskError('账号配置无效：每行需要 登录账号|密码')
    return username.strip(), password


def checked_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise TaskError('接口返回非受信 HTTPS 地址，已停止')
    return url


def numeric_bonus(value):
    if isinstance(value, bool):
        raise TaskError('签到空间奖励字段异常')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise TaskError('签到空间奖励字段缺失或异常') from None
    if not math.isfinite(number) or not 0 <= number <= 1000000000:
        raise TaskError('签到空间奖励字段异常')
    return format(number, 'g')


class Cloud:
    def __init__(self):
        try:
            import requests
            import rsa
        except ImportError:
            raise TaskError('缺少公开依赖 requests 或 rsa，请先在青龙依赖管理中安装') from None
        self.requests, self.rsa = requests, rsa
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA})

    def close(self):
        self.session.close()

    def request(self, method, url, **kwargs):
        # 手动校验每一跳；POST 不自动重试，也不跨跳重发密码。
        for _ in range(9):
            checked_url(url)
            try:
                response = self.session.request(method, url, timeout=(10, 20),
                                                allow_redirects=False, stream=True, **kwargs)
                with response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        if method != 'GET':
                            raise TaskError('登录提交发生重定向，已停止以保护凭据')
                        location = response.headers.get('Location')
                        if not location:
                            raise TaskError('接口重定向缺少目标地址')
                        url = checked_url(urljoin(url, location))
                        continue
                    if not 200 <= response.status_code < 300:
                        raise TaskError('接口 HTTP 请求失败（状态码 {}）'.format(response.status_code))
                    parts, size = [], 0
                    for chunk in response.iter_content(8192):
                        size += len(chunk)
                        if size > 1048576:
                            raise TaskError('接口响应超出大小限制')
                        parts.append(chunk)
                    return b''.join(parts).decode('utf-8', errors='replace')
            except self.requests.exceptions.RequestException:
                raise TaskError('接口连接失败或超时，未输出地址及响应') from None
        raise TaskError('接口重定向次数超限')

    def data(self, method, url, **kwargs):
        try:
            result = json.loads(self.request(method, url, **kwargs))
        except (ValueError, TypeError):
            raise TaskError('接口未返回有效 JSON') from None
        if not isinstance(result, dict):
            raise TaskError('接口返回结构异常')
        return result

    def encrypt(self, key, text):
        pem = '-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----'.format(key)
        try:
            pub = self.rsa.PublicKey.load_pkcs1_openssl_pem(pem.encode())
            return self.rsa.encrypt(text.encode(), pub).hex()
        except Exception:
            raise TaskError('登录公钥无效或凭据长度不适用') from None

    def login(self, username, password):
        page = self.request('GET', 'https://cloud.189.cn/udb/udb_login.jsp?pageId=1&redirectURL=/main.action')
        patterns = {
            'captchaToken': r"captchaToken['\"]\s+value=['\"]([^'\"]+)['\"]",
            'lt': r'\blt\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            'returnUrl': r'\breturnUrl\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            'paramId': r'\bparamId\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            'key': r'j_rsaKey[\'\"]\s+value=[\'\"]([^\'\"]+)[\'\"]',
        }
        fields = {}
        for name, pattern in patterns.items():
            match = re.search(pattern, page)
            if not match:
                raise TaskError('登录页契约不匹配，缺少字段 ' + name)
            fields[name] = match.group(1)
        form = {'appKey': 'cloud', 'accountType': '01',
                'userName': '{RSA}' + self.encrypt(fields['key'], username),
                'password': '{RSA}' + self.encrypt(fields['key'], password),
                'validateCode': '', 'captchaToken': fields['captchaToken'],
                'returnUrl': fields['returnUrl'], 'mailSuffix': '@189.cn', 'paramId': fields['paramId']}
        result = self.data('POST', 'https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do',
                           data=form, headers={'lt': fields['lt'], 'Referer': 'https://open.e.189.cn/'})
        if type(result.get('result')) is not int or result['result'] != 0:
            raise TaskError('登录未成功，请在官方客户端检查密码、验证码或账号风控')
        target = result.get('toUrl')
        if not isinstance(target, str) or not target:
            raise TaskError('登录响应缺少认证跳转地址')
        self.request('GET', checked_url(target))
        # 身份只取官方明确的公开字段；手机号、凭据和设备值永不展示。
        for name in ('nickname', 'nickName', 'displayName', 'username', 'publicUid'):
            value = result.get(name)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                if (text and not (password and password in text)
                        and not re.search(r'(?<!\d)1\d{10}(?!\d)', text)):
                    log('官方账号身份：' + text.replace('\n', ' ').replace('\r', ' '))
        return 'success', '登录及认证跳转完成'

    @staticmethod
    def check_codes(data):
        for field in ('errorCode', 'res_code', 'result'):
            if field in data and (isinstance(data[field], bool) or data[field] not in (0, '0')):
                raise TaskError('业务接口返回失败状态（已隐藏原始响应）')

    def action(self, name):
        headers = {'Referer': 'https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp'}
        if name == 'sign':
            data = self.data('GET', 'https://api.cloud.189.cn/mkt/userSign.action?rand={}'
                             '&clientType=TELEANDROID&version=8.6.3&model=SM-G930K'.format(int(time.time()*1000)),
                             headers=headers)
            self.check_codes(data)
            signed = data.get('isSign')
            if type(signed) is bool:
                already = signed
            elif signed in ('true', 'false'):
                already = signed == 'true'
            else:
                raise TaskError('签到结果缺少明确的 isSign 标志')
            bonus = numeric_bonus(data.get('netdiskBonus'))
            return ('alreadyComplete' if already else 'success',
                    ('已签到' if already else '签到成功') + '，空间奖励 ' + bonus + ' MB')
        task = 'TASK_SIGNIN' if name == 'draw' else 'TASK_SIGNIN_PHOTOS'
        data = self.data('GET', 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId='
                         + task + '&activityId=ACT_SIGNIN', headers=headers)
        self.check_codes(data)
        if not isinstance(data.get('description'), str) or not data['description'].strip():
            raise TaskError('抽奖响应缺少中奖结果，不能确认成功')
        return 'success', '抽奖成功，已收到奖励说明（不输出原始文本）'


def notify(summary, dry):
    setting = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if setting in FALSE:
        return '已关闭'
    if setting not in TRUE | {'auto'}:
        return '配置无效，未发送'
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is not None:
        choices = re.split(r'[,;\s]+', selectors.strip())
        identities = [CATALOG_ID, Path(__file__).name, 'candidate.py', str(Path(__file__))]
        for root in ('/ql/data/scripts/', '/ql/scripts/'):
            if str(Path(__file__)).startswith(root):
                identities.append(str(Path(__file__))[len(root):])
        if not any(fnmatch.fnmatchcase(item, pattern) for item in identities for pattern in choices if pattern):
            return '未被通知列表选中'
    # 本维护任务默认列入通知；显式列表会替换默认值。
    if dry:
        return '离线预演已模拟通知，未加载通知器或联网'
    body = ('账号总数：{accounts}；成功：{success}；失败：{failure}；状态：{status}。'
            '子任务成功：{stepsSuccess}；已完成：{stepsAlready}；跳过：{stepsSkipped}；失败：{stepsFailure}。').format(**summary)
    paths = []
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.append(spec.origin)
    except (ImportError, ValueError, AttributeError):
        pass
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(str(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py'))
    paths += ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
    helper = ('import importlib.util,json,sys; '
              'sys.path.insert(0,str(__import__("pathlib").Path(sys.argv[1]).parent)); '
              's=importlib.util.spec_from_file_location("notify",sys.argv[1]); '
              'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
              'p=json.load(sys.stdin); m.send(p["title"],p["body"])')
    for path in dict.fromkeys(paths):
        if not Path(path).is_file():
            continue
        try:
            subprocess.run([sys.executable, '-c', helper, path],
                           input=json.dumps({'title': TITLE, 'body': body}), text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=True)
            return '已发送'
        except (OSError, subprocess.SubprocessError):
            continue
    return '通知不可用或发送失败，保留业务退出码'


def main():
    started = time.monotonic()
    lines = account_lines()
    dry, config_error = False, None
    tasks = list(TASKS)
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + datetime.now().isoformat(timespec='seconds'))
    try:
        dry = switch('TY189_DRY_RUN', '0')
        requested = os.getenv('TY189_TASKS', 'sign,draw,photos').split(',')
        requested = [value.strip() for value in requested]
        if not requested or any(value not in TASKS for value in requested):
            raise TaskError('TY189_TASKS 仅接受 sign,draw,photos，不能留空')
        tasks = [name for name in TASKS if name in requested]
        if not lines:
            raise TaskError('未配置必填变量 TY189_ACCOUNTS')
    except TaskError as error:
        config_error = str(error)
    log('运行模式：' + ('离线预演' if dry else '实际执行') + '；账号数：' + str(len(lines)))
    summary = {'accounts': len(lines), 'success': 0, 'failure': 0,
               'stepsSuccess': 0, 'stepsAlready': 0, 'stepsSkipped': 0, 'stepsFailure': 0}
    if config_error:
        summary['failure'] = len(lines)
        log('❌ 配置错误：' + config_error)
    else:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            counts = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
            client, login_ok = None, False
            stages = ['login'] + tasks
            try:
                user, password = credentials(line)
            except TaskError:
                user, password = None, None
            for number, name in enumerate(stages, 1):
                label = '密码登录' if name == 'login' else TASKS[name]
                step_start = time.monotonic()
                log('账号 {} 阶段 {}/{}：{}'.format(index, number, len(stages), label))
                try:
                    if name == 'login':
                        if user is None:
                            raise TaskError('账号配置无效：每行需要 登录账号|密码')
                        if dry:
                            state, message = 'skipped', 'DRY_RUN 配置有效；模拟登录，不发起请求'
                        else:
                            client = Cloud()
                            state, message = client.login(user, password)
                        login_ok = True
                    elif not login_ok:
                        state, message = 'skipped', '登录失败，跳过依赖任务'
                    elif dry:
                        state, message = 'skipped', 'DRY_RUN 已演练任务；不发起请求、不修改账号'
                    else:
                        state, message = client.action(name)
                except TaskError as error:
                    state, message = 'failure', str(error)
                except Exception:
                    state, message = 'failure', '执行异常，已隐藏内部细节及凭据'
                counts[state] += 1
                icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️', 'failure': '❌'}[state]
                log('{} 账号 {} {}：{}；耗时 {:.2f} 秒'.format(icon, index, label, message, time.monotonic()-step_start))
            if client is not None:
                try:
                    client.close()
                except Exception:
                    log('⚠️ 会话资源关闭异常，保留已核验的业务结果')
            failed = counts['failure'] > 0
            summary['failure' if failed else 'success'] += 1
            for source, target in [('success', 'stepsSuccess'), ('alreadyComplete', 'stepsAlready'),
                                   ('skipped', 'stepsSkipped'), ('failure', 'stepsFailure')]:
                summary[target] += counts[source]
            log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f} 秒'.format(
                index, len(stages), counts['success'], counts['alreadyComplete'], counts['skipped'], counts['failure'], time.monotonic()-begin))
    code = 1 if config_error or summary['failure'] else 0
    summary['status'] = ('configuration-error' if config_error else
                         'partial-failure' if summary['failure'] and summary['success'] else
                         'failure' if code else 'dry-run' if dry else 'success')
    summary['mode'] = 'dry-run' if dry else 'live'
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        summary['notification'] = '通知异常，保留业务退出码'
    summary['durationSeconds'] = round(time.monotonic()-started, 2)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('任务统计：账号总数 {accounts}，成功 {success}，失败 {failure}；子任务成功 {stepsSuccess}，已完成 {stepsAlready}，跳过 {stepsSkipped}，失败 {stepsFailure}'.format(**summary))
    log('通知状态：' + summary['notification'])
    log('完成时间：{}；总耗时 {} 秒；最终状态：{}'.format(summary['finishedAt'], summary['durationSeconds'], summary['status']))
    if not code:
        log('DRY_RUN_OK' if dry else 'TY189_TASK_OK')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
