#!/usr/bin/env python3
# name: 全民K歌签到与奖励
# cron: 0 9 * * *
# SPDX-License-Identifier: MIT
# 来源：Sitoi/dailycheckin dailycheckin/kgqq/main.py
# 上游提交：135cc236e59ac4f14bcddc44acb3cbb3ed6010b5
# Copyright (c) Sitoi
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
"""独立全民K歌账号任务，配置说明见同目录 contract.json。
KGQQ_COOKIE 每行完整 Cookie，须含 uid；Cookie 内分号及等号原样保留。
抽奖、音乐奖励需显式开启，音乐奖励须提供同账号实际 g_tk_openkey，禁止枚举。
开启音乐奖励时每行使用 Cookie|g_tk_openkey，只在第一个 | 处分割。
"""
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

URLS = {'proto_profile_url': 'https://node.kg.qq.com/webapp/proxy?ns=proto_profile&cmd=profile.getProfile&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnByb2ZpbGVfd2ViYXBwSmNlJTIyJTJDJTIyY21kTmFtZSUyMiUzQSUyMlByb2ZpbGVHZXQlMjIlMkMlMjJhcHBpZCUyMiUzQTEwMDA2MjYlMkMlMjJkY2FwaSUyMiUzQSU3QiUyMmludGVyZmFjZUlkJTIyJTNBMjA1MzU5NTk3JTdEJTJDJTIybDVhcGklMjIlM0ElN0IlMjJtb2RpZCUyMiUzQTI5NDAxNyUyQyUyMmNtZCUyMiUzQTI2MjE0NCU3RCUyQyUyMmlwJTIyJTNBJTIyMTAwLjExMy4xNjIuMTc4JTIyJTJDJTIycG9ydCUyMiUzQSUyMjEyNDA2JTIyJTdE&t_uUid=__UID__', 'url_list': ['https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.getLottery&ns_inbuf=&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVyeVJlcSUyMiUyQyUyMnduc0NvbmZpZyUyMiUzQSU3QiUyMmFwcGlkJTIyJTNBMTAwMDU1NyU3RCUyQyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQlMjIlM0E1ODk4MjQlN0QlN0Q%3D&t_uid=__UID__&t_iShowEntry=1&t_type=1', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.getLottery&ns_inbuf=&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVyeVJlcSUyMiUyQyUyMnduc0NvbmZpZyUyMiUzQSU3QiUyMmFwcGlkJTIyJTNBMTAwMDU1NyU3RCUyQyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQlMjIlM0E1ODk4MjQlN0QlN0Q%3D&t_uid=__UID__&t_iShowEntry=1&t_type=2', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=1', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=2', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=4', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=16', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=128', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.signinGetAward&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyR2V0U2lnbkluQXdhcmRSZXElMjIlMkMlMjJ3bnNDb25maWclMjIlM0ElN0IlMjJhcHBpZCUyMiUzQTEwMDA2MjYlN0QlMkMlMjJsNWFwaSUyMiUzQSU3QiUyMm1vZGlkJTIyJTNBNTAzOTM3JTJDJTIyY21kJTIyJTNBNTg5ODI0JTdEJTdE&t_uid=__UID__&t_iShowEntry=512', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.getLottery&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVyeVJlcSUyMiUyQyUyMnduc0NvbmZpZyUyMiUzQSU3QiUyMmFwcGlkJTIyJTNBMTAwMDU1NyU3RCUyQyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQlMjIlM0E1ODk4MjQlN0QlN0Q&t_uid=__UID__&t_iShowEntry=4&t_type=104', 'https://node.kg.qq.com/webapp/proxy?ns=KG_TASK&cmd=task.getLottery&mapExt=JTdCJTIyZmlsZSUyMiUzQSUyMnRhc2tKY2UlMjIlMkMlMjJjbWROYW1lJTIyJTNBJTIyTG90dGVyeVJlcSUyMiUyQyUyMmw1YXBpJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E1MDM5MzclMkMlMjJjbWQlMjIlM0E1ODk4MjQlN0QlMkMlMjJsNWFwaV9leHAxJTIyJTNBJTdCJTIybW9kaWQlMjIlM0E4MTcwODklMkMlMjJjbWQlMjIlM0EzODAxMDg4JTdEJTdE&t_uid=__UID__&t_type=103'], 'proto_music_station_url': 'https://node.kg.qq.com/webapp/proxy?ns=proto_music_station&cmd=message.batch_get_music_cards&mapExt=JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldEJhdGNoTXVzaWNDYXJkc1JlcSUyMiUyQyUyMmZpbGUlMjIlM0ElMjJwcm90b19tdXNpY19zdGF0aW9uSmNlJTIyJTJDJTIyd25zRGlzcGF0Y2hlciUyMiUzQXRydWUlN0Q&t_uUid=__UID__&g_tk_openkey=', 'url_10': 'https://node.kg.qq.com/webapp/proxy?t_stReward%3Aobject=%7B%22uInteractiveType%22%3A1%2C%22uRewardType%22%3A0%2C%22uFlowerNum%22%3A15%7D&ns=proto_music_station&cmd=message.get_reward&mapExt=JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldFJld2FyZFJlcSUyMiUyQyUyMmZpbGUlMjIlM0ElMjJwcm90b19tdXNpY19zdGF0aW9uSmNlJTIyJTJDJTIyd25zRGlzcGF0Y2hlciUyMiUzQXRydWUlN0Q&t_uUid=__UID__&t_strUgcId=', 'url_15': 'https://node.kg.qq.com/webapp/proxy?t_stReward%3Aobject=%7B%22uInteractiveType%22%3A0%2C%22uRewardType%22%3A0%2C%22uFlowerNum%22%3A10%7D&ns=proto_music_station&cmd=message.get_reward&mapExt=JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldFJld2FyZFJlcSUyMiUyQyUyMmZpbGUlMjIlM0ElMjJwcm90b19tdXNpY19zdGF0aW9uSmNlJTIyJTJDJTIyd25zRGlzcGF0Y2hlciUyMiUzQXRydWUlN0Q&t_uUid=__UID__&t_strUgcId=', 'getinfourl': 'https://node.kg.qq.com/webapp/proxy?ns=proto_vip_webapp&cmd=vip.get_vip_info&t_uUid=__UID__&t_uWebReq=1&t_uGetDataFromC4B=1', 'vipurl': 'https://node.kg.qq.com/webapp/proxy?t_uUid=__UID__&ns=proto_vip_webapp&cmd=vip.get_vip_day_reward&ns_inbuf=&nocache=1613719349184&mapExt=JTdCJTIyY21kTmFtZSUyMiUzQSUyMkdldFZpcERheVJld2FyZCUyMiU3RA%3D%3D&g_tk_openkey=642424811'}
TITLE = '全民K歌签到与奖励'
FALSE_VALUES = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def enabled(name, default='0'):
    value = os.getenv(name, default).strip().lower()
    if value not in FALSE_VALUES | {'1', 'true', 'yes', 'on'}:
        raise TaskError('开关配置无效：' + name)
    return value not in FALSE_VALUES


def log(message):
    print(f'[{datetime.datetime.now():%H:%M:%S}] {message}', flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向被拒绝')


def request(url, cookie, command):
    # 每个请求独立；不持久化 Cookie，不向其他主机转发凭据。
    if urllib.parse.urlsplit(url).netloc != 'node.kg.qq.com':
        raise TaskError('接口主机不匹配')
    req = urllib.request.Request(url, headers={'Cookie': cookie, 'User-Agent': 'Mozilla/5.0'})
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise TaskError('接口响应过大')
        data = json.loads(raw)
    except TaskError:
        raise
    except Exception:
        raise TaskError('请求失败或响应不是有效 JSON') from None
    if not isinstance(data, dict) or type(data.get('code')) is not int or data['code'] != 0:
        raise TaskError('接口未明确返回成功业务码')
    payload = data.get('data')
    if not isinstance(payload, dict) or not isinstance(payload.get(command), dict):
        raise TaskError('接口业务字段缺失')
    payload = payload[command]
    for key in ('code', 'ret', 'iRet', 'iResult', 'result'):
        if key in payload and (type(payload[key]) is not int or payload[key] != 0):
            raise TaskError('子业务未明确返回成功')
    return payload


def parse_account(line, music):
    cookie, delimiter, token = line.partition('|')
    cookie = cookie.strip()
    if not cookie or any(ord(c) < 32 for c in cookie):
        raise TaskError('Cookie 为空或含控制字符')
    fields = {}
    for field in cookie.split(';'):
        key, sep, value = field.strip().partition('=')
        if sep:
            fields[key] = value
    uid = fields.get('uid', '')
    if not re.fullmatch(r'[0-9]+', uid):
        raise TaskError('Cookie 须包含数字 uid 字段')
    token = token.strip()
    if music and (not delimiter or not re.fullmatch(r'[0-9]+', token)):
        raise TaskError('音乐奖励需同账号真实 g_tk_openkey，使用 Cookie|g_tk_openkey')
    return cookie, uid, token


def url_for(name, uid):
    return URLS[name].replace('__UID__', urllib.parse.quote(uid, safe=''))


def profile(cookie, uid):
    data = request(url_for('proto_profile_url', uid), cookie, 'profile.getProfile')
    number = data.get('uFlowerNum')
    person = data.get('stPersonInfo')
    if type(number) is not int or number < 0 or not isinstance(person, dict):
        raise TaskError('账号资料字段无效')
    nickname = person.get('sKgNick')
    if not isinstance(nickname, str) or not nickname.strip() or any(ord(c) < 32 for c in nickname):
        raise TaskError('账号昵称字段无效')
    return number, nickname


def run_account(index, line, dry, lottery, music):
    started = time.monotonic()
    stats = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    def stage(label, action):
        stats['total'] += 1
        tick = time.monotonic()
        log(f'账号 {index} 阶段 {stats["total"]}：{label}')
        try:
            if dry:
                log(f'⏭️ 断网预演：仅验证配置与执行计划，耗时 {time.monotonic() - tick:.2f} 秒')
                stats['skipped'] += 1
                return None
            result = action()
            stats['success'] += 1
            log(f'✅ {label}：业务成功，耗时 {time.monotonic() - tick:.2f} 秒')
            return result
        except Exception as exc:
            stats['failed'] += 1
            # 仅本脚本固定错误文案可以进入日志。
            message = str(exc) if isinstance(exc, TaskError) else '处理失败：业务字段异常'
            log(f'❌ {label}：{message}，耗时 {time.monotonic() - tick:.2f} 秒')
            return None
    try:
        cookie, uid, token = parse_account(line, music)
    except TaskError as exc:
        stats.update(total=1, failed=1)
        log(f'账号 {index} 阶段 1：配置检查失败：{exc}，耗时 {time.monotonic() - started:.2f} 秒')
    else:
        before = stage('读取昵称和鲜花余额', lambda: profile(cookie, uid))
        if before:
            log(f'账号 {index} 昵称：{before[1]}；当前鲜花：{before[0]}')
        if dry or before:
            urls = URLS['url_list']
            for position, template in enumerate(urls):
                is_lottery = position < 2 or position >= 8
                label = ('抽奖' if is_lottery else '签到奖励') + f'入口 {position + 1}'
                if is_lottery and not lottery:
                    stats['total'] += 1
                    stats['skipped'] += 1
                    log(f'账号 {index} 阶段 {stats["total"]}：⏭️ {label}未开启，耗时 0.00 秒')
                    continue
                command = 'task.getLottery' if is_lottery else 'task.signinGetAward'
                stage(label, lambda t=template, c=command: request(t.replace('__UID__', uid), cookie, c))
            if music:
                def music_rewards():
                    cards = request(url_for('proto_music_station_url', uid) + token, cookie,
                                    'message.batch_get_music_cards').get('vctMusicCards')
                    if not isinstance(cards, list) or not cards:
                        raise TaskError('音乐卡片缺失，未领取奖励')
                    selected = max(cards, key=lambda card: card['stReward']['uFlowerNum'])
                    reward = selected['stReward']['uFlowerNum']
                    if type(reward) is not int:
                        raise TaskError('音乐奖励字段异常')
                    name = 'url_10' if reward > 10 else 'url_15' if 1 < reward < 10 else None
                    if name is None:
                        raise TaskError('没有上游支持的音乐奖励档位')
                    ugc, key = selected['strUgcId'], selected['strKey']
                    if not isinstance(ugc, str) or not ugc or not isinstance(key, str) or not key:
                        raise TaskError('音乐奖励领取参数缺失')
                    url = url_for(name, uid) + urllib.parse.quote(ugc, safe='')
                    url += '&t_strKey=' + urllib.parse.quote(key, safe='')
                    return request(url, cookie, 'message.get_reward')
                stage('读取音乐卡片并领取最高档奖励', music_rewards)
            else:
                stats['total'] += 1
                stats['skipped'] += 1
                log(f'账号 {index} 阶段 {stats["total"]}：⏭️ 音乐奖励未开启，耗时 0.00 秒')
            vip = stage('查询 VIP 状态', lambda: request(url_for('getinfourl', uid), cookie, 'vip.get_vip_info'))
            status = None
            if vip is not None:
                core = vip.get('stVipCoreInfo')
                status = core.get('uStatus') if isinstance(core, dict) else None
                if type(status) is not int:
                    stats['failed'] += 1
                    stats['success'] -= 1
                    log('❌ VIP 状态字段缺失')
            if dry or status == 1:
                def vip_reward():
                    data = request(url_for('vipurl', uid), cookie, 'vip.get_vip_day_reward')
                    amount = data.get('uCurRewardNum')
                    if type(amount) is not int or amount < 0 or not isinstance(data.get('strTips'), str):
                        raise TaskError('VIP 奖励结果字段缺失')
                    log(f'VIP 福利道具：{amount} 个')
                    return data
                stage('领取 VIP 日奖励', vip_reward)
            elif type(status) is int:
                stats['total'] += 1
                stats['skipped'] += 1
                log(f'账号 {index} 阶段 {stats["total"]}：⏭️ 非 VIP 用户，耗时 0.00 秒')
            after = stage('核对最终鲜花余额', lambda: profile(cookie, uid))
            if before and after:
                log(f'账号 {index} 昵称：{after[1]}；获取鲜花：{after[0] - before[0]}；当前鲜花：{after[0]}')
    stats['elapsedSeconds'] = round(time.monotonic() - started, 2)
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["elapsedSeconds"]} 秒')
    return stats


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in FALSE_VALUES:
        return '已关闭'
    if dry:
        log('通知预演：' + body)
        return '断网预演未发送'
    # 通知在独立进程中执行，清除业务凭据，设置最长执行时间。
    script = '''import importlib.util, pathlib, sys
path = sys.argv[1]
if path:
    sys.path.insert(0, str(pathlib.Path(path).parent))
    spec = importlib.util.spec_from_file_location("notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    import notify as module
module.send(sys.argv[2], sys.argv[3])
'''
    clean_env = {k: v for k, v in os.environ.items() if k not in {'KGQQ_COOKIE', 'KGQQ_COOKIES'}}
    folder = os.getenv('QINGLONG_NOTIFY_DIR', '')
    roots = ([pathlib.Path(folder)] if folder else []) + [pathlib.Path('/ql/data/scripts'), pathlib.Path('/ql/scripts')]
    candidates = [('python', '')]
    candidates += [('python', str(p / 'notify.py')) for p in roots if (p / 'notify.py').is_file()]
    candidates += [('javascript', str(p / 'sendNotify.js')) for p in roots if (p / 'sendNotify.js').is_file()]
    for runtime, path in candidates:
        if runtime == 'python':
            command = [sys.executable, '-c', script, path, TITLE, body]
        else:
            command = ['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2], process.argv[3])).catch(()=>process.exit(1))', path, TITLE, body]
        try:
            result = subprocess.run(command, env=clean_env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except Exception:
            pass
    log('⚠️ 通知模块不可用或发送失败，保留业务退出码')
    return '发送失败'


def main():
    start = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.datetime.now().isoformat(timespec="seconds")}')
    lines = [line.strip() for line in (os.getenv('KGQQ_COOKIE') or os.getenv('KGQQ_COOKIES', '')).splitlines() if line.strip()]
    results = []
    configuration_error = False
    dry = False
    log('运行模式：' + ('断网预演' if os.getenv('KGQQ_DRY_RUN', '').strip().lower() in {'1', 'true', 'yes', 'on'} else '正式执行或待校验配置'))
    log(f'账号数量：{len(lines)}')
    try:
        dry = enabled('KGQQ_DRY_RUN')
        lottery = enabled('KGQQ_LOTTERY')
        music = enabled('KGQQ_MUSIC_REWARDS')
        if not lines:
            raise TaskError('缺少 KGQQ_COOKIE：每行一个完整 Cookie')
        for index, line in enumerate(lines, 1):
            results.append(run_account(index, line, dry, lottery, music))
    except TaskError as exc:
        configuration_error = True
        log('❌ 配置错误：' + str(exc))
    failed = sum(r['failed'] > 0 for r in results)
    succeeded = len(results) - failed
    exit_code = int(configuration_error or failed > 0)
    status = 'configuration-error' if configuration_error else 'partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if dry else 'success'
    body = f'状态：{status}；账号总数 {len(lines)}，成功 {succeeded if not dry else 0}，失败 {failed}，预演通过 {succeeded if dry else 0}，配置错误 {int(configuration_error)}'
    delivery = notify(body, dry or os.getenv('KGQQ_DRY_RUN', '').strip().lower() not in FALSE_VALUES | {''})
    log('----------------------------------------')
    log(body)
    totals = {key: sum(r[key] for r in results) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'总耗时：{time.monotonic() - start:.2f} 秒；通知：{delivery}')
    log(f'完成时间：{datetime.datetime.now().isoformat(timespec="seconds")}；最终状态：{status}')
    summary = {'status': status, 'accounts': len(lines), 'success': succeeded if not dry else 0,
               'failed': failed, 'dryRunPassed': succeeded if dry else 0,
               'configurationError': configuration_error, 'tasks': totals,
               'notification': delivery, 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
