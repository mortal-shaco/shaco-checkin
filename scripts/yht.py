#!/usr/bin/env python3
# name: 益禾堂手机点单
# cron: 8 6 * * *
# 原作者: 清风；来源: Rookie-wb-WH/ql_scripts/yht.py
# 原始更新: 2024.09.03 更新种植活动；2024.10.12 添加领取功能、增加活动互助。
# 上游参数说明: vx小程序 -- 益禾堂手机点单；抓包 webapi.qmai.cn 下的 qm-user-token。
# 上游多账号曾使用 # 分隔；维护版本保留 Yht_token 名称，改为每行一个账号。
# License: MIT (effectiveLicense supplied by source catalog).
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
"""Python 3.9+，仅使用标准库。Yht_token 每个非空行填写一个完整 token。
在微信益禾堂手机点单小程序登录，使用自己的授权抓包工具查看 webapi.qmai.cn
请求头 qm-user-token。不要填写手机号、Cookie 或整段请求头。
默认每日种植流程；YHT_SIGN=1 启用原有未调用的签到，YHT_HELP=1 启用本次
配置账号之间的互助。不会访问作者远端名单，不向第三方助力。
YHT_DRY_RUN=1 完全断网预演，通知适配器也在禁网子进程中调用。
历史活动 ID 仅为上游证据，并不保证活动目前开放；失败请在小程序核实后更新 ID。
"""
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '益禾堂手机点单'
APP = 'wx4080846d0cec2fd5'
BASE = 'https://webapi.qmai.cn/web/'
UA = 'Mozilla/5.0 (Linux; Android 13; Xiaomi Mi 11 Build/PROS03P8SML4CNCIMP4; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1220133 MMWEBSDK/20230306 MMWEBID/1419 MicroMessenger/8.0.40.2420(0x28002939) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64'
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = []


class TaskError(Exception):
    pass


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def safe(value):
    text = str(value)
    for token in SECRETS:
        text = text.replace(token, '[凭据已隐藏]')
    return re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text).replace('\r', ' ').replace('\n', ' ')


def log(text):
    print('[{}] {}'.format(time.strftime('%H:%M:%S'), safe(text)), flush=True)


def flag(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value in FALSE:
        return False
    if value in {'1', 'true', 'yes', 'on'}:
        return True
    raise TaskError(name + ' 只能为 1 或 0（也支持 true/false、yes/no、on/off）')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向已拒绝，未转发凭据')


class Client:
    def __init__(self, token, dry, timeout):
        self.token, self.dry, self.timeout = token, dry, timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, data, method='POST', activity=False):
        if self.dry:
            raise TaskError('预演禁止 HTTP 请求')
        headers = {'Content-Type': 'application/json', 'qm-from': 'wechat',
                   'qm-from-type': 'catering', 'qm-user-token': self.token,
                   'Referer': 'https://servicewechat.com/' + APP + '/327/page-frame.html',
                   'User-Agent': UA}
        url = BASE + path
        body = None
        if method == 'GET':
            url += '?' + urllib.parse.urlencode(data)
        else:
            body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态非 200')
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应过大')
            result = json.loads(raw)
        except TaskError:
            raise
        except urllib.error.HTTPError as exc:
            raise TaskError('HTTP 请求失败，状态 {}'.format(exc.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TaskError('网络请求失败或超时；未自动重试写入') from None
        except (ValueError, UnicodeError):
            raise TaskError('接口未返回合法 JSON') from None
        if not isinstance(result, dict):
            raise TaskError('响应结构不符合契约')
        # activityInfo 上游使用 code == 0；其他接口使用布尔 status。
        ok = type(result.get('code')) is int and result['code'] == 0 if activity else result.get('status') is True
        if activity and result.get('status') is False:
            ok = False
        return result, ok

    def verified(self, path, data, method='POST', activity=False):
        result, ok = self.request(path, data, method, activity)
        if not ok:
            raise TaskError('业务未确认成功（原始响应已隐藏）')
        return result.get('data')


class Account:
    def __init__(self, number, client):
        self.number, self.client = number, client
        self.uid = None
        self.stats = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
        self.steps = 0
        self.started = time.monotonic()

    def step(self, name, fn=None, enabled=True):
        self.steps += 1
        start = time.monotonic()
        log('账号 {} 阶段 {}：{}'.format(self.number, self.steps, name))
        result = None
        if not enabled:
            state, detail = 'skipped', '开关关闭或前置阶段未通过'
        elif self.client.dry:
            state, detail = 'skipped', 'DRY_RUN：已检查请求计划，不调用接口，不确认业务成功'
        else:
            try:
                result = fn()
                state, detail = 'success', '业务成功已核验'
            except TaskError as exc:
                state, detail = 'failed', str(exc)
            except Exception:
                state, detail = 'failed', '返回字段或执行契约异常（详情已隐藏）'
        self.stats[state] += 1
        log('{} 账号 {} {}：{}；耗时 {:.2f}s'.format(
            {'success': '✅', 'failed': '❌', 'skipped': '⏭️'}[state],
            self.number, name, detail, time.monotonic() - start))
        return state == 'success', result


def data_object(data, fields):
    if not isinstance(data, dict) or any(field not in data for field in fields):
        raise TaskError('成功响应缺少必要业务字段')
    return data


def profile(account):
    data = data_object(account.client.verified('catering/crm/personal-info', {'appid': APP}, 'GET'), ())
    # 只输出官方非敏感身份字段，绝不输出 mobilePhone。
    for field in ('name', 'nickname', 'username', 'displayName', 'uid'):
        if data.get(field) is not None and str(data[field]).strip():
            log('账号 {} 官方身份：{}'.format(account.number, data[field]))
            break


def discover_uid(account):
    data = data_object(account.client.verified('catering/crm/customer/card/level/benefits', {'appid': APP}, 'GET'), ('upgradeInfoResponse',))
    info = data_object(data['upgradeInfoResponse'], ('customerId',))
    uid = str(info['customerId'])
    if not uid or uid == 'None':
        raise TaskError('未返回互助用户标识')
    account.uid = uid
    log('账号 {} 互助用户标识已取得'.format(account.number))


def activity(account, payload):
    data = data_object(account.client.verified('cmk-center/nurture/activityInfo', payload, activity=True), ('activityTitle',))
    log('活动：{}'.format(data['activityTitle']))


def reward(account, payload):
    data = account.client.verified('cmk-center/nurture/sendReward', payload)
    if not isinstance(data, list) or not data:
        raise TaskError('奖励响应缺少领取结果')
    for item in data:
        item = data_object(item, ('rewardName', 'sendNum'))
        if not isinstance(item['sendNum'], (int, float)) or isinstance(item['sendNum'], bool) or item['sendNum'] <= 0:
            raise TaskError('奖励数量未确认')
        log('领取奖励：{} x{}'.format(item['rewardName'], item['sendNum']))


def fertilize(account, payload, limit):
    for index in range(limit):
        result, ok = account.client.request('cmk-center/nurture/add/nutrient', payload)
        if ok:
            log('施肥第 {} 次：成功'.format(index + 1))
            if index + 1 < limit:
                time.sleep(1)
            continue
        if result.get('message') == '当前不存在进行中的活动':
            claimed, _ = account.step('种植完成后领取奖励', lambda: reward(account, payload))
            if claimed:
                log('种植结束且奖励领取已核验；结束施肥')
                return
            raise TaskError('当前无进行中的种植且奖励未确认领取成功')
        raise TaskError('施肥第 {} 次业务失败；已停止，未推定为肥料耗尽'.format(index + 1))
    log('施肥达到配置上限 {} 次，全部返回成功'.format(limit))


def stage(account, payload):
    data = data_object(account.client.verified('cmk-center/nurture/stageInfo', payload), ('level', 'nextName', 'upgradeThreshold', 'nutrientUsed'))
    remaining = data['upgradeThreshold'] - data['nutrientUsed']
    log('当前等级：{}级；距离 {} 还差 {} 次施肥'.format(data['level'], data['nextName'], remaining))


def signin(account, sign_id):
    data = data_object(account.client.verified('cmk-center/sign/takePartInSign', {'activityId': sign_id, 'appid': APP}), ('rewardDetailList',))
    items = data['rewardDetailList']
    if not isinstance(items, list) or not items:
        raise TaskError('签到响应缺少奖励详情；不推定重复签到成功')
    for item in items:
        item = data_object(item, ('rewardName', 'sendNum'))
        log('签到奖励：{} x{}'.format(item['rewardName'], item['sendNum']))


# 通知在独立进程执行，超时及异常不改变业务退出码。预演禁止套接字及派生进程。
NOTIFY_RUNNER = r'''
import sys, json, os, importlib.util, socket, subprocess
payload = json.loads(sys.stdin.read())
if payload['dry']:
    def deny(*args, **kwargs):
        raise RuntimeError('dry-run notification network disabled')
    socket.socket = deny
    socket.create_connection = deny
    subprocess.Popen = deny
    os.system = deny
    os.fork = deny
    os.posix_spawn = deny
    os.posix_spawnp = deny
    def audit(event, args):
        if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.system', 'os.fork', 'ctypes.')):
            deny()
    sys.addaudithook(audit)
sys.path.insert(0, payload['scriptDir'])
paths = []
if os.getenv('QINGLONG_NOTIFY_DIR'):
    paths.append(os.path.join(os.getenv('QINGLONG_NOTIFY_DIR'), 'notify.py'))
paths += ['/ql/data/scripts/notify.py', '/ql/scripts/notify.py']
try:
    try:
        import notify
    except ImportError:
        notify = None
        for path in paths:
            if os.path.isfile(path):
                spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                notify = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(notify)
                break
    if notify is None or not callable(getattr(notify, 'send', None)):
        sys.exit(2)
    notify.send(payload['title'], payload['body'])
except Exception:
    sys.exit(3)
'''


def notification(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE:
        log('通知：全局开关已关闭')
        return 'disabled'
    try:
        # 子进程只接收通知所需变量，不继承账号凭据。
        env = {key: value for key, value in os.environ.items()
               if key not in {'Yht_token'} and not key.startswith('YHT_')}
        result = subprocess.run([sys.executable, '-c', NOTIFY_RUNNER], input=json.dumps(
            {'title': TITLE, 'body': body, 'dry': dry, 'scriptDir': os.path.dirname(os.path.abspath(__file__))}, ensure_ascii=False), text=True,
            capture_output=True, timeout=20, env=env)
        if result.returncode == 0:
            log('通知：适配器已调用' + ('（禁网预演）' if dry else ''))
            return 'sent'
        log('通知：适配器不可用或发送失败' + ('（预演禁止联网）' if dry else '') + '；保留业务退出码')
    except Exception:
        log('通知：发送异常或超时；保留业务退出码')
    return 'unavailable'


def main():
    started, start_time = time.monotonic(), now()
    raw_accounts = [line.strip() for line in os.getenv('Yht_token', '').splitlines() if line.strip()]
    SECRETS.extend(raw_accounts)
    accounts, error = [], None
    dry = os.getenv('YHT_DRY_RUN', '0').strip().lower() not in FALSE
    log('========== ' + TITLE + ' ==========')
    log('开始时间：{}；模式：{}；账号数：{}'.format(start_time, '断网预演' if dry else '实跑', len(raw_accounts)))
    try:
        dry = flag('YHT_DRY_RUN')
        help_enabled, sign_enabled = flag('YHT_HELP'), flag('YHT_SIGN')
        timeout = float(os.getenv('YHT_TIMEOUT', '15'))
        limit = int(os.getenv('YHT_FERTILIZE_LIMIT', '100'))
        if not 1 <= timeout <= 60 or not 1 <= limit <= 100:
            raise TaskError('超时须为 1～60 秒；施肥上限须为 1～100')
        if not raw_accounts:
            raise TaskError('缺少 Yht_token，请填写每行一个账号的 qm-user-token')
        for token in raw_accounts:
            if any(char in token for char in ('#', '&', '@')) or any(char.isspace() or ord(char) < 32 or ord(char) > 126 for char in token):
                raise TaskError('Yht_token 格式错误：每行一个完整令牌，不支持旧的 # 等账号分隔符')
        plant_id = os.getenv('YHT_PLANT_ACTIVITY_ID', '1025694534292430849')
        sign_id = os.getenv('YHT_SIGN_ACTIVITY_ID', '992065397145317377')
        if not plant_id.isdecimal() or not sign_id.isdecimal():
            raise TaskError('活动 ID 必须为数字')
        payload = {'activityId': plant_id, 'appid': APP}
        accounts = [Account(i, Client(token, dry, timeout)) for i, token in enumerate(raw_accounts, 1)]
        for account in accounts:
            profile_ok, _ = account.step('账号身份查询', lambda a=account: profile(a))
            account.authorized = profile_ok or dry
            account.step('互助身份查询', lambda a=account: discover_uid(a), help_enabled and account.authorized)
        for account in accounts:
            if help_enabled:
                targets = [a for a in accounts if a is not account and (a.uid or dry)]
                for target in targets:
                    account.step('助力配置账号 {}'.format(target.number), lambda t=target: account.client.verified(
                        'cmk-center/task/userHelp', dict(payload, inviteUserId=t.uid)), account.authorized)
                if not targets:
                    account.step('配置账号互助', enabled=False)
            else:
                account.step('配置账号互助', enabled=False)
            account.step('每日签到', lambda: signin(account, sign_id), sign_enabled and account.authorized)
            entry_ok, _ = account.step('种植活动查询', lambda: activity(account, payload), account.authorized)
            # 查询失败时不盲目写入；种植失败可能是重复参与，不推定成功，仍可独立施肥查询进度。
            account.step('参与种植', lambda: account.client.verified('cmk-center/nurture/takePartInNurture', payload), entry_ok or dry)
            account.step('施肥（上限 {} 次）'.format(limit), lambda: fertilize(account, payload, limit), entry_ok or dry)
            account.step('种植进度查询', lambda: stage(account, payload), entry_ok or dry)
            if dry:
                account.step('种植完成后领取奖励（条件分支）')
            log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，耗时 {:.2f}s'.format(
                account.number, account.steps, account.stats['success'], account.stats['alreadyComplete'],
                account.stats['skipped'], account.stats['failed'], time.monotonic() - account.started))
    except TaskError as exc:
        error = str(exc)
    except Exception:
        error = '参数或执行异常（详情已隐藏）'
    if error:
        log('❌ 配置错误：' + error)
    failed = sum(a.stats['failed'] > 0 for a in accounts)
    if error:
        failed = len(raw_accounts)
    succeeded = 0 if dry or error else len(accounts) - failed
    exit_code = 1 if error or failed else 0
    status = 'configuration-error' if error else 'dry-run' if dry else 'partial-failure' if failed and succeeded else 'failure' if failed else 'success'
    totals = {key: sum(a.stats[key] for a in accounts) for key in ('success', 'alreadyComplete', 'skipped', 'failed')}
    body = '{}；模式 {}；账号总数 {}，成功 {}，失败 {}，预演 {}；子任务成功 {}，跳过 {}，失败 {}'.format(
        TITLE, '断网预演' if dry else '实跑', len(raw_accounts), succeeded, failed,
        len(accounts) if dry else 0, totals['success'], totals['skipped'], totals['failed'])
    log('------------------------------')
    log(body)
    notify_status = notification(body + '；最终状态 ' + status, dry)
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accounts': len(raw_accounts), 'success': succeeded, 'failed': failed,
               'dryRunAccounts': len(accounts) if dry else 0, 'stages': totals,
               'accountResults': [{'account': a.number, 'total': a.steps, **a.stats,
                                   'elapsedSeconds': round(time.monotonic() - a.started, 2)} for a in accounts],
               'notification': notify_status, 'startTime': start_time, 'finishTime': now(),
               'elapsedSeconds': round(time.monotonic() - started, 2), 'exitCode': exit_code}
    log('完成时间：{}；总耗时 {:.2f}s；最终状态：{}；退出码 {}'.format(
        summary['finishTime'], summary['elapsedSeconds'], status, exit_code))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
