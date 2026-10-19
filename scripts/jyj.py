#!/usr/bin/env python3
# name: 劲友家日常任务
# cron: 12 2 * * *
# SPDX-License-Identifier: MIT
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
# 上游：Rookie-wb-WH/ql_scripts，jingyoujia/jyj.py
# commit: 08e5c06461c4a0112ea3735f48fe671734bb7707
"""劲友家（微信小程序）独立维护版。

参数获取：进入小程序及页面活动，使用本人授权的抓包工具查看
https://jjw.jingjiu.com/app-jingyoujia/app/jingyoujia/promoteCode/scanUserPromoteCode
请求头 authorization 与请求体 userid。jyjck 每个非空行填写 authorization#userid，
只在第一个 # 分割；不再用 @@ 分隔账号。不要分享抓包内容。
jyjlatlon 沿用原执行代码的顺序：纬度#经度（原说明文字顺序有误）；
从本人小程序请求中获取真实位置，不使用内置或伪造坐标。
青龙 Python 依赖管理添加 pycryptodome；不限定 Python 3.10。

JYJ_TASKS 逗号分隔动作，默认 sign,daily-water。可用：
info,sign,beat,turntable,like,subscribe,survey,share,run,garden,daily-water,
photo,photo-query,health-draw,red-rain,herb-game。
jyjRun=1 显式开启健康运动任务（默认关闭）。like/subscribe/survey/share
改变互动或任务记录，必须显式选入；run 仅限本人已完成运动后开启。
garden 需 JYJ_PLANT_TYPE（查询接口内的 medicineType）、JYJ_WATER_LIMIT
（0..100，默认0），不会随机种植或默认消耗水滴。
photo/red-rain/health-draw 为 MOUNTAIN_CLIMBING_2024 独立活动，默认关闭，
需确认活动仍开放；photo 需 JYJ_PHOTO_PATH 指向本人真实照片。
herb-game 需 JYJ_HERB_SCORE 填写本人本次实际游戏成绩，不生成成绩。
beat 记录脚本实际经过的秒数，不伪造拍一拍成绩。turntable 最多3次，
herb-game 每轮1次；任何业务失败均失败闭合，不推断为已完成。
JYJ_DRY_RUN=1 完全断网，仅验证参数和计划；不会验证真实业务。
QINGLONG_NOTIFY 未设置时按上架状态，设0关闭；预演只调用本地通知适配器且阻断网络。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
if "QINGLONG_NOTIFY" not in _ql_notify_os.environ:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('d484be6cd2a617db', 'scripts/jyj.py', 'jyj.py', 'jyj')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://jjw.jingjiu.com/app-jingyoujia/'
OFF = {'0', 'false', 'no', 'off'}
ACTIONS = {'info', 'sign', 'beat', 'turntable', 'like', 'subscribe', 'survey',
           'share', 'run', 'garden', 'daily-water', 'photo', 'photo-query',
           'health-draw', 'red-rain', 'herb-game'}

class TaskError(Exception):
    pass

def log(text):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), text), flush=True)

def request(url, method='GET', headers=None, body=None, expected=200):
    if os.getenv('JYJ_DRY_RUN', '0').lower() not in OFF:
        raise TaskError('预演禁止网络请求')
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    # 禁止重定向，避免凭据被转发至其他主机；不自动重试状态变更。
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as res:
            if res.status != expected:
                raise TaskError('HTTP状态不符合接口契约')
            data = res.read(1048577)
            if len(data) > 1048576:
                raise TaskError('响应过大')
    except urllib.error.HTTPError as exc:
        raise TaskError('HTTP请求失败（状态%d）' % exc.code) from None
    except (OSError, ValueError):
        raise TaskError('网络请求失败或超时') from None
    if expected == 204:
        return None
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效JSON') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构发生变化')
    return result

def encrypt(data):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        raise TaskError('缺少公开依赖 pycryptodome') from None
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    # 上游业务协议中的公开固定密钥，不是账号凭据。
    cipher = AES.new(b'Z0J7M480h6kppf67', AES.MODE_ECB)
    return {'v1': base64.b64encode(cipher.encrypt(pad(raw, 16))).decode()}

class Client:
    def __init__(self, token, uid, coords):
        self.uid = uid
        self.coords = coords
        self.headers = {'appid': 'wx10bc773e0851aedd', 'authorization': token,
                        'Content-Type': 'application/json', 'charset': 'utf-8',
                        'Referer': 'https://servicewechat.com/wx10bc773e0851aedd/544/page-frame.html',
                        'User-Agent': 'Mozilla/5.0 MicroMessenger/8.0.49 MiniProgramEnv/android'}
    def api(self, path, data=None, encrypted=True):
        body = None if data is None else json.dumps(encrypt(data) if encrypted else data).encode()
        res = request(BASE + path, 'GET' if data is None else 'POST', self.headers, body)
        # 上游成功码为整数200；空data或失败码不能视为今日已完成。
        if type(res.get('code')) is not int or res['code'] != 200:
            raise TaskError('业务未返回成功码200；请在小程序核对状态')
        return res
    def loc(self):
        if self.coords is None:
            raise TaskError('此动作需要 jyjlatlon 真实纬度#经度')
        return {'lat': self.coords[0], 'lon': self.coords[1]}
    def activity(self):
        loc = self.loc()
        return {'activityType': 'MOUNTAIN_CLIMBING_2024',
                'latitude': float(loc['lat']), 'longitude': float(loc['lon'])}
    def info(self):
        data = self.api('app/jingyoujia/customer/detail').get('data')
        if not isinstance(data, dict):
            raise TaskError('账号详情结构不符')
        if isinstance(data.get('nickName'), str) and data['nickName']:
            # 官方昵称直接显示，移除换行防止伪造日志，不输出mobile等字段。
            log('官方昵称：' + data['nickName'].replace('\n', ' ').replace('\r', ' '))
        totals = self.api('app/jingyoujia/customer/queryIntegralLog').get('data')
        if not isinstance(totals, dict) or any(type(totals.get(k)) not in (int, float) for k in
                ('totalIntegral', 'totalDelIntegral', 'totalIncIntegral')):
            raise TaskError('积分统计结构不符')
        log('积分：可用%s，历史使用%s，历史总数%s' % tuple(totals[k] for k in
            ('totalIntegral', 'totalDelIntegral', 'totalIncIntegral')))
    def do(self, action):
        root = 'app/jingyoujia/'
        if action == 'info':
            return self.info()
        if action == 'sign':
            data = self.api(root + 'taskContinuousRecord', {'taskId': 5}).get('data')
            if not isinstance(data, dict) or type(data.get('integral')) not in (int, float):
                raise TaskError('签到积分结果结构不符')
            log('签到积分：%s' % data['integral'])
        elif action in {'subscribe', 'survey', 'run', 'share', 'daily-water'}:
            paths = {'subscribe': 'task/subscribe', 'survey': 'task/doSurvey', 'run': 'task/run',
                     'share': 'extend/share', 'daily-water': 'user/everyDayWater'}
            res = self.api(root + 'game/' + paths[action], self.loc())
            data = res.get('data')
            if action == 'daily-water':
                if type(data) not in (int, float) or data <= 0:
                    raise TaskError('未确认领取到每日水滴')
                log('领取水滴：%s' % data)
            elif data is not True and not (action == 'run' and type(data) in (int, float) and data > 0):
                raise TaskError('接口未确认本次任务完成')
        elif action == 'like':
            res = self.api('app/ugcExcellent/queryUgcExcellentTopicList?pageNum=1&pageSize=10')
            rows = res.get('rows')
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict) or not rows[0].get('topicId'):
                raise TaskError('未获取到有效文章；不使用过期内置文章')
            res = self.api(root + 'ugc/sendTopicLike', {'invokeType': 1, 'topicId': rows[0]['topicId']}, False)
            data = res.get('data')
            if not isinstance(data, dict) or data.get('water') is not True:
                raise TaskError('未确认点赞获取水滴')
            if type(data.get('waterNum')) not in (int, float):
                raise TaskError('点赞水滴数量字段缺失')
            log('点赞领取水滴：%s' % data['waterNum'])
        elif action == 'turntable':
            for n in range(3):
                data = self.api(root + 'taskHallTurntable/extractTurntableGoods', {'activityId': 3}).get('data')
                if not isinstance(data, dict) or not data.get('awardName'):
                    raise TaskError('未确认转盘结果')
                log('转盘第%d次：已确认奖品结果' % (n + 1))
                if n < 2:
                    time.sleep(10)
        elif action == 'beat':
            for n in range(3):
                record = self.api(root + 'beatSecondConfig/starGame', {'gameId': 1}).get('data')
                if isinstance(record, bool) or not isinstance(record, (str, int)) or not record:
                    raise TaskError('未获取有效游戏记录')
                start = time.monotonic()
                time.sleep(5)
                score = round(time.monotonic() - start, 2)
                data = self.api(root + 'beatSecondConfig/endGame', {'beatTime': score, 'recordId': record}).get('data')
                if not isinstance(data, dict) or type(data.get('integral')) not in (int, float):
                    raise TaskError('拍一拍积分结果结构不符')
                log('拍一拍第%d次：实际计时完成，积分%s' % (n + 1, data['integral']))
                time.sleep(2)
        elif action == 'garden':
            self.garden()
        elif action == 'photo-query':
            self.api('business/jingfan/queryFinishPhotoTimes')
        elif action in {'health-draw', 'red-rain'}:
            data = self.activity()
            if action == 'red-rain':
                data['click'] = True
            path = 'business/Mountain/healthFestivalCardDraw' if action == 'health-draw' else 'business/spring2024/redDraw'
            res = self.api(path, data).get('data')
            if not isinstance(res, dict) or not res.get('awardName'):
                raise TaskError('未确认活动抽奖结果')
        elif action == 'herb-game':
            score = int(os.environ['JYJ_HERB_SCORE'])
            game_id = self.api(root + 'game/extend/playStart', self.loc()).get('data')
            if isinstance(game_id, bool) or not isinstance(game_id, (str, int)) or not game_id:
                raise TaskError('未获取有效游戏记录')
            time.sleep(15)
            data = dict(self.loc(), id=game_id, score=score)
            res = self.api(root + 'game/extend/playEnd', data).get('data')
            if not isinstance(res, dict) or not isinstance(res.get('award'), dict) or not res['award'].get('awardName'):
                raise TaskError('未确认药材游戏结果')
        elif action == 'photo':
            self.photo()
    def garden(self):
        root = 'app/jingyoujia/game/'
        current = self.api(root + 'currentGrowMedicine')
        if 'data' not in current:
            raise TaskError('种植状态字段缺失')
        if not current['data']:
            choice = os.getenv('JYJ_PLANT_TYPE', '')
            if choice:
                rows = self.api(root + 'medicineType').get('data')
                if not isinstance(rows, list) or not any(isinstance(r, dict) and
                        str(r.get('medicineType')) == choice and r.get('use') is True and
                        not r.get('alreadyPlant') for r in rows):
                    raise TaskError('指定药材未被接口确认为可种植')
                self.api(root + 'plantMedicine', dict(self.loc(), medicineType=int(choice)))
            else:
                log('⏭️ 未种植且未指定药材；不自动种植')
                return
        for n in range(int(os.getenv('JYJ_WATER_LIMIT', '0'))):
            data = self.api(root + 'water', self.loc()).get('data')
            if not isinstance(data, dict) or type(data.get('surplusWaterNum')) not in (int, float):
                raise TaskError('浇水结果结构不符')
            log('浇水第%d次：下一阶段还需%s克' % (n + 1, data['surplusWaterNum']))
            time.sleep(3)
    def photo(self):
        image = Path(os.environ['JYJ_PHOTO_PATH']).read_bytes()
        if not image or len(image) > 10 * 1024 * 1024:
            raise TaskError('照片为空或超过10MB')
        if not image.startswith(b'\xff\xd8\xff'):
            raise TaskError('照片不是JPEG，拒绝上传其他文件内容')
        filename = 'jingyoujia/' + datetime.datetime.now().strftime('%Y/%m/%d/') + uuid.uuid4().hex + '.jpg'
        data = self.api('system/oss/preSignedUrlV2', {'fileName': filename, 'method': 'POST'}, False).get('data')
        if not isinstance(data, dict) or not isinstance(data.get('formFields'), dict):
            raise TaskError('上传授权结构不符')
        fields = data['formFields']
        upload = str(data.get('v2UploadUrl', '')).rstrip('/') + '/' + str(data.get('v2Bucket', ''))
        cdn = str(data.get('v2CDNUrl', '')).rstrip('/') + '/' + str(fields.get('key', ''))
        for url in (upload, cdn):
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != 'https' or parts.username or parts.password or not parts.hostname or not (
                    parts.hostname.endswith('.ctyunxs.cn') or parts.hostname.endswith('.jingjiu.com')):
                raise TaskError('上传服务域名不符合上游契约')
        boundary = 'JYJ' + uuid.uuid4().hex
        pieces = []
        mapping = {'key': fields.get('key'), 'bucket': data.get('v2Bucket'),
                   'X-Amz-Algorithm': fields.get('x-amz-algorithm'),
                   'X-Amz-Credential': fields.get('x-amz-credential'), 'X-Amz-Date': fields.get('x-amz-date'),
                   'X-Amz-Signature': fields.get('x-amz-signature'), 'Policy': fields.get('Policy'), 'acl': fields.get('acl')}
        for key, value in mapping.items():
            if not isinstance(value, str) or not value:
                raise TaskError('上传授权字段缺失')
            pieces.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n' + value + '\r\n').encode())
        pieces.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="Sign.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode() + image + ('\r\n--' + boundary + '--\r\n').encode())
        request(upload, 'POST', {'Content-Type': 'multipart/form-data; boundary=' + boundary}, b''.join(pieces), 204)
        self.api('app/img/ai/recognition', {'recognitionUrl': cdn}, False)
        self.api('app/jingyoujia/activityCommon/photoPunch', dict(self.activity(), recordUrl=cdn, code=self.uid), False)
        self.api('business/jingfan/queryFinishPhotoTimes')

def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in OFF:
        return '已关闭'
    body = '模式：%s；账号总数：%d；成功：%d；失败：%d；状态：%s' % (
        summary['mode'], summary['accounts'], summary['success'], summary['failed'], summary['status'])
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path(__file__).resolve().parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    runner = '''import importlib.util,sys,socket
if sys.argv[3]=="1":
 def deny(*a,**k): raise OSError("dry-run network disabled")
 socket.socket=deny; socket.create_connection=deny; socket.getaddrinfo=deny
if sys.argv[1]:
 spec=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
else:
 import notify as m
m.send("劲友家日常任务",sys.argv[2])
'''
    candidates = [str(p) for p in paths if p.is_file()] or ['']
    for path in candidates:
        try:
            res = subprocess.run([sys.executable, '-c', runner, path, body, '1' if dry else '0'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if res.returncode == 0:
                return '已调用本地通知适配器' if dry else '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not dry:
        directories = [Path(os.getenv('QINGLONG_NOTIFY_DIR', '.')), Path('/ql/data/scripts'), Path('/ql/scripts')]
        for directory in directories:
            script = directory / 'sendNotify.js'
            if script.is_file():
                try:
                    code = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
                    res = subprocess.run(['node', '-e', code, str(script.resolve()), '劲友家日常任务', body],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                    if res.returncode == 0:
                        return '已发送'
                except (OSError, subprocess.TimeoutExpired):
                    pass
    return '通知不可用或发送失败（保留业务退出码）'

def main():
    begin = time.monotonic()
    dry = os.getenv('JYJ_DRY_RUN', '0').lower() not in OFF
    if dry:
        def deny(*args, **kwargs):
            raise OSError('dry-run network disabled')
        socket.socket = deny
        socket.create_connection = deny
        socket.getaddrinfo = deny
    accounts = [line.strip() for line in os.getenv('jyjck', '').splitlines() if line.strip()]
    summary = {'mode': '断网预演' if dry else '正式运行', 'accounts': len(accounts), 'success': 0,
               'failed': 0, 'status': 'failure', 'tasks': {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}}
    log('========== 劲友家日常任务 ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('模式：%s；账号数量：%d' % (summary['mode'], len(accounts)))
    config_error = None
    try:
        if not accounts:
            raise TaskError('未配置 jyjck，每个非空行一个账号')
        tasks = list(dict.fromkeys(x.strip() for x in os.getenv('JYJ_TASKS', 'sign,daily-water').split(',') if x.strip()))
        if os.getenv('jyjRun', '0') == '1' and 'run' not in tasks:
            tasks.append('run')
        if not tasks or set(tasks) - ACTIONS:
            raise TaskError('JYJ_TASKS 为空或包含未知动作')
        coords = None
        if os.getenv('jyjlatlon'):
            parts = os.environ['jyjlatlon'].split('#')
            if len(parts) != 2:
                raise TaskError('jyjlatlon 需纬度#经度')
            lat, lon = map(float, parts)
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise TaskError('坐标范围不合法')
            coords = parts
        if set(tasks) - {'info', 'sign', 'beat', 'turntable', 'like', 'photo-query'} and coords is None:
            raise TaskError('所选任务需配置 jyjlatlon 真实位置')
        limit = int(os.getenv('JYJ_WATER_LIMIT', '0'))
        if not 0 <= limit <= 100:
            raise TaskError('JYJ_WATER_LIMIT 范围为0至100')
        if os.getenv('JYJ_PLANT_TYPE') and int(os.environ['JYJ_PLANT_TYPE']) <= 0:
            raise TaskError('JYJ_PLANT_TYPE 需正整数')
        if 'herb-game' in tasks and int(os.getenv('JYJ_HERB_SCORE', '-1')) < 0:
            raise TaskError('herb-game 需提供本人本次真实成绩 JYJ_HERB_SCORE')
        if 'photo' in tasks and not Path(os.getenv('JYJ_PHOTO_PATH', '')).is_file():
            raise TaskError('photo 需提供本人真实照片 JYJ_PHOTO_PATH')
    except (TaskError, ValueError):
        config_error = '配置错误；请检查账号、动作、真实坐标及所选动作必需参数'
    if config_error:
        log('❌ ' + config_error)
        summary['failed'] = len(accounts)
        summary['status'] = 'configuration-error'
    else:
        for index, line in enumerate(accounts, 1):
            start = time.monotonic()
            counters = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            log('----- 账号%d -----' % index)
            try:
                token, uid = line.split('#', 1)
                if not token.strip() or not uid.strip() or '@@' in line or any(c in token for c in '\r\n'):
                    raise ValueError()
                client = Client(token.strip(), uid.strip(), coords)
            except ValueError:
                log('❌ 账号格式错误，需单行 authorization#userid；不接受@@账号分隔')
                counters['total'] = counters['failed'] = 1
            else:
                planned = ['info'] + [x for x in tasks if x != 'info']
                for number, action in enumerate(planned, 1):
                    stage = time.monotonic()
                    counters['total'] += 1
                    log('阶段%d：%s 开始' % (number, action))
                    try:
                        if dry:
                            log('⏭️ 断网预演：参数与任务计划已检查，未执行业务')
                            counters['skipped'] += 1
                        else:
                            client.do(action)
                            counters['success'] += 1
                            log('✅ 接口确认成功')
                    except Exception as exc:
                        counters['failed'] += 1
                        log('❌ ' + (str(exc) if isinstance(exc, TaskError) else '任务执行异常（详情已脱敏）'))
                    log('阶段%d耗时：%.2f秒' % (number, time.monotonic() - stage))
                    # 账号认证失败后，不继续状态变更。
                    if action == 'info' and counters['failed']:
                        counters['total'] += len(planned) - 1
                        counters['skipped'] += len(planned) - 1
                        log('⏭️ 账号核验失败，后续动作全部跳过')
                        break
            summary['failed' if counters['failed'] else 'success'] += 1
            for key in counters:
                summary['tasks'][key] += counters[key]
            log('账号%d统计：总任务%d，成功%d，已完成%d，跳过%d，失败%d；耗时%.2f秒' %
                (index, counters['total'], counters['success'], counters['alreadyComplete'], counters['skipped'], counters['failed'], time.monotonic() - start))
        summary['status'] = ('partial-failure' if summary['success'] else 'failure') if summary['failed'] else ('dry-run' if dry else 'success')
    exit_code = 1 if config_error or summary['failed'] else 0
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        summary['notification'] = '通知配置或适配器异常（保留业务退出码）'
    summary['elapsedSeconds'] = round(time.monotonic() - begin, 2)
    summary['finishedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('任务统计：账号%d，成功%d，失败%d；子任务%s；总耗时%.2f秒' %
        (summary['accounts'], summary['success'], summary['failed'], json.dumps(summary['tasks'], ensure_ascii=False), summary['elapsedSeconds']))
    log('通知状态：' + summary['notification'])
    log('完成时间：%s；最终状态：%s' % (summary['finishedAt'], summary['status']))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
