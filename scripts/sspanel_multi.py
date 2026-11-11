#!/usr/bin/env python3
# name: SSPanel 多站点签到
# cron: 41 10 * * *
# SPDX-License-Identifier: GPL-3.0
# Based on ElainaMoe/SSPanel-Multi-Checkin, checkin.py
# Upstream: https://github.com/ElainaMoe/SSPanel-Multi-Checkin
# Commit: 1816b58a81202e1305d084f5d50df0e93bfded44
# Distributed under GNU GPL version 3: https://www.gnu.org/licenses/gpl-3.0.html
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3.
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# 沿用现维护发布计划：每日 10:41；上游源码未声明计划。
"""独立 SSPanel 登录签到。SSPANEL_ACCOUNTS 每行：HTTPS站点|邮箱|密码。
只按前两个 | 分隔，密码中的后续 | 保留；账号之间只用换行。
兼容 websites/user_list/pwd_list 三组等长配置，以及当前目录 site/users/pwd。
新变量优先，其次完整本地配置文件，最后旧环境变量。不读取工作流私有路径。
SSPANEL_DRY_RUN=1 完全断网预演；实际运行使用标准库和系统信任证书。
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
        _ql_notify_identities = ('b0a70bb3b0d001db', 'scripts/sspanel_multi.py', 'sspanel_multi.py', 'sspanel_multi')
        _ql_notify_enabled = any(
            _ql_notify_fnmatch.fnmatch(identity, selector)
            for selector in _ql_notify_selectors
            for identity in _ql_notify_identities
        )
    _ql_notify_os.environ["QINGLONG_NOTIFY"] = "1" if _ql_notify_enabled else "0"
# qinglong-notification-policy: end
# 合并 jing5460/SSr-Sign 的账户查询、可选通知与云函数入口；整体 GPL-3.0。
"""独立 SSPanel 签到；原作者 Icrons，2021/3/21，来源 jing5460/SSr-Sign/main.py。
上游许可 MIT，保留原始署名：@Time ： 2021/3/21 12:01；@Auth ： Icrons；@IDE ：PyCharm。

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
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

SSPANEL_ACCOUNTS：每个非空行 HTTPS站点|邮箱|密码，仅分割前两个 |。
站点和账号从所使用的 SSPanel 站点注册/登录页获取，密码从密码管理器获取。
无源码内置凭据，无自动购买、转账、发帖操作。只支持原来的密码登录接口，
不绕过验证码或双因素认证。SSPANEL_DRY_RUN=1 完全断网，通知适配器仅在隔离断网环境中尝试执行。
原脚本未提供 cron；沿用维护版发布计划每日 10:41。兼容云函数 main_handler(event, context)。
"""

import contextlib
import fnmatch
import http.cookiejar
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
from html import unescape
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = 'SSPanel 多站点签到'
CATALOG_ID = 'b0a70bb3b0d001db'
TRUE = {'1', 'true', 'yes', 'on'}
FALSE = {'0', 'false', 'no', 'off'}
MAX_BYTES = 262144
TIMEOUT = 15
LIMIT = 1024 * 1024
APPLICATION_KEY = 'jing5460/ssr-sign::main'


class TaskError(Exception):
    """只携带可公开的固定错误描述。"""


def log(text):
    print(f'[{time.strftime("%H:%M:%S")}] {text}', flush=True)


def block_network():
    def denied(*args, **kwargs):
        raise OSError('dry-run 禁止网络')
    socket.socket = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied


def lines(value):
    return [line for line in value.splitlines() if line.strip()]


def validate_account(url, email, password):
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        raise TaskError('站点地址格式错误') from None
    if (parts.scheme != 'https' or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment
            or any(c.isspace() for c in url)):
        raise TaskError('站点必须是无凭据、查询参数及片段的 HTTPS 地址')
    if not email or '@' not in email or not password:
        raise TaskError('邮箱或密码缺失，或邮箱格式错误')
    return (url.rstrip('/'), email, password)


def load_accounts():
    if 'SSPANEL_ACCOUNTS' in os.environ:
        records = lines(os.environ['SSPANEL_ACCOUNTS'])
        accounts = []
        for record in records:
            fields = record.split('|', 2)
            accounts.append(tuple(fields) if len(fields) == 3 else None)
        return accounts
    files = [Path(name) for name in ('site', 'users', 'pwd')]
    present = [p.is_file() for p in files]
    if any(present):
        if not all(present):
            raise TaskError('兼容配置文件不完整，需要 site、users、pwd 三个文件')
        try:
            values = [p.read_text(encoding='utf-8') for p in files]
        except (OSError, UnicodeError):
            raise TaskError('无法读取兼容配置文件') from None
    else:
        values = [os.environ.get(name, '') for name in ('websites', 'user_list', 'pwd_list')]
    # 旧配置不静默压缩中间空行，以免把其他账号的密码配给错误邮箱。
    groups = [v.splitlines() for v in values]
    if not all(groups) or len({len(g) for g in groups}) != 1:
        raise TaskError('请配置 SSPANEL_ACCOUNTS，或提供行数一致的旧站点、邮箱、密码配置')
    return list(zip(*groups))


def numeric_setting(name, default, low, high):
    try:
        value = float(os.environ.get(name, str(default)))
        if not low <= value <= high:
            raise ValueError
        return value
    except ValueError:
        raise TaskError(f'{name} 必须在 {low} 至 {high} 之间') from None


def origin(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme, p.hostname, p.port or 443


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if origin(req.full_url) != origin(newurl):
            raise TaskError('拒绝跨站或降级重定向')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, base, timeout):
        self.base, self.timeout = base, timeout
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), SafeRedirect())

    def request(self, path='', data=None, expect_json=False, as_text=False):
        if os.environ.get('SSPANEL_DRY_RUN', '').lower() in TRUE:
            raise TaskError('断网预演禁止请求')
        headers = {'User-Agent': 'Mozilla/5.0 SSPanel-Multi-Checkin/1.0',
                   'Referer': self.base + '/user'}
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise TaskError(f'接口 HTTP 状态异常：{response.status}')
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise TaskError('接口响应超过大小上限')
        except urllib.error.HTTPError as exc:
            raise TaskError(f'接口 HTTP 状态异常：{exc.code}') from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise TaskError('网络、证书或超时错误') from None
        if not expect_json:
            return raw.decode('utf-8', errors='replace') if as_text else None
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TaskError('接口未返回有效 JSON，可能需要人工处理站点验证') from None
        if not isinstance(payload, dict):
            raise TaskError('接口 JSON 结构不符合 SSPanel 契约')
        return payload


def succeeded(payload):
    # SSPanel 原接口的业务字段为 ret；HTTP 200 本身不算签到成功。
    value = payload.get('ret')
    return type(value) in (bool, int, str) and value in (True, 1, '1')


def already_done(payload):
    value = payload.get('ret')
    message = payload.get('msg')
    return (value in (0, '0') and isinstance(message, str)
            and bool(re.search(r'今日(?:已经?|已)签到|今天(?:已经?|已)签到|您似乎已经签到|already\s+(?:checked\s*in|signed\s*in)', message, re.I)))


def identity(payload, credentials):
    containers = [payload]
    for key in ('data', 'user'):
        if isinstance(payload.get(key), dict):
            containers.append(payload[key])
    for container in containers:
        for key in ('nickname', 'username', 'display_name', 'displayName', 'public_uid', 'uid'):
            value = container.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            text = str(value)
            # 保留官方公开身份；明确凭据值、邮箱、手机号及控制字符不得进入日志。
            if (not text or any(secret and secret in text for secret in credentials)
                    or '@' in text or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text)
                    or any(ord(c) < 32 or ord(c) == 127 for c in text)):
                continue
            log('官方账号身份：' + text)
            return


def account_info(client, credentials):
    """只读取 editXY 展示字段；查询不可用不推翻已经验证的签到。"""
    page = client.request('/user', as_text=True)
    found = 0
    for key, title in (('Class', '用户等级'), ('Class_Expire', '到期时间'),
                       ('Unused_Traffic', '剩余流量')):
        match = re.search(r'\[\s*"' + key + r'"\s*,\s*"([^"\r\n]*)"\s*\]', page)
        if not match:
            continue
        value = unescape(re.sub(r'<[^>]*>', '', match.group(1))).strip()
        # 不输出原始页面、任意消息、标记属性、邮箱、手机号或疑似密钥。
        patterns = {'Class': r'[\dA-Za-z\u4e00-\u9fff ._-]{1,24}',
                    'Class_Expire': r'[\d\s:/+.TZ-]{1,40}|永久|永不过期',
                    'Unused_Traffic': r'[\d\s.,+-]+(?:[KMGTPEkmgtpe]?[Bb](?:[Ii][Bb])?|字节)?'}
        if (not re.fullmatch(patterns[key], value)
                or any(secret and secret in value for secret in credentials)
                or re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', value)):
            log(f'⏭️ {title}：字段无法安全展示')
            continue
        log(f'{title}：{value}')
        found += 1
    return found


def run_account(index, record, dry, timeout, delay):
    started = time.monotonic()
    stats = {'total': 4, 'success': 0, 'alreadyComplete': 0, 'skipped': 0, 'failure': 0}
    stage = 0
    tick = started
    try:
        if record is None:
            raise TaskError('账号行必须包含站点、邮箱和密码三个字段')
        base, email, password = validate_account(*record)
        client = None if dry else Client(base, timeout)
        for stage, title in enumerate(('站点预热与连接验证', '账号登录', '每日签到', '查询账户信息（editXY）'), 1):
            tick = time.monotonic()
            log(f'账号 {index} 阶段 {stage}/4：{title}')
            if dry:
                log(f'⏭️ 账号 {index} 阶段 {stage} 配置有效；断网预演，不发送请求（耗时 {time.monotonic()-tick:.2f} 秒）')
                stats['skipped'] += 1
                continue
            if stage == 1:
                client.request()
                time.sleep(delay)
                client.request()
            elif stage == 2:
                payload = client.request('/auth/login', {'email': email, 'passwd': password, 'code': ''}, True)
                if not succeeded(payload):
                    raise TaskError('登录业务结果失败或无法确认，不执行签到')
                identity(payload, (email, password))
            elif stage == 3:
                payload = client.request('/user/checkin', {}, True)
                identity(payload, (email, password))
                if already_done(payload):
                    stats['alreadyComplete'] += 1
                    log(f'☑️ 账号 {index} 今日已签到（耗时 {time.monotonic()-tick:.2f} 秒）')
                    continue
                if not succeeded(payload):
                    raise TaskError('签到业务结果失败或无法确认')
            else:
                try:
                    found = account_info(client, (email, password))
                    if not found:
                        stats['skipped'] += 1
                        log(f'⏭️ 账号 {index} 未提供可展示的 editXY 字段（耗时 {time.monotonic()-tick:.2f} 秒）')
                        continue
                    log(f'账号 {index} 已读取 {found}/3 项账户信息')
                except Exception:
                    stats['skipped'] += 1
                    log(f'⚠️ 账号 {index} 信息查询不可用，保留已验证签到结果（耗时 {time.monotonic()-tick:.2f} 秒）')
                    continue
            stats['success'] += 1
            log(f'✅ 账号 {index} 阶段 {stage} 已验证成功（耗时 {time.monotonic()-tick:.2f} 秒）')
        ok = True
    except Exception as exc:
        ok = False
        stats['failure'] += 1
        stats['skipped'] = stats['total'] - stats['success'] - stats['alreadyComplete'] - stats['failure']
        reason = str(exc) if isinstance(exc, TaskError) else '执行异常，已隐藏详情'
        log(f'❌ 账号 {index} 阶段 {stage}/4：{reason}；后续阶段跳过（耗时 {time.monotonic()-tick:.2f} 秒）')
    log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failure"]}，耗时 {time.monotonic()-started:.2f} 秒')
    return ok, stats


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # 不向重定向目标转发账号、密码或通知密钥。
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def notification_client():
    return urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def notification_request(opener, url, data=None, headers=None, as_json=True, raw=False):
    if os.environ.get("SSPANEL_DRY_RUN", "").lower() in TRUE:
        raise TaskError("断网预演禁止请求")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise TaskError("请求地址必须为无内嵌凭据的 HTTPS 地址")
    body = data if raw else (urllib.parse.urlencode(data).encode() if data is not None else None)
    request_headers = {"User-Agent": "SSPanel-Qinglong/1.0"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=request_headers)
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            content = response.read(LIMIT + 1)
        if len(content) > LIMIT:
            raise TaskError("响应超过大小限制")
        text = content.decode("utf-8")
        return json.loads(text) if as_json else text
    except TaskError:
        raise
    except urllib.error.HTTPError as exc:
        raise TaskError(f"HTTP 请求失败（状态码 {exc.code}，不自动重试）") from None
    except Exception:
        raise TaskError("请求失败：网络、超时或响应格式异常") from None


def legacy_notify(body):
    """保留原五个可选渠道；独立密钥仍为可选配置。"""
    jobs = []
    env = os.environ
    if env.get("SendKey"):
        jobs.append(("Server酱", "https://sctapi.ftqq.com/" + urllib.parse.quote(env["SendKey"], safe="") + ".send",
                     {"text": TITLE, "desp": body}, lambda p: p.get("code") == 0))
    if env.get("ktkey"):
        jobs.append(("酷推", "https://push.xuthus.cc/send/" + urllib.parse.quote(env["ktkey"], safe=""),
                     body.encode(), lambda p: p.get("code") == 200))
    if env.get("QmsgKey"):
        jobs.append(("Qmsg", "https://qmsg.zendee.cn/send/" + urllib.parse.quote(env["QmsgKey"], safe=""),
                     {"msg": body}, lambda p: p.get("success") is True))
    if env.get("tele_bot_token"):
        jobs.append(("Telegram", env.get("tele_api_url", "https://api.telegram.org").rstrip("/") +
                     "/bot" + urllib.parse.quote(env["tele_bot_token"], safe=":") + "/sendMessage",
                     {"chat_id": env.get("tele_user_id", ""), "text": body}, lambda p: p.get("ok") is True))
    if env.get("push_token"):
        jobs.append(("Pushplus", "https://www.pushplus.plus/send",
                     {"token": env["push_token"], "title": TITLE, "content": body}, lambda p: p.get("code") == 200))
    statuses = []
    for name, url, data, check in jobs:
        try:
            headers = None
            if name == "Pushplus":
                data = json.dumps(data).encode("utf-8")
                headers = {"Content-Type": "application/json"}
            payload = notification_request(notification_client(), url, data, headers=headers, raw=isinstance(data, bytes))
            state = "已发送" if isinstance(payload, dict) and check(payload) else "未获成功确认"
            statuses.append(name + "：" + state)
            log(f"{name} 通知：" + state)
        except Exception:
            statuses.append(name + "：失败")
            log(f"{name} 通知失败（详情已隐藏，不改变业务退出码）")
    return "；".join(statuses)


def notification_worker():
    # 独立进程限制通知插件耗时、隔离其输出；断网预演同时禁止插件启动外部进程。
    body = sys.stdin.read()
    dry = os.environ.get('SSPANEL_DRY_RUN', '').lower() in TRUE
    if dry:
        block_network()
        def denied(*args, **kwargs):
            raise OSError('dry-run 禁止子进程')
        subprocess.Popen = denied
        os.system = denied
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
        paths = []
        if os.environ.get('QINGLONG_NOTIFY_DIR'):
            paths.append(Path(os.environ['QINGLONG_NOTIFY_DIR']) / 'notify.py')
        paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
        if module is None:
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('ql_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is not None and callable(getattr(module, 'send', None)):
            module.send(TITLE, body)
            return 0
        if not dry:
            js_paths = [p.with_name('sendNotify.js') for p in paths]
            for path in js_paths:
                if path.is_file():
                    code = 'const fs=require("fs");const n=require(process.argv[1]);Promise.resolve(n.sendNotify(process.argv[2],fs.readFileSync(0,"utf8"))).catch(()=>process.exit(1));'
                    return subprocess.run(['node', '-e', code, str(path), TITLE], input=body,
                                          text=True, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, timeout=15).returncode
    return 3


def notify(body, dry):
    switch = os.environ.get('QINGLONG_NOTIFY', 'auto').lower()
    if switch in FALSE:
        return '已关闭'
    if switch not in TRUE | {'auto'}:
        return '通知开关无效，未发送'
    if switch == 'auto' and 'QINGLONG_NOTIFY_SCRIPTS' in os.environ:
        selectors = re.split(r'[,;\s]+', os.environ['QINGLONG_NOTIFY_SCRIPTS'].strip())
        names = [CATALOG_ID, 'a5843af909a36789', 'checkin.py', 'sspanel_multi.py',
                 'scripts/sspanel_multi.py', 'task_a5843af9.py', 'scripts/task_a5843af9.py',
                 Path(__file__).name, Path(__file__).as_posix()]
        for root in ('/ql/data/scripts', '/ql/scripts'):
            try:
                names.append(Path(__file__).resolve().relative_to(root).as_posix())
            except ValueError:
                pass
        if not any(fnmatch.fnmatch(name, pattern) for pattern in selectors if pattern for name in names):
            return '未在通知选择列表中'
    # 本候选属于默认列出的定时账号任务；显式选择列表替换该默认。
    optional = legacy_notify(body) if not dry else ""
    suffix = ("；" + optional) if optional else ""
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--notify-worker'],
                                input=body, text=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20)
        if result.returncode == 0:
            return '断网通知适配器已执行' if dry else '青龙已发送' + suffix
        return '断网预演未投递（通知不可用或网络被禁止）' if dry else '青龙通知不可用或发送失败' + suffix
    except (OSError, subprocess.TimeoutExpired):
        return '通知不可用或超时' + suffix


def main():
    started = time.monotonic()
    dry = os.environ.get('SSPANEL_DRY_RUN', '').lower() in TRUE
    log('========== ' + TITLE + ' ==========')
    log('开始时间：' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('运行模式：' + ('断网预演' if dry else '实际签到'))
    accounts, results = [], []
    config_error = False
    try:
        accounts = load_accounts()
        if not accounts:
            raise TaskError('账号列表为空')
        timeout = numeric_setting('SSPANEL_TIMEOUT', 20, 1, 120)
        delay = numeric_setting('SSPANEL_WARMUP_SECONDS', 10, 0, 60)
        log(f'账号数量：{len(accounts)}')
        for index, record in enumerate(accounts, 1):
            results.append(run_account(index, record, dry, timeout, delay))
    except TaskError as exc:
        config_error = True
        log(f'账号数量：{len(accounts)}')
        log('❌ 配置错误：' + str(exc))
    except Exception:
        config_error = True
        log(f'账号数量：{len(accounts)}；❌ 配置读取失败，已隐藏详情')
    successful = sum(ok for ok, stats in results)
    failed = len(accounts) - successful
    exit_code = 1 if config_error or failed else 0
    status = ('configuration-error' if config_error else
              'partial-failure' if failed and successful else
              'failure' if failed else 'dry-run' if dry else 'success')
    totals = {key: sum(stats[key] for ok, stats in results)
              for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failure')}
    body = f'状态：{status}；账号总数 {len(accounts)}，成功 {successful}，失败 {failed}；配置错误 {int(config_error)}。'
    if dry:
        body += ' 断网预演，成功数仅表示参数检查通过，未实际签到。'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'通知状态：{notification}；总耗时 {time.monotonic()-started:.2f} 秒')
    log('完成时间：' + time.strftime('%Y-%m-%d %H:%M:%S') + '；最终状态：' + status)
    print('TASK_SUMMARY=' + json.dumps({'applicationKey': APPLICATION_KEY, 'status': status,
          'dryRun': dry, 'accounts': len(accounts), 'success': successful, 'failure': failed,
          'configurationError': config_error, 'tasks': totals, 'notification': notification,
          'exitCode': exit_code}, ensure_ascii=False, separators=(',', ':')), flush=True)
    return exit_code


def main_handler(event, context):
    return {'exitCode': main()}


if __name__ == '__main__':
    if sys.argv[1:] == ['--notify-worker']:
        try:
            sys.exit(notification_worker())
        except Exception:
            sys.exit(1)
    sys.exit(main())
