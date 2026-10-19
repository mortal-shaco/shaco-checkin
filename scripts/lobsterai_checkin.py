#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: LobsterAI 每日签到
# cron: 27 0 * * *
# 来源：L0NE-6/LobsterAI-AutoCheckin / lobsterai_checkin.py，许可证：MIT。
# 上游提供的三个输入文件未包含额外版权声明；保留来源归属。
"""LobsterAI 独立每日签到（Python 标准库，无需桌面客户端或仓库）。

LOBSTERAI_TOKEN：每个非空行一个账号，uid:AT:RT、uid:AT 或纯 AT。
在官方门户 https://lobsterai.youdao.com/portal#/login 登录，开发者工具
Network 中复制 Authorization 的 Bearer 后的 accessToken；refreshToken
可从本人登录响应或 Application 的本地存储获取，UID 从本人账号资料获取。
RT 可不填；过期时需手动更新。不得分享凭据。也可 --auths 显式指定自己的
JSON 目录（lobsterai-*.json，auth.accessToken/refreshToken 与 account.uid）。
--only UID 筛选账号，--version 数字版本覆盖自动版本，--base 仅允许 HTTPS。
默认每天 9 点；AT 七天内到期时自动续期，私密缓存采用 0600 原子保存。
LOBSTERAI_REFRESH_STORE 可指定缓存文件，默认脚本目录 lb_refresh_tokens.json。
LOBSTERAI_DRY_RUN=1 完全离线：仅检查配置并模拟流程，不读写续期缓存，不发通知。
QINGLONG_NOTIFY=0 禁用通知；QINGLONG_NOTIFY_DIR 指定青龙通知模块目录。
PUSHPLUS_TOKEN 保留可选微信推送；同样服从全局通知开关。

MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
        _ql_notify_identities = ('3328423575cf7143', 'scripts/lobsterai_checkin.py', 'lobsterai_checkin.py', 'lobsterai_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import base64
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'https://lobsterai-server.youdao.com'
UPDATE = 'https://api-overmind.youdao.com/openapi/get/luna/hardware/lobsterai/prod/update'
DEFAULT_VERSION = '2026.9.4'
TITLE = 'LobsterAI 每日签到'
DISABLED = {'0', 'false', 'no', 'off'}


class TaskError(Exception):
    pass


def log(message):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), message), flush=True)


def stage(number, name, fn):
    start = time.monotonic()
    log('阶段 %d：%s' % (number, name))
    try:
        value = fn()
        log('阶段 %d 完成，耗时 %.2f 秒' % (number, time.monotonic() - start))
        return value
    except Exception:
        log('阶段 %d 失败，耗时 %.2f 秒' % (number, time.monotonic() - start))
        raise


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('接口重定向被拒绝，避免凭据泄漏')


def http(url, body=None, token='', version=DEFAULT_VERSION, timeout=30):
    headers = {'Accept': 'application/json', 'User-Agent': 'LobsterAI/' + version}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise TaskError('响应过大')
        doc = json.loads(data)
        if not isinstance(doc, dict):
            raise TaskError('响应结构异常')
        return doc
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError('HTTP 请求失败（状态 %d）' % exc.code) from None
    except Exception:
        raise TaskError('网络、超时或响应解析失败') from None


def api(base, path, token, version, body=None):
    doc = http(base + path, body, token, version)
    if type(doc.get('code')) is not int or doc['code'] != 0:
        raise TaskError('业务接口未明确返回成功码 0')
    data = doc.get('data')
    if not isinstance(data, dict):
        raise TaskError('业务数据结构异常')
    return data


def jwt(token):
    try:
        payload = token.split('.')[1]
        data = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_line(line):
    uid, delimiter, rest = line.partition(':')
    if delimiter:
        at, _, rt = rest.partition(':')
    else:
        at, rt, uid = line, '', ''
    at, rt = at.strip(), rt.strip()
    return {'uid': uid.strip() or str(jwt(at).get('sub', '')), 'token': at, 'rt': rt}


def accounts(args):
    raw = os.environ.get('LOBSTERAI_TOKEN', '').strip()
    if raw:
        rows = [parse_line(line.strip()) for line in raw.splitlines() if line.strip()]
    elif args.auths:
        rows = []
        for path in sorted(Path(args.auths).glob('lobsterai-*.json')):
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
                auth = doc.get('auth') or doc
                account = doc.get('account') or {}
                at = auth.get('accessToken') or auth.get('access_token') or ''
                rows.append({'token': at, 'rt': auth.get('refreshToken') or auth.get('refresh_token') or '',
                             'uid': str(account.get('uid') or auth.get('uid') or jwt(at).get('sub', ''))})
            except Exception:
                rows.append({'uid': '', 'token': '', 'rt': ''})
    else:
        rows = []
    return [row for row in rows if not args.only or row['uid'] == args.only]


def save_store(path, store):
    fd, temporary = tempfile.mkstemp(prefix='.lb-refresh-', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(store, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def refresh(acc, base, version, path):
    store = {}
    if path.exists():
        try:
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise TaskError('续期缓存权限不安全，请设置为 0600')
            store = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(store, dict):
                raise ValueError()
        except TaskError:
            raise
        except Exception:
            raise TaskError('续期缓存无法读取，请安全检查文件') from None
    # 没有 UID 时不共用缓存，避免多个纯 AT 账号串号。
    cached = store.get(acc['uid'], {}) if acc['uid'] else {}
    if cached:
        cached_at = cached.get('access_token', '')
        if jwt(cached_at).get('sub') and str(jwt(cached_at)['sub']) != acc['uid']:
            raise TaskError('续期缓存账号不匹配')
        acc['token'] = cached_at or acc['token']
        acc['rt'] = cached.get('refresh_token') or acc['rt']
    try:
        exp = float(jwt(acc['token']).get('exp', 0))
    except (ValueError, TypeError):
        exp = 0
    if exp > time.time() + 7 * 86400:
        log('⏭️ AT 有效期充足，无需续期')
        return
    if not acc['rt']:
        if exp and exp <= time.time():
            raise TaskError('AT 已过期且未配置 RT，请重新登录更新凭据')
        log('⏭️ 未配置 RT，使用 AT 由业务接口核验')
        return
    if not acc['uid']:
        raise TaskError('自动续期需提供 UID，以安全保存轮换凭据')
    stamp = str(int(time.time() * 1000))
    data = api(base, '/api/auth/refresh', '', version, {
        'refreshToken': acc['rt'], 'firstKeyfrom': stamp, 'latestKeyfrom': stamp,
        'version': '0.1.0', 'uuid': str(uuid.uuid4())})
    at = data.get('accessToken')
    rt = data.get('refreshToken') or acc['rt']
    if not isinstance(at, str) or not at or not isinstance(rt, str):
        raise TaskError('续期响应缺少有效凭据')
    if jwt(at).get('sub') and str(jwt(at)['sub']) != acc['uid']:
        raise TaskError('续期响应账号不匹配')
    store[acc['uid']] = {'access_token': at, 'refresh_token': rt, 'updated': time.strftime('%Y-%m-%d %H:%M')}
    try:
        save_store(path, store)
    except Exception:
        raise TaskError('续期成功但私密缓存保存失败，请重新获取凭据') from None
    acc.update(token=at, rt=rt)
    log('✅ 续期成功，凭据已私密保存')


def identity(data):
    # 只读取明确的非敏感身份字段，不打印本地凭据或原始响应。
    user = data.get('user') or data.get('account') or {}
    if isinstance(user, dict):
        for key in ('nickname', 'username', 'displayName', 'uid'):
            if isinstance(user.get(key), (str, int)) and str(user[key]):
                value = str(user[key])
                if re.fullmatch(r'\+?\d[\d -]{9,14}', value) and key != 'uid':
                    continue
                log('官方账号身份：' + value.replace('\n', ' ').replace('\r', ' '))


def credits(data):
    for key in ('creditsGranted', 'rewardCredits', 'credits', 'grantedCredits', 'creditAmount'):
        try:
            val = float(data.get(key))
            if math.isfinite(val) and val > 0:
                return val
        except (TypeError, ValueError):
            pass
    return credits(data['result']) if isinstance(data.get('result'), dict) else 0


def checkin(acc, base, version):
    slot = stage(2, '查询签到活动', lambda: api(base,
        '/api/client-activities/slot?' + urllib.parse.urlencode({'placement': 'desktop_sidebar',
        'clientVersion': version, 'containerApiVersion': 2, 'platform': 'win32'}), acc['token'], version))
    identity(slot)
    activity = slot.get('activity')
    if slot.get('slotState') != 'available' or not isinstance(activity, dict):
        raise TaskError('签到活动未投放，无法核验签到成功；可用 --version 指定官方版本')
    code = activity.get('activityCode')
    rev = activity.get('configRevision')
    if not isinstance(code, str) or not code or type(rev) is not int:
        raise TaskError('活动配置字段异常')
    prefix = '/api/client-activities/' + urllib.parse.quote(code, safe='')
    def context():
        return api(base, prefix + '/context?configRevision=%d' % rev, acc['token'], version)
    ctx = stage(3, '查询今日状态', context)
    identity(ctx)
    if type(ctx.get('configRevision')) is int:
        rev = ctx['configRevision']
    state = ctx.get('state') or {}
    if state.get('claimedToday') is True:
        log('☑️ 今天已签到（官方状态已核验）')
        return 'already', 0
    actions = ctx.get('actions') or []
    if not isinstance(actions, list) or 'check_in' not in [a.lower().strip() for a in actions if isinstance(a, str)]:
        raise TaskError('未提供签到动作，不能视为已签到')
    before = state.get('claimedDays', 0)
    response = stage(4, '提交幂等签到', lambda: api(base, prefix + '/actions/check_in', acc['token'], version,
        {'configRevision': rev, 'idempotencyKey': str(uuid.uuid4()), 'payload': {}}))
    after = stage(5, '复核签到结果', context)
    identity(after)
    new = after.get('state') or {}
    changed = (type(new.get('claimedDays')) is int and type(before) is int and new['claimedDays'] > before)
    if new.get('claimedToday') is not True and not changed:
        raise TaskError('未核验到今日领取或领取天数变化，不计成功')
    granted = credits(response)
    log('✅ 签到成功，积分 +%g' % granted)
    for key, label in (('streakDays', '连续签到天数'), ('streak', '连登天数'), ('claimedDays', '已领取天数'), ('totalDays', '活动总天数')):
        if type(new.get(key, state.get(key))) is int:
            log('%s：%d' % (label, new.get(key, state.get(key))))
    total = new.get('totalDays', state.get('totalDays'))
    days = new.get('claimedDays')
    if type(total) is int and type(days) is int and total > days:
        log('剩余领取天数：%d' % (total - days))
    return 'ok', granted


def notify(body, dry):
    if os.environ.get('QINGLONG_NOTIFY', '1').lower() in DISABLED:
        return '已禁用'
    if dry:
        log('⏭️ 离线预演通知摘要已生成，未调用通知模块或推送接口')
        return '离线预演跳过发送'
    delivered = False
    paths = []
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
    paths.extend([Path(__file__).resolve().parent / 'notify.py', Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
    # 独立子进程隔离通知日志，避免模块意外输出凭据，并限制等待时长。
    code = "import importlib.util,json,sys; p=json.load(sys.stdin); s=importlib.util.spec_from_file_location('notify',p['path']); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(p['title'],p['body'])"
    for path in paths:
        if path.is_file():
            try:
                result = subprocess.run([sys.executable, '-c', code], input=json.dumps({'path': str(path), 'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                delivered = result.returncode == 0
            except Exception:
                pass
            if delivered:
                break
    if not delivered:
        # 支持导入路径中的 notify.send。
        try:
            result = subprocess.run([sys.executable, '-c', "import notify,sys; notify.send(sys.argv[1],sys.stdin.read())", TITLE], input=body, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            delivered = result.returncode == 0
        except Exception:
            pass
    push = os.environ.get('PUSHPLUS_TOKEN', '').strip()
    if push:
        try:
            response = http('https://www.pushplus.plus/send', {'token': push, 'title': TITLE, 'content': body, 'template': 'txt'}, timeout=20)
            log('PushPlus：' + ('✅ 推送成功' if response.get('code') == 200 else '⚠️ 推送失败'))
        except Exception:
            log('⚠️ PushPlus 推送失败')
    return '青龙通知成功' if delivered else '青龙通知不可用或失败，保留业务退出码'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令行参数错误，请使用 --help 查看用法')


def main():
    started = time.monotonic()
    dry = os.environ.get('LOBSTERAI_DRY_RUN', '0').lower() in {'1', 'true', 'yes', 'on'}
    log('========== 🦞 %s ==========' % TITLE)
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('模式：' + ('离线预演' if dry else '正式签到'))
    results, rows, config_error = [], [], ''
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--auths', default='', help='可选本人凭据目录，不依赖其他仓库')
    parser.add_argument('--base', default=BASE, help='HTTPS 上游地址')
    parser.add_argument('--version', default='', help='数字客户端版本')
    parser.add_argument('--only', default='', help='只运行指定 UID')
    try:
        args = parser.parse_args()
        parsed = urllib.parse.urlsplit(args.base)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise TaskError('上游地址必须为无凭据的 HTTPS 地址')
        args.base = args.base.rstrip('/')
        if args.version and not re.fullmatch(r'\d+(?:\.\d+)*', args.version):
            raise TaskError('版本参数格式错误')
        rows = accounts(args)
        if not rows:
            raise TaskError('未找到账号，请设置 LOBSTERAI_TOKEN，每行 uid:AT:RT 或 AT')
        log('账号数：%d' % len(rows))
        version = args.version or DEFAULT_VERSION
        if not args.version and not dry:
            try:
                doc = http(UPDATE, timeout=8)
                value = doc['data']['value']['version']
                if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+)*', value):
                    raise ValueError()
                version = value
                log('✅ 自动获取官方客户端版本：' + version)
            except Exception:
                log('⚠️ 官方版本查询失败，使用兜底版本：' + version)
        path = Path(os.environ.get('LOBSTERAI_REFRESH_STORE', str(Path(__file__).resolve().parent / 'lb_refresh_tokens.json')))
        for idx, acc in enumerate(rows, 1):
            t = time.monotonic()
            log('----- 账号 %d -----' % idx)
            status, granted = 'error', 0
            try:
                if not acc['token'] or any(c in acc['token'] + acc['rt'] for c in '\r\n@&'):
                    raise TaskError('账号凭据为空或包含不支持的分隔符')
                if dry:
                    stage(1, '检查凭据配置', lambda: None)
                    for number, name in enumerate(('查询活动', '查询今日状态', '提交签到', '复核结果'), 2):
                        stage(number, name + '（仅模拟，不请求）', lambda: None)
                    log('✅ DRY_RUN_OK：离线流程完成，不代表真实业务成功')
                    status = 'dry-run'
                else:
                    stage(1, '检查与续期凭据', lambda: refresh(acc, args.base, version, path))
                    status, granted = checkin(acc, args.base, version)
            except TaskError as exc:
                log('❌ ' + str(exc))
            except Exception:
                log('❌ 数据结构、配置或执行异常（已隐藏原始内容）')
            result = {'idx': idx, 'status': status, 'granted': granted, 'elapsed': round(time.monotonic() - t, 2)}
            results.append(result)
            log('账号统计：总任务 1，成功 %d，已完成 %d，跳过 %d，失败 %d，耗时 %.2f 秒' %
                (status == 'ok', status == 'already', status == 'dry-run', status == 'error', result['elapsed']))
    except TaskError as exc:
        config_error = str(exc)
        log('账号数：%d' % len(rows))
        log('❌ 配置错误：' + config_error)
    except Exception:
        config_error = '配置读取失败（已隐藏原始内容）'
        log('账号数：%d' % len(rows))
        log('❌ ' + config_error)
    failed = sum(r['status'] == 'error' for r in results)
    success = sum(r['status'] in {'ok', 'already', 'dry-run'} for r in results)
    exit_code = 1 if config_error or failed else 0
    final = 'configuration-error' if config_error else ('partial-failure' if failed and success else 'failure' if failed else 'dry-run' if dry else 'success')
    body = '%s\n状态：%s\n账号总数 %d，成功数 %d，失败数 %d\n已签到 %d，预演 %d，积分 %g' % (
        TITLE, final, len(rows), success, failed, sum(r['status'] == 'already' for r in results), sum(r['status'] == 'dry-run' for r in results), sum(r['granted'] for r in results))
    if config_error:
        body += '\n配置错误：' + config_error
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body.replace('\n', ' | '))
    log('子任务统计：总数 %d，成功 %d，已完成 %d，跳过 %d，失败 %d' % (len(results),
        sum(r['status'] == 'ok' for r in results), sum(r['status'] == 'already' for r in results),
        sum(r['status'] == 'dry-run' for r in results), failed))
    log('通知状态：' + notification)
    log('完成时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('总耗时：%.2f 秒，最终状态：%s' % (time.monotonic() - started, final))
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': final,
        'accounts': len(rows), 'success': success, 'failed': failed, 'configurationError': bool(config_error),
        'results': results, 'notification': notification, 'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
