# -*- coding: utf-8 -*-
# name: 库街区每日签到
# cron: 31 7 * * *
"""库街区签到，Python 3.9+，仅使用标准库。
来源：https://github.com/lango578/astrbot_plugin_kuro_checkin，main.py
上游作者标识：AstrBot User；维护转换遵循 MIT 许可。
原始输入未附带版权行；保留来源与作者标识。

KURO_ACCOUNTS：每个非空行一个账号，可为 token 或 JSON 对象：
{"token":"...","devcode":"...","distinct_id":"..."}。
在 https://www.kurobbs.com 登录，F12 → Application → Cookies 复制
user_token；设备字段可从本人 api.kurobbs.com 请求头 devCode、distinct_id 获取。
未填设备字段时沿用上游固定登录设备值。不要粘贴整个 Cookie。
KURO_TOKEN 是仅在 KURO_ACCOUNTS 未设置时使用的单账号兼容输入。
KURO_ENABLE_WUWA、KURO_ENABLE_PGR、KURO_ENABLE_FORUM_SIGN 默认 1；
KURO_ENABLE_FORUM_TASKS 默认 0（开启后浏览3篇、点赞5篇并登记分享，不发布文字）。
KURO_DRY_RUN=1 完全离线，只检查配置并展示计划，不发送通知或请求。
定时由青龙管理，默认每日07:30，时区以青龙为准；手动运行同一脚本即可立即签到。
绑定/解绑由增删环境变量完成；不保存凭据，不发短信，不自动登录。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
        _ql_notify_identities = ('df0326edb14b4597', 'scripts/astrbot_plugin_kuro.py', 'astrbot_plugin_kuro.py', 'astrbot_plugin_kuro')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import contextlib
import fnmatch
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

TITLE = '库街区每日签到'
CATALOG = 'df0326edb14b4597'
BASE = 'https://api.kurobbs.com'
DEFAULT_DEVICE = 'QZlE9fzPUlHON9FGUsfLfWwyM2dRKr6K'
DEFAULT_DISTINCT = '19dafdce461609-023472cbe40c9b-1e462c69-2073600-19dafdce462ebd'
GAMES = [('wuwa', '3', '鸣潮', '7f574e49b1f24c4c915e74bb1dfd4e4d'),
         ('pgr', '2', '战双', '1000')]


def log(text):
    print(f'[{datetime.now():%H:%M:%S}] {text}', flush=True)


def flag(name, default=False):
    value = os.getenv(name, '1' if default else '0').strip().lower()
    if value not in ('1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'):
        raise ValueError('布尔参数格式错误：' + name)
    return value in ('1', 'true', 'yes', 'on')


class Failure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, account):
        self.account = account
        self.opener = build_opener(NoRedirect())

    def post(self, path, data=None):
        if flag('KURO_DRY_RUN'):
            raise Failure('离线模式禁止请求')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Origin': 'https://www.kurobbs.com', 'Referer': 'https://www.kurobbs.com/',
            'source': 'h5', 'version': '3.0.1', 'token': self.account['token'],
            'devCode': self.account.get('devcode') or DEFAULT_DEVICE,
            'distinct_id': self.account.get('distinct_id') or DEFAULT_DISTINCT,
        }
        try:
            req = Request(BASE + path, data=urlencode(data or {}).encode(), headers=headers, method='POST')
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(1024 * 1024 + 1)
                if response.status != 200 or len(raw) > 1024 * 1024:
                    raise Failure('HTTP 状态异常或响应过大')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise Failure('响应结构异常')
            return result
        except Failure:
            raise
        except Exception:
            raise Failure('网络请求或响应解析失败') from None


def successful(result):
    # 有明确失败码时不能用 success=true 将其覆盖。
    return result.get('code') == 200 or ('code' not in result and result.get('success') is True)


def checked(result, already=False):
    if already and result.get('code') == 1511:
        return 'already'
    if successful(result):
        return 'success'
    code = result.get('code')
    if code == 220:
        raise Failure('登录过期，请重新获取凭据')
    if code == 1513:
        raise Failure('用户信息异常')
    # 不输出服务端错误文字，以免含凭据或手机号。
    label = str(code) if isinstance(code, int) else '未知'
    raise Failure('业务未成功，代码：' + label)


def parse_account(line):
    try:
        account = json.loads(line) if line.startswith('{') else {'token': line}
    except Exception:
        raise Failure('账号 JSON 格式错误') from None
    if not isinstance(account, dict) or not isinstance(account.get('token'), str) or not account['token'].strip():
        raise Failure('缺少 token')
    for key in ('token', 'devcode', 'distinct_id'):
        value = account.get(key, '')
        if not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise Failure('凭据字段必须为不含控制字符的 ASCII 文本')
    return account


def public_text(value, account):
    text = str(value)
    for key in ('token', 'devcode', 'distinct_id'):
        secret = account.get(key)
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    text = re.sub(r'(?<!\d)1\d{10}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


class Runner:
    def __init__(self, index, client, dry):
        self.index, self.client, self.dry = index, client, dry
        self.stats = dict(success=0, already=0, skipped=0, failure=0)
        self.started = time.monotonic()
        self.stage = 0

    def step(self, name, action, enabled=True):
        self.stage += 1
        start = time.monotonic()
        log(f'账号{self.index} 阶段{self.stage} {name} 开始')
        try:
            if not enabled:
                status, detail = 'skipped', '配置已关闭'
            elif self.dry:
                status, detail = 'skipped', '离线预演：已检查执行计划，未发请求'
            else:
                result = action()
                status, detail = result if isinstance(result, tuple) else (result, '')
        except Failure as exc:
            status, detail = 'failure', str(exc)
        except Exception:
            status, detail = 'failure', '响应字段异常或内部执行错误'
        self.stats[status] += 1
        log(f'账号{self.index} 阶段{self.stage} {name} {status} {detail} 耗时{time.monotonic()-start:.2f}秒')

    def user(self):
        resp = self.client.post('/user/mineV2', {'size': '10'})
        checked(resp)
        mine = resp.get('data', {}).get('mine', {})
        identity = [(key, mine[key]) for key in ('nickname', 'userName', 'displayName', 'userId') if mine.get(key) is not None]
        if not identity:
            raise Failure('未取得账号身份')
        return 'success', ' '.join(f'{key}={public_text(value, self.client.account)}' for key, value in identity)

    def game(self, game):
        _, game_id, _, server = game
        roles = None
        failures = 0
        for path in ('/gamer/role/list', '/user/role/findRoleList'):
            try:
                resp = self.client.post(path, {'gameId': game_id})
                checked(resp)
                data = resp.get('data')
                items = data if isinstance(data, list) else data.get('roleList', [])
                if not isinstance(items, list):
                    raise Failure('角色列表结构异常')
                roles = items
                if roles:
                    break
            except Exception:
                failures += 1
        if not roles:
            if failures:
                raise Failure('主备角色接口未能确认角色信息')
            return 'skipped', '已确认未绑定该游戏角色'
        role = roles[0]
        if not role.get('roleId'):
            raise Failure('角色缺少 roleId')
        if role.get('roleName'):
            log('角色名称：' + public_text(role['roleName'], self.client.account))
        payload = {'gameId': game_id, 'serverId': role.get('serverId') or server, 'roleId': str(role['roleId'])}
        status = checked(self.client.post('/encourage/signIn/v2', dict(payload, reqMonth=datetime.now().strftime('%m'))), True)
        try:
            reward = self.client.post('/encourage/signIn/queryRecordV2', payload)
            checked(reward)
            records = reward.get('data')
            if isinstance(records, list) and records and records[0].get('goodsName'):
                log('签到记录奖励：' + public_text(records[0]['goodsName'], self.client.account))
        except Exception:
            log('⚠️ 奖励查询失败，不影响已核验的签到结果')
        return status, '签到成功' if status == 'success' else '今天已签到'

    def community(self):
        return checked(self.client.post('/user/signIn', {'gameId': '3'}), True)

    def gold(self):
        resp = self.client.post('/encourage/gold/getTotalGold')
        checked(resp)
        value = resp.get('data', {}).get('goldNum')
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise Failure('余额字段缺失或异常')
        return 'success', f'当前库洛币：{value}'

    def forum(self):
        resp = self.client.post('/forum/list', {'forumId': '9', 'gameId': '3', 'pageIndex': '1', 'pageSize': '20', 'searchType': '3', 'timeType': '0'})
        checked(resp)
        posts = resp.get('data', {}).get('postList', [])
        if not isinstance(posts, list) or len(posts) < 5:
            raise Failure('帖子不足，无法核验完整论坛任务')
        failed = 0
        for pos, post in enumerate(posts[:5]):
            if pos < 3:
                try:
                    checked(self.client.post('/forum/getPostDetail', {'isOnlyPublisher': '0', 'postId': str(post['postId']), 'showOrderTyper': '2'}))
                    log(f'浏览 {pos+1}/3 成功')
                except Exception:
                    failed += 1
                    log(f'浏览 {pos+1}/3 失败')
                time.sleep(1)
            try:
                checked(self.client.post('/forum/like', {'forumId': 11, 'gameId': 3, 'likeType': 1, 'operateType': 1, 'postCommentId': '', 'postCommentReplyId': '', 'postId': str(post['postId']), 'postType': 1, 'toUserId': str(post.get('userId', ''))}))
                log(f'点赞 {pos+1}/5 成功')
            except Exception:
                failed += 1
                log(f'点赞 {pos+1}/5 失败')
            time.sleep(1)
        try:
            checked(self.client.post('/encourage/level/shareTask', {'gameId': 3}))
            log('分享登记成功（不发布文字）')
        except Exception:
            failed += 1
            log('分享登记失败')
        if failed:
            raise Failure(f'论坛任务部分失败：{failed}项')
        return 'success', '浏览3篇、点赞5篇、分享登记均已核验'


def notify(body, dry):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in ('0', 'false', 'no', 'off'):
        return '已关闭'
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if switch not in ('1', 'true', 'yes', 'on'):
        if selectors is not None:
            choices = re.split(r'[,;\s]+', selectors.strip())
            names = (CATALOG, Path(__file__).name, 'scripts/' + Path(__file__).name)
            if not any(fnmatch.fnmatch(n, p) for n in names for p in choices if p):
                return '未选中'
        # 此脚本作为已列入的维护账号任务，默认发送。
    if dry:
        return '离线预演：已生成脱敏通知，未调用通知渠道'
    paths = [Path('/ql/data/scripts'), Path('/ql/scripts')]
    if os.getenv('QINGLONG_NOTIFY_DIR'):
        paths.insert(0, Path(os.environ['QINGLONG_NOTIFY_DIR']))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                module = importlib.import_module('notify')
            except ImportError:
                module = None
            if module and callable(getattr(module, 'send', None)):
                module.send(TITLE, body)
                return '已发送'
            for folder in paths:
                path = folder / 'notify.py'
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('ql_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.send(TITLE, body)
                    return '已发送'
            for folder in paths:
                path = folder / 'sendNotify.js'
                if path.is_file():
                    js = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
                    result = subprocess.run(['node', '-e', js, str(path), TITLE, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)
                    return '已发送' if result.returncode == 0 else '通知失败'
    except Exception:
        return '通知失败，保留业务退出码'
    return '通知渠道不可用，保留业务退出码'


def main():
    started = time.monotonic()
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}')
    lines = [x.strip() for x in os.getenv('KURO_ACCOUNTS', os.getenv('KURO_TOKEN', '')).splitlines() if x.strip()]
    dry = os.getenv('KURO_DRY_RUN', '0').lower() in ('1', 'true', 'yes', 'on')
    log(f'模式：{"离线预演" if dry else "正式运行"}；账号数量：{len(lines)}')
    results = []
    configuration_error = False
    try:
        dry = flag('KURO_DRY_RUN')
        enabled = {key: flag('KURO_ENABLE_' + key.upper(), key != 'forum_tasks') for key in ('wuwa', 'pgr', 'forum_sign', 'forum_tasks')}
        if not lines:
            raise Failure('未配置 KURO_ACCOUNTS')
        if not any(enabled.values()):
            raise Failure('没有启用任何签到或论坛任务')
    except (ValueError, Failure) as exc:
        log('❌ 配置错误：' + str(exc))
        configuration_error = True
    if not configuration_error:
        for index, line in enumerate(lines, 1):
            try:
                client = Client(parse_account(line))
                runner = Runner(index, client, dry)
                runner.step('账号身份查询', runner.user)
                for game in GAMES:
                    runner.step(game[2] + '签到', lambda g=game: runner.game(g), enabled[game[0]])
                runner.step('社区签到', runner.community, enabled['forum_sign'])
                runner.step('论坛每日任务', runner.forum, enabled['forum_tasks'])
                runner.step('库洛币余额', runner.gold)
                stats = runner.stats
                elapsed = time.monotonic() - runner.started
            except Exception:
                log(f'账号{index} 配置错误：账号格式无效')
                stats = dict(success=0, already=0, skipped=0, failure=1)
                elapsed = 0
            results.append(stats)
            log(f'账号{index} 统计：总任务{sum(stats.values())} 成功{stats["success"]} 已完成{stats["already"]} 跳过{stats["skipped"]} 失败{stats["failure"]} 耗时{elapsed:.2f}秒')
    failed = sum(r['failure'] > 0 for r in results)
    good = len(results) - failed
    status = ('configuration-error' if configuration_error else 'partial-failure' if failed and good else 'failure' if failed else 'dry-run' if dry else 'success')
    code = 1 if configuration_error or failed else 0
    totals = {key: sum(r[key] for r in results) for key in ('success', 'already', 'skipped', 'failure')}
    body = f'状态：{status}；账号总数{len(lines)}，成功{good}，失败{failed}；子任务{json.dumps(totals, ensure_ascii=False)}'
    notice = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log(f'通知状态：{notice}；总耗时{time.monotonic()-started:.2f}秒')
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；最终状态：{status}')
    print('TASK_SUMMARY=' + json.dumps(dict(status=status, mode='dry-run' if dry else 'live', accounts=len(lines), successfulAccounts=good, failedAccounts=failed, tasks=totals, notification=notice, exitCode=code), ensure_ascii=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
