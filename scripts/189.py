#!/usr/bin/env python3
# name: 天翼云盘每日签到及抽奖
# cron: 44 10 * * *
# 来源: jing207/189Checkin, checkin.py (MIT)
# 兼容参考: task catalog a239bc381f7989b5 (MIT)，增加验证码失败提示。
# 上游文件未含额外版权声明；本文件保留来源并沿用 MIT 许可。
# MIT License
# Copyright (c) jing207/189Checkin contributors
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
"""天翼云盘账号任务。

189_ACCOUNTS: 每个非空行是 账号|密码，仅在第一个 | 分割，密码可含 |。
请在天翼云盘官网或官方客户端注册账号并设置登录密码，无需抓包。
兼容 --username / --password 单账号参数（优先于环境变量，但不推荐暴露于进程参数）。
189_DRY_RUN=1 完全断网预演，包含通知模拟，不会校验真实凭据。
189_DRAW_SIGNIN / 189_DRAW_PHOTOS=0 可关闭对应抽奖，默认均开启。
推荐每日 08:15 运行一次；原始来源没有 cron，此为维护版建议。
依赖: 公共 PyPI requests、rsa；预演无需安装它们。不会上传照片或开启相册备份。
验证码拦截须自行在官方客户端处理，不自动改密或绕过验证。
通知遵循 QINGLONG_NOTIFY 和 QINGLONG_NOTIFY_SCRIPTS 选择；未配置选择时不默认推送。
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
        _ql_notify_identities = ('e9e87f29cf49ea77', 'scripts/189.py', '189.py', '189')
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
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit

TITLE = '天翼云盘每日签到及抽奖'
CATALOG = 'e9e87f29cf49ea77'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
HOSTS = {'cloud.189.cn', 'open.e.189.cn', 'api.cloud.189.cn', 'm.cloud.189.cn'}
LOGIN = ('https://cloud.189.cn/api/portal/loginUrl.action?'
         'redirectURL=https://cloud.189.cn/web/redirect.html?returnURL=/main.action')
SUBMIT = 'https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do'
SIGN = 'https://api.cloud.189.cn/mkt/userSign.action'
DRAW = 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action'
UA = 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K) AppleWebKit/537.36 Mobile Safari/537.36 Ecloud/8.6.3'


class TaskError(Exception):
    """只允许使用固定的脱敏错误描述。"""


def log(message):
    print(f'[{dt.datetime.now():%H:%M:%S}] {message}', flush=True)


def switch(name, default):
    value = os.environ.get(name, str(int(default))).strip().lower()
    if value not in TRUE | FALSE:
        raise TaskError(f'{name} 必须为 1/0、true/false、yes/no 或 on/off')
    return value in TRUE


def trusted_url(url):
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == 'https' and parsed.hostname in HOSTS
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password)
    except ValueError:
        valid = False
    if not valid:
        raise TaskError('接口返回了不受信任的跳转地址，已停止')
    return url


class Client:
    def __init__(self, username, password):
        try:
            import requests
            import rsa
        except ImportError:
            raise TaskError('缺少公共依赖，请在青龙 Python 依赖中安装 requests 和 rsa') from None
        self.rsa = rsa
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': UA})
        self.username, self.password = username, password
        self.secrets = [username, password]

    def close(self):
        self.session.close()

    def request(self, method, url, **kwargs):
        # 手动处理跳转，防止携带登录数据或会话头跳转到非官方域名。
        trusted_url(url)
        for _ in range(8):
            try:
                response = self.session.request(method, url, timeout=(10, 25),
                                                allow_redirects=False, **kwargs)
            except Exception:
                raise TaskError('网络请求失败或超时（未输出敏感异常）') from None
            if response.is_redirect:
                target = trusted_url(urljoin(url, response.headers.get('Location', '')))
                if method != 'GET':
                    raise TaskError('登录提交出现非预期跳转，已停止')
                url = target
                continue
            if not 200 <= response.status_code < 300:
                raise TaskError('接口 HTTP 状态异常')
            if len(response.content) > 2 * 1024 * 1024:
                raise TaskError('接口响应超过大小限制')
            return response
        raise TaskError('接口跳转次数超限')

    def json(self, method, url, **kwargs):
        try:
            data = self.request(method, url, **kwargs).json()
        except TaskError:
            raise
        except Exception:
            raise TaskError('接口未返回有效 JSON') from None
        if not isinstance(data, dict):
            raise TaskError('接口响应结构发生变化')
        return data

    def identity(self, data):
        # 不将登录账号或 phone 等字段当成公开身份。
        for key in ('nickname', 'nickName', 'displayName', 'username', 'userName', 'publicUid'):
            value = data.get(key)
            if not isinstance(value, (str, int)):
                continue
            text = str(value)
            if (not text or any(secret and secret in text for secret in self.secrets)
                    or (key != 'publicUid' and re.search(r'(?<!\d)\+?\d[\d -]{6,}\d(?!\d)', text))
                    or any(c in text for c in '\r\n\x1b')):
                continue
            log(f'官方账号身份：{text}')

    def login(self):
        page = self.request('GET', LOGIN).text
        patterns = {
            'captchaToken': r"captchaToken' value='(.+?)'",
            'lt': r'lt = "(.+?)"',
            'returnUrl': r"returnUrl = '(.+?)'",
            'paramId': r'paramId = "(.+?)"',
            'key': r'j_rsaKey" value="(\S+)"',
        }
        fields = {}
        for name, pattern in patterns.items():
            match = re.search(pattern, page)
            if not match:
                raise TaskError('登录页缺少必要字段，可能需要验证码或接口已变化')
            fields[name] = match.group(1)
        self.secrets.extend(fields.values())
        try:
            public_key = self.rsa.PublicKey.load_pkcs1_openssl_pem(
                ('-----BEGIN PUBLIC KEY-----\n' + fields['key'] + '\n-----END PUBLIC KEY-----').encode())
            def encrypt(value):
                return '{RSA}' + self.rsa.encrypt(value.encode(), public_key).hex()
            data = {'appKey': 'cloud', 'accountType': '01', 'userName': encrypt(self.username),
                    'password': encrypt(self.password), 'validateCode': '',
                    'captchaToken': fields['captchaToken'], 'returnUrl': fields['returnUrl'],
                    'mailSuffix': '@189.cn', 'paramId': fields['paramId']}
        except Exception:
            raise TaskError('登录加密失败，检查依赖和官方登录页') from None
        self.session.headers.update({'lt': fields['lt']})
        result = self.json('POST', SUBMIT, data=data, headers={'Referer': 'https://open.e.189.cn/'})
        if str(result.get('result')) != '0':
            if '验证码' in str(result.get('msg', '')):
                raise TaskError('登录需要验证码，请先在官方客户端完成验证再重试')
            raise TaskError('登录业务失败，请检查账号密码及官方客户端登录状态')
        redirect = result.get('toUrl')
        if not isinstance(redirect, str) or not redirect:
            raise TaskError('登录未返回会话跳转地址')
        self.request('GET', trusted_url(redirect))
        self.identity(result)
        return 'success', '登录业务校验通过，已建立独立会话'

    def sign(self):
        data = self.json('GET', SIGN, params={'rand': str(round(time.time() * 1000)),
                         'clientType': 'TELEANDROID', 'version': '8.6.3', 'model': 'SM-G930K'},
                         headers={'Referer': 'https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1'})
        flag, bonus = data.get('isSign'), data.get('netdiskBonus')
        if ('errorCode' in data or str(flag).lower() not in {'true', 'false'}
                or isinstance(bonus, bool) or not re.fullmatch(r'\d+(?:\.\d+)?', str(bonus))):
            raise TaskError('签到未取得明确业务成功字段')
        self.identity(data)
        if str(flag).lower() == 'true':
            return 'already', f'今日已经签到，空间奖励 {bonus}M'
        return 'success', f'签到成功，获得 {bonus}M 空间'

    def draw(self, task):
        data = self.json('GET', DRAW, params={'taskId': task, 'activityId': 'ACT_SIGNIN'},
                         headers={'Referer': 'https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1'})
        # 来源只提供 prizeName 成功契约；未知错误不假定为“已抽奖”。
        if 'errorCode' in data or not isinstance(data.get('prizeName'), str) or not data['prizeName'].strip():
            raise TaskError('抽奖未取得明确奖品结果，可能已抽取、资格不足或接口变化')
        self.identity(data)
        return 'success', '抽奖成功，已确认奖品结果'


def notify(summary, dry):
    value = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if value in FALSE:
        return '已关闭'
    if value not in TRUE | {'auto'}:
        log('⚠️ 通知开关无效，不影响业务退出码')
        return '配置无效'
    selected = value in TRUE
    if 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        patterns = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        names = [CATALOG, Path(__file__).name, 'scripts/' + Path(__file__).name]
        # 允许匹配安装后的 scripts 相对路径。
        parts = Path(__file__).parts
        if 'scripts' in parts:
            names.append('/'.join(parts[parts.index('scripts') + 1:]))
        selected = any(p and fnmatch.fnmatch(n, p) for p in patterns for n in names)
    if not selected:
        return '未选中推送'
    if dry:
        log('通知预演：已生成脱敏摘要；断网模式不调用通知传输')
        return '断网模拟'
    body = (f"模式：{summary['mode']}；状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功数：{summary['succeeded']}；失败数：{summary['failed']}；"
            f"配置错误：{summary['configurationErrors']}")
    dirs = [Path(p) for p in [os.environ.get('QINGLONG_NOTIFY_DIR', ''),
                             '/ql/data/scripts', '/ql/scripts'] if p]
    # 子进程隔离通知输出和超时；只传递固定标题与脱敏计数。
    python_code = ('import importlib.util,sys; '
                   's=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); '
                   'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                   'm.send(sys.argv[2],sys.argv[3])')
    commands = []
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            commands.append([sys.executable, '-c', python_code, spec.origin, TITLE, body])
    except Exception:
        pass
    for directory in dirs:
        if (directory / 'notify.py').is_file():
            commands.append([sys.executable, '-c', python_code, str(directory / 'notify.py'), TITLE, body])
        if (directory / 'sendNotify.js').is_file():
            commands.append(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',
                             str(directory / 'sendNotify.js'), TITLE, body])
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    log('⚠️ 通知模块不可用或发送失败，保留业务退出码')
    return '不可用或发送失败'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令行参数无效，请配套使用 --username 和 --password')


def main():
    started = time.monotonic()
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{dt.datetime.now().isoformat(timespec="seconds")}')
    dry = os.environ.get('189_DRY_RUN', '').strip().lower() in TRUE
    records, config_errors = [], 0
    accounts = []
    try:
        dry = switch('189_DRY_RUN', False)
        parser = Parser(description=__doc__)
        parser.add_argument('--username')
        parser.add_argument('--password')
        args = parser.parse_args()
        if args.username is not None or args.password is not None:
            if not args.username or not args.password:
                raise TaskError('命令行账号密码必须同时非空')
            accounts = [(args.username, args.password)]
        else:
            lines = [line for line in os.environ.get('189_ACCOUNTS', '').splitlines() if line.strip()]
            for line in lines:
                user, sep, password = line.partition('|')
                accounts.append((user, password) if sep and user and password else None)
            if not accounts:
                raise TaskError('缺少 189_ACCOUNTS：每个非空行填写 账号|密码')
        sign_draw, photos_draw = switch('189_DRAW_SIGNIN', True), switch('189_DRAW_PHOTOS', True)
    except TaskError as exc:
        config_errors += 1
        log(f'❌ 配置错误：{exc}')
        sign_draw = photos_draw = False
    log(f'运行模式：{"断网预演" if dry else "正式执行"}；账号数量：{len(accounts)}')
    if not config_errors:
        for number, account in enumerate(accounts, 1):
            began = time.monotonic()
            counts = dict(success=0, already=0, skipped=0, failure=0)
            client = None
            logged_in = False
            steps = [('登录', True), ('每日签到', True), ('签到抽奖', sign_draw), ('相册签到抽奖', photos_draw)]
            for stage, (label, enabled) in enumerate(steps, 1):
                step_start = time.monotonic()
                log(f'账号 {number} / 阶段 {stage}/4：{label}')
                try:
                    if account is None:
                        if stage == 1:
                            raise TaskError('账号行格式错误，应为 账号|密码')
                        status, detail = 'skipped', '账号配置错误，跳过后续任务'
                    elif not enabled:
                        status, detail = 'skipped', '已通过任务开关关闭'
                    elif dry:
                        status, detail = 'skipped', 'DRY_RUN_OK：仅检查配置，不请求网络、不变更账号'
                    elif stage > 1 and not logged_in:
                        status, detail = 'skipped', '登录失败，跳过后续任务'
                    else:
                        if stage == 1:
                            client = Client(*account)
                            status, detail = client.login()
                            logged_in = True
                        elif stage == 2:
                            status, detail = client.sign()
                        else:
                            status, detail = client.draw('TASK_SIGNIN' if stage == 3 else 'TASK_SIGNIN_PHOTOS')
                except TaskError as exc:
                    status, detail = 'failure', str(exc)
                except Exception:
                    status, detail = 'failure', '任务异常，未输出可能含凭据的错误详情'
                counts[status] += 1
                icon = {'success': '✅', 'already': '☑️', 'skipped': '⏭️', 'failure': '❌'}[status]
                log(f'账号 {number} / 阶段 {stage}：{icon} {detail}；耗时 {time.monotonic()-step_start:.2f} 秒')
            if client:
                client.close()
            record = {'account': number, 'total': 4, **counts, 'seconds': round(time.monotonic()-began, 2)}
            records.append(record)
            log(f'账号 {number} 统计：总任务 4，成功 {counts["success"]}，已完成 {counts["already"]}，'
                f'跳过 {counts["skipped"]}，失败 {counts["failure"]}，耗时 {record["seconds"]} 秒')
    failed = sum(r['failure'] > 0 for r in records)
    ok = len(records) - failed
    exit_code = 1 if failed or config_errors else 0
    status = ('configuration-error' if config_errors else 'partial-failure' if failed and ok
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'applicationKey': '189', 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(accounts), 'succeeded': ok, 'failed': failed,
               'configurationErrors': config_errors, 'results': records, 'exitCode': exit_code}
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        log('⚠️ 通知执行异常，保留业务退出码')
        summary['notification'] = '发送失败'
    summary['seconds'] = round(time.monotonic()-started, 2)
    summary['finishedAt'] = dt.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log(f'账号统计：总数 {len(accounts)}，成功 {ok}，失败 {failed}；配置错误 {config_errors}')
    totals = {key: sum(r[key] for r in records) for key in ('total', 'success', 'already', 'skipped', 'failure')}
    log(f'子任务统计：总数 {totals["total"]}，成功 {totals["success"]}，已完成 {totals["already"]}，'
        f'跳过 {totals["skipped"]}，失败 {totals["failure"]}')
    log(f'总耗时：{summary["seconds"]} 秒；完成时间：{summary["finishedAt"]}')
    log(f'通知状态：{summary["notification"]}；最终状态：{status}；退出码：{exit_code}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
