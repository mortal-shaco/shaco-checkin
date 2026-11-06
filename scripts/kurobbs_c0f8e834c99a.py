#!/usr/bin/env python3
# name: 库街区自动签到
# cron: 55 9 * * *
# 来源：KF912/kurobbs_auto_checkin，auto_checkin.py、ext_notification.py。
# MIT License（上游输入未附单独版权行；保留来源署名）
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
"""Python 3.9+；无工作流仓库依赖。默认每天北京时间 08:00 运行（面板需设时区）。

TOKEN 必填，每个非空行一个库街区登录 token，不用 & 或 @ 分隔账号。
获取：在自己的设备登录库街区，使用自己授权的 HTTPS 调试工具查看
api.kurobbs.com 请求头 token 的完整值；不是 Cookie、手机号或游戏角色 ID。
KUROBBS_TASKS=all（默认）/checkin/community：游戏签到奖励/社区签到。
KUROBBS_DRY_RUN=1 完全断网，仅验证配置和阶段编排，不声称真实签到成功。
DEBUG 兼容保留，但不输出响应和凭据。接口超时 15 秒，不重试写操作。
BARK_SERVER_URL（HTTPS 服务根地址）+ BARK_DEVICE_KEY：兼容可选 Bark。
SERVER3_SEND_KEY：兼容 Server酱3，需要公开包 serverchan-sdk。
青龙通知遵守 QINGLONG_NOTIFY 与 QINGLONG_NOTIFY_SCRIPTS；auto 为列表选择，
未配置列表时不默认选择此脚本。QINGLONG_NOTIFY=1 强制开启，=0 关闭所有通知。
通知摘要仅含计数；预演只打印通知摘要，不调用通知模块或外部程序。
原源码未声明 cron，以上每日计划为维护建议，可在青龙调整。
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
        _ql_notify_identities = ('c0f8e834c99a1475', 'scripts/kurobbs_c0f8e834c99a.py', 'kurobbs_c0f8e834c99a.py', 'kurobbs_c0f8e834c99a')
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
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

TITLE = '库街区自动签到'
CATALOG = 'c0f8e834c99a1475'
TZ = timezone(timedelta(hours=8))
YES = {'1', 'true', 'yes', 'on'}
NO = {'0', 'false', 'no', 'off'}
BASE = 'https://api.kurobbs.com'


class TaskError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把账号请求头转发至跳转目的地。
        return None


def now():
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')


def scrub(value):
    text = str(value)
    for key in ('TOKEN', 'BARK_DEVICE_KEY', 'SERVER3_SEND_KEY'):
        for secret in os.getenv(key, '').splitlines():
            if secret.strip():
                text = text.replace(secret.strip(), '[已隐藏]')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c if c.isprintable() else ' ' for c in text)


def log(message):
    print(f'[{now()[11:]}] {scrub(message)}', flush=True)


def http_json(url, data=None, headers=None, timeout=15):
    if os.getenv('KUROBBS_DRY_RUN', '').lower().strip() in YES:
        raise TaskError('预演禁止网络请求')
    if urlsplit(url).scheme != 'https':
        raise TaskError('仅允许 HTTPS')
    request = Request(url, data=data, headers=headers or {})
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超出大小限制')
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TaskError('响应结构异常')
        return obj
    except HTTPError as exc:
        raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
    except (URLError, TimeoutError, OSError):
        raise TaskError('网络请求失败或超时') from None
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None


class Client:
    def __init__(self, token):
        self.token = token

    def post(self, path, fields, mutation=False):
        headers = {
            'osversion': 'Android', 'devcode': '2fba3859fe9bfe9099f2696b8648c2c6',
            'countrycode': 'CN', 'ip': '10.0.2.233', 'model': '2211133C',
            'source': 'android', 'lang': 'zh-Hans', 'version': '1.0.9',
            'versioncode': '1090', 'token': self.token,
            'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
            'accept-encoding': 'identity', 'user-agent': 'okhttp/3.10.0',
        }
        result = http_json(BASE + path, urlencode(fields).encode(), headers)
        # 不用 truthiness 接受字符串 "false"，不把任意 HTTP 200 当成业务成功。
        if type(result.get('code')) is not int or result['code'] != 200:
            raise TaskError('业务状态未确认成功（请检查登录状态及接口兼容性）')
        if result.get('success') is False or (mutation and result.get('success') is not True):
            raise TaskError('业务成功标记缺失或为失败')
        return result.get('data')

    def profile(self):
        data = self.post('/user/mineV2', {'type': 1})
        mine = data.get('mine') if isinstance(data, dict) else None
        if not isinstance(mine, dict) or not valid_id(mine.get('userId')):
            raise TaskError('个人资料缺少公开用户 ID')
        for key in ('nickname', 'nickName', 'userName', 'username', 'displayName'):
            if isinstance(mine.get(key), str) and mine[key].strip():
                log('官方账号身份：' + mine[key])
                break
        # userId 是参考源码用于 queryUserId 的公开身份字段，不是 token。
        log('官方公开 UID：' + str(mine['userId']))
        return mine['userId']

    def role(self, uid):
        data = self.post('/gamer/role/default', {'queryUserId': uid})
        roles = data.get('defaultRoleList') if isinstance(data, dict) else None
        if not isinstance(roles, list) or not roles:
            raise TaskError('未找到默认绑定角色，请先在库街区绑定游戏角色')
        # 优先保留主来源的 gameId=3，缺失时采用相关来源的首个默认角色。
        role = next((r for r in roles if isinstance(r, dict) and str(r.get('gameId')) == '3'), roles[0])
        if not isinstance(role, dict) or any(not valid_id(role.get(k)) for k in ('gameId', 'serverId', 'roleId', 'userId')):
            raise TaskError('角色必需字段缺失，拒绝使用虚构默认值签到')
        return {k: role[k] for k in ('gameId', 'serverId', 'roleId', 'userId')}

    def checkin(self, role):
        payload = dict(role, reqMonth=datetime.now(TZ).strftime('%m'))
        self.post('/encourage/signIn/v2', payload, mutation=True)

    def community(self):
        self.post('/user/signIn', {'gameId': 2}, mutation=True)


def valid_id(value):
    return isinstance(value, (int, str)) and not isinstance(value, bool) and str(value).strip() not in ('', '0')


def notify_enabled():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in NO:
        return False
    if switch in YES:
        return True
    patterns = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    identities = (CATALOG, Path(__file__).name, 'auto_checkin.py', 'scripts/' + Path(__file__).name,
                  'scripts/auto_checkin.py')
    return any(p and any(fnmatch.fnmatchcase(i, p) for i in identities) for p in patterns)


def notify(summary, dry):
    body = (f"状态：{summary['status']}；账号总数 {summary['accounts']}，"
            f"成功 {summary['success']}，失败 {summary['failed']}；"
            f"子任务成功 {summary['steps']['success']}，失败 {summary['steps']['failed']}，"
            f"跳过 {summary['steps']['skipped']}")
    if dry:
        log('通知预演（未发送）：' + body)
        return 'dry-run'
    if not notify_enabled():
        log('通知：全局关闭或未被通知列表选中')
        return 'disabled'
    delivered = 0
    # 外部通知模块在独立进程中运行，输出不回显，超时或退出不改变业务结果。
    runner = '''import importlib.util,sys,os,contextlib
with open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
 if sys.argv[1] == 'import':
  import notify as module
 else:
  spec=importlib.util.spec_from_file_location('ql_notify',sys.argv[1])
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.send(sys.argv[2],sys.argv[3])
'''
    paths = ['import']
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.append(str(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py'))
    paths.extend(['/ql/data/scripts/notify.py', '/ql/scripts/notify.py'])
    for path in paths:
        if path != 'import' and not Path(path).is_file():
            continue
        try:
            result = subprocess.run([sys.executable, '-c', runner, path, TITLE, body],
                                    capture_output=True, timeout=20, check=False)
            if result.returncode == 0:
                delivered += 1
                break
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not delivered:
        js_paths = []
        if os.getenv('QINGLONG_NOTIFY_DIR'):
            js_paths.append(str(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'sendNotify.js'))
        js_paths.extend(['/ql/data/scripts/sendNotify.js', '/ql/scripts/sendNotify.js'])
        for path in js_paths:
            if not Path(path).is_file():
                continue
            code = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
            try:
                result = subprocess.run(['node', '-e', code, path, TITLE, body], capture_output=True, timeout=20)
                if result.returncode == 0:
                    delivered += 1
                    break
            except (OSError, subprocess.TimeoutExpired):
                pass
    bark_url = os.getenv('BARK_SERVER_URL', '').rstrip('/')
    bark_key = os.getenv('BARK_DEVICE_KEY', '')
    if bark_url and bark_key:
        try:
            result = http_json(bark_url + '/' + '/'.join(quote(s, safe='') for s in (bark_key, TITLE, body)), timeout=10)
            if result.get('code') == 200:
                delivered += 1
            else:
                log('⚠️ Bark 未确认送达')
        except TaskError:
            log('⚠️ Bark 发送失败')
    if os.getenv('SERVER3_SEND_KEY'):
        code = '''import os,sys
from serverchan_sdk import sc_send
r=sc_send(os.environ['SERVER3_SEND_KEY'],sys.argv[1],sys.argv[2],{'tags':'Github Action|库街区'})
sys.exit(0 if isinstance(r,dict) and (r.get('code') == 0 or r.get('errno') == 0) else 1)
'''
        try:
            result = subprocess.run([sys.executable, '-c', code, TITLE, body], capture_output=True, timeout=20)
            if result.returncode == 0:
                delivered += 1
            else:
                log('⚠️ Server酱3 未送达或未安装 serverchan-sdk')
        except (OSError, subprocess.TimeoutExpired):
            log('⚠️ Server酱3 发送失败')
    log('通知：' + ('已调用通知渠道' if delivered else '渠道不可用或发送失败；保留业务退出码'))
    return 'delivered' if delivered else 'unavailable'


def main():
    begin = time.monotonic()
    dry = os.getenv('KUROBBS_DRY_RUN', '').strip().lower() in YES
    tokens = [line.strip() for line in os.getenv('TOKEN', '').splitlines() if line.strip()]
    tasks = os.getenv('KUROBBS_TASKS', 'all').strip().lower()
    summary = {'status': '', 'mode': 'dry-run' if dry else 'live', 'accounts': len(tokens),
               'success': 0, 'failed': 0, 'steps': {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0},
               'startTime': now()}
    log('========== 库街区自动签到 ==========')
    log(f"开始时间：{summary['startTime']}；模式：{summary['mode']}；账号数：{len(tokens)}")
    errors = []
    if not tokens:
        errors.append('缺少 TOKEN；每个非空行填写一个账号 token')
    if tasks not in ('all', 'checkin', 'community'):
        errors.append('KUROBBS_TASKS 只能为 all、checkin 或 community')
    if errors:
        for error in errors:
            log('❌ 配置错误：' + error)
        summary['status'] = 'configuration-error'
        summary['failed'] = len(tokens)
    else:
        for index, token in enumerate(tokens, 1):
            start = time.monotonic()
            stats = {'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failed': 0}
            if any(ord(c) < 33 or ord(c) > 126 for c in token):
                summary['failed'] += 1
                stats['failed'] = 1
                stats['skipped'] = 3
                summary['steps']['failed'] += 1
                summary['steps']['skipped'] += 3
                log(f'账号 {index} 阶段 1/4：配置检查失败，TOKEN 包含空白或非法请求头字符；其余阶段跳过')
                log(f'账号 {index} 统计：总任务 4，成功 0，已完成 0，跳过 3，失败 1；耗时 {time.monotonic()-start:.2f} 秒')
                continue
            client = Client(token)
            state = {}
            log(f'账号 {index} 开始')
            stages = [('查询个人资料', lambda: state.update(uid=client.profile()), True),
                      ('查询默认游戏角色', lambda: state.update(role=client.role(state['uid'])), tasks != 'community'),
                      ('游戏签到奖励', lambda: client.checkin(state['role']), tasks != 'community'),
                      ('社区签到', client.community, tasks != 'checkin')]
            for number, (label, action, selected) in enumerate(stages, 1):
                stage_start = time.monotonic()
                log(f'账号 {index} 阶段 {number}/4：{label} 开始')
                status, detail = 'skipped', '⏭️ 未选择此任务'
                if selected:
                    if dry:
                        detail = '⏭️ DRY_RUN_OK：已验证阶段编排，不请求接口、不执行签到'
                    else:
                        try:
                            action()
                            status, detail = 'success', '✅ 已核验业务成功'
                        except KeyError:
                            status, detail = 'failed', '❌ 前置资料或角色查询失败，未发送该签到请求'
                        except TaskError as exc:
                            status, detail = 'failed', '❌ ' + str(exc)
                        except Exception:
                            status, detail = 'failed', '❌ 处理失败（异常详情已隐藏）'
                stats[status] += 1
                log(f'账号 {index} 阶段 {number}/4：{label} {detail}；耗时 {time.monotonic()-stage_start:.2f} 秒')
            for key in stats:
                summary['steps'][key] += stats[key]
            summary['failed' if stats['failed'] else 'success'] += 1
            log(f"账号 {index} 统计：总任务 4，成功 {stats['success']}，已完成 {stats['alreadyComplete']}，"
                f"跳过 {stats['skipped']}，失败 {stats['failed']}；耗时 {time.monotonic()-start:.2f} 秒")
        summary['status'] = ('partial-failure' if summary['success'] else 'failure') if summary['failed'] else ('dry-run' if dry else 'success')
    exit_code = 1 if errors or summary['failed'] else 0
    try:
        summary['notification'] = notify(summary, dry)
    except Exception:
        log('⚠️ 通知异常，保留业务退出码')
        summary['notification'] = 'unavailable'
    summary.update(finishTime=now(), elapsedSeconds=round(time.monotonic()-begin, 2), exitCode=exit_code)
    log('----------------------------------------')
    log(f"账号统计：总数 {len(tokens)}，成功 {summary['success']}，失败 {summary['failed']}")
    log('子任务统计：' + json.dumps(summary['steps'], ensure_ascii=False))
    log(f"完成时间：{summary['finishTime']}；总耗时 {summary['elapsedSeconds']} 秒；通知 {summary['notification']}")
    log('最终状态：' + summary['status'])
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
