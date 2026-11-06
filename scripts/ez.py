#!/usr/bin/env python3
# name: M-SEC 每日签到与积分查询
# cron: 44 9 * * *
# SPDX-License-Identifier: MIT
# Upstream: crazy0x70/EZ-Checkin, main.py
# https://github.com/crazy0x70/EZ-Checkin
# Upstream input contains no additional copyright/license notice.
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
"""M-SEC 独立维护版（Python 3.9+，仅标准库）。
EZ_ACCOUNTS：每个非空行一个 JSON 对象，Authorization 为原样请求头值；
可配套 username/password/CAPTCHA_TOKEN，不使用 & 或 @ 分隔账号。
也兼容 --config-file 的 user* JSON 配置及旧 Authorization= 配置。
密码登录仅在 EZ_PASSWORD_LOGIN=1 时启用，可能消耗云码额度；验证码服务
强制使用 HTTPS（原 HTTP 接口不再发送令牌，HTTPS 可用性尚未联网核验）。
默认不改写配置、不写积分历史；EZ_SAVE_TOKEN=1 / EZ_SAVE_STATE=1 显式启用。
青龙按 cron 单次执行；--daemon 保留启动执行及每天本地时区 08:00 常驻模式。
EZ_DRY_RUN=1 完全断网，不调用通知模块或写入业务文件。
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
        _ql_notify_identities = ('8381000e0a1ea0a9', 'scripts/ez.py', 'ez.py', 'ez')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

TITLE = 'M-SEC 每日签到与积分查询'
CATALOG = '8381000e0a1ea0a9'
BASE = 'https://msec.nsfocus.com/backend_api/'
OCR = 'https://api.jfbym.com/api/YmServer/customApi'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
SECRETS = set()
LAST_LOGIN = 0.0
TZ = ZoneInfo('Asia/Shanghai')
DRY = False

class Failure(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Failure('命令行参数无效，请运行 --help 查看格式')

def enabled(name):
    return os.getenv(name, '').lower() in TRUE

def clean(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[手机号已隐藏]', text)
    return ''.join(c if c >= ' ' else ' ' for c in text)

def log(message):
    print(f'[{datetime.now(TZ):%H:%M:%S}] {clean(message)}', flush=True)

def remember(user):
    for key in ('Authorization', 'authorization', 'password', 'CAPTCHA_TOKEN', 'LARK_WEBHOOK', 'FEISHU_WEBHOOK'):
        value = user.get(key)
        if isinstance(value, str) and value:
            SECRETS.add(value)

def request(url, payload, authorization='', headers=None):
    if DRY:
        raise Failure('预演禁止网络请求')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise Failure('仅允许无用户信息的 HTTPS 接口')
    hdr = {'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    if parsed.hostname == 'msec.nsfocus.com':
        hdr.update({'Origin': 'https://msec.nsfocus.com', 'Referer': 'https://msec.nsfocus.com/'})
        if authorization:
            hdr['Authorization'] = authorization
    elif authorization:
        raise Failure('禁止向其他服务发送账号凭据')
    if headers:
        hdr.update(headers)
    try:
        req = Request(url, data=json.dumps(payload).encode(), headers=hdr, method='POST')
        try:
            response = build_opener(NoRedirect()).open(req, timeout=30)
        except HTTPError as exc:
            if exc.code not in (400, 401, 403, 429):
                exc.close()
                raise Failure(f'HTTP 请求失败（{exc.code}）') from None
            response = exc
        with response:
            raw = response.read(1024 * 1024 + 1)
            http = response.code
        if len(raw) > 1024 * 1024:
            raise Failure('接口响应超过安全大小')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise Failure('接口响应结构无效')
        label = {
            'checkin/checkin': '签到或确认', 'point/common/get': '积分查询',
            'account/captcha': '获取验证码', 'account/login': '账号登录'
        }.get(parsed.path.removeprefix('/backend_api/'), '云码识别' if url == OCR else '机器人通知')
        code = data.get('status', data.get('code', data.get('StatusCode')))
        code = code if type(code) is int else '缺失或非数字'
        log(f'{label}响应：HTTP {http}，业务码 {code}')
        return http, data
    except Failure:
        raise
    except (URLError, TimeoutError, OSError, ValueError):
        raise Failure('网络、超时或 JSON 响应错误（详情已脱敏）') from None


def accounts_from(args):
    defaults = {}
    users = []
    if os.getenv('EZ_ACCOUNTS', '').strip():
        lines = [line.strip() for line in os.environ['EZ_ACCOUNTS'].splitlines() if line.strip()]
        for line in lines:
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError()
                users.append(value)
            except ValueError:
                users.append({'_invalid': True})
    elif Path(args.config_file).is_file():
        try:
            content = Path(args.config_file).read_text(encoding='utf-8')
            try:
                cfg = json.loads(content)
            except ValueError:
                cfg = {}
                for line in content.splitlines():
                    if '=' in line and not line.lstrip().startswith('#'):
                        k, v = line.split('=', 1)
                        cfg[k.strip()] = v.strip()
            if not isinstance(cfg, dict):
                raise ValueError()
            defaults = {k: cfg.get(k, '') for k in ('LARK_WEBHOOK', 'FEISHU_WEBHOOK', 'CAPTCHA_TOKEN')}
            users = [v.copy() for k, v in cfg.items() if k.startswith('user') and isinstance(v, dict)]
            if not users and cfg.get('Authorization'):
                users = [{'Authorization': cfg['Authorization']}]
        except (OSError, ValueError):
            raise Failure('兼容配置文件无法读取或格式错误') from None
    for user in users:
        for key in ('Authorization', 'authorization', 'password', 'username', 'CAPTCHA_TOKEN', 'LARK_WEBHOOK', 'FEISHU_WEBHOOK'):
            value = user.get(key, '')
            if not isinstance(value, str):
                user['_invalid'] = True
                user[key] = ''
        user['Authorization'] = user.get('Authorization') or user.get('authorization', '')
        user['CAPTCHA_TOKEN'] = user.get('CAPTCHA_TOKEN') or defaults.get('CAPTCHA_TOKEN') or os.getenv('CAPTCHA_TOKEN', '')
        for key, override in [('LARK_WEBHOOK', args.lark), ('FEISHU_WEBHOOK', args.feishu)]:
            user[key] = override or user.get(key) or defaults.get(key) or os.getenv(key, '')
        remember(user)
    return users


def atomic_json(path, value):
    path = Path(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            temp = handle.name
            os.chmod(temp, 0o600)
            json.dump(value, handle, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def persist_token(args, user, token):
    if not enabled('EZ_SAVE_TOKEN'):
        return
    if os.getenv('EZ_ACCOUNTS', '').strip():
        raise Failure('环境变量账号不支持 Token 写回；请关闭 EZ_SAVE_TOKEN')
    try:
        cfg = json.loads(Path(args.config_file).read_text(encoding='utf-8'))
        matches = [v for k, v in cfg.items() if k.startswith('user') and isinstance(v, dict)
                   and v.get('username') == user.get('username')]
        if len(matches) != 1:
            raise ValueError()
        matches[0]['Authorization'] = token
        atomic_json(args.config_file, cfg)
        log('Token 已安全写回显式指定的兼容配置')
    except (OSError, ValueError, AttributeError):
        raise Failure('Token 写回失败；仅支持含唯一 username 的 user* JSON 配置') from None


def identity(data):
    obj = data.get('data')
    if isinstance(obj, dict):
        objects = [obj] + [obj[k] for k in ('user', 'userInfo') if isinstance(obj.get(k), dict)]
        for item in objects:
            for key in ('nickname', 'username', 'displayName', 'uid'):
                if isinstance(item.get(key), (str, int)) and not isinstance(item.get(key), bool):
                    log(f'官方账号身份：{item[key]}')


def login(args, user):
    global LAST_LOGIN
    if not enabled('EZ_PASSWORD_LOGIN'):
        raise Failure('缺少有效 Token；密码登录需要显式开启 EZ_PASSWORD_LOGIN=1')
    if not all(user.get(k) for k in ('username', 'password', 'CAPTCHA_TOKEN')):
        raise Failure('密码登录缺少 username、password 或 CAPTCHA_TOKEN')
    wait = max(0, LAST_LOGIN + 10 - time.monotonic()) if LAST_LOGIN else 0
    if wait:
        time.sleep(wait)
    LAST_LOGIN = time.monotonic()
    # 默认只调用一次付费识别；避免上游十次重试产生不受控费用。
    http, captcha = request(BASE + 'account/captcha', {})
    obj = captcha.get('data')
    if http != 200 or not isinstance(obj, dict) or not obj.get('id') or not isinstance(obj.get('captcha'), str):
        raise Failure('获取验证码失败')
    image = obj['captcha'].split(',')[-1]
    http, recognized = request(OCR, {'token': user['CAPTCHA_TOKEN'], 'type': 10103, 'image': image})
    answer = recognized.get('data', {})
    answer = answer.get('data') if isinstance(answer, dict) else None
    if http != 200 or recognized.get('code') != 10000 or not isinstance(answer, str) or len(answer) != 5:
        raise Failure('云码识别失败；HTTPS 接口需自行确认可用，不回退明文 HTTP')
    http, auth = request(BASE + 'account/login', {'captcha_answer': answer, 'captcha_id': obj['id'],
                                                'username': user['username'], 'password': user['password']})
    token = auth.get('data', {})
    token = token.get('token') if isinstance(token, dict) else None
    if http != 200 or auth.get('status') != 200 or not isinstance(token, str) or not token:
        raise Failure('登录未通过业务成功检查')
    SECRETS.add(token)
    identity(auth)
    user['Authorization'] = token
    persist_token(args, user, token)
    log('登录成功；验证码及 Token 不输出')
    return token


def check_result(http, data):
    # 不接受仅包含“成功”的任意响应；已签到只接受上游明确的业务组合。
    already = (http in (200, 400) and data.get('status') == 400 and
               any(isinstance(data.get(k), str) and '已经签到' in data[k] for k in ('message', 'data')))
    ok = http == 200 and data.get('status') == 200
    return ok, already


def webhook_url(value, brand):
    if not value:
        return ''
    host = 'open.larksuite.com' if brand == 'LARK_WEBHOOK' else 'open.feishu.cn'
    value = value.strip().strip('"\'')
    if '://' not in value:
        value = 'https://' + host + '/open-apis/bot/v2/hook/' + value.lstrip('/\\')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.hostname != host or parsed.username or parsed.password or not parsed.path.startswith('/open-apis/bot/v2/hook/'):
        raise Failure('飞书/Lark Webhook 必须为官方 HTTPS 地址或机器人令牌')
    return value


def notify(body):
    mode = os.getenv('QINGLONG_NOTIFY', 'auto').lower()
    selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', CATALOG).strip())
    names = [CATALOG, Path(__file__).name, str(Path(__file__)).split('/scripts/')[-1]]
    selected = any(s and any(fnmatch.fnmatch(n, s) for n in names) for s in selectors)
    if mode in FALSE or (mode not in TRUE and not selected):
        return '已关闭或未选中'
    if DRY:
        return '预演已抑制通知网络调用'
    # 子进程隔离通知输出和异常，防止第三方模块打印凭据或更改业务退出码。
    roots = [Path(os.getenv('QINGLONG_NOTIFY_DIR', '.')), Path('/ql/data/scripts'), Path('/ql/scripts')]
    code = ('import importlib.util,sys; s=importlib.util.spec_from_file_location("notify",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(sys.argv[2],sys.argv[3])')
    paths = [root / 'notify.py' for root in roots]
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            paths.insert(0, Path(spec.origin))
    except (ImportError, ValueError):
        pass
    commands = [[sys.executable, '-c', code, str(p.resolve()), TITLE, body] for p in paths if p.is_file()]
    js = 'Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))'
    commands += [['node', '-e', js, str((root / 'sendNotify.js').resolve()), TITLE, body]
                 for root in roots if (root / 'sendNotify.js').is_file()]
    for cmd in commands:
        try:
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
            if proc.returncode == 0:
                return '已发送'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return '通知模块不可用或发送失败（保留业务退出码）'


def account_flow(args, user, index):
    started = time.monotonic()
    stats = dict(total=3, success=0, alreadyComplete=0, skipped=0, failure=0)
    def stage(number, title, action):
        t = time.monotonic()
        log(f'账号 {index} 阶段 {number}/3：{title}')
        try:
            result = action()
        except Exception:
            log(f'账号 {index} 阶段 {number}/3 失败，耗时 {time.monotonic()-t:.2f} 秒')
            raise
        log(f'账号 {index} 阶段 {number}/3 完成，耗时 {time.monotonic()-t:.2f} 秒')
        return result
    result = {'account': index, 'success': False, 'points': None, 'total_points': None}
    try:
        if user.get('_invalid'):
            raise Failure('账号行格式无效，需要单行 JSON 对象且凭据字段为字符串')
        if not user.get('Authorization') and not (enabled('EZ_PASSWORD_LOGIN') and all(user.get(k) for k in ('username', 'password', 'CAPTCHA_TOKEN'))):
            raise Failure('账号缺少 Authorization 或显式启用的完整密码登录参数')
        if DRY:
            for i, title in enumerate(['认证参数检查', '签到及已签到确认计划', '积分查询计划'], 1):
                stage(i, title, lambda: log('DRY_RUN_OK：仅检查计划，不发送请求、不写入文件'))
                stats['skipped'] += 1
            result['success'] = True
        else:
            token = stage(1, '认证', lambda: user.get('Authorization') or login(args, user))
            stats['success'] += 1
            def sign():
                nonlocal token
                http, data = request(BASE + 'checkin/checkin', {}, token)
                if http in (401, 403) or data.get('status') in (401, 403):
                    token = login(args, user)
                    http, data = request(BASE + 'checkin/checkin', {}, token)
                identity(data)
                ok, already = check_result(http, data)
                if not already:
                    time.sleep(1.2)
                    for delay in [0, 1.5, 3.0, 5.0]:
                        if delay:
                            time.sleep(delay)
                        ch, confirm = request(BASE + 'checkin/checkin', {}, token)
                        _, confirmed = check_result(ch, confirm)
                        if confirmed:
                            already = not ok
                            ok = True
                            break
                        if ch != 429 and confirm.get('status') != 429:
                            break
                if not (ok or already):
                    raise Failure('签到及已签到确认均未通过业务成功检查')
                return already
            if stage(2, '签到及确认', sign):
                stats['alreadyComplete'] += 1
                log('☑️ 官方明确返回已经签到')
            else:
                stats['success'] += 1
                log('✅ 签到成功')
            def points():
                http, data = request(BASE + 'point/common/get', {}, token)
                obj = data.get('data')
                if http != 200 or data.get('status') != 200 or not isinstance(obj, dict):
                    raise Failure('积分查询未通过业务成功检查')
                accrued, total = obj.get('accrued'), obj.get('total')
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 for v in (accrued, total)):
                    raise Failure('积分字段缺失或类型无效')
                identity(data)
                log(f'积分：当前 {total} ｜ 累计 {accrued}')
                if enabled('EZ_SAVE_STATE'):
                    path = Path(os.getenv('EZ_STATE_FILE', 'points_state.json'))
                    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                    state[user.get('username') or f'账号{index}'] = {'current_points': accrued, 'total_points': total,
                                                                   'last_update': datetime.now(TZ).isoformat()}
                    atomic_json(path, state)
                return accrued, total
            result['points'], result['total_points'] = stage(3, '积分查询及可选历史记录', points)
            stats['success'] += 1
            result['success'] = True
    except Exception as exc:
        stats['failure'] += 1
        stats['skipped'] = max(0, stats['total'] - stats['success'] - stats['alreadyComplete'] - stats['failure'])
        log(f'❌ 账号 {index}：{exc if isinstance(exc, Failure) else "处理失败（异常详情已隐藏）"}')
    stats['seconds'] = round(time.monotonic() - started, 2)
    result['statistics'] = stats
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {stats["seconds"]} 秒')
    return result


def run(args, config_error=None):
    started = time.monotonic()
    log('=' * 44)
    log(f'{TITLE} | 开始时间 {datetime.now(TZ):%Y-%m-%d %H:%M:%S %Z}')
    log(f'模式：{"断网预演" if DRY else "正式执行"}')
    users, results, error = [], [], config_error
    if not error:
        try:
            users = accounts_from(args)
            if not users:
                raise Failure('未找到账号，请设置 EZ_ACCOUNTS 或提供兼容配置文件')
        except Failure as exc:
            error = str(exc)
    log(f'账号总数：{len(users)}')
    if error:
        log(f'❌ 配置错误：{error}')
    else:
        for index, user in enumerate(users, 1):
            results.append(account_flow(args, user, index))
    success = sum(r['success'] for r in results)
    failed = len(users) - success
    status = 'configuration-error' if error else ('partial-failure' if success and failed else 'failure' if failed else 'dry-run' if DRY else 'success')
    body = f'{TITLE}；账号总数 {len(users)}，成功 {success}，失败 {failed}；状态 {status}'
    if error:
        body += '；配置错误'
    notification = notify(body)
    if not DRY:
        grouped = {}
        for user, result in zip(users, results):
            for brand in ('LARK_WEBHOOK', 'FEISHU_WEBHOOK'):
                if user.get(brand):
                    grouped.setdefault((brand, user[brand]), []).append(result)
        for (brand, value), rows in grouped.items():
            try:
                own_ok = sum(row['success'] for row in rows)
                text = f'{TITLE}；账号总数 {len(rows)}，成功 {own_ok}，失败 {len(rows)-own_ok}'
                for row in rows:
                    text += f'；账号 {row["account"]} 当前积分 {row["total_points"]} 累计积分 {row["points"]}'
                http, resp = request(webhook_url(value, brand), {'msg_type': 'text', 'content': {'text': text}})
                code = resp.get('code', resp.get('StatusCode'))
                log('附加机器人通知：' + ('已发送' if http == 200 and code == 0 else '业务发送失败'))
            except Exception:
                log('附加机器人通知失败（保留业务退出码）')
    log('-' * 44)
    log(body)
    totals = {k: sum(r['statistics'][k] for r in results) for k in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'通知：{notification}')
    log(f'完成时间 {datetime.now(TZ):%Y-%m-%d %H:%M:%S %Z}；总耗时 {time.monotonic()-started:.2f} 秒；最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps({'status': status, 'accounts': len(users), 'success': success, 'failed': failed,
                                      'configurationErrors': int(bool(error)), 'tasks': totals, 'results': results,
                                      'notification': notification}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return 1 if error or failed else 0


def main():
    global TZ, DRY
    DRY = enabled('EZ_DRY_RUN')
    parser = Parser(description=__doc__)
    parser.add_argument('--config-file', default='config.json', help='可选兼容配置文件')
    parser.add_argument('--lark', default='', help='可选 Lark 机器人令牌或 HTTPS 地址')
    parser.add_argument('--feishu', default='', help='可选飞书机器人令牌或 HTTPS 地址')
    parser.add_argument('--tz', default=os.getenv('TZ', 'Asia/Shanghai'), help='调度时区')
    parser.add_argument('--daemon', action='store_true', help='启动执行并常驻，每天 08:00 再执行')
    try:
        args, unknown = parser.parse_known_args()
        for arg in unknown:
            if arg.startswith('lark='):
                args.lark = args.lark or arg.split('=', 1)[1]
            elif arg.startswith('feishu='):
                args.feishu = args.feishu or arg.split('=', 1)[1]
            else:
                raise Failure('存在未知命令行参数')
        TZ = ZoneInfo(args.tz)
    except Exception:
        return run(None, '命令行参数或时区无效')
    code = run(args)
    if not args.daemon or DRY:
        return code
    # 常驻仅显式启用；每轮一条 TASK_SUMMARY，任一轮失败保留非零退出码。
    try:
        while True:
            now = datetime.now(TZ)
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            while datetime.now(TZ) < target:
                time.sleep(min(60, max(0, (target - datetime.now(TZ)).total_seconds())))
            code = max(code, run(args))
    except KeyboardInterrupt:
        return code

if __name__ == '__main__':
    sys.exit(main())
