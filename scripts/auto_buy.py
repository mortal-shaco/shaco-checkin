#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 上海杨浦商城定时抢购
# cron: 0 0 10 * * *
"""
定时抢购脚本：用于在指定时间自动抢购商品。
新增同产品积分任务来自 script/shyp/main.py 与 api.py。
原声明：上海云媒体积分任务自动化脚本；上海云媒体 API Interface；
Author: Assistant；Date: 2025-11-06。
SHYP_TASK=buy（默认）保留商城行为；SHYP_TASK=points 单独运行积分任务。
不要将两个任务自动串联：凭据、时限不同。商城 cron 保持 0 0 10 * * *；
积分上游 cron 保持 1 1 1 1 1，可在青龙另建同脚本任务设置 SHYP_TASK=points。
积分参数获取：登录自己的上海杨浦 App，抓取 app.ypmedia.cn 的
/media-basic-port/api/app/personal/score/info 请求头 token、deviceid、siteid。
SHYP_POINTS_ACCOUNTS 每个非空行是 JSON 对象，必填 token、device_id；
可选 site_id（默认 310110）、user_agent（默认 okhttp/4.10.0）。
JSON 保留凭据内所有分隔符；不读取私有 config/token.json。
SHYP_POINTS_DRY_RUN=1 完全断网，仅校验配置与流程，不模拟业务成功。
SHYP_POINTS_ENABLE=1 才执行积分动作，否则仅查询积分、签到和任务状态。
SHYP_POINTS_ACTIONS 默认 read,video,favor,comment,share，可按逗号选动作。
SHYP_POINTS_UNFAVOR=1 才在收藏后取消收藏，默认保留收藏避免破坏已有状态。
评论优先从 https://v1.hitokoto.cn/?encode=json 获取带作者/来源的文字；
所有失败回退本地短句，可用 SHYP_POINTS_LOCAL_TEXT 指定（最长 280 字）。
SHYP_POINTS_TIMEOUT 默认 30 秒；保留原动作等待区间；未知结果不重试。
积分任务没有签到写入接口证据，因此只查询签到，不伪造签到功能。
积分每步要求 code 为数字 0 且无冲突错误，刷新任务进度核对最终完成。

上游：Cat-zaizai/ZaiZaiCat-Checkin，script/shyp/auto_buy.py
版本：d6a334e43d0a0c8f41b039cd410be33593efc35b；许可：MIT。
原文件没有单独的版权声明。保留上游归属，修改版同样使用 MIT 许可。

参数获取：登录上海杨浦 App，在商城兑换页面抓取自己账号的
mall-api.shmedia.tech/trade-service/trade/carts/buy 请求。
SHYP_BUY_ACCOUNTS 每个非空行为 Authorization|Cookie，按第一个 | 分割；
Cookie 可省略，不要填写请求头名称。不要使用积分接口的 token/deviceid。
从自己要兑换的商品请求查询参数获取 sku_id、activity_id、promotion_type、num。
SHYP_BUY_SKU_ID 和 SHYP_BUY_ACTIVITY_ID 必填，数量默认 1，类型默认 EXCHANGE。
只有 SHYP_BUY_ENABLE=1 才允许真实下单；可能消耗积分或生成付费订单。
SHYP_BUY_TARGET_TIME 默认 10:00:00，可用 YYYY-MM-DD HH:MM:SS 或 immediate。
仅时分秒已过则等待明天；使用运行环境本地时区，建议青龙设置 Asia/Shanghai。
SHYP_BUY_RETRY_TIMES 默认 10；仅明确 success=false 的业务拒绝才可重试。
空响应、未知结构、HTTP 错误或超时结果不确定，不重试，须在商城核对订单。
接口成功码在提供的源码中没有可靠证据，因此仅接受明确 success=true，
且没有冲突的错误字段；其他响应失败闭合，不把 HTTP 200 当业务成功。
SHYP_BUY_DRY_RUN=1 完全断网，不等待、不下单、不调用通知模块。
通知由青龙 notify.py 发送；缺失或失败不会覆盖业务退出码。

MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
        _ql_notify_identities = ('0196c3c6c89dc959', 'scripts/auto_buy.py', 'auto_buy.py', 'auto_buy')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import json
import math
import random
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = '上海杨浦商城定时抢购'
URL = 'https://mall-api.shmedia.tech/trade-service/trade/carts/buy'
DISABLED = {'0', 'false', 'no', 'off'}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def target_time(value):
    now = datetime.now()
    if value == 'immediate':
        return now
    if ' ' in value:
        result = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if result < now:
            raise ValueError('完整日期已过期，拒绝下单')
        return result
    result = datetime.combine(now.date(), datetime.strptime(value, '%H:%M:%S').time())
    return result + timedelta(days=1) if result < now else result


def number(name, default, low, high, integer=False):
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or not low <= value <= high or (integer and not value.is_integer()):
        raise ValueError(f'{name} 超出允许范围')
    return int(value) if integer else value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def identities(result, secrets):
    # 只读取明确身份字段；不读取手机号、令牌、设备标识或完整响应。
    containers = [result]
    data = result.get('data')
    if isinstance(data, dict):
        containers.append(data)
        if isinstance(data.get('user'), dict):
            containers.append(data['user'])
    for container in containers:
        for key in ('nickname', 'username', 'displayName', 'publicUid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                value = str(value)
                if any(secret and secret in value for secret in secrets) or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value):
                    continue
                log(f'官方账号身份 {key}: {json.dumps(value, ensure_ascii=False)}')


def buy(token, cookie, params, timeout):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; MI 8 SE Build/QKQ1.190828.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.101 Mobile Safari/537.36Rmt/YangPu; Version/3.0.2',
        'Accept': 'application/json, text/plain, */*',
        'Authorization': token,
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin': 'https://mall-mobile.shmedia.tech',
        'X-Requested-With': 'com.wdit.shrmtyp',
        'Referer': 'https://mall-mobile.shmedia.tech/real.html?shop_id=31011001&site_id=310110&target=media&access_id=182&version=2025091601',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    if cookie:
        headers['Cookie'] = cookie
    try:
        request = Request(URL + '?' + urlencode(params), data=b'', headers=headers, method='POST')
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                return False, False, 'HTTP 状态异常，结果不确定'
            raw = response.read(1024 * 1024 + 1)
        if not raw or len(raw) > 1024 * 1024:
            return False, False, '空响应或响应过大，结果不确定'
        result = json.loads(raw)
        if not isinstance(result, dict):
            return False, False, '响应结构未知，结果不确定'
        identities(result, (token, cookie))
        # 不推测 code=0/200；积分服务的业务码不能证明商城服务契约。
        if result.get('success') is True and not result.get('error') and not result.get('errors') and ('code' not in result or str(result['code']) in {'0', '200'}):
            return True, False, '抢购成功：接口明确确认 success=true'
        if result.get('success') is False:
            return False, True, '接口明确拒绝本次抢购'
        return False, False, '未取得明确业务成功确认，停止重试并请核对商城订单'
    except Exception:
        # urllib 异常可能包含完整 URL、请求参数或响应，禁止输出异常文本。
        return False, False, '网络、HTTP 或解析错误，结果不确定，停止重试'


def notify(body, dry, title=TITLE):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        log('通知状态：全局开关已关闭')
        return 'disabled'
    if dry:
        log('通知状态：断网预演已生成脱敏通知摘要，不调用可能联网的通知模块')
        log(body)
        return 'dry-run'
    # 子进程隔离并限制通知耗时；捕获第三方输出避免泄露其配置。
    code = '''import importlib.util, os, pathlib, sys
try:
    import notify
except ImportError:
    candidates = []
    if os.environ.get("QINGLONG_NOTIFY_DIR"):
        candidates.append(pathlib.Path(os.environ["QINGLONG_NOTIFY_DIR"]) / "notify.py")
    candidates.extend(map(pathlib.Path, ["/ql/data/scripts/notify.py", "/ql/scripts/notify.py"]))
    path = next((p for p in candidates if p.is_file()), None)
    if path is None: sys.exit(2)
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("notify", path)
    notify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notify)
notify.send(sys.argv[1], sys.argv[2])
'''
    try:
        result = subprocess.run([sys.executable, '-c', code, title, body], capture_output=True, timeout=30, check=False)
        ok = result.returncode == 0
    except Exception:
        ok = False
    log('通知状态：已发送' if ok else '通知状态：不可用或发送失败，保留业务退出码')
    return 'sent' if ok else 'unavailable'


def buy_main():
    start = time.monotonic()
    dry = os.environ.get('SHYP_BUY_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    lines = [line.strip() for line in os.environ.get('SHYP_BUY_ACCOUNTS', '').splitlines() if line.strip()]
    log('=' * 50)
    log(f'{TITLE} | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式：{"断网预演" if dry else "真实执行"}；账号数量：{len(lines)}')
    results = []
    config_error = False
    interrupted = False
    try:
        stage = time.monotonic()
        log('阶段 1：检查全局参数')
        if not lines:
            raise ValueError('必须配置 SHYP_BUY_ACCOUNTS，每行一个账号')
        params = {'sku_id': os.environ.get('SHYP_BUY_SKU_ID', ''),
                  'activity_id': os.environ.get('SHYP_BUY_ACTIVITY_ID', ''),
                  'num': str(number('SHYP_BUY_NUM', '1', 1, 100, True)),
                  'promotion_type': os.environ.get('SHYP_BUY_PROMOTION_TYPE', 'EXCHANGE')}
        if not all(params.values()) or not params['sku_id'].isdigit() or not params['activity_id'].isdigit():
            raise ValueError('必须配置合法的商品及活动编号，禁止使用硬编码商品下单')
        if not re.fullmatch(r'[A-Z_]{1,40}', params['promotion_type']):
            raise ValueError('促销类型格式无效')
        retries = number('SHYP_BUY_RETRY_TIMES', '10', 1, 100, True)
        interval = number('SHYP_BUY_RETRY_INTERVAL', '0.3', 0.1, 60)
        timeout = number('SHYP_BUY_TIMEOUT', '10', 1, 60)
        target = target_time(os.environ.get('SHYP_BUY_TARGET_TIME', '10:00:00'))
        if not dry and os.environ.get('SHYP_BUY_ENABLE', '0') != '1':
            raise ValueError('真实下单须明确设置 SHYP_BUY_ENABLE=1，默认不消费')
        log(f'阶段 1：参数检查通过，耗时 {time.monotonic() - stage:.3f} 秒')
        stage = time.monotonic()
        log(f'阶段 2：目标时间 {target:%Y-%m-%d %H:%M:%S}')
        if dry:
            log('阶段 2：预演跳过等待')
        else:
            while (target - datetime.now()).total_seconds() > 0:
                time.sleep(min(30, (target - datetime.now()).total_seconds()))
        log(f'阶段 2：完成，耗时 {time.monotonic() - stage:.3f} 秒')
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            log(f'账号 {index} / 阶段 3：校验账号并执行抢购')
            token, delimiter, cookie = line.partition('|')
            token = token.strip()
            cookie = cookie.strip()
            ok = False
            attempts = 0
            if not token or any(ord(c) < 32 or ord(c) > 255 for c in token + cookie):
                log('❌ 账号凭据格式错误')
            elif dry:
                log('DRY_RUN_OK：凭据解析和抢购流程预演通过；未发送 HTTP、未消费')
                ok = True
            else:
                for attempt in range(retries):
                    attempts += 1
                    step = time.monotonic()
                    ok, retryable, message = buy(token, cookie, params, timeout)
                    log(f'账号 {index} / 阶段 3.{attempt + 1}：{message}；耗时 {time.monotonic() - step:.3f} 秒')
                    if ok or not retryable:
                        break
                    if attempt + 1 < retries:
                        time.sleep(interval)
            result = {'account': index, 'total': 1, 'success': int(ok and not dry),
                      'alreadyComplete': 0, 'skipped': int(ok and dry), 'failed': int(not ok),
                      'attempts': attempts, 'ok': ok, 'seconds': round(time.monotonic() - account_start, 3)}
            results.append(result)
            log(f'账号 {index} 统计：总任务 1，成功 {result["success"]}，已完成 0，跳过 {result["skipped"]}，失败 {result["failed"]}，耗时 {result["seconds"]} 秒')
    except KeyboardInterrupt:
        interrupted = True
        log('❌ 用户中断；未确认成功的账号按失败计入')
    except Exception as error:
        config_error = True
        # 仅输出自有静态校验说明，不输出解析器生成的输入回显。
        message = str(error) if isinstance(error, ValueError) and str(error).startswith(('必须', '真实', '完整', '促销', 'SHYP_')) else '配置格式错误'
        log(f'❌ 配置错误：{message}')
    successes = sum(r['ok'] for r in results)
    failures = len(lines) - successes
    exit_code = 1 if config_error or interrupted or failures else 0
    status = 'configuration-error' if config_error else 'partial-failure' if failures and successes else 'failure' if exit_code else 'dry-run' if dry else 'success'
    log('-' * 50)
    body = f'状态：{status}；账号总数：{len(lines)}；成功数：{successes}；失败数：{failures}；模式：{"预演，不代表业务成功" if dry else "真实执行"}'
    log(body)
    log(f'子任务统计：总数 {len(lines)}，成功 {sum(r["success"] for r in results)}，已完成 0，跳过 {sum(r["skipped"] for r in results)}，失败 {failures}')
    notification = notify(body, dry)
    finish = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f'完成时间：{finish}；总耗时：{time.monotonic() - start:.3f} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(lines), 'success': successes, 'failed': failures, 'results': results,
          'notification': notification, 'finishTime': finish, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


POINTS_TITLE = '上海杨浦积分任务'
POINTS_BASE = 'https://app.ypmedia.cn/media-basic-port/api/app/'
ACTIONS = {'read': ('002', '阅读', (2, 4)),
           'video': ('003', '视频', (10, 15)),
           'favor': ('005', '收藏', (15, 20)),
           'comment': ('006', '评论', (30, 35)),
           'share': ('007', '分享', (5, 10))}
LOCAL_TEXT = ['👍', '写得好', '支持', '不错', '很好', '赞', '有意义', '学习了', '感谢分享', '受益匪浅']


class TaskError(Exception):
    """只包含静态脱敏错误说明。"""


def normalized(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def comment_text(local):
    # 独立请求，绝不复用账号请求头，不跟随重定向。
    try:
        req = Request('https://v1.hitokoto.cn/?encode=json',
                      headers={'Accept': 'application/json'}, method='GET')
        with build_opener(NoRedirect()).open(req, timeout=8) as response:
            if response.status != 200:
                raise TaskError('文字服务状态异常')
            raw = response.read(16385)
        if len(raw) > 16384:
            raise TaskError('文字服务响应过大')
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TaskError('文字服务结构异常')
        text = normalized(obj.get('hitokoto'))
        author = normalized(obj.get('from_who'))
        source = normalized(obj.get('from'))
        if not text:
            raise TaskError('文字为空')
        if author and source:
            text += f' —— {author}《{source}》'
        elif source:
            text += f' ——《{source}》'
        elif author:
            text += f' —— {author}'
        if len(text) > 280:
            raise TaskError('文字过长')
        log('评论文字：一言获取成功，保留作者及来源署名')
        return text
    except Exception:
        log('⚠️ 评论文字：文字服务不可用或格式不合规，采用本地回退')
        return local or random.choice(LOCAL_TEXT)


class PointsAPI:
    def __init__(self, account, timeout):
        self.site = account.get('site_id', '310110')
        self.timeout = timeout
        self.secrets = (account['token'], account['device_id'])
        self.headers = {'User-Agent': account.get('user_agent', 'okhttp/4.10.0'),
                        'Content-Type': 'application/json; charset=UTF-8',
                        'Accept-Encoding': 'identity',
                        'log-header': 'I am the log request header.',
                        'deviceid': account['device_id'], 'siteid': self.site,
                        'token': account['token']}

    def common(self, **extra):
        return dict(orderBy='release_desc', requestType='1', siteId=self.site, **extra)

    def call(self, endpoint, data):
        started = time.monotonic()
        try:
            req = Request(POINTS_BASE + endpoint,
                          data=json.dumps(data, ensure_ascii=False).encode(),
                          headers=self.headers, method='POST')
            with build_opener(NoRedirect()).open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError('HTTP 状态异常，结果不确定，不自动重试')
                raw = response.read(1024 * 1024 + 1)
            if not raw or len(raw) > 1024 * 1024:
                raise TaskError('响应为空或过大，结果不确定')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise TaskError('响应结构未知')
            identities(result, self.secrets)
            if (type(result.get('code')) is not int or result['code'] != 0
                    or result.get('success') is False or result.get('error') or result.get('errors')):
                raise TaskError('接口未明确确认业务成功，不自动重试')
            log(f'✅ 请求 {endpoint}：业务 code=0；耗时 {time.monotonic() - started:.3f} 秒')
            return result
        except TaskError:
            raise
        except Exception:
            raise TaskError('网络、HTTP 或解析失败，结果不确定，不自动重试') from None

    def score(self):
        result = self.call('personal/score/info',
                           {'orderBy': 'release_desc', 'requestType': '2', 'siteId': self.site})
        data = result.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
            raise TaskError('积分及任务响应结构变化')
        if any(not isinstance(job, dict) for job in data['jobs']):
            raise TaskError('任务列表结构变化')
        return data

    def records(self, video=False, size=10, page=1):
        channel = 'd7036c2839e047b48fe64bc36987650c' if video else 'a978f44b3e284e5e86777f9d4e3be7bb'
        result = self.call('news/content/list', self.common(channel={'id': channel}, pageNo=page, pageSize=size))
        data = result.get('data')
        records = data.get('records') if isinstance(data, dict) else None
        if not isinstance(records, list) or any(not isinstance(x, dict) or not x.get('id') for x in records):
            raise TaskError('内容列表结构无效')
        return records


def progress(job):
    try:
        values = [int(job['progress']), int(job['totalProgress'])]
        if any(str(v) != str(job[k]) for v, k in zip(values, ('progress', 'totalProgress'))):
            raise ValueError()
        if not 0 <= values[0] <= values[1] <= 1000:
            raise ValueError()
        return values
    except Exception:
        raise TaskError('任务进度缺失或格式无效，禁止猜测执行次数') from None


def show_score(data, secrets):
    # 不输出原始任务标题/摘要，避免服务端错误内容携带凭据。
    for key, label in [('totalScore', '总积分'), ('todayPoint', '今日积分'),
                       ('todayIncreasePoint', '今日新增积分')]:
        value = data.get(key)
        if type(value) in (int, float) and math.isfinite(value):
            log(f'{label}：{value}')
    title = data.get('signTitle')
    if isinstance(title, str) and not any(x and x in title for x in secrets) and not re.search(r'1[3-9]\d{9}', title):
        log('签到状态：' + json.dumps(title, ensure_ascii=False))
    jobs = data['jobs']
    log(f'任务统计：总数 {len(jobs)}，已完成 {sum(str(j.get("status")) == "1" for j in jobs)}')
    for action, (task_id, label, _) in ACTIONS.items():
        for job in jobs:
            if str(job.get('id')) == task_id:
                current, total = progress(job)
                log(f'{label}任务：进度 {current}/{total}，{"已完成" if str(job.get("status")) == "1" else "待完成"}')


def run_action(api, action, job, local, unfavor):
    _, label, delay = ACTIONS[action]
    current, total = progress(job)
    remaining = total - current
    if remaining <= 0:
        raise TaskError('任务未完成但进度已满，状态冲突')
    if action == 'comment':
        records = []
        for page in (1, 2):
            records.extend(api.records(page=page))
            if page == 1:
                time.sleep(random.uniform(1, 2))
        # 去重，避免重复评论相同内容。
        records = list({str(x['id']): x for x in records}.values())
        records = random.sample(records, min(remaining, len(records)))
    else:
        records = api.records(video=action == 'video', size=remaining)[:remaining]
    if len(records) < remaining:
        raise TaskError('可用内容数量不足，停止该动作，不虚报完成')
    for index, record in enumerate(records, 1):
        content_id = record['id']
        started = time.monotonic()
        log(f'{label} / 步骤 {index}/{remaining}：开始')
        if action in ('read', 'share'):
            api.call('common/count/usage/inc', api.common(countType='contentRead', id=content_id))
            api.call(f'points/{action}/add', api.common())
        elif action == 'video':
            api.call('multimedia/drama/get', api.common(id=content_id))
            api.call('points/video/add', api.common())
        elif action == 'favor':
            api.call('news/content/favor', {'id': content_id})
            if unfavor:
                time.sleep(random.uniform(1, 2))
                api.call('news/content/disfavor', {'id': content_id})
        elif action == 'comment':
            api.call('common/comment/add', {'displayResources': [], 'content': comment_text(local),
                                          'targetType': 'content', 'targetId': content_id})
        log(f'✅ {label} / 步骤 {index}/{remaining}：接口确认完成，耗时 {time.monotonic() - started:.3f} 秒')
        if index < remaining:
            time.sleep(random.uniform(*delay))


def points_main():
    start = time.monotonic()
    dry = os.environ.get('SHYP_POINTS_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    lines = [x.strip() for x in os.environ.get('SHYP_POINTS_ACCOUNTS', '').splitlines() if x.strip()]
    enabled = os.environ.get('SHYP_POINTS_ENABLE', '0') == '1'
    results = []
    config_error = False
    interrupted = False
    log('=' * 50)
    log(f'{POINTS_TITLE} | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式：{"断网预演" if dry else "真实执行"}；账号数量：{len(lines)}；积分动作：{"已启用" if enabled else "仅查询"}')
    try:
        stage = time.monotonic()
        log('阶段 1：检查全局参数')
        if not lines:
            raise TaskError('必须配置 SHYP_POINTS_ACCOUNTS，每行一个账号 JSON 对象')
        timeout = number('SHYP_POINTS_TIMEOUT', '30', 1, 60)
        actions = list(dict.fromkeys(x.strip() for x in os.environ.get('SHYP_POINTS_ACTIONS', 'read,video,favor,comment,share').split(',')))
        if not actions or any(x not in ACTIONS for x in actions):
            raise TaskError('SHYP_POINTS_ACTIONS 仅支持 read,video,favor,comment,share')
        local = normalized(os.environ.get('SHYP_POINTS_LOCAL_TEXT', ''))
        if len(local) > 280:
            raise TaskError('本地评论文字不能超过 280 字')
        unfavor = os.environ.get('SHYP_POINTS_UNFAVOR', '0') == '1'
        log(f'阶段 1：通过，耗时 {time.monotonic() - stage:.3f} 秒')
        for index, line in enumerate(lines, 1):
            account_start = time.monotonic()
            stats = {'account': index, 'total': 1 + len(actions), 'success': 0,
                     'alreadyComplete': 0, 'skipped': 0, 'failed': 0, 'ok': False}
            results.append(stats)
            try:
                log(f'账号 {index} / 阶段 2：检查配套凭据')
                try:
                    account = json.loads(line)
                    if not isinstance(account, dict):
                        raise ValueError()
                    for field in ('token', 'device_id', 'site_id', 'user_agent'):
                        if field in ('token', 'device_id') or field in account:
                            value = account.get(field)
                            if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) > 255 for c in value):
                                raise ValueError()
                except Exception:
                    raise TaskError('账号 JSON 或 token/device_id 配套凭据格式错误') from None
                if dry:
                    log('DRY_RUN_OK：积分凭据及查询、阅读、视频、收藏、评论、分享流程预演通过；未发 HTTP、未修改状态')
                    log('账号 / 阶段 3：预演跳过积分查询；阶段 4：预演跳过所选动作及文字服务；阶段 5：预演跳过最终核验')
                    stats['skipped'] = stats['total']
                else:
                    api = PointsAPI(account, timeout)
                    stage = time.monotonic()
                    log(f'账号 {index} / 阶段 3：查询积分、签到状态及任务')
                    before = api.score()
                    show_score(before, api.secrets)
                    stats['success'] += 1
                    log(f'阶段 3：查询完成，耗时 {time.monotonic() - stage:.3f} 秒')
                    pending = []
                    for action_index, action in enumerate(actions, 1):
                        stage = time.monotonic()
                        task_id, label, _ = ACTIONS[action]
                        log(f'账号 {index} / 阶段 4.{action_index}：{label}')
                        matches = [j for j in before['jobs'] if str(j.get('id')) == task_id]
                        if not enabled:
                            stats['skipped'] += 1
                            log('⏭️ 未显式启用积分动作，跳过')
                        elif len(matches) != 1:
                            stats['failed'] += 1
                            log('❌ 任务缺失或重复，不推测接口')
                        elif str(matches[0].get('status')) == '1':
                            stats['alreadyComplete'] += 1
                            log('☑️ 服务端确认任务已完成')
                        else:
                            try:
                                run_action(api, action, matches[0], local, unfavor)
                                pending.append(action)
                            except TaskError as error:
                                stats['failed'] += 1
                                log('❌ ' + str(error))
                        log(f'阶段 4.{action_index}：结束，耗时 {time.monotonic() - stage:.3f} 秒')
                        if enabled and action_index < len(actions):
                            time.sleep(random.uniform(5, 10))
                    stage = time.monotonic()
                    log(f'账号 {index} / 阶段 5：刷新并核验任务完成情况')
                    if enabled:
                        time.sleep(random.uniform(5, 10))
                        after = api.score()
                        show_score(after, api.secrets)
                        for action in pending:
                            task_id, label, _ = ACTIONS[action]
                            matches = [j for j in after['jobs'] if str(j.get('id')) == task_id]
                            if len(matches) == 1 and str(matches[0].get('status')) == '1':
                                stats['success'] += 1
                                log(f'✅ {label}：刷新后业务确认完成')
                            else:
                                stats['failed'] += 1
                                log(f'❌ {label}：刷新后未确认完成')
                    else:
                        log('☑️ 只读查询成功，无积分动作需要核验')
                    log(f'阶段 5：结束，耗时 {time.monotonic() - stage:.3f} 秒')
                stats['ok'] = stats['failed'] == 0
            except TaskError as error:
                log('❌ ' + str(error))
            except Exception:
                log('❌ 账号处理或响应结构异常，未确认任务按失败计入')
            finally:
                counted = stats['success'] + stats['alreadyComplete'] + stats['skipped'] + stats['failed']
                stats['failed'] += max(0, stats['total'] - counted)
                stats['ok'] = stats['failed'] == 0
                stats['seconds'] = round(time.monotonic() - account_start, 3)
                log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["seconds"]} 秒')
            if not dry and index < len(lines):
                time.sleep(random.uniform(5, 10))
    except KeyboardInterrupt:
        interrupted = True
        log('❌ 用户中断，未确认成功的任务按失败计入')
    except Exception as error:
        config_error = True
        log('❌ 配置错误：' + (str(error) if isinstance(error, TaskError) else '参数数值或格式无效'))
    successes = sum(r['ok'] for r in results)
    failures = len(lines) - successes
    exit_code = int(config_error or interrupted or failures > 0)
    status = 'configuration-error' if config_error else 'partial-failure' if successes and failures else 'failure' if exit_code else 'dry-run' if dry else 'success'
    log('-' * 50)
    body = f'{POINTS_TITLE}；状态：{status}；账号总数：{len(lines)}；成功数：{successes}；失败数：{failures}；模式：{"预演，不代表业务成功" if dry else "真实执行"}'
    log(body)
    log('子任务统计：' + '，'.join(f'{label} {sum(r[key] for r in results)}' for key, label in [('total', '总数'), ('success', '成功'), ('alreadyComplete', '已完成'), ('skipped', '跳过'), ('failed', '失败')]))
    notification = notify(body, dry, POINTS_TITLE)
    finish = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f'完成时间：{finish}；总耗时：{time.monotonic() - start:.3f} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': 'points', 'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(lines), 'success': successes, 'failed': failures, 'results': results,
          'notification': notification, 'finishTime': finish, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


def main():
    task = os.environ.get('SHYP_TASK', 'buy')
    if task == 'buy':
        return buy_main()
    if task == 'points':
        return points_main()
    # 错误模式也必须汇总及通知，但不得执行其他任务。
    dry = any(os.environ.get(key, '0').lower() in {'1', 'true', 'yes', 'on'}
              for key in ('SHYP_BUY_DRY_RUN', 'SHYP_POINTS_DRY_RUN'))
    log('=' * 50)
    log(f'{TITLE} | 开始时间 {datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'模式：{"断网预演" if dry else "真实执行"}；账号数量：0')
    log('阶段 1：❌ SHYP_TASK 必须是 buy 或 points；耗时 0 秒')
    body = '配置错误；账号总数：0；成功数：0；失败数：0'
    log('-' * 50)
    log(body)
    log('子任务统计：总数 0，成功 0，已完成 0，跳过 0，失败 0')
    notification = notify(body, dry)
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：configuration-error')
    print('TASK_SUMMARY=' + json.dumps({'status': 'configuration-error', 'accounts': 0,
          'success': 0, 'failed': 0, 'notification': notification, 'exitCode': 1}, separators=(',', ':')))
    return 1


if __name__ == '__main__':
    sys.exit(main())
