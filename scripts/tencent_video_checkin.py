#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 腾讯视频签到
# cron: 45 9 * * *
# new Env('腾讯视频签到')
# 原始来源: deeplee/personal-scripts / tencent_video_checkin.py
# 原始提交: c8c7c0f4fd1802df86c32a86c26b5c26cfef5023
# 许可: MIT。原始脚本未包含单独的版权声明。
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
"""腾讯视频每日签到、观看奖励、积分等级及 VIP 到期查询，纯标准库。
TENCENT_VIDEO_COOKIES：每个非空行一个完整 Cookie；支持 # 开头的注释。
兼容 TENCENT_VIDEO_COOKIE（仅在规范变量为空时使用），保留单账号输入。
浏览器登录腾讯视频，开发者工具网络页找到 vip.video.qq.com 请求，复制
请求头 Cookie。必需非空字段 vqq_openid、vqq_access_token、main_login；
建议保留 vqq_vuserid、vqq_appid、vdevice_qimei36、ip 等原始字段，不伪造。
Cookie 内以分号分隔字段，仅按第一个等号拆分字段，值中的等号原样保留。
TENCENT_VIDEO_DRY_RUN=1：验证配置并预演四项任务，禁止所有网络与外部通知。
QINGLONG_NOTIFY 默认 1；0/false/no/off 关闭所有通知。
青龙通知不可用时兼容 PUSHPLUS_TOKEN、SENDKEY，均为可选敏感凭据。
预演时仍向青龙通知函数提供脱敏总结，但阻断网络和子进程发送。
任何账号的任一步骤失败均非零退出；通知失败不改变业务退出码。
"""
import datetime
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TITLE = '腾讯视频签到'
DISABLED = {'0', 'false', 'no', 'off'}
UA = ('Mozilla/5.0 (Linux; Android 11; M2104K10AC Build/RP1A.200720.011; wv) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/89.0.4389.72 '
      'MQQBrowser/6.2 TBS/046237 Mobile Safari/537.36 QQLiveBrowser/8.7.85.27058')
BASE = 'https://vip.video.qq.com/'
CHECKIN_URL = BASE + 'rpc/trpc.new_task_system.task_system.TaskSystem/CheckIn?rpc_data=%7B%7D'
PROVIDE_URL = BASE + 'rpc/trpc.new_task_system.task_system.TaskSystem/ProvideAward?rpc_data=%7B%22task_id%22%3A1%7D'
SCORE_URL = BASE + 'fcgi-bin/comm_cgi?name=spp_vscore_user_mashup&cmd=&otype=xjson&type=1'
VIPINFO_URL = BASE + 'rpc/trpc.query_vipinfo.vipinfo.QueryVipInfo/GetVipUserInfoH5'
REFERER = ('https://film.video.qq.com/x/vip-center/?entry=common&hidetitlebar=1'
           '&aid=V0%24%241%3A0%242%3A8%243%3A8.7.85.60%244%3A3%245%3A%246%3A%247%3A%248%3A4'
           '%249%3A%2410%3A&isDarkMode=0')
DRY = os.environ.get('TENCENT_VIDEO_DRY_RUN', '').lower().strip() in {'1', 'true', 'yes', 'on'}
SECRETS = []


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def safe(value):
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    for secret in sorted(set(SECRETS), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[敏感值]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号]', text)
    return ''.join(c for c in text if c.isprintable())[:200]


def log(message):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), message), flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向，已阻止凭据转发')


def http_json(url, cookie=None, body=None, content_type='application/json', success_codes=(0, '0')):
    if DRY:
        raise TaskError('预演禁止网络请求')
    headers = {'Accept': 'application/json, text/plain, */*',
               'Accept-Language': 'zh-CN,zh;q=0.9', 'User-Agent': UA,
               'Referer': REFERER, 'Content-Type': content_type}
    if cookie is not None:
        headers['Cookie'] = cookie
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method='POST' if body is not None else 'GET')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(262145)
            if len(raw) > 262144:
                raise TaskError('响应超过限制')
        data = json.loads(raw.decode('utf-8'))
    except TaskError:
        raise
    except Exception:
        raise TaskError('网络、HTTP 或 JSON 解析失败（详情已脱敏）') from None
    if not isinstance(data, dict):
        raise TaskError('响应结构异常')
    # 有业务码时必须成功；不将服务端消息或响应写入日志。
    for key in ('code', 'ret', 'retcode', 'errcode', 'err_code'):
        if key in data and (isinstance(data[key], bool) or data[key] not in success_codes):
            raise TaskError('接口业务码失败')
    return data


def number(value):
    if isinstance(value, bool) or value is None:
        raise TaskError('缺少有效数值结果')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise TaskError('数值结果格式异常') from None
    if not math.isfinite(result) or result < 0:
        raise TaskError('数值结果无效')
    return str(int(result)) if result.is_integer() else str(result)


def identity(data):
    for container in (data, data.get('user_info'), data.get('userinfo')):
        if not isinstance(container, dict):
            continue
        for key in ('nickname', 'nick_name', 'username', 'display_name', 'uid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                log('官方账号身份：%s' % safe(value))
                return


def query_score(cookie):
    data = http_json(SCORE_URL, cookie)
    identity(data)
    parts = []
    for section, key, label in (('lscore_info', 'level', '等级'),
                                ('lscore_info', 'score', 'V力值'),
                                ('cscore_info', 'vip_score_total', '会员积分')):
        obj = data.get(section)
        if isinstance(obj, dict) and key in obj:
            parts.append(label + number(obj[key]))
    if not parts:
        raise TaskError('未返回可核验的积分或等级字段')
    return 'success', ' '.join(parts)


def checkin(cookie):
    data = http_json(CHECKIN_URL, cookie)
    identity(data)
    score = number(data.get('check_in_score'))
    # 仅依据上游提供的明确数值字段判定，不猜测“已签到”业务码。
    return 'success', '签到已核验，获得 %s V力值' % score


def award(cookie):
    data = http_json(PROVIDE_URL, cookie)
    identity(data)
    return 'success', '观看奖励已核验，获得 %s V力值' % number(data.get('provide_value'))


def vipinfo(cookie):
    body = json.dumps({'geticon': 1, 'viptype': 'svip|nfl', 'platform': 8}).encode('utf-8')
    data = http_json(VIPINFO_URL, cookie, body, 'text/plain;charset=UTF-8')
    identity(data)
    end = data.get('endTime')
    if not isinstance(end, (str, int)) or isinstance(end, bool) or not end:
        raise TaskError('未返回有效 VIP 到期时间')
    # 不输出任意远端文本，仅展示符合日期/时间格式的到期字段。
    if not re.fullmatch(r'[0-9TtZz:+ ./-]{1,64}', str(end)):
        raise TaskError('VIP 到期时间格式异常')
    return 'success', 'VIP到期：%s' % safe(end)


def accounts():
    raw = os.environ.get('TENCENT_VIDEO_COOKIES', '').strip()
    if not raw:
        raw = os.environ.get('TENCENT_VIDEO_COOKIE', '').strip()
    return [line.strip().strip("'\"") for line in raw.splitlines()
            if line.strip() and not line.strip().startswith('#')]


def validate(cookie):
    fields = {}
    if any(ord(c) < 32 or ord(c) == 127 for c in cookie):
        raise TaskError('Cookie 含非法控制字符')
    for part in cookie.split(';'):
        if '=' in part:
            key, value = part.strip().split('=', 1)
            fields[key.strip()] = value.strip()
    SECRETS.extend(fields.values())
    missing = [key for key in ('vqq_openid', 'vqq_access_token', 'main_login') if not fields.get(key)]
    if missing:
        raise TaskError('Cookie 缺少非空字段：' + '、'.join(missing))


# 通知在独立子进程执行，限制耗时并丢弃模块输出，防止插件输出敏感值。
NOTIFY_CODE = r'''
import contextlib, importlib.util, json, os, socket, subprocess, sys, urllib.request
p = json.load(sys.stdin)
if p['dry']:
    def deny(*args, **kwargs):
        raise RuntimeError('dry-run: network disabled')
    socket.socket = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    subprocess.Popen = deny
try:
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        if p['path']:
            sys.path.insert(0, os.path.dirname(p['path']))
            spec = importlib.util.spec_from_file_location('notify', p['path'])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            import notify as module
        module.send(p['title'], p['body'])
except BaseException:
    sys.exit(1)
'''


def notify(title, body):
    if os.environ.get('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    paths = [None]
    directory = os.environ.get('QINGLONG_NOTIFY_DIR', '').strip()
    if directory:
        paths.append(os.path.join(directory, 'notify.py'))
    paths.extend(['/ql/data/scripts/notify.py', '/ql/scripts/notify.py'])
    for path in paths:
        if path and not os.path.isfile(path):
            continue
        try:
            result = subprocess.run([sys.executable, '-c', NOTIFY_CODE],
                                    input=json.dumps({'path': path, 'title': title, 'body': body, 'dry': DRY}),
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if result.returncode == 0:
                return '青龙通知（预演禁止联网）' if DRY else '青龙通知'
        except Exception:
            pass
    if DRY:
        return '预演总结已生成；青龙通知不可用或网络发送被阻止'
    js_paths = ([os.path.join(directory, 'sendNotify.js')] if directory else [])
    js_paths.extend(['/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'])
    for path in js_paths:
        if not os.path.isfile(path):
            continue
        try:
            code = "const p=JSON.parse(require('fs').readFileSync(0,'utf8')); Promise.resolve(require(p.path).sendNotify(p.title,p.body)).catch(()=>process.exit(1));"
            result = subprocess.run(['node', '-e', code], input=json.dumps({'path': path, 'title': title, 'body': body}),
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if result.returncode == 0:
                return '青龙通知'
        except Exception:
            pass
    token = os.environ.get('PUSHPLUS_TOKEN', '').strip()
    if token:
        try:
            payload = json.dumps({'token': token, 'title': title, 'content': body}).encode('utf-8')
            data = http_json('https://www.pushplus.plus/send', body=payload, success_codes=(200, '200'))
            if type(data.get('code')) is int and data['code'] == 200:
                return 'PushPlus'
        except TaskError:
            pass
    key = os.environ.get('SENDKEY', '').strip()
    if key:
        try:
            payload = urllib.parse.urlencode({'title': title, 'desp': body}).encode('utf-8')
            data = http_json('https://sctapi.ftqq.com/%s.send' % urllib.parse.quote(key, safe=''),
                             body=payload, content_type='application/x-www-form-urlencoded')
            if data.get('code') in (0, '0') and not isinstance(data.get('code'), bool):
                return 'Server酱'
        except TaskError:
            pass
    return '无可用通知渠道或通知失败（业务退出码不变）'


def main():
    started, start_clock = now(), time.monotonic()
    items = accounts()
    SECRETS.extend(items)
    SECRETS.extend(os.environ.get(key, '') for key in ('PUSHPLUS_TOKEN', 'SENDKEY'))
    log('=' * 50)
    log(TITLE + ' | 开始时间：' + started)
    log('运行模式：%s | 账号数：%d' % ('断网预演' if DRY else '实际执行', len(items)))
    totals = dict(total=0, success=0, alreadyComplete=0, skipped=0, failure=0)
    results = []
    tasks = [('积分与等级查询', query_score), ('每日签到', checkin),
             ('领取每日观看奖励', award), ('VIP 到期查询', vipinfo)]
    for index, cookie in enumerate(items, 1):
        began = time.monotonic()
        stats = dict(total=4, success=0, alreadyComplete=0, skipped=0, failure=0)
        log('账号%d 开始' % index)
        try:
            validate(cookie)
        except TaskError as error:
            stats['failure'], stats['skipped'] = 1, 3
            log('账号%d 阶段0 配置校验 ❌ %s | 耗时 %.2f秒' % (index, error, time.monotonic() - began))
        else:
            for stage, (name, action) in enumerate(tasks, 1):
                clock = time.monotonic()
                log('账号%d 阶段%d %s 开始' % (index, stage, name))
                try:
                    if DRY:
                        status, message = 'skipped', 'DRY_RUN_OK：配置有效，仅预演；未请求或改变账号状态'
                    else:
                        status, message = action(cookie)
                except TaskError as error:
                    status, message = 'failure', str(error)
                except Exception:
                    status, message = 'failure', '执行异常（详情已脱敏）'
                stats[status] += 1
                log('账号%d 阶段%d %s %s %s | 耗时 %.2f秒' %
                    (index, stage, name, {'success': '✅', 'skipped': '⏭️', 'failure': '❌'}[status],
                     message, time.monotonic() - clock))
                if not DRY and stage < len(tasks):
                    time.sleep(1)
        elapsed = round(time.monotonic() - began, 3)
        for key in totals:
            totals[key] += stats[key]
        results.append({'account': index, 'ok': stats['failure'] == 0, 'tasks': stats, 'elapsedSeconds': elapsed})
        log('账号%d 统计：总任务%d 成功%d 已完成%d 跳过%d 失败%d | 耗时 %.2f秒' %
            (index, stats['total'], stats['success'], stats['alreadyComplete'], stats['skipped'], stats['failure'], elapsed))
    success = sum(item['ok'] for item in results)
    failure = len(items) - success
    status = ('configuration-error' if not items else 'partial-failure' if failure and success else
              'failure' if failure else 'dry-run' if DRY else 'success')
    exit_code = 1 if not items or failure else 0
    if not items:
        log('❌ 未配置账号；请设置 TENCENT_VIDEO_COOKIES，每行一个完整 Cookie')
    body = ('状态：%s\n账号总数：%d，成功：%d，失败：%d\n'
            '子任务总数：%d，成功：%d，已完成：%d，跳过：%d，失败：%d\n%s' %
            (status, len(items), success, failure, totals['total'], totals['success'],
             totals['alreadyComplete'], totals['skipped'], totals['failure'],
             '预演成功仅表示本地配置检查通过，不代表真实业务成功。' if DRY else '仅按接口明确结果核验。'))
    delivery = notify(TITLE, body)
    finished = now()
    summary = {'task': TITLE, 'mode': 'dry-run' if DRY else 'live', 'status': status,
               'accounts': {'total': len(items), 'success': success, 'failure': failure},
               'tasks': totals, 'results': results, 'startedAt': started, 'finishedAt': finished,
               'elapsedSeconds': round(time.monotonic() - start_clock, 3),
               'notification': delivery, 'exitCode': exit_code}
    log('-' * 50)
    for line in body.splitlines():
        log(line)
    log('通知状态：' + delivery)
    log('完成时间：%s | 总耗时 %.2f秒 | 最终状态：%s' % (finished, summary['elapsedSeconds'], status))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
