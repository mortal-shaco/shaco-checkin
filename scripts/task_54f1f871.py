#!/usr/bin/env python3
# name: HoYoLAB 多游戏签到
# cron: 35 10 * * *
# SPDX-License-Identifier: MIT
# Source: Jesewe/HoYoLAB-Auto-Check-In, main.py
# https://github.com/Jesewe/HoYoLAB-Auto-Check-In
# Upstream revision: f28e2860265afa9b7457b836590b2fa68f7b6687
# MIT License (upstream attribution retained above; input contains no copyright notice).
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
"""独立 HoYoLAB 签到，Python 3.9+，无需第三方依赖。

HOYOLAB_ACCOUNTS：每个非空行填写一个账号的完整 Cookie，不用 & 或 @ 分账号。
获取：登录官方 https://www.hoyolab.com，在开发者工具 Network 中打开本人
签到请求，将 Request Headers 的 Cookie 整段复制；不要复制到日志或聊天。
HOYOLAB_GAMES：明确选择游戏，以空格或逗号隔开：zzz gi hsr hi3 tot。
兼容原 config.json（只读，不生成）：accounts=[{cookie:..., games:[...]}]，
discord={webhook_url:..., user_id:...}。环境账号优先于配置账号。
保留 --accounts 0 1、--games gi hsr；新增 --info-only 只查状态和奖励。
HOYOLAB_DRY_RUN=1 完全断网，包括通知；QINGLONG_NOTIFY 控制青龙通知。
原源码没有 cron；建议每天 08:15 运行。Discord 仅显式配置时发送脱敏总结。
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
        _ql_notify_identities = ('54f1f8710298d67d', 'scripts/task_54f1f871.py', 'task_54f1f871.py', 'task_54f1f871')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import fnmatch
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
from datetime import datetime

TITLE = 'HoYoLAB 多游戏签到'
CATALOG = '54f1f8710298d67d'
ENDPOINTS = {
    'zzz': ('https://sg-act-nap-api.hoyolab.com/event/luna/zzz/os/', 'e202406031448091'),
    'gi': ('https://sg-hk4e-api.hoyolab.com/event/sol/', 'e202102251931481'),
    'hsr': ('https://sg-public-api.hoyolab.com/event/luna/os/', 'e202303301540311'),
    'hi3': ('https://sg-public-api.hoyolab.com/event/mani/', 'e202110291205111'),
    'tot': ('https://sg-public-api.hoyolab.com/event/luna/os/', 'e202202281857121'),
}
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = set()
DRY = os.getenv('HOYOLAB_DRY_RUN', '').lower() in TRUE


def register_secret(value):
    if not isinstance(value, str):
        return
    if value:
        SECRETS.add(value)
    for part in value.split(';'):
        if '=' in part:
            secret = part.split('=', 1)[1].strip()
            if secret:
                SECRETS.add(secret)


def clean(value, public_uid=False):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        text = text.replace(secret, '[已隐藏]')
    if not public_uid:
        text = re.sub(r'(?<!\d)\+?\d[\d -]{9,}\d(?!\d)', '[手机号已隐藏]', text)
    return re.sub(r'[\x00-\x1f\x7f]', ' ', text)[:500]


def log(message, public_uid=False):
    print(f'[{datetime.now():%H:%M:%S}] {clean(message, public_uid=public_uid)}', flush=True)


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TaskError('拒绝重定向，避免凭据跨站发送')


def request(url, cookie=None, game=None, payload=None):
    if DRY:
        raise TaskError('预演模式禁止网络')
    headers = {'Accept': 'application/json, text/plain, */*',
               'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'}
    if cookie is not None:
        headers.update({'Cookie': cookie, 'x-rpc-signgame': game})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json;charset=UTF-8'
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise TaskError('响应过大')
            if not raw and cookie is None and response.status == 204:
                return {}
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise TaskError('响应结构异常')
            return result
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 请求失败，状态 {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise TaskError('网络超时、传输失败或响应不是有效 JSON') from None


def business(result):
    code = result.get('retcode')
    if type(code) is not int:
        raise TaskError('响应缺少有效业务状态码')
    if code != 0:
        # Do not print server messages: they may echo credentials.
        known = {-100: 'Cookie 无效，请重新获取', -10002: '账号未开通此游戏'}
        raise TaskError(known.get(code, '接口返回非成功业务状态'))
    data = result.get('data')
    if not isinstance(data, dict):
        raise TaskError('响应缺少有效业务数据')
    return data


def info(cookie, game):
    base, act = ENDPOINTS[game]
    data = business(request(base + 'info?' + urllib.parse.urlencode({'lang': 'en-us', 'act_id': act}), cookie, game))
    if type(data.get('is_sign')) is not bool:
        raise TaskError('签到状态字段异常')
    for key in ('nickname', 'username', 'display_name', 'uid'):
        if isinstance(data.get(key), (str, int)) and not isinstance(data[key], bool):
            log(f'官方账号 {key}: {data[key]}', public_uid=(key == 'uid'))
    log(f"{game.upper()} 今日签到：{'已签到' if data['is_sign'] else '未签到'}；累计天数：{data.get('total_sign_day', '未返回')}；漏签天数：{data.get('sign_cnt_missed', '未返回')}")
    awards = data.get('awards', data.get('rewards', []))
    if isinstance(awards, list) and awards:
        for award in awards:
            if isinstance(award, dict):
                log(f"奖励：{award.get('name', '未命名')} × {award.get('cnt', award.get('count', 0))}")
    else:
        log('接口未返回奖励列表')
    return data


def game_task(cookie, game, info_only):
    before = info(cookie, game)
    if info_only:
        return 'success'
    if before['is_sign']:
        log('☑️ Already checked in today：官方状态确认今日已签到')
        return 'alreadyComplete'
    base, act = ENDPOINTS[game]
    params = {'lang': 'en-us', 'act_id': act}
    result = request(base + 'sign?' + urllib.parse.urlencode(params), cookie, game, params)
    code = result.get('retcode')
    if type(code) is not int or code not in (0, -5003):
        business(result)
        raise TaskError('签到返回不可识别状态')
    data = result.get('data')
    if not isinstance(data, dict):
        raise TaskError('签到响应缺少数据，无法确认成功')
    if data.get('is_risk') or data.get('gt') or data.get('challenge') or data.get('success') not in (None, 0, True):
        raise TaskError('签到触发验证或风险检查，请在官方页面处理')
    after = info(cookie, game)
    if not after['is_sign']:
        raise TaskError('签到后复核未签到，不能确认业务成功')
    log('✅ Check-in successful!：官方状态复核成功')
    return 'alreadyComplete' if code == -5003 else 'success'


def games_list(value):
    if isinstance(value, str):
        value = re.split(r'[\s,]+', value.strip())
    if not isinstance(value, list) or not value or any(not isinstance(g, str) or g.lower() not in ENDPOINTS for g in value):
        raise TaskError('必须明确指定有效游戏：zzz gi hsr hi3 tot')
    return list(dict.fromkeys(g.lower() for g in value))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TaskError('命令行参数错误，请使用 --help 查看说明')


def load():
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--accounts', type=int, nargs='*')
    parser.add_argument('--games', nargs='*')
    parser.add_argument('--info-only', action='store_true')
    args = parser.parse_args()
    config = {}
    # No implicit writes, no private repository dependency.
    if Path('config.json').is_file():
        try:
            config = json.loads(Path('config.json').read_text(encoding='utf-8'))
        except (ValueError, OSError):
            raise TaskError('config.json 无法读取或不是有效 JSON') from None
        if not isinstance(config, dict):
            raise TaskError('config.json 顶层必须是对象')
    if 'HOYOLAB_ACCOUNTS' in os.environ:
        accounts = [{'cookie': line.strip(), 'games': os.getenv('HOYOLAB_GAMES', '')}
                    for line in os.environ['HOYOLAB_ACCOUNTS'].splitlines() if line.strip()]
    else:
        accounts = config.get('accounts', [])
    if not isinstance(accounts, list) or not accounts:
        raise TaskError('缺少账号：请配置 HOYOLAB_ACCOUNTS，每个非空行一个完整 Cookie')
    # Register secrets before processing any response or notification.
    for account in accounts:
        if isinstance(account, dict):
            register_secret(account.get('cookie'))
    discord = config.get('discord', {})
    if not isinstance(discord, dict):
        raise TaskError('discord 配置必须是对象')
    register_secret(discord.get('webhook_url'))
    indices = args.accounts or list(range(len(accounts)))  # retain upstream empty-filter semantics
    return accounts, indices, args, discord


def notification_selected():
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return False
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if selectors is not None:
        script = Path(__file__).resolve()
        names = [CATALOG, script.name, 'scripts/' + script.name]
        if 'scripts' in script.parts:
            names.append('/'.join(script.parts[script.parts.index('scripts'):]))
        return any(fnmatch.fnmatchcase(name, item) for item in re.split(r'[,;\s]+', selectors.strip()) if item for name in names)
    return switch in TRUE  # listed-only: no implicit subscription when no list was provided


def notify(body):
    if not notification_selected():
        return '未选中或已关闭'
    if DRY:
        return '预演跳过（断网）'
    # Isolate optional notification code and suppress its stdout/stderr, including secrets.
    worker = '''import importlib.util,json,sys
p=json.loads(sys.stdin.read())
if p['path']:
 s=importlib.util.spec_from_file_location('ql_notify',p['path']); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
else:
 import notify as m
m.send(p['title'],p['body'])
'''
    locations = [None]
    roots = [os.getenv('QINGLONG_NOTIFY_DIR'), '/ql/data/scripts', '/ql/scripts']
    locations.extend(str(Path(root) / 'notify.py') for root in roots if root and (Path(root) / 'notify.py').is_file())
    for path in locations:
        try:
            proc = subprocess.run([sys.executable, '-c', worker], input=json.dumps({'path': path, 'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    for root in roots:
        if not root or not (Path(root) / 'sendNotify.js').is_file():
            continue
        try:
            proc = subprocess.run(['node', '-e', "const fs=require('fs'); const p=JSON.parse(fs.readFileSync(0,'utf8')); Promise.resolve(require(p.path).sendNotify(p.title,p.body)).catch(()=>process.exit(1));"], input=json.dumps({'path': str(Path(root) / 'sendNotify.js'), 'title': TITLE, 'body': body}), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '不可用或发送失败（保留业务退出码）'


def main():
    started = time.monotonic()
    start_time = datetime.now().isoformat(timespec='seconds')
    log(f'===== {TITLE} =====')
    log(f"开始时间：{start_time}；模式：{'断网预演' if DRY else '正式运行'}")
    summary = {'mode': 'dry-run' if DRY else 'live', 'accounts': 0, 'success': 0, 'failed': 0,
               'tasks': dict.fromkeys(['total', 'success', 'alreadyComplete', 'skipped', 'failed'], 0)}
    discord = {}
    configuration_error = False
    log('阶段 1：读取账号与任务参数')
    try:
        accounts, indices, args, discord = load()
        summary['accounts'] = len(indices)
        log(f'账号数量：{len(indices)}；阶段 1：参数检查完成，耗时 {time.monotonic()-started:.2f} 秒')
        for position, index in enumerate(indices, 1):
            tick = time.monotonic()
            stats = dict.fromkeys(summary['tasks'], 0)
            log(f'账号 {position}（配置索引 {index}）开始')
            try:
                if index < 0 or index >= len(accounts) or not isinstance(accounts[index], dict):
                    raise TaskError('账号索引无效或账号配置格式错误')
                account = accounts[index]
                cookie = account.get('cookie')
                if not isinstance(cookie, str) or not cookie.strip() or any(c in cookie for c in '\r\n\x00'):
                    raise TaskError('账号 Cookie 缺失或含非法换行')
                games = games_list(args.games or os.getenv('HOYOLAB_GAMES') or account.get('games'))
                for stage, game in enumerate(games, 2):
                    step = time.monotonic()
                    stats['total'] += 1
                    log(f"账号 {position} 阶段 {stage}：{game.upper()} {'查询信息' if args.info_only else '查询并签到'}")
                    try:
                        if DRY:
                            log(f'{game.upper()} 参数检查通过；将查询状态、奖励' + ('，并在未签到时提交签到、复核状态' if not args.info_only else ''))
                            stats['skipped'] += 1
                        else:
                            stats[game_task(cookie, game, args.info_only)] += 1
                    except Exception as exc:
                        stats['failed'] += 1
                        log(f'❌ {exc if isinstance(exc, TaskError) else "内部处理异常（已隐藏详情）"}')
                    log(f'账号 {position} 阶段 {stage} 结束，耗时 {time.monotonic() - step:.2f} 秒')
            except TaskError as exc:
                stats['total'] += 1
                stats['failed'] += 1
                log(f'❌ 账号配置错误：{exc}')
            summary['failed' if stats['failed'] else 'success'] += 1
            for key in stats:
                summary['tasks'][key] += stats[key]
            log(f'账号 {position} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}，耗时 {time.monotonic()-tick:.2f} 秒')
    except Exception as exc:
        configuration_error = True
        log(f'❌ 配置错误：{exc if isinstance(exc, TaskError) else "无法解析配置（已隐藏详情）"}')
        log('账号数量：0')
    failed = configuration_error or summary['failed'] > 0
    status = ('configuration-error' if configuration_error else 'partial-failure' if summary['failed'] and summary['success'] else 'failure' if failed else 'dry-run' if DRY else 'success')
    body = f"状态：{status}；账号总数 {summary['accounts']}，成功 {summary['success']}，失败 {summary['failed']}；子任务 {json.dumps(summary['tasks'], ensure_ascii=False)}"
    body = clean(body)
    # Optional upstream Discord channel; never transmit on dry-run, no full logs.
    if discord.get('webhook_url'):
        if DRY:
            log('Discord：预演跳过（断网）')
        else:
            url = discord['webhook_url']
            parsed = urllib.parse.urlparse(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme != 'https' or parsed.netloc != 'discord.com' or not parsed.path.startswith('/api/webhooks/'):
                log('Discord：地址无效（保留业务退出码）')
            else:
                try:
                    user_id = discord.get('user_id', '')
                    content = (f'<@{user_id}>\n' if isinstance(user_id, str) and re.fullmatch(r'\d{1,25}', user_id) else '') + body
                    request(url, payload={'content': content})
                    log('Discord：已发送脱敏总结')
                except Exception:
                    log('Discord：发送失败（保留业务退出码）')
    try:
        summary['notification'] = notify(body)
    except Exception:
        summary['notification'] = '通知异常（保留业务退出码）'
    summary.update(status=status, exitCode=1 if failed else 0, startTime=start_time,
                   finishTime=datetime.now().isoformat(timespec='seconds'), elapsedSeconds=round(time.monotonic()-started, 2))
    log('----------------------------------------')
    log(body)
    log(f'通知状态：{summary["notification"]}；总耗时：{summary["elapsedSeconds"]} 秒')
    log(f'完成时间：{summary["finishTime"]}；最终状态：{status}')
    if DRY and not failed:
        log('DRY_RUN_OK：预演完成，未执行网络请求或签到')
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return summary['exitCode']


if __name__ == '__main__':
    sys.exit(main())
