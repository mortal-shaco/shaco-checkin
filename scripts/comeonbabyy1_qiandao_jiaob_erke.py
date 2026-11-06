#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 鸿星尔克签到与积分查询
# cron: 48 9 * * *
"""鸿星尔克签到与积分查询（Python 3，仅标准库）。

来源：comeonbabyy1/qiandao-jiaob，script/erke/main.py 和 api.py。
原主脚本说明：Author: Assistant; Date: 2025-11-28。
原 API 说明：鸿星尔克API模块，提供鸿星尔克小程序相关的API接口。
上游许可证：MIT；本维护版本同样采用 MIT。

ERKE_ACCOUNTS：每个非空行是一个 JSON 对象，保留上游字段 member_id、
enterprise_id、unionid、openid、wx_openid；可选 account_name、user_agent。
在自己的鸿星尔克微信小程序登录后，从积分查询或签到请求中取得对应字段，
memberId -> member_id，enterpriseId -> enterprise_id，wxOpenid -> wx_openid。
不再依赖上游 config/token.json、api 或 notification 私有模块。
ERKE_DRY_RUN=1 完全断网，仅校验配置和展示计划，不声称签到成功。
上游没有声明 cron，本版本建议每日 08:15 执行。

MIT License
Copyright (c) comeonbabyy1/qiandao-jiaob contributors

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
_ql_notify_raw = _ql_notify_os.environ.get("QINGLONG_NOTIFY")
if _ql_notify_raw is None or str(_ql_notify_raw).strip().lower() in {"", "auto"}:
    _ql_notify_selection = _ql_notify_os.environ.get("QINGLONG_NOTIFY_SCRIPTS")
    if _ql_notify_selection is None:
        _ql_notify_enabled = False
    else:
        _ql_notify_selectors = [item.lower() for item in _ql_notify_re.split(r"[,;\s]+", _ql_notify_selection.strip()) if item]
        _ql_notify_identities = ('8f2a9a5ae3fed5d4', 'scripts/comeonbabyy1_qiandao_jiaob_erke.py', 'comeonbabyy1_qiandao_jiaob_erke.py', 'comeonbabyy1_qiandao_jiaob_erke')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = '鸿星尔克签到'
CATALOG = '8f2a9a5ae3fed5d4'
BASE = 'https://hope.demogic.com/gic-wx-app'
APPID = 'wxa1f1fa3785a47c7d'
FIELDS = ('member_id', 'enterprise_id', 'unionid', 'openid', 'wx_openid')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 '
      'MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI '
      'MiniProgramEnv/Windows WindowsWechat/WMPF '
      'WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541510) XWEB/17071')


class TaskError(Exception):
    """只携带可公开的固定错误描述。"""


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def log(message):
    print(f'[{now():%H:%M:%S}] {message}', flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不将含凭据的请求转发到未知地址，也不重试变更请求。
        return None


def parse_account(line):
    try:
        account = json.loads(line)
    except (ValueError, TypeError):
        raise TaskError('账号行必须是有效的 JSON 对象') from None
    if not isinstance(account, dict):
        raise TaskError('账号行必须是 JSON 对象')
    for field in FIELDS:
        value = account.get(field)
        if not isinstance(value, str) or not value.strip():
            raise TaskError(f'缺少有效字段 {field}')
        if any(ord(c) < 32 for c in value):
            raise TaskError(f'字段 {field} 包含控制字符')
    if 'user_agent' in account:
        ua = account['user_agent']
        if not isinstance(ua, str) or not ua or any(ord(c) < 32 for c in ua):
            raise TaskError('user_agent 格式无效')
    return account


def payload(account, signing=False):
    timestamp = now().strftime('%Y-%m-%d %H:%M:%S')
    random = secrets.randbelow(10000000)
    trans_id = APPID + timestamp
    sign_string = (f'timestamp={timestamp}transId={trans_id}secret=damogic8888'
                   f'random={random}memberId={account["member_id"]}')
    data = {
        'memberId': account['member_id'], 'enterpriseId': account['enterprise_id'],
        'unionid': account['unionid'], 'openid': account['openid'],
        'wxOpenid': account['wx_openid'], 'cliqueId': '-1', 'cliqueMemberId': '-1',
        'useClique': 0 if signing else '0', 'random': random, 'appid': APPID,
        'transId': trans_id, 'timestamp': timestamp,
        'sign': hashlib.md5(sign_string.encode()).hexdigest(),
        'gicWxaVersion': '3.9.56',
        'launchOptions': '{"path":"pages/authorize/authorize","query":{},"scene":1101,"referrerInfo":{},"apiCategory":"default"}'
    }
    data.update({'source': 'wxapp'} if signing else {'currentPage': 1, 'pageSize': 5})
    return data


def request(account, signing=False):
    if os.getenv('ERKE_DRY_RUN', '0').strip().lower() not in FALSE:
        raise TaskError('预演模式禁止请求')
    data = payload(account, signing)
    headers = {
        'User-Agent': account.get('user_agent', UA),
        'Content-Type': 'application/json;charset=UTF-8' if signing else 'application/x-www-form-urlencoded',
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache',
        # 参照原 API：header sign 是 enterpriseId，表单 sign 才是 MD5。
        'sign': account['enterprise_id'], 'channelEntrance': 'wx_app', 'xweb_xhr': '1',
        'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://servicewechat.com/{APPID}/85/page-frame.html',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    }
    body = json.dumps(data).encode() if signing else urlencode(data).encode()
    endpoint = '/sign/member_sign.json' if signing else '/integral_record.json'
    req = Request(BASE + endpoint, data=body, headers=headers, method='POST')
    try:
        with build_opener(NoRedirect()).open(req, timeout=30) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超过长度限制')
            result = json.loads(raw)
    except HTTPError:
        raise TaskError('HTTP 请求失败；请核对小程序登录状态') from None
    except (URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时；未自动重试') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构异常')
    return result


def print_identity(result, account):
    # 仅展示明确的公开身份键，绝不展示 openid、memberId、手机号或原始响应。
    containers = [result]
    if isinstance(result.get('response'), dict):
        containers.append(result['response'])
    for container in containers:
        for key in ('nickname', 'nickName', 'username', 'displayName', 'publicUid'):
            value = container.get(key)
            if isinstance(value, (str, int)) and str(value):
                text = str(value)
                if any(str(account[f]) in text for f in FIELDS) or re.search(r'\d{11}', text):
                    continue
                log('官方账号身份：' + json.dumps(text, ensure_ascii=False))
                return


def points_result(result):
    # 原参考仅按 HTTP 成功判断；维护版要求业务码及积分结构均有效。
    if result.get('code') != '0000':
        raise TaskError('积分查询业务失败或业务码缺失')
    response = result.get('response')
    if not isinstance(response, dict):
        raise TaskError('积分查询缺少 response 对象')
    values = []
    for field in ('accumulatPoints', 'frozenPoints'):
        value = response.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise TaskError('积分字段缺失或类型异常')
        values.append(value)
    total, frozen = values
    log(f'累计积分：{total}；冻结积分：{frozen}；可用积分：{total - frozen}')
    page = response.get('page')
    if isinstance(page, dict):
        count = page.get('totalCount')
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            log(f'积分记录数：{count}（查询第一页，每页 5 条）')


def notify(summary, dry):
    if dry:
        return '预演跳过通知发送（断网）'
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in FALSE:
        return '通知已关闭'
    if switch not in TRUE | {'auto'}:
        return '通知开关无效，跳过发送'
    if switch == 'auto':
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
        ids = (CATALOG, 'script/erke/main.py', 'candidate.py', Path(__file__).name)
        if not any(s and any(fnmatch.fnmatchcase(i, s) for i in ids) for s in selectors):
            return '未列入通知名单'
    body = (f'状态：{summary["status"]}；账号总数：{summary["accounts"]}；'
            f'成功：{summary["success"]}；失败：{summary["failed"]}；'
            f'子任务：{summary["steps"]}')
    # 在子进程中调用青龙通知，捕获全部输出避免第三方模块输出凭据。
    roots = []
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        roots.append(Path(os.environ['QINGLONG_NOTIFY_DIR']))
    roots.extend([Path('/ql/data/scripts'), Path('/ql/scripts')])
    code = ('import importlib.util,sys; '
            's=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
            'm.send(sys.argv[2],sys.argv[3])')
    commands = [[sys.executable, '-c', 'import notify,sys; notify.send(sys.argv[1],sys.argv[2])', TITLE, body]]
    commands += [[sys.executable, '-c', code, str(root / 'notify.py'), TITLE, body]
                 for root in roots if (root / 'notify.py').is_file()]
    for cmd in commands:
        try:
            done = subprocess.run(cmd, capture_output=True, timeout=20, check=False)
            if done.returncode == 0:
                return '通知已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '通知不可用或发送失败（保留业务退出码）'


def main():
    start = time.monotonic()
    dry_value = os.getenv('ERKE_DRY_RUN', '0').strip().lower()
    dry = dry_value not in FALSE
    lines = [line.strip() for line in os.getenv('ERKE_ACCOUNTS', '').splitlines() if line.strip()]
    log('=' * 55)
    log(TITLE + f' | 开始时间：{now():%Y-%m-%d %H:%M:%S %z}')
    log(f'运行模式：{"断网预演" if dry else "正式执行"}；账号数：{len(lines)}')
    results = []
    config_error = not lines or dry_value not in TRUE | FALSE
    if not lines:
        log('❌ 配置错误：请设置 ERKE_ACCOUNTS，每行一个账号 JSON 对象')
    if dry_value not in TRUE | FALSE:
        log('❌ 配置错误：ERKE_DRY_RUN 只能设置为布尔开关值')
    for index, line in enumerate(lines, 1):
        account_start = time.monotonic()
        stats = dict(success=0, alreadyComplete=0, skipped=0, failed=0)
        log(f'账号 {index} 开始')
        try:
            account = parse_account(line)
        except TaskError as error:
            config_error = True
            stats.update(failed=1, skipped=2)
            log(f'❌ 阶段 1/3 配置校验失败：{error}；耗时 {time.monotonic() - account_start:.2f} 秒')
            log('⏭️ 阶段 2/3 积分查询、阶段 3/3 会员签到均跳过；耗时 0.00 秒')
        else:
            stats['success'] += 1
            log('✅ 阶段 1/3 配置校验通过；耗时 0.00 秒')
            for stage, signing in ((2, False), (3, True)):
                stage_start = time.monotonic()
                name = '会员签到' if signing else '积分明细查询'
                log(f'阶段 {stage}/3 {name}')
                if dry:
                    stats['skipped'] += 1
                    log(f'⏭️ 预演计划：{name}；未联网，未执行；耗时 0.00 秒')
                    continue
                try:
                    result = request(account, signing)
                    print_identity(result, account)
                    if signing:
                        code = result.get('code')
                        if code not in ('0000', '1001'):
                            raise TaskError('签到业务失败或业务码缺失')
                        if code == '1001':
                            stats['alreadyComplete'] += 1
                            log('☑️ 今日已签到（业务码 1001）')
                        else:
                            stats['success'] += 1
                            log('✅ 签到成功（业务码 0000）')
                    else:
                        points_result(result)
                        stats['success'] += 1
                        log('✅ 积分查询成功（业务码 0000）')
                except TaskError as error:
                    stats['failed'] += 1
                    log(f'❌ {name}失败：{error}')
                except Exception:
                    stats['failed'] += 1
                    log(f'❌ {name}发生未预期错误（详情已抑制）')
                log(f'阶段 {stage}/3 耗时：{time.monotonic() - stage_start:.2f} 秒')
        log(f'账号 {index} 统计：总任务 3；成功 {stats["success"]}；已完成 {stats["alreadyComplete"]}；'
            f'跳过 {stats["skipped"]}；失败 {stats["failed"]}；耗时 {time.monotonic() - account_start:.2f} 秒')
        results.append(stats)
    failed = sum(item['failed'] > 0 for item in results)
    success = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and success
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(status=status, mode='dry-run' if dry else 'live', accounts=len(lines),
                   success=success, failed=failed, exitCode=exit_code,
                   steps={key: sum(r[key] for r in results)
                          for key in ('success', 'alreadyComplete', 'skipped', 'failed')})
    try:
        notification = notify(summary, dry or dry_value not in TRUE | FALSE)
    except Exception:
        notification = '通知失败（保留业务退出码）'
    log('-' * 55)
    log(f'任务统计：账号总数 {len(lines)}；成功 {success}；失败 {failed}')
    log(f'子任务统计：{summary["steps"]}')
    log('通知状态：' + notification)
    summary.update(notification=notification, durationSeconds=round(time.monotonic() - start, 3),
                   finishTime=now().isoformat())
    log(f'完成时间：{summary["finishTime"]}；总耗时：{summary["durationSeconds"]} 秒；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
