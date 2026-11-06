#!/usr/bin/env python3
# name: Ole精品超市签到
# cron: 53 9 * * *
# 来源: comeonbabyy1/qiandao-jiaob
# script/huaruntong/ole/main.py 与 api.py，commit ce494881ab17ef23b5b9de9df30ea60567b3865c
# 原源码未附版权声明；沿用任务声明的 MIT 许可。
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
"""OLE_ACCOUNTS：每行一个原账号 JSON 对象，字段说明见 contract.json。
仅执行签到，不更改账号资料、不消费积分。OLE_DRY_RUN=1 时完全不联网，通知亦预演。
上游没有成功响应样例，仅接受 JSON 顶层 success 为布尔 true，且无 error；
若返回其他结构，失败闭合并提示核实契约，不根据 HTTP 200 或任意响应猜测成功。
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
        _ql_notify_identities = ('298cb5cdd1a60602', 'scripts/comeonbabyy1_qiandao_jiaob_ole.py', 'comeonbabyy1_qiandao_jiaob_ole.py', 'comeonbabyy1_qiandao_jiaob_ole')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = 'Ole精品超市签到'
URL = 'https://ole-app.crvole.com.cn/vgdt_app_api/v1/vgdt-fea-app-member/front_api/member_sign'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 '
      'MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac '
      'MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26405f0) XWEB/13910')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
FIELDS = ('session_id', 'device_name', 'unique', 'ole_wx_open_id')
SECRETS = set()


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {text}', flush=True)


def account_config(line):
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        raise ValueError('账号必须为单行 JSON 对象') from None
    if not isinstance(obj, dict):
        raise ValueError('账号必须为 JSON 对象')
    for key in FIELDS + ('shop_code', 'city_id', 'user_agent'):
        value = obj.get(key, {'shop_code': '205368', 'city_id': 'c_region_11122', 'user_agent': UA}.get(key))
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) > 255 for c in value):
            raise ValueError('凭据或请求头字段缺失或格式无效，请核对字段说明')
        obj[key] = value
        if key in FIELDS:
            SECRETS.add(value)
    return obj


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sign_in(account):
    headers = {
        'User-Agent': account['user_agent'], 'Content-Type': 'application/json',
        'Tenant-Channel': 'OLE', 'cityId': account['city_id'],
        'oleWxOpenId': account['ole_wx_open_id'], 'Tenant': 'VGDT',
        'sessionId': account['session_id'], 'Device-Name': account['device_name'],
        'unique': account['unique'], 'channel': 'wxmini',
        'shopCode': account['shop_code'], 'os': 'ios', 'appVersion': '1.10.17',
        'Referer': 'https://servicewechat.com/wx6c61aaeba1551439/93/page-frame.html',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    payload = json.dumps({'enter_shop_code': account['shop_code']}).encode()
    request = Request(URL, data=payload, headers=headers, method='POST')
    # 不跟随重定向，防止认证请求头被转发。签到不自动重试，避免重复副作用。
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('HTTP 状态异常，签到未获确认')
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('响应超长，签到未获确认')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('响应不是有效 JSON，签到未获确认') from None
    if not isinstance(data, dict):
        raise ValueError('响应未明确确认业务成功，请核实会话及业务响应契约')
    nested = data.get('data')
    for obj in (data, nested):
        if not isinstance(obj, dict):
            continue
        for field in ('nickname', 'nickName', 'username', 'userName', 'displayName', 'uid'):
            identity = obj.get(field)
            if isinstance(identity, (str, int)) and not isinstance(identity, bool):
                text = str(identity)
                # 仅显示官方身份；不打印响应、手机号、凭据或设备值。
                if (text and not any(s and s in text for s in SECRETS)
                        and not re.search(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', text)
                        and not any(ord(c) < 32 for c in text)):
                    log(f'官方账号身份: {text}')
    if data.get('success') is not True or data.get('error'):
        raise ValueError('响应未明确确认业务成功，请核实会话及业务响应契约')
    if isinstance(nested, dict) and (nested.get('success') is False or nested.get('error')):
        raise ValueError('响应包含业务失败，签到未获确认')
    return True


def notify(summary, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '开关无效，未投递'
    selection = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    names = ('298cb5cdd1a60602', 'candidate.py', Path(__file__).name,
             'script/huaruntong/ole/main.py', 'scripts/candidate.py')
    if selection is not None:
        selected = any(fnmatch.fnmatchcase(name, pattern)
                       for pattern in re.split(r'[,;\s]+', selection.strip()) if pattern
                       for name in names)
    else:
        selected = True  # 本任务属于通知默认名单。
    if switch == 'auto' and not selected:
        return '未在通知名单中'
    if dry:
        return '预演汇总已生成，断网模式不投递'
    body = (f"状态: {summary['status']}\n账号总数: {summary['accounts']}\n"
            f"成功数: {summary['success']}\n失败数: {summary['failed']}\n"
            f"配置错误: {summary['configurationErrors']}")
    # 隔离通知库输出和异常，避免其日志泄漏，不改变签到退出码。
    paths = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    paths.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    python_sender = r"""
import importlib, importlib.util, json, pathlib, sys
item = json.load(sys.stdin)
try:
    module = importlib.import_module('notify')
except ImportError:
    module = None
if module is None or not callable(getattr(module, 'send', None)):
    for folder in item['paths']:
        path = pathlib.Path(folder) / 'notify.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('ole_ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
if module is None or not callable(getattr(module, 'send', None)):
    sys.exit(3)
module.send(item['title'], item['body'])
"""
    try:
        sent = subprocess.run([sys.executable, '-c', python_sender],
                              input=json.dumps({'paths': [str(p) for p in paths],
                                                'title': TITLE, 'body': body}),
                              text=True, timeout=30, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        if sent.returncode == 0:
            return '已调用青龙通知'
        if sent.returncode != 3:
            return '投递失败，保留业务退出码'
        for directory in paths:
            js = directory / 'sendNotify.js'
            if js.is_file():
                subprocess.run(['node', '-e',
                                'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))',
                                str(js), TITLE, body], check=True, timeout=30,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return '已调用青龙通知'
    except Exception:
        return '投递失败，保留业务退出码'
    return '通知模块不可用，保留业务退出码'


def main():
    start = time.monotonic()
    dry = os.getenv('OLE_DRY_RUN', '').strip().lower() in TRUE
    lines = [line.strip() for line in os.getenv('OLE_ACCOUNTS', '').splitlines() if line.strip()]
    log('=' * 50)
    log(TITLE)
    log(f'开始时间: {datetime.now():%Y-%m-%d %H:%M:%S} | 模式: {"断网预演" if dry else "实际签到"} | 账号数: {len(lines)}')
    results = []
    if not lines:
        log('❌ 配置错误: 必须设置 OLE_ACCOUNTS，每行一个账号 JSON 对象')
    for index, line in enumerate(lines, 1):
        began = time.monotonic()
        stats = {'account': index, 'total': 1, 'success': 0, 'alreadyComplete': 0,
                 'skipped': 0, 'failed': 0, 'configurationError': False}
        stage = time.monotonic()
        log(f'账号 {index} / 阶段 1: 核对参数')
        try:
            account = account_config(line)
            log(f'✅ 参数校验通过 | 阶段耗时 {time.monotonic()-stage:.2f} 秒')
        except ValueError as error:
            stats.update(failed=1, configurationError=True)
            log(f'❌ {error} | 阶段耗时 {time.monotonic()-stage:.2f} 秒')
        else:
            stage = time.monotonic()
            log(f'账号 {index} / 阶段 2: {"预演签到" if dry else "提交签到"}')
            try:
                if dry:
                    log('⏭️ DRY_RUN_OK：参数有效；未请求签到接口、文本服务或通知服务')
                    stats['skipped'] = 1
                else:
                    sign_in(account)
                    stats['success'] = 1
                    log('✅ 签到成功（success=true）')
            except ValueError as error:
                stats['failed'] = 1
                log(f'❌ {error}')
            except Exception:
                stats['failed'] = 1
                log('❌ 网络、HTTP 或响应处理失败；未输出原始响应或异常，请核对网络与凭据')
            log(f'阶段 2 耗时 {time.monotonic()-stage:.2f} 秒')
        stats['durationSeconds'] = round(time.monotonic()-began, 2)
        results.append(stats)
        log(f"账号 {index} 统计: 总任务 1 / 成功 {stats['success']} / 已完成 0 / 跳过 {stats['skipped']} / 失败 {stats['failed']} / 耗时 {stats['durationSeconds']} 秒")
    failed = sum(r['failed'] for r in results)
    success = sum(r['success'] for r in results)
    config_errors = sum(r['configurationError'] for r in results) + int(not lines)
    exit_code = 1 if failed or config_errors else 0
    status = ('configuration-error' if config_errors else
              'partial-failure' if failed and (success or (dry and failed < len(lines))) else
              'failure' if failed else 'dry-run' if dry else 'success')
    summary = {'status': status, 'mode': 'dry-run' if dry else 'live', 'accounts': len(lines),
               'success': success, 'failed': failed, 'configurationErrors': config_errors,
               'tasks': {'total': len(lines), 'success': success, 'alreadyComplete': 0,
                         'skipped': sum(r['skipped'] for r in results), 'failed': failed},
               'results': results, 'exitCode': exit_code}
    summary['notification'] = notify(summary, dry)
    summary['durationSeconds'] = round(time.monotonic()-start, 2)
    summary['finishedAt'] = datetime.now().isoformat(timespec='seconds')
    log('-' * 50)
    log(f'账号结果: 总计 {len(lines)} / 成功 {success} / 失败 {failed} / 配置错误 {config_errors}')
    log(f"子任务结果: {json.dumps(summary['tasks'], ensure_ascii=False)}")
    log(f"总耗时: {summary['durationSeconds']} 秒 | 完成时间: {summary['finishedAt']}")
    log(f"通知状态: {summary['notification']} | 最终状态: {status}")
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
