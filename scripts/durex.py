#!/usr/bin/env python3
# name: 杜蕾斯会员中心
# cron: 52 0 * * *
# SPDX-License-Identifier: MIT
# 来源：Rookie-wb-WH/ql_scripts，durex.py，提交 08e5c06461c4a0112ea3735f48fe671734bb7707
# MIT License（任务准入声明的上游许可）
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
# 上游原说明：vx小程序 -- 杜蕾斯会员中心；抓包 vip.ixiliu.cn 下的 Access-Token；完成 签到,抽奖。
"""独立维护版，Python 3.9 及以上，仅使用标准库。
在微信「杜蕾斯会员中心」小程序登录，用本人授权的抓包工具获取
vip.ixiliu.cn 请求头 Access-Token。dlshyzx 每个非空行一个令牌；不再使用 # 分账号。
原变量 dlshyzx、dlshyzx_drawid 和每天 09:09 的计划保留。
默认查询昵称与积分并签到。DUREX_SHARE=1 仅在确实分享过活动时上报分享记录；
DUREX_SHARE_ACT_ID 默认沿用上游活动编号，请在小程序核对活动有效性。
DUREX_DRAW=1 明确同意参与抽奖（可能消耗机会或积分），并设置 dlshyzx_drawid。
抽奖编号从本人小程序抽奖请求的 snId 参数获取；不要填写过期示例编号。
DUREX_DRY_RUN=1 完全断网，仅检查配置并模拟阶段，通知也只输出本地预览。
QINGLONG_NOTIFY=0 关闭通知；QINGLONG_NOTIFY_DIR 可指定青龙通知模块目录。
本脚本的分享接口只上报活动记录，不发布文本，因此不调用随机文本提供者。
"""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TITLE = '杜蕾斯会员中心'
DISABLED = {'0', 'false', 'no', 'off'}
USER_AGENT = ('Mozilla/5.0 (Linux; Android 14; 23090RA98C Build/UP1A.231005.007; wv) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile '
              'Safari/537.36 XWEB/1160117 MMWEBSDK/20231202 MMWEBID/1747 '
              'MicroMessenger/8.0.47.2560(0x28002F30) WeChat/arm64 Weixin NetType/WIFI '
              'Language/zh_CN ABI/arm64 MiniProgramEnv/android')

class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def log(message):
    print('[{}] {}'.format(time.strftime('%H:%M:%S'), message), flush=True)


def flag(name, default='0'):
    value = os.environ.get(name, default).strip().lower()
    if value not in {'1', 'true', 'yes', 'on'} | DISABLED:
        raise TaskError('{} 必须为 1 或 0'.format(name))
    return value not in DISABLED


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不向重定向目标转发账号凭据，也不重复变更请求。
        return None


def request(token, path, method='GET', fields=None):
    headers = {'access-token': token, 'content-type': 'application/json;charset=utf-8',
               'platform': 'MP-WEIXIN', 'sid': '10006', 'user-agent': USER_AGENT,
               'referer': 'https://servicewechat.com/wxe11089c85860ec02/30/page-frame.html'}
    url = 'https://vip.ixiliu.cn' + path
    body = None
    if fields:
        encoded = urllib.parse.urlencode(fields)
        if method == 'GET':
            url += '?' + encoded
        else:
            # 保持上游 requests.post(data=...) 的表单编码及原请求头，不臆测新协议。
            body = encoded.encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(131073)
            if len(raw) > 131072:
                raise TaskError('响应超过大小限制')
        result = json.loads(raw)
    except TaskError:
        raise
    except Exception:
        raise TaskError('请求失败或响应无效；请核对网络、活动和凭据') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构不符合契约')
    if type(result.get('status')) is not int or result['status'] != 200:
        if path.endswith('/draw') and result.get('msg') == '今日抽奖次数已用完':
            raise TaskError('今日抽奖次数已用完，未执行成功')
        raise TaskError('业务未确认成功；请在小程序核对登录和活动状态')
    return result


def notify(summary, dry):
    body = ('模式：{mode}；状态：{status}；账号总数：{accounts}；成功：{succeeded}；'
            '失败：{failed}；子任务失败：{steps_failed}').format(**summary)
    if os.environ.get('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        log('⏭️ 通知已关闭')
        return 'disabled'
    if dry:
        log('通知本地预览：' + body)
        return 'dry-run-preview'
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    paths = [Path(d) / 'notify.py' for d in directories if d]
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.insert(0, Path(spec.origin))
    except Exception:
        pass
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        helper = ('import importlib.util,sys; '
                  's=importlib.util.spec_from_file_location("notify",sys.argv[1]); '
                  'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                  'm.send(sys.argv[2],sys.stdin.read())')
        try:
            delivered = subprocess.run([sys.executable, '-c', helper, str(path), TITLE],
                                       input=body, text=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=30)
            if delivered.returncode == 0:
                log('✅ 通知已发送')
                return 'sent'
        except Exception:
            pass
    log('⚠️ 通知模块不可用或发送失败；保留业务退出码')
    return 'unavailable-or-failed'


def main():
    started = time.monotonic()
    start_time = stamp()
    tokens = [line.strip() for line in os.environ.get('dlshyzx', '').splitlines() if line.strip()]
    dry = os.environ.get('DUREX_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(tokens),
               'succeeded': 0, 'failed': 0, 'steps_success': 0, 'steps_failed': 0,
               'steps_skipped': 0, 'steps_already_complete': 0, 'steps_simulated': 0,
               'start_time': start_time, 'account_results': []}
    log('========== {} =========='.format(TITLE))
    log('开始时间：{}；模式：{}；账号数：{}'.format(start_time, summary['mode'], len(tokens)))
    config_error = False
    try:
        dry = flag('DUREX_DRY_RUN')
        share = flag('DUREX_SHARE')
        draw = flag('DUREX_DRAW')
        drawid = os.environ.get('dlshyzx_drawid', '').strip()
        actid = os.environ.get('DUREX_SHARE_ACT_ID', '343766308960192').strip()
        if not tokens:
            raise TaskError('缺少 dlshyzx：请填写每行一个 Access-Token')
        if share and not actid.isdecimal():
            raise TaskError('分享活动编号必须为数字')
        if draw and not drawid.isdecimal():
            raise TaskError('开启抽奖必须设置有效的 dlshyzx_drawid')
    except TaskError as exc:
        config_error = True
        log('❌ 配置错误：' + str(exc))
        summary['failed'] = len(tokens)
    if not config_error:
        for index, token in enumerate(tokens, 1):
            account_start = time.monotonic()
            stats = {'account': index, 'total': 4, 'success': 0, 'failed': 0,
                     'skipped': 0, 'already_complete': 0, 'simulated': 0}
            authenticated = False
            log('---------- 账号 {} ----------'.format(index))
            stages = [('用户信息与积分', True, '/mp/user/info', 'GET', None),
                      ('每日签到', True, '/mp/sign/applyV2', 'GET', None),
                      ('分享记录', share, '/mp/activity.record/share', 'POST',
                       {'act_id': int(actid) if share else 0, 'scene': 20, 'channel_sn': 0}),
                      ('抽奖', draw, '/mp/activity.lottery/draw', 'GET',
                       {'snId': drawid, 'channelSn': '0'})]
            for number, (name, enabled, path, method, fields) in enumerate(stages, 1):
                stage_start = time.monotonic()
                log('阶段 {}/4：{}'.format(number, name))
                try:
                    if not enabled or (number > 1 and not authenticated):
                        stats['skipped'] += 1
                        log('⏭️ 未开启' if not enabled else '⏭️ 用户信息校验失败，停止账号变更')
                    elif dry:
                        stats['simulated'] += 1
                        authenticated = True
                        log('✅ 断网预演通过：{} {}，未发起请求'.format(method, path))
                    else:
                        res = request(token, path, method, fields)
                        if number == 1:
                            data = res.get('data')
                            info = data.get('userInfo') if isinstance(data, dict) else None
                            if not isinstance(info, dict) or 'nick_name' not in info or 'points' not in info:
                                raise TaskError('用户信息缺少昵称或积分字段')
                            if not isinstance(info['nick_name'], str) or type(info['points']) not in (int, float):
                                raise TaskError('昵称或积分字段类型异常')
                            # 仅展示官方非秘密身份；不记录手机、令牌、设备或原始响应。
                            log('✅ 官方昵称：{}；当前积分：{}'.format(info['nick_name'], info['points']))
                            authenticated = True
                        elif number == 4:
                            data = res.get('data')
                            prize = data.get('prize') if isinstance(data, dict) else None
                            if not isinstance(prize, dict) or not isinstance(prize.get('prize_name'), str):
                                raise TaskError('抽奖结果缺少奖品名称，未确认成功')
                            log('✅ 抽奖成功，已确认奖品结果')
                        else:
                            log('✅ {}成功，业务 status=200'.format(name))
                        stats['success'] += 1
                except Exception as exc:
                    stats['failed'] += 1
                    log('❌ ' + (str(exc) if isinstance(exc, TaskError) else '处理失败，响应不符合契约'))
                log('阶段 {} 耗时 {:.2f} 秒'.format(number, time.monotonic() - stage_start))
                if not dry and enabled and authenticated and number in (2, 3):
                    time.sleep(random.uniform(1, 3))
            stats['elapsed_seconds'] = round(time.monotonic() - account_start, 2)
            log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}，预演 {}，耗时 {} 秒'.format(
                index, stats['total'], stats['success'], stats['already_complete'], stats['skipped'],
                stats['failed'], stats['simulated'], stats['elapsed_seconds']))
            summary['account_results'].append(stats)
            summary['failed' if stats['failed'] else 'succeeded'] += 1
            for key in ('success', 'failed', 'skipped', 'already_complete', 'simulated'):
                summary['steps_' + key] += stats[key]
            if not dry and index < len(tokens):
                time.sleep(random.uniform(1, 5))
    exit_code = 1 if config_error or summary['failed'] else 0
    summary['status'] = ('configuration-error' if config_error else
                         'partial-failure' if summary['failed'] and summary['succeeded'] else
                         'failure' if summary['failed'] else 'dry-run' if dry else 'success')
    summary['notification'] = notify(summary, dry)
    summary['finish_time'] = stamp()
    summary['elapsed_seconds'] = round(time.monotonic() - started, 2)
    summary['exit_code'] = exit_code
    log('----------------------------------------')
    log('账号总数 {}，成功 {}，失败 {}；子任务成功 {}，失败 {}，跳过 {}，预演 {}'.format(
        summary['accounts'], summary['succeeded'], summary['failed'], summary['steps_success'],
        summary['steps_failed'], summary['steps_skipped'], summary['steps_simulated']))
    log('完成时间：{}；总耗时 {} 秒；最终状态：{}；通知：{}'.format(
        summary['finish_time'], summary['elapsed_seconds'], summary['status'], summary['notification']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
