#!/usr/bin/env python3
# name: 统一茄皇集市抽奖
# cron: 0 0 0 * * *
# 上游作者：清风；来源：Rookie-wb-WH/ql_scripts，tyqhDraw.py
# 上游许可：MIT（任务来源许可声明）；保留上游作者署名。
"""统一茄皇集市抽奖，Python 3.9+。

登录统一茄皇小程序，通过本机 HTTPS 抓包查看官方 login 请求 JSON 中的
thirdId 和 wid；两者必须来自同一账号。切勿分享抓包或凭据。
tyqhCookie：每个非空行 thirdId#wid#备注（备注可省略），不再用 @ 分隔账号。
保留上游变量名与字段顺序；备注用第二个 # 分隔，备注中的后续 # 保留。
日程保留每日零点：0 0 0 * * *。
默认仅登录、查询调料包/番茄及奖品记录。TYQH_DRAW_ENABLE=1 才开启兑换抽奖，
可能消耗资产或抽奖机会；活动 id 固定为上游的 58，每次最多 10 次。
TYQH_DRAW_LIMIT 可设为 1..10。开启前请在官方活动页了解当前兑换成本。
滑块使用本脚本的本地图像匹配（Pillow、numpy），不上传图片至第三方。
旧 ocr_url 无需设置；不再依赖 OCR 容器、服务或任何安装引导程序。
TYQH_DRY_RUN=1 完全断网，包括模拟通知；预演成功不表示业务成功。
QINGLONG_NOTIFY 未设置时按上架状态；0/false/no/off 关闭。支持青龙 notify.py，
QINGLONG_NOTIFY_DIR 可选指定其所在目录；通知故障不改变业务退出码。
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
        _ql_notify_identities = ('8ccef1e6eb2d7404', 'scripts/tyqhdraw.py', 'tyqhdraw.py', 'tyqhdraw')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '统一茄皇集市抽奖'
BASE = 'https://qiehuang-apig.xiaoyisz.com/qiehuangsecond/ga/'
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def stamp():
    return datetime.datetime.now().strftime('%H:%M:%S')


def log(message):
    print('[{}] {}'.format(stamp(), message), flush=True)


def sign(query=None, body=None):
    """保持上游参数排序、JSON 序列化和签名顺序。固定值是公开客户端常量。"""
    query = query or {}
    query_text = '&'.join('{}={}'.format(k, json.dumps(query[k]) if isinstance(query[k], dict)
                                        else query[k]) for k in sorted(query))
    timestamp = int(time.time() * 1000)
    chars = list('BxzTx45uIGT25TTHIIBU2')
    for digit in str(timestamp)[-3:]:
        chars.insert(int(digit), digit)
    secret = hashlib.md5(''.join(chars).encode()).hexdigest()
    nonce = ''.join(random.SystemRandom().choice(
        '0123456789qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM') for _ in range(16))
    values = ['game', nonce, str(timestamp), json.dumps(body) if body else '', query_text, secret]
    digest = hashlib.md5('|'.join(values).encode()).hexdigest().upper()
    return {'client_id': 'game', 'timestamp': str(timestamp), 'nonstr': nonce, 'sign': digest}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向已拒绝')


class Client:
    def __init__(self, third_id, wid):
        self.third_id, self.wid, self.token = third_id, wid, None
        # 禁用环境代理，防止凭据意外转发；每个账号独立 HTTP 客户端。
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, query=None, body=None):
        if os.getenv('TYQH_DRY_RUN', '0') == '1':
            raise TaskError('预演禁止 HTTP')
        headers = {'Content-Type': 'application/json', **sign(query, body)}
        if self.token:
            headers['Authorization'] = self.token
        url = BASE + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method='POST' if body is not None else 'GET')
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskError('接口响应过大')
            value = json.loads(raw)
        except TaskError:
            raise
        except Exception:
            # 异常文本可能包含 URL、请求参数或原始响应，禁止直接打印。
            raise TaskError('HTTP、超时或响应解析失败；未重试可能改变状态的请求') from None
        if not isinstance(value, dict) or type(value.get('code')) is not int:
            raise TaskError('接口业务结构异常')
        return value

    @staticmethod
    def checked(value):
        if value['code'] != 0:
            raise TaskError('接口未返回业务成功码')
        return value.get('data')

    def login(self):
        data = self.checked(self.request('public/api/login', body={
            'thirdId': self.third_id, 'wid': self.wid}))
        if not isinstance(data, dict) or not isinstance(data.get('token'), str) or not data['token']:
            raise TaskError('登录成功响应缺少有效会话')
        self.token = data['token']
        return data


def identity(data):
    # 仅白名单官方非秘密身份；不输出用户备注、电话或设备字段。
    if isinstance(data, dict):
        for field in ('nickname', 'nickName', 'username', 'displayName', 'publicUid'):
            value = data.get(field)
            if isinstance(value, (str, int)) and str(value):
                log('官方账号身份：' + str(value))


def slider_position(info):
    """对官方 base64 图片进行透明掩膜灰度模板匹配；不请求外部 OCR。"""
    try:
        import numpy as np
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 1000000
        def decode(value):
            if not isinstance(value, str) or len(value) > 1500000:
                raise ValueError()
            value = value.split(',', 1)[1] if value.startswith('data:image/') else value
            raw = base64.b64decode(value, validate=True)
            im = Image.open(io.BytesIO(raw))
            if im.width > 1000 or im.height > 1000:
                raise ValueError()
            im.load()
            return im
        foreground = decode(info['slidingImage']).convert('RGBA')
        background = decode(info['backImage']).convert('L')
        rgba = np.asarray(foreground)
        mask = rgba[:, :, 3] > 128
        ys, xs = np.where(mask)
        if len(xs) < 50 or mask.all():
            raise ValueError()  # 无掩膜不能可靠识别，拒绝猜测坐标。
        left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1
        template = np.asarray(foreground.convert('L'), dtype=float)[top:bottom, left:right]
        mask = mask[top:bottom, left:right]
        bg = np.asarray(background, dtype=float)
        h, w = template.shape
        if h > bg.shape[0] or w >= bg.shape[1]:
            raise ValueError()
        t = template[mask]; t = t - t.mean()
        norm = float(np.linalg.norm(t))
        if norm < 1:
            raise ValueError()
        scores = []
        for x in range(1, bg.shape[1] - w + 1):
            best = -1.0
            for y in range(bg.shape[0] - h + 1):
                b = bg[y:y+h, x:x+w][mask]; b = b - b.mean()
                n = float(np.linalg.norm(b))
                if n:
                    best = max(best, float(np.dot(t, b) / (norm*n)))
            scores.append((best, x))
        scores.sort(reverse=True)
        best, x = scores[0]
        rivals = [s for s, pos in scores if abs(pos-x) > 3]
        if best < 0.75 or (rivals and best - max(rivals) < 0.05):
            raise ValueError()
        # 与上游 OCR target[0] 一致，提交缺口在背景图中的横坐标。
        return x
    except Exception:
        raise TaskError('本地滑块识别失败或置信度不足，已停止抽奖') from None


def draw(client, limit):
    won = 0
    for attempt in range(1, limit + 1):
        value = client.request('activity/draw', query={'id': 58})
        if value['code'] == 4000:
            data = value.get('data')
            if not isinstance(data, dict) or not isinstance(data.get('slideImgInfo'), dict):
                raise TaskError('滑块挑战结构异常')
            xpos = slider_position(data['slideImgInfo'])
            client.checked(client.request('checkUserCapCode', body={'xpos': xpos}))
            log('✅ 第 {} 次抽奖：滑块验证业务成功'.format(attempt))
            value = client.request('activity/draw', query={'id': 58})
        if value['code'] != 0 and value.get('message') == '今日抽奖次数不足':
            log('☑️ 官方确认今日抽奖次数不足；已成功抽奖 {} 次'.format(won))
            return 'alreadyComplete'
        data = client.checked(value)
        if not isinstance(data, dict) or not isinstance(data.get('name'), str) or not data['name']:
            raise TaskError('抽奖成功响应缺少奖品，无法确认结果')
        won += 1
        # 只打印非秘密奖品字段，不打印服务端 message 或原始响应。
        log('✅ 第 {} 次抽奖业务成功；奖品：{}'.format(attempt, data['name'].replace('\n', ' ')))
        if attempt < limit:
            time.sleep(random.uniform(2, 4))
    return 'success'


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已关闭'
    if dry:
        return '预演模拟发送（完全断网）'
    body = '账号总数 {}，成功 {}，失败 {}，状态 {}'.format(
        summary['accountCount'], summary['successAccounts'], summary['failedAccounts'], summary['status'])
    # 在子进程导入青龙通知，限制挂起时间且不泄露通知器内部输出。
    code = """import importlib.util,sys
from pathlib import Path
try:
 import notify
except ImportError:
 for directory in sys.argv[3:]:
  path=Path(directory)/'notify.py'
  if path.is_file():
   sys.path.insert(0,str(path.parent))
   spec=importlib.util.spec_from_file_location('notify',path)
   notify=importlib.util.module_from_spec(spec);spec.loader.exec_module(notify)
   break
 else: sys.exit(2)
notify.send(sys.argv[1],sys.argv[2])
"""
    dirs = [d for d in (os.getenv('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts') if d]
    try:
        result = subprocess.run([sys.executable, '-c', code, TITLE, body] + dirs,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return '已发送' if result.returncode == 0 else '不可用或发送失败'
    except Exception:
        return '不可用或发送失败'


def main():
    started = time.monotonic()
    dry = os.getenv('TYQH_DRY_RUN', '0') == '1'
    lines = [line.strip() for line in os.getenv('tyqhCookie', '').splitlines() if line.strip()]
    log('========== {} =========='.format(TITLE))
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('运行模式：{}；账号数：{}'.format('完全断网预演' if dry else '正式', len(lines)))
    accounts = []
    config_error = None
    try:
        if not lines:
            raise TaskError('缺少 tyqhCookie；请按每行 thirdId#wid#备注 配置')
        if os.getenv('TYQH_DRAW_ENABLE', '0') not in ('0', '1'):
            raise TaskError('TYQH_DRAW_ENABLE 仅允许 0 或 1')
        limit = int(os.getenv('TYQH_DRAW_LIMIT', '10'))
        if not 1 <= limit <= 10:
            raise ValueError()
        if os.getenv('TYQH_DRY_RUN', '0') not in ('0', '1'):
            raise TaskError('TYQH_DRY_RUN 仅允许 0 或 1')
    except (TaskError, ValueError) as exc:
        config_error = str(exc) if isinstance(exc, TaskError) else 'TYQH_DRAW_LIMIT 必须为 1..10 整数'
        log('❌ 配置错误：' + config_error)
    if not config_error:
        for index, line in enumerate(lines, 1):
            begin = time.monotonic()
            stats = dict(success=0, alreadyComplete=0, skipped=0, failure=0)
            log('----- 账号 {} -----'.format(index))
            def stage(number, title, action):
                tick = time.monotonic()
                log('阶段 {}：{}'.format(number, title))
                try:
                    outcome = action() or 'success'
                    stats[outcome] += 1
                    log('{} 阶段 {} {}：{}，耗时 {:.2f} 秒'.format(
                        '⏭️' if outcome == 'skipped' else '✅', number, title, outcome, time.monotonic()-tick))
                    return True
                except Exception as exc:
                    stats['failure'] += 1
                    message = str(exc) if isinstance(exc, TaskError) else '执行或响应字段校验失败'
                    log('❌ 阶段 {} {}：{}，耗时 {:.2f} 秒'.format(number, title, message, time.monotonic()-tick))
                    return False
            try:
                third, rest = line.split('#', 1)
                wid, _, remark = rest.partition('#')
                if not third or not wid or '@' in third or '@' in wid:
                    raise ValueError()
            except ValueError:
                stage(1, '账号参数检查', lambda: (_ for _ in ()).throw(TaskError('账号格式错误；不支持 @ 分隔账号')))
            else:
                client = Client(third, wid)
                def login():
                    if dry:
                        log('预演：已校验配套凭据格式；未登录、未校验凭据有效性')
                    else:
                        identity(client.login())
                ok = stage(1, '登录', login)
                def assets():
                    if dry:
                        log('预演：资产查询路径和业务码检查已加载')
                        return
                    data = client.checked(client.request('userInfo/get'))
                    if not isinstance(data, dict) or any(type(data.get(k)) not in (int, float) for k in ('gold', 'score')):
                        raise TaskError('资产响应字段异常')
                    identity(data)
                    log('资产：调料包 {}，番茄 {}'.format(data['gold'], data['score']))
                def lottery():
                    if os.getenv('TYQH_DRAW_ENABLE', '0') != '1':
                        log('抽奖开关未开启；兑换操作已跳过')
                        return 'skipped'
                    if dry:
                        log('预演：活动 58，最多 {} 次；未抽奖、未请求验证码'.format(limit))
                        return
                    return draw(client, limit)
                def prizes():
                    if dry:
                        log('预演：奖品记录查询路径和字段校验已加载')
                        return
                    data = client.checked(client.request('draw-prize/log/find'))
                    if not isinstance(data, list) or any(not isinstance(x, dict) or
                            not isinstance(x.get('prizeRankName'), str) or not isinstance(x.get('name'), str) for x in data):
                        raise TaskError('奖品记录结构异常')
                    physical = [x for x in data if x['prizeRankName'] == '实物礼品']
                    for item in physical:
                        log('实物礼品：' + item['name'].replace('\n', ' '))
                    log('实物礼品 {} 条；礼品数量（非实物）{} 条'.format(len(physical), len(data)-len(physical)))
                for number, title, action in ((2, '查询资产', assets), (3, '集市兑换抽奖', lottery), (4, '查询奖品记录', prizes)):
                    stage(number, title, action if ok else lambda: 'skipped')
            elapsed = round(time.monotonic()-begin, 2)
            result = {'account': index, 'status': 'failure' if stats['failure'] else 'success',
                      'statistics': {'total': sum(stats.values()), **stats}, 'elapsedSeconds': elapsed}
            accounts.append(result)
            log('账号 {} 统计：总任务 {}，成功 {}，已完成 {}，跳过 {}，失败 {}；耗时 {} 秒'.format(
                index, sum(stats.values()), stats['success'], stats['alreadyComplete'], stats['skipped'], stats['failure'], elapsed))
    failed = sum(a['status'] == 'failure' for a in accounts)
    success = len(accounts)-failed
    exit_code = 1 if config_error or failed else 0
    status = 'configuration-error' if config_error else ('partial-failure' if failed and success else
             'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status,
               'accountCount': len(lines), 'successAccounts': success, 'failedAccounts': len(lines) if config_error else failed,
               'accounts': accounts, 'exitCode': exit_code}
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic()-started, 2)
    summary['finishTime'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('----------------------------------------')
    log('任务统计：账号总数 {}，成功 {}，失败 {}'.format(len(lines), success, summary['failedAccounts']))
    totals = {key: sum(a['statistics'][key] for a in accounts) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    summary['statistics'] = totals
    log('子任务统计：总数 {total}，成功 {success}，已完成 {alreadyComplete}，跳过 {skipped}，失败 {failure}'.format(**totals))
    log('通知状态：' + summary['notification'])
    log('总耗时：{} 秒；完成时间：{}；最终状态：{}'.format(summary['elapsedSeconds'], summary['finishTime'], status))
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
