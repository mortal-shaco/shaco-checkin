#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 微微免费电话签到
# cron: 33 10 * * *
# 上游：Jim6699/Python_scripts，微微免费电话/qiandao.py
# 来源提交：3b17c42aac3604cc842c6c94821603699f0bd071；许可证：MIT
# Copyright (c) Jim6699
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
"""微微免费电话每日签到（仅标准库）。
WEWE_ACCOUNTS：每个非空行填写一个从本人 App 签到请求中取得的 userId。
原脚本没有定时声明；建议每天 08:00。关联 recall.py 会拨打电话，不合并。
上游仅给出 HTTP 地址，未验证 HTTPS 或响应契约，不擅自替换接口。
正式运行须自行评估并设置 WEWE_ALLOW_INSECURE_HTTP=1；默认不传输凭据。
WEWE_REPORT_SIGNIN=1 可恢复原有匿名签到事件上报；默认关闭非必要上报。
WEWE_DRY_RUN=1 完全断网，仅验证配置、展示计划和生成通知摘要。
PushPlus 可选 PUSHPLUS_TOKEN；通知正文只含统计，不含账号及接口原文。
未提供真实成功响应样本：仅接受明确签到成功/已签到文本；未知响应失败闭合。
"""
# qinglong-notification-policy: begin
import fnmatch as _ql_notify_fnmatch
import os as _ql_notify_os
import re as _ql_notify_re
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('fa764c990d2fb7f6', 'scripts/qiandao.py', 'qiandao.py', 'qiandao')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import datetime
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = '微微免费电话签到'
CATALOG = 'fa764c990d2fb7f6'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SIGN_URL = 'http://xconfig.uwewe.cn/sign/signvideoClient'
REPORT_URL = 'http://xreport.uwewe.cn/click/add'
MAX_BYTES = 65536


def enabled(name):
    value = os.getenv(name, '0').strip().lower()
    if value not in TRUE | FALSE:
        raise ValueError('开关配置无效：' + name)
    return value in TRUE


def log(message):
    print(time.strftime('[%H:%M:%S] ') + message, flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不跟随重定向，避免凭据被转发到未知地址。
        return None


def post(url, fields, timeout, as_json=False):
    payload = (json.dumps(fields).encode('utf-8') if as_json else
               urllib.parse.urlencode(fields).encode('utf-8'))
    req = urllib.request.Request(url, data=payload, headers={
        'User-Agent': 'Mozilla/5.0 (Linux; Android 9) AppleWebKit/537.36 Mobile Safari/537.36',
        'Content-Type': 'application/json' if as_json else 'application/x-www-form-urlencoded',
        'Accept-Language': 'zh-CN,zh;q=0.8',
    }, method='POST')
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('响应超过大小限制')
        return raw.decode('utf-8-sig')


def sign_result(text):
    """不以 HTTP 200、任意 msg 字段或原文包含关键字直接当作成功。"""
    message = text.strip()
    data = None
    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        pass
    if isinstance(data, dict):
        if data.get('success') is False:
            return 'failed'
        for key in ('code', 'ret', 'status'):
            if key in data and str(data[key]) not in {'0', '200', 'success', 'ok', 'true', 'True'}:
                return 'failed'
        message = next((data[k] for k in ('msg', 'message', 'Message')
                        if isinstance(data.get(k), str)), '')
    elif data is not None:
        return 'failed'
    message = message.strip().rstrip('!！。')
    if message in {'签到成功', '今日签到成功', '今天签到成功'}:
        return 'success'
    if message in {'已签到', '今日已签到', '今天已签到', '今日已签过到'}:
        return 'already'
    return 'failed'


def show_identity(text, credentials):
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return
        containers = [data]
        if isinstance(data.get('data'), dict):
            containers.append(data['data'])
        for item in containers:
            for key in ('nickname', 'nickName', 'username', 'displayName', 'publicUid'):
                value = item.get(key)
                if isinstance(value, (str, int)):
                    value = str(value)
                    # 身份按原值显示；疑似手机号、凭据、控制字符则不输出。
                    if (len(value) <= 128 and value and not any(c in value for c in credentials)
                            and not re.search(r'\d{11,}|[\x00-\x1f\x7f]', value)
                            and not re.search(r'cookie|token|session|authorization', value, re.I)):
                        log('官方账号身份：' + value)
                        return
    except (ValueError, TypeError):
        return


NOTIFY_CHILD = r'''
import importlib.util, json, sys
source, title, body = sys.argv[1:]
if source == '@import':
    import notify
else:
    spec = importlib.util.spec_from_file_location('notify', source)
    notify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notify)
notify.send(title, body)
'''


def notify_summary(body, dry_run):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '开关无效，未发送'
    selected = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if switch == 'auto' and selected is not None:
        selectors = [s for s in re.split(r'[,;\s]+', selected) if s]
        names = [CATALOG, Path(__file__).name, 'candidate.py', 'qiandao.py',
                 '微微免费电话/qiandao.py']
        if not any(fnmatch.fnmatch(n, s) for n in names for s in selectors):
            return '未选中'
    if dry_run:
        log('通知摘要（断网预演，不调用通知网络）：' + body)
        return '预演已生成，未联网投递'
    sources = []
    try:
        if importlib.util.find_spec('notify') is not None:
            sources.append('@import')
    except (ValueError, ImportError):
        pass
    roots = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        roots.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    roots.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    sources.extend(str(root / 'notify.py') for root in roots if (root / 'notify.py').is_file())
    for source in dict.fromkeys(sources):
        try:
            result = subprocess.run([sys.executable, '-c', NOTIFY_CHILD, source, TITLE, body],
                                    capture_output=True, timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    for root in roots:
        path = root / 'sendNotify.js'
        if not path.is_file():
            continue
        try:
            code = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
            result = subprocess.run(['node', '-e', code, str(path), TITLE, body],
                                    capture_output=True, timeout=30, check=False)
            if result.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '不可用或投递失败（业务退出码不变）'


def main():
    started = time.monotonic()
    accounts = [line.strip() for line in os.getenv('WEWE_ACCOUNTS', '').splitlines() if line.strip()]
    dry = os.getenv('WEWE_DRY_RUN', '0').strip().lower() in TRUE
    results = []
    config_error = False
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + datetime.datetime.now().isoformat(timespec='seconds'))
    log('模式：' + ('断网预演' if dry else '正式运行') + '；账号数：' + str(len(accounts)))
    try:
        dry = enabled('WEWE_DRY_RUN')
        report = enabled('WEWE_REPORT_SIGNIN')
        allow_http = enabled('WEWE_ALLOW_INSECURE_HTTP')
        timeout = float(os.getenv('WEWE_TIMEOUT', '15'))
        if not 1 <= timeout <= 60:
            raise ValueError('WEWE_TIMEOUT 必须为 1 至 60 秒')
        if not accounts:
            raise ValueError('缺少 WEWE_ACCOUNTS；每个非空行填写一个 userId')
        if any(any(ord(c) < 32 or ord(c) == 127 for c in account) for account in accounts):
            raise ValueError('账号包含控制字符')
        if not dry and not allow_http:
            raise ValueError('上游仅提供明文 HTTP；默认停止。知悉风险后显式设置 WEWE_ALLOW_INSECURE_HTTP=1')
    except ValueError as exc:
        config_error = True
        # 仅输出本地固定错误；不回显配置值或异常中的网络正文。
        log('❌ 配置错误：' + str(exc))
    if not config_error:
        for number, account in enumerate(accounts, 1):
            account_start = time.monotonic()
            stats = dict(total=2 if report else 1, success=0, already=0, skipped=0, failed=0)
            log('----- 账号 ' + str(number) + ' -----')
            step = time.monotonic()
            log('阶段 1/2：签到事件上报')
            if not report:
                log('⏭️ 非必要上报默认关闭；耗时 0.00 秒')
            elif dry:
                stats['skipped'] += 1
                log('⏭️ 预演：计划上报，不发送请求；耗时 0.00 秒')
            else:
                try:
                    post(REPORT_URL, {'event': 'signin', 'place': 'WebActivity',
                         'time': time.strftime('%Y-%m-%d%H:%M:%S'), 'type': '签到',
                         'typeEN': 'signin', 'plat': 'android', 'version': '10011'}, timeout)
                    # 原始来源未提供事件接口成功契约，不能冒充业务成功。
                    stats['failed'] += 1
                    log('⚠️ 事件已提交，但响应成功契约未知，标记未核实')
                except Exception:
                    stats['failed'] += 1
                    log('❌ 事件上报失败（详细响应已隐藏）')
                log('阶段 1 耗时 %.2f 秒' % (time.monotonic() - step))
            step = time.monotonic()
            log('阶段 2/2：每日签到')
            if dry:
                stats['skipped'] += 1
                log('⏭️ 预演：账号配置有效，计划提交签到；未执行 HTTP')
            else:
                try:
                    text = post(SIGN_URL, {'userId': account, 'extra': 'android-10011-102'}, timeout)
                    show_identity(text, accounts)
                    outcome = sign_result(text)
                    if outcome == 'success':
                        stats['success'] += 1
                        log('✅ 签到成功（明确业务消息）')
                    elif outcome == 'already':
                        stats['already'] += 1
                        log('☑️ 今日已签到（明确业务消息）')
                    else:
                        stats['failed'] += 1
                        log('❌ 未确认签到成功；业务失败或未知响应格式，未输出原文')
                except Exception:
                    stats['failed'] += 1
                    log('❌ 签到请求失败（网络、超时或响应解析异常；详情已隐藏）')
            log('阶段 2 耗时 %.2f 秒' % (time.monotonic() - step))
            stats['account'] = number
            stats['durationSeconds'] = round(time.monotonic() - account_start, 2)
            results.append(stats)
            log(('账号 ' + str(number) + ' 统计：总任务 %(total)d，成功 %(success)d，已完成 %(already)d，跳过 %(skipped)d，失败 %(failed)d，耗时 %(durationSeconds).2f 秒') % stats)
    failed = sum(r['failed'] > 0 for r in results)
    successful = sum(r['failed'] == 0 for r in results) if not dry else 0
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and successful
              else 'failure' if failed else 'dry-run' if dry else 'success')
    body = '账号总数 %d，成功 %d，失败 %d，预演 %d，状态 %s' % (
        len(accounts), successful, failed, len(results) if dry else 0, status)
    notification = notify_summary(body, dry)
    push_status = '未配置'
    push_token = os.getenv('PUSHPLUS_TOKEN', '').strip()
    if push_token:
        if dry:
            push_status = '断网预演，未投递'
        elif os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower() in FALSE:
            push_status = '已关闭'
        else:
            try:
                reply = json.loads(post('https://www.pushplus.plus/send',
                     {'token': push_token, 'title': TITLE, 'content': body, 'template': 'txt'}, 15, True))
                push_status = '已发送' if isinstance(reply, dict) and reply.get('code') == 200 else '投递未确认'
            except Exception:
                push_status = '投递失败'
    totals = {k: sum(r[k] for r in results) for k in ('total', 'success', 'already', 'skipped', 'failed')}
    log('----------------------------------------')
    log(body)
    log('子任务统计：总数 {total}，成功 {success}，已完成 {already}，跳过 {skipped}，失败 {failed}'.format(**totals))
    log('青龙通知：' + notification + '；PushPlus：' + push_status)
    log('总耗时 %.2f 秒；完成时间：%s；最终状态：%s' % (
        time.monotonic() - started, datetime.datetime.now().isoformat(timespec='seconds'), status))
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'mode': 'dry-run' if dry else 'live',
          'accounts': len(accounts), 'successfulAccounts': successful, 'failedAccounts': failed,
          'configurationError': config_error, 'tasks': totals, 'results': results,
          'notification': notification, 'pushplus': push_status, 'exitCode': exit_code},
          ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


def main_handler(event=None, context=None):
    return main()


if __name__ == '__main__':
    sys.exit(main())
