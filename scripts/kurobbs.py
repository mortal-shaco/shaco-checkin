#!/usr/bin/env python3
# name: 库街区社区与游戏签到
# cron: 43 9 * * *
# Upstream: Kilaers/multi-game-auto-sign, src/kurobbs.py
# Source commit: 220ad60046a75312ced4dd171d8d7c9ecb29cd82
# License: MIT (effectiveLicense supplied by source catalog).
# MIT License
# Copyright (c) Kilaers/multi-game-auto-sign contributors
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
"""KURO_TOKEN: 每个非空行一个账号的 token；不按逗号、& 或 @ 拆分。
在库街区 APP 登录后，用可信抓包工具查看 api.kurobbs.com 请求头的 token。
默认执行社区签到和全部默认绑定游戏角色签到。缺少环境变量时兼容读取当前
目录 KURO_TOKEN.txt；不会自动登录或写入文件。
仅人工终端显式设置 KURO_TYPE=add_account 时，支持短信或手动添加账号，
以权限 0600 保存至当前目录 KURO_TOKEN.txt，且不签到。短信可能触发极验，
此时改用手动抓包。KURO_DRY_RUN=1 完全断网，不读写账号文件或交互。
原源码未声明 cron；维护版建议每天 08:00，可在青龙修改。
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
        _ql_notify_identities = ('d0719f985bead4d5', 'scripts/kurobbs.py', 'kurobbs.py', 'kurobbs')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import fnmatch
import getpass
import json
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
from datetime import datetime

TITLE = '库街区社区与游戏签到'
CATALOG = 'd0719f985bead4d5'
BASE = 'https://api.kurobbs.com'
TOKEN_FILE = Path('KURO_TOKEN.txt')
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
GAME_NAMES = {2: '战双帕弥什', 3: '鸣潮'}
SECRETS = []


class TaskError(Exception):
    pass


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def identity(value, public_uid=False):
    if not isinstance(value, (str, int)):
        return ''
    text = str(value)
    for secret in SECRETS:
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    if not public_uid:
        text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return re.sub(r'[\r\n\x00-\x1f\x7f]', ' ', text)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, data, token=None, login=False):
    if os.environ.get('KURO_DRY_RUN', '').lower() in TRUE:
        raise TaskError('预演禁止网络请求')
    headers = {
        'osversion': 'Android', 'devcode': '2fba3859fe9bfe9099f2696b8648c2c6',
        'countrycode': 'CN', 'source': 'android', 'lang': 'zh-Hans',
        'version': '1.0.9', 'versioncode': '1090',
        'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
        'accept-encoding': 'identity', 'user-agent': 'okhttp/3.10.0',
    }
    if token:
        headers['token'] = token
    if login:
        headers.update({'distinct_id': str(uuid.uuid4()), 'ip': '10.0.2.233',
                        'model': '2211133C'})
        if path == '/user/getSmsCode':
            headers['devcode'] = '073A9EFAC18FC50616DD15808DAE719DBCB904B7'
    req = urllib.request.Request(BASE + path,
                                 data=urllib.parse.urlencode(data).encode(),
                                 headers=headers, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应超出大小限制')
        result = json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 请求失败（状态 {exc.code}）') from None
    except (OSError, ValueError, urllib.error.URLError):
        raise TaskError('请求超时、网络异常或响应格式无效') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构无效')
    # 不输出服务端 msg，避免服务端回显凭据；不猜测“已签到”的业务码。
    if type(result.get('code')) is not int or result['code'] != 200:
        code = result.get('code')
        suffix = f'（业务码 {code}）' if type(code) is int else '（业务码缺失或无效）'
        raise TaskError('业务失败' + suffix)
    return result


def stage(stats, number, name, action):
    started = time.monotonic()
    log(f'阶段 {number}：{name}')
    stats['total'] += 1
    try:
        result = action()
        stats['success'] += 1
        log(f'✅ 阶段 {number}：{name}成功，耗时 {time.monotonic()-started:.2f} 秒')
        return result
    except Exception as exc:
        stats['failed'] += 1
        detail = str(exc) if isinstance(exc, TaskError) else '内部处理异常（详情已隐藏）'
        log(f'❌ 阶段 {number}：{name}失败：{detail}，耗时 {time.monotonic()-started:.2f} 秒')
        return None


def new_stats():
    return dict(total=0, success=0, alreadyComplete=0, skipped=0, failed=0)


def sign_account(token, stats):
    stage(stats, 1, '社区签到', lambda: request('/user/signIn', {'gameId': 2}, token))

    def mine():
        resp = request('/user/mineV2', {'type': 1}, token)
        data = resp.get('data')
        user = data.get('mine') if isinstance(data, dict) else None
        if not isinstance(user, dict) or not user.get('userId'):
            raise TaskError('未返回有效用户 ID')
        for key in ('nickname', 'nickName', 'userName', 'username', 'displayName', 'userId'):
            if user.get(key) is not None:
                log(f'账号身份 {key}：{identity(user[key], public_uid=key == "userId")}')
        return user['userId']

    uid = stage(stats, 2, '查询账号身份', mine)
    if uid is None:
        stats['total'] += 1
        stats['skipped'] += 1
        log('⏭️ 阶段 3：缺少用户 ID，跳过角色查询和游戏签到')
        return

    def roles():
        resp = request('/gamer/role/default', {'queryUserId': uid}, token)
        data = resp.get('data')
        items = data.get('defaultRoleList') if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise TaskError('默认角色列表缺失或格式无效')
        return items

    items = stage(stats, 3, '查询默认绑定角色', roles)
    if items is None:
        return
    if not items:
        stats['total'] += 1
        stats['skipped'] += 1
        log('⏭️ 阶段 4：官方返回空角色列表，无游戏角色可签到')
    for index, role in enumerate(items, 4):
        def sign(role=role):
            if not isinstance(role, dict) or any(role.get(k) in (None, '') for k in
                                                    ('gameId', 'serverId', 'roleId', 'userId')):
                raise TaskError('角色签到所需字段缺失')
            if role.get('roleName') is not None:
                log(f'角色昵称：{identity(role["roleName"])}')
            game = role['gameId']
            log(f'签到游戏：{GAME_NAMES.get(game, "其他绑定游戏")}')
            data = {k: role[k] for k in ('gameId', 'serverId', 'roleId', 'userId')}
            data['reqMonth'] = f'{datetime.now().month:02d}'
            return request('/encourage/signIn/v2', data, token)
        stage(stats, index, '游戏角色签到', sign)


def add_account():
    if not sys.stdin.isatty():
        raise TaskError('添加账号仅允许在人工终端运行')
    log('添加账号模式：1 短信登录；2 手动输入已抓包 Token；本模式不签到')
    mode = input('请选择（默认 1）：').strip() or '1'
    if mode == '1':
        phone = getpass.getpass('手机号（隐藏输入）：').strip()
        if not re.fullmatch(r'1\d{10}', phone):
            raise TaskError('手机号格式不正确')
        SECRETS.append(phone)
        resp = request('/user/getSmsCode', {'mobile': phone, 'geeTestData': ''}, login=True)
        if isinstance(resp.get('data'), dict) and resp['data'].get('geeTest') is True:
            raise TaskError('触发极验，请改用手动输入抓包 Token')
        code = getpass.getpass('短信验证码（隐藏输入）：').strip()
        if not code:
            raise TaskError('验证码不能为空')
        SECRETS.append(code)
        resp = request('/user/sdkLogin', {'mobile': phone, 'code': code,
                       'devCode': '2fba3859fe9bfe9099f2696b8648c2c6', 'gameList': ''}, login=True)
        data = resp.get('data')
        token = data.get('token') if isinstance(data, dict) else None
    elif mode == '2':
        log('在库街区 APP 登录后抓取 api.kurobbs.com 请求，复制请求头 token 字段')
        token = getpass.getpass('Token（隐藏输入）：').strip()
    else:
        raise TaskError('添加方式无效')
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise TaskError('未获得有效 Token')
    SECRETS.append(token)
    existing = TOKEN_FILE.read_text(encoding='utf-8').splitlines() if TOKEN_FILE.exists() else []
    tokens = list(dict.fromkeys(t.strip() for t in existing + [token] if t.strip()))
    # 显式添加才写文件；原子替换，不跟随目标符号链接。
    if TOKEN_FILE.is_symlink():
        raise TaskError('拒绝写入符号链接账号文件')
    fd, name = tempfile.mkstemp(prefix='.kuro-token-', dir='.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('\n'.join(tokens) + '\n')
        os.replace(name, TOKEN_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    log('✅ 已保存账号文件，权限 0600；请在青龙 KURO_TOKEN 中每行配置一个账号')


def notification_enabled():
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return False
    if switch in TRUE:
        return True
    selectors = re.split(r'[,;\s]+', os.environ.get('QINGLONG_NOTIFY_SCRIPTS', '').strip())
    names = (CATALOG, Path(__file__).name, 'kurobbs.py', 'scripts/kurobbs.py')
    return any(fnmatch.fnmatchcase(name, item) for item in selectors if item for name in names)


def notify(summary, dry):
    if dry:
        log('⏭️ 通知：断网预演，仅生成脱敏摘要，不调用通知模块')
        return 'dry-run'
    if not notification_enabled():
        log('⏭️ 通知：未被列入通知列表或已关闭')
        return 'disabled'
    body = (f"状态：{summary['status']}；账号总数：{summary['accounts']}；"
            f"成功：{summary['success']}；失败：{summary['failed']}")
    directories = [os.environ.get('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
    # 在独立子进程中隔离通知输出和超时，不改变业务退出码。
    helper = '''import contextlib,io,importlib.util,sys
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
 if sys.argv[1]:
  s=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
 else:
  import notify as m
 m.send(sys.argv[2],sys.argv[3])
'''
    options = [[sys.executable, '-c', helper, '', TITLE, body]]
    for directory in directories:
        if directory:
            path = Path(directory) / 'notify.py'
            if path.is_file():
                options.append([sys.executable, '-c', helper, str(path), TITLE, body])
    for directory in directories:
        if directory:
            path = Path(directory) / 'sendNotify.js'
            if path.is_file():
                options.append(['node', '-e', 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))', str(path), TITLE, body])
    for command in options:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            if result.returncode == 0:
                log('✅ 通知：已发送脱敏摘要')
                return 'sent'
        except (OSError, subprocess.TimeoutExpired):
            pass
    log('⚠️ 通知：模块不可用或发送失败，保留业务退出码')
    return 'unavailable'


def main():
    started = time.monotonic()
    dry = os.environ.get('KURO_DRY_RUN', '').lower() in TRUE
    mode = os.environ.get('KURO_TYPE', '').strip()
    log('=' * 48)
    log(f'{TITLE} | 开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}')
    log(f'运行模式：{"断网预演" if dry else "添加账号" if mode == "add_account" else "正式签到"}')
    results = []
    config_error = False
    tokens = []
    try:
        if mode not in ('', 'sign', 'add_account'):
            raise TaskError('KURO_TYPE 仅允许 sign、add_account 或留空')
        if mode != 'add_account':
            text = os.environ.get('KURO_TOKEN', '')
            if not text.strip() and not dry and TOKEN_FILE.exists():
                text = TOKEN_FILE.read_text(encoding='utf-8')
            tokens = list(dict.fromkeys(t.strip() for t in text.splitlines() if t.strip()))
            if not tokens:
                raise TaskError('缺少 KURO_TOKEN：请每个非空行配置一个账号 Token')
            if any(any(c.isspace() for c in token) for token in tokens):
                raise TaskError('Token 行内不能包含空白字符')
            SECRETS.extend(tokens)
        log(f'账号数量：{1 if mode == "add_account" else len(tokens)}')
        for index, token in enumerate([None] if mode == 'add_account' else tokens, 1):
            begin = time.monotonic()
            stats = new_stats()
            log(f'---- 账号 {index} ----')
            if dry:
                for num, label in enumerate(['添加账号与安全保存'] if mode == 'add_account' else
                                            ['社区签到', '查询账号身份', '查询默认绑定角色', '游戏角色签到'], 1):
                    stats['total'] += 1
                    stats['skipped'] += 1
                    log(f'⏭️ 阶段 {num}：{label}，预演跳过，耗时 0.00 秒')
                log('DRY_RUN_OK：参数解析完成，未访问网络、未读写账号文件')
            elif mode == 'add_account':
                stage(stats, 1, '添加账号与安全保存', add_account)
            else:
                sign_account(token, stats)
            stats['elapsedSeconds'] = round(time.monotonic()-begin, 2)
            results.append(stats)
            log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {stats["elapsedSeconds"]} 秒')
    except Exception as exc:
        config_error = True
        log('账号数量：' + str(len(tokens)))
        log('❌ 配置错误：' + (str(exc) if isinstance(exc, TaskError) else '无法读取账号配置（详情已隐藏）'))
    failed = sum(r['failed'] > 0 for r in results)
    success = len(results) - failed
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else 'partial-failure' if failed and success
              else 'failure' if failed else 'dry-run' if dry else 'success')
    summary = dict(status=status, mode='dry-run' if dry else mode or 'sign',
                   accounts=len(tokens) if mode != 'add_account' else 1,
                   success=success if not dry else 0, failed=failed,
                   dryRunAccounts=len(results) if dry else 0, exitCode=exit_code,
                   tasks={key: sum(r[key] for r in results) for key in new_stats()})
    summary['notification'] = notify(summary, dry)
    summary['elapsedSeconds'] = round(time.monotonic()-started, 2)
    summary['finishTime'] = datetime.now().isoformat(timespec='seconds')
    log('-' * 48)
    log(f'任务统计：账号 {summary["accounts"]}，成功 {summary["success"]}，失败 {failed}，预演 {summary["dryRunAccounts"]}；子任务 {json.dumps(summary["tasks"], ensure_ascii=False)}')
    log(f'总耗时：{summary["elapsedSeconds"]} 秒；通知状态：{summary["notification"]}')
    log(f'完成时间：{summary["finishTime"]}；最终状态：{status}')
    if status == 'success':
        log('KURO_TASK_SUCCESS：全部账号任务已通过业务码检查')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
