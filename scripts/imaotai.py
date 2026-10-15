#!/usr/bin/env python3
# name: i茅台申购与耐力
# cron: 38 2 * * *
# 来源: Sitoi/dailycheckin, dailycheckin/imaotai/main.py
# 上游许可: MIT；原始输入未包含额外版权声明。
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""IMAOTAI_ACCOUNTS: 每行一个 JSON 对象，沿用上游字段 token、userid、
province、city、lat、lng、item_codes、reserve_rule；增加 device_id，来自本人抓包。
mobile 兼容但不使用、不输出。禁止共享默认设备或伪造定位。
默认只领取耐力；IMAOTAI_RESERVE=1 才执行申购；IMAOTAI_ENERGY=0 关闭耐力。
未取得商品/库存或业务成功码均视为失败。申购成功不代表中签或购买成功。
登录参考 imaotai_login.py 为交互配置工具，不合并短信发送和账号文件写入。
"""
import base64
import datetime as dt
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = 'i茅台申购与耐力'
DEFAULT_ITEMS = ['11318', '11319']
APP = 'https://app.moutai519.com.cn'
STATIC = 'https://static.moutai519.com.cn/mt-backend/xhr/front/mall'
H5 = 'https://h5.moutai519.com.cn'
FALSE = {'0', 'false', 'no', 'off'}

class TaskError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，避免凭据跨站传输')

def enabled(name, default='1'):
    return os.getenv(name, default).lower().strip() not in FALSE

def log(text):
    print(f'[{dt.datetime.now():%H:%M:%S}] {text}', flush=True)

def request(url, headers=None, payload=None, codes=None, dry=False):
    if dry:
        raise TaskError('预演禁止网络请求')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {
        'app.moutai519.com.cn', 'static.moutai519.com.cn',
        'h5.moutai519.com.cn', 'itunes.apple.com'
    } or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise TaskError('拒绝未获准的接口地址')
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, data=body, headers=headers or {}, method='GET' if body is None else 'POST')
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise TaskError('接口响应过大')
        result = json.loads(raw)
    except TaskError:
        raise
    except Exception:
        raise TaskError('网络请求或响应解析失败') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构异常')
    if codes is not None and result.get('code') not in codes:
        raise TaskError('业务码未确认成功；请核对账号状态和接口')
    return result

def data(result):
    if 'code' in result and result['code'] not in (200, 2000):
        raise TaskError('查询业务码失败')
    value = result.get('data')
    if not isinstance(value, dict):
        raise TaskError('查询缺少有效数据')
    return value

def parse_account(line, reserve):
    try:
        a = json.loads(line)
        if not isinstance(a, dict):
            raise ValueError
        if isinstance(a.get('userid'), int) and not isinstance(a['userid'], bool):
            a['userid'] = str(a['userid'])
        for field in ('token', 'userid', 'device_id'):
            if not isinstance(a.get(field), str) or not a[field].strip() or any(c in a[field] for c in '\r\n'):
                raise ValueError
        a = dict(a)
        if reserve:
            for field in ('province', 'city'):
                if not isinstance(a.get(field), str) or not a[field].strip():
                    raise ValueError
            lat, lng = float(a['lat']), float(a['lng'])
            if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
                raise ValueError
            a['lat'], a['lng'] = str(lat), str(lng)
            a['item_codes'] = a.get('item_codes', DEFAULT_ITEMS)
            if not isinstance(a['item_codes'], list) or not a['item_codes'] or any(not isinstance(i, str) or not i.isdigit() for i in a['item_codes']):
                raise ValueError
            if a.get('reserve_rule', 0) not in (0, 1):
                raise ValueError
        return a
    except Exception:
        raise TaskError('账号配置错误：核对 JSON、凭据、设备标识及申购字段') from None

def headers(a, version):
    h = {'Content-Type': 'application/json', 'Accept': 'application/json',
         'MT-Token': a['token'], 'userId': a['userid'], 'MT-Device-ID': a['device_id'],
         'MT-APP-Version': version, 'MT-Bundle-ID': 'com.moutai.mall',
         'MT-Network-Type': 'WIFI', 'MT-User-Tag': '0',
         'User-Agent': 'iOS;16.3;Apple;?unrecognized?',
         'MT-Info': '028e7f96f6369cafe1d105579c5b9377',
         'MT-R': 'clips_OlU6TmFRag5rCXwbNAQ/Tz1SKlN8THcecBp/HGhHdw==',
         'MT-Request-ID': str(time.time_ns()), 'MT-K': str(int(time.time()*1000))}
    for field in ('lat', 'lng'):
        if field in a:
            h['MT-' + field.capitalize()] = str(a[field])
    return h

def identity(result, a):
    d = result.get('data')
    if not isinstance(d, dict):
        return
    for key in ('nickname', 'nickName', 'username', 'displayName', 'userId', 'uid'):
        value = d.get(key)
        if isinstance(value, (str, int)) and str(value):
            text = str(value)
            # 不将凭据、手机号、设备标识混入身份日志。
            for secret in (a.get('token'), a.get('device_id'), a.get('mobile')):
                if secret:
                    text = text.replace(str(secret), '[已脱敏]')
            text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已脱敏]', text)
            log('官方账号身份：' + text.replace('\n', ' ').replace('\r', ' '))
            return

def choose_shop(a, shops, directory, item):
    available = []
    for shop in shops:
        sid = str(shop.get('shopId', ''))
        info = directory.get(sid, {})
        inventories = [i.get('inventory', 0) for i in shop.get('items', []) if str(i.get('itemId')) == item]
        if not inventories:
            continue
        if a.get('reserve_rule', 0) == 1:
            if info.get('provinceName') != a['province'] or info.get('cityName') != a['city']:
                continue
            count = max(float(n) for n in inventories)
            if count > 0:
                available.append((-count, sid))
        elif info and max(float(n) for n in inventories) > 0:
            distance = (float(a['lat'])-float(info['lat']))**2 + (float(a['lng'])-float(info['lng']))**2
            available.append((distance, sid))
    if not available:
        raise TaskError('当前商品没有可申购门店，不认定业务成功')
    return min(available)[1]

def reservation(a, h, session, shop, item):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        raise TaskError('缺少 pycryptodome；请在青龙依赖管理安装') from None
    params = {'itemInfoList': [{'count': 1, 'itemId': item}],
              'sessionId': int(session), 'userId': a['userid'], 'shopId': shop}
    encrypted = AES.new(b'qbhajinldepmucsonaaaccgypwuvcjaa', AES.MODE_CBC, b'2018534749963515').encrypt(pad(json.dumps(params).encode(), 16))
    params['actParam'] = base64.b64encode(encrypted).decode()
    del params['userId']
    return request(APP + '/xhr/front/mall/reservation/add', h, params, codes=(2000,))

def energy(a, h):
    h = dict(h)
    h['Cookie'] = 'MT-Device-ID-Wap=' + quote(a['device_id'], safe='') + '; MT-Token-Wap=' + quote(a['token'], safe='') + '; YX_SUPPORT_WEBP=1'
    return request(H5 + '/game/isolationPage/getUserEnergyAward', h, {}, codes=(200,))

def notify(body, dry):
    if not enabled('QINGLONG_NOTIFY'):
        log('⏭️ 通知：全局开关已关闭')
        return 'disabled'
    if dry:
        log('⏭️ 通知：断网预演仅展示脱敏总结：' + body)
        return 'dry-run-local'
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path(__file__).parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    # 在子进程加载青龙通知，超时或失败不影响业务退出码，也不输出通知内部日志。
    code = "import importlib.util,sys; s=importlib.util.spec_from_file_location('notify',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])"
    for path in paths:
        if path.is_file():
            try:
                r = subprocess.run([sys.executable, '-c', code, str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
                if r.returncode == 0:
                    log('✅ 通知已提交')
                    return 'sent'
            except Exception:
                pass
    # 标准安装的 notify 模块与 JS 通知兼容路径。
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            r = subprocess.run([sys.executable, '-c', code, spec.origin, TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if r.returncode == 0:
                return 'sent'
    except Exception:
        pass
    dirs = [Path('/ql/data/scripts'), Path('/ql/scripts')]
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        dirs.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']))
    for directory in dirs:
        path = directory / 'sendNotify.js'
        if path.is_file():
            try:
                r = subprocess.run(['node', '-e', "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))", str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                if r.returncode == 0:
                    return 'sent'
            except Exception:
                pass
    log('⚠️ 通知不可用或发送失败；保留业务退出码')
    return 'unavailable'

def main():
    started = time.monotonic()
    dry = enabled('IMAOTAI_DRY_RUN', '0')
    reserve, award = enabled('IMAOTAI_RESERVE', '0'), enabled('IMAOTAI_ENERGY')
    lines = [line.strip() for line in os.getenv('IMAOTAI_ACCOUNTS', '').splitlines() if line.strip()]
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "正式"}；账号数：{len(lines)}')
    totals = {'total': 0, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
    results = []
    config_error = not lines or not (reserve or award)
    if config_error:
        log('❌ 配置错误：需要账号且至少启用一项任务')
    for number, line in enumerate(lines, 1):
        begin = time.monotonic()
        stats = dict.fromkeys(totals, 0)
        stage_number = 0
        def stage(name, action):
            nonlocal stage_number
            stage_number += 1
            clock = time.monotonic()
            stats['total'] += 1
            log(f'账号 {number} 阶段 {stage_number}：{name}')
            try:
                value = action()
                stats['success'] += 1
                log(f'✅ 账号 {number} 阶段 {stage_number}：{name} {"预演通过（未执行）" if dry else "成功"}；耗时 {time.monotonic()-clock:.2f} 秒')
                return value
            except Exception as exc:
                stats['failed'] += 1
                message = str(exc) if isinstance(exc, TaskError) else '结构或运行异常（敏感细节已隐藏）'
                log(f'❌ 账号 {number} 阶段 {stage_number}：{message}；耗时 {time.monotonic()-clock:.2f} 秒')
                return None
        a = stage('解析账号配置', lambda: parse_account(line, reserve))
        if a and not config_error:
            if dry:
                if reserve:
                    stage('查询版本、场次及门店（不联网）', lambda: True)
                    for item in a['item_codes']:
                        stage('商品 ' + item + ' 选店及 AES 申购计划（不提交）', lambda: True)
                        if award:
                            stage('领取耐力计划（不提交）', lambda: True)
                elif award:
                    stage('领取耐力计划（不提交）', lambda: True)
                log('DRY_RUN_OK：仅验证配置和执行计划，不代表真实业务成功')
            else:
                def version_lookup():
                    result = request('https://itunes.apple.com/cn/lookup?id=1600482450')
                    v = result['results'][0]['version']
                    if not isinstance(v, str) or not re.fullmatch(r'\d+(?:\.\d+)+', v):
                        raise TaskError('应用版本数据异常')
                    return v
                version = stage('查询应用版本', version_lookup)
                if version:
                    h = headers(a, version)
                    context = None
                    if reserve:
                        def query():
                            midnight = int(dt.datetime.combine(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date(), dt.time(), tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000)
                            session = data(request(STATIC + f'/index/session/get/{midnight}'))['sessionId']
                            resource_headers = {k: v for k, v in h.items() if k not in ('MT-Token', 'userId', 'current_session_id')}
                            resource_headers.update({'X-Requested-With': 'XMLHttpRequest', 'Referer': H5 + '/gux/game/main?appConfig=2_1_2', 'Origin': H5, 'Client-User-Agent': 'iOS;16.0.1;Apple;iPhone 14 ProMax', 'Accept-Language': 'zh-CN,zh-Hans;q=1'})
                            resource = data(request(STATIC + '/resource/get', resource_headers))['mtshops_pc']['url']
                            directory = request(resource)
                            return session, midnight, directory
                        context = stage('查询场次与门店资源', query)
                    if context:
                        session, midnight, directory = context
                        h['current_session_id'] = str(session)
                        for item in a['item_codes']:
                            def buy(item=item):
                                url = STATIC + '/shop/list/slim/v3/' + '/'.join(quote(str(x), safe='') for x in (session, a['province'], item, midnight))
                                shops = data(request(url))['shops']
                                shop = choose_shop(a, shops, directory, item)
                                result = reservation(a, h, session, shop, item)
                                identity(result, a)
                                return True
                            stage('商品 ' + item + ' 选店与申购（非中签结果）', buy)
                            if award:
                                time.sleep(20)
                                stage('领取耐力', lambda: claim(a, h))
                    elif award:
                        stage('领取耐力', lambda: claim(a, h))
        for key in totals:
            totals[key] += stats[key]
        passed = stats['failed'] == 0 and not config_error
        results.append({'account': number, 'status': 'dry-run' if passed and dry else 'success' if passed else 'failure', **stats})
        log(f'账号 {number} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {time.monotonic()-begin:.2f} 秒')
    failed = sum(r['status'] == 'failure' for r in results)
    success = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = 'configuration-error' if config_error else 'partial-failure' if failed and success else 'failure' if failed else 'dry-run' if dry else 'success'
    body = f'状态：{status}；账号总数 {len(lines)}，成功 {success}，失败 {failed}；子任务成功 {totals["success"]}，失败 {totals["failed"]}'
    log('----------------------------------------')
    log(body)
    notification = notify(body, dry)
    log(f'完成时间：{dt.datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic()-started:.2f} 秒；最终状态 {status}；通知 {notification}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status, 'accounts': len(lines), 'success': success, 'failed': failed, 'tasks': totals, 'results': results, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code

def claim(a, h):
    result = energy(a, h)
    identity(result, a)
    return True

if __name__ == '__main__':
    sys.exit(main())
