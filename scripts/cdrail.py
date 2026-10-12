#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 成都地铁签到
# cron: 0 9 * * *
# 来源: agluo/ql-script-hub/CDRail.py (MIT)
# 源提交: a8d39b97cb22c3ac657089014df754342b456ff6
# 保留上游 MIT 授权和署名；上游输入未附带版权年份及完整许可证文本。
"""成都地铁签到，Python 3 标准库即可运行。
CDRAIL_DATA 每个非空行一个 JSON 对象（推荐）或 URL 编码查询字符串。
在本人已登录成都地铁 App 的签到请求中提取 token、app-token、Cookie，
以及实际 deviceId/device-id 和需要的其他请求头；不要分享抓包内容。
查询字符串以 & 分字段、以第一个 = 分键值，值中的 & 必须编码为 %26。
账号仅以换行分隔，@ 是凭据内容。CDRAIL_DRY_RUN=1 完全断网预演。
TIMEOUT 默认15秒；RANDOM_SIGNIN 默认true；MAX_RANDOM_DELAY 默认3600秒。
MAX_RETRIES 不再重放具有签到副作用的请求，PRIVACY_MODE 不再允许泄露凭据。
QINGLONG_NOTIFY 默认1；可选 QINGLONG_NOTIFY_DIR 指向青龙通知模块目录。
"""
# MIT License
# Attribution: agluo/ql-script-hub contributors
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

import http.client
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import parse_qsl

TITLE = '成都地铁签到'
HOST = 'app.cdmetro.chengdurail.cn'
PATH = '/platform/users/user/sign-in-integral'
DISABLED = {'0', 'false', 'no', 'off'}
DEFAULT_HEADERS = {
    'system-version': '16.4.1', 'system': 'iOS', 'app-version': '3.5.6',
    'source': 'CD-METRO-APP', 'User-Agent': 'CDMetro/3.5.6 (iPhone; iOS 16.4.1; Scale/3.00)',
    'vendor': 'iPhone15,3', 'language': 'zh-Hans', 'Accept': '*/*',
    'Accept-Language': 'zh-Hans-US;q=1, en-US;q=0.9', 'user': 'external',
}


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def headers_for(line):
    if line.startswith('{'):
        data = json.loads(line)
    else:
        pairs = parse_qsl(line, keep_blank_values=True, strict_parsing=True)
        if len(dict(pairs)) != len(pairs):
            raise ValueError('duplicate')
        data = dict(pairs)
    if not isinstance(data, dict):
        raise ValueError('object')
    headers = {k.lower(): v for k, v in DEFAULT_HEADERS.items()}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('header')
        key = key.lower()
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", key) or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('header')
        value.encode('latin-1')
        key = {'apptoken': 'app-token', 'app_token': 'app-token', 'device_id': 'deviceid'}.get(key, key)
        if key in {'host', 'content-length', 'transfer-encoding', 'connection', 'accept-encoding'}:
            continue
        headers[key] = value
        if key in {'deviceid', 'device-id'}:
            headers['deviceid'] = headers['device-id'] = value
    if not headers.get('token', '').strip() or not headers.get('app-token', '').strip():
        raise ValueError('required')
    headers['accept-encoding'] = 'identity'
    return headers


def signin(headers, timeout):
    conn = http.client.HTTPSConnection(HOST, timeout=timeout)
    try:
        conn.request('GET', PATH, headers=headers)
        resp = conn.getresponse()
        if resp.status != 200:
            return 'failure', 'HTTP 请求失败', None
        raw = resp.read(1048577)
        if len(raw) > 1048576:
            return 'failure', '响应超过大小限制', None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return 'failure', '响应结构无效', None
        code = data.get('code')
        payload = data.get('data')
        identity = None
        if isinstance(payload, dict):
            for key in ('nickname', 'username', 'displayName', 'uid'):
                value = payload.get(key)
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    value = str(value)
                    # 防止凭据回显、手机号及控制字符进入日志。
                    if value and not re.search(r'[\x00-\x1f\x7f]|\+?\d{11,}', value) and not any(value == headers.get(k) for k in ('token', 'app-token', 'cookie', 'deviceid', 'device-id')):
                        identity = value
                        break
        if not isinstance(code, bool) and str(code) in {'0', '200', '000000'}:
            increment = payload.get('integralIncrement') if isinstance(payload, dict) else None
            detail = '签到成功'
            if isinstance(increment, (int, float)) and not isinstance(increment, bool):
                detail += f'，积分增加 {increment}'
            return 'success', detail, identity
        if str(code) == '1102':
            return 'already', '今日已签到', identity
        # 不以任意错误消息中包含“已签到”判断成功，避免否定句造成误判。
        return 'failure', '业务码未确认成功，请在 App 核对凭据或接口状态', identity
    finally:
        conn.close()


def notify(summary, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        log('通知预演：' + summary)
        return '预演完成（未发送网络通知）'
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.insert(0, Path(spec.origin))
    except Exception:
        pass
    for path in paths:
        if path.is_file():
            code = "import importlib.util,sys; s=importlib.util.spec_from_file_location('notify',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])"
            try:
                result = subprocess.run([sys.executable, '-c', code, str(path), TITLE, summary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                return '已发送' if result.returncode == 0 else '发送失败（保留业务退出码）'
            except Exception:
                return '发送失败（保留业务退出码）'
    return '通知模块不可用（保留业务退出码）'


def main():
    start = time.monotonic()
    dry = os.getenv('CDRAIL_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    lines = [line.strip() for line in os.getenv('CDRAIL_DATA', '').splitlines() if line.strip()]
    print('==== 成都地铁签到 ====')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：{"断网预演" if dry else "正式执行"}；账号数：{len(lines)}')
    counts = dict(success=0, already=0, skipped=0, failure=0)
    config_error = False
    try:
        timeout = int(os.getenv('TIMEOUT', '15'))
        delay = int(os.getenv('MAX_RANDOM_DELAY', '3600'))
        if not 1 <= timeout <= 120 or not 0 <= delay <= 86400:
            raise ValueError()
    except ValueError:
        timeout, delay = 15, 0
        config_error = True
        log('❌ 全局配置错误：TIMEOUT 应为1至120，MAX_RANDOM_DELAY 应为0至86400的整数')
    if not lines:
        config_error = True
        log('❌ 配置错误：CDRAIL_DATA 未设置有效账号行')
    for index, line in enumerate(lines, 1):
        began = time.monotonic()
        log(f'账号{index} 阶段1/2：解析并验证请求头')
        state, detail, identity = 'failure', '账号字段无效或缺少 token/app-token', None
        try:
            headers = headers_for(line)
            log(f'账号{index} 阶段1/2：参数检查通过，耗时 {time.monotonic()-began:.2f}秒')
            stage = time.monotonic()
            log(f'账号{index} 阶段2/2：签到')
            if config_error:
                detail = '全局配置错误，未发送请求'
            elif dry:
                state, detail = 'skipped', 'DRY_RUN_OK：参数通过，模拟签到及通知，不请求网络、不等待'
            else:
                if index == 1 and os.getenv('RANDOM_SIGNIN', 'true').lower() == 'true' and delay:
                    wait = random.randint(0, delay)
                    log(f'随机延迟 {wait}秒')
                    while wait:
                        interval = min(wait, 60)
                        time.sleep(interval)
                        wait -= interval
                        log(f'随机等待剩余 {wait}秒')
                state, detail, identity = signin(headers, timeout)
            log(f'账号{index} 阶段2/2：{detail}；耗时 {time.monotonic()-stage:.2f}秒')
        except (ValueError, TypeError, UnicodeError):
            log(f'账号{index} ❌ 参数或响应格式无效（已隐藏原文）')
        except Exception:
            detail = '网络或处理异常，未确认成功；不自动重放签到请求'
            log(f'账号{index} ❌ {detail}')
        if identity:
            log(f'账号{index} 官方账号身份：{identity}')
        counts[state] += 1
        log(f'账号{index} 统计：总任务1，成功{int(state=="success")}，已完成{int(state=="already")}，跳过{int(state=="skipped")}，失败{int(state=="failure")}；耗时 {time.monotonic()-began:.2f}秒')
        if not dry and not config_error and index < len(lines):
            time.sleep(random.uniform(3, 8))
    failed = counts['failure']
    passed = counts['success'] + counts['already']
    status = 'configuration-error' if config_error else ('partial-failure' if failed and passed else 'failure' if failed else 'dry-run' if dry else 'success')
    exit_code = int(config_error or failed > 0)
    summary = f'账号总数{len(lines)}，成功{passed}，失败{failed}，预演跳过{counts["skipped"]}，状态{status}'
    notification = notify(summary, dry)
    print('----------------------------------------')
    log(summary)
    log(f'子任务统计：{json.dumps(counts, ensure_ascii=False)}')
    log(f'通知状态：{notification}；总耗时 {time.monotonic()-start:.2f}秒；完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines), 'successfulAccounts': passed, 'failedAccounts': failed, 'tasks': counts, 'status': status, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
