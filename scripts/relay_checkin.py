#!/usr/bin/env python3
# name: Relay 中转站每日签到
# cron: 38 9 * * *
# License: MIT; derived from sstxww/relay-checkin, relay_checkin.py
# Upstream: https://github.com/sstxww/relay-checkin
# Reference tests: sstxww/relay-checkin tests/test_relay_checkin.py
# The supplied upstream files contain no additional copyright/license notice.
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
"""Relay 签到。RELAY_ACCOUNTS 每行 site_id:user_id|Authorization（仅分割首个 |）。
站点使用 RELAY_SITES_JSON（原 sites.json 结构）或 --config 配置；单站点可用
RELAY_BASE_URL，默认 id=example、签到路径=/api/user/checkin。
令牌及 New-Api-User 从本人登录后的浏览器网络面板签到请求头获取，保留令牌前缀。
兼容各站点 access_token_env/user_id_env 指定的旧变量，包括
EXAMPLE_ACCESS_TOKEN / EXAMPLE_USER_ID。不要填写模型调用 API Key。
"""
from __future__ import annotations
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
        _ql_notify_identities = ('b3357f7fc6526506', 'scripts/relay_checkin.py', 'relay_checkin.py', 'relay_checkin')
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
import io
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

VERSION = '0.1.0'
TITLE = 'Relay 中转站每日签到'
ENV_NAME_PATTERN = re.compile(r'^[A-Z_][A-Z0-9_]*$')
SECRETS = set()
MAX_BODY = 1048576


class CheckinError(RuntimeError):
    pass


def safe(value):
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[凭据已隐藏]')
    text = re.sub(r'(?i)(bearer\s+\S+|(?:token|cookie|session|device|authorization)[=:]\S+)', '[敏感字段已隐藏]', text)
    text = re.sub(r'(?<!\d)(?:\+?\d{10,15}|(?:\+\d{1,3}[ -]?)?\d{3}[ -]\d{3}[ -]\d{4}|1\d{2}[ -]\d{4}[ -]\d{4})(?!\d)', '[号码已隐藏]', text)
    return ''.join(c for c in text if c.isprintable())


def log(text):
    print(f'[{time.strftime("%H:%M:%S")}] {safe(text)}', flush=True)


def validate_url(value):
    try:
        p = urlparse(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError()
        _ = p.port
    except (ValueError, TypeError):
        raise CheckinError('站点地址必须是无凭据、无查询参数的 HTTPS 地址') from None


@dataclass(frozen=True)
class SiteConfig:
    site_id: str
    name: str
    homepage: str
    base_url: str
    checkin_path: str
    access_token_env: str
    user_id_env: str
    already_checked_in_messages: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict):
            raise CheckinError('站点配置必须是对象')
        required = ('id', 'name', 'homepage', 'base_url', 'checkin_path', 'access_token_env', 'user_id_env')
        if any(not isinstance(value.get(k), str) or not value[k].strip() for k in required):
            raise CheckinError('站点配置缺少必要字符串字段')
        for key in ('homepage', 'base_url'):
            validate_url(value[key])
        path = value['checkin_path']
        if not path.startswith('/') or path.startswith('//') or '\\' in path or any(ord(c) < 32 for c in path):
            raise CheckinError('签到路径必须是站内绝对路径')
        for key in ('access_token_env', 'user_id_env'):
            if not ENV_NAME_PATTERN.fullmatch(value[key]):
                raise CheckinError('凭据环境变量名无效')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value['id']):
            raise CheckinError('站点标识只能使用字母、数字、下划线、点和短横线')
        markers = value.get('already_checked_in_messages', ['already checked in', '今日已签到'])
        if not isinstance(markers, list) or not all(isinstance(m, str) and m.strip() for m in markers):
            raise CheckinError('重复签到提示必须是非空字符串列表')
        return cls(value['id'], value['name'], value['homepage'], value['base_url'].rstrip('/'), path,
                   value['access_token_env'], value['user_id_env'], tuple(markers))


@dataclass(frozen=True)
class CheckinResult:
    site: SiteConfig
    message: str
    quota_awarded: int | float | None = None
    already_checked_in: bool = False
    identity: str = ''


def load_sites(path):
    try:
        if path is not None:
            payload = json.loads(Path(path).read_text(encoding='utf-8'))
        elif os.environ.get('RELAY_SITES_JSON'):
            payload = json.loads(os.environ['RELAY_SITES_JSON'])
        elif Path(__file__).with_name('sites.json').is_file():
            payload = json.loads(Path(__file__).with_name('sites.json').read_text(encoding='utf-8'))
        else:
            base = os.environ.get('RELAY_BASE_URL', '')
            if not base:
                raise CheckinError('请配置 RELAY_BASE_URL、RELAY_SITES_JSON 或 --config')
            payload = {'sites': [dict(id='example', name='Relay', homepage=base, base_url=base,
                checkin_path='/api/user/checkin', access_token_env='EXAMPLE_ACCESS_TOKEN',
                user_id_env='EXAMPLE_USER_ID')]}
        raw = payload.get('sites') if isinstance(payload, dict) else None
        if not isinstance(raw, list) or not raw:
            raise CheckinError('配置必须包含非空 sites 列表')
        sites = [SiteConfig.from_mapping(v) for v in raw]
        if len({s.site_id for s in sites}) != len(sites):
            raise CheckinError('站点标识重复')
        return sites
    except (OSError, ValueError, TypeError):
        raise CheckinError('站点配置无法读取或 JSON 格式无效') from None


def _required_env(site, environ):
    token = environ.get(site.access_token_env, '').strip()
    uid = environ.get(site.user_id_env, '').strip()
    SECRETS.add(token)
    if not token or not uid:
        raise CheckinError('缺少账号凭据')
    if any(c in token + uid for c in '\r\n'):
        raise CheckinError('单个凭据不能包含换行')
    if not uid.isascii() or not uid.isdecimal():
        raise CheckinError('New-Api-User 必须是数字用户编号')
    try:
        token.encode('latin-1')
    except UnicodeEncodeError:
        raise CheckinError('Authorization 包含无效字符') from None
    return token, uid


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckinError('拒绝签到重定向，防止凭据发送到其他地址')


def check_in(site, environ, timeout=30.0, opener=None):
    token, uid = _required_env(site, environ)
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise CheckinError('超时应为 0 到 120 秒之间的有限数值')
    endpoint = urljoin(site.base_url + '/', site.checkin_path.lstrip('/'))
    request = Request(endpoint, data=b'{}', method='POST', headers={
        'Accept': 'application/json', 'Content-Type': 'application/json',
        'Authorization': token, 'New-Api-User': uid, 'User-Agent': f'relay-checkin/{VERSION}'})
    try:
        with (opener or build_opener(NoRedirect()).open)(request, timeout=timeout) as response:
            status = getattr(response, 'status', 200)
            body = response.read(MAX_BODY + 1)
        if not 200 <= status < 300:
            raise CheckinError(f'HTTP {status}')
        if len(body) > MAX_BODY:
            raise CheckinError('响应过大')
        payload = json.loads(body.decode('utf-8'))
    except HTTPError as exc:
        raise CheckinError(f'HTTP {exc.code}') from None
    except (URLError, OSError, TimeoutError):
        raise CheckinError('网络或超时错误') from None
    except (ValueError, UnicodeError):
        raise CheckinError('响应不是有效 JSON') from None
    if not isinstance(payload, dict):
        raise CheckinError('响应结构无效')
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    identity = ''
    for obj in (data, payload):
        for key in ('nickname', 'username', 'display_name', 'public_uid'):
            if isinstance(obj.get(key), (str, int)) and not isinstance(obj.get(key), bool):
                identity = str(obj[key])
                break
        if identity:
            break
    if payload.get('success') is True:
        quota = data.get('quota_awarded')
        if isinstance(quota, bool) or not isinstance(quota, (int, float)) or not math.isfinite(quota):
            quota = None
        return CheckinResult(site, '签到成功', quota, False, identity)
    message = payload.get('message')
    if isinstance(message, str) and any(m.lower() in message.lower() for m in site.already_checked_in_messages):
        return CheckinResult(site, '今日已签到', None, True, identity)
    raise CheckinError('签到被拒绝：未获得明确成功或已签到结果，请检查账号权限及站点接口')


def select_sites(sites, selected_ids):
    if not selected_ids:
        return list(sites)
    if set(selected_ids) - {s.site_id for s in sites}:
        raise CheckinError('选择了不存在的站点标识')
    return [s for s in sites if s.site_id in selected_ids]


def accounts_for(sites, all_sites, environ):
    # Read and redact all credential values before logging any supplied configuration.
    for s in all_sites:
        SECRETS.add(environ.get(s.access_token_env, ''))
    # Explicit legacy reads also keep the published environment contract importable.
    legacy_token = environ.get('EXAMPLE_ACCESS_TOKEN', '')
    legacy_uid = environ.get('EXAMPLE_USER_ID', '')
    SECRETS.add(legacy_token)
    value = environ.get('RELAY_ACCOUNTS', '')
    if not value.strip():
        return [(s, dict(environ, EXAMPLE_ACCESS_TOKEN=legacy_token, EXAMPLE_USER_ID=legacy_uid), '') for s in sites]
    rows = []
    valid_ids = {s.site_id for s in all_sites}
    chosen = {s.site_id: s for s in sites}
    for line in value.splitlines():
        if not line.strip():
            continue
        left, sep, token = line.strip().partition('|')
        sid, colon, uid = left.partition(':')
        SECRETS.add(token)
        if not sep or not colon or sid not in valid_ids:
            rows.append((None, {}, '账号格式错误或站点标识不存在'))
        elif sid in chosen:
            s = chosen[sid]
            rows.append((s, {s.access_token_env: token, s.user_id_env: uid}, ''))
    if not rows:
        raise CheckinError('所选站点没有配置账号')
    return rows


def notification(body, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').strip().lower()
    if switch in ('0', 'false', 'no', 'off'):
        return '已关闭'
    selection = os.environ.get('QINGLONG_NOTIFY_SCRIPTS')
    if selection is not None:
        selectors = re.split(r'[,;\s]+', selection.strip())
        identities = ('b3357f7fc6526506', 'relay_checkin.py', 'candidate.py', Path(__file__).name,
                      'scripts/relay_checkin.py', 'scripts/candidate.py')
        if not any(fnmatch.fnmatchcase(i, s) for s in selectors if s for i in identities):
            return '未选中'
    elif switch not in ('1', 'true', 'yes', 'on'):
        return '未选中（默认仅通知所选脚本）'
    if dry:
        return '预演已模拟通知，未联网'
    # Notification is optional infrastructure, never a business dependency.
    worker = r'''
import contextlib, importlib, importlib.util, io, json, os, pathlib, subprocess, sys
v=json.load(sys.stdin)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        m=importlib.import_module('notify')
        send=m.send
    except (ImportError, AttributeError):
        send=None
    paths=[pathlib.Path('/ql/data/scripts'), pathlib.Path('/ql/scripts')]
    if os.environ.get('QINGLONG_NOTIFY_DIR'):
        paths.insert(0,pathlib.Path(os.environ['QINGLONG_NOTIFY_DIR']))
    if send is None:
        for p in paths:
            f=p/'notify.py'
            if f.is_file():
                spec=importlib.util.spec_from_file_location('ql_notify',f)
                m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
                send=m.send; break
    if send:
        send(v['title'],v['body'])
    else:
        for p in paths:
            f=p/'sendNotify.js'
            if f.is_file():
                code="let b='';process.stdin.on('data',c=>b+=c);process.stdin.on('end',async()=>{try{const v=JSON.parse(b);await require(process.argv[1]).sendNotify(v.title,v.body)}catch(e){process.exitCode=1}})"
                subprocess.run(['node','-e',code,str(f)],input=json.dumps(v),text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=12,check=True)
                break
        else:
            raise RuntimeError('unavailable')
'''
    try:
        result = subprocess.run([sys.executable, '-c', worker], input=json.dumps({'title': TITLE, 'body': safe(body)}),
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=18, check=False)
        return '已发送' if result.returncode == 0 else '不可用或发送失败（保留业务退出码）'
    except (OSError, subprocess.TimeoutExpired):
        return '不可用或发送超时（保留业务退出码）'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckinError('命令行参数无效，请使用 --help 查看说明')


def build_parser():
    p = Parser(description=__doc__)
    p.add_argument('--config', type=Path, help='站点 JSON 文件，兼容原配置结构')
    p.add_argument('--site', action='append', default=[], help='只运行指定站点，可重复')
    p.add_argument('--timeout', type=float, default=30.0)
    p.add_argument('--list', action='store_true', help='列出站点，不执行签到')
    p.add_argument('--dry-run', action='store_true', help='完全断网预演')
    p.add_argument('--version', action='version', version=VERSION)
    return p


def main(argv: Sequence[str] | None = None):
    started = time.monotonic()
    dry = os.environ.get('RELAY_DRY_RUN', '').lower() in ('1', 'true', 'yes', 'on')
    log(f'========== {TITLE} ==========')
    log(f'开始时间：{time.strftime("%Y-%m-%d %H:%M:%S %z")}')
    total = ok = failed = already = skipped = 0
    code = 0
    status = 'success'
    try:
        args = build_parser().parse_args(argv)
        dry = dry or args.dry_run
        log(f'运行模式：{"断网预演" if dry else "正式"}')
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 120:
            raise CheckinError('超时应为 0 到 120 秒之间的有限数值')
        phase = time.monotonic()
        all_sites = load_sites(args.config)
        sites = select_sites(all_sites, args.site)
        rows = accounts_for(sites, all_sites, os.environ) if not args.list else []
        total = len(rows)
        log(f'阶段 1 配置检查：站点数 {len(sites)}，账号数 {total}，耗时 {time.monotonic()-phase:.2f} 秒')
        if args.list:
            for s in sites:
                print('\t'.join(safe(v) for v in (s.site_id, s.name, s.homepage)))
            status = 'listed'
        for index, (site, env, error) in enumerate(rows, 1):
            tick = time.monotonic()
            account_already = False
            account_ok = False
            try:
                log(f'账号 {index} / {total} · 阶段 2 凭据检查')
                if error:
                    raise CheckinError(error)
                _required_env(site, env)
                log(f'账号 {index} · 阶段 2 完成，耗时 {time.monotonic()-tick:.2f} 秒')
                phase = time.monotonic()
                log(f'账号 {index} · 阶段 3 {"断网预演" if dry else "签到请求"}')
                if dry:
                    log(f'[OK] 账号 {index}：configuration is valid；DRY_RUN_OK；未发送请求')
                    skipped += 1
                else:
                    result = check_in(site, env, args.timeout)
                    account_already = result.already_checked_in
                    identity = f'，身份：{result.identity}' if result.identity else ''
                    quota = f'；quota_awarded={result.quota_awarded}' if result.quota_awarded is not None else ''
                    log(f'[OK] 账号 {index}{identity}：{result.message}{quota}')
                    already += int(account_already)
                log(f'账号 {index} · 阶段 3 完成，耗时 {time.monotonic()-phase:.2f} 秒')
                ok += 1
                account_ok = True
            except CheckinError as exc:
                failed += 1
                log(f'[ERROR] 账号 {index}：{exc}')
            except Exception:
                failed += 1
                log(f'[ERROR] 账号 {index}：执行异常，已隐藏异常内容')
            log(f'账号 {index} 统计：总任务 1，成功 {int(account_ok and not dry and not account_already)}，已完成 {int(account_already)}，跳过 {int(account_ok and dry)}，失败 {int(not account_ok)}，耗时 {time.monotonic()-tick:.2f} 秒')
        code = 1 if failed else 0
        if failed:
            status = 'partial-failure' if ok else 'failure'
        elif dry:
            status = 'dry-run'
    except CheckinError as exc:
        log(f'[ERROR] 配置错误：{exc}')
        code, status = 2, 'configuration-error'
    except Exception:
        log('[ERROR] 配置处理异常，已隐藏异常内容')
        code, status = 2, 'configuration-error'
    log('----------------------------------------')
    body = f'状态 {status}；账号总数 {total}，成功 {ok}，失败 {failed}；成功子任务 {ok-already-skipped}，已完成 {already}，跳过 {skipped}，失败子任务 {failed}'
    notice = notification(body, dry)
    log(body)
    log(f'通知状态：{notice}')
    finish = time.strftime('%Y-%m-%d %H:%M:%S %z')
    log(f'完成时间：{finish}；总耗时 {time.monotonic()-started:.2f} 秒；最终状态：{status}；退出码 {code}')
    print('TASK_SUMMARY=' + json.dumps(dict(status=status, mode='dry-run' if dry else 'live',
        accounts=total, success=ok, failed=failed, tasks=dict(total=total, success=ok-already-skipped,
        alreadyComplete=already, skipped=skipped, failed=failed), notification=notice,
        elapsedSeconds=round(time.monotonic()-started, 3), finishTime=finish, exitCode=code), ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
