#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 鸿星尔克签到
# cron: 12 1 1 1 1
"""鸿星尔克签到；Author: ZaiZaiCat；Date: 2025-11-28。
来源：Cat-zaizai/ZaiZaiCat-Checkin，script/erke/main.py、api.py。
维护版：ERKE_ACCOUNTS 每个非空行为一个 JSON 对象，包含 member_id、
enterprise_id、unionid、openid、wx_openid；可选 account_name、user_agent。
在本人登录的鸿星尔克小程序中，从 integral_record.json 或
sign/member_sign.json 请求体获取上述五项字段，不要公开凭据。
原 config/token.json 的 erke.accounts 对象可逐个复制为 JSON 行；不再读取私有文件。
ERKE_DRY_RUN=1 完全断网预演；原 cron 保留，用户可在青龙中自行调整。
仅签到改变账号状态，不发帖、不分享、不消费积分。

MIT License (上游许可；保留上游作者归属)
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
import datetime as dt
import hashlib
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

TITLE = '鸿星尔克签到'
FIELDS = ('member_id', 'enterprise_id', 'unionid', 'openid', 'wx_openid')
APPID = 'wxa1f1fa3785a47c7d'
BASE = 'https://hope.demogic.com/gic-wx-app'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 '
      'MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI '
      'MiniProgramEnv/Windows WindowsWechat/WMPF '
      'WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541510) XWEB/17071')
TZ = dt.timezone(dt.timedelta(hours=8))
DISABLED = {'0', 'false', 'no', 'off'}


def stamp():
    return dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')


def log(message):
    print(f'[{stamp()[11:]}] {message}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向已拒绝，避免凭据跨地址传递')


def request(account, sign_in, dry=False):
    timestamp = stamp()
    nonce = random.randint(0, 9999999)
    trans = APPID + timestamp
    value = (f'timestamp={timestamp}transId={trans}secret=damogic8888'
             f'random={nonce}memberId={account["member_id"]}')
    signature = hashlib.md5(value.encode()).hexdigest()
    payload = {
        'memberId': account['member_id'], 'enterpriseId': account['enterprise_id'],
        'unionid': account['unionid'], 'openid': account['openid'],
        'wxOpenid': account['wx_openid'], 'cliqueId': '-1', 'cliqueMemberId': '-1',
        'useClique': 0 if sign_in else '0', 'random': nonce, 'appid': APPID,
        'transId': trans, 'sign': signature, 'timestamp': timestamp,
        'gicWxaVersion': '3.9.56',
        'launchOptions': '{"path":"pages/authorize/authorize","query":{},"scene":1101,"referrerInfo":{},"apiCategory":"default"}'
    }
    if sign_in:
        payload['source'] = 'wxapp'
        path = '/sign/member_sign.json'
        content_type = 'application/json;charset=UTF-8'
        data = json.dumps(payload).encode()
    else:
        payload.update(currentPage=1, pageSize=5)
        path = '/integral_record.json'
        content_type = 'application/x-www-form-urlencoded'
        data = urllib.parse.urlencode(payload).encode()
    headers = {
        'User-Agent': account.get('user_agent') or UA, 'Content-Type': content_type,
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache',
        'sign': account['enterprise_id'], 'channelEntrance': 'wx_app', 'xweb_xhr': '1',
        'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://servicewechat.com/{APPID}/85/page-frame.html',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    }
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method='POST')
    if dry:
        return req
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
        if len(raw) > 1024 * 1024:
            raise TaskError('响应过大')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TaskError('响应结构异常')
        return result
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应 JSON 或请求参数格式异常') from None


def business_status(result, sign_in):
    code = str(result.get('code', '')).strip()
    message = result.get('message', '')
    if result.get('success') is False:
        raise TaskError('业务接口明确返回失败')
    if sign_in and code == '1001' and isinstance(message, str) and '已签到' in message and not any(x in message for x in ('未', '失败', '不能')):
        return 'already'
    if code not in {'0000', '0', '200'}:
        raise TaskError('业务成功码未确认，请核对小程序接口和凭据')
    return 'success'


def identity(result, account):
    containers = [result, result.get('response')]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ('nickname', 'nickName', 'username', 'displayName', 'publicUid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                text = str(value)
                # 身份原样展示；拒绝手机号、控制符或与凭据相同的值。
                if text and not re.search(r'[\r\n\x00-\x1f]|(?<!\d)1[3-9]\d{9}(?!\d)', text) and not any(str(account[k]) in text for k in FIELDS):
                    log(f'官方账号身份：{text}')


def notify(body, dry):
    if os.getenv('QINGLONG_NOTIFY', '1').strip().lower() in DISABLED:
        return '已关闭'
    if dry:
        return '断网预演：通知摘要已生成，未调用通知渠道'
    # 隔离通知模块的输出和异常，避免影响业务退出码；子进程限制耗时。
    loader = '''import importlib.util,json,sys
module_path=sys.argv[1]
if module_path:
 spec=importlib.util.spec_from_file_location("ql_task_notify",module_path)
 module=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(module)
else:
 import notify as module
payload=json.loads(sys.stdin.read())
module.send(payload["title"],payload["body"])
'''
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR')
    if directory:
        paths.append(Path(directory) / 'notify.py')
    paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    choices = [''] + [str(p) for p in paths if p.is_file()]
    for path in choices:
        try:
            completed = subprocess.run([sys.executable, '-c', loader, path],
                                       input=json.dumps({'title': TITLE, 'body': body}),
                                       text=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=20, check=False)
            if completed.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    js_paths = ([Path(directory) / 'sendNotify.js'] if directory else []) + [Path('/ql/data/scripts/sendNotify.js'), Path('/ql/scripts/sendNotify.js')]
    for path in js_paths:
        if not path.is_file():
            continue
        try:
            result = subprocess.run(['node', '-e', 'let b="";process.stdin.on("data",x=>b+=x);process.stdin.on("end",async()=>{try{const p=JSON.parse(b);await require(process.argv[1]).sendNotify(p.title,p.body);}catch(e){process.exitCode=1;}});', str(path)], input=json.dumps({'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '不可用或发送失败（保留业务退出码）'


def parse_account(line):
    try:
        account = json.loads(line)
    except ValueError:
        raise TaskError('账号必须为单行 JSON 对象') from None
    if not isinstance(account, dict) or any(not isinstance(account.get(k), str) or not account[k].strip() for k in FIELDS):
        raise TaskError('账号缺少五项非空字符串凭据')
    if any('\r' in account[k] or '\n' in account[k] for k in FIELDS):
        raise TaskError('凭据包含不允许的换行')
    if 'user_agent' in account and (not isinstance(account['user_agent'], str) or re.search(r'[\r\n\x00]', account['user_agent'])):
        raise TaskError('user_agent 参数格式异常')
    return account


def run():
    started = time.monotonic()
    dry = os.getenv('ERKE_DRY_RUN', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    lines = [line.strip() for line in os.getenv('ERKE_ACCOUNTS', '').splitlines() if line.strip()]
    log('=' * 60)
    log(f'{TITLE} | 开始时间：{stamp()} | 模式：{"断网预演" if dry else "正式执行"} | 账号数：{len(lines)}')
    totals = dict(success=0, already=0, skipped=0, failed=0)
    results = []
    config_error = not lines
    if not lines:
        log('❌ 配置错误：请设置 ERKE_ACCOUNTS')
    for index, line in enumerate(lines, 1):
        begin = time.monotonic()
        counts = dict(success=0, already=0, skipped=0, failed=0)
        log(f'账号 {index} 开始')
        try:
            account = parse_account(line)
        except TaskError as exc:
            config_error = True
            counts['failed'] = 1
            counts['skipped'] = 2
            log(f'❌ 账号 {index} 配置错误：{exc}')
        else:
            for stage, sign_in in enumerate((False, True), 1):
                stage_start = time.monotonic()
                name = '会员签到' if sign_in else '积分明细查询'
                log(f'账号 {index} 阶段 {stage}/2：{name}')
                try:
                    if dry:
                        request(account, sign_in, dry=True)
                        counts['skipped'] += 1
                        log('⏭️ DRY_RUN_OK：参数、请求结构和签名可构造；未发送请求，未确认业务成功')
                    else:
                        data = request(account, sign_in)
                        status = business_status(data, sign_in)
                        identity(data, account)
                        if not sign_in:
                            info = data.get('response')
                            if not isinstance(info, dict):
                                raise TaskError('积分响应缺少 response 对象')
                            accumulate = info.get('accumulatPoints')
                            frozen = info.get('frozenPoints')
                            if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (accumulate, frozen)):
                                raise TaskError('积分响应缺少有效累计积分或冻结积分')
                            log(f'累计积分：{accumulate}；冻结积分：{frozen}；可用积分：{accumulate - frozen}')
                            page = info.get('page')
                            if isinstance(page, dict) and isinstance(page.get('totalCount'), int):
                                log(f'积分记录数：{page["totalCount"]}')
                        counts[status] += 1
                        log('☑️ 已签到' if status == 'already' else f'✅ {name}成功（业务码已核验）')
                except TaskError as exc:
                    counts['failed'] += 1
                    log(f'❌ {name}失败：{exc}')
                except Exception:
                    counts['failed'] += 1
                    log(f'❌ {name}失败：执行异常（详细内容已脱敏隐藏）')
                log(f'账号 {index} 阶段 {stage} 耗时：{time.monotonic() - stage_start:.2f} 秒')
        ok = counts['failed'] == 0
        for key in totals:
            totals[key] += counts[key]
        results.append({'account': index, 'ok': ok, **counts})
        log(f'账号 {index} 统计：总任务 {sum(counts.values())}，成功 {counts["success"]}，已完成 {counts["already"]}，跳过 {counts["skipped"]}，失败 {counts["failed"]}，耗时 {time.monotonic() - begin:.2f} 秒')
    failed = sum(not r['ok'] for r in results)
    passed = len(results) - failed
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and passed else
              'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if config_error or failed else 0
    body = f'模式：{"断网预演" if dry else "正式执行"}；状态：{status}；账号总数 {len(lines)}，成功 {passed}，失败 {failed}；子任务成功 {totals["success"]}，已完成 {totals["already"]}，跳过 {totals["skipped"]}，失败 {totals["failed"]}'
    log('-' * 60)
    log(body)
    delivery = notify(body, dry)
    finished = stamp()
    log(f'通知：{delivery}；总耗时：{time.monotonic() - started:.2f} 秒；完成时间：{finished}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines), 'successfulAccounts': passed, 'failedAccounts': failed, 'steps': totals, 'results': results, 'notification': delivery, 'finishedAt': finished, 'exitCode': code}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(run())
