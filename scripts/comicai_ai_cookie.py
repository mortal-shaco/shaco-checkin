#!/usr/bin/env python3
# name: ComicAI 每日签到
# cron: 0 9 * * *
# SPDX-License-Identifier: GPL-3.0
# 原始来源：CSDN2024/QianDaoMZH，comicai-ai-cookie.py
# 保留上游 GPL-3.0 许可；源码未提供其他版权声明。
"""ComicAI 每日签到（Python 标准库，无需安装依赖）。

COMICAI_ACCOUNTS：每个非空行一个 JSON 对象，token 必填、cookie 可选。
在 ComicAI 网页登录后，从开发者工具网络请求读取 api.comicai.ai 请求的
Token 请求头，以及 comicai.ai 的 Cookie 请求头。只在本地青龙保存，勿分享。
未设置规范变量时，兼容 comicai_Token / comicai_Cookie，每行对应同一账号。
Cookie 只用于访问原始登录页；API 依旧仅使用 Token，不推断 Cookie 能签到。
COMICAI_DRY_RUN=1 完全断网，仅检查配置并模拟流程，不声称业务成功。
每天 09:00 运行（面板本地时区），原脚本未指定 cron。
QINGLONG_NOTIFY 默认 1；预演也尝试通知，但禁止网络和子进程，联网通知会失败且不影响业务退出码。
"""
import importlib
import importlib.util
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

TITLE = 'ComicAI 每日签到'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.6261.70 Safari/537.36'
SECRETS = []


def enabled(value):
    return str(value).strip().lower() not in ('0', 'false', 'no', 'off', '')


def log(message):
    print(f'[{datetime.now():%H:%M:%S}] {message}', flush=True)


def safe_identity(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value)
    if any(secret and secret in text for secret in SECRETS):
        return None
    if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
        return None
    # 不改变公开身份字符；只拒绝日志控制字符及过长内容。
    if len(text) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        return None
    return text


class TaskError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 防止 Token/Cookie 随重定向流向其他地址。
        return None


def request(url, headers, data=None, json_response=True):
    req = urllib.request.Request(url, data=data, headers=headers)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=15) as response:
            if response.status != 200:
                raise TaskError('HTTP 状态异常')
            body = response.read(262145)
    except urllib.error.HTTPError as exc:
        raise TaskError(f'HTTP 状态 {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TaskError('网络连接失败或超时') from None
    if len(body) > 262144:
        raise TaskError('响应超过大小限制')
    if not json_response:
        return None
    try:
        result = json.loads(body)
    except (ValueError, UnicodeError):
        raise TaskError('响应不是有效 JSON') from None
    if not isinstance(result, dict):
        raise TaskError('响应结构不符合契约')
    return result


def mana_value(result):
    try:
        mana = result['data']['asset']['mana']
    except (KeyError, TypeError):
        raise TaskError('响应缺少积分字段 data.asset.mana') from None
    if isinstance(mana, bool) or not isinstance(mana, (int, float)) or not math.isfinite(mana) or mana < 0:
        raise TaskError('积分字段不是有效非负数值')
    return mana


def account_lines():
    canonical = os.environ.get('COMICAI_ACCOUNTS', '')
    if canonical.strip():
        return [(line, None) for line in canonical.splitlines() if line.strip()], True
    tokens = [s.strip() for s in os.environ.get('comicai_Token', '').splitlines() if s.strip()]
    cookies = [s.strip() for s in os.environ.get('comicai_Cookie', '').splitlines() if s.strip()]
    if cookies and len(cookies) != len(tokens):
        raise TaskError('兼容变量 Cookie 与 Token 的非空行数必须一致')
    return [(token, cookies[i] if cookies else '') for i, token in enumerate(tokens)], False


def parse_account(row, canonical):
    if canonical:
        try:
            account = json.loads(row[0])
        except ValueError:
            raise TaskError('账号行必须是 JSON 对象') from None
        if not isinstance(account, dict):
            raise TaskError('账号行必须是 JSON 对象')
        token, cookie = account.get('token'), account.get('cookie', '')
    else:
        token, cookie = row
    if not isinstance(token, str) or not token.strip() or not isinstance(cookie, str):
        raise TaskError('账号需要非空 token；cookie 必须为字符串')
    token, cookie = token.strip(), cookie.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in token + cookie):
        raise TaskError('凭据含非法控制字符')
    SECRETS.extend([token, cookie])
    return token, cookie


def notify(body, dry):
    if not enabled(os.environ.get('QINGLONG_NOTIFY', '1')):
        log('⏭️ 通知已由 QINGLONG_NOTIFY 关闭')
        return 'disabled'
    try:
        try:
            module = importlib.import_module('notify')
        except ImportError:
            module = None
            paths = []
            directory = os.environ.get('QINGLONG_NOTIFY_DIR')
            if directory:
                paths.append(Path(directory) / 'notify.py')
            paths.extend([Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')])
            for path in paths:
                if path.is_file():
                    spec = importlib.util.spec_from_file_location('qinglong_notify', path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    break
        if module is None or not callable(getattr(module, 'send', None)):
            log('⚠️ 未找到青龙 notify.py，保留业务退出码')
            return 'unavailable'
        # 屏蔽通知器输出，避免其异常或调试输出泄漏运行环境。
        import contextlib
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module.send(TITLE, body)
        log('✅ 已发送脱敏通知')
        return 'sent'
    except BaseException:
        log('⚠️ 通知失败，保留业务退出码')
        return 'failed'


def main():
    started = time.monotonic()
    dry = enabled(os.environ.get('COMICAI_DRY_RUN', '0'))
    if dry:
        def deny_network(event, args):
            if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'):
                raise RuntimeError('断网预演禁止网络和子进程')
        sys.addaudithook(deny_network)
    log('========== ' + TITLE + ' ==========')
    log(f'开始时间：{datetime.now():%Y-%m-%d %H:%M:%S}；模式：' + ('断网预演' if dry else '实际执行'))
    accounts = []
    config_error = False
    try:
        rows, canonical = account_lines()
        if not rows:
            raise TaskError('缺少 COMICAI_ACCOUNTS 或兼容变量 comicai_Token')
    except TaskError as exc:
        rows, canonical = [], True
        config_error = True
        log('❌ 配置错误：' + str(exc))
    log(f'账号数量：{len(rows)}')
    for index, row in enumerate(rows, 1):
        account_start = time.monotonic()
        stats = dict(total=3, success=0, alreadyComplete=0, skipped=0, failed=0)
        failed = False
        stage = 0
        try:
            token, cookie = parse_account(row, canonical)
            headers = {'Token': token, 'User-Agent': UA}
            for stage in (1, 2, 3):
                step_start = time.monotonic()
                label = {1: '访问登录页', 2: '查询签到前积分', 3: '每日签到'}[stage]
                log(f'账号 {index} / 阶段 {stage}/3：{label}')
                if dry:
                    stats['skipped'] += 1
                    log(f'⏭️ 配置有效，模拟{label}；未发出请求；耗时 {time.monotonic()-step_start:.2f}s')
                    continue
                if stage == 1:
                    if cookie:
                        request('https://comicai.ai/signin', {'Cookie': cookie, 'User-Agent': UA}, json_response=False)
                        stats['success'] += 1
                        log('✅ 登录页 HTTP 200（仅页面访问，不作为认证成功证据）')
                    else:
                        stats['skipped'] += 1
                        log('⏭️ 未配置 Cookie，跳过登录页访问')
                elif stage == 2:
                    result = request('https://api.comicai.ai/api/v1/user/info', headers)
                    if result.get('code') != 'Success':
                        raise TaskError('积分查询业务码未确认成功；停止本账号签到')
                    mana = mana_value(result)
                    data = result.get('data', {})
                    for key in ('nickname', 'username', 'displayName', 'display_name', 'uid'):
                        identity = safe_identity(data.get(key))
                        if identity is not None:
                            log(f'账号 {index} 官方身份 {key}：{identity}')
                    log(f'asset_mana-签到前的积分数：{mana}')
                    stats['success'] += 1
                else:
                    result = request('https://api.comicai.ai/api/v1/user/sign', {**headers, 'Content-Type': 'application/json'}, b'{}')
                    if result.get('code') == 'Success':
                        mana = mana_value(result)
                        log(f'✅ 签到成功,签到后得到的积分数 mana 值为: {mana}')
                        stats['success'] += 1
                    elif result.get('code') == 'USER_REPEAT_SIGN':
                        log('☑️ 今天已经签到过了')
                        stats['alreadyComplete'] += 1
                    else:
                        raise TaskError('签到业务码未确认成功')
                log(f'阶段 {stage} 完成；耗时 {time.monotonic()-step_start:.2f}s')
        except TaskError as exc:
            failed = True
            stats['failed'] += 1
            stats['skipped'] += stats['total'] - sum(stats[k] for k in ('success', 'alreadyComplete', 'skipped', 'failed'))
            log(f'❌ 账号 {index} 阶段 {stage}：{exc}；耗时 {time.monotonic()-(step_start if stage else account_start):.2f}s')
        except Exception:
            failed = True
            stats['failed'] += 1
            stats['skipped'] += max(0, stats['total'] - sum(stats[k] for k in ('success', 'alreadyComplete', 'skipped', 'failed')))
            log(f'❌ 账号 {index}：执行异常（已隐藏异常内容）')
        log(f'账号 {index} 统计：总任务 {stats["total"]}，成功 {stats["success"]}，已完成 {stats["alreadyComplete"]}，跳过 {stats["skipped"]}，失败 {stats["failed"]}；耗时 {time.monotonic()-account_start:.2f}s')
        accounts.append({'account': index, 'status': 'failure' if failed else ('dry-run' if dry else 'success'), **stats})
    failures = sum(a['status'] == 'failure' for a in accounts)
    success = sum(a['status'] == 'success' for a in accounts)
    status = 'configuration-error' if config_error else ('partial-failure' if failures and failures < len(accounts) else 'failure' if failures else 'dry-run' if dry else 'success')
    body = f'状态：{status}；账号总数 {len(accounts)}，成功 {success}，失败 {failures}，预演 {sum(a["status"] == "dry-run" for a in accounts)}'
    notification = notify(body, dry)
    log('----------------------------------------')
    log(body)
    totals = {key: sum(a[key] for a in accounts) for key in ('total', 'success', 'alreadyComplete', 'skipped', 'failed')}
    log('子任务统计：' + json.dumps(totals, ensure_ascii=False))
    log(f'完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}；总耗时 {time.monotonic()-started:.2f}s；通知状态 {notification}；最终状态 {status}')
    print('TASK_SUMMARY=' + json.dumps({'task': TITLE, 'mode': 'dry-run' if dry else 'live', 'status': status, 'accountCount': len(accounts), 'successCount': success, 'failureCount': failures, 'accounts': accounts, 'statistics': totals, 'notification': notification}, ensure_ascii=False, separators=(',', ':')))
    return 1 if config_error or failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
