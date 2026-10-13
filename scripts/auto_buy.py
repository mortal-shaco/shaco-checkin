#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 上海杨浦商城定时抢购
# cron: 0 0 10 * * *
"""
定时抢购脚本：用于在指定时间自动抢购商品。
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
import json
import math
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


def notify(body, dry):
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
        result = subprocess.run([sys.executable, '-c', code, TITLE, body], capture_output=True, timeout=30, check=False)
        ok = result.returncode == 0
    except Exception:
        ok = False
    log('通知状态：已发送' if ok else '通知状态：不可用或发送失败，保留业务退出码')
    return 'sent' if ok else 'unavailable'


def main():
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


if __name__ == '__main__':
    sys.exit(main())
