#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: AtomCode 免费套餐领取
# cron: 3 11 * * *
# 上游：L0NE-6/AtomCode-Daily，MIT License。
# MIT License — L0NE-6/AtomCode-Daily
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
# 来源：atomcode_daily.py / atomcode_auth.py；保留原作者归属。
# 上游输入未附额外版权声明。维护版本继续采用 MIT License。
"""
AtomCode 免费 CodingPlan 自动领取（Python 3.9+，无第三方依赖）。
定时建议每天 09:00（上游未声明 cron）；--query 仅查询套餐和额度。
ATOMCODE_TOKENS 每个非空行一个账号，推荐：备注|JSON对象
JSON 使用 access_token、refresh_token、expires_at 等字段。
兼容：备注|access_token[|refresh_token[|expires_at[|created_at|expires_in]]]
字段分隔符不得出现在旧格式字段内；JSON 形式可保存任意后续凭据文本。
在本人已登录的官方 AtomCode/AtomGit 客户端本地 auth.json/auth.toml 中
读取 tokens.access_token / refresh_token 与到期字段，在青龙环境变量中填写；
不要发送凭据给他人或粘贴到日志。TOML 读取需 Python 3.11+。
ATOMCODE_AUTH_FILE 可显式读取本人导出的 JSON/TOML 文件，不扫描私人目录。
兼容 ATOMCODE_TOKEN、ATOMCODE_REFRESH_TOKEN、ATOMCODE_EXPIRES_AT。
ATOMCODE_STATE_FILE 显式设置后才以 0600 权限保存续期令牌；未设置不落盘。
--only N 仅处理第 N 个账号，--no-notify / ATOMCODE_NO_NOTIFY=1 关闭通知。
ATOMCODE_DRY_RUN=1 完全断网，不读取本地凭据/状态、不落盘、不发送通知。
QINGLONG_NOTIFY=1 启用青龙通知；auto 仅匹配 QINGLONG_NOTIFY_SCRIPTS 列表。
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
        _ql_notify_identities = ('e10a36a978f215b9', 'scripts/atomcode_daily.py', 'atomcode_daily.py', 'atomcode_daily')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
import argparse
import contextlib
import fnmatch
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BROKER_BASE = os.getenv('ATOMCODE_BROKER_BASE', '').strip().rstrip('/') or 'https://acs.atomgit.com'
API_BASE = os.getenv('ATOMCODE_CODINGPLAN_API_BASE', '').strip().rstrip('/') or 'https://api.gitcode.com/api/v5'
REFRESH_PATH = '/oauth/refresh'
STATUS_PATH = '/coding-plan/status-v2'
CLAIM_PATH = '/coding-plan/claim-v2'
USER_AGENT = 'checkin-daily/1.0'
TIERS = ('Max', 'Pro', 'Lite')
REFRESH_WINDOW_SEC = 3600
STATE_FILE = os.getenv('ATOMCODE_STATE_FILE', '').strip()
DRY_RUN = os.getenv('ATOMCODE_DRY_RUN', '').lower() in ('1', 'true', 'yes', 'on')
TITLE = 'AtomCode 免费套餐领取'

class AtomCodeError(Exception):
    pass

def log(message):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), message), flush=True)

def strip_bearer(token):
    text = str(token or "").strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text


def parse_timestamp(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            return 0
        return int(number * 1000) if number < 100000000000 else int(number)
    text = str(value).strip()
    if not text:
        return 0
    try:
        number = float(text)
        return int(number * 1000) if number < 100000000000 else int(number)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(text[:19], fmt).timestamp() * 1000)
        except Exception:
            continue
    return 0


def first_text(record, keys):
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_account(record, index):
    if not isinstance(record, dict):
        return None
    tokens = record.get("tokens") if isinstance(record.get("tokens"), dict) else {}
    user = record.get("user") if isinstance(record.get("user"), dict) else {}

    def pick(keys):
        value = first_text(record, keys)
        return value or first_text(tokens, keys)

    access = strip_bearer(
        pick(("accessToken", "access_token", "token"))
    )
    refresh = strip_bearer(
        pick(("refreshToken", "refresh_token"))
    )
    if not access and not refresh:
        return None
    user_id = pick(("userId", "user_id", "uid")) or first_text(user, ("id", "userId"))
    username = pick(("username", "userName")) or first_text(user, ("username", "name"))
    name = first_text(record, ("name", "nickname")) or username or user_id or (
        "账号%d" % index
    )
    expires_at = parse_timestamp(
        pick(("expiresAt", "expires_at"))
    )
    created_at = parse_timestamp(
        pick(("createdAt", "created_at"))
    )
    added_at = parse_timestamp(
        pick(("addedAt", "added_at"))
    )
    try:
        expires_in = int(float(pick(("expiresIn", "expires_in")) or 0))
    except Exception:
        expires_in = 0
    if not expires_at and expires_in > 0:
        basis = created_at or added_at
        if basis:
            expires_at = basis + expires_in * 1000
    key = user_id or username or name
    return {
        "name": name,
        "key": key,
        "user_id": user_id,
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires_at,
    }


def active_plan(status):
    plan = status.get("codingplan_free") if isinstance(status, dict) else None
    if not isinstance(plan, dict):
        return None
    name = str(plan.get("plan_name") or "").strip()
    expires_at = str(plan.get("expires_at") or "").strip()
    try:
        remaining = int(plan.get("remaining_days") or 0)
    except Exception:
        remaining = 0
    expiry_ts = None
    if expires_at:
        try:
            text = expires_at[:-1] + "+00:00" if expires_at.endswith("Z") else expires_at
            expiry = datetime.fromisoformat(text)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone(timedelta(hours=8)))
            expiry_ts = expiry.timestamp()
        except Exception:
            expiry_ts = None
    # 有可解析的到期时间时以它为准；缺失/不可解析时才用 remaining_days。
    # 旧实现只看 expires_at 非空，过期套餐也会被当成有效，永远不会续领。
    active = expiry_ts > time.time() if expiry_ts is not None else remaining > 0
    if not active:
        return None
    return name, expires_at, remaining


def quota_summary(status):
    windows = status.get("rate_limit_windows") if isinstance(status, dict) else None
    if not isinstance(windows, list):
        return ""
    for item in windows:
        if not isinstance(item, dict):
            continue
        try:
            show = int(item.get("show_enable") or 0)
            limit = int(item.get("call_limit") or 0)
            used = int(item.get("calls_used") or 0)
            hours = int(item.get("window_hours") or 0)
        except Exception:
            continue
        if show != 1 or limit <= 0:
            continue
        text = "已用 %s/%s 次" % (used, limit)
        if hours > 0:
            text += "（每 %s 小时滚动）" % hours
        reset = str(item.get("reset_at_display") or "").strip()
        if reset:
            text += "，%s 重置" % reset
        return text
    return ""


def classify_claim(payload):
    message = str(payload.get("message") or payload.get("msg") or "").strip()
    plan_name = str(payload.get("plan_name") or payload.get("planName") or "").strip()
    if payload.get("duplicate") is True:
        return "held", message, plan_name
    if payload.get("success") is True:
        return "granted", message, plan_name
    return "refused", message, plan_name



def load_accounts():
    accounts = []
    auth = os.getenv('ATOMCODE_AUTH_FILE', '').strip()
    if auth and not DRY_RUN:
        try:
            raw = Path(auth).read_text(encoding='utf-8-sig')
            if auth.lower().endswith('.toml'):
                import tomllib
                value = tomllib.loads(raw)
            else:
                value = json.loads(raw)
            if isinstance(value, dict):
                value = value.get('accounts', [value])
            if not isinstance(value, list) or not value:
                raise ValueError()
            for record in value:
                account = normalize_account(record, len(accounts) + 1)
                accounts.append(account or {'invalid': True})
        except Exception:
            accounts.append({'invalid': True})
    for line in os.getenv('ATOMCODE_TOKENS', '').splitlines():
        if not line.strip():
            continue
        try:
            name, credentials = line.strip().split('|', 1)
            if credentials.lstrip().startswith('{'):
                record = json.loads(credentials)
                if not isinstance(record, dict):
                    raise ValueError()
                record['name'] = name
            else:
                parts = credentials.split('|')
                if len(parts) > 5:
                    raise ValueError()
                record = dict(zip(('access_token', 'refresh_token', 'expires_at',
                                   'created_at', 'expires_in'), parts))
                record['name'] = name
            account = normalize_account(record, len(accounts) + 1)
            accounts.append(account or {'invalid': True})
        except Exception:
            accounts.append({'invalid': True})
    if not accounts:
        account = normalize_account({
            'access_token': os.getenv('ATOMCODE_TOKEN', ''),
            'refresh_token': os.getenv('ATOMCODE_REFRESH_TOKEN', ''),
            'expires_at': os.getenv('ATOMCODE_EXPIRES_AT', '')}, 1)
        if account:
            accounts.append(account)
    return accounts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(method, url, body=None, token=''):
    if DRY_RUN:
        raise AtomCodeError('预演禁止网络请求')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise AtomCodeError('接口必须为不含凭据的 HTTPS 地址')
    headers = {'Accept': 'application/json', 'User-Agent': USER_AGENT}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    proxy = os.getenv('ATOMCODE_PROXY', '').strip()
    handlers = [NoRedirect()]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    try:
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.build_opener(*handlers).open(request, timeout=30) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise AtomCodeError('响应超过大小限制')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise AtomCodeError('响应结构不符合契约')
        return value
    except urllib.error.HTTPError as exc:
        # 只保留数字状态码，绝不回显响应正文或请求地址。
        error = AtomCodeError('接口 HTTP %d' % exc.code)
        error.http_status = exc.code
        raise error from None
    except AtomCodeError:
        raise
    except Exception:
        raise AtomCodeError('网络、超时或 JSON 解析失败') from None


def check_business(payload):
    if payload.get('success') is False or payload.get('error'):
        raise AtomCodeError('接口明确返回业务失败')
    if 'code' in payload and payload['code'] not in (0, 200, '0', '200'):
        raise AtomCodeError('接口返回非成功业务码')


def show_identity(payload):
    user = payload.get('user')
    records = [user, payload] if isinstance(user, dict) else [payload]
    for record in records:
        for key in ('nickname', 'username', 'display_name', 'displayName', 'user_id', 'uid') + (('id', 'name') if record is user else ()):
            value = record.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                text = str(value)
                # 只展示官方公开身份；手机号和凭据不属于身份展示范围。
                if re.search(r'\b1[3-9]\d{9}\b', text):
                    continue
                secrets = [a.get(k, '') for a in ACTIVE_ACCOUNTS
                           for k in ('access_token', 'refresh_token')]
                if any(secret and secret in text for secret in secrets):
                    continue
                log('官方账号身份：' + re.sub(r'[\r\n\x00-\x1f\x7f]', ' ', text))
                return


class AtomCodeClient:
    def __init__(self, account, state):
        self.account = account
        self.state = state
        # 不以用户备注作状态键，避免重名串号和记录明文身份。
        self.key = hashlib.sha256((account.get('refresh_token') or account.get('access_token', '')).encode()).hexdigest()
        saved = state.get('accounts', {}).get(self.key, {})
        self.access_token = saved.get('access_token') or account.get('access_token', '')
        self.refresh_token = saved.get('refresh_token') or account.get('refresh_token', '')
        self.expires_at = saved.get('expires_at') or account.get('expires_at', 0)

    def save_tokens(self):
        if not STATE_FILE:
            log('续期令牌仅保留在本次进程内；未配置状态文件')
            return
        self.state.setdefault('accounts', {})[self.key] = {
            'access_token': self.access_token, 'refresh_token': self.refresh_token,
            'expires_at': self.expires_at}
        path = Path(STATE_FILE)
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(prefix='.atomcode-', dir=str(path.parent))
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                os.fchmod(handle.fileno(), 0o600)
                json.dump(self.state, handle, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            raise AtomCodeError('令牌续期成功但安全保存失败，请检查状态文件配置') from None
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    def refresh(self):
        if not self.refresh_token:
            raise AtomCodeError('缺少续期令牌，请重新登录获取凭据')
        payload = http_json('POST', BROKER_BASE + REFRESH_PATH,
                            {'refresh_token': self.refresh_token})
        check_business(payload)
        access = strip_bearer(payload.get('access_token'))
        if not access:
            raise AtomCodeError('续期未返回有效访问令牌')
        show_identity(payload)
        self.access_token = access
        self.refresh_token = strip_bearer(payload.get('refresh_token')) or self.refresh_token
        try:
            expiry = int(payload.get('expires_in') or 0)
        except (TypeError, ValueError):
            raise AtomCodeError('续期有效期字段无效') from None
        self.expires_at = int(time.time() * 1000) + expiry * 1000 if expiry > 0 else 0
        self.save_tokens()
        log('令牌续期成功')

    def request(self, method, path, body=None):
        if self.refresh_token and (not self.access_token or
                (self.expires_at and int(self.expires_at) <= (time.time() + REFRESH_WINDOW_SEC) * 1000)):
            self.refresh()
        if not self.access_token:
            raise AtomCodeError('缺少访问令牌')
        try:
            payload = http_json(method, API_BASE + path, body, self.access_token)
        except AtomCodeError as exc:
            if getattr(exc, 'http_status', None) not in (401, 403) or not self.refresh_token:
                raise
            self.refresh()
            payload = http_json(method, API_BASE + path, body, self.access_token)
        show_identity(payload)
        return payload

    def status(self):
        value = self.request('GET', STATUS_PATH)
        check_business(value)
        if 'codingplan_free' not in value or (value['codingplan_free'] is not None
                and not isinstance(value['codingplan_free'], dict)):
            raise AtomCodeError('套餐状态结构发生变化，无法核验业务成功')
        return value

    def claim(self, tier):
        return self.request('POST', CLAIM_PATH, {'plan_type': tier})


ACTIVE_ACCOUNTS = []


def stage(stats, number, title, action):
    started = time.monotonic()
    log('阶段 %d：%s' % (number, title))
    stats['total'] += 1
    try:
        value, outcome, message = action()
        stats[outcome] += 1
        log('%s %s（耗时 %.2f 秒）' % (
            {'success': '✅', 'already_complete': '☑️', 'skipped': '⏭️'}[outcome],
            message, time.monotonic() - started))
        return value
    except Exception:
        stats['failed'] += 1
        log('❌ 阶段失败（耗时 %.2f 秒）' % (time.monotonic() - started))
        raise


def run_account(client, stats, query_only):
    status = stage(stats, 1, '查询套餐和额度',
                   lambda: (client.status(), 'success', '状态结构核验通过'))
    quota = quota_summary(status)
    if quota:
        # 只显示解析后的数字，不回显未知服务端文本。
        for window in status.get('rate_limit_windows', []):
            if isinstance(window, dict) and str(window.get('show_enable')) == '1':
                try:
                    log('额度已用 %d/%d 次，滚动窗口 %d 小时' % (
                        int(window.get('calls_used', 0)), int(window.get('call_limit', 0)),
                        int(window.get('window_hours', 0))))
                except (TypeError, ValueError):
                    pass
    plan = active_plan(status)
    if plan:
        stage(stats, 2, '核验有效套餐', lambda: (None, 'already_complete',
              '已有有效套餐，剩余 %d 天，无需领取' % plan[2]))
        return
    if query_only:
        stage(stats, 2, '只查询模式', lambda: (None, 'skipped', '当前没有有效套餐'))
        return
    for number, tier in enumerate(TIERS, 2):
        def claim():
            payload = client.claim(tier)
            verdict, _, _ = classify_claim(payload)
            if payload.get('success') is False and verdict == 'granted':
                raise AtomCodeError('领取结果冲突')
            if verdict in ('granted', 'held'):
                # 业务标志之外再读取状态，避免无套餐却报告成功。
                check_business(payload)
                if not active_plan(client.status()):
                    raise AtomCodeError('领取响应后未核验到有效套餐')
                return True, ('success' if verdict == 'granted' else 'already_complete'), tier + ' 档套餐已核验'
            return False, 'skipped', tier + ' 档未获批准，尝试下一档'
        if stage(stats, number, tier + ' 档免费套餐领取', claim):
            return
    stats['total'] += 1
    stats['failed'] += 1
    raise AtomCodeError('三档免费套餐均未领取')


def notify_summary(body, disabled):
    switch = os.getenv('QINGLONG_NOTIFY', 'auto').strip().lower()
    if disabled or switch in ('0', 'false', 'no', 'off'):
        return '已关闭'
    if switch not in ('1', 'true', 'yes', 'on'):
        selectors = re.split(r'[,;\s]+', os.getenv('QINGLONG_NOTIFY_SCRIPTS', '').strip())
        names = ('e10a36a978f215b9', 'atomcode_daily.py', Path(__file__).name,
                 'scripts/atomcode_daily.py', 'scripts/' + Path(__file__).name)
        names = list(names)
        for root in ('/ql/data/scripts', '/ql/scripts'):
            try:
                names.append(str(Path(__file__).resolve().relative_to(root)))
            except ValueError:
                pass
        if not any(fnmatch.fnmatch(name, pattern) for name in names for pattern in selectors if pattern):
            return '未选中'
    if DRY_RUN:
        return '预演禁止外发，已生成脱敏通知摘要'
    # 在受限时子进程中运行通知，屏蔽模块输出，避免退出或阻塞破坏业务结果。
    folders = [os.getenv('QINGLONG_NOTIFY_DIR', ''), '/ql/data/scripts', '/ql/scripts']
    bridge = """
import importlib, importlib.util, json, pathlib, sys
folders = json.loads(sys.argv[3])
try:
    import notify
    notify.send(sys.argv[1], sys.argv[2])
    sys.exit(0)
except Exception:
    pass
for folder in folders:
    if not folder:
        continue
    path = pathlib.Path(folder) / 'notify.py'
    if path.is_file():
        try:
            sys.path.insert(0, str(path.parent))
            spec = importlib.util.spec_from_file_location('atomcode_ql_notify', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(sys.argv[1], sys.argv[2])
            sys.exit(0)
        except Exception:
            pass
sys.exit(1)
"""
    try:
        result = subprocess.run([sys.executable, '-c', bridge, TITLE, body, json.dumps(folders)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode == 0:
            return '已发送'
    except Exception:
        pass
    for folder in folders:
        if folder and (Path(folder) / 'sendNotify.js').is_file():
            try:
                js = "Promise.resolve(require(process.argv[1]).sendNotify(process.argv[2],process.argv[3])).catch(()=>process.exit(1))"
                result = subprocess.run(['node', '-e', js, str(Path(folder) / 'sendNotify.js'), TITLE, body],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                if result.returncode == 0:
                    return '已发送'
            except Exception:
                pass
    return '不可用或发送失败（保留业务退出码）'


def main():
    global ACTIVE_ACCOUNTS
    started = time.monotonic()
    log('========== %s ==========' % TITLE)
    log('开始时间：' + datetime.now().isoformat(timespec='seconds'))
    log('运行模式：' + ('断网预演' if DRY_RUN else '正式运行'))
    results = []
    config_error = False
    no_notify = os.getenv('ATOMCODE_NO_NOTIFY', '').strip() == '1' or '--no-notify' in sys.argv
    try:
        # 不使用 argparse 默认错误退出，配置错误也进入统一汇总和通知。
        class Parser(argparse.ArgumentParser):
            def error(self, message):
                raise AtomCodeError('命令参数无效；支持 --query、--only 正整数、--no-notify')
        parser = Parser(add_help=False)
        parser.add_argument('--query', action='store_true')
        parser.add_argument('--only', type=int)
        parser.add_argument('--no-notify', action='store_true')
        args = parser.parse_args()
        accounts = load_accounts()
        ACTIVE_ACCOUNTS = accounts
        if not accounts:
            raise AtomCodeError('未配置 ATOMCODE_TOKENS 或兼容凭据输入')
        if args.only is not None and not 1 <= args.only <= len(accounts):
            raise AtomCodeError('--only 未匹配有效账号序号')
        selected = [(i, a) for i, a in enumerate(accounts, 1) if args.only is None or i == args.only]
        log('账号数量：%d' % len(selected))
        state = {'accounts': {}}
        if STATE_FILE and not DRY_RUN and Path(STATE_FILE).exists():
            try:
                state = json.loads(Path(STATE_FILE).read_text(encoding='utf-8'))
                if not isinstance(state, dict) or not isinstance(state.get('accounts'), dict):
                    raise ValueError()
            except Exception:
                raise AtomCodeError('状态文件无效，停止运行以免覆盖凭据') from None
        for i, account in selected:
            account_start = time.monotonic()
            stats = dict.fromkeys(('total', 'success', 'already_complete', 'skipped', 'failed'), 0)
            log('----- 账号 %d -----' % i)
            ok = False
            try:
                if account.get('invalid'):
                    stats.update(total=1, failed=1)
                    raise AtomCodeError('账号格式错误或凭据文件无法解析')
                if DRY_RUN:
                    stage(stats, 1, '配置及任务链预演', lambda: (None, 'skipped',
                        'DRY_RUN_OK：凭据格式通过；不请求、不续期、不领取、不落盘'))
                else:
                    run_account(AtomCodeClient(account, state), stats, args.query)
                ok = True
            except AtomCodeError as exc:
                log('❌ ' + str(exc))
            except Exception:
                log('❌ 本账号运行异常，详情已隐藏以保护凭据')
            if not ok and not stats['failed']:
                stats['total'] += 1
                stats['failed'] += 1
            result = {'account': i, 'ok': ok, 'tasks': stats, 'elapsed': round(time.monotonic() - account_start, 2)}
            results.append(result)
            log('账号 %d：%s；总任务 %d，成功 %d，已完成 %d，跳过 %d，失败 %d；耗时 %.2f 秒' %
                (i, '预演通过' if ok and DRY_RUN else '成功' if ok else '失败', stats['total'], stats['success'],
                 stats['already_complete'], stats['skipped'], stats['failed'], result['elapsed']))
    except AtomCodeError as exc:
        config_error = True
        log('账号数量：%d；配置错误：%s' % (len(results), str(exc)))
    except Exception:
        config_error = True
        log('账号数量：%d；配置解析失败（敏感详情已隐藏）' % len(results))
    succeeded = sum(r['ok'] for r in results)
    failed = len(results) - succeeded
    exit_code = 1 if config_error or failed or not results else 0
    status = 'configuration-error' if config_error else 'partial-failure' if failed and succeeded else 'failure' if failed else 'dry-run' if DRY_RUN else 'success'
    body = '账号总数 %d，成功 %d，失败 %d；状态 %s' % (len(results), succeeded, failed, status)
    notification = notify_summary(body, no_notify)
    log('------------------------------')
    log(body)
    totals = {key: sum(r['tasks'][key] for r in results) for key in ('total', 'success', 'already_complete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log('通知状态：' + notification)
    finish = datetime.now().isoformat(timespec='seconds')
    log('完成时间：%s；总耗时 %.2f 秒；最终状态：%s' % (finish, time.monotonic() - started, status))
    print('TASK_SUMMARY=' + json.dumps({'applicationKey': 'atomcode', 'status': status,
        'accounts': len(results), 'success': succeeded, 'failed': failed,
        'configurationError': config_error, 'dryRun': DRY_RUN, 'tasks': totals,
        'results': results, 'notification': notification, 'finishTime': finish,
        'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
