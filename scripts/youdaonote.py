#!/usr/bin/env python3
# name: 有道云笔记签到
# cron: 50 9 * * *
# 来源: clouin/youdaonote-signin (main.py, config.py, notify/dingtalk.py)
# 上游许可及本维护版本许可: MIT
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
"""青龙单次任务；每日 08:00 调度由青龙 cron 管理。
YOUDAO_ACCOUNTS 必填，每个非空行 用户名|原始密码，只在首个 | 分割。
账号及密码取自有道云笔记官方客户端的网易账号登录，不支持第三方扫码密码。
可选 YOUDAO_CONFIG 显式读取已有 INI（不写文件），兼容 account.username /
password / retry_times / captcha_length、dingtalk.access_token / secret。
INI schedule.time 保留为 --daemon 的本地每日时间，默认 08:00；青龙无需此参数。
YOUDAO_DRY_RUN=1 完全断网，不加载 OCR、不发送通知、不保存验证码。
网络依赖: pip install requests ddddocr；验证码只在内存识别。
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
        _ql_notify_identities = ('575d117646dd4fd8', 'scripts/youdaonote.py', 'youdaonote.py', 'youdaonote')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import configparser
import fnmatch
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

TITLE = '有道云笔记签到'
CATALOG_ID = '575d117646dd4fd8'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
BASE = 'https://note.youdao.com'
# 保留上游 PC 客户端协议参数；不记录这些设备字段或会话值。
CLIENT = dict(app='client', product='YNOTE', ClientVer='61000010000',
              GUID='PCe3ea009f17ce4a46c', client_ver='61000010000',
              device_id='PCe3ea009f17ce4a46c', device_name='DESKTOP-0PK60BL',
              device_type='PC', keyfrom='pc', os='Windows', os_ver='Windows 10',
              vendor='website', vendornew='website')


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def integer(value, low, high):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise TaskError('整数配置格式错误') from None
    if not low <= n <= high:
        raise TaskError('整数配置超出允许范围')
    return n


def settings():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_dict({'account': {'username': '', 'password': '', 'retry_times': '3',
                              'captcha_length': '5'},
                   'dingtalk': {'access_token': '', 'secret': ''},
                   'schedule': {'time': '08:00'}, 'log': {'loglevel': 'INFO'}})
    if os.environ.get('YOUDAO_CONFIG'):
        try:
            with open(os.environ['YOUDAO_CONFIG'], encoding='utf-8') as f:
                cfg.read_file(f)
        except (OSError, configparser.Error, UnicodeError):
            raise TaskError('无法读取指定 INI 配置') from None
    raw = os.environ.get('YOUDAO_ACCOUNTS')
    if raw is None and cfg['account']['username'] and cfg['account']['password']:
        raw = cfg['account']['username'] + '|' + cfg['account']['password']
    lines = [line for line in (raw or '').splitlines() if line.strip()]
    if not lines:
        raise TaskError('缺少 YOUDAO_ACCOUNTS；每行填写 用户名|原始密码')
    accounts = []
    for line in lines:
        username, sep, password = line.partition('|')
        # 无效账号也单独统计，不阻断其余账号。
        accounts.append((username.strip(), password) if sep and username.strip() and password else None)
    length = os.environ.get('YOUDAO_CAPTCHA_LENGTH', cfg['account']['captcha_length'])
    ding = os.environ.get('YOUDAO_DINGTALK')
    if ding is not None:
        token, sep, secret = ding.partition('|')
        if ding and (not sep or not token or not secret):
            raise TaskError('YOUDAO_DINGTALK 格式应为 访问令牌|加签密钥')
    else:
        token, secret = cfg['dingtalk']['access_token'], cfg['dingtalk']['secret']
    if bool(token) != bool(secret):
        raise TaskError('钉钉访问令牌和加签密钥必须配套')
    daily = os.environ.get('YOUDAO_SCHEDULE_TIME', cfg['schedule']['time'])
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', daily):
        raise TaskError('每日时间应为 HH:MM')
    return dict(accounts=accounts,
                retries=integer(os.environ.get('YOUDAO_RETRY_TIMES', cfg['account']['retry_times']), 0, 10),
                length=integer(length, 1, 16) if length else None,
                timeout=integer(os.environ.get('YOUDAO_TIMEOUT', '20'), 1, 120),
                ding=(token, secret), daily=daily)


def json_object(response):
    try:
        data = response.json()
    except (ValueError, TypeError):
        raise TaskError('接口未返回有效 JSON；未确认成功') from None
    if not isinstance(data, dict):
        raise TaskError('接口返回结构错误；未确认成功')
    return data


def has_error(data):
    for key in ('error', 'errorCode', 'error_code', 'errcode', 'code', 'ret'):
        if key in data and data[key] not in (None, '', 0, '0', False):
            return True
    return data.get('success') is False


def show_identity(data, credentials):
    candidates = [data]
    for key in ('user', 'data', 'result'):
        if isinstance(data.get(key), dict):
            candidates.append(data[key])
    for obj in candidates:
        for key in ('nickname', 'nickName', 'displayName', 'username', 'uid'):
            value = obj.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            # 官方公开身份原样显示；手机号、邮箱账号及凭据仍不打印。
            if (not value or len(value) > 200 or '@' in value
                    or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value)
                    or any(ord(c) < 32 for c in value)
                    or any(secret and secret in value for secret in credentials)):
                continue
            log(f'官方账号身份：{value}')
            return


class Signer:
    def __init__(self, account, options):
        import requests
        import ddddocr
        self.session = requests.Session()
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.username, self.password = account
        self.options = options

    def close(self):
        self.session.close()

    def request(self, method, path, **kwargs):
        # 所有业务请求自行实现；禁止重定向携带登录数据或 Cookie。
        time.sleep(5 + int.from_bytes(os.urandom(1), 'big') % 16)
        try:
            with self.session.request(method, BASE + path, timeout=self.options['timeout'],
                                      allow_redirects=False, stream=True, **kwargs) as response:
                if response.status_code != 200:
                    raise TaskError('HTTP 状态异常；未确认业务成功')
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise TaskError('接口响应过大')
                    chunks.append(chunk)
                response._content = b''.join(chunks)
                response._content_consumed = True
                return response
        except TaskError:
            raise
        except Exception:
            raise TaskError('网络请求失败或超时；不输出请求详情') from None

    def captcha(self):
        for attempt in range(5):
            try:
                response = self.request('GET', '/login/acc/urs/verify/get', params=CLIENT)
                code = str(self.ocr.classification(response.content) or '')
                if code and (self.options['length'] is None or len(code) == self.options['length']):
                    log(f'验证码识别完成（第 {attempt + 1} 次，内容已隐藏）')
                    return code
            except Exception:
                pass
            log(f'验证码获取或长度校验未通过（第 {attempt + 1}/5 次）')
        raise TaskError('验证码获取失败，已达到重试上限')

    def login(self):
        for attempt in range(self.options['retries'] + 1):
            self.session.cookies.clear()
            try:
                code = self.captcha()
                params = dict(CLIENT, show='true', tp='urstoken', cf='6', vcode=code)
                response = self.request('POST', '/login/acc/urs/verify/check', params=params,
                                        data={'username': self.username,
                                              'password': hashlib.md5(self.password.encode()).hexdigest()},
                                        headers={'Content-Type': 'application/x-www-form-urlencoded'})
                # 不假定 HTTP 200 成功；仅接受明确成功字段或登录会话，
                # 最终仍必须通过签到的完整业务结果验证。
                data = {}
                try:
                    data = json_object(response)
                except TaskError:
                    pass
                explicit = (data.get('success') is True or any(
                    key in data and type(data[key]) in (str, int) and data[key] in (0, '0')
                    for key in ('code', 'ret', 'errorCode')))
                authenticated = any(c.name in ('YNOTE_LOGIN', 'YNOTE_SESS') and c.value
                                    for c in self.session.cookies)
                if has_error(data) or not (explicit or authenticated):
                    raise TaskError('登录响应未证明认证成功')
                show_identity(data, (self.password, hashlib.md5(self.password.encode()).hexdigest()))
                log('登录验证通过；待签到接口核验业务结果')
                return
            except TaskError:
                log(f'登录尝试失败（第 {attempt + 1}/{self.options["retries"] + 1} 次），详情已脱敏')
        raise TaskError('登录失败，已达到重试上限')

    def sign(self):
        # 不自动重试签到，避免响应丢失后重复提交状态变更。
        data = json_object(self.request('POST', '/yws/mapi/user', params={'method': 'checkin'}))
        if has_error(data):
            raise TaskError('签到接口返回业务失败')
        values = []
        for key in ('space', 'total', 'time'):
            value = data.get(key)
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise TaskError('签到响应缺少有效奖励或时间字段')
            try:
                number = float(value)
            except (ValueError, OverflowError):
                raise TaskError('签到数值字段格式错误') from None
            if not math.isfinite(number) or number < 0:
                raise TaskError('签到数值字段超出有效范围')
            values.append(number)
        space, total, stamp = values
        if stamp <= 0 or total < space:
            raise TaskError('签到结果校验失败')
        try:
            signed_at = datetime.fromtimestamp(stamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OverflowError, OSError):
            raise TaskError('签到时间字段无效') from None
        show_identity(data, (self.password, hashlib.md5(self.password.encode()).hexdigest()))
        log(f'✅ 签到成功；签到时间 {signed_at}；本次获得 {space / 1048576:.1f} MB；总共获得 {total / 1048576:.1f} MB')


def notification_enabled():
    mode = os.environ.get('QINGLONG_NOTIFY', 'auto').lower().strip()
    if mode in FALSE:
        return False
    if mode in TRUE:
        return True
    if mode != 'auto':
        log('⚠️ QINGLONG_NOTIFY 无效，禁用通知')
        return False
    selectors = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is None:
        return False  # listed-only，没有默认选中名单
    script = Path(__file__).resolve()
    relative = script.name
    if 'scripts' in script.parts:
        relative = Path(*script.parts[script.parts.index('scripts') + 1:]).as_posix()
    else:
        try:
            relative = script.relative_to(Path.cwd()).as_posix()
        except ValueError:
            pass
    names = (CATALOG_ID, relative, Path(__file__).name, 'candidate.py',
             'checkin/youdaonote.py', 'youdaonote.py', Path(__file__).as_posix())
    return any(fnmatch.fnmatch(name, pattern) for pattern in re.split(r'[,;\s]+', selectors.strip())
               if pattern for name in names)


def notify(body, options, dry):
    if dry:
        log('⏭️ 通知断网预演：仅生成脱敏摘要，不调用通知模块')
        return '断网预演'
    if not notification_enabled():
        return '全局策略未选中'
    delivered = False
    # 青龙通知是可选适配器；缺失时不影响独立业务请求和退出码。
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    helper = ("import importlib.util,sys; p=sys.argv[1]; "
              "s=importlib.util.spec_from_file_location('ql_notification',p); "
              "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
              "m.send(sys.argv[2],sys.argv[3])")
    commands = [[sys.executable, '-c', 'from notify import send; import sys; send(sys.argv[1],sys.argv[2])', TITLE, body]]
    commands.extend([sys.executable, '-c', helper, str(p), TITLE, body] for p in paths if p.is_file())
    js_dirs = [p.parent for p in paths]
    js_helper = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
    commands.extend(['node', '-e', js_helper, str(p / 'sendNotify.js'), TITLE, body]
                    for p in js_dirs if (p / 'sendNotify.js').is_file())
    for cmd in commands:
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            if result.returncode == 0:
                delivered = True
                break
        except (OSError, subprocess.TimeoutExpired):
            pass
    # 原有钉钉配置作为兼容附加通道，同样受全局通知开关控制。
    if options and all(options['ding']):
        try:
            import requests
            token, secret = options['ding']
            stamp = str(round(time.time() * 1000))
            signature = base64.b64encode(hmac.new(secret.encode(), f'{stamp}\n{secret}'.encode(), hashlib.sha256).digest()).decode()
            response = requests.post('https://oapi.dingtalk.com/robot/send',
                                     params={'access_token': token, 'timestamp': stamp, 'sign': signature},
                                     json={'msgtype': 'text', 'text': {'content': TITLE + '\n' + body}},
                                     timeout=options['timeout'], allow_redirects=False)
            if response.status_code == 200 and json_object(response).get('errcode') == 0:
                delivered = True
            else:
                log('⚠️ 钉钉通知未确认成功')
        except Exception:
            log('⚠️ 钉钉通知失败，错误详情已隐藏')
    return '已发送' if delivered else '通知不可用或失败（保留业务退出码）'


def run():
    started = time.monotonic()
    dry = os.environ.get('YOUDAO_DRY_RUN', '').strip().lower() in TRUE
    log('=' * 48)
    log(TITLE + f' | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log('运行模式：' + ('断网预演' if dry else '正式签到'))
    options, results, config_error = None, [], False
    try:
        options = settings()
        log(f'账号总数：{len(options["accounts"])}')
        for index, account in enumerate(options['accounts'], 1):
            account_start = time.monotonic()
            stats = dict(account=index, total=2, success=0, alreadyComplete=0, skipped=0, failed=0)
            log(f'----- 账号 {index} -----')
            signer = None
            try:
                if account is None:
                    raise TaskError('账号行格式错误，应为 用户名|原始密码')
                if dry:
                    for stage, title in ((1, '验证码识别与登录'), (2, '签到及奖励统计')):
                        log(f'阶段 {stage}/2 {title}：⏭️ 参数检查通过，断网跳过，耗时 0.000 秒')
                    stats['skipped'] = 2
                else:
                    for stage, title in ((1, '验证码识别与登录'), (2, '签到及奖励统计')):
                        stage_start = time.monotonic()
                        log(f'阶段 {stage}/2 {title}：开始')
                        try:
                            if stage == 1:
                                signer = Signer(account, options)
                                signer.login()
                            else:
                                signer.sign()
                        finally:
                            log(f'阶段 {stage}/2 {title}：结束，耗时 {time.monotonic() - stage_start:.3f} 秒')
                        stats['success'] += 1
            except Exception as exc:
                message = str(exc) if isinstance(exc, TaskError) else '执行失败（检查公共依赖和运行环境；错误详情已隐藏）'
                log('❌ ' + message)
                stats['failed'] = 1
                stats['skipped'] = 2 - stats['success'] - 1
            finally:
                if signer:
                    signer.close()
            stats['status'] = 'failure' if stats['failed'] else ('dry-run' if dry else 'success')
            stats['seconds'] = round(time.monotonic() - account_start, 3)
            results.append(stats)
            log(f'账号 {index} 统计：总任务 2；成功 {stats["success"]}；已完成 0；跳过 {stats["skipped"]}；失败 {stats["failed"]}；耗时 {stats["seconds"]} 秒')
    except Exception as exc:
        config_error = True
        log('账号总数：0')
        log('❌ 配置错误：' + (str(exc) if isinstance(exc, TaskError) else '配置解析失败，详情已隐藏'))
    failed = sum(r['failed'] > 0 for r in results)
    succeeded = sum(r['status'] == 'success' for r in results)
    status = ('configuration-error' if config_error else
              ('partial-failure' if failed and failed < len(results) else 'failure') if failed else
              'dry-run' if dry else 'success')
    summary = dict(status=status, mode='dry-run' if dry else 'live', accounts=len(results),
                   success=succeeded, failed=failed, dryRun=sum(r['status'] == 'dry-run' for r in results),
                   configurationError=config_error, accountResults=results)
    body = (f'状态：{status}；账号总数 {len(results)}；成功 {succeeded}；失败 {failed}；'
            f'预演 {summary["dryRun"]}；配置错误 {int(config_error)}')
    try:
        summary['notification'] = notify(body, options, dry)
    except Exception:
        summary['notification'] = '通知失败（保留业务退出码）'
    summary['seconds'] = round(time.monotonic() - started, 3)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log('-' * 48)
    log(body)
    log('子任务统计：' + '；'.join(f'{label} {sum(r[key] for r in results)}' for key, label in
                                     [('total', '总数'), ('success', '成功'), ('alreadyComplete', '已完成'), ('skipped', '跳过'), ('failed', '失败')]))
    log(f'总耗时 {summary["seconds"]} 秒；完成时间 {summary["finishedAt"]}；通知状态：{summary["notification"]}')
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return 1 if config_error or failed else 0


def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument('--daemon', action='store_true', help='兼容上游每日定时常驻模式，青龙不使用')
    args = parser.parse_args()
    if not args.daemon or os.environ.get('YOUDAO_DRY_RUN', '').lower() in TRUE:
        return run()
    # 保留原每日调度能力；青龙使用顶部 cron 单次执行以避免重复调度。
    try:
        daily = settings()['daily']
    except Exception:
        return run()
    failed = False
    try:
        while True:
            hour, minute = map(int, daily.split(':'))
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            log(f'每日调度等待：{next_run:%Y-%m-%d %H:%M:%S}')
            while datetime.now() < next_run:
                time.sleep(min(30, max(0.01, (next_run - datetime.now()).total_seconds())))
            failed = bool(run()) or failed
    except KeyboardInterrupt:
        return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
