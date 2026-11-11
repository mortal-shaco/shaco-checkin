#!/usr/bin/env python3
# name: 天翼云盘签到与抽奖
# cron: 43 10 * * *
# SPDX-License-Identifier: MIT
# 来源：lijialei888/cloundqiandao，checkin.py（MIT）
# 上游提交：4d1990494ef90cbbbf878a8f5fa232bf11a89f09
# 上游输入未附版权声明；保留来源归属，维护版本继续采用 MIT 许可。
"""天翼云盘：CLOUD189_ACCOUNTS 每个非空行填写 账号|密码，仅分割首个 |。
账号密码与天翼云盘官方客户端一致；验证码/风控须在官方客户端处理，不绕过。
兼容 --username/--password（命令行凭据可能被系统进程列表读取，推荐环境变量）。
CLOUD189_DRY_RUN=1 完全断网预演；无需安装 rsa。正式运行依赖公开 PyPI 包 rsa。
每日 08:15 运行签到与两次免费活动抽奖；上游未声明 cron，此处为维护版建议。
不上传相册、不启用备份、不购买抽奖次数。服务规则变化时失败闭合，不重试写请求。
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
        _ql_notify_identities = ('9973f7e502796463', 'scripts/task_9973f7e5.py', 'task_9973f7e5.py', 'task_9973f7e5')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import datetime as dt
import fnmatch
import http.cookiejar
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

TITLE = '天翼云盘签到与抽奖'
CATALOG = '9973f7e502796463'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = []
UA = 'Mozilla/5.0 (Linux; Android 5.1.1) AppleWebKit/537.36 Chrome/74.0 Mobile Safari/537.36 Ecloud/8.6.3'
LOGIN = 'https://cloud.189.cn/api/portal/loginUrl.action?redirectURL=https://cloud.189.cn/web/redirect.html?returnURL=/main.action'
SUBMIT = 'https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do'


class TaskError(Exception):
    pass


def safe_text(value):
    text = str(value)
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', text)
    return text[:160]


def log(message):
    print(f'[{dt.datetime.now().strftime("%H:%M:%S")}] {message}', flush=True)


def official_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host == '189.cn' or host.endswith('.189.cn'))):
        raise TaskError('拒绝非天翼官方 HTTPS 地址')
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_url(newurl)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).hostname != urllib.parse.urlsplit(newurl).hostname:
            # lt 只在登录站点使用，禁止转发给其他站点。
            redirected.remove_header('Lt')
        return redirected


class Cloud189:
    def __init__(self, username, password):
        self.username, self.password = username, password
        jar = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), OfficialRedirect())

    def request(self, url, data=None, headers=None, as_json=False):
        official_url(url)
        request_headers = {'User-Agent': UA}
        request_headers.update(headers or {})
        body = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, headers=request_headers)
        try:
            with self.client.open(req, timeout=15) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常')
                payload = response.read(1048577)
                if len(payload) > 1048576:
                    raise TaskError('响应超过安全大小限制')
                result = payload.decode('utf-8')
        except TaskError:
            raise
        except Exception:
            # URL、重定向票据、登录凭据和服务器原文均不进入日志。
            raise TaskError('网络、超时、编码或重定向失败') from None
        if not as_json:
            return result
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            raise TaskError('响应不是有效 JSON') from None
        if not isinstance(result, dict):
            raise TaskError('响应结构不符合预期')
        return result

    @staticmethod
    def rsa_encode(key, value):
        try:
            import rsa
            pem = '-----BEGIN PUBLIC KEY-----\n' + key + '\n-----END PUBLIC KEY-----'
            public_key = rsa.PublicKey.load_pkcs1_openssl_pem(pem.encode())
            # 与上游 base64→hex 转换等价；保留 PKCS#1 v1.5 协议。
            return rsa.encrypt(value.encode(), public_key).hex()
        except ImportError:
            raise TaskError('缺少公开依赖 rsa，请在青龙依赖管理中安装 Python 包 rsa') from None
        except Exception:
            raise TaskError('公钥或 RSA 加密失败') from None

    def login(self):
        page = self.request(LOGIN)
        expressions = {
            'captchaToken': r'''captchaToken['"]?\s+value=['"]([^'"]+)['"]''',
            'lt': r'''\blt\s*=\s*['"]([^'"]+)['"]''',
            'returnUrl': r'''\breturnUrl\s*=\s*['"]([^'"]+)['"]''',
            'paramId': r'''\bparamId\s*=\s*['"]([^'"]+)['"]''',
            'key': r'''j_rsaKey['"]\s+value=['"]([^'"]+)['"]''',
        }
        fields = {}
        for name, expression in expressions.items():
            match = re.search(expression, page)
            if not match:
                raise TaskError('登录页面字段缺失；需核对官方接口，未继续提交')
            fields[name] = match.group(1)
            SECRETS.append(fields[name])
        data = {'appKey': 'cloud', 'accountType': '01',
                'userName': '{RSA}' + self.rsa_encode(fields['key'], self.username),
                'password': '{RSA}' + self.rsa_encode(fields['key'], self.password),
                'validateCode': '', 'captchaToken': fields['captchaToken'],
                'returnUrl': fields['returnUrl'], 'mailSuffix': '@189.cn',
                'paramId': fields['paramId']}
        result = self.request(SUBMIT, data, {'lt': fields['lt'], 'Referer': 'https://open.e.189.cn/'}, True)
        if str(result.get('result')) != '0' or not isinstance(result.get('toUrl'), str) or not result['toUrl']:
            raise TaskError('登录未获明确成功；请在官方客户端检查密码、验证码或风控')
        self.request(official_url(result['toUrl']))
        show_identity(result)
        return 'success', '登录认证通过'

    def sign(self):
        result = self.request('https://api.cloud.189.cn/mkt/userSign.action?' + urllib.parse.urlencode({
            'rand': round(time.time() * 1000), 'clientType': 'TELEANDROID',
            'version': '8.6.3', 'model': 'SM-G930K'}), headers=activity_headers(), as_json=True)
        check_error(result)
        flag, bonus = result.get('isSign'), result.get('netdiskBonus')
        if not (type(flag) is bool or type(flag) is str and flag in ('true', 'false')):
            raise TaskError('签到响应缺少明确状态')
        if type(bonus) not in (int, float, str) or not re.fullmatch(r'\d+(?:\.\d+)?', str(bonus)):
            raise TaskError('签到响应缺少有效空间奖励')
        show_identity(result)
        return ('alreadyComplete' if flag in (True, 'true') else 'success', f'签到通过，空间奖励 {bonus} M')

    def draw(self, task_id):
        result = self.request('https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?' +
                              urllib.parse.urlencode({'taskId': task_id, 'activityId': 'ACT_SIGNIN'}),
                              headers=activity_headers(), as_json=True)
        check_error(result)
        prize = result.get('prizeName')
        if not isinstance(prize, str) or not prize.strip():
            raise TaskError('抽奖未返回明确奖品，未判为成功')
        show_identity(result)
        return 'success', '抽奖成功，奖品：' + safe_text(prize)


def activity_headers():
    return {'Referer': 'https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1'}


def check_error(result):
    for field in ('errorCode', 'res_code', 'result', 'code'):
        if field in result and str(result[field]) not in ('0', ''):
            raise TaskError('业务接口返回错误；未输出原文或自动重试')


def show_identity(result):
    for key in ('nickname', 'nickName', 'displayName', 'userName', 'username', 'publicUid'):
        identity = result.get(key)
        if isinstance(identity, (str, int)) and str(identity):
            value = str(identity)
            # 手机号码、登录账号和凭据不作为公开身份打印。
            if value in SECRETS or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                continue
            log('官方账号身份：' + safe_text(value))


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令行配置错误；使用 --username 与 --password 配套传入，或配置 CLOUD189_ACCOUNTS')


def accounts_from_config():
    parser = SafeParser(description=TITLE)
    parser.add_argument('--username')
    parser.add_argument('--password')
    args = parser.parse_args()
    raw = os.environ.get('CLOUD189_ACCOUNTS', '')
    if args.username is not None or args.password is not None:
        if not args.username or not args.password or raw.strip():
            raise TaskError('命令行账号密码必须成对填写，且不能与 CLOUD189_ACCOUNTS 同时使用')
        accounts = [(args.username, args.password)]
    else:
        accounts = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            username, delimiter, password = line.partition('|')
            accounts.append((username.strip(), password) if delimiter and username.strip() and password else None)
        if not accounts:
            raise TaskError('缺少 CLOUD189_ACCOUNTS；每个非空行使用 账号|密码')
        # 单行错误仍交由该账号处理，其他合法账号继续。
    for account in accounts:
        if account:
            SECRETS.extend(account)
    return accounts


def notification_enabled():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return False
    if 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        identities = (CATALOG, Path(__file__).name, Path(__file__).as_posix(), 'output/candidate.py',
                      'scripts/task_9973f7e5.py', 'task_9973f7e5.py')
        return any(fnmatch.fnmatchcase(identity, selector) for selector in selectors if selector for identity in identities)
    return switch in TRUE  # listed-only：未列出时 auto 默认不发送。


def send_python_notification(payload):
    """在隔离子进程内集成青龙 notify.py，导入和发送异常由父进程处理。"""
    sys.path[:0] = payload['dirs']
    from notify import send
    send(payload['title'], payload['body'])


def notify_summary(body, dry):
    if not notification_enabled():
        return '未启用（全局开关或列表选择）'
    if dry:
        return '断网预演：已生成通知摘要，未调用外部发送器'
    directories = [str(Path(__file__).resolve().parent)]
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        directories.append(os.environ['QINGLONG_NOTIFY_DIR'])
    directories.extend(['/ql/data/scripts', '/ql/scripts'])
    # 子进程隔离通知输出与失败，避免发送器打印凭据、阻塞或改变业务退出码。
    code = ('import json, runpy, sys; p=json.load(sys.stdin); '
            'runpy.run_path(p["script"])["send_python_notification"](p)')
    try:
        result = subprocess.run([sys.executable, '-c', code],
                                input=json.dumps({'script': str(Path(__file__).resolve()),
                                                  'dirs': directories, 'title': TITLE, 'body': body}),
                                text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if result.returncode == 0:
            return '已发送'
    except Exception:
        pass
    for directory in directories:
        js_path = Path(directory) / 'sendNotify.js'
        if not js_path.is_file():
            continue
        code = ('const fs=require("fs");const p=JSON.parse(fs.readFileSync(0,"utf8"));'
                'Promise.resolve(require(p.path).sendNotify(p.title,p.body)).catch(()=>process.exit(1));')
        try:
            result = subprocess.run(['node', '-e', code], text=True,
                                    input=json.dumps({'path': str(js_path.resolve()), 'title': TITLE, 'body': body}),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    return '发送器不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    dry = os.environ.get('CLOUD189_DRY_RUN', '').strip().lower() in TRUE
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + dt.datetime.now().isoformat(timespec='seconds'))
    log('运行模式：' + ('断网预演' if dry else '正式运行'))
    results, config_error = [], False
    try:
        accounts = accounts_from_config()
    except TaskError as error:
        accounts, config_error = [], True
        log('❌ 配置错误：' + str(error))
    log(f'账号数量：{len(accounts)}')
    totals = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    for index, account in enumerate(accounts, 1):
        account_start = time.monotonic()
        counts = {key: 0 for key in totals}
        log(f'账号 {index} 开始')
        client = Cloud189(*account) if account and not dry else None
        authenticated = False
        actions = [('登录', 'login'), ('每日签到', 'sign'),
                   ('签到活动抽奖', 'TASK_SIGNIN'), ('相册活动抽奖', 'TASK_SIGNIN_PHOTOS')]
        for stage, (label, action) in enumerate(actions, 1):
            step_start = time.monotonic()
            log(f'账号 {index} 阶段 {stage}/4：{label}')
            try:
                if not account:
                    raise TaskError('账号行格式错误；应为 账号|密码')
                if dry:
                    status, detail = 'skipped', '参数通过；预演跳过 HTTP、加密与实际副作用'
                elif stage > 1 and not authenticated:
                    status, detail = 'skipped', '登录未成功，跳过此阶段'
                else:
                    status, detail = (client.login() if action == 'login' else
                                      client.sign() if action == 'sign' else client.draw(action))
                    if stage == 1:
                        authenticated = True
            except TaskError as error:
                status, detail = 'failure', str(error)
            except Exception:
                status, detail = 'failure', '执行异常，未输出敏感异常原文'
            counts[status] += 1
            icon = {'success': '✅', 'alreadyComplete': '☑️', 'skipped': '⏭️', 'failure': '❌'}[status]
            log(f'{icon} 账号 {index} 阶段 {stage}：{detail}；耗时 {time.monotonic() - step_start:.2f} 秒')
        for key in totals:
            totals[key] += counts[key]
        result = {'account': index, 'total': 4, **counts, 'elapsedSeconds': round(time.monotonic() - account_start, 2)}
        results.append(result)
        log(f'账号 {index} 统计：总任务 4，成功 {counts["success"]}，已完成 {counts["alreadyComplete"]}，'
            f'跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {result["elapsedSeconds"]} 秒')
    failed = sum(result['failure'] > 0 for result in results)
    succeeded = len(results) - failed
    exit_code = int(config_error or failed > 0)
    status = ('configuration-error' if config_error else 'partial-failure' if failed and succeeded else
              'failure' if failed else 'dry-run' if dry else 'success')
    body = f'状态：{status}；账号总数 {len(results)}，通过 {succeeded}，失败 {failed}；子任务失败 {totals["failure"]}'
    notification = notify_summary(body, dry)
    log('----------------------------------------')
    log(body)
    log(f'子任务统计：总计 {sum(totals.values())}，成功 {totals["success"]}，已完成 {totals["alreadyComplete"]}，'
        f'跳过 {totals["skipped"]}，失败 {totals["failure"]}')
    log('通知状态：' + notification)
    finished = dt.datetime.now().isoformat(timespec='seconds')
    elapsed = round(time.monotonic() - started, 2)
    log(f'完成时间：{finished}；总耗时 {elapsed} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accountCount': len(results), 'succeededAccounts': succeeded, 'failedAccounts': failed,
          'configurationError': config_error, 'tasks': totals, 'accounts': results,
          'notification': notification, 'elapsedSeconds': elapsed, 'finishedAt': finished,
          'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
