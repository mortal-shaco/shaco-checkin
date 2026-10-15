#!/usr/bin/env python3
# name: 杰士邦安心福利社
# cron: 21 2 * * *
# 来源：Rookie-wb-WH/ql_scripts，jissbon.py
# 上游许可：MIT（task.json 指定）；原文件没有独立版权声明。
# 原始说明：vx小程序 -- 杰士邦安心福利社；抓包 vip.ixiliu.cn 下的 Access-Token；
# 原参数 jsbaxfls，原计划 9 9 * * *；已完成 签到,分享任务。
"""杰士邦安心福利社，Python 3.9+，仅使用标准库。
jsbaxfls：微信小程序登录后，从自己访问 vip.ixiliu.cn 的请求头获取
Access-Token 的完整值；每个非空行一个账号。旧 # 分隔请改为换行。
JSB_LOTTERY=1 显式启用抽奖（可能消耗积分/机会），默认关闭。
JSB_LOTTERY_COUNT=1..10，默认10；活动编号沿用原脚本，未验证当前有效性。
JSB_DRY_RUN=1 完全断网预演，不验证凭据或业务成功。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
移除固定对象竞猜助力和外部推广请求；分享接口仅登记奖励，不发布文字。
"""
# MIT License
# Attribution: Rookie-wb-WH/ql_scripts (upstream author/repository).
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
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.request
import urllib.parse

TITLE = '杰士邦安心福利社'
BASE = 'https://vip.ixiliu.cn'
UA = 'Mozilla/5.0 (Linux; Android 14; 23090RA98C Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20231202 MMWEBID/1747 MicroMessenger/8.0.47.2560(0x28002F30) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android'
DISABLED = {'0', 'false', 'no', 'off'}


def enabled(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value in DISABLED:
        return False
    if value in {'1', 'true', 'yes', 'on'}:
        return True
    raise ValueError(name + ' 必须为布尔开关')


def log(message):
    print(time.strftime('[%H:%M:%S] ') + message, flush=True)


class BusinessError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BusinessError('拒绝重定向，防止凭据转发')


def request(token, path, params=None, lottery=False):
    if enabled('JSB_DRY_RUN'):
        raise BusinessError('预演禁止网络')
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    headers = {'access-token': token, 'content-type': 'application/json;charset=utf-8',
               'platform': 'MP-WEIXIN', 'sid': '10009', 'user-agent': UA,
               'referer': 'https://servicewechat.com/' +
               ('wxe11089c85860ec02/30' if lottery else 'wx9a2dc52c95994011/81') + '/page-frame.html'}
    try:
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(urllib.request.Request(url, headers=headers), timeout=15) as response:
            if response.status != 200:
                raise BusinessError('HTTP状态失败')
            raw = response.read(262145)
            if len(raw) > 262144:
                raise BusinessError('响应超过大小限制')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise BusinessError('响应结构异常')
        return result
    except BusinessError:
        raise
    except Exception:
        raise BusinessError('请求失败或响应无法解析（详情已脱敏）') from None


def checked(result):
    # 原脚本明确使用数值 status=200，不猜测其它成功码。
    if type(result.get('status')) is not int or result['status'] != 200:
        raise BusinessError('业务状态未确认成功')
    return result.get('data')


def notify_worker():
    payload = json.load(sys.stdin)
    if payload['dry']:
        import socket
        def denied(*args, **kwargs):
            raise RuntimeError('预演禁止网络')
        socket.socket.connect = denied
        socket.socket.connect_ex = denied
        socket.create_connection = denied
        socket.getaddrinfo = denied
        socket.gethostbyname = denied
        socket.socket.sendto = denied
        subprocess.Popen = denied
        os.system = denied
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path(__file__).resolve().parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    # 捕获通知模块的输出，防止模块输出配置或原始响应。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            import notify
        except ImportError:
            notify = None
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('notify', str(path))
                    notify = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(notify)
                    break
        if notify is None or not callable(getattr(notify, 'send', None)):
            return 2
        notify.send(TITLE, payload['body'])
    return 0


def notify_summary(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--notify-worker'],
                                input=json.dumps({'body': body, 'dry': dry}), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if result.returncode == 0:
            return '已调用通知模块' if not dry else '已调用通知模块（网络禁止）'
        return '不可用或发送失败（保留业务退出码）'
    except Exception:
        return '通知失败或超时（保留业务退出码）'


def run_account(index, token, dry, lottery, count):
    start = time.monotonic()
    stats = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    authenticated = False
    def stage(number, name, action=None):
        nonlocal authenticated
        tick = time.monotonic()
        stats['total'] += 1
        log('账号%d 阶段%d：%s' % (index, number, name))
        outcome = 'success'
        try:
            if action is None:
                outcome = 'skipped'
                log('⏭️ 未开启，跳过')
            elif dry:
                outcome = 'skipped'
                log('⏭️ 预演：将执行该阶段，不发请求、不验证业务')
            elif action is None or (number > 1 and not authenticated):
                outcome = 'skipped'
                log('⏭️ 未开启或账号身份核验失败，跳过')
            else:
                outcome = action() or 'success'
                log(('☑️ 已完成' if outcome == 'alreadyComplete' else '✅ 成功') + '：' + name)
        except Exception as exc:
            outcome = 'failure'
            log('❌ ' + (str(exc) if isinstance(exc, BusinessError) else '响应字段异常（详情已脱敏）'))
        stats[outcome] += 1
        log('阶段%d结束，耗时%.2f秒' % (number, time.monotonic() - tick))
        return outcome
    def info():
        nonlocal authenticated
        data = checked(request(token, '/mp/user/info'))
        user = data['userInfo']
        if not isinstance(user, dict) or 'points' not in user:
            raise BusinessError('用户信息契约异常')
        points = user['points']
        if isinstance(points, bool) or not isinstance(points, (int, float)):
            raise BusinessError('积分字段异常')
        nickname = user.get('nick_name')
        if isinstance(nickname, str) and nickname:
            # 按官方昵称显示；只排除凭据、手机号等已知敏感值。
            sensitive = [token, user.get('mobile')]
            if not any(isinstance(x, str) and x and x in nickname for x in sensitive):
                print('官方昵称：' + json.dumps(nickname, ensure_ascii=False), flush=True)
        log('当前积分：%s' % points)
        authenticated = True
    def sign():
        checked(request(token, '/mp/sign/applyV2'))
    def share():
        data = checked(request(token, '/mp/guess.home/share'))
        if not isinstance(data, dict) or data.get('isTodayFirst') is not True:
            # 上游 false 分支为失败；不能擅自视为已经成功。
            raise BusinessError('分享奖励未确认：isTodayFirst不为true')
    def draw():
        r = request(token, '/mp/activity.lottery/draw', {'snId': 351193591081728, 'channelSn': '0'}, True)
        if r.get('msg') == '今日抽奖次数已用完' and r.get('status') != 200:
            log('☑️ 官方返回今日抽奖次数已用完')
            return 'alreadyComplete'
        data = checked(r)
        prize = data['prize']['prize_name']
        if not isinstance(prize, str) or not prize:
            raise BusinessError('抽奖结果契约异常')
        log('抽奖成功，奖品字段已核验')
    stage(1, '账号信息与积分', info)
    stage(2, '每日签到', sign)
    if not dry: time.sleep(random.uniform(1, 3))
    stage(3, '分享奖励登记（不发布文字）', share)
    if lottery:
        for turn in range(count):
            if not dry: time.sleep(random.uniform(.5, .8))
            outcome = stage(4 + turn, '抽奖第%d次' % (turn + 1), draw)
            if outcome in {'failure', 'alreadyComplete'} or not authenticated and not dry:
                break
    else:
        stage(4, '抽奖（默认关闭）')
    stats['elapsedSeconds'] = round(time.monotonic() - start, 2)
    stats['index'] = index
    stats['status'] = 'failure' if stats['failure'] else ('dry-run' if dry else 'success')
    log('账号%d统计：总任务%d 成功%d 已完成%d 跳过%d 失败%d 耗时%.2f秒' %
        (index, stats['total'], stats['success'], stats['alreadyComplete'], stats['skipped'], stats['failure'], stats['elapsedSeconds']))
    return stats


def main():
    start = time.monotonic()
    started = time.strftime('%Y-%m-%d %H:%M:%S')
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + started)
    accounts = [x.strip() for x in os.getenv('jsbaxfls', '').splitlines() if x.strip()]
    dry = os.getenv('JSB_DRY_RUN', '0').strip().lower() not in DISABLED
    results = []
    config_error = False
    try:
        dry = enabled('JSB_DRY_RUN')
        lottery = enabled('JSB_LOTTERY')
        count = int(os.getenv('JSB_LOTTERY_COUNT', '10'))
        if count < 1 or count > 10:
            raise ValueError('JSB_LOTTERY_COUNT 必须为1至10')
        if not accounts:
            raise ValueError('缺少jsbaxfls：请按每行一个账号填写Access-Token')
        if any(any(c in x for c in '#\r\x00') for x in accounts):
            raise ValueError('账号格式错误：旧#分隔请改为换行，凭据不得含控制字符')
        for x in accounts:
            if any(ord(c) < 32 or ord(c) > 126 for c in x):
                raise ValueError('Access-Token必须为可打印ASCII请求头值')
    except (ValueError, TypeError):
        config_error = True
        log('❌ 配置错误：检查jsbaxfls非空、换行分隔、ASCII凭据和布尔开关、抽奖次数1至10')
    log('模式：' + ('断网预演' if dry else '实际执行'))
    log('账号总数：%d' % len(accounts))
    if not config_error:
        for i, token in enumerate(accounts, 1):
            results.append(run_account(i, token, dry, lottery, count))
    failed = sum(x['status'] == 'failure' for x in results)
    success = sum(x['status'] == 'success' for x in results)
    status = 'configuration-error' if config_error else ('partial-failure' if failed and failed < len(results) else 'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if config_error or failed else 0
    body = '状态：%s；账号总数：%d；成功：%d；失败：%d；预演：%d。配置错误：%s。' % (status, len(accounts), success, failed, len(results) if dry else 0, '是' if config_error else '否')
    notification = notify_summary(body, dry)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(x[key] for x in results) for key in ['total', 'success', 'alreadyComplete', 'skipped', 'failure']}
    log('子任务统计：总数%d 成功%d 已完成%d 跳过%d 失败%d' % tuple(totals.values()))
    finish = time.strftime('%Y-%m-%d %H:%M:%S')
    log('总耗时：%.2f秒；完成时间：%s' % (time.monotonic() - start, finish))
    log('通知状态：' + notification)
    log('最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'mode': 'dry-run' if dry else 'live', 'accountCount': len(accounts), 'success': success, 'failure': failed, 'dryRunAccounts': len(results) if dry else 0, 'configurationError': config_error, 'accounts': results, 'stages': totals, 'startedAt': started, 'finishedAt': finish, 'notification': notification, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    if sys.argv[1:] == ['--notify-worker']:
        try:
            sys.exit(notify_worker())
        except Exception:
            sys.exit(2)
    sys.exit(main())
