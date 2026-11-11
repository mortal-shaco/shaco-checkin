#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: Qoder 每日签到
# cron: 6 11 * * *
"""Qoder 每日签到，Python 标准库独立实现。

来源 spirodelazz/ide-daily-checkin/scripts/qoder_checkin.py，
合并自 wallechfox/qoder-checkin（MIT）的 qoder_core.py + 02_checkin.py。
相关凭据格式参考同仓库 qoder_extract.py（改编自 01_extract.py，MIT）。
保留上游 MIT 授权与归属。

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

QODER_ACCOUNTS 每个非空行一个 JSON 对象，包含 accessToken、refreshToken、
expiresAt 以及可选 device 对象。兼容原 JSON 数组和 {"accounts": [...]}。
从本人已授权的 Qoder 登录请求取得 Bearer 令牌及 Cosy-* 请求头，刷新令牌从
本人登录会话取得。无需安装客户端或执行提取程序，禁止分享这些凭据。
设备字段沿用原 QODER_COSY_* 环境变量，也可逐账号提供 device。
兼容 QODER_CONFIG_FILE、QODER_ACCOUNTS_FILE 指向自行提供的 JSON 文件。
环境账号存在时优先使用环境输入，避免意外执行文件中的额外账号。

保留已发布计划，每日按青龙时区 11:06 执行。上游主控的 10:20 主跑及
15:00、20:30 兜底可沿用独立计划任务。日志时间使用北京时间。
活动未下发时本轮最多查询 3 次，间隔 20 秒，兼容 QODER_EMPTY_RETRY、
QODER_EMPTY_WAIT 覆盖查询次数及间隔秒数，次数至少 1，间隔至少 0。
无效整数沿用默认值；仅没有 CLAIM_BENEFIT 时重查，预演不等待。
兼容 silent、poll、silent-poll 参数，均执行查询与幂等奖励领取。
QODER_DRY_RUN=1 完全断网，仅校验输入及预演流程和通知。
QODER_CACHE_FILE 可选，显式开启私有令牌缓存，刷新后原子保存，原凭据文件保持只读。
QODER_LOG_FILE 可选 JSON 行日志，默认 qoder_checkin.log，预演不写文件。
QINGLONG_NOTIFY 支持 auto/1/0，auto 按 QINGLONG_NOTIFY_SCRIPTS 选择，
未设置选择器时本任务默认入选。预演只展示脱敏通知内容。
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
        _ql_notify_identities = ('9cceef808f4e3500', 'scripts/qoder_checkin.py', 'qoder_checkin.py', 'qoder_checkin')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import base64
import fnmatch
import hashlib
import importlib.util
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
from datetime import datetime, timezone

TITLE = 'Qoder 每日签到'
CATALOG = '9cceef808f4e3500'
HERE = Path(__file__).resolve().parent
PATH_CAMPAIGNS = '/sash/api/v1/me/campaigns'
PATH_CLAIM = '/sash/api/v1/me/campaigns/{cid}/claim'
PATH_REFRESH = '/api/v1/deviceToken/refresh'
DEVICE_KEYS = [
    ('clientType', 'Cosy-ClientType', 'QODER_COSY_CLIENT_TYPE', '10'),
    ('machineOS', 'Cosy-MachineOS', 'QODER_COSY_MACHINE_OS', ''),
    ('machineHostname', 'Cosy-MachineHostname', 'QODER_COSY_MACHINE_HOSTNAME', ''),
    ('machineId', 'Cosy-MachineId', 'QODER_COSY_MACHINE_ID', ''),
    ('machineToken', 'Cosy-MachineToken', 'QODER_COSY_MACHINE_TOKEN', ''),
    ('machineCode', 'Cosy-MachineCode', 'QODER_COSY_MACHINE_CODE', ''),
    ('machineType', 'Cosy-MachineType', 'QODER_COSY_MACHINE_TYPE', ''),
    ('version', 'Cosy-Version', 'QODER_COSY_VERSION', ''),
]
SECRETS = set()

# 保留上游 pythonw 无控制台运行能力。
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError, ValueError):
        pass


class TaskError(Exception):
    pass


def flag(name):
    return os.getenv(name, '').strip().lower() in ('1', 'true', 'yes', 'on')


def stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() + 28800))


def safe(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    return ''.join(c for c in text if c >= ' ' and c != '\x7f')


def log(message):
    print(f'[{stamp()[11:]}] {safe(message)}', flush=True)


def read_json(path, default):
    try:
        with open(path, encoding='utf-8-sig') as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default
    except (OSError, ValueError):
        raise TaskError('配置文件不可读或 JSON 格式错误') from None


def coerce_exp(value):
    if not value or isinstance(value, bool):
        return 0
    try:
        number = float(value)
        if not math.isfinite(number):
            return 0
        return int(number / 1000 if number > 1e12 else number)
    except (ValueError, TypeError, OverflowError):
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return int(dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp())
        except (ValueError, TypeError, OverflowError):
            return 0


def jwt_exp(token):
    try:
        segment = token.split('.')[1]
        payload = json.loads(base64.urlsafe_b64decode(segment + '=' * (-len(segment) % 4)))
        return coerce_exp(payload.get('exp'))
    except (ValueError, IndexError, TypeError, AttributeError):
        return 0


def normalize(item, index):
    if not isinstance(item, dict):
        return {'error': '账号必须为 JSON 对象', 'index': index}
    lower = {str(k).lower(): v for k, v in item.items()}
    def pick(*names):
        return next((lower[n.lower()] for n in names if lower.get(n.lower())), '')
    account = {
        'accessToken': pick('accessToken', 'access_token', 'token'),
        'refreshToken': pick('refreshToken', 'refresh_token'),
        'expiresAt': coerce_exp(pick('expiresAt', 'expires_at')),
        'device': item.get('device', {}), 'index': index,
    }
    for key in ('accessToken', 'refreshToken'):
        value = account[key]
        if not isinstance(value, str) or any(c.isspace() for c in value):
            account['error'] = '令牌必须为无空白的字符串'
        elif value:
            SECRETS.add(value)
    if not account['accessToken'] and not account['refreshToken']:
        account['error'] = '缺少访问令牌或刷新令牌'
    if not isinstance(account['device'], dict):
        account['error'] = 'device 必须为对象'
        account['device'] = {}
    for key in ('machineToken', 'machineCode', 'machineId', 'machineHostname'):
        value = account['device'].get(key)
        if isinstance(value, str) and value:
            SECRETS.add(value)
    source = json.dumps([account['accessToken'], account['refreshToken']], ensure_ascii=False)
    account['cacheKey'] = hashlib.sha256(source.encode()).hexdigest()
    return account


def load_accounts():
    raw = os.getenv('QODER_ACCOUNTS', '').strip()
    if raw:
        try:
            doc = json.loads(raw)
        except ValueError:
            items = []
            for line in raw.splitlines():
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except ValueError:
                        items.append(None)
            return [normalize(item, i + 1) for i, item in enumerate(items)]
    else:
        doc = read_json(os.getenv('QODER_ACCOUNTS_FILE') or HERE / 'qoder_accounts.json', [])
    if isinstance(doc, dict):
        doc = doc.get('accounts', [doc])
    if not isinstance(doc, list):
        raise TaskError('账号配置必须为每行 JSON 对象或旧版 JSON 数组')
    return [normalize(item, i + 1) for i, item in enumerate(doc)]


def empty_retry_plan():
    """沿用当前上游的空活动查询次数、间隔及非法值兼容规则。"""
    def integer(name, default):
        try:
            return int(os.getenv(name, '').strip() or default)
        except (TypeError, ValueError):
            return default
    return max(1, integer('QODER_EMPTY_RETRY', 3)), max(0, integer('QODER_EMPTY_WAIT', 20))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise TaskError('接口必须为无用户信息的 HTTPS 地址')
    return url


class Service:
    def __init__(self, config, dry, use_env=True):
        self.config = config
        self.dry = dry
        bases = os.getenv('QODER_BASE_URL', '').strip() if use_env else ''
        self.bases = bases.split(',') if bases else config.get('baseUrls', ['https://openapi.qoder.com.cn'])
        if not isinstance(self.bases, list) or not self.bases:
            raise TaskError('接口列表为空或格式错误')
        self.bases = [https_url(str(base).strip()).rstrip('/') for base in self.bases]
        if any(urllib.parse.urlsplit(base).query for base in self.bases):
            raise TaskError('接口基址不得携带查询参数')
        self.opener = urllib.request.build_opener(NoRedirect())
        try:
            self.margin = int(config.get('refreshMarginH', 72)) * 3600
            if self.margin < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise TaskError('refreshMarginH 必须为非负整数') from None

    def request(self, url, method='GET', body=None, headers=None):
        if self.dry:
            raise TaskError('预演模式禁止网络请求')
        https_url(url)
        hdr = {'Accept': 'application/json', 'User-Agent': 'Qoder/claim'}
        hdr.update(headers or {})
        data = None
        if body is not None:
            hdr['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        try:
            req = urllib.request.Request(url, data=data, headers=hdr, method=method)
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(1048577)
                status = response.status
            if len(raw) > 1048576:
                return status, None
            return status, json.loads(raw)
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (ValueError, OSError, urllib.error.URLError):
            return 0, None

    def api(self, account, path, method='GET', body=None, authorized=True):
        device = self.config.get('device', {})
        if not isinstance(device, dict):
            raise TaskError('设备配置必须为对象')
        device = dict(device, **account['device'])
        headers = {}
        for field, header, env, default in DEVICE_KEYS:
            value = str(account['device'].get(field) or os.getenv(env, '').strip() or device.get(field) or default)
            if value:
                if any(c in value for c in '\r\n'):
                    raise TaskError('设备请求头包含非法换行')
                headers[header] = value
                if field in ('machineToken', 'machineCode', 'machineId', 'machineHostname'):
                    SECRETS.add(value)
        if authorized:
            headers['Authorization'] = 'Bearer ' + account['accessToken']
        last = (0, None)
        for base in list(self.bases):
            last = self.request(base + path, method, body, headers)
            if last[0] not in (0, 404):
                self.bases.remove(base)
                self.bases.insert(0, base)
                return last
            log(f'⚠️ 当前端点请求未完成，HTTP {last[0]}，继续尝试配置的后备端点')
        return last


def business_ok(data):
    return (isinstance(data, dict) and data.get('success') is not False
            and ('code' not in data or data['code'] in (0, 200, '0', '200')))


def save_cache(account):
    filename = os.getenv('QODER_CACHE_FILE', '').strip()
    if not filename:
        log('令牌已刷新，仅本次运行使用；可配置 QODER_CACHE_FILE 安全保存轮换令牌')
        return
    # Entire live run holds an advisory lock for this cache, including read/refresh/write.
    cache = read_json(filename, {})
    if not isinstance(cache, dict):
        raise TaskError('令牌缓存格式错误')
    cache[account['cacheKey']] = {k: account[k] for k in ('accessToken', 'refreshToken', 'expiresAt')}
    temp = None
    try:
        fd, temp = tempfile.mkstemp(prefix='.qoder-', dir=Path(filename).resolve().parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(cache, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, filename)
    except OSError:
        raise TaskError('令牌已轮换但安全缓存保存失败，请更新凭据') from None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def ensure_token(service, account, force=False):
    token = account['accessToken']
    expiry = account['expiresAt'] or jwt_exp(token)
    if token and not force and (not expiry or expiry - time.time() > service.margin):
        return
    refresh = account['refreshToken']
    if refresh:
        status, data = service.api(account, PATH_REFRESH, 'POST', {'refresh_token': refresh}, False)
        if status == 200 and business_ok(data):
            new = data.get('token') or data.get('accessToken') or data.get('access_token') or data.get('device_token')
            rotated = data.get('refreshToken') or data.get('refresh_token') or refresh
            if isinstance(new, str) and new and not any(c.isspace() for c in new) and isinstance(rotated, str) and not any(c.isspace() for c in rotated):
                account.update(accessToken=new, refreshToken=rotated,
                               expiresAt=coerce_exp(data.get('expires_at') or data.get('expiresAt')) or jwt_exp(new))
                SECRETS.update((new, rotated))
                save_cache(account)
                log('✅ 令牌刷新成功，已取得有效格式的访问令牌')
                return
    if token and not force and (not expiry or expiry > time.time()):
        log('⚠️ 刷新不可用，继续使用尚未过期的访问令牌')
        return
    raise TaskError('认证失败，请更新本人授权的访问令牌及刷新令牌')


def identity(data, index):
    for obj in (data, data.get('user'), data.get('account')):
        if isinstance(obj, dict):
            for key in ('nickname', 'username', 'displayName', 'uid', 'userId'):
                if isinstance(obj.get(key), (str, int)) and str(obj[key]):
                    value = str(obj[key])
                    if key not in ('uid', 'userId') and re.fullmatch(r'\+?\d[\d -]{9,}\d', value):
                        return f'账号{index}（身份含手机号，已隐藏）'
                    return safe(value)
    return f'账号{index}'


def stage(number, name, action):
    start = time.monotonic()
    log(f'{number}. {name} 开始')
    try:
        result = action()
    except Exception:
        log(f'{number}. {name} 失败，耗时 {time.monotonic() - start:.2f} 秒')
        raise
    log(f'{number}. {name} 完成，耗时 {time.monotonic() - start:.2f} 秒')
    return result


def run_account(service, account):
    index = account['index']
    if account.get('error'):
        raise TaskError(account['error'])
    if service.dry:
        def validate_device():
            device = service.config.get('device', {})
            if not isinstance(device, dict):
                raise TaskError('设备配置必须为对象')
            for field, header, env, default in DEVICE_KEYS:
                value = str(account['device'].get(field) or os.getenv(env, '').strip() or device.get(field) or default)
                if any(c in value for c in '\r\n'):
                    raise TaskError('设备请求头包含非法换行')
        stage(1, '凭据与设备配置检查', validate_device)
        times, wait = empty_retry_plan()
        stage(2, '活动查询预演', lambda: log(f'空活动最多查询 {times} 次，间隔 {wait} 秒；预演跳过请求与等待'))
        stage(3, '幂等奖励领取预演', lambda: None)
        return {'name': f'账号{index}', 'uid': '-', 'phase': 'dry-run', 'msg': 'DRY_RUN_OK，未请求接口或写入文件',
                'credits': 0, 'tasks': {'success': 0, 'already': 0, 'skipped': 3, 'failed': 0}}
    account['_tasks'] = {'success': 0, 'already': 0, 'skipped': 0, 'failed': 0}
    stage(1, '检查或刷新令牌', lambda: ensure_token(service, account))
    account['_tasks']['success'] = 1
    def campaigns():
        times, wait = empty_retry_plan()
        for attempt in range(1, times + 1):
            log(f'2.{attempt} 活动查询开始，最多 {times} 次')
            status, data = service.api(account, PATH_CAMPAIGNS)
            if status == 401:
                log('⚠️ 活动查询认证失效，强制刷新后重试一次')
                ensure_token(service, account, True)
                status, data = service.api(account, PATH_CAMPAIGNS)
            if status != 200 or not business_ok(data) or not isinstance(data.get('campaigns'), list):
                raise TaskError(f'活动查询失败或响应契约不匹配，HTTP {status}')
            benefits = [c for c in data['campaigns']
                        if isinstance(c, dict) and c.get('actionType') == 'CLAIM_BENEFIT']
            log(f'✅ 活动查询通过，奖励活动 {len(benefits)} 个')
            if benefits or attempt == times:
                return data
            log(f'⏳ 活动未下发，等待 {wait} 秒后重查')
            if wait:
                time.sleep(wait)
    data = stage(2, '查询活动', campaigns)
    account['_tasks']['success'] = 2
    name = identity(data, index)
    log(f'官方账号 {name}')
    benefits = [c for c in data['campaigns'] if isinstance(c, dict) and c.get('actionType') == 'CLAIM_BENEFIT']
    available = [c for c in benefits if c.get('claimStatus') == 'CLAIMABLE']
    result = {'name': name, 'uid': '-', 'phase': 'pending', 'msg': '活动未开放或未下发，本轮查询结束，等待下轮，尚未验证领取成功',
              'credits': 0, 'tasks': {'success': 2, 'already': 0, 'skipped': 0, 'failed': 0}}
    if available:
        failed = 0
        for number, campaign in enumerate(available, 3):
            def claim():
                cid = campaign.get('campaignId')
                if not isinstance(cid, (str, int)) or not str(cid):
                    raise TaskError('可领取活动缺少标识')
                path = PATH_CLAIM.format(cid=urllib.parse.quote(str(cid), safe=''))
                status, body = service.api(account, path, 'POST', {})
                if status != 200 or not business_ok(body):
                    raise TaskError(f'领取失败，HTTP {status}')
                detail = body.get('data', body)
                if not isinstance(detail, dict) or detail.get('status') != 'CLAIMED':
                    raise TaskError('领取响应未确认 CLAIMED')
                benefit = detail.get('benefit') or campaign.get('benefit') or {}
                try:
                    amount = float(benefit.get('amount', 0))
                    return amount if math.isfinite(amount) else 0
                except (ValueError, TypeError, AttributeError):
                    return 0
            try:
                result['credits'] += stage(number, '领取活动奖励', claim)
                result['tasks']['success'] += 1
                log('✅ 服务端已确认 CLAIMED')
            except TaskError as exc:
                failed += 1
                result['tasks']['failed'] += 1
                log(str(exc))
        result['phase'] = 'error' if failed else 'claimed'
        result['msg'] = f'{failed}/{len(available)} 个活动领取失败' if failed else f"签到成功 +{result['credits']:g} Credits"
    else:
        now = time.time()
        completed = [c for c in benefits if c.get('claimStatus') == 'CLAIMED'
                     and coerce_exp(c.get('startAt')) <= now < coerce_exp(c.get('endAt'))]
        if completed:
            result.update(phase='already', msg='今日已领取，服务端确认 CLAIMED')
            result['tasks']['already'] = 1
        else:
            result['tasks']['skipped'] = 1
        log('3. 奖励领取阶段 ' + result['msg'] + '，耗时 0.00 秒')
    return result


def notification(service, body):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in ('0', 'false', 'no', 'off'):
        return '已关闭'
    if switch not in ('auto', '1', 'true', 'yes', 'on'):
        return '开关无效，已跳过'
    selectors = os.getenv('QINGLONG_NOTIFY_SCRIPTS')
    if switch == 'auto' and selectors is not None:
        names = (CATALOG, 'scripts/qoder_checkin.py', 'qoder_checkin.py', 'candidate.py', Path(__file__).name)
        patterns = re.split(r'[,;\s]+', selectors.strip())
        if not any(fnmatch.fnmatchcase(name, pattern) for name in names for pattern in patterns if pattern):
            return '未入选'
    if service.dry:
        log('通知预演 ' + body)
        return '预演完成'
    # Run notification helpers in a child so their output and failures cannot leak credentials
    # or change the task exit status. Business requests never depend on these helpers.
    paths = []
    directory = os.getenv('QINGLONG_NOTIFY_DIR', '').strip()
    if directory:
        paths.append(Path(directory))
    paths.extend((HERE, Path('/ql/data/scripts'), Path('/ql/scripts')))
    commands = []
    try:
        spec = importlib.util.find_spec('notify')
        if spec and spec.origin:
            commands.append([sys.executable, '-c', 'import json,sys,notify; notify.send(*json.load(sys.stdin))'])
    except (ImportError, ValueError):
        pass
    for folder in paths:
        if (folder / 'notify.py').is_file():
            commands.append([sys.executable, '-c',
                             'import importlib.util,json,sys; s=importlib.util.spec_from_file_location("ql_notify",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.send(*json.load(sys.stdin))', str(folder / 'notify.py')])
        if (folder / 'sendNotify.js').is_file():
            commands.append(['node', '-e',
                             'const fs=require("fs");const [title,body]=JSON.parse(fs.readFileSync(0,"utf8"));Promise.resolve(require(process.argv[1]).sendNotify(title,body)).catch(()=>process.exit(1));', str(folder / 'sendNotify.js')])
    delivered = False
    for command in commands:
        try:
            proc = subprocess.run(command, input=json.dumps([TITLE, body]), text=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if proc.returncode == 0:
                delivered = True
                break
        except (OSError, subprocess.TimeoutExpired):
            continue
    # Preserve explicitly configured upstream channels, with the same global switch.
    conf = service.config.get('notify', {})
    if not isinstance(conf, dict):
        conf = {}
    legacy = [('QYWX_TOKEN', 'qywxToken'), ('PLUSPLUS_TOKEN', 'plusplusToken'), ('QODER_WEBHOOK', 'webhook')]
    for env, key in legacy:
        value = str(os.getenv(env, '') or conf.get(key) or '').strip()
        if not value:
            continue
        SECRETS.add(value)
        if key == 'qywxToken':
            url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=' + urllib.parse.quote(value.split('key=')[-1], safe='')
            payload = {'msgtype': 'text', 'text': {'content': TITLE + '\n' + body}}
        elif key == 'plusplusToken':
            url, payload = 'https://www.pushplus.plus/send', {'token': value, 'title': TITLE, 'content': body, 'template': 'txt'}
        else:
            url, payload = value, {'title': TITLE, 'content': body}
        try:
            status, response = service.request(url, 'POST', payload)
            ok = status == 200 and isinstance(response, dict)
            if key == 'qywxToken':
                ok = ok and response.get('errcode') == 0
            elif key == 'plusplusToken':
                ok = ok and response.get('code') == 200
            else:
                ok = ok and business_ok(response)
            delivered = delivered or ok
            log('兼容通知渠道 ' + ('投递成功' if ok else '未确认投递'))
        except Exception:
            log('兼容通知渠道不可用')
    return '已发送' if delivered else '通知不可用或失败，保留业务退出码'


def main():
    if any(arg in ('-h', '--help') for arg in sys.argv[1:]):
        print(__doc__)
        return 0
    started = time.monotonic()
    dry = flag('QODER_DRY_RUN')
    trigger = 'poll' if any(arg in ('poll', 'silent-poll') for arg in sys.argv[1:]) else 'checkin'
    log('=' * 56)
    log(TITLE + ' 开始时间 ' + stamp())
    log('运行模式 ' + ('断网预演' if dry else trigger))
    results, accounts = [], []
    configuration_error = False
    lock = None
    service = Service({}, dry, use_env=False)
    try:
        config = read_json(os.getenv('QODER_CONFIG_FILE') or HERE / 'qoder_config.json', {})
        if not isinstance(config, dict):
            raise TaskError('配置必须为 JSON 对象')
        service = Service(config, dry)
        accounts = load_accounts()
        log(f'账号数量 {len(accounts)}')
        if not accounts:
            raise TaskError('没有可用账号，请配置 QODER_ACCOUNTS')
        cache_path = os.getenv('QODER_CACHE_FILE', '').strip()
        if cache_path and not dry:
            import fcntl
            lock_fd = os.open(cache_path + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
            lock = os.fdopen(lock_fd, 'w')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise TaskError('令牌缓存正在使用，请等待下一轮') from None
            cache = read_json(cache_path, {})
            if not isinstance(cache, dict):
                raise TaskError('令牌缓存格式错误')
            for account in accounts:
                stored = cache.get(account.get('cacheKey'))
                if isinstance(stored, dict):
                    checked = normalize(stored, account['index'])
                    if checked.get('error'):
                        raise TaskError('缓存账号格式错误')
                    account.update({key: checked[key] for key in ('accessToken', 'refreshToken', 'expiresAt')})
        for account in accounts:
            begin = time.monotonic()
            log(f"账号 {account['index']} 开始")
            try:
                result = run_account(service, account)
            except TaskError as exc:
                result = {'name': f"账号{account['index']}", 'uid': '-', 'phase': 'error', 'msg': str(exc), 'credits': 0,
                          'tasks': {'success': 0, 'already': 0, 'skipped': 0, 'failed': 1}}
            except Exception:
                result = {'name': f"账号{account['index']}", 'uid': '-', 'phase': 'error', 'msg': '运行失败，已隐藏异常细节', 'credits': 0,
                          'tasks': {'success': 0, 'already': 0, 'skipped': 0, 'failed': 1}}
            if result['phase'] == 'error' and account.get('_tasks') and result['tasks']['success'] == 0:
                result['tasks']['success'] = account['_tasks']['success']
            result['elapsed'] = round(time.monotonic() - begin, 2)
            results.append(result)
            counts = result['tasks']
            log(f"{result['name']} {result['msg']}")
            log(f"账号统计 总任务 {sum(counts.values())} 成功 {counts['success']} 已完成 {counts['already']} 跳过 {counts['skipped']} 失败 {counts['failed']} 耗时 {result['elapsed']:.2f} 秒")
    except Exception as exc:
        configuration_error = True
        log('配置错误 ' + (str(exc) if isinstance(exc, TaskError) else '配置或缓存初始化失败，已隐藏细节'))
        log(f'账号数量 {len(accounts)}')
    finally:
        if lock is not None:
            lock.close()
    bad = sum(r['phase'] not in ('claimed', 'already', 'dry-run') for r in results)
    good = len(results) - bad
    exit_code = 1 if configuration_error else (2 if bad else 0)
    status = 'configuration-error' if configuration_error else ('partial-failure' if bad and good else 'failure' if bad else 'dry-run' if dry else 'success')
    counts = {k: sum(r['tasks'][k] for r in results) for k in ('success', 'already', 'skipped', 'failed')}
    body = f'账号总数 {len(accounts)}，成功 {good}，失败 {bad}，状态 {status}'
    if configuration_error:
        body += '，配置错误 1'
    notify_state = '通知不可用，保留业务退出码'
    try:
        notify_state = notification(service, safe(body))
    except Exception:
        pass
    log('-' * 56)
    log(body)
    log(f"子任务 总数 {sum(counts.values())} 成功 {counts['success']} 已完成 {counts['already']} 跳过 {counts['skipped']} 失败 {counts['failed']}")
    log(f'总耗时 {time.monotonic() - started:.2f} 秒 完成时间 {stamp()} 通知状态 {notify_state}')
    log('最终状态 ' + status)
    record = {'time': stamp(), 'script': 'qoder_checkin', 'trigger': trigger,
              'result': 'ERROR' if exit_code else 'DRY_RUN' if dry else 'CLAIMED' if any(r['phase'] == 'claimed' for r in results) else 'ALREADY',
              'summary': {'claimed': sum(r['phase'] == 'claimed' for r in results), 'already': sum(r['phase'] == 'already' for r in results),
                          'pending': sum(r['phase'] == 'pending' for r in results), 'failed': bad + int(configuration_error)}, 'results': results}
    encoded = json.dumps(record, ensure_ascii=False)
    print(encoded)
    if not dry:
        try:
            with open(os.getenv('QODER_LOG_FILE') or HERE / 'qoder_checkin.log', 'a', encoding='utf-8') as stream:
                stream.write(encoded + '\n')
        except OSError:
            log('⚠️ JSON 行日志写入失败，标准输出已保留记录')
    summary = {'status': status, 'accounts': len(accounts), 'success': good, 'failed': bad,
               'configurationErrors': int(configuration_error), 'tasks': counts, 'notification': notify_state, 'exitCode': exit_code}
    print('TASK_SUMMARY=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
