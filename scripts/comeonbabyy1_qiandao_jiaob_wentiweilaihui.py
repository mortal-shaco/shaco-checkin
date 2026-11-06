#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 文体未来荟签到与积分查询
# cron: 47 9 * * *
# 来源: comeonbabyy1/qiandao-jiaob
# script/huaruntong/wentiweilaihui/{main.py,api.py}
# 上游未声明 cron；这里提供每日 08:00 的青龙默认调度。
# License: MIT (effectiveLicense in source catalog). Original source attribution retained.
#
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
"""独立维护版，仅依赖 Python 标准库。

WTWLH_ACCOUNTS: 每个非空行 mobile|token，按第一个 | 分割，不以 & 或 @ 分账号。
也可每行提供 JSON 对象，字段为 mobile、token、account_name、user_agent，
兼容原配置的账号字段，但不再读取私有仓库的 config/token.json。
在微信文体未来荟小程序登录后，从本人授权请求中获取 token 请求头及
signin 请求 data.mobile。不要提供 Cookie 或整段请求。
WTWLH_USER_AGENT 可设置默认 User-Agent；JSON 中的 user_agent 优先。
WTWLH_DRY_RUN=1 完全断网，仅校验配置和展示两阶段计划，不验证业务成功，
通知亦仅模拟。签到是原脚本明确用途，不增加消费、兑换、发布等副作用。
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
        _ql_notify_identities = ('34d1495efaa008cc', 'scripts/comeonbabyy1_qiandao_jiaob_wentiweilaihui.py', 'comeonbabyy1_qiandao_jiaob_wentiweilaihui.py', 'comeonbabyy1_qiandao_jiaob_wentiweilaihui')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

TITLE = "文体未来荟签到与积分查询"
CATALOG_ID = "34d1495efaa008cc"
SOURCE_PATH = "script/huaruntong/wentiweilaihui/main.py"
BASE_URL = "https://wtmp.crland.com.cn"
DEFAULT_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 '
              'Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI '
              'MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) '
              'UnifiedPCMacWechat(0xf26405f0) XWEB/13910')
TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


class TaskError(Exception):
    """仅使用固定脱敏错误，不传递服务端原始消息或异常文本。"""


def parse_account(line):
    try:
        if line.startswith("{"):
            account = json.loads(line)
            if not isinstance(account, dict):
                raise ValueError
        else:
            mobile, token = line.split("|", 1)
            account = {"mobile": mobile.strip(), "token": token.strip()}
        for field in ("mobile", "token"):
            value = account.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError
            account[field] = value.strip()
        if not re.fullmatch(r"1[0-9]{10}", account["mobile"]):
            raise ValueError
        if any(ord(c) < 32 or ord(c) == 127 for c in account["token"]):
            raise ValueError
        account["token"].encode("latin-1")
        ua = account.get("user_agent") or os.getenv("WTWLH_USER_AGENT") or DEFAULT_UA
        if not isinstance(ua, str) or any(ord(c) < 32 or ord(c) == 127 for c in ua):
            raise ValueError
        ua.encode("latin-1")
        account["user_agent"] = ua
        # 自定义标签不输出，防止标签意外包含手机号或凭据。
        return account
    except (ValueError, TypeError, UnicodeError):
        raise TaskError("账号格式错误：需要手机号与 token，可选 JSON 用户代理必须是有效请求头") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不向重定向地址发送凭据，不重试有副作用的请求。


class API:
    def __init__(self, account, dry_run=False):
        self.account = account
        self.dry_run = dry_run
        self.opener = build_opener(NoRedirect())

    def post(self, path, payload):
        if self.dry_run:
            raise TaskError("断网预演禁止 HTTP 请求")
        headers = {
            'User-Agent': self.account['user_agent'],
            'Content-Type': 'application/json',
            'xweb_xhr': '1',
            'x-hrt-mid-appid': 'API_AUTH_MINI',
            'token': self.account['token'],
            'sec-fetch-site': 'cross-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://servicewechat.com/wx3c35b1f0737c23ce/11/page-frame.html',
            'accept-language': 'zh-CN,zh;q=0.9',
            'priority': 'u=1, i',
        }
        request = Request(BASE_URL + path, data=json.dumps(payload).encode(),
                          headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != 200:
                    raise TaskError("HTTP 状态异常")
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise TaskError("响应过大")
            result = json.loads(raw)
        except TaskError:
            raise
        except HTTPError:
            raise TaskError("HTTP 请求失败，请检查登录状态及接口可用性") from None
        except (URLError, TimeoutError, OSError):
            raise TaskError("网络请求失败或超时，未自动重试") from None
        except (ValueError, UnicodeError):
            raise TaskError("响应不是有效 JSON") from None
        if not isinstance(result, dict):
            raise TaskError("响应结构不符合接口契约")
        # 上游只以 JSON 布尔 success 判定业务，不猜测其他业务码。
        if result.get("success") is not True:
            raise TaskError("业务未确认成功，请检查凭据或在小程序核对状态")
        return result

    def sign_in(self):
        return self.post('/promotion/app/sign/signin', {"data": {
            "outOrderNo": str(uuid.uuid4()), "mobile": self.account['mobile'],
            "timestamp": int(time.time() * 1000),
            "projectCode": "df2d2333f94f4c508073e0646610c021",
            "deviceChannel": "WECHAT", "businessChannel": "miniprogram",
            "channelCode": "wechat"}})

    def query_points(self):
        return self.post('/pointsAccount/app/queryAccount', {})


def public_identity(response, account):
    """只显示官方明确的公开身份字段；手机号/凭据型值不输出。"""
    containers = [response, response.get("data")]
    for obj in list(containers):
        if isinstance(obj, dict):
            containers.extend(obj.get(k) for k in ("userInfo", "user", "accountInfo"))
    for obj in containers:
        if not isinstance(obj, dict):
            continue
        for key in ("nickname", "nickName", "username", "userName", "displayName", "publicUid", "uid"):
            value = obj.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            value = str(value)
            if (not value or account['token'] in value or account['mobile'] in value
                    or re.search(r"(?<!\d)1[0-9]{10}(?!\d)", value)
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                continue
            log(f"官方账号身份（{key}）: {value}")
            return


def points_data(response):
    data = response.get("data")
    if not isinstance(data, dict):
        raise TaskError("积分响应缺少 data 对象")
    values = {}
    for key in ("points", "availablePoints", "holdPoints"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise TaskError("积分响应缺少有效积分字段")
        # 只输出经过数值校验的积分，绝不回显任意响应文本。
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise TaskError("积分字段不是有效数值") from None
        if not math.isfinite(number) or number < 0:
            raise TaskError("积分字段不是有效非负数值")
        values[key] = int(number) if number.is_integer() else number
    return values


def process_account(index, line, dry_run):
    start = time.monotonic()
    stats = dict(total=2, success=0, alreadyComplete=0, skipped=0, failed=0)
    result = {"account": index, "success": False, "statistics": stats}
    log(f"账号 {index} 开始")
    try:
        account = parse_account(line)
    except TaskError as exc:
        log(f"❌ 账号 {index} 配置错误：{exc}")
        stats.update(failed=1, skipped=1)
        result["configurationError"] = True
    else:
        api = API(account, dry_run)
        for stage, label, action in ((1, "签到", api.sign_in), (2, "查询万象星积分", api.query_points)):
            stage_start = time.monotonic()
            log(f"账号 {index} 阶段 {stage}/2 {label} 开始")
            try:
                if dry_run:
                    log(f"⏭️ {label}：断网预演，已校验参数，未发送请求")
                    stats['skipped'] += 1
                else:
                    response = action()
                    public_identity(response, account)
                    if stage == 2:
                        values = points_data(response)
                        result['points'] = values['points']
                        result['available_points'] = values['availablePoints']
                        result['hold_points'] = values['holdPoints']
                        log(f"总积分: {values['points']} | 可用积分: {values['availablePoints']} | 冻结积分: {values['holdPoints']}")
                    log(f"✅ {label}成功（业务 success=true）")
                    stats['success'] += 1
            except TaskError as exc:
                stats['failed'] += 1
                log(f"❌ {label}失败：{exc}")
            except Exception:
                stats['failed'] += 1
                log(f"❌ {label}发生未预期异常，详情已抑制以保护凭据")
            log(f"账号 {index} 阶段 {stage}/2 {label} 结束，耗时 {time.monotonic() - stage_start:.2f} 秒")
        result['success'] = not dry_run and stats['success'] == 2
    result['durationSeconds'] = round(time.monotonic() - start, 3)
    log(f"账号 {index} 统计：总任务 {stats['total']}，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，跳过 {stats['skipped']}，失败 {stats['failed']}，耗时 {result['durationSeconds']:.2f} 秒")
    return result


def notification_selected():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').lower().strip()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    # listed-only：未提供名单则不主动推送；显式空名单禁用全部。
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    names = (CATALOG_ID, SOURCE_PATH, Path(__file__).name, 'candidate.py',
             'wentiweilaihui.py', 'wentiweilaihui/main.py')
    return any(s and any(fnmatch.fnmatchcase(n, s) for n in names) for s in selectors)


def notify(body, dry_run):
    if dry_run:
        log('通知：断网预演仅生成脱敏汇总，不调用通知网络')
        return 'dry-run'
    if not notification_selected():
        log('通知：已按全局开关或脚本名单跳过')
        return 'disabled'
    payload = json.dumps({'title': TITLE, 'body': body}, ensure_ascii=False)
    locations = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        locations.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    locations.extend((Path('/ql/data/scripts'), Path('/ql/scripts')))
    pycode = ('import json,sys,importlib.util; p=json.load(sys.stdin); '
              'spec=importlib.util.spec_from_file_location("notify",sys.argv[1]); '
              'm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); '
              'm.send(p["title"],p["body"])')
    commands = []
    try:
        if importlib.util.find_spec('notify') is not None:
            commands.append([sys.executable, '-c',
                             'import json,sys,notify; p=json.load(sys.stdin); notify.send(p["title"],p["body"])'])
    except (ImportError, ValueError):
        pass
    for folder in locations:
        if (folder / 'notify.py').is_file():
            commands.append([sys.executable, '-c', pycode, str(folder / 'notify.py')])
    if shutil.which('node'):
        jscode = ('const fs=require("fs");const p=JSON.parse(fs.readFileSync(0,"utf8"));'
                  'Promise.resolve(require(process.argv[1]).sendNotify(p.title,p.body))'
                  '.catch(()=>process.exit(1));')
        for folder in locations:
            if (folder / 'sendNotify.js').is_file():
                commands.append(['node', '-e', jscode, str(folder / 'sendNotify.js')])
    for command in commands:
        try:
            completed = subprocess.run(command, input=payload, text=True, timeout=20,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if completed.returncode == 0:
                log('通知：通知模块调用完成')
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 通知：模块不可用或调用失败，保留业务退出码')
    return 'unavailable-or-failed'


def main():
    started = stamp()
    timer = time.monotonic()
    dry_run = os.getenv('WTWLH_DRY_RUN', '0').lower().strip() in TRUE
    lines = [line.strip() for line in os.getenv('WTWLH_ACCOUNTS', '').splitlines() if line.strip()]
    print('=' * 56)
    log(TITLE)
    log(f"开始时间: {started} | 模式: {'断网预演' if dry_run else '正式执行'} | 账号数: {len(lines)}")
    results = []
    if not lines:
        log('❌ 配置错误：未设置必填 WTWLH_ACCOUNTS，至少需要一行账号')
    for index, line in enumerate(lines, 1):
        results.append(process_account(index, line, dry_run))
    configuration_error = not lines or any(r.get('configurationError') for r in results)
    failed = sum(r['statistics']['failed'] > 0 for r in results)
    success = sum(r['success'] for r in results)
    exit_code = 1 if configuration_error or failed else 0
    if configuration_error:
        status = 'configuration-error'
    elif dry_run:
        status = 'dry-run'
    elif failed:
        status = 'partial-failure' if success else 'failure'
    else:
        status = 'success'
    totals = {k: sum(r['statistics'][k] for r in results)
              for k in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    body = (f"状态: {status}\n账号总数: {len(lines)}，成功数: {success}，失败数: {failed}"
            f"\n预演账号数: {len(lines) - failed if dry_run else 0}"
            f"\n子任务成功: {totals['success']}，失败: {totals['failed']}，跳过: {totals['skipped']}")
    notification = notify(body, dry_run)
    finished = stamp()
    print('-' * 56)
    log(body.replace('\n', ' | '))
    log(f"子任务统计：总数 {totals['total']}，已完成 {totals['alreadyComplete']}")
    log(f"完成时间: {finished} | 总耗时: {time.monotonic() - timer:.2f} 秒 | 通知状态: {notification}")
    log(f"最终状态: {status} | 退出码: {exit_code}")
    if dry_run and exit_code == 0:
        log('DRY_RUN_OK：配置和两阶段流程校验完成，未验证真实业务')
    if status == 'success':
        log('TASK_SUCCESS：全部账号签到与积分查询均已核验成功')
    summary = {'status': status, 'mode': 'dry-run' if dry_run else 'live',
               'accounts': len(lines), 'success': success, 'failed': failed,
               'configurationErrors': sum(bool(r.get('configurationError')) for r in results) + int(not lines),
               'statistics': totals, 'results': results, 'notification': notification,
               'startedAt': started, 'finishedAt': finished,
               'durationSeconds': round(time.monotonic() - timer, 3), 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
